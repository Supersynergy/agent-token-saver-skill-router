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
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SKILL_NAME = "agent-token-saver-skill-router"
ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILL = ROOT / "SKILL.md"
WORD_RE = re.compile(r"[a-zA-Z0-9_+-]{2,}")
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
    "your",
    "builder",
}
TOKEN_NORMALIZATION = {
    "tests": "test",
    "testing": "test",
    "pytest": "test",
    "debugging": "debug",
    "debugger": "debug",
    "failing": "fail",
    "failed": "fail",
    "failure": "fail",
    "failures": "fail",
}
PLATFORM_TOKENS = {
    "python", "node", "nodejs", "javascript", "typescript", "rust", "golang", "go"
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
DEFAULT_MAX_SELECTED = 3
MAX_SELECTED = 10


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


def words(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in WORD_RE.findall(text or ""):
        lowered = raw.lower()
        if lowered in STOPWORDS:
            continue
        tokens.add(TOKEN_NORMALIZATION.get(lowered, lowered))
        if lowered == "pytest":
            tokens.add("python")
    return tokens


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
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return path.parent.name, "", ""
    end = text.find("\n---", 3)
    if end == -1:
        return path.parent.name, "", ""
    fm = text[3:end]
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
        start = path.read_text(encoding="utf-8", errors="ignore")[:512]
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


def iter_skill_files(root: Path, max_files: int) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDE_DIRS and not NOISE_NAME_RE.search(d)
        ]
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
    skill_phrase = re.escape(skill.name.lower())
    if re.search(rf"(?<![a-z0-9_+-]){skill_phrase}(?![a-z0-9_+-])", lowered):
        s += 20
    for token in iw:
        if token in skill.path.lower():
            s += 1 * rarity(token, doc_freq)
    is_software_dev = "/software-development/" in skill.path
    if is_software_dev and iw & {"debug", "test", "fail"}:
        s += 20
    if is_software_dev and "python" in iw and "python" in (nw | dw | kw):
        s += 12
    skill_platforms = (nw | dw | kw) & PLATFORM_TOKENS
    requested_platforms = iw & PLATFORM_TOKENS
    if skill_platforms and requested_platforms and not (skill_platforms & requested_platforms):
        s -= 8
    if s > 0 and favorites:
        # Cap the boost at the base score: favorites win close calls but a
        # barely-matching favorite can never bury a strong specific match.
        s += min(float(favorites.get(skill.name.lower(), 0)), s)
    return round(s)


def route(
    intent: str,
    max_selected: int = DEFAULT_MAX_SELECTED,
    roots: list[Path] | None = None,
) -> RouteResult:
    max_selected = selection_limit(max_selected)
    skills = scan(roots)
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
            intent, selected, len(skills), roots or common_roots(), favorites
        )
        return RouteResult(
            intent=intent,
            selected=selected,
            scanned=len(skills),
            roots=[str(p) for p in (roots or common_roots())],
            router_block=block,
        )
    doc_freq = doc_frequencies(skills)
    ranked = sorted(
        (
            (score(intent, s, doc_freq, favorites), s)
            for s in skills
            if s.name != SKILL_NAME
        ),
        key=lambda x: (
            -x[0],
            0 if x[1].name.lower() in favorites else 1,
            x[1].name,
        ),
    )
    selected = [s for points, s in ranked if points > 0][:max_selected]
    block = render_router_block(
        intent, selected, len(skills), roots or common_roots(), favorites
    )
    return RouteResult(
        intent=intent,
        selected=selected,
        scanned=len(skills),
        roots=[str(p) for p in (roots or common_roots())],
        router_block=block,
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


def bench(intent: str, max_selected: int = DEFAULT_MAX_SELECTED) -> dict[str, object]:
    roots = common_roots()
    skills = scan(roots)
    rr = route(intent, max_selected=max_selected, roots=roots)
    full = full_catalog_text(skills)
    router = rr.router_block
    full_tokens = estimate_tokens(full)
    router_tokens = estimate_tokens(router)
    saved = full_tokens - router_tokens
    pct = round((saved / full_tokens * 100), 2) if full_tokens else 0.0
    return {
        "intent": intent,
        "skills_scanned": len(skills),
        "full_chars": len(full),
        "full_est_tokens": full_tokens,
        "router_chars": len(router),
        "router_est_tokens": router_tokens,
        "saved_est_tokens": saved,
        "reduction_pct": pct,
        "selected": [asdict(s) for s in rr.selected],
    }


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
        shutil.copyfile(ROOT_SKILL, dest)
        script_src = ROOT / "scripts" / "agent_token_saver.py"
        if script_src.exists() and dest.name == "SKILL.md":
            script_dest = dest.parent / "scripts" / script_src.name
            script_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script_src, script_dest)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive token-saving skill router")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_route = sub.add_parser("route")
    p_route.add_argument("intent")
    p_route.add_argument("--max", type=int, default=DEFAULT_MAX_SELECTED)
    p_route.add_argument("--json", action="store_true")
    p_bench = sub.add_parser("bench")
    p_bench.add_argument("intent")
    p_bench.add_argument("--max", type=int, default=DEFAULT_MAX_SELECTED)
    p_install = sub.add_parser("install")
    p_install.add_argument(
        "--target",
        default="all",
        choices=["all", "hermes", "claude", "codex", "ggcoder", "opencode", "repo"],
    )
    p_install.add_argument("--dry-run", action="store_true")
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.cmd == "route":
        rr = route(args.intent, max_selected=selection_limit(args.max))
        if args.json:
            print(json.dumps(asdict(rr), indent=2, ensure_ascii=False))
        else:
            print(rr.router_block)
        return 0
    if args.cmd == "bench":
        print(
            json.dumps(
                bench(args.intent, max_selected=selection_limit(args.max)),
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
