#!/usr/bin/env python3.13
"""si-autotune — grid-race scoring weights against the labeled eval set.

Referenced by si's TUNED_DEFAULTS comment but previously missing. Candidate
weights are written to tuned-weights.json, scored via `si bench --quality`,
and only a strictly better winner is persisted; otherwise the previous state
is restored. Stdlib only.

Usage: si-autotune [--rounds N]   (default 40 random candidates around current)
"""
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

SI = os.environ.get("SI_BIN", "si")
STATE = Path.home() / ".local/state/agent-skill-router/tuned-weights.json"
# simplification: random neighborhood search, not full grid — eval set is
# small (28 cases); upgrade path = larger labeled set + coordinate descent.
SPANS = {
    "name_w": (4.0, 14.0),
    "desc_w": (1.0, 6.0),
    "kw_w": (3.0, 12.0),
    "coverage_w": (2.0, 8.0),
    "bigram_name": (6.0, 20.0),
    "bigram_desc": (2.0, 10.0),
    "desc_damp_start": (40.0, 90.0),
    "desc_damp_floor": (0.2, 0.6),
    "no_workflow_min_score": (10.0, 20.0),
    "no_workflow_min_margin": (2.0, 8.0),
}


def bench() -> tuple[float, float, float]:
    out = subprocess.run(
        [SI, "bench", "--quality"], capture_output=True, text=True, timeout=300
    )
    d = json.loads(out.stdout)
    return d["precision_at_1"], d["precision_at_3"], d["latency_ms"]["median"]


def score(p1: float, p3: float) -> float:
    return p1 + 0.5 * p3  # p1 dominates; p3 breaks ties


def main() -> int:
    rounds = 40
    if "--rounds" in sys.argv:
        rounds = int(sys.argv[sys.argv.index("--rounds") + 1])

    backup = STATE.with_suffix(".json.bak")
    had_state = STATE.exists()
    if had_state:
        shutil.copy(STATE, backup)
    base = json.loads(STATE.read_text())["weights"] if had_state else {}

    p1, p3, lat = bench()
    best, best_w = score(p1, p3), None
    print(f"baseline: p@1={p1:.4f} p@3={p3:.4f} lat={lat}ms score={best:.4f}")

    rng = random.Random(42)
    cur = dict(base)
    try:
        for i in range(rounds):
            cand = {}
            for k, (lo, hi) in SPANS.items():
                center = cur.get(k, (lo + hi) / 2)
                jitter = (hi - lo) * 0.25
                cand[k] = round(min(hi, max(lo, center + rng.uniform(-jitter, jitter))), 2)
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"weights": cand}))
            p1, p3, _ = bench()
            s = score(p1, p3)
            marker = ""
            if s > best:
                best, best_w = s, cand
                cur = cand  # hill-climb around the new winner
                marker = "  << new best"
            print(f"round {i+1:02d}: p@1={p1:.4f} p@3={p3:.4f} score={s:.4f}{marker}")
    finally:
        if best_w is not None:
            STATE.write_text(json.dumps({"weights": best_w}, indent=1))
            print(f"WINNER persisted (score {best:.4f}): {STATE}")
        elif had_state:
            shutil.copy(backup, STATE)
            print("no improvement — previous weights restored")
        else:
            STATE.unlink(missing_ok=True)
            print("no improvement — defaults keep applying")
    return 0


if __name__ == "__main__":
    sys.exit(main())
