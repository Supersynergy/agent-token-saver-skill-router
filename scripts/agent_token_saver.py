#!/usr/bin/env python3
"""Adaptive token-saving skill router.

Python stdlib only. Works as a small CLI helper for Hermes, Claude Code,
Codex CLI, OpenCode, Cursor, Windsurf, and repo-local agents.

Runs on Python 3.9+ so the macOS system interpreter is enough, and is tested
up to the latest stable release. The floor is a compatibility guarantee, not a
recommendation: any newer Python on PATH is used automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

MIN_PYTHON = (3, 9)
if sys.version_info < MIN_PYTHON:  # pragma: no cover - depends on interpreter
    # Without this, an old interpreter fails somewhere deep in the stdlib with
    # a message that says nothing about the actual problem.
    sys.exit(
        "agent-token-saver-skill-router needs Python "
        f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, but this is "
        f"{sys.version_info[0]}.{sys.version_info[1]}. "
        "Run it with a newer interpreter, e.g. `python3.14 agent-skill-route ...`."
    )

SKILL_NAME = "agent-token-saver-skill-router"
# Compatibility names stay resolvable for explicit users and old hosts. A
# suite/component relationship is deliberately not an alias: distinct
# procedures keep independent exact-name routing, telemetry, and feedback.
SKILL_ALIASES = {
    "ad-hoc-verification": "verification-workflows",
    "allskills": SKILL_NAME,
    "claude-token-saver-setup": "token-stack-operations",
    "just-in-time-skill-router": SKILL_NAME,
    "qdrant-os-allskills": SKILL_NAME,
    "requesting-code-review": "metareview",
    "scrapedeep": "scrape-deep",
    "sm": SKILL_NAME,
    "sm-md": SKILL_NAME,
    "token-context-optimization": "agent-token-saver",
}
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
    # This legacy ML controller can recursively select another router. Its
    # telemetry remains readable, but automatic 0/1 routing must choose a
    # domain procedure instead of another selector.
    "skill-autopilot",
    "agent-os-meta",
    "allskills",
    "claude-token-saver-setup",
    "meta-cross-skill-recipe-composer",
    # master-check is a control skill (unified verify/audit dashboard). It was
    # excluded because its broad trigger list can win on generic "check" intents,
    # but it must remain reachable when the user asks for a unified dashboard.
    # Removed 2026-07-24; control skills are now first-class routable targets.
    "megaforge",
    "omega",
    "qdrant-os-allskills",
    "requesting-code-review",
    "scrape-deep",
    "scrapedeep",
    "simplify-code",
    "stealth-research",
    "stealth-scraper",
    "superscrape",
    "token-context-optimization",
    "ad-hoc-verification",
}
ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILL = ROOT / "SKILL.md"
WORD_RE = re.compile(r"[\w+]{2,}", re.UNICODE)
EXPLICIT_SKILL_RE = re.compile(r"\$([a-zA-Z0-9_:+.-]+)")
SKILL_SPEC_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):(?:[ \t]*(.*))?$")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
QUALITY_FRAMEWORK_VERSION = "agent-skills-spec+si-runtime-v1"
SCALAR_FRONTMATTER_FIELDS = {
    "argument-hint",
    "compatibility",
    "description",
    "license",
    "name",
}
SCRIPT_SYNTAX_SUFFIXES = {".py", ".sh", ".bash", ".zsh", ".js", ".cjs", ".mjs"}
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
    "why",
    "your",
    "builder",
    "bei",
    "alle",
    "allen",
    "alles",
    "also",
    "auch",
    "das",
    "dem",
    "den",
    "der",
    "die",
    "du",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "es",
    "für",
    "fuer",
    "im",
    "ich",
    "ist",
    "mit",
    "muss",
    "müssen",
    "muessen",
    "noch",
    "nach",
    "nur",
    "oder",
    "etwas",
    "haben",
    "hat",
    "jede",
    "jeder",
    "jedes",
    "mach",
    "mache",
    "machen",
    "macht",
    "sind",
    "sich",
    "mal",
    "war",
    "warum",
    "weshalb",
    "wieso",
    "wirklich",
    "wir",
    "wofür",
    "wofuer",
    "und",
    "unser",
    "unsere",
    "unseren",
    "soll",
    "sollen",
    "vom",
    "von",
    "werden",
    "welche",
    "welcher",
    "welches",
    "wie",
    "zu",
}
TOKEN_NORMALIZATION = {
    "contexts": "context",
    "skills": "skill",
    "tests": "test",
    "testing": "test",
    "pytest": "test",
    "debugging": "debug",
    "debugger": "debug",
    "failing": "fail",
    "failed": "fail",
    "failure": "fail",
    "failures": "fail",
    "agents": "agent",
    "capsules": "capsule",
    "memories": "memory",
    "optimized": "optimize",
    "optimizing": "optimize",
    "optimization": "optimize",
    "diagnose": "debug",
    "diagnoses": "debug",
    "diagnosis": "debug",
    "diagnostic": "debug",
    "routed": "route",
    "router": "route",
    "routers": "route",
    "routing": "route",
    "improvement": "optimize",
    "improvements": "optimize",
    "extracted": "extract",
    "extracting": "extract",
    "extraction": "extract",
    "contacts": "contact",
    "websites": "website",
    "capabilities": "capability",
    "claims": "claim",
    "documents": "document",
    "sources": "source",
    "updated": "update",
    "updates": "update",
    "updating": "update",
    "outputs": "output",
    "verified": "verify",
    "verifies": "verify",
    "verifying": "verify",
    "verification": "verify",
    "validated": "validate",
    "validates": "validate",
    "validating": "validate",
    "validation": "validate",
    "subagents": "subagent",
    "teams": "team",
    "tokens": "token",
    "tools": "tool",
    "prompts": "prompt",
    "libraries": "library",
    "bibliothek": "library",
    "bibliotheken": "library",
    "sammlung": "library",
    "sammlungen": "library",
    "promptbibliothek": "prompt",
    "promptbibliotheken": "prompt",
    "promptquelle": "prompt",
    "promptquellen": "prompt",
    "promptsammlung": "prompt",
    "promptsammlungen": "prompt",
    "evaluation": "evaluate",
    "evaluations": "evaluate",
    "selected": "select",
    "selecting": "select",
    "selection": "select",
    "synthesis": "synthesize",
    "syntheses": "synthesize",
    "synthesized": "synthesize",
    "synthesizing": "synthesize",
    "invalidation": "invalidate",
    "invalidations": "invalidate",
    "angewendet": "use",
    "anwenden": "use",
    "auflisten": "list",
    "aufräumen": "cleanup",
    "aufraeumen": "cleanup",
    "aufgeräumt": "cleanup",
    "aufgeraeumt": "cleanup",
    "auswahl": "select",
    "baue": "build",
    "bauen": "build",
    "erstelle": "create",
    "erstellen": "create",
    "liste": "list",
    "mergen": "merge",
    "nutzung": "usage",
    "optimiere": "optimize",
    "optimieren": "optimize",
    "pruefe": "test",
    "pruefen": "test",
    "prüfe": "test",
    "prüfen": "test",
    "selbstlernend": "learn",
    "teste": "test",
    "testen": "test",
    "testfall": "test",
    "testfälle": "test",
    "testfaelle": "test",
    "reproduzierbar": "reproducible",
    "feste": "fixed",
    "festen": "fixed",
    "verbessere": "optimize",
    "verbessert": "optimize",
    "verbessern": "optimize",
    "verbesserung": "optimize",
    "verbesserungen": "optimize",
    "überlege": "analyze",
    "überlegen": "analyze",
    "ueberlege": "analyze",
    "ueberlegen": "analyze",
    "maximiere": "optimize",
    "maximieren": "optimize",
    "maximiert": "optimize",
    "kombiniere": "combine",
    "kombinieren": "combine",
    "kombiniert": "combine",
    "combination": "combine",
    "combinations": "combine",
    "ergänzend": "complementary",
    "ergänzende": "complementary",
    "ergänzenden": "complementary",
    "ergaenzend": "complementary",
    "ergaenzende": "complementary",
    "mehrsprachig": "multilingual",
    "mehrsprachige": "multilingual",
    "mehrsprachiges": "multilingual",
    "natürlich": "natural",
    "natürliche": "natural",
    "natürliches": "natural",
    "natuerlich": "natural",
    "natuerliche": "natural",
    "natuerliches": "natural",
    "aktualisiere": "update",
    "aktualisieren": "update",
    "aktuell": "current",
    "aktuelle": "current",
    "aktuellen": "current",
    "aktueller": "current",
    "aktuelles": "current",
    "crawle": "crawl",
    "crawlen": "crawl",
    "extrahiere": "extract",
    "extrahieren": "extract",
    "fasse": "summarize",
    "herunterladen": "download",
    "quelle": "source",
    "quellen": "source",
    "überblick": "overview",
    "ueberblick": "overview",
    "gespeichert": "local",
    "gespeicherte": "local",
    "gespeicherten": "local",
    "recherche": "research",
    "recherchiere": "research",
    "recherchieren": "research",
    "recherchiert": "research",
    "suche": "search",
    "suchen": "search",
    "durchsuche": "search",
    "durchsuchen": "search",
    "synthetisiere": "synthesize",
    "synthetisieren": "synthesize",
    "synthese": "synthesize",
    "beleg": "evidence",
    "belege": "evidence",
    "belegen": "evidence",
    "widerlege": "invalidate",
    "widerlegen": "invalidate",
    "webquelle": "web",
    "webquellen": "web",
    "webseite": "website",
    "webseiten": "website",
    "zitat": "cited",
    "zitate": "cited",
    "zitaten": "cited",
    "zitiert": "cited",
    "zusammenfassen": "summarize",
    "zusammenführen": "merge",
    "zusammenfuehren": "merge",
    # German verb/object coverage (2026-07-23 recall fix): the workflow gate and
    # the scorer are English-centric; map common German task words onto the
    # English tokens that skill descriptions actually use.
    "schick": "send",
    "schicke": "send",
    "schicken": "send",
    "sende": "send",
    "senden": "send",
    "transkribiere": "transcribe",
    "transkribieren": "transcribe",
    "transkript": "transcript",
    "trainiere": "train",
    "trainieren": "train",
    "trainiert": "train",
    "training": "train",
    "starte": "start",
    "starten": "start",
    "zeige": "show",
    "zeigen": "show",
    "anzeigen": "show",
    "schreibe": "write",
    "schreiben": "write",
    "analysiere": "analyze",
    "analysieren": "analyze",
    "analyse": "analyze",
    "repariere": "fix",
    "reparieren": "fix",
    "installiere": "install",
    "installieren": "install",
    "vergleiche": "compare",
    "vergleichen": "compare",
    "messe": "measure",
    "messen": "measure",
    "berechne": "calculate",
    "berechnen": "calculate",
    "übersetze": "translate",
    "übersetzen": "translate",
    "uebersetze": "translate",
    "uebersetzen": "translate",
    "generiere": "generate",
    "generieren": "generate",
    "erzeuge": "generate",
    "erzeugen": "generate",
    "überwache": "monitor",
    "überwachen": "monitor",
    "ueberwache": "monitor",
    "ueberwachen": "monitor",
    "veröffentliche": "publish",
    "veröffentlichen": "publish",
    "veroeffentliche": "publish",
    "veroeffentlichen": "publish",
    "plane": "plan",
    "planen": "plan",
    "finde": "find",
    "finden": "find",
    "wähle": "select",
    "waehle": "select",
    "wählen": "select",
    "waehlen": "select",
    "auswählen": "select",
    "auswaehlen": "select",
    "erkläre": "explain",
    "erklären": "explain",
    "erklaere": "explain",
    "erklaeren": "explain",
    "debugge": "debug",
    "debuggen": "debug",
    "öffne": "open",
    "öffnet": "open",
    "öffnen": "open",
    "oeffne": "open",
    "oeffnet": "open",
    "oeffnen": "open",
    "startet": "start",
    "läuft": "run",
    "laeuft": "run",
    "ständig": "repeat",
    "staendig": "repeat",
    "wiederholt": "repeat",
    "brauch": "need",
    "brauche": "need",
    "braucht": "need",
    "benötige": "need",
    "benötigt": "need",
    "benoetige": "need",
    "benoetigt": "need",
    "entscheide": "evaluate",
    "entscheiden": "evaluate",
    "konvertiere": "convert",
    "konvertieren": "convert",
    "umwandeln": "convert",
    "wetter": "weather",
    "nachricht": "message",
    "nachrichten": "message",
    "tabelle": "spreadsheet",
    "tabellen": "spreadsheet",
    "präsentation": "presentation",
    "praesentation": "presentation",
    "bild": "image",
    "bilder": "image",
    "datei": "file",
    "dateien": "file",
    "daten": "data",
    "datenbank": "database",
    "dokument": "document",
    "dokumente": "document",
    "ladezeit": "performance",
    "webshop": "shop",
    "herunterlade": "download",
    "runterladen": "download",
    "abspielen": "play",
    "spiele": "play",
    "aufnehmen": "record",
    "aufzeichnen": "record",
    "einrichten": "install",
    "losche": "delete",
    "lösche": "delete",
    "löschen": "delete",
    "loeschen": "delete",
    "prüfung": "review",
    "bewerte": "evaluate",
    "bewerten": "evaluate",
}
TOKEN_EXPANSIONS = {
    "evidenzsynthese": ("evidence", "synthesize"),
    "promptbibliothek": ("prompt", "library"),
    "promptbibliotheken": ("prompt", "library"),
    "promptquelle": ("prompt", "source"),
    "promptquellen": ("prompt", "source"),
    "promptsammlung": ("prompt", "library"),
    "promptsammlungen": ("prompt", "library"),
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
PULL_REQUEST_REVIEW_SKILL_NAMES = {
    "code-review",
    "code-review-excellence",
    "github-code-review",
    "github-pr-workflow",
}
WEB_PERFORMANCE_SKILL_NAMES = {
    "core-web-vitals",
    "performance",
    "web-perf",
}
EXACT_ARTIFACT_NAME_TOKENS = {
    "audio",
    "document",
    "image",
    "pdf",
    "presentation",
    "slides",
    "spreadsheet",
    "video",
    "xlsx",
}
AUDIO_OUTPUT_TOKENS = {"audio", "elevenlabs", "mp3", "speech", "tts", "voice"}
TOKEN_CONTEXT_TOKENS = {
    "context",
    "feedback",
    "learn",
    "log",
    "logging",
    "memory",
    "route",
    "router",
    "routing",
    "saving",
    "selection",
    "skill",
    "stack",
    "token",
    "usage",
}
PLAIN_TEST_TOKENS = {"change", "check", "output", "run", "suite", "test", "verify"}
AGENT_TEAM_TOKENS = {
    "agent",
    "capsule",
    "controller",
    "oracle",
    "subagent",
    "team",
    "worker",
}
MEETING_TOKENS = {"calendar", "graph", "meeting", "microsoft", "subscription"}
# Control/orchestration skills (agent-loop, omnigoal, verification-loop, master-check,
# goalmaster) must be reachable from abstract multi-step intents. These tokens signal
# "closed-loop / goal / verify / orchestrate" workflows that the verb allowlist missed.
CONTROL_TOKENS = {
    "achieve",
    "agent",
    "audit",
    "budget",
    "close",
    "closed",
    "contract",
    "converge",
    "convergence",
    "controller",
    "coordinate",
    "coordination",
    "delegate",
    "delegation",
    "dod",
    "drive",
    "fleet",
    "gate",
    "goal",
    "loop",
    "master",
    "oracle",
    "orchestrate",
    "orchestration",
    "pipeline",
    "review",
    "spawn",
    "steer",
    "stop",
    "unified",
    "validate",
    "validation",
    "verify",
    "verification",
    "workflow",
}
WORKFLOW_TOKENS = {
    "analyze",
    "audit",
    "benchmark",
    "build",
    "code",
    "compress",
    "combine",
    "condense",
    "cleanup",
    "create",
    "crawl",
    "cut",
    "debug",
    "deploy",
    "design",
    "edit",
    "evaluate",
    "extract",
    "explain",
    "fail",
    "fix",
    "health",
    "implement",
    "install",
    "minimize",
    "merge",
    "optimize",
    "learn",
    "list",
    "plan",
    "rank",
    "ranking",
    "readme",
    "reduce",
    "refactor",
    "release",
    "report",
    "research",
    "review",
    "route",
    "save",
    "scrape",
    "search",
    "select",
    "shrink",
    "synthesize",
    "summarize",
    "test",
    "trim",
    "update",
    "write",
    # Recall fix (2026-07-23): verbs that previously fell through the gate and
    # produced empty routes despite strong candidates (send/train/transcribe...).
    "send",
    "train",
    "transcribe",
    "download",
    "generate",
    "monitor",
    "convert",
    "publish",
    "post",
    "schedule",
    "track",
    "play",
    "show",
    "start",
    "find",
    "compare",
    "measure",
    "calculate",
    "translate",
    "invalidate",
    "record",
    "run",
    "check",
    "load",
    "delete",
    "review",
    "message",
    "weather",
    # Control/orchestration verbs (2026-07-24 recall fix): abstract multi-step
    # intents like "multi-step coding task with verification gate" or "orchestrate
    # a goal-driven agent loop" previously hit the no-workflow gate despite strong
    # control-skill candidates. These verbs also let control skills compete on
    # equal footing with domain verbs.
    "verify",
    "validate",
    "verification",
    "orchestrate",
    "coordinate",
    "delegate",
    "spawn",
    "steer",
    "converge",
    "close",
    "achieve",
    "drive",
    "gate",
    "loop",
    "goal",
    "contract",
    "budget",
    "pipeline",
    "workflow",
    "master",
    "control",
    "coding",
    "task",
}
DIRECT_TOOL_TOKENS = {"compress", "fetch", "query", "read", "recall", "search"}
MATERIAL_TASK_TOKENS = {
    "audit",
    "benchmark",
    "build",
    "cleanup",
    "combine",
    "create",
    "crawl",
    "debug",
    "deploy",
    "design",
    "edit",
    "evaluate",
    "extract",
    "fix",
    "implement",
    "install",
    "merge",
    "optimize",
    "plan",
    "refactor",
    "release",
    "research",
    "select",
    "scrape",
    "test",
    "synthesize",
    "invalidate",
    "update",
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
    "_skill-packages",
    "backup",
    "backups",
    "related-skills",
    "runs",
}
NOISE_NAME_RE = re.compile(
    r"(\.bak(?:$|[-._])|\.old$|\.disabled$|[-._]backup(?:$|[-._0-9])|[-._]deprecated$)",
    re.IGNORECASE,
)
FLAT_SKILL_SKIP = {"readme.md", "changelog.md", "license.md", "contributing.md"}
DEFAULT_FAVORITE_BOOST = 6
DEFAULT_MAX_SELECTED = 5
MAX_SELECTED = 10
MAX_AUTOMATIC_SELECTED = 5
MIN_STRICT_SCORE = 8
MIN_STRICT_MARGIN = 3
CONTROL_SKILL_NAMES = {
    "agent-loop",
    "blueprint",
    "goalmaster",
    "master-check",
    "omnigoal",
    "verification-loop",
}
SKILL_ROUTER_GOVERNANCE_NAMES = {
    "agent-efficiency-orchestrator",
    "agent-token-saver",
    "skill-fleet-audit",
    "skill-portfolio-governance",
}
SKILL_ROUTER_MANAGEMENT_TOKENS = {
    "accuracy",
    "audit",
    "combine",
    "evaluate",
    "governance",
    "optimize",
    "quality",
}
BUNDLE_MODIFIER_TOKENS = {
    "combine",
    "complementary",
    "current",
    "final",
    "five",
    "multilingual",
    "natural",
    "need",
    "request",
    "together",
}
NATURAL_SKILL_CUE_RE = re.compile(
    r"\b(?:apply|combine|load|use|using|with|via|kombiniere|kombinieren|lade|"
    r"laden|mit|nutze|nutzen|verwende|verwenden)\b",
    re.IGNORECASE,
)
# "do not use the taste skill" contains the same cue and phrase as a request to
# load it. Inference from prose must respect an explicit refusal, otherwise the
# router loads exactly what the user just declined.
NEGATION_CUE_RE = re.compile(
    r"n't\b|\b(?:never|not|without|avoid|avoids|avoiding|skip|skips|skipping|"
    r"instead\s+of|rather\s+than|"
    r"nicht|kein(?:e|en|er)?|ohne|niemals|statt|anstatt|vermeide|vermeiden)\b",
    re.IGNORECASE,
)
# A cue only negates within its own clause: "use best practices, not the old
# approach" must still load the skill.
CLAUSE_BOUNDARY_CHARS = ".;!?,\n"
CLAUSE_SPLIT_RE = re.compile(
    r"(?:[.!?;\n]+|,\s*|\b(?:and then|then|and|plus|sowie|und dann|danach|und)\b)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tunable scoring weights (autolearn layer, 2026-07-23).
# si-autotune grid-races these against the labeled eval set and persists the
# winner to tuned-weights.json. Stdlib only; missing file = safe defaults.
# ---------------------------------------------------------------------------
TUNED_DEFAULTS: dict[str, float] = {
    "name_w": 8.0,  # intent token in skill name
    "desc_w": 3.0,  # intent token in description
    "kw_w": 6.0,  # intent token in keywords
    "coverage_w": 4.0,  # per extra matched token
    "bigram_name": 12.0,  # intent bigram found in skill name
    "bigram_desc": 5.0,  # intent bigram found in description
    "desc_damp_start": 60.0,  # description word count where damping kicks in
    "desc_damp_floor": 0.35,  # minimum description scale
    "no_workflow_min_score": 14.0,  # fallback gate: min top score w/o verb
    "no_workflow_min_margin": 4.0,  # fallback gate: min margin over #2
}
_tuned_cache: dict[str, float] | None = None


def tuned_weights() -> dict[str, float]:
    """Load autotuned scoring weights; fall back to TUNED_DEFAULTS."""
    global _tuned_cache
    if _tuned_cache is not None:
        return _tuned_cache
    weights = dict(TUNED_DEFAULTS)
    path = Path.home() / ".local/state/agent-skill-router/tuned-weights.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            source = raw.get("weights", raw)
            for key, value in source.items():
                if key in weights and isinstance(value, (int, float)):
                    weights[key] = float(value)
    except Exception:
        pass
    _tuned_cache = weights
    return weights


INDEX_SCHEMA = 1
DEFAULT_INDEX_TTL_SECONDS = 300.0
TELEMETRY_SCHEMA = 1
GENERIC_SKILL_NAMES = {"skill", "readme", "index", "main"}

# Jury cases (2026-07-24): a deterministic battery for automated cross-checking
# the router. Each case asserts that at least one expected skill is reachable
# for a representative intent. Control skills (agent-loop, omnigoal,
# verification-loop, master-check, goalmaster) must be reachable from abstract
# multi-step intents; domain skills must still route from concrete asks. Add
# cases here when a regression is found; never delete a case without a witness.
JURY_CASES = [
    # Control-skill routing — the original failing cases.
    {
        "intent": "multi-step coding task with verification gate",
        "max": 3,
        "expected": ["verification-loop", "agent-loop", "master-check", "blueprint"],
    },
    {
        "intent": "run a multi-step coding task with verification gate",
        "max": 3,
        "expected": ["verification-loop", "agent-loop"],
    },
    {
        "intent": "orchestrate a goal-driven agent loop",
        "max": 1,
        "strict": True,
        "expected": ["agent-loop", "omnigoal"],
    },
    {
        "intent": "run omnigoal closed-loop goal controller",
        "max": 3,
        "expected": ["omnigoal", "agent-loop"],
    },
    {
        "intent": "master-check dashboard before demo",
        "max": 1,
        "strict": True,
        "expected": ["master-check"],
    },
    {
        "intent": "goalmaster goal mode objective",
        "max": 1,
        "strict": True,
        "expected": ["goalmaster"],
    },
    {
        "intent": "verify build types lint tests security diff before PR",
        "max": 1,
        "strict": True,
        "expected": ["verification-loop"],
    },
    # Lock in the original failing case: --max 1 --strict must return a control
    # skill, not an empty list. The control-skill ambiguity exception lets the
    # top pick win when top-2 are both control skills.
    {
        "intent": "multi-step coding task with verification gate",
        "max": 1,
        "strict": True,
        "expected": ["verification-loop", "agent-loop", "master-check"],
    },
    # Domain sanity checks — must not regress when control skills opened up.
    {
        "intent": "fix a bug in a python file",
        "max": 1,
        "strict": True,
        "expected": ["python-debugpy", "bug-detective"],
    },
    {
        "intent": "send a telegram message",
        "max": 3,
        "expected": ["bluebubbles", "using-telegram-bot", "agentmaster"],
    },
    {
        "intent": (
            "fix bitte die ganzen skills nach best practices, jeder skill stabil "
            "und im skillindexer aufrufbar"
        ),
        "max": 1,
        "strict": True,
        "expected": ["skill-fleet-audit"],
    },
    {
        "intent": "transcribe and answer this audio file",
        "max": 1,
        "strict": True,
        "expected": ["tawnser"],
    },
]


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
    decision: str = "selected"
    top_score: int = 0
    margin: int = 0
    recommended_tools: list[ToolRecommendation] = field(default_factory=list)
    selection_roles: dict[str, str] = field(default_factory=dict)
    alternatives: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    keywords: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolRecommendation:
    name: str
    aliases: tuple[str, ...]
    path: str
    total_score: int
    base_score: int
    adaptive_adjustment: int
    matched_tokens: tuple[str, ...]
    explicit: bool = False


@dataclass
class UsageSignal:
    routed: int = 0
    applied: int = 0
    views: int = 0
    patches: int = 0
    success: int = 0
    failure: int = 0
    legacy_suggested: int = 0
    last_activity: str = ""


@dataclass
class ToolSignal:
    routed: int = 0
    used: int = 0
    success: int = 0
    failure: int = 0
    total_latency_ms: int = 0
    last_activity: str = ""


@dataclass
class UsageData:
    signals: dict[str, UsageSignal]
    tool_signals: dict[str, ToolSignal] = field(default_factory=dict)
    malformed: int = 0
    route_events: int = 0
    feedback_events: int = 0
    tool_events: int = 0


@dataclass(frozen=True)
class Catalog:
    skills: list[Skill]
    roots: list[Path]
    source: str
    index_path: Path


@dataclass(frozen=True)
class SkillIssue:
    path: str
    code: str
    severity: str
    message: str
    line: int = 0


@dataclass(frozen=True)
class FrontmatterDocument:
    text: str
    lines: list[str]
    start: int
    end: int
    fields: dict[str, str]
    field_lines: dict[str, int]
    body: str


# Tool routing is intentionally separate from skill routing. A CLI invocation
# is usage of executable infrastructure, not evidence that a SKILL.md was read.
TOOL_SPECS = (
    ToolSpec(
        "rg",
        "Search exact text, filenames, and local repository content quickly.",
        "local repository exact text file search regex ripgrep",
        ("ripgrep",),
    ),
    ToolSpec(
        "just",
        "Run repository-defined recipes and verification commands.",
        "repository recipe task check test build command",
    ),
    ToolSpec(
        "git",
        "Inspect version-control status, history, branches, and diffs.",
        "version control repository status history branch commit diff",
    ),
    ToolSpec(
        "jq",
        "Query and transform JSON from files or command output.",
        "json query filter transform command output",
    ),
    ToolSpec(
        "sqlite3",
        "Query and maintain local SQLite databases.",
        "sqlite database sql local query data",
    ),
    ToolSpec(
        "duckdb",
        "Analyze local tabular files and datasets with SQL.",
        "duckdb database sql analytics parquet csv data local query",
    ),
    ToolSpec(
        "ghmax",
        "Search current GitHub code and repositories with bounded cached results.",
        "github code repository remote implementation pattern search",
        ("ghgrep",),
    ),
    ToolSpec(
        "superweb",
        "Search, fetch, batch, crawl, research, summarize cited sources, extract, browse dynamic pages, query official sources, and download current web artifacts.",
        "web internet search fetch batch crawl research summarize cited scrape extract browser javascript challenge stealth api official source documentation current live download pdf contact email phone social toolbus mcp",
        (
            "superscrape",
            "smart-fetch",
            "hyperfetch",
            "superfetch",
            "supersearch",
            "feeds-pull",
            "batch-md-rs",
            "bulkfetch",
        ),
    ),
    ToolSpec(
        "tilth",
        "Read and search structured source code within a fixed token budget.",
        "source code structured symbols read search context budget",
    ),
    ToolSpec(
        "grepgod",
        "Review diffs and source for correctness or security findings.",
        "review audit diff code security findings regression",
    ),
    ToolSpec(
        "synxp",
        "Recall compact cross-project memory and prior decisions.",
        "memory recall history prior decision cross project context",
        ("synx",),
    ),
    ToolSpec(
        "rtk",
        "Compress noisy shell command output before it reaches model context.",
        "compress shell command output log token noisy savings",
    ),
    ToolSpec(
        "graphify",
        "Query an existing repository code-structure graph.",
        "repository code graph architecture relationship structure query",
    ),
    ToolSpec(
        "codegraph",
        "Find code callers, callees, dependencies, and impact.",
        "code graph callers callees dependencies impact symbols",
    ),
    ToolSpec(
        "freshdocs",
        "Load current version-matched package and API documentation.",
        "current package api documentation dependency version library",
    ),
    ToolSpec(
        "run-guard",
        "Bound long-running jobs by wall time, memory, and threads.",
        "process long job timeout memory cpu gpu threads resource guard",
    ),
    ToolSpec(
        "debugmaster",
        "Diagnose failures with a bounded debugging workflow.",
        "debug diagnose failure root cause regression",
    ),
    ToolSpec(
        "superverify",
        "Run focused verification and repository checks.",
        "verify test checks validation repository",
    ),
    ToolSpec(
        "repovista",
        "Inspect a compact repository overview and inventory.",
        "repository overview inventory architecture inspect",
    ),
    ToolSpec(
        "agent-token-ledger",
        "Account parent, child, retry, and fallback token usage.",
        "agent token ledger cost child retry fallback usage",
    ),
    ToolSpec(
        "agent-token-saver",
        "Inspect or operate the full token-saving stack.",
        "agent token save context stack routing doctor",
    ),
)


def contextual_intent_tokens(text: str) -> set[str]:
    """Add small phrase-level signals that bag-of-words matching cannot express."""
    lowered = (text or "").lower()
    tokens: set[str] = set()
    problem_question = re.search(r"\b(?:warum|weshalb|wieso|why)\b", lowered)
    runtime_symptom = re.search(
        r"\b(?:fail\w*|fehl\w*|hängt|haengt|keeps?|läuft|laeuft|open\w*|"
        r"öffnet|oeffnet|start\w*|ständig|staendig|wiederholt)\b",
        lowered,
    )
    if problem_question and runtime_symptom:
        tokens.add("debug")
    if re.search(
        r"\b(?:brauch(?:e|t)?\s+ich|benötig\w*|benoetig\w*|do\s+i\s+need|"
        r"is\s+(?:it|this|that)\s+needed)\b",
        lowered,
    ):
        tokens.add("evaluate")
    if (
        re.search(r"\b(?:prüf\w*|pruef\w*|review\w*)\b", lowered)
        and re.search(r"\b(?:pull\s+request|merge\s+request|pr)\b", lowered)
    ):
        tokens.add("review")
    return tokens


@lru_cache(maxsize=8192)
def words(text: str) -> frozenset[str]:
    tokens: set[str] = contextual_intent_tokens(text)
    for raw in WORD_RE.findall(text or ""):
        lowered = raw.lower()
        if lowered in STOPWORDS:
            continue
        expansion = TOKEN_EXPANSIONS.get(lowered)
        if expansion:
            tokens.update(expansion)
        else:
            tokens.add(TOKEN_NORMALIZATION.get(lowered, lowered))
        if lowered == "pytest":
            tokens.add("python")
    return frozenset(tokens)


def tool_specs(*, include_unavailable: bool = False) -> list[tuple[ToolSpec, str]]:
    """Return canonical tools and their live executable paths."""
    found: list[tuple[ToolSpec, str]] = []
    for spec in TOOL_SPECS:
        path = shutil.which(spec.name)
        if path is None:
            for alias in spec.aliases:
                path = shutil.which(alias)
                if path:
                    break
        if path or include_unavailable:
            found.append((spec, path or ""))
    return found


def canonical_tool_name(name: str) -> str | None:
    normalized = Path(name.strip()).name.lower()
    for spec in TOOL_SPECS:
        if normalized == spec.name or normalized in spec.aliases:
            return spec.name
    return None


def canonical_skill_name(name: str) -> str:
    normalized = name.strip().lstrip("$").lower()
    seen: set[str] = set()
    while normalized in SKILL_ALIASES and normalized not in seen:
        seen.add(normalized)
        normalized = SKILL_ALIASES[normalized]
    return normalized


def explicit_tool_names(intent: str) -> list[str]:
    """Resolve literal executable/alias mentions without fuzzy substrings."""
    explicit: list[str] = []
    for spec in TOOL_SPECS:
        names = (spec.name, *spec.aliases)
        if any(
            re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", intent, re.I)
            for name in names
        ):
            explicit.append(spec.name)
    return explicit


def tool_learned_adjustment(signal: ToolSignal | None) -> int:
    """Bounded outcome tie-breaker; it can never create tool relevance."""
    if signal is None:
        return 0
    familiarity = min(2, math.floor(math.log2(signal.used + 1)))
    outcomes = signal.success + signal.failure
    quality = (
        round(6 * (signal.success - signal.failure) / (outcomes + 2)) if outcomes else 0
    )
    latency_penalty = 0
    if signal.used and signal.total_latency_ms:
        average_ms = signal.total_latency_ms / signal.used
        latency_penalty = (
            -2 if average_ms >= 30_000 else (-1 if average_ms >= 10_000 else 0)
        )
    return max(-8, min(8, familiarity + quality + latency_penalty))


def rank_tools(
    intent: str,
    usage_data: UsageData | None = None,
    *,
    include_unavailable: bool = False,
) -> list[ToolRecommendation]:
    """Rank installed CLIs independently from SKILL.md candidates."""
    intent_words = words(intent)
    literal = set(explicit_tool_names(intent))
    ranked: list[ToolRecommendation] = []
    for spec, path in tool_specs(include_unavailable=include_unavailable):
        name_words = words(" ".join((spec.name, *spec.aliases)).replace("-", " "))
        semantic_words = words(f"{spec.description} {spec.keywords}")
        matched_name = intent_words & name_words
        matched_semantic = intent_words & semantic_words
        explicit = spec.name in literal
        base = 100 if explicit else 7 * len(matched_name) + 3 * len(matched_semantic)
        if base <= 0:
            continue
        adaptive = 0
        if usage_data is not None:
            adaptive = tool_learned_adjustment(usage_data.tool_signals.get(spec.name))
        ranked.append(
            ToolRecommendation(
                name=spec.name,
                aliases=spec.aliases,
                path=path,
                total_score=base + adaptive,
                base_score=base,
                adaptive_adjustment=adaptive,
                matched_tokens=tuple(sorted(matched_name | matched_semantic)),
                explicit=explicit,
            )
        )
    return sorted(ranked, key=lambda item: (-item.total_score, item.name))


def recommend_tools(
    intent: str, usage_data: UsageData | None = None
) -> list[ToolRecommendation]:
    ranked = rank_tools(intent, usage_data)
    if not ranked:
        return []
    if ranked[0].explicit:
        return ranked[:1]
    margin = ranked[0].total_score - (ranked[1].total_score if len(ranked) > 1 else 0)
    return ranked[:1] if ranked[0].total_score >= 8 and margin >= 3 else []


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


def decode_frontmatter_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, str) else str(decoded)
        except (TypeError, ValueError):
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def frontmatter_document_from_text(text: str) -> FrontmatterDocument | None:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return None
    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    index = 1
    while index < end:
        line = lines[index]
        match = FRONTMATTER_KEY_RE.match(line) if line == line.lstrip() else None
        if not match:
            index += 1
            continue
        key = match.group(1)
        raw = (match.group(2) or "").strip()
        field_lines.setdefault(key, index + 1)
        if raw in {">-", ">", "|-", "|"}:
            tail: list[str] = []
            cursor = index + 1
            while cursor < end and (
                not lines[cursor].strip() or lines[cursor] != lines[cursor].lstrip()
            ):
                tail.append(lines[cursor].strip())
                cursor += 1
            fields.setdefault(key, " ".join(item for item in tail if item).strip())
            index = cursor
            continue
        fields.setdefault(key, decode_frontmatter_scalar(raw))
        index += 1
    return FrontmatterDocument(
        text=text,
        lines=lines,
        start=0,
        end=end,
        fields=fields,
        field_lines=field_lines,
        body="\n".join(lines[end + 1 :]),
    )


def parse_frontmatter_document(path: Path) -> FrontmatterDocument | None:
    return frontmatter_document_from_text(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[str, str, str]:
    document = parse_frontmatter_document(path)
    if document is None:
        fallback = path.stem if path.name != "SKILL.md" else path.parent.name
        return fallback, "", ""
    name = document.fields.get("name", "").strip()
    desc = document.fields.get("description", "").strip()
    tags = ""
    for line in document.lines[1 : document.end]:
        if line.strip().startswith("tags:"):
            raw = line.split(":", 1)[1].strip()
            tags = " ".join(WORD_RE.findall(raw))
            break
    fallback = path.stem if path.name != "SKILL.md" else path.parent.name
    return name or fallback, desc, tags


def normalized_skill_name(path: Path) -> str:
    raw = path.stem if path.name != "SKILL.md" else path.parent.name
    normalized = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized[:64].rstrip("-") or "unnamed-skill"


def description_from_body(body: str, name: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    without_fences = re.sub(r"```.*?```", "", without_comments, flags=re.DOTALL)
    candidates: list[str] = []
    for paragraph in re.split(r"\n\s*\n", without_fences):
        compact = " ".join(line.strip() for line in paragraph.splitlines()).strip()
        if not compact or compact.startswith(("#", "---", "::", "<")):
            continue
        compact = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", compact)
        compact = re.sub(r"[*_`>|]", "", compact)
        compact = re.sub(r"\s+", " ", compact).strip(" -")
        if len(compact) >= 24:
            candidates.append(compact)
            break
    base = candidates[0] if candidates else f"Procedures and references for {name}."
    if len(base) > 820:
        base = base[:817].rsplit(" ", 1)[0] + "..."
    if not re.search(
        r"\b(use when|use for|when to use|nutze|verwende|trigger)\b", base, re.I
    ):
        base = f"{base} Use when a task requires {name.replace('-', ' ')}."
    return base[:1024]


def scalar_needs_yaml_quotes(key: str, raw: str) -> bool:
    value = raw.strip()
    if key not in SCALAR_FRONTMATTER_FIELDS or not value:
        return False
    if value in {">-", ">", "|-", "|"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return False
    if key == "argument-hint":
        return True
    return (
        ": " in value
        or " #" in value
        or value.startswith(("[", "{", "&", "*", "!", "%", "@", "`"))
    )


def local_markdown_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif " " in target:
        target = target.split(" ", 1)[0]
    target = unquote(target).split("#", 1)[0].strip()
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    return target


def script_syntax_issues(skill_path: Path, max_scripts: int = 500) -> list[SkillIssue]:
    if skill_path.name != "SKILL.md":
        return []
    scripts_dir = skill_path.parent / "scripts"
    if not scripts_dir.is_dir():
        return []
    candidates = sorted(
        path
        for path in scripts_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SCRIPT_SYNTAX_SUFFIXES
        and not any(part in EXCLUDE_DIRS for part in path.parts)
    )
    issues: list[SkillIssue] = []
    if len(candidates) > max_scripts:
        issues.append(
            SkillIssue(
                str(skill_path),
                "script-check-limit",
                "warning",
                f"checked first {max_scripts} of {len(candidates)} scripts",
            )
        )
        candidates = candidates[:max_scripts]
    missing_checkers: set[str] = set()
    for script in candidates:
        try:
            source = script.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(
                SkillIssue(str(script), "script-unreadable", "error", str(exc))
            )
            continue
        suffix = script.suffix.lower()
        problem = ""
        if suffix == ".py":
            try:
                compile(source, str(script), "exec")
            except (SyntaxError, ValueError) as exc:
                problem = f"{type(exc).__name__}: {exc}"
        elif suffix in {".sh", ".bash", ".zsh"}:
            checker = "zsh" if suffix == ".zsh" else "bash"
            binary = shutil.which(checker)
            if binary:
                try:
                    completed = subprocess.run(
                        [binary, "-n", str(script)],
                        capture_output=True,
                        text=True,
                        timeout=8,
                        check=False,
                    )
                    if completed.returncode:
                        problem = (completed.stderr or completed.stdout).strip()
                except (OSError, subprocess.TimeoutExpired) as exc:
                    problem = str(exc)
            else:
                missing_checkers.add(checker)
        else:
            binary = shutil.which("node")
            if binary:
                try:
                    completed = subprocess.run(
                        [binary, "--check", str(script)],
                        capture_output=True,
                        text=True,
                        timeout=8,
                        check=False,
                    )
                    if completed.returncode:
                        problem = (completed.stderr or completed.stdout).strip()
                except (OSError, subprocess.TimeoutExpired) as exc:
                    problem = str(exc)
            else:
                missing_checkers.add("node")
        if problem:
            issues.append(
                SkillIssue(str(script), "script-syntax", "error", problem[:500])
            )
        if source.startswith("#!") and not os.access(script, os.X_OK):
            issues.append(
                SkillIssue(
                    str(script),
                    "script-not-executable",
                    "warning",
                    "script has a shebang but is not executable",
                )
            )
    for checker in sorted(missing_checkers):
        issues.append(
            SkillIssue(
                str(skill_path),
                "script-checker-missing",
                "warning",
                f"{checker} is unavailable; matching scripts were not syntax-checked",
            )
        )
    return issues


def validate_skill_file(
    path: Path, *, spec_strict: bool = False, check_scripts: bool = False
) -> list[SkillIssue]:
    issues: list[SkillIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [SkillIssue(str(path), "unreadable", "error", str(exc))]
    document = frontmatter_document_from_text(text)
    if document is None:
        code = (
            "missing-frontmatter"
            if not text.lstrip("\ufeff").startswith("---")
            else "unclosed-frontmatter"
        )
        return [
            SkillIssue(
                str(path),
                code,
                "error",
                "SKILL.md must start with a closed YAML frontmatter block",
                1,
            )
        ]
    frontmatter_bytes = len("\n".join(document.lines[1 : document.end]).encode("utf-8"))
    if frontmatter_bytes > 65_536:
        issues.append(
            SkillIssue(
                str(path),
                "frontmatter-too-large",
                "error",
                f"frontmatter is {frontmatter_bytes} bytes; limit is 65536",
                1,
            )
        )
    seen_keys: set[str] = set()
    for index, line in enumerate(document.lines[1 : document.end], 2):
        match = FRONTMATTER_KEY_RE.match(line) if line == line.lstrip() else None
        if not match:
            continue
        key = match.group(1)
        raw = (match.group(2) or "").strip()
        if key in seen_keys:
            issues.append(
                SkillIssue(str(path), "duplicate-frontmatter-key", "error", key, index)
            )
        seen_keys.add(key)
        if scalar_needs_yaml_quotes(key, raw):
            issues.append(
                SkillIssue(
                    str(path),
                    "invalid-yaml-scalar",
                    "error",
                    f"quote the {key} scalar",
                    index,
                )
            )
    name = document.fields.get("name", "").strip()
    description = document.fields.get("description", "").strip()
    if not name:
        issues.append(
            SkillIssue(str(path), "missing-name", "error", "name is required")
        )
    else:
        if len(name) > 64 or not SKILL_SPEC_NAME_RE.fullmatch(name):
            issues.append(
                SkillIssue(
                    str(path),
                    "invalid-name",
                    "error" if spec_strict else "warning",
                    "name must be 1-64 lowercase letters, digits, or single hyphens",
                    document.field_lines.get("name", 0),
                )
            )
        if path.name == "SKILL.md" and name != path.parent.name:
            issues.append(
                SkillIssue(
                    str(path),
                    "name-directory-mismatch",
                    "error" if spec_strict else "warning",
                    f"frontmatter name {name!r} differs from directory {path.parent.name!r}",
                    document.field_lines.get("name", 0),
                )
            )
    if not description:
        issues.append(
            SkillIssue(
                str(path), "missing-description", "error", "description is required"
            )
        )
    elif len(description) > 1024:
        issues.append(
            SkillIssue(
                str(path),
                "description-too-long",
                "error",
                f"description has {len(description)} characters; limit is 1024",
                document.field_lines.get("description", 0),
            )
        )
    compatibility = document.fields.get("compatibility", "").strip()
    if compatibility and len(compatibility) > 500:
        issues.append(
            SkillIssue(
                str(path),
                "compatibility-too-long",
                "error",
                f"compatibility has {len(compatibility)} characters; limit is 500",
                document.field_lines.get("compatibility", 0),
            )
        )
    if not document.body.strip():
        issues.append(
            SkillIssue(str(path), "empty-body", "error", "skill body is empty")
        )
    body_lines = document.body.splitlines()
    if len(body_lines) > 500:
        issues.append(
            SkillIssue(
                str(path),
                "body-over-500-lines",
                "warning",
                f"body has {len(body_lines)} lines; split details into references",
            )
        )
    if path.name != "SKILL.md":
        issues.append(
            SkillIssue(
                str(path),
                "flat-skill-extension",
                "error" if spec_strict else "warning",
                "runtime-compatible flat skill; portable Agent Skills use <name>/SKILL.md",
            )
        )
    skill_root = path.parent
    for match in MARKDOWN_LINK_RE.finditer(document.body):
        target = local_markdown_target(match.group(1))
        if target is None:
            continue
        line = document.end + 2 + document.body[: match.start()].count("\n")
        if Path(target).is_absolute():
            issues.append(
                SkillIssue(
                    str(path),
                    "absolute-resource-path",
                    "warning",
                    f"prefer a relative resource path: {target}",
                    line,
                )
            )
            continue
        candidate = (skill_root / target).resolve()
        try:
            candidate.relative_to(skill_root.resolve())
        except ValueError:
            issues.append(
                SkillIssue(
                    str(path),
                    "resource-path-escape",
                    "error" if spec_strict else "warning",
                    target,
                    line,
                )
            )
            continue
        if not candidate.exists():
            strong_reference = target.startswith(("scripts/", "references/", "assets/"))
            issues.append(
                SkillIssue(
                    str(path),
                    "missing-resource",
                    "error" if spec_strict or strong_reference else "warning",
                    target,
                    line,
                )
            )
    if check_scripts:
        issues.extend(script_syntax_issues(path))
    return issues


def validation_report(
    paths: Iterable[Path], *, spec_strict: bool = False, check_scripts: bool = False
) -> dict[str, object]:
    unique_paths = sorted({str(path.resolve()) for path in paths})
    issues: list[SkillIssue] = []
    for raw_path in unique_paths:
        issues.extend(
            validate_skill_file(
                Path(raw_path), spec_strict=spec_strict, check_scripts=check_scripts
            )
        )
    errors = sum(issue.severity == "error" for issue in issues)
    warnings = len(issues) - errors
    counts = Counter(issue.code for issue in issues)
    return {
        "ok": errors == 0,
        "framework": QUALITY_FRAMEWORK_VERSION,
        "files": len(unique_paths),
        "errors": errors,
        "warnings": warnings,
        "issue_counts": dict(sorted(counts.items())),
        "issues": [asdict(issue) for issue in issues],
    }


def embedded_frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    for start in range(1, min(len(lines), 80)):
        if lines[start].strip() != "---":
            continue
        try:
            end = next(
                index
                for index in range(start + 1, min(len(lines), start + 120))
                if lines[index].strip() == "---"
            )
        except StopIteration:
            continue
        block = lines[start + 1 : end]
        if any(line.startswith("name:") for line in block) and any(
            line.startswith("description:") for line in block
        ):
            return start, end
    return None


def repair_skill_text(path: Path, text: str) -> tuple[str, list[str]]:
    fixes: list[str] = []
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        bounds = embedded_frontmatter_bounds(lines)
        if bounds:
            start, end = bounds
            frontmatter = lines[start : end + 1]
            prefix = lines[:start]
            suffix = lines[end + 1 :]
            parts = frontmatter + [""]
            if any(line.strip() for line in prefix):
                parts.extend(prefix)
                parts.append("")
            parts.extend(suffix)
            lines = parts
            fixes.append("frontmatter-moved-to-start")
        else:
            name = normalized_skill_name(path)
            description = description_from_body(text, name)
            lines = [
                "---",
                f"name: {name}",
                f"description: {json.dumps(description, ensure_ascii=False)}",
                "---",
                "",
                *lines,
            ]
            fixes.append("frontmatter-added")
    candidate = "\n".join(lines).rstrip() + "\n"
    document = frontmatter_document_from_text(candidate)
    if document is None:
        return text, []
    lines = document.lines
    inserts: list[str] = []
    name = document.fields.get("name", "").strip()
    if not name:
        name = normalized_skill_name(path)
        inserts.append(f"name: {name}")
        fixes.append("name-added")
    if not document.fields.get("description", "").strip():
        description = description_from_body(document.body, name)
        inserts.append(f"description: {json.dumps(description, ensure_ascii=False)}")
        fixes.append("description-added")
    if inserts:
        lines[1:1] = inserts
        candidate = "\n".join(lines).rstrip() + "\n"
        document = frontmatter_document_from_text(candidate)
        if document is None:
            return text, []
        lines = document.lines
    for index in range(1, document.end):
        line = lines[index]
        match = FRONTMATTER_KEY_RE.match(line) if line == line.lstrip() else None
        if not match:
            continue
        key = match.group(1)
        raw = (match.group(2) or "").strip()
        if scalar_needs_yaml_quotes(key, raw):
            lines[index] = (
                f"{key}: {json.dumps(decode_frontmatter_scalar(raw), ensure_ascii=False)}"
            )
            fixes.append(f"quoted-{key}")
    repaired = "\n".join(lines).rstrip() + "\n"
    return repaired, sorted(set(fixes))


def repair_report(paths: Iterable[Path], *, apply: bool = False) -> dict[str, object]:
    proposals: list[dict[str, object]] = []
    originals: dict[str, str] = {}
    for raw_path in sorted({str(path.resolve()) for path in paths}):
        path = Path(raw_path)
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        repaired, fixes = repair_skill_text(path, original)
        if fixes and repaired != original:
            originals[raw_path] = original
            proposals.append(
                {
                    "path": raw_path,
                    "fixes": fixes,
                    "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "after_sha256": hashlib.sha256(repaired.encode()).hexdigest(),
                    "repaired": repaired,
                }
            )
    backup_dir: Path | None = None
    manifest_rows: list[dict[str, object]] = []
    if apply and proposals:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = (
            router_state_dir() / "skill-repair-backups" / f"{stamp}-{os.getpid()}"
        )
        backup_dir.mkdir(parents=True, exist_ok=False)
        os.chmod(backup_dir, stat.S_IRWXU)
        files_dir = backup_dir / "files"
        files_dir.mkdir(mode=0o700)
        for number, proposal in enumerate(proposals, 1):
            path = Path(str(proposal["path"]))
            before = originals[str(path)]
            mode = path.stat().st_mode & 0o777
            backup = files_dir / f"{number:04d}.md"
            atomic_write_text(backup, before)
            os.chmod(backup, 0o600)
            atomic_write_text(path, str(proposal["repaired"]))
            os.chmod(path, mode)
            manifest_rows.append(
                {key: value for key, value in proposal.items() if key != "repaired"}
                | {"backup": str(backup)}
            )
        atomic_write_text(
            backup_dir / "manifest.json",
            json.dumps(manifest_rows, indent=2, ensure_ascii=False) + "\n",
        )
        os.chmod(backup_dir / "manifest.json", 0o600)
    return {
        "ok": True,
        "framework": QUALITY_FRAMEWORK_VERSION,
        "apply": apply,
        "changed": len(proposals),
        "backup_dir": str(backup_dir) if backup_dir else "",
        "changes": [
            {key: value for key, value in proposal.items() if key != "repaired"}
            for proposal in proposals
        ],
    }


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
        # Canonical global distribution. Keep this before host-specific bridges
        # so a skill installed through Superskills has one authoritative path.
        home / "superskills" / "skills",
        home / ".agents" / "skills",
        home / ".hermes" / "skills",
        home / ".claude" / "skills",
        home / ".claude" / "cts" / "skills",
        # cts also stores skills directly under ~/.claude/cts/<name> (not only
        # in cts/skills); scanning the parent recovers those (e.g. docker-patterns).
        home / ".claude" / "cts",
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
    # Hermes skills.external_dirs: the router must see the same catalog the
    # Hermes session sees, otherwise skills routable in Hermes score zero here.
    hermes_cfg = home / ".hermes" / "config.yaml"
    try:
        in_ext = False
        for line in hermes_cfg.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines():
            stripped = line.strip()
            if stripped.startswith("external_dirs:"):
                in_ext = True
                continue
            if in_ext:
                if stripped.startswith("- "):
                    candidates.append(Path(stripped[2:].strip()).expanduser())
                elif stripped and not line.startswith((" ", "\t")):
                    in_ext = False
    except OSError:
        pass
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
    selected: dict[str, tuple[tuple[object, ...], int, Skill]] = {}
    sequence = 0
    for root_index, root in enumerate(roots):
        for path in iter_skill_files(root, max_files_per_root):
            try:
                name, desc, tags = parse_frontmatter(path)
                resolved = path.resolve()
                relative = resolved.relative_to(root.resolve())
            except (OSError, UnicodeError):
                continue
            except ValueError:
                relative = Path(path.name)
            key = name.lower()
            skill = Skill(
                name=name,
                description=desc,
                keywords=tags,
                path=str(path),
                root=str(root),
            )
            portable_name_match = path.name != "SKILL.md" or path.parent.name == name
            priority: tuple[object, ...] = (
                root_index,
                0 if portable_name_match else 1,
                len(relative.parts),
                str(relative),
            )
            current = selected.get(key)
            if current is None or priority < current[0]:
                selected[key] = (priority, sequence, skill)
            sequence += 1
    return [item[2] for item in sorted(selected.values(), key=lambda item: item[1])]


def scan_all_copies(
    roots: list[Path] | None = None, max_files_per_root: int = 1000
) -> list[Skill]:
    """Scan every active skill copy instead of hiding duplicate names."""
    roots = roots or common_roots()
    skills: list[Skill] = []
    seen_paths: set[str] = set()
    for root in roots:
        for path in iter_skill_files(root, max_files_per_root):
            try:
                resolved_path = str(path.resolve())
                name, desc, tags = parse_frontmatter(path)
            except (OSError, UnicodeError):
                continue
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            skills.append(
                Skill(
                    name=name,
                    description=desc,
                    keywords=tags,
                    path=resolved_path,
                    root=str(root),
                )
            )
    return skills


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def skill_drift_report(
    roots: list[Path] | None = None, *, include_rows: bool = False
) -> dict[str, object]:
    """Report active same-name copies whose bodies have drifted apart."""
    copies = scan_all_copies(roots)
    grouped: dict[str, list[dict[str, object]]] = {}
    unreadable = 0
    for skill in copies:
        try:
            digest = file_sha256(Path(skill.path))
            size = Path(skill.path).stat().st_size
        except OSError:
            unreadable += 1
            continue
        grouped.setdefault(skill.name.lower(), []).append(
            {
                "path": skill.path,
                "root": skill.root,
                "sha256": digest,
                "bytes": size,
            }
        )

    rows: list[dict[str, object]] = []
    for name, items in grouped.items():
        if len(items) < 2:
            continue
        variants = len({str(item["sha256"]) for item in items})
        rows.append(
            {
                "name": name,
                "canonical_name": canonical_skill_name(name),
                "copies": len(items),
                "variants": variants,
                "divergent": variants > 1,
                "paths": sorted(str(item["path"]) for item in items),
                "files": sorted(items, key=lambda item: str(item["path"])),
            }
        )
    rows.sort(
        key=lambda row: (
            not bool(row["divergent"]),
            -int(row["variants"]),
            -int(row["copies"]),
            str(row["name"]),
        )
    )
    divergent = [row for row in rows if bool(row["divergent"])]
    summary: dict[str, object] = {
        "active_files": len(copies),
        "unique_names": len(grouped),
        "duplicate_groups": len(rows),
        "divergent_groups": len(divergent),
        "identical_copy_groups": len(rows) - len(divergent),
        "divergent_files": sum(int(row["copies"]) for row in divergent),
        "unreadable_files": unreadable,
        "top_divergent": [
            {
                "name": row["name"],
                "canonical_name": row["canonical_name"],
                "copies": row["copies"],
                "variants": row["variants"],
                "paths": row["paths"],
            }
            for row in divergent[:20]
        ],
    }
    if include_rows:
        summary["rows"] = rows
    return summary


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def router_state_dir() -> Path:
    configured = os.getenv("AGENT_SKILL_ROUTER_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    state_home = os.getenv("XDG_STATE_HOME", "").strip()
    base = (
        Path(state_home).expanduser()
        if state_home
        else Path.home() / ".local" / "state"
    )
    return base / "agent-skill-router"


def route_events_file() -> Path:
    configured = os.getenv("AGENT_SKILL_ROUTER_LOG", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else router_state_dir() / "events.jsonl"
    )


def feedback_state_file() -> Path:
    return router_state_dir() / "learning.json"


def telemetry_key_file() -> Path:
    return router_state_dir() / ".telemetry-key"


def telemetry_key() -> bytes:
    path = telemetry_key_file()
    try:
        key = bytes.fromhex(path.read_text(encoding="ascii").strip())
        if len(key) >= 32:
            return key
    except (OSError, ValueError):
        pass
    key = os.urandom(32)
    atomic_write_text(path, key.hex() + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def telemetry_enabled() -> bool:
    return os.getenv("AGENT_SKILL_ROUTER_TELEMETRY", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def learning_enabled() -> bool:
    return os.getenv("AGENT_SKILL_ROUTER_LEARNING", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    """Append one compact event without ever persisting raw prompt text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        max_bytes = max(
            65536, int(os.getenv("AGENT_SKILL_ROUTER_LOG_MAX_BYTES", "5242880"))
        )
    except ValueError:
        max_bytes = 5242880
    try:
        if path.stat().st_size >= max_bytes:
            backup = path.with_suffix(path.suffix + ".1")
            backup.unlink(missing_ok=True)
            os.replace(path, backup)
    except OSError:
        pass
    encoded = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)


