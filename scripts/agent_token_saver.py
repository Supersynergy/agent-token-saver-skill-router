#!/usr/bin/env python3
"""Adaptive token-saving skill router.

Python stdlib only. Works as a small CLI helper for Hermes, Claude Code,
Codex CLI, OpenCode, Cursor, Windsurf, and repo-local agents.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

SKILL_NAME = "agent-token-saver-skill-router"
# Legacy in-context controllers may call this router again and recursively load
# more skills. Keep them explicit-only; normal fuzzy routing selects a domain
# skill directly.
AUTO_ROUTE_EXCLUDED = {
    SKILL_NAME,
    "just-in-time-skill-router",
    "sm",
    # Context-mode is a deliberate heavy/session layer. Its broad trigger list
    # must not make ordinary test or log tasks pay to load its full handbook.
    "context-mode",
}
ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILL = ROOT / "SKILL.md"
WORD_RE = re.compile(r"[a-zA-Z0-9+]{2,}")
EXPLICIT_SKILL_RE = re.compile(r"\$([a-zA-Z0-9_:+.-]+)")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "make",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "use",
    "using",
    "with",
    "without",
    "what",
    "your",
    "builder",
}
TOKEN_NORMALIZATION = {
    "contexts": "context",
    "tests": "test",
    "testing": "test",
    "pytest": "test",
    "debugging": "debug",
    "debugger": "debug",
    "failing": "fail",
    "failed": "fail",
    "failure": "fail",
    "failures": "fail",
    "memories": "memory",
    "optimized": "optimize",
    "optimizing": "optimize",
    "optimization": "optimize",
    "outputs": "output",
    "subagents": "subagent",
    "tokens": "token",
    "tools": "tool",
}
PLATFORM_TOKENS = {
    "python",
    "node",
    "nodejs",
    "javascript",
    "typescript",
    "rust",
    "golang",
    "go",
}
SECURITY_TOKENS = {
    "auth",
    "authentication",
    "authorization",
    "owasp",
    "secret",
    "secrets",
    "secure",
    "security",
    "vulnerability",
    "vulnerabilities",
}
REVIEW_TOKENS = {"audit", "review", "regression", "regressions"}
TOKEN_CONTEXT_TOKENS = {
    "context",
    "memory",
    "router",
    "routing",
    "saving",
    "skill",
    "stack",
    "token",
}
WORKFLOW_TOKENS = {
    "analyze",
    "audit",
    "benchmark",
    "build",
    "code",
    "compress",
    "condense",
    "create",
    "cut",
    "debug",
    "deploy",
    "design",
    "edit",
    "explain",
    "fail",
    "fix",
    "implement",
    "install",
    "minimize",
    "optimize",
    "plan",
    "readme",
    "reduce",
    "refactor",
    "release",
    "research",
    "review",
    "route",
    "save",
    "scrape",
    "search",
    "shrink",
    "test",
    "trim",
    "write",
}
EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "target",
    ".venv",
    "venv",
    "__pycache__",
    ".archive",
    "_archive",
    "runs",
}
NOISE_NAME_RE = re.compile(
    r"(\.bak(?:$|[-._])|\.old$|\.disabled$|[-._]backup(?:$|[-._0-9])|[-._]deprecated$)",
    re.IGNORECASE,
)
FLAT_SKILL_SKIP = {"readme.md", "changelog.md", "license.md", "contributing.md"}
DEFAULT_FAVORITE_BOOST = 6
DEFAULT_MAX_SELECTED = 1
MAX_SELECTED = 10
MIN_STRICT_SCORE = 8
MIN_STRICT_MARGIN = 3
INDEX_SCHEMA = 1
DEFAULT_INDEX_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    keywords: str
    path: str
    root: str


@dataclass(frozen=True)
class RouteResult:
    intent: str
    selected: list[Skill]
    scanned: int
    roots: list[str]
    router_block: str
    catalog_source: str = "scan"


@dataclass(frozen=True)
class Catalog:
    skills: list[Skill]
    roots: list[Path]
    source: str
    index_path: Path


@lru_cache(maxsize=8192)
def words(text: str) -> frozenset[str]:
    tokens: set[str] = set()
    for raw in WORD_RE.findall(text or ""):
        lowered = raw.lower()
        if lowered in STOPWORDS:
            continue
        tokens.add(TOKEN_NORMALIZATION.get(lowered, lowered))
        if lowered == "pytest":
            tokens.add("python")
    return frozenset(tokens)


def favorites_file() -> Path:
    env = os.getenv("AGENT_SKILL_FAVORITES_FILE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".agents" / "skill-favorites.txt"


def load_favorites() -> dict[str, int]:
    """User-pinned skills that win close calls. One `name` or `name=weight` per line."""
    favorites: dict[str, int] = {}
    try:
        text = favorites_file().read_text(encoding="utf-8")
    except OSError:
        return favorites
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, weight_raw = line.partition("=")
        weight = DEFAULT_FAVORITE_BOOST
        if sep:
            try:
                weight = int(weight_raw.strip())
            except ValueError:
                weight = DEFAULT_FAVORITE_BOOST
        favorites[name.strip().lower()] = weight
    return favorites


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def selection_limit(value: int) -> int:
    """Keep stacks bounded even for callers that bypass the CLI."""
    return max(1, min(value, MAX_SELECTED))


def parse_frontmatter(path: Path) -> tuple[str, str, str]:
    with path.open(encoding="utf-8", errors="ignore") as handle:
        if handle.readline().strip() != "---":
            return path.parent.name, "", ""
        frontmatter: list[str] = []
        size = 0
        for line in handle:
            if line.rstrip("\r\n") == "---":
                break
            size += len(line)
            if size > 65_536:
                return path.parent.name, "", ""
            frontmatter.append(line)
        else:
            return path.parent.name, "", ""
    fm = "".join(frontmatter)
    name = ""
    desc = ""
    tags = ""
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip("\"'")
        elif line.startswith("description:"):
            raw = line.split(":", 1)[1].strip()
            if raw in {">-", ">", "|-", "|"}:
                tail = []
                for nxt in lines[i + 1 :]:
                    if re.match(r"^[A-Za-z0-9_.-]+:\s*", nxt):
                        break
                    tail.append(nxt.strip())
                desc = " ".join(x for x in tail if x).strip()
            else:
                desc = raw.strip("\"'")
        elif line.strip().startswith("tags:"):
            raw = line.split(":", 1)[1].strip()
            tags = " ".join(WORD_RE.findall(raw))
    return name or path.parent.name, desc, tags


def looks_like_flat_skill(path: Path) -> bool:
    if path.name.lower() in FLAT_SKILL_SKIP or path.suffix.lower() != ".md":
        return False
    if NOISE_NAME_RE.search(path.stem):
        return False
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            start = handle.read(512)
    except OSError:
        return False
    return start.startswith("---") and "\nname:" in start


def common_roots(cwd: Path | None = None) -> list[Path]:
    home = Path.home()
    cwd = cwd or Path.cwd()
    candidates = [
        cwd / ".agents" / "skills",
        cwd / ".claude" / "skills",
        cwd / ".codex" / "skills",
        home / ".agents" / "skills",
        home / ".hermes" / "skills",
        home / ".claude" / "skills",
        home / ".claude" / "cts" / "skills",
        home / ".codex" / "skills",
        home / ".codex" / "plugins" / "cache",
        home / ".gg" / "skills",
        home / ".opencode" / "skills",
        home / ".cursor" / "skills",
        home / ".windsurf" / "skills",
    ]
    extra = os.getenv("AGENT_SKILL_DIRS", "")
    for part in extra.split(os.pathsep):
        if part.strip():
            candidates.append(Path(part).expanduser())
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        try:
            rp = p.expanduser().resolve()
        except OSError:
            continue
        key = str(rp)
        if key not in seen and rp.exists():
            seen.add(key)
            out.append(rp)
    return out


def skill_index_file() -> Path:
    override = os.getenv("AGENT_SKILL_INDEX", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "agent-token-saver" / "skills-index.json"


def skill_index_tsv_file(index_path: Path | None = None) -> Path:
    override = os.getenv("AGENT_SKILL_INDEX_TSV", "").strip()
    if override:
        return Path(override).expanduser()
    return (index_path or skill_index_file()).with_name("skills.idx")


def skill_index_ttl_seconds() -> float:
    raw = os.getenv("AGENT_SKILL_INDEX_TTL", "").strip()
    if not raw:
        return DEFAULT_INDEX_TTL_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_INDEX_TTL_SECONDS


def iter_skill_files(root: Path, max_files: int) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in EXCLUDE_DIRS and not NOISE_NAME_RE.search(d)
        )
        if "SKILL.md" in filenames:
            yield Path(dirpath) / "SKILL.md"
            count += 1
            if count >= max_files:
                return
        if Path(dirpath) == root:
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                if looks_like_flat_skill(path):
                    yield path
                    count += 1
                    if count >= max_files:
                        return


def scan(
    roots: list[Path] | None = None, max_files_per_root: int = 1000
) -> list[Skill]:
    roots = roots or common_roots()
    skills: list[Skill] = []
    seen_names: set[str] = set()
    for root in roots:
        for path in iter_skill_files(root, max_files_per_root):
            try:
                name, desc, tags = parse_frontmatter(path)
            except OSError:
                continue
            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            skills.append(
                Skill(
                    name=name,
                    description=desc,
                    keywords=tags,
                    path=str(path),
                    root=str(root),
                )
            )
    return skills


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_skill_index(
    skills: list[Skill], roots: list[Path], path: Path | None = None
) -> None:
    path = path or skill_index_file()
    payload = {
        "schema": INDEX_SCHEMA,
        "generated_at": time.time(),
        "roots": [str(root) for root in roots],
        "skills": [asdict(skill) for skill in skills],
    }
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
    )
    rows = []
    for skill in sorted(skills, key=lambda item: item.name.lower()):
        fields = (
            skill.name.replace("\t", " ").replace("\n", " "),
            skill.description.replace("\t", " ").replace("\n", " "),
            skill.path.replace("\t", " ").replace("\n", " "),
        )
        rows.append("\t".join(fields))
    atomic_write_text(
        skill_index_tsv_file(path), "\n".join(rows) + ("\n" if rows else "")
    )


def read_skill_index(
    roots: list[Path], path: Path | None = None, ttl_seconds: float | None = None
) -> list[Skill] | None:
    path = path or skill_index_file()
    ttl_seconds = skill_index_ttl_seconds() if ttl_seconds is None else ttl_seconds
    try:
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw_skills = payload.get("skills")
    if payload.get("schema") != INDEX_SCHEMA:
        return None
    if payload.get("roots") != [str(root) for root in roots]:
        return None
    if not isinstance(raw_skills, list) or not all(
        isinstance(item, dict) and {"name", "path", "root"} <= item.keys()
        for item in raw_skills
    ):
        return None
    return [
        Skill(
            name=str(item["name"]),
            description=str(item.get("description", "")),
            keywords=str(item.get("keywords", "")),
            path=str(item["path"]),
            root=str(item["root"]),
        )
        for item in raw_skills
    ]


def load_catalog(
    roots: list[Path] | None = None,
    *,
    refresh: bool = False,
    use_index: bool | None = None,
) -> Catalog:
    resolved_roots = list(roots) if roots is not None else common_roots()
    if use_index is None:
        use_index = roots is None
    index_path = skill_index_file()
    if use_index and not refresh:
        cached = read_skill_index(resolved_roots, index_path)
        if cached is not None:
            return Catalog(cached, resolved_roots, "cache", index_path)
    skills = scan(resolved_roots)
    if use_index:
        try:
            write_skill_index(skills, resolved_roots, index_path)
            source = "rebuilt"
        except OSError:
            source = "scan"
    else:
        source = "scan"
    return Catalog(skills, resolved_roots, source, index_path)


def doc_frequencies(skills: list[Skill]) -> Counter:
    df: Counter = Counter()
    for skill in skills:
        for token in (
            words(skill.name.replace("-", " "))
            | words(skill.description)
            | words(skill.keywords)
        ):
            df[token] += 1
    return df


def rarity(token: str, doc_freq: Counter | None) -> float:
    """Down-weight tokens that match many skills; specific tokens dominate."""
    if not doc_freq:
        return 1.0
    df = doc_freq.get(token, 1)
    if df <= 2:
        return 1.0
    if df <= 8:
        return 0.5
    return 0.25


def contains_bounded_phrase(text: str, phrase: str) -> bool:
    start = 0
    while True:
        index = text.find(phrase, start)
        if index < 0:
            return False
        end = index + len(phrase)
        before_ok = index == 0 or not (
            text[index - 1].isalnum() or text[index - 1] in "_+-"
        )
        after_ok = end == len(text) or not (text[end].isalnum() or text[end] in "_+-")
        if before_ok and after_ok:
            return True
        start = index + 1


def score(
    intent: str,
    skill: Skill,
    doc_freq: Counter | None = None,
    favorites: dict[str, int] | None = None,
) -> int:
    iw = words(intent)
    nw = words(skill.name.replace("-", " "))
    dw = words(skill.description)
    kw = words(skill.keywords)
    if not iw:
        return 0
    s = 0.0
    for token in iw & nw:
        s += 8 * rarity(token, doc_freq)
    for token in iw & dw:
        s += 3 * rarity(token, doc_freq)
    for token in iw & kw:
        s += 6 * rarity(token, doc_freq)
    # Coverage: a skill matching several intent tokens must outrank a skill
    # that hit one lucky rare token (e.g. "builder" in an unrelated name).
    matched = (iw & nw) | (iw & dw) | (iw & kw)
    if len(matched) > 1:
        s += 4 * (len(matched) - 1)
    lowered = intent.lower()
    skill_phrase = skill.name.lower()
    # A generic one-word platform name such as "codex" is usually context,
    # not an explicit request to delegate to that skill. Bare names and
    # `$skill` are already resolved exactly in route().
    if "-" in skill.name and contains_bounded_phrase(lowered, skill_phrase):
        s += 20
    for token in iw:
        if token in skill.path.lower():
            s += 1 * rarity(token, doc_freq)
    is_software_dev = "/software-development/" in skill.path
    skill_words = nw | dw | kw
    test_debug_intent = iw & {"debug", "test", "fail"}
    if is_software_dev and test_debug_intent & skill_words:
        s += 20
    if is_software_dev and "python" in iw and "python" in (nw | dw | kw):
        s += 12
    # Security review is a closed local-code task. Prefer skills that actually
    # cover security/review; a generic web/API skill must not win on "api".
    if iw & SECURITY_TOKENS and skill_words & SECURITY_TOKENS:
        s += 20
    if iw & REVIEW_TOKENS and skill_words & (SECURITY_TOKENS | REVIEW_TOKENS):
        s += 12
    # When a request clearly clusters around token/context infrastructure,
    # reject accidental matches such as ML skills that only mention "memory"
    # or "accuracy". Require the candidate itself to cover the domain broadly.
    if len(iw & TOKEN_CONTEXT_TOKENS) >= 2:
        domain_coverage = len(skill_words & TOKEN_CONTEXT_TOKENS)
        if domain_coverage >= 2:
            s += 12
        elif domain_coverage == 0:
            s -= 12
    skill_platforms = (nw | dw | kw) & PLATFORM_TOKENS
    requested_platforms = iw & PLATFORM_TOKENS
    if (
        skill_platforms
        and requested_platforms
        and not (skill_platforms & requested_platforms)
    ):
        s -= 8
    if s > 0 and favorites and ((iw & nw) or (iw & kw)):
        # Cap the boost at the base score: favorites win close calls but a
        # barely-matching favorite can never bury a strong specific match.
        s += min(float(favorites.get(skill.name.lower(), 0)), s)
    return round(s)


def route(
    intent: str,
    max_selected: int = DEFAULT_MAX_SELECTED,
    roots: list[Path] | None = None,
    strict: bool = False,
    refresh_index: bool = False,
    catalog_data: Catalog | None = None,
) -> RouteResult:
    max_selected = selection_limit(max_selected)
    catalog_data = catalog_data or load_catalog(roots, refresh=refresh_index)
    skills = catalog_data.skills
    root_paths = catalog_data.roots
    favorites = load_favorites()
    by_name = {
        skill.name.lower(): skill for skill in skills if skill.name != SKILL_NAME
    }
    explicit_names = [name.lower() for name in EXPLICIT_SKILL_RE.findall(intent)]
    bare_name = intent.strip().lower()
    if not explicit_names and bare_name in by_name:
        explicit_names = [bare_name]
    if explicit_names:
        selected = []
        for name in explicit_names:
            skill = by_name.get(name)
            if skill is not None and skill not in selected:
                selected.append(skill)
        selected = selected[:max_selected]
        block = render_router_block(
            intent, selected, len(skills), root_paths, favorites
        )
        return RouteResult(
            intent=intent,
            selected=selected,
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
        )
    intent_words = words(intent)
    if not (intent_words & WORKFLOW_TOKENS):
        block = render_router_block(intent, [], len(skills), root_paths, favorites)
        return RouteResult(
            intent=intent,
            selected=[],
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
        )
    routable_skills = [
        skill for skill in skills if skill.name not in AUTO_ROUTE_EXCLUDED
    ]
    doc_freq = doc_frequencies(routable_skills)
    ranked = sorted(
        ((score(intent, s, doc_freq, favorites), s) for s in routable_skills),
        key=lambda x: (
            -x[0],
            0 if x[1].name.lower() in favorites else 1,
            x[1].name,
        ),
    )
    if intent_words & SECURITY_TOKENS and intent_words & REVIEW_TOKENS:
        review_ranked = []
        for points, skill in ranked:
            skill_words = (
                words(skill.name.replace("-", " "))
                | words(skill.description)
                | words(skill.keywords)
            )
            if skill_words & REVIEW_TOKENS and skill_words & SECURITY_TOKENS:
                review_ranked.append((points, skill))
        if review_ranked:
            ranked = review_ranked
    positive = [(points, skill) for points, skill in ranked if points > 0]
    if strict:
        if not positive or positive[0][0] < MIN_STRICT_SCORE:
            positive = []
        elif len(positive) > 1 and positive[0][0] - positive[1][0] < MIN_STRICT_MARGIN:
            positive = []
    confidence_floor = max(4, round(positive[0][0] * 0.33)) if positive else 0
    selected = [skill for points, skill in positive if points >= confidence_floor][
        :max_selected
    ]
    block = render_router_block(intent, selected, len(skills), root_paths, favorites)
    return RouteResult(
        intent=intent,
        selected=selected,
        scanned=len(skills),
        roots=[str(p) for p in root_paths],
        router_block=block,
        catalog_source=catalog_data.source,
    )


def render_router_block(
    intent: str,
    selected: list[Skill],
    scanned: int,
    roots: list[Path],
    favorites: dict[str, int] | None = None,
) -> str:
    lines = [f"router: {SKILL_NAME}", f"intent: {intent}", f"scanned: {scanned}"]
    if selected:
        lines.append("load:")
        for s in selected:
            star = " ★" if favorites and s.name.lower() in favorites else ""
            lines.append(f"- {s.name}{star}: {s.description[:160]} ({s.path})")
    else:
        lines.append("load: []")
    return "\n".join(lines)


def full_catalog_text(skills: list[Skill]) -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)


def bench(
    intent: str,
    max_selected: int = DEFAULT_MAX_SELECTED,
    refresh_index: bool = False,
) -> dict[str, object]:
    catalog_data = load_catalog(refresh=refresh_index)
    skills = catalog_data.skills
    rr = route(intent, max_selected=max_selected, catalog_data=catalog_data)
    full = full_catalog_text(skills)
    router = rr.router_block
    full_tokens = estimate_tokens(full)
    router_tokens = estimate_tokens(router)
    saved = full_tokens - router_tokens
    pct = round((saved / full_tokens * 100), 2) if full_tokens else 0.0
    return {
        "intent": intent,
        "catalog_source": catalog_data.source,
        "index_path": str(catalog_data.index_path),
        "skills_scanned": len(skills),
        "full_chars": len(full),
        "full_est_tokens": full_tokens,
        "router_chars": len(router),
        "router_est_tokens": router_tokens,
        "saved_est_tokens": saved,
        "reduction_pct": pct,
        "selected": [asdict(s) for s in rr.selected],
    }


def find_skills(
    query: str, skills: list[Skill], limit: int = 8
) -> list[tuple[int, Skill]]:
    limit = max(1, min(limit, 50))
    normalized = query.strip().lstrip("$").lower()
    frequencies = doc_frequencies(skills)
    ranked: list[tuple[int, Skill]] = []
    for skill in skills:
        if skill.name == SKILL_NAME:
            continue
        points = score(query, skill, frequencies)
        if skill.name.lower() == normalized:
            points += 1000
        elif normalized and normalized in skill.name.lower():
            points += 20
        if points > 0:
            ranked.append((points, skill))
    return sorted(ranked, key=lambda item: (-item[0], item[1].name.lower()))[:limit]


def resolve_skill(name: str, skills: list[Skill]) -> Skill | None:
    normalized = name.strip().lstrip("$").lower()
    return next((skill for skill in skills if skill.name.lower() == normalized), None)


def catalog_summary(catalog_data: Catalog) -> dict[str, object]:
    return {
        "status": catalog_data.source,
        "skills": len(catalog_data.skills),
        "roots": [str(root) for root in catalog_data.roots],
        "index_path": str(catalog_data.index_path),
        "tsv_path": str(skill_index_tsv_file(catalog_data.index_path)),
        "ttl_seconds": skill_index_ttl_seconds(),
    }


def source_skill_file() -> Path:
    home = Path.home()
    candidates = [
        ROOT_SKILL,
        home / ".codex" / "skills" / SKILL_NAME / "SKILL.md",
        home / ".claude" / "skills" / SKILL_NAME / "SKILL.md",
        home / ".hermes" / "skills" / "metaskills" / SKILL_NAME / "SKILL.md",
        home / ".gg" / "skills" / f"{SKILL_NAME}.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("router SKILL.md source not found")


def install(target: str, dry_run: bool = False) -> list[str]:
    home = Path.home()
    targets = {
        "hermes": home / ".hermes" / "skills" / "metaskills" / SKILL_NAME / "SKILL.md",
        "claude": home / ".claude" / "skills" / SKILL_NAME / "SKILL.md",
        "codex": home / ".codex" / "skills" / SKILL_NAME / "SKILL.md",
        "ggcoder": home / ".gg" / "skills" / f"{SKILL_NAME}.md",
        "opencode": home / ".opencode" / "skills" / SKILL_NAME / "SKILL.md",
        "repo": Path.cwd() / ".agents" / "skills" / SKILL_NAME / "SKILL.md",
    }
    names = list(targets) if target == "all" else [target]
    skill_src = source_skill_file()
    script_src = Path(__file__).resolve()
    written: list[str] = []
    for name in names:
        if name not in targets:
            raise SystemExit(
                f"unknown target: {name}; choose {', '.join(targets)} or all"
            )
        dest = targets[name]
        written.append(str(dest))
        if dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if skill_src.resolve() != dest.resolve():
            shutil.copyfile(skill_src, dest)
        if script_src.exists() and dest.name == "SKILL.md":
            script_dest = dest.parent / "scripts" / script_src.name
            script_dest.parent.mkdir(parents=True, exist_ok=True)
            if script_src.resolve() != script_dest.resolve():
                shutil.copyfile(script_src, script_dest)
    for launcher_name in ("agent-skill-route", "si"):
        launcher = home / ".local" / "bin" / launcher_name
        if launcher_name == "si" and launcher.exists():
            try:
                owned = (
                    "Adaptive token-saving skill router"
                    in launcher.read_text(encoding="utf-8", errors="ignore")[:512]
                )
            except OSError:
                owned = False
            if not owned:
                continue
        written.append(str(launcher))
        if not dry_run:
            launcher.parent.mkdir(parents=True, exist_ok=True)
            if script_src.resolve() != launcher.resolve():
                shutil.copyfile(script_src, launcher)
            launcher.chmod(0o755)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive token-saving skill router")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_route = sub.add_parser("route")
    p_route.add_argument("intent")
    p_route.add_argument("--max", type=int, default=DEFAULT_MAX_SELECTED)
    p_route.add_argument("--json", action="store_true")
    p_route.add_argument("--strict", action="store_true")
    p_route.add_argument("--refresh-index", action="store_true")
    p_bench = sub.add_parser("bench")
    p_bench.add_argument("intent")
    p_bench.add_argument("--max", type=int, default=DEFAULT_MAX_SELECTED)
    p_bench.add_argument("--refresh-index", action="store_true")
    p_install = sub.add_parser("install")
    p_install.add_argument(
        "--target",
        default="all",
        choices=["all", "hermes", "claude", "codex", "ggcoder", "opencode", "repo"],
    )
    p_install.add_argument("--dry-run", action="store_true")
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--json", action="store_true")
    p_index = sub.add_parser("index")
    p_index.add_argument("--refresh", action="store_true")
    p_index.add_argument("--json", action="store_true")
    p_find = sub.add_parser("find")
    p_find.add_argument("query")
    p_find.add_argument("--limit", type=int, default=8)
    p_find.add_argument("--json", action="store_true")
    p_find.add_argument("--refresh-index", action="store_true")
    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("name")
    p_resolve.add_argument("--json", action="store_true")
    p_resolve.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    if args.cmd == "route":
        rr = route(
            args.intent,
            max_selected=selection_limit(args.max),
            strict=args.strict,
            refresh_index=args.refresh_index,
        )
        if args.json:
            print(json.dumps(asdict(rr), indent=2, ensure_ascii=False))
        else:
            print(rr.router_block)
        return 0
    if args.cmd == "bench":
        print(
            json.dumps(
                bench(
                    args.intent,
                    max_selected=selection_limit(args.max),
                    refresh_index=args.refresh_index,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "install":
        print(
            json.dumps(
                {
                    "written": install(args.target, dry_run=args.dry_run),
                    "dry_run": args.dry_run,
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "scan":
        skills = scan()
        if args.json:
            print(json.dumps([asdict(s) for s in skills], indent=2, ensure_ascii=False))
        else:
            for s in skills:
                print(f"{s.name}\t{s.description}\t{s.path}")
        return 0
    if args.cmd == "index":
        catalog_data = load_catalog(refresh=args.refresh)
        summary = catalog_summary(catalog_data)
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(
                f"{summary['status']}\t{summary['skills']} skills\t"
                f"{summary['index_path']}\t{summary['tsv_path']}"
            )
        return 0
    if args.cmd == "find":
        catalog_data = load_catalog(refresh=args.refresh_index)
        matches = find_skills(args.query, catalog_data.skills, args.limit)
        if args.json:
            print(
                json.dumps(
                    [dict(score=points, **asdict(skill)) for points, skill in matches],
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            for points, skill in matches:
                print(f"{points}\t{skill.name}\t{skill.description}\t{skill.path}")
        return 0 if matches else 1
    if args.cmd == "resolve":
        catalog_data = load_catalog(refresh=args.refresh_index)
        skill = resolve_skill(args.name, catalog_data.skills)
        if skill is None:
            return 1
        if args.json:
            print(json.dumps(asdict(skill), indent=2, ensure_ascii=False))
        else:
            print(skill.path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