def signal_for(data: UsageData, name: str) -> UsageSignal:
    normalized = name.strip().lower()
    return data.signals.setdefault(normalized, UsageSignal())


def canonical_skill_signal(data: UsageData, name: str) -> UsageSignal:
    """Aggregate historical aliases so learning follows one responsibility."""
    canonical = canonical_skill_name(name)
    aggregate = UsageSignal()
    for observed_name, signal in data.signals.items():
        if canonical_skill_name(observed_name) != canonical:
            continue
        for field_name in (
            "routed",
            "applied",
            "views",
            "patches",
            "success",
            "failure",
            "legacy_suggested",
        ):
            setattr(
                aggregate,
                field_name,
                int(getattr(aggregate, field_name)) + int(getattr(signal, field_name)),
            )
        aggregate.last_activity = max(aggregate.last_activity, signal.last_activity)
    return aggregate


def tool_signal_for(data: UsageData, name: str) -> ToolSignal:
    normalized = canonical_tool_name(name) or name.strip().lower()
    return data.tool_signals.setdefault(normalized, ToolSignal())


def event_skill_name(event: dict[str, object]) -> str:
    raw_name = str(event.get("skill_name") or event.get("skill") or "").strip()
    if raw_name.lower() not in GENERIC_SKILL_NAMES and raw_name:
        return raw_name.lower()
    raw_path = str(event.get("skill_path") or event.get("path") or "").strip()
    if not raw_path:
        return raw_name.lower()
    path = Path(raw_path)
    return (
        path.parent.name if path.stem.lower() in GENERIC_SKILL_NAMES else path.stem
    ).lower()


def update_last_activity(signal: UsageSignal | ToolSignal, value: object) -> None:
    timestamp = str(value or "")
    if timestamp and timestamp > signal.last_activity:
        signal.last_activity = timestamp


def read_jsonl_events(path: Path, data: UsageData) -> Iterable[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    events: list[dict[str, object]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            data.malformed += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            data.malformed += 1
    return events


def load_usage_data(*, include_routes: bool = False) -> UsageData:
    """Merge truthful usage sidecars without reading skill bodies or raw prompts."""
    data = UsageData(signals={})
    home = Path.home()

    for path in (
        home / ".gg" / "skill-usage.jsonl",
        home / ".gg" / "skill-usage-archive.jsonl",
    ):
        for event in read_jsonl_events(path, data):
            event_type = str(event.get("event") or "")
            if event_type == "skill_loaded":
                name = event_skill_name(event)
                if name:
                    signal = signal_for(data, name)
                    signal.applied += 1
                    update_last_activity(signal, event.get("ts"))
            elif event_type == "prediction":
                predicted = event.get("predicted")
                if isinstance(predicted, str) and predicted:
                    signal_for(data, predicted).legacy_suggested += 1

    hermes_usage = home / ".hermes" / "skills" / ".usage.json"
    try:
        payload = json.loads(hermes_usage.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    records = payload.get("skills", payload) if isinstance(payload, dict) else {}
    if isinstance(records, dict):
        for name, record in records.items():
            if not isinstance(record, dict):
                continue
            signal = signal_for(data, str(name))
            signal.applied += int(record.get("use_count") or 0)
            signal.views += int(record.get("view_count") or 0)
            signal.patches += int(record.get("patch_count") or 0)
            update_last_activity(
                signal,
                max(
                    str(record.get("last_used_at") or ""),
                    str(record.get("last_viewed_at") or ""),
                    str(record.get("last_patched_at") or ""),
                ),
            )

    try:
        state = json.loads(feedback_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    feedback_skills = state.get("skills", {}) if isinstance(state, dict) else {}
    if isinstance(feedback_skills, dict):
        for name, record in feedback_skills.items():
            if not isinstance(record, dict):
                continue
            signal = signal_for(data, str(name))
            signal.success += int(record.get("success") or 0)
            signal.failure += int(record.get("failure") or 0)
            update_last_activity(signal, record.get("updated_at"))

    feedback_tools = state.get("tools", {}) if isinstance(state, dict) else {}
    if isinstance(feedback_tools, dict):
        for name, record in feedback_tools.items():
            if not isinstance(record, dict):
                continue
            signal = tool_signal_for(data, str(name))
            signal.used += int(record.get("used") or 0)
            signal.success += int(record.get("success") or 0)
            signal.failure += int(record.get("failure") or 0)
            signal.total_latency_ms += int(record.get("total_latency_ms") or 0)
            update_last_activity(signal, record.get("updated_at"))

    if include_routes:
        for event in read_jsonl_events(route_events_file(), data):
            event_type = str(event.get("event") or "")
            if event_type == "route":
                data.route_events += 1
                selected = event.get("selected")
                if isinstance(selected, list):
                    for name in selected:
                        if isinstance(name, str) and name:
                            signal = signal_for(data, name)
                            signal.routed += 1
                            update_last_activity(signal, event.get("ts"))
                recommended_tools = event.get("recommended_tools")
                if isinstance(recommended_tools, list):
                    for name in recommended_tools:
                        if isinstance(name, str) and canonical_tool_name(name):
                            signal = tool_signal_for(data, name)
                            signal.routed += 1
                            update_last_activity(signal, event.get("ts"))
            elif event_type == "feedback":
                data.feedback_events += 1
            elif event_type in {"tool_use", "tool_feedback"}:
                data.tool_events += 1
    return data


def learned_adjustment(signal: UsageSignal | None) -> int:
    """Bounded tie-breaker: use never creates relevance and feedback dominates."""
    if signal is None:
        return 0
    familiarity = min(2, math.floor(math.log2(signal.applied + 1)))
    total_feedback = signal.success + signal.failure
    feedback = (
        round(6 * (signal.success - signal.failure) / (total_feedback + 2))
        if total_feedback
        else 0
    )
    return max(-6, min(8, familiarity + feedback))


def learning_observation(data: UsageData) -> dict[str, object]:
    """Expose whether adaptive ranking has enough outcome evidence to trust."""
    canonical_names = {canonical_skill_name(name) for name in data.signals}
    skill_feedback = sum(
        canonical_skill_signal(data, name).success
        + canonical_skill_signal(data, name).failure
        for name in canonical_names
    )
    tool_feedback = sum(
        signal.success + signal.failure for signal in data.tool_signals.values()
    )
    last_activity = max(
        (
            signal.last_activity
            for signal in (*data.signals.values(), *data.tool_signals.values())
            if signal.last_activity
        ),
        default="",
    )
    outcome_events = skill_feedback + tool_feedback
    if outcome_events < 5:
        confidence = "low"
        reason = "fewer than 5 observed success/failure outcomes"
    elif outcome_events < 20 or data.route_events < 20:
        confidence = "medium"
        reason = "useful tie-breaker evidence, but observation window is still small"
    else:
        confidence = "high"
        reason = "at least 20 outcomes and 20 recorded routes"
    return {
        "confidence": confidence,
        "reason": reason,
        "route_events": data.route_events,
        "skill_feedback_outcomes": skill_feedback,
        "tool_feedback_outcomes": tool_feedback,
        "tool_events": data.tool_events,
        "last_activity": last_activity,
        "raw_prompts_stored": False,
        "raw_arguments_stored": False,
        "ranking_contract": "deterministic relevance first; adaptive adjustment is bounded to a tie-breaker",
    }


def record_route(result: RouteResult, *, strict: bool, source: str = "cli") -> str:
    route_id = hashlib.sha256(
        f"{time.time_ns()}:{os.getpid()}:{result.intent}".encode("utf-8")
    ).hexdigest()[:16]
    if not telemetry_enabled():
        return route_id
    append_jsonl(
        route_events_file(),
        {
            "schema": TELEMETRY_SCHEMA,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "route",
            "route_id": route_id,
            "intent_hash": hmac.new(
                telemetry_key(), result.intent.encode("utf-8"), hashlib.sha256
            ).hexdigest()[:16],
            "selected": [skill.name for skill in result.selected],
            "recommended_tools": [tool.name for tool in result.recommended_tools],
            "decision": result.decision,
            "top_score": result.top_score,
            "margin": result.margin,
            "strict": strict,
            "scanned": result.scanned,
            "catalog_source": result.catalog_source,
            "source": source,
        },
    )
    return route_id


def record_feedback(
    skill_name: str, outcome: str, route_id: str = ""
) -> dict[str, object]:
    normalized = canonical_skill_name(skill_name)
    if outcome not in {"success", "failure"}:
        raise ValueError("outcome must be success or failure")
    try:
        state = json.loads(feedback_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict) or state.get("schema") not in {
        None,
        TELEMETRY_SCHEMA,
    }:
        state = {}
    skills = state.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        state["skills"] = skills
    record = skills.get(normalized)
    if not isinstance(record, dict):
        record = {"success": 0, "failure": 0}
        skills[normalized] = record
    record[outcome] = int(record.get(outcome) or 0) + 1
    record["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["schema"] = TELEMETRY_SCHEMA
    atomic_write_text(
        feedback_state_file(),
        json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n",
    )
    event = {
        "schema": TELEMETRY_SCHEMA,
        "ts": record["updated_at"],
        "event": "feedback",
        "skill": normalized,
        "outcome": outcome,
        "route_id": route_id,
    }
    if telemetry_enabled():
        append_jsonl(route_events_file(), event)
    return event


def record_tool_usage(
    tool_name: str,
    outcome: str = "unknown",
    latency_ms: int = 0,
    *,
    event_name: str = "tool_use",
) -> dict[str, object]:
    """Record only canonical name/outcome/latency, never command args or output."""
    normalized = canonical_tool_name(tool_name)
    if normalized is None:
        raise ValueError(f"unknown tool: {tool_name}")
    if outcome not in {"success", "failure", "unknown"}:
        raise ValueError("outcome must be success, failure, or unknown")
    latency_ms = max(0, min(int(latency_ms), 3_600_000))
    try:
        state = json.loads(feedback_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict) or state.get("schema") not in {
        None,
        TELEMETRY_SCHEMA,
    }:
        state = {}
    tools = state.get("tools")
    if not isinstance(tools, dict):
        tools = {}
        state["tools"] = tools
    record = tools.get(normalized)
    if not isinstance(record, dict):
        record = {
            "used": 0,
            "success": 0,
            "failure": 0,
            "total_latency_ms": 0,
        }
        tools[normalized] = record
    record["used"] = int(record.get("used") or 0) + 1
    if outcome in {"success", "failure"}:
        record[outcome] = int(record.get(outcome) or 0) + 1
    record["total_latency_ms"] = int(record.get("total_latency_ms") or 0) + latency_ms
    record["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["schema"] = TELEMETRY_SCHEMA
    atomic_write_text(
        feedback_state_file(),
        json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n",
    )
    event = {
        "schema": TELEMETRY_SCHEMA,
        "ts": record["updated_at"],
        "event": event_name,
        "tool": normalized,
        "outcome": outcome,
        "latency_ms": latency_ms,
    }
    if telemetry_enabled():
        append_jsonl(route_events_file(), event)
    return event


def _hook_command(payload: dict[str, object]) -> str:
    for container_name in ("tool_input", "input", "arguments"):
        container = payload.get(container_name)
        if isinstance(container, dict):
            for key in ("command", "cmd"):
                value = container.get(key)
                if isinstance(value, str):
                    return value
    for key in ("command", "cmd"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def observed_tool_names(command: str) -> list[str]:
    """Read executable positions only; quoted arguments cannot become tools."""
    if not command.strip():
        return []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and all(character in ";|&\n" for character in token):
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(token)
    observed: list[str] = []
    for segment in segments:
        if not segment:
            continue
        index = 0
        while index < len(segment) and (
            "=" in segment[index] and not segment[index].startswith(("/", "./"))
        ):
            index += 1
        while index < len(segment) and Path(segment[index]).name in {
            "command",
            "env",
            "nice",
            "nohup",
            "sudo",
        }:
            index += 1
        if index >= len(segment):
            continue
        first = Path(segment[index]).name
        canonical = canonical_tool_name(first)
        if canonical and canonical not in observed:
            observed.append(canonical)
        if canonical == "rtk":
            index += 1
            if index < len(segment) and segment[index] == "proxy":
                index += 1
            if index < len(segment):
                wrapped = canonical_tool_name(Path(segment[index]).name)
                if wrapped and wrapped not in observed:
                    observed.append(wrapped)
    return observed


def _hook_outcome(payload: dict[str, object]) -> str:
    candidates: list[object] = [payload]
    for key in ("tool_response", "response", "result", "output", "extra"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ("exit_code", "exitCode", "code"):
            value = candidate.get(key)
            if isinstance(value, int):
                return "success" if value == 0 else "failure"
        value = str(candidate.get("status") or "").lower()
        if value in {"success", "succeeded", "completed", "ok"}:
            return "success"
        if value in {"failure", "failed", "error"}:
            return "failure"
    return "unknown"


def _hook_latency_ms(payload: dict[str, object]) -> int:
    candidates: list[dict[str, object]] = [payload]
    for key in ("tool_response", "response", "result", "extra"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in candidates:
        for key in ("latency_ms", "duration_ms", "elapsed_ms"):
            value = candidate.get(key)
            if isinstance(value, (int, float)):
                return max(0, min(round(value), 3_600_000))
    return 0


def observe_hook_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    outcome = _hook_outcome(payload)
    latency_ms = _hook_latency_ms(payload)
    return [
        record_tool_usage(name, outcome, latency_ms)
        for name in observed_tool_names(_hook_command(payload))
    ]


HOOK_MATCHER = r"Bash|Shell|shell|shell_command|exec_command|functions\.exec_command"


def hook_command() -> str:
    return str(Path.home() / ".local" / "bin" / "si") + " observe"


def hook_config_path(target: str) -> Path:
    if target == "codex":
        return Path.home() / ".codex" / "hooks.json"
    if target == "claude":
        return Path.home() / ".claude" / "settings.json"
    if target == "hermes":
        return Path.home() / ".hermes" / "config.yaml"
    raise ValueError(f"unknown hook target: {target}")


def hook_has_observer(target: str) -> bool:
    path = hook_config_path(target)
    if target == "hermes":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        return (
            re.search(r"(?m)^hooks:\s*$", text) is not None
            and re.search(r"(?m)^  post_tool_call:\s*$", text) is not None
            and f"command: {json.dumps(hook_command())}" in text
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    post = (
        payload.get("hooks", {}).get("PostToolUse", [])
        if isinstance(payload, dict)
        else []
    )
    if not isinstance(post, list):
        return False
    for entry in post:
        hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
        if isinstance(hooks, list) and any(
            isinstance(hook, dict) and hook.get("command") == hook_command()
            for hook in hooks
        ):
            return True
    return False


def install_hermes_hook(dry_run: bool = False) -> dict[str, object]:
    """Append the native Hermes post_tool_call hook without a YAML dependency."""
    path = hook_config_path("hermes")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    command_line = f"      command: {json.dumps(hook_command())}\n"
    if command_line.strip() in text:
        return {
            "target": "hermes",
            "path": str(path),
            "changed": False,
            "dry_run": dry_run,
        }
    entry = (
        '    - matcher: "terminal|shell|bash"\n' + command_line + "      timeout: 3\n"
    )
    null_hooks = re.search(r"(?m)^hooks:\s*(?:null|~)\s*$", text)
    if null_hooks:
        updated = (
            text[: null_hooks.start()]
            + "hooks:\n  post_tool_call:\n"
            + entry
            + text[null_hooks.end() :]
        )
    else:
        lines = text.splitlines(keepends=True)
        hooks_index = next(
            (
                index
                for index, line in enumerate(lines)
                if re.match(r"^hooks:\s*$", line)
            ),
            None,
        )
        if hooks_index is None:
            separator = "" if not text or text.endswith("\n") else "\n"
            updated = text + separator + "hooks:\n  post_tool_call:\n" + entry
        else:
            block_end = next(
                (
                    index
                    for index in range(hooks_index + 1, len(lines))
                    if lines[index].strip()
                    and not lines[index].startswith((" ", "\t", "#"))
                ),
                len(lines),
            )
            post_index = next(
                (
                    index
                    for index in range(hooks_index + 1, block_end)
                    if re.match(r"^  post_tool_call:\s*$", lines[index])
                ),
                None,
            )
            insert_at = post_index + 1 if post_index is not None else block_end
            addition = (
                entry if post_index is not None else "  post_tool_call:\n" + entry
            )
            lines.insert(insert_at, addition)
            updated = "".join(lines)
    if not dry_run:
        atomic_write_text(path, updated)
    return {"target": "hermes", "path": str(path), "changed": True, "dry_run": dry_run}


def install_hooks(
    target: str = "all", dry_run: bool = False
) -> list[dict[str, object]]:
    names = ["codex", "claude", "hermes"] if target == "all" else [target]
    results = []
    for name in names:
        if name == "hermes":
            results.append(install_hermes_hook(dry_run=dry_run))
            continue
        path = hook_config_path(name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            payload = {}
        except ValueError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object in {path}")
        hooks = payload.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError(f"expected hooks object in {path}")
        post = hooks.setdefault("PostToolUse", [])
        if not isinstance(post, list):
            raise ValueError(f"expected PostToolUse list in {path}")
        present = any(
            isinstance(entry, dict)
            and any(
                isinstance(hook, dict) and hook.get("command") == hook_command()
                for hook in entry.get("hooks", [])
                if isinstance(entry.get("hooks"), list)
            )
            for entry in post
        )
        changed = not present
        if changed:
            post.append(
                {
                    "matcher": HOOK_MATCHER,
                    "hooks": [
                        {"type": "command", "command": hook_command(), "timeout": 3}
                    ],
                }
            )
            if not dry_run:
                atomic_write_text(path, json.dumps(payload, indent=2) + "\n")
        results.append(
            {"target": name, "path": str(path), "changed": changed, "dry_run": dry_run}
        )
    return results


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


def _ordered_tokens(text: str) -> list[str]:
    """Normalized tokens in original order (for bigram phrase matching)."""
    out: list[str] = []
    for raw in WORD_RE.findall(text or ""):
        lowered = raw.lower()
        if lowered in STOPWORDS:
            continue
        expansion = TOKEN_EXPANSIONS.get(lowered)
        if expansion:
            out.extend(expansion)
        else:
            out.append(TOKEN_NORMALIZATION.get(lowered, lowered))
    return out


def _intent_bigrams(text: str) -> list[str]:
    tokens = [t for t in _ordered_tokens(text) if len(t) > 2]
    return [f"{a} {b}" for a, b in zip(tokens, tokens[1:]) if a != b]


def normalized_phrase_text(text: str) -> str:
    normalized = re.sub(r"[-_]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def mention_is_negated(text: str, start: int) -> bool:
    """True when a negation cue governs the phrase at `start` within its clause."""
    clause_start = max(
        (text.rfind(char, 0, start) for char in CLAUSE_BOUNDARY_CHARS), default=-1
    )
    return bool(NEGATION_CUE_RE.search(text[clause_start + 1 : start]))


def mentioned_skill_names(intent: str, skills: list[Skill]) -> list[str]:
    """Resolve `$names` plus naturally named multi-word skills in user order.

    A naturally named skill is inferred from prose, so an explicit refusal in
    the same clause drops it. A `$name` is a deliberate invocation sigil and is
    always honoured.

    Explicit mentions are located in the raw `intent` string; natural mentions
    are located in `normalized_intent`, a separately whitespace-collapsed
    copy, so the sort and the overlap check below compare two different
    coordinate systems directly. A regex-per-skill, single-coordinate rewrite
    was tried and measured: correct, but ~50ms slower per cold CLI invocation
    (100ms+ of `re.compile` for the ~800 multi-word names in the real
    catalog -- an in-memory cache does not survive across CLI invocations, so
    it never warms up). It was reverted.

    The mixed-coordinate version is safe today because normalization only
    shrinks positions and always leaves at least one separator character per
    collapsed run, which keeps relative ordering intact; over 60,000 targeted
    fuzz trials (heavy irregular whitespace, mixed $name/natural mentions,
    adjacency edge cases) found no case where it produces a wrong result. If
    `normalized_phrase_text` ever changes to a transform that can *grow* a
    string (e.g. Unicode NFKC expansion, symbol-to-word expansion), that
    invariant breaks and this needs the single-coordinate rewrite instead.
    """
    mentions: list[tuple[int, int, str, bool]] = [
        (match.start(), match.end(), match.group(1).lower(), True)
        for match in EXPLICIT_SKILL_RE.finditer(intent)
    ]
    normalized_intent = normalized_phrase_text(intent)
    if NATURAL_SKILL_CUE_RE.search(intent):
        for skill in skills:
            phrase = normalized_phrase_text(skill.name)
            if " " not in phrase:
                continue
            start = 0
            while True:
                index = normalized_intent.find(phrase, start)
                if index < 0:
                    break
                end = index + len(phrase)
                before_ok = index == 0 or not (
                    normalized_intent[index - 1].isalnum()
                    or normalized_intent[index - 1] in "_+-"
                )
                after_ok = end == len(normalized_intent) or not (
                    normalized_intent[end].isalnum()
                    or normalized_intent[end] in "_+-"
                )
                if (
                    before_ok
                    and after_ok
                    and not mention_is_negated(normalized_intent, index)
                ):
                    mentions.append((index, end, skill.name.lower(), False))
                start = index + 1
    # Longest phrase wins when names overlap: "macos-computer-use" must not
    # implicitly add the nested "computer-use" skill.
    mentions.sort(key=lambda item: (item[0], -(item[1] - item[0]), not item[3]))
    names: list[str] = []
    accepted_spans: list[tuple[int, int]] = []
    for start, end, name, _explicit in mentions:
        if name in names:
            continue
        if any(
            start < prior_end and end > prior_start
            for prior_start, prior_end in accepted_spans
        ):
            continue
        names.append(name)
        accepted_spans.append((start, end))
    return names


def natural_names_are_complete_stack(intent: str, names: list[str]) -> bool:
    """True when the request only asks to load/combine the named skills."""
    named_tokens: set[str] = set()
    for name in names:
        named_tokens.update(words(name.replace("-", " ")))
    residual_workflow = (words(intent) - named_tokens) & WORKFLOW_TOKENS
    return not (residual_workflow - {"combine", "load"})


def without_natural_skill_mentions(intent: str, names: list[str]) -> str:
    """Remove named-skill phrases so the underlying task can choose a primary."""
    masked = intent
    for name in sorted(names, key=len, reverse=True):
        parts = [part for part in re.split(r"[-_\s]+", name) if part]
        if not parts:
            continue
        pattern = r"(?<![\w+])" + r"[-_\s]+".join(
            re.escape(part) for part in parts
        ) + r"(?![\w+])"
        masked = re.sub(pattern, " ", masked, flags=re.IGNORECASE)
    return NATURAL_SKILL_CUE_RE.sub(" ", masked)


def negated_skill_names(intent: str, skills: list[Skill]) -> list[str]:
    """Skill names whose phrase appears under a negation cue in its clause."""
    normalized = normalized_phrase_text(intent)
    negated = []
    for skill in skills:
        phrase = normalized_phrase_text(skill.name)
        if not phrase:
            continue
        index = normalized.find(phrase)
        while index >= 0:
            end = index + len(phrase)
            bounded = (index == 0 or not normalized[index - 1].isalnum()) and (
                end == len(normalized) or not normalized[end].isalnum()
            )
            if bounded and mention_is_negated(normalized, index):
                negated.append(skill.name.lower())
                break
            index = normalized.find(phrase, index + 1)
    return negated


def without_negated_skill_mentions(intent: str, skills: list[Skill]) -> str:
    """Drop refused skill phrases so they cannot score as evidence.

    Only the named phrase is removed, never the whole clause: "fix the bug
    without best practices" must keep "fix the bug" as routable intent.
    """
    names = negated_skill_names(intent, skills)
    return without_natural_skill_mentions(intent, names) if names else intent


def actionable_clauses(intent: str) -> list[str]:
    clauses = []
    for raw in CLAUSE_SPLIT_RE.split(intent):
        clause = raw.strip(" \t\r\n-–—:()[]")
        if clause and words(clause) & WORKFLOW_TOKENS:
            clauses.append(clause)
    return clauses


def skill_words(skill: Skill) -> frozenset[str]:
    return (
        words(skill.name.replace("-", " "))
        | words(skill.description)
        | words(skill.keywords)
    )


def score(
    intent: str,
    skill: Skill,
    doc_freq: Counter | None = None,
    favorites: dict[str, int] | None = None,
) -> int:
    tw = tuned_weights()
    iw = words(intent)
    nw = words(skill.name.replace("-", " "))
    dw = words(skill.description)
    kw = words(skill.keywords)
    if not iw:
        return 0
    s = 0.0
    # Keyword-stuffed mega-descriptions must not outrank precise short ones:
    # damp the description contribution linearly past desc_damp_start words.
    desc_scale = 1.0
    if len(dw) > tw["desc_damp_start"]:
        desc_scale = max(tw["desc_damp_floor"], tw["desc_damp_start"] / len(dw))
    for token in iw & nw:
        s += tw["name_w"] * rarity(token, doc_freq)
    for token in iw & dw:
        s += tw["desc_w"] * desc_scale * rarity(token, doc_freq)
    for token in iw & kw:
        s += tw["kw_w"] * rarity(token, doc_freq)
    # Coverage: a skill matching several intent tokens must outrank a skill
    # that hit one lucky rare token (e.g. "builder" in an unrelated name).
    matched = (iw & nw) | (iw & dw) | (iw & kw)
    if len(matched) > 1:
        s += tw["coverage_w"] * (len(matched) - 1)
    lowered = intent.lower()
    # Phrase-level evidence: "pull request", "core web", "fine tuning" are far
    # more specific than their unigrams. Name hits beat description hits.
    name_hay = skill.name.lower().replace("-", " ")
    desc_hay = skill.description.lower()
    for bigram in _intent_bigrams(intent):
        if bigram in name_hay:
            s += tw["bigram_name"]
        elif bigram in desc_hay:
            s += tw["bigram_desc"]
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
    debug_failure_intent = iw & {"debug", "fail"}
    platform_test_intent = "test" in iw and bool(iw & PLATFORM_TOKENS)
    if is_software_dev and (
        debug_failure_intent & skill_words
        or (platform_test_intent and "test" in skill_words)
    ):
        s += 20
    if is_software_dev and "python" in iw and "python" in (nw | dw | kw):
        s += 12
    # Security review is a closed local-code task. Prefer skills that actually
    # cover security/review; a generic web/API skill must not win on "api".
    if iw & SECURITY_TOKENS and skill_words & SECURITY_TOKENS:
        s += 20
    if iw & REVIEW_TOKENS and skill_words & (SECURITY_TOKENS | REVIEW_TOKENS):
        s += 12
    if {"security", "review"} <= iw and {"security", "review"} <= nw:
        s += 12
    # Exact output-format names carry more intent than the generic words
    # "create" or "report", even when hundreds of skills mention PDFs.
    if len(nw) == 1 and nw <= iw and nw & EXACT_ARTIFACT_NAME_TOKENS:
        s += 16
    # German compounds expand into the same domain pair as the canonical
    # skill name. Reward that pair over broad descriptions that merely mention
    # prompts or evidence somewhere in a universal workflow.
    if "prompt" in iw and iw & {"library", "source"}:
        if {"prompt", "library"} <= nw:
            s += 16
    if "synthesize" in iw and iw & {"claim", "document", "evidence"}:
        if {"evidence", "synthesize"} <= nw:
            s += 16
    # An audio-only briefing workflow needs positive modality evidence. The
    # noun "briefing" alone usually denotes a written research artifact and
    # must not pull a TTS player into an otherwise text-only bundle.
    audio_only_skill = {"audio", "tts"} <= skill_words
    if audio_only_skill and not (iw & AUDIO_OUTPUT_TOKENS):
        s -= 20
    # A German verb such as "prüfe" used with "pull request" means review,
    # not merely execute tests. Prefer the dedicated PR-review workflows over
    # skills that happen to mention PR checks or GitHub comments.
    pull_request_review = (
        "review" in iw
        and bool(re.search(r"\b(?:pull\s+request|merge\s+request|pr)\b", lowered))
    )
    if (
        pull_request_review
        and canonical_skill_name(skill.name) in PULL_REQUEST_REVIEW_SKILL_NAMES
    ):
        s += 20
        if "github" in iw and "github" in nw:
            s += 8
    # "Ladezeit" normalizes to performance. Landing-page wording otherwise
    # overweights ad/copy skills, so preserve the technical web-performance
    # domain when speed is the requested outcome.
    web_performance_intent = (
        "performance" in iw
        and bool(iw & {"landing", "lcp", "page", "speed", "vitals"})
    )
    if web_performance_intent:
        canonical_name = canonical_skill_name(skill.name)
        if canonical_name in WEB_PERFORMANCE_SKILL_NAMES:
            s += 20
        elif nw & {"ad", "ads", "creative"}:
            s -= 8
    # When a request clearly clusters around token/context infrastructure,
    # reject accidental matches such as ML skills that only mention "memory"
    # or "accuracy". Require the candidate itself to cover the domain broadly.
    if len(iw & TOKEN_CONTEXT_TOKENS) >= 2:
        domain_coverage = len(skill_words & TOKEN_CONTEXT_TOKENS)
        if domain_coverage >= 2:
            s += 12
        elif domain_coverage == 0:
            s -= 12
    # Requests about improving the skill router itself are governance work.
    # A fetch/router implementation may share the words "skill" and "route",
    # but it is not a portfolio-quality or routing-policy workflow.
    skill_router_management = (
        {"skill", "route"} <= iw
        and bool(iw & SKILL_ROUTER_MANAGEMENT_TOKENS)
    )
    if skill_router_management:
        canonical_name = canonical_skill_name(skill.name)
        if canonical_name in SKILL_ROUTER_GOVERNANCE_NAMES:
            s += 12
        elif not (skill_words & SKILL_ROUTER_MANAGEMENT_TOKENS):
            s -= 10
    # "agent team" is a workflow concept, not a request for Microsoft Teams.
    # Prefer skills that describe controller/worker contracts and penalize
    # meeting/calendar integrations that only match the generic word "team".
    if {"agent", "team"} <= iw:
        team_coverage = len(skill_words & AGENT_TEAM_TOKENS)
        if team_coverage >= 2:
            s += 4 * team_coverage
        elif skill_words & MEETING_TOKENS:
            s -= 12
    # Control/orchestration skills (2026-07-24): abstract multi-step intents that
    # ask for closed-loop / goal / verify / orchestrate workflows must strongly
    # prefer control skills (agent-loop, omnigoal, verification-loop, master-check,
    # goalmaster). Require the candidate itself to cover the control domain.
    control_intent = iw & CONTROL_TOKENS
    if len(control_intent) >= 2:
        control_coverage = len(skill_words & CONTROL_TOKENS)
        if control_coverage >= 2:
            s += 15 + 2 * (control_coverage - 2)
        elif control_coverage == 0 and not (skill_words & AGENT_TEAM_TOKENS):
            s -= 8
    # Name-level control match (2026-07-24): a skill whose NAME contains a control
    # token from the intent (e.g. "verification-loop" for "... verification gate")
    # is the canonical pick. Description-stuffed skills must not outrank it.
    name_control = iw & nw & CONTROL_TOKENS
    if name_control:
        s += 18 * len(name_control)
    skill_platforms = (nw | dw | kw) & PLATFORM_TOKENS
    requested_platforms = iw & PLATFORM_TOKENS
    if is_software_dev and debug_failure_intent and skill_platforms:
        if not requested_platforms:
            # A generic diagnosis must prefer the generic root-cause workflow.
            # Platform debuggers require positive Node/Python/etc. evidence.
            s -= 20
        elif not (skill_platforms & requested_platforms):
            s -= 20
    elif (
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


def rank_candidates(
    intent: str,
    skills: list[Skill],
    favorites: dict[str, int] | None = None,
    usage_data: UsageData | None = None,
) -> list[tuple[int, int, int, Skill]]:
    """Return total, deterministic base, adaptive tie-breaker, and skill."""
    # Single choke point for every scoring path, so a refused skill cannot win
    # on content score after mention detection already declined it.
    intent = without_negated_skill_mentions(intent, skills)
    available_names = {skill.name.lower() for skill in skills}
    routable = [
        skill
        for skill in skills
        if skill.name.lower() not in AUTO_ROUTE_EXCLUDED
        or (
            skill.name.lower() in SKILL_ALIASES
            and canonical_skill_name(skill.name.lower()) not in available_names
        )
    ]
    frequencies = doc_frequencies(routable)
    ranked: list[tuple[int, int, int, Skill]] = []
    for skill in routable:
        base = score(intent, skill, frequencies, favorites)
        adaptive = 0
        if base > 0 and usage_data is not None:
            adaptive = learned_adjustment(
                canonical_skill_signal(usage_data, skill.name)
            )
        ranked.append((base + adaptive, base, adaptive, skill))
    ranked.sort(
        key=lambda item: (
            -item[0],
            0 if favorites and item[3].name.lower() in favorites else 1,
            item[3].name,
        )
    )
    intent_words = words(intent)
    if (
        intent_words & SECURITY_TOKENS
        and intent_words & REVIEW_TOKENS
        and len(actionable_clauses(intent)) <= 1
    ):
        review_ranked = []
        for item in ranked:
            skill = item[3]
            skill_words = (
                words(skill.name.replace("-", " "))
                | words(skill.description)
                | words(skill.keywords)
            )
            if skill_words & REVIEW_TOKENS and skill_words & SECURITY_TOKENS:
                review_ranked.append(item)
        if review_ranked:
            ranked = review_ranked
    return ranked


def is_control_skill_tie(items: list[tuple[int, int, int, Skill]]) -> bool:
    return len(items) >= 2 and all(
        canonical_skill_name(item[3].name) in CONTROL_SKILL_NAMES for item in items[:2]
    )


def is_safe_domain_tie(items: list[tuple[int, int, int, Skill]]) -> bool:
    if is_control_skill_tie(items):
        return True
    return len(items) >= 2 and all(
        canonical_skill_name(item[3].name) in SKILL_ROUTER_GOVERNANCE_NAMES
        for item in items[:2]
    )


def selection_roles(selected: list[Skill]) -> dict[str, str]:
    return {
        skill.name: "primary" if index == 0 else "support"
        for index, skill in enumerate(selected)
    }


def alternative_summaries(
    ranked: list[tuple[int, int, int, Skill]], limit: int = 3
) -> list[dict[str, object]]:
    rows = []
    for total, base, adaptive, skill in ranked:
        if total <= 0:
            continue
        rows.append(
            {
                "name": skill.name,
                "score": total,
                "base_score": base,
                "adaptive_adjustment": adaptive,
                "path": skill.path,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def complementary_bundle(
    intent: str,
    ranked: list[tuple[int, int, int, Skill]],
    skills: list[Skill],
    limit: int,
    favorites: dict[str, int] | None = None,
    usage_data: UsageData | None = None,
) -> list[tuple[int, int, int, Skill]]:
    """Select one primary plus skills that cover still-uncovered intent evidence."""
    positive = [item for item in ranked if item[0] > 0]
    if not positive:
        return []
    limit = max(1, min(limit, MAX_AUTOMATIC_SELECTED))
    intent_words = words(intent)
    frequencies = doc_frequencies(skills)
    clauses = actionable_clauses(intent)
    global_by_name = {item[3].name: item for item in positive}
    clause_winners: list[tuple[int, int, int, Skill]] = []

    # A broad multi-phase prompt can make one domain boost dwarf another
    # legitimate phase. For a real multi-clause request, build the bundle in
    # task order so a generic full-prompt match cannot displace phase one.
    if len(clauses) >= 2:
        for clause in clauses:
            clause_positive = [
                item
                for item in rank_candidates(clause, skills, favorites, usage_data)
                if item[0] > 0
            ]
            if not clause_positive or clause_positive[0][1] < MIN_STRICT_SCORE:
                continue
            clause_margin = clause_positive[0][0] - (
                clause_positive[1][0] if len(clause_positive) > 1 else 0
            )
            if (
                len(clause_positive) > 1
                and clause_margin < MIN_STRICT_MARGIN
                and not is_safe_domain_tie(clause_positive)
            ):
                continue
            clause_item = clause_positive[0]
            clause_winners.append(
                global_by_name.get(clause_item[3].name, clause_item)
            )

    # Two-clause requests often have a precise holistic winner (for example
    # scrape + extract -> Superweb). With three or more phases, clause order is
    # the safer primary signal than a description that mentions everything.
    ordered_clause_primary = len(clauses) >= 3 and bool(clause_winners)
    primary = clause_winners[0] if ordered_clause_primary else positive[0]
    selected = [primary]
    if limit == 1:
        return selected
    covered = intent_words & skill_words(primary[3])
    selected_names = {primary[3].name}

    remaining_clause_winners = (
        clause_winners[1:] if ordered_clause_primary else clause_winners
    )
    for item in remaining_clause_winners:
        skill = item[3]
        if skill.name in selected_names:
            continue
        selected.append(item)
        selected_names.add(skill.name)
        covered |= intent_words & skill_words(skill)
        if len(selected) >= limit:
            return selected

    floor = max(MIN_STRICT_SCORE, round(positive[0][0] * 0.35))
    for item in positive[1:]:
        total, base, _adaptive, skill = item
        if skill.name in selected_names:
            continue
        if total < floor or base < MIN_STRICT_SCORE:
            continue
        matched = intent_words & skill_words(skill)
        new_matches = matched - covered
        has_workflow_evidence = bool(matched & WORKFLOW_TOKENS)
        has_security_review_evidence = bool(
            matched & SECURITY_TOKENS
            and intent_words & REVIEW_TOKENS
            and skill_words(skill) & REVIEW_TOKENS
        )
        if not (has_workflow_evidence or has_security_review_evidence):
            continue
        informative = {
            token
            for token in new_matches
            if rarity(token, frequencies) >= 0.5
            and token not in BUNDLE_MODIFIER_TOKENS
        }
        # A generic modifier (for example "natural") is insufficient evidence
        # for another skill. A concrete new facet such as "auth" remains valid.
        if not informative:
            continue
        selected.append(item)
        selected_names.add(skill.name)
        covered |= matched
        if len(selected) >= limit:
            break
    return selected


def route(
    intent: str,
    max_selected: int = DEFAULT_MAX_SELECTED,
    roots: list[Path] | None = None,
    strict: bool = False,
    refresh_index: bool = False,
    catalog_data: Catalog | None = None,
    usage_data: UsageData | None = None,
) -> RouteResult:
    max_selected = selection_limit(max_selected)
    automatic_limit = min(max_selected, MAX_AUTOMATIC_SELECTED)
    catalog_data = catalog_data or load_catalog(roots, refresh=refresh_index)
    skills = catalog_data.skills
    root_paths = catalog_data.roots
    favorites = load_favorites()
    if usage_data is None and learning_enabled():
        usage_data = load_usage_data()
    recommended_tools = recommend_tools(intent, usage_data)
    by_name = {skill.name.lower(): skill for skill in skills}
    bare_name = intent.strip().lower()
    dollar_names = [
        match.group(1).lower() for match in EXPLICIT_SKILL_RE.finditer(intent)
    ]
    if bare_name in by_name or canonical_skill_name(bare_name) in by_name:
        explicit_names = [bare_name]
    else:
        explicit_names = mentioned_skill_names(intent, skills)
    if explicit_names:
        named_selected = []
        for name in explicit_names:
            skill = by_name.get(canonical_skill_name(name)) or by_name.get(name)
            if skill is not None and skill not in named_selected:
                named_selected.append(skill)
        selected = named_selected[:max_selected]
        decision = "explicit"
        top_score = margin = 0
        alternatives: list[dict[str, object]] = []
        hybrid_natural_request = (
            not dollar_names
            and bare_name not in by_name
            and canonical_skill_name(bare_name) not in by_name
            and len(named_selected) < automatic_limit
            and not natural_names_are_complete_stack(intent, explicit_names)
        )
        if hybrid_natural_request:
            inferred = route(
                without_natural_skill_mentions(intent, explicit_names),
                max_selected=1,
                strict=strict,
                catalog_data=catalog_data,
                usage_data=usage_data,
            )
            selected = []
            for skill in [*inferred.selected, *named_selected]:
                if skill not in selected:
                    selected.append(skill)
            selected = selected[:automatic_limit]
            decision = "mixed-explicit" if inferred.selected else "explicit"
            top_score = inferred.top_score
            margin = inferred.margin
            alternatives = inferred.alternatives
        roles = selection_roles(selected)
        block = render_router_block(
            intent,
            selected,
            len(skills),
            root_paths,
            favorites,
            recommended_tools,
            roles=roles,
            alternatives=alternatives,
        )
        return RouteResult(
            intent=intent,
            selected=selected,
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
            decision=decision,
            top_score=top_score,
            margin=margin,
            recommended_tools=recommended_tools,
            selection_roles=roles,
            alternatives=alternatives,
        )
    if explicit_tool_names(intent):
        block = render_router_block(
            intent, [], len(skills), root_paths, favorites, recommended_tools
        )
        return RouteResult(
            intent=intent,
            selected=[],
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
            decision="explicit-tool",
            recommended_tools=recommended_tools,
        )
    intent_words = words(intent)
    if (
        recommended_tools
        and recommended_tools[0].base_score >= 12
        and intent_words & DIRECT_TOOL_TOKENS
        and not intent_words & MATERIAL_TASK_TOKENS
    ):
        block = render_router_block(
            intent, [], len(skills), root_paths, favorites, recommended_tools
        )
        return RouteResult(
            intent=intent,
            selected=[],
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
            decision="tool-selected",
            recommended_tools=recommended_tools,
        )
    if not (intent_words & WORKFLOW_TOKENS):
        # Fallback (2026-07-23): the verb allowlist used to hard-drop requests
        # like "send a telegram message" or "train a lora" even when a skill
        # matched strongly. A confident deterministic content match now beats
        # the missing verb; only weak/ambiguous intents stay zero-skill.
        tw = tuned_weights()
        fb_ranked = rank_candidates(intent, skills, favorites, usage_data)
        fb_positive = [item for item in fb_ranked if item[0] > 0]
        fb_top = fb_positive[0][0] if fb_positive else 0
        fb_margin = fb_top - fb_positive[1][0] if len(fb_positive) > 1 else fb_top
        if (
            fb_positive
            and fb_top >= tw["no_workflow_min_score"]
            and fb_margin >= tw["no_workflow_min_margin"]
        ):
            selected = [fb_positive[0][3]][:automatic_limit]
            roles = selection_roles(selected)
            block = render_router_block(
                intent,
                selected,
                len(skills),
                root_paths,
                favorites,
                recommended_tools,
                roles=roles,
            )
            return RouteResult(
                intent=intent,
                selected=selected,
                scanned=len(skills),
                roots=[str(p) for p in root_paths],
                router_block=block,
                catalog_source=catalog_data.source,
                decision="content-fallback",
                top_score=fb_top,
                margin=fb_margin,
                recommended_tools=recommended_tools,
                selection_roles=roles,
            )
        alternatives = alternative_summaries(fb_ranked)
        block = render_router_block(
            intent,
            [],
            len(skills),
            root_paths,
            favorites,
            recommended_tools,
            alternatives=alternatives,
        )
        return RouteResult(
            intent=intent,
            selected=[],
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
            decision="no-workflow",
            recommended_tools=recommended_tools,
            alternatives=alternatives,
        )
    if "test" in intent_words and intent_words <= PLAIN_TEST_TOKENS:
        block = render_router_block(
            intent, [], len(skills), root_paths, favorites, recommended_tools
        )
        return RouteResult(
            intent=intent,
            selected=[],
            scanned=len(skills),
            roots=[str(p) for p in root_paths],
            router_block=block,
            catalog_source=catalog_data.source,
            decision="plain-test",
            recommended_tools=recommended_tools,
        )
    ranked = rank_candidates(intent, skills, favorites, usage_data)
    positive = [item for item in ranked if item[0] > 0]
    top_score = positive[0][0] if positive else 0
    margin = top_score - positive[1][0] if len(positive) > 1 else top_score
    bundle = complementary_bundle(
        intent, ranked, skills, automatic_limit, favorites, usage_data
    )
    decision = "selected" if positive else "no-match"
    if strict:
        top_base = positive[0][1] if positive else 0
        if not positive or top_base < MIN_STRICT_SCORE:
            positive = []
            bundle = []
            decision = "low-confidence" if top_score else "no-match"
        elif len(positive) > 1 and margin < MIN_STRICT_MARGIN:
            confident_multiphase_bundle = (
                len(bundle) >= 2 and len(actionable_clauses(intent)) >= 2
            )
            if is_safe_domain_tie(positive) or confident_multiphase_bundle:
                decision = "selected"
            else:
                positive = []
                bundle = []
                decision = "ambiguous"
    selected = [item[3] for item in bundle] if positive else []
    roles = selection_roles(selected)
    alternatives = alternative_summaries(ranked) if not selected else []
    block = render_router_block(
        intent,
        selected,
        len(skills),
        root_paths,
        favorites,
        recommended_tools,
        roles=roles,
        alternatives=alternatives,
    )
    return RouteResult(
        intent=intent,
        selected=selected,
        scanned=len(skills),
        roots=[str(p) for p in root_paths],
        router_block=block,
        catalog_source=catalog_data.source,
        decision=decision,
        top_score=top_score,
        margin=margin,
        recommended_tools=recommended_tools,
        selection_roles=roles,
        alternatives=alternatives,
    )


def render_router_block(
    intent: str,
    selected: list[Skill],
    scanned: int,
    roots: list[Path],
    favorites: dict[str, int] | None = None,
    recommended_tools: list[ToolRecommendation] | None = None,
    roles: dict[str, str] | None = None,
    alternatives: list[dict[str, object]] | None = None,
) -> str:
    lines = [f"router: {SKILL_NAME}", f"intent: {intent}", f"scanned: {scanned}"]
    if selected:
        lines.append("load:")
        for s in selected:
            star = " ★" if favorites and s.name.lower() in favorites else ""
            role = f" [{roles[s.name]}]" if roles and s.name in roles else ""
            lines.append(
                f"- {s.name}{star}{role}: {s.description[:160]} ({s.path})"
            )
    else:
        lines.append("load: []")
    if alternatives:
        lines.append("consider:")
        for candidate in alternatives:
            lines.append(
                f"- {candidate['name']}: score={candidate['score']} "
                f"base={candidate['base_score']} ({candidate['path']})"
            )
    if recommended_tools:
        lines.append("tools:")
        for tool in recommended_tools:
            lines.append(f"- {tool.name}: {tool.path}")
    else:
        lines.append("tools: []")
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


def default_eval_set_path() -> Path:
    return Path.home() / ".local/state/agent-skill-router/eval-set.json"


def quality_bench(
    eval_path: Path | None = None,
    *,
    max_selected: int = 3,
    refresh_index: bool = False,
) -> dict[str, object]:
    """Labeled routing-quality benchmark: P@1, P@3, empty-rate, latency.

    Eval file format: [{"q": "...", "accept": ["skill-a", "skill-b"]}, ...]
    An empty accept list means the correct answer is zero skills.
    """
    import time as _time

    path = eval_path or default_eval_set_path()
    cases = json.loads(path.read_text(encoding="utf-8"))
    catalog_data = load_catalog(refresh=refresh_index)
    usage_data = load_usage_data() if learning_enabled() else None
    p1 = p3 = empty_correct = 0
    latencies: list[float] = []
    rows = []
    for case in cases:
        query = case["q"]
        accept = [a.lower() for a in case.get("accept", [])]
        t0 = _time.perf_counter()
        rr = route(
            query,
            max_selected=max_selected,
            catalog_data=catalog_data,
            usage_data=usage_data,
        )
        latencies.append((_time.perf_counter() - t0) * 1000)
        names = [s.name.lower() for s in rr.selected]
        if not accept:
            hit1 = hit3 = names == []
            empty_correct += hit1
        else:
            hit1 = bool(names) and names[0] in accept
            hit3 = any(n in accept for n in names[:3])
        p1 += hit1
        p3 += hit3
        rows.append(
            {
                "q": query,
                "accept": accept,
                "got": names[:3],
                "decision": rr.decision,
                "p1": bool(hit1),
                "p3": bool(hit3),
            }
        )
    n = max(1, len(cases))
    lat_sorted = sorted(latencies)
    return {
        "eval_path": str(path),
        "cases": len(cases),
        "precision_at_1": round(p1 / n, 4),
        "precision_at_3": round(p3 / n, 4),
        "hits_p1": p1,
        "hits_p3": p3,
        "latency_ms": {
            "median": round(lat_sorted[len(lat_sorted) // 2], 1),
            "max": round(max(latencies), 1),
        },
        "weights": tuned_weights(),
        "rows": rows,
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


def skill_alias_report(catalog_data: Catalog) -> list[dict[str, object]]:
    """Return the compatibility map without reading any skill body."""
    names = {skill.name.lower() for skill in catalog_data.skills}
    return [
        {
            "alias": alias,
            "canonical": canonical_skill_name(alias),
            "alias_present": alias in names,
            "canonical_present": canonical_skill_name(alias) in names,
        }
        for alias in sorted(SKILL_ALIASES)
    ]


def catalog_summary(catalog_data: Catalog) -> dict[str, object]:
    return {
        "status": catalog_data.source,
        "skills": len(catalog_data.skills),
        "roots": [str(root) for root in catalog_data.roots],
        "index_path": str(catalog_data.index_path),
        "tsv_path": str(skill_index_tsv_file(catalog_data.index_path)),
        "ttl_seconds": skill_index_ttl_seconds(),
    }


def catalog_skill_paths(
    *, all_copies: bool = False, refresh_index: bool = False
) -> tuple[list[Path], Catalog]:
    catalog_data = load_catalog(refresh=refresh_index)
    if all_copies:
        paths = [Path(skill.path) for skill in scan_all_copies(catalog_data.roots)]
    else:
        paths = [Path(skill.path) for skill in catalog_data.skills]
    return paths, catalog_data


def skill_smoke_report(catalog_data: Catalog) -> dict[str, object]:
    failures: list[dict[str, str]] = []
    resolved_count = 0
    invoked_count = 0
    alias_redirects = 0
    empty_usage = UsageData(signals={})
    names = {skill.name.lower() for skill in catalog_data.skills}
    for skill in catalog_data.skills:
        resolved = resolve_skill(skill.name, catalog_data.skills)
        if resolved is None or resolved.path != skill.path:
            failures.append(
                {
                    "name": skill.name,
                    "stage": "resolve",
                    "message": "exact name did not resolve to its indexed path",
                }
            )
            continue
        resolved_count += 1
        if not Path(skill.path).is_file():
            failures.append(
                {
                    "name": skill.name,
                    "stage": "read",
                    "message": f"indexed path is missing: {skill.path}",
                }
            )
            continue
        if not skill.description.strip():
            failures.append(
                {
                    "name": skill.name,
                    "stage": "metadata",
                    "message": "indexed description is empty",
                }
            )
            continue
        result = route(
            skill.name,
            catalog_data=catalog_data,
            usage_data=empty_usage,
        )
        expected = canonical_skill_name(skill.name)
        selected_names = [item.name.lower() for item in result.selected]
        acceptable = skill.name.lower()
        if expected in names and expected != acceptable:
            acceptable = expected
            alias_redirects += 1
        if selected_names != [acceptable]:
            failures.append(
                {
                    "name": skill.name,
                    "stage": "invoke",
                    "message": f"expected {[acceptable]}, got {selected_names}",
                }
            )
            continue
        invoked_count += 1
    total = len(catalog_data.skills)
    return {
        "ok": not failures,
        "framework": QUALITY_FRAMEWORK_VERSION,
        "catalog": catalog_summary(catalog_data),
        "total": total,
        "resolved": resolved_count,
        "invoked": invoked_count,
        "alias_redirects": alias_redirects,
        "failures": failures,
    }


def explain_route(
    intent: str,
    *,
    strict: bool = True,
    limit: int = 5,
    refresh_index: bool = False,
) -> dict[str, object]:
    catalog_data = load_catalog(refresh=refresh_index)
    usage_data = load_usage_data()
    favorites = load_favorites()
    result = route(
        intent,
        strict=strict,
        catalog_data=catalog_data,
        usage_data=usage_data,
    )
    candidates = []
    intent_words = words(intent)
    for total, base, adaptive, skill in rank_candidates(
        intent, catalog_data.skills, favorites, usage_data
    )[: max(1, min(limit, 20))]:
        skill_words = (
            words(skill.name.replace("-", " "))
            | words(skill.description)
            | words(skill.keywords)
        )
        candidates.append(
            {
                "name": skill.name,
                "total_score": total,
                "base_score": base,
                "adaptive_adjustment": adaptive,
                "matched_tokens": sorted(intent_words & skill_words),
                "path": skill.path,
            }
        )
    tool_candidates = [
        asdict(candidate)
        for candidate in rank_tools(intent, usage_data)[: max(1, min(limit, 20))]
    ]
    return {
        "route": asdict(result),
        "candidates": candidates,
        "tool_candidates": tool_candidates,
    }


def tool_usage_report(
    usage_data: UsageData, *, include_rows: bool = False
) -> dict[str, object]:
    rows = []
    for spec, path in tool_specs(include_unavailable=True):
        signal = usage_data.tool_signals.get(spec.name, ToolSignal())
        rows.append(
            {
                "name": spec.name,
                "aliases": list(spec.aliases),
                "available": bool(path),
                "path": path,
                "routed": signal.routed,
                "used": signal.used,
                "success": signal.success,
                "failure": signal.failure,
                "success_rate_pct": round(
                    signal.success / (signal.success + signal.failure) * 100, 2
                )
                if signal.success + signal.failure
                else None,
                "average_latency_ms": round(signal.total_latency_ms / signal.used)
                if signal.used
                else 0,
                "adaptive_adjustment": tool_learned_adjustment(signal),
                "last_activity": signal.last_activity,
            }
        )
    summary: dict[str, object] = {
        "tools": len(rows),
        "tools_available": sum(bool(row["available"]) for row in rows),
        "tools_used": sum(int(row["used"]) > 0 for row in rows),
        "total_uses": sum(int(row["used"]) for row in rows),
        "total_success": sum(int(row["success"]) for row in rows),
        "total_failure": sum(int(row["failure"]) for row in rows),
        "tool_events": usage_data.tool_events,
        "raw_commands_stored": False,
        "raw_arguments_stored": False,
        "learning_observation": learning_observation(usage_data),
        "top_used": sorted(
            (row for row in rows if int(row["used"])),
            key=lambda row: (-int(row["used"]), str(row["name"])),
        )[:20],
    }
    if include_rows:
        summary["rows"] = rows
    return summary


def render_tool_usage_tsv(rows: list[dict[str, object]]) -> str:
    fields = (
        "name",
        "aliases",
        "available",
        "path",
        "routed",
        "used",
        "success",
        "failure",
        "success_rate_pct",
        "average_latency_ms",
        "adaptive_adjustment",
        "last_activity",
    )
    lines = ["\t".join(fields)]
    for row in rows:
        values = dict(row)
        values["aliases"] = ",".join(str(value) for value in row.get("aliases", []))
        lines.append(
            "\t".join(
                str(values.get(field, "")).replace("\t", " ").replace("\n", " ")
                for field in fields
            )
        )
    return "\n".join(lines) + "\n"


def usage_report(
    catalog_data: Catalog, usage_data: UsageData, *, include_rows: bool = False
) -> dict[str, object]:
    rows = []
    catalog_names = {skill.name.lower() for skill in catalog_data.skills}
    for skill in sorted(catalog_data.skills, key=lambda item: item.name.lower()):
        signal = usage_data.signals.get(skill.name.lower(), UsageSignal())
        rows.append(
            {
                "name": skill.name,
                "canonical_name": canonical_skill_name(skill.name),
                "routed": signal.routed,
                "applied": signal.applied,
                "views": signal.views,
                "patches": signal.patches,
                "success": signal.success,
                "failure": signal.failure,
                "legacy_suggested": signal.legacy_suggested,
                "adaptive_adjustment": learned_adjustment(signal),
                "last_activity": signal.last_activity,
                "path": skill.path,
            }
        )
    canonical_records: dict[str, dict[str, object]] = {}
    for observed_name, signal in usage_data.signals.items():
        canonical = canonical_skill_name(observed_name)
        record = canonical_records.setdefault(
            canonical,
            {
                "name": canonical,
                "aliases": set(),
                "routed": 0,
                "applied": 0,
                "views": 0,
                "patches": 0,
                "success": 0,
                "failure": 0,
                "legacy_suggested": 0,
                "last_activity": "",
            },
        )
        if observed_name != canonical:
            record["aliases"].add(observed_name)
        for field_name in (
            "routed",
            "applied",
            "views",
            "patches",
            "success",
            "failure",
            "legacy_suggested",
        ):
            record[field_name] = int(record[field_name]) + int(
                getattr(signal, field_name)
            )
        record["last_activity"] = max(
            str(record["last_activity"]), signal.last_activity
        )
    canonical_rows = []
    for record in canonical_records.values():
        record["aliases"] = sorted(record["aliases"])
        aggregate_signal = UsageSignal(
            applied=int(record["applied"]),
            success=int(record["success"]),
            failure=int(record["failure"]),
        )
        record["adaptive_adjustment"] = learned_adjustment(aggregate_signal)
        canonical_rows.append(record)
    canonical_rows.sort(key=lambda row: str(row["name"]))
    used = [row for row in rows if int(row["applied"]) > 0]
    routed = [row for row in rows if int(row["routed"]) > 0]
    summary: dict[str, object] = {
        "skills": len(rows),
        "skills_applied": len(used),
        "skills_routed": len(routed),
        "total_applied": sum(int(row["applied"]) for row in canonical_rows),
        "total_routes": usage_data.route_events,
        "total_feedback": sum(
            int(row["success"]) + int(row["failure"]) for row in canonical_rows
        ),
        "feedback_events": usage_data.feedback_events,
        "malformed_events": usage_data.malformed,
        "unknown_observed_skills": sorted(
            name
            for name in usage_data.signals
            if name not in catalog_names
            and name not in SKILL_ALIASES
            and canonical_skill_name(name) not in catalog_names
        ),
        "telemetry_path": str(route_events_file()),
        "learning_path": str(feedback_state_file()),
        "raw_prompts_stored": False,
        "learning_observation": learning_observation(usage_data),
        "top_applied": sorted(
            used, key=lambda row: (-int(row["applied"]), str(row["name"]))
        )[:20],
        "top_routed": sorted(
            routed, key=lambda row: (-int(row["routed"]), str(row["name"]))
        )[:20],
        "canonical_usage": canonical_rows,
        "top_canonical_applied": sorted(
            (row for row in canonical_rows if int(row["applied"])),
            key=lambda row: (-int(row["applied"]), str(row["name"])),
        )[:20],
    }
    if include_rows:
        summary["rows"] = rows
    return summary


def render_usage_tsv(rows: list[dict[str, object]]) -> str:
    fields = (
        "name",
        "canonical_name",
        "routed",
        "applied",
        "views",
        "patches",
        "success",
        "failure",
        "legacy_suggested",
        "adaptive_adjustment",
        "last_activity",
        "path",
    )
    lines = ["\t".join(fields)]
    for row in rows:
        lines.append(
            "\t".join(
                str(row.get(field, "")).replace("\t", " ").replace("\n", " ")
                for field in fields
            )
        )
    return "\n".join(lines) + "\n"


def doctor_report(refresh_index: bool = False) -> dict[str, object]:
    catalog_data = load_catalog(refresh=refresh_index)
    usage_data = load_usage_data(include_routes=True)
    report = usage_report(catalog_data, usage_data)
    tools = tool_usage_report(usage_data)
    drift = skill_drift_report(catalog_data.roots)
    quality_report = validation_report(
        Path(skill.path) for skill in catalog_data.skills
    )
    quality = {
        key: quality_report[key]
        for key in ("ok", "framework", "files", "errors", "warnings", "issue_counts")
    }
    return {
        "ok": usage_data.malformed == 0 and quality_report["ok"],
        "catalog": catalog_summary(catalog_data),
        "quality": quality,
        "telemetry_enabled": telemetry_enabled(),
        "learning_enabled": learning_enabled(),
        "raw_prompts_stored": False,
        "raw_commands_stored": False,
        "route_events": report["total_routes"],
        "applied_events": report["total_applied"],
        "feedback_events": report["total_feedback"],
        "usage_coverage_pct": round(
            (int(report["skills_applied"]) / int(report["skills"]) * 100), 2
        )
        if report["skills"]
        else 0.0,
        "malformed_events": usage_data.malformed,
        "missing_descriptions": [
            skill.name for skill in catalog_data.skills if not skill.description.strip()
        ],
        "unknown_observed_skills": report["unknown_observed_skills"],
        "tools": tools["tools"],
        "tools_available": tools["tools_available"],
        "tools_used": tools["tools_used"],
        "tool_events": tools["tool_events"],
        "learning_observation": report["learning_observation"],
        "drift": drift,
        "hook_status": [
            {
                "target": target,
                "path": str(hook_config_path(target)),
                "installed": hook_has_observer(target),
            }
            for target in ("codex", "claude", "hermes")
        ],
        "auto_route_excluded": sorted(AUTO_ROUTE_EXCLUDED),
        "skill_aliases": skill_alias_report(catalog_data),
        "canonical_skills_used": sum(
            int(row["applied"]) > 0 for row in report["canonical_usage"]
        ),
        "telemetry_path": str(route_events_file()),
        "learning_path": str(feedback_state_file()),
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


def run_jury(*, strict: bool = False, refresh_index: bool = False) -> dict:
    """Run a jury of test intents and cross-check that expected control skills
    are reachable. Each case declares an intent, a max-selected budget, and a
    set of acceptable skills (any-of). The jury passes when at least one
    acceptable skill appears in the selected set.

    This is the automated cross-check the user asked for: a deterministic
    battery that flags regressions in control-skill routing (agent-loop,
    omnigoal, verification-loop, master-check, goalmaster) alongside domain
    sanity checks (python debug, telegram, transcribe).
    """
    cases = JURY_CASES
    results = []
    passed = 0
    for case in cases:
        rr = route(
            case["intent"],
            max_selected=selection_limit(case["max"]),
            strict=case.get("strict", strict),
            refresh_index=refresh_index,
        )
        got = [s.name for s in rr.selected]
        expected = case["expected"]
        ok = any(name in expected for name in got) if expected else bool(got)
        if ok:
            passed += 1
        results.append(
            {
                "intent": case["intent"],
                "max": case["max"],
                "strict": case.get("strict", strict),
                "expected": list(expected),
                "got": got,
                "decision": rr.decision,
                "top_score": rr.top_score,
                "passed": ok,
            }
        )
    return {
        "ok": passed == len(cases),
        "passed": passed,
        "total": len(cases),
        "cases": results,
    }


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
    p_bench.add_argument("intent", nargs="?", default="")
    p_bench.add_argument("--max", type=int, default=DEFAULT_MAX_SELECTED)
    p_bench.add_argument("--refresh-index", action="store_true")
    p_bench.add_argument(
        "--quality",
        action="store_true",
        help="run the labeled routing-quality benchmark instead of a token bench",
    )
    p_bench.add_argument(
        "--eval-file",
        default="",
        help="path to a labeled eval set JSON (default: ~/.local/state/agent-skill-router/eval-set.json)",
    )
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
    p_resolve.add_argument("--canonical", action="store_true")
    p_resolve.add_argument("--refresh-index", action="store_true")
    p_aliases = sub.add_parser("aliases")
    p_aliases.add_argument("--json", action="store_true")
    p_aliases.add_argument("--refresh-index", action="store_true")
    p_drift = sub.add_parser("drift")
    p_drift.add_argument("--all", action="store_true")
    p_drift.add_argument("--json", action="store_true")
    p_drift.add_argument("--output")
    p_explain = sub.add_parser("explain")
    p_explain.add_argument("intent")
    p_explain.add_argument("--limit", type=int, default=5)
    p_explain.add_argument("--no-strict", action="store_true")
    p_explain.add_argument("--refresh-index", action="store_true")
    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--all", action="store_true")
    p_stats.add_argument("--json", action="store_true")
    p_stats.add_argument("--output")
    p_stats.add_argument("--refresh-index", action="store_true")
    p_feedback = sub.add_parser("feedback")
    p_feedback.add_argument("name")
    p_feedback.add_argument("outcome", choices=["success", "failure"])
    p_feedback.add_argument("--route-id", default="")
    p_tools = sub.add_parser("tools")
    p_tools.add_argument("--all", action="store_true")
    p_tools.add_argument("--json", action="store_true")
    p_tools.add_argument("--output")
    p_tool_feedback = sub.add_parser("tool-feedback")
    p_tool_feedback.add_argument("name")
    p_tool_feedback.add_argument("outcome", choices=["success", "failure"])
    p_tool_feedback.add_argument("--latency-ms", type=int, default=0)
    p_inventory = sub.add_parser("inventory")
    p_inventory.add_argument("--output")
    p_inventory.add_argument("--refresh-index", action="store_true")
    sub.add_parser("observe")
    p_install_hooks = sub.add_parser("install-hooks")
    p_install_hooks.add_argument(
        "--target", default="all", choices=["all", "codex", "claude", "hermes"]
    )
    p_install_hooks.add_argument("--dry-run", action="store_true")
    sub.add_parser("hook-status")
    p_doctor = sub.add_parser("doctor")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.add_argument("--refresh-index", action="store_true")
    p_jury = sub.add_parser("jury")
    p_jury.add_argument("--strict", action="store_true")
    p_jury.add_argument("--json", action="store_true")
    p_jury.add_argument("--refresh-index", action="store_true")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--all-copies", action="store_true")
    p_validate.add_argument("--strict", action="store_true")
    p_validate.add_argument("--scripts", action="store_true")
    p_validate.add_argument("--json", action="store_true")
    p_validate.add_argument("--output")
    p_validate.add_argument("--refresh-index", action="store_true")
    p_repair = sub.add_parser("repair")
    p_repair.add_argument("--all-copies", action="store_true")
    p_repair.add_argument("--apply", action="store_true")
    p_repair.add_argument("--json", action="store_true")
    p_repair.add_argument("--output")
    p_repair.add_argument("--refresh-index", action="store_true")
    p_smoke = sub.add_parser("smoke")
    p_smoke.add_argument("--json", action="store_true")
    p_smoke.add_argument("--output")
    p_smoke.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    if args.cmd == "route":
        rr = route(
            args.intent,
            max_selected=selection_limit(args.max),
            strict=args.strict,
            refresh_index=args.refresh_index,
        )
        route_id = record_route(rr, strict=args.strict)
        if args.json:
            payload = asdict(rr)
            payload["route_id"] = route_id
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(rr.router_block)
        return 0
    if args.cmd == "bench":
        if args.quality:
            eval_path = Path(args.eval_file).expanduser() if args.eval_file else None
            print(
                json.dumps(
                    quality_bench(
                        eval_path,
                        max_selected=selection_limit(max(args.max, 3)),
                        refresh_index=args.refresh_index,
                    ),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if not args.intent:
            print("bench requires an intent (or --quality)", file=sys.stderr)
            return 2
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
    if args.cmd == "validate":
        paths, _catalog_data = catalog_skill_paths(
            all_copies=args.all_copies,
            refresh_index=args.refresh_index,
        )
        report = validation_report(
            paths,
            spec_strict=args.strict,
            check_scripts=args.scripts,
        )
        if args.json or args.output:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        else:
            rendered = (
                f"{'PASS' if report['ok'] else 'FAIL'}\t{report['files']} files\t"
                f"{report['errors']} errors\t{report['warnings']} warnings\n"
            )
            rendered += "\n".join(
                f"{count}\t{code}" for code, count in report["issue_counts"].items()
            )
            if report["issue_counts"]:
                rendered += "\n"
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0 if report["ok"] else 1
    if args.cmd == "repair":
        paths, _catalog_data = catalog_skill_paths(
            all_copies=args.all_copies,
            refresh_index=args.refresh_index,
        )
        report = repair_report(paths, apply=args.apply)
        if args.apply and report["changed"]:
            report["catalog_after"] = catalog_summary(load_catalog(refresh=True))
        if args.json or args.output:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        else:
            mode = "APPLIED" if args.apply else "DRY-RUN"
            rendered = f"{mode}\t{report['changed']} files\n"
            if report["backup_dir"]:
                rendered += f"backup\t{report['backup_dir']}\n"
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0
    if args.cmd == "smoke":
        report = skill_smoke_report(load_catalog(refresh=args.refresh_index))
        if args.json or args.output:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        else:
            rendered = (
                f"{'PASS' if report['ok'] else 'FAIL'}\t{report['total']} skills\t"
                f"{report['resolved']} resolved\t{report['invoked']} invoked\t"
                f"{len(report['failures'])} failures\n"
            )
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0 if report["ok"] else 1
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
        requested_name = (
            canonical_skill_name(args.name) if args.canonical else args.name
        )
        skill = resolve_skill(requested_name, catalog_data.skills)
        if skill is None:
            return 1
        if args.json:
            print(json.dumps(asdict(skill), indent=2, ensure_ascii=False))
        else:
            print(skill.path)
        return 0
    if args.cmd == "aliases":
        catalog_data = load_catalog(refresh=args.refresh_index)
        aliases = skill_alias_report(catalog_data)
        if args.json:
            print(json.dumps(aliases, indent=2, ensure_ascii=False))
        else:
            for item in aliases:
                print(
                    f"{item['alias']}\t{item['canonical']}\t"
                    f"alias={'yes' if item['alias_present'] else 'archived'}\t"
                    f"canonical={'yes' if item['canonical_present'] else 'missing'}"
                )
        return 0
    if args.cmd == "drift":
        report = skill_drift_report(include_rows=args.all)
        if args.json:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        else:
            lines = [
                f"{report['active_files']} active files\t"
                f"{report['unique_names']} names\t"
                f"{report['duplicate_groups']} duplicate groups\t"
                f"{report['divergent_groups']} divergent groups"
            ]
            if args.all:
                for row in report["rows"]:
                    lines.append(
                        f"{row['name']}\t{row['copies']} copies\t"
                        f"{row['variants']} variants\t"
                        f"{'divergent' if row['divergent'] else 'identical'}"
                    )
            rendered = "\n".join(lines) + "\n"
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0
    if args.cmd == "explain":
        print(
            json.dumps(
                explain_route(
                    args.intent,
                    strict=not args.no_strict,
                    limit=args.limit,
                    refresh_index=args.refresh_index,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "stats":
        catalog_data = load_catalog(refresh=args.refresh_index)
        report = usage_report(
            catalog_data, load_usage_data(include_routes=True), include_rows=args.all
        )
        if args.all and not args.json:
            rendered = render_usage_tsv(report["rows"])
        else:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0
    if args.cmd == "feedback":
        catalog_data = load_catalog()
        skill = resolve_skill(args.name, catalog_data.skills)
        if skill is None:
            return 1
        print(
            json.dumps(
                record_feedback(skill.name, args.outcome, args.route_id),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "tools":
        report = tool_usage_report(
            load_usage_data(include_routes=True), include_rows=args.all
        )
        if args.all and not args.json:
            rendered = render_tool_usage_tsv(report["rows"])
        else:
            rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0
    if args.cmd == "tool-feedback":
        try:
            event = record_tool_usage(
                args.name,
                args.outcome,
                args.latency_ms,
                event_name="tool_feedback",
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(event, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "inventory":
        catalog_data = load_catalog(refresh=args.refresh_index)
        usage_data = load_usage_data(include_routes=True)
        rendered = (
            json.dumps(
                {
                    "skills": usage_report(catalog_data, usage_data, include_rows=True),
                    "tools": tool_usage_report(usage_data, include_rows=True),
                    "aliases": skill_alias_report(catalog_data),
                    "drift": skill_drift_report(catalog_data.roots, include_rows=True),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        if args.output:
            atomic_write_text(Path(args.output).expanduser(), rendered)
            print(str(Path(args.output).expanduser()))
        else:
            print(rendered, end="")
        return 0
    if args.cmd == "observe":
        try:
            payload = json.load(sys.stdin)
        except (TypeError, ValueError):
            return 0
        if isinstance(payload, dict):
            observe_hook_payload(payload)
        return 0
    if args.cmd == "install-hooks":
        try:
            result = install_hooks(args.target, dry_run=args.dry_run)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "hook-status":
        status = [
            {
                "target": target,
                "path": str(hook_config_path(target)),
                "installed": hook_has_observer(target),
            }
            for target in ("codex", "claude", "hermes")
        ]
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0 if all(item["installed"] for item in status) else 1
    if args.cmd == "doctor":
        report = doctor_report(refresh_index=args.refresh_index)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(
                f"{'ok' if report['ok'] else 'warning'}\t"
                f"{report['catalog']['skills']} skills\t"
                f"{report['route_events']} routes\t"
                f"{report['applied_events']} applied\t"
                f"{report['feedback_events']} feedback"
            )
        return 0 if report["ok"] else 1
    if args.cmd == "jury":
        report = run_jury(strict=args.strict, refresh_index=args.refresh_index)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            lines = [
                f"jury: {report['passed']}/{report['total']} passed",
                f"verdict: {'PASS' if report['ok'] else 'FAIL'}",
            ]
            for case in report["cases"]:
                mark = "PASS" if case["passed"] else "FAIL"
                got = ",".join(case["got"]) or "-"
                exp = ",".join(case["expected"])
                lines.append(
                    f"  [{mark}] {case['intent']!r}\n"
                    f"      expected one of: {exp}\n"
                    f"      got top-{case['max']}: {got}  (decision={case['decision']}, top={case['top_score']})"
                )
            print("\n".join(lines))
        return 0 if report["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
