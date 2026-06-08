#!/usr/bin/env python3
"""Audit Paper #1 dataset completeness against the canonical §3.3 ladder.

Canonical cells: N in {10,25,50,100,200,500,1000}, n=10 reps/cell.
  - 70B AWQ family: TP=2 only (TP=1 infeasible, >32 GiB single card).
  - Small/mid (<=12B): TP in {1,2}.

Reads two raw formats, reports per-model per-(TP,N) ok-rep count and gaps.
Read-only; prints a table. EMBARGO: prints counts only, no throughput numbers.
"""

import csv
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "results"
CANON_N = [10, 25, 50, 100, 200, 500, 1000]
REPS_TARGET = 10

# Paper model set. tier -> expected TPs.
SMALL_TPS = [1, 2]
BIG_TPS = [2]

BIG_MODELS = [
    "Llama-PLLuM-70B-base-2412-awq",
    "Llama-PLLuM-70B-base-2508-awq",
    "Llama-PLLuM-70B-chat-2412-awq",
    "Llama-PLLuM-70B-chat-2508-awq",
    "Llama-PLLuM-70B-chat-2512-awq",
    "Llama-PLLuM-70B-instruct-2412-awq",
    "Llama-PLLuM-70B-instruct-2508-awq",
    "Llama-PLLuM-70B-instruct-2512-awq",
]
SMALL_MODELS = [
    "bielik-11b-v23",
    "bielik-11b-v30",
    "bielik-4.5b-v30",
    "bielik-pl-11b-v30-instruct",
    "bielik-11b-v30-instruct-awq",
    "Llama-PLLuM-8B-chat-2512-awq",
    "PLLuM-12B-chat-2512-awq",
]


def ok_counts_phase2(csv_path):
    """Format B: phase2_sweep.csv (pre-aggregated). Returns {(tp,N): n_ok}."""
    out = {}
    with open(csv_path) as f:
        rows = [r for r in f if not r.startswith("#")]
    rdr = csv.DictReader(rows)
    for r in rdr:
        try:
            tp = int(r["TP"])
            n = int(r["N"])
            nok = int(r["n_runs_ok"])
        except (KeyError, ValueError):
            continue
        out[(tp, n)] = out.get((tp, n), 0) + nok
    return out


def ok_counts_scaling(model_dir):
    """Format A: scaling/repNN/results_table.csv. Returns {(tp,N): n_ok}."""
    out = {}
    reps = sorted(model_dir.glob("scaling/rep*"))
    for rep in reps:
        tbl = rep / "results_table.csv"
        if not tbl.exists():
            continue
        with open(tbl) as f:
            rdr = csv.DictReader(r for r in f if not r.startswith("#"))
            for r in rdr:
                try:
                    tp = int(r["TP"])
                    n = int(r["N"])
                    ok = str(r.get("ok", "")).strip().lower() in ("true", "1", "ok")
                except (KeyError, ValueError):
                    continue
                if ok:
                    out[(tp, n)] = out.get((tp, n), 0) + 1
    return out


def audit(model, tps):
    d = RESULTS / model
    if not d.exists():
        return model, None, "DIR MISSING"
    p2 = d / "phase2_sweep.csv"
    if p2.exists():
        counts = ok_counts_phase2(p2)
        fmt = "phase2"
    elif (d / "scaling").exists():
        counts = ok_counts_scaling(d)
        fmt = "scaling"
    else:
        return model, None, "SUMMARY-only (n=1 exploratory, NO n=10)"
    gaps = []
    for tp in tps:
        for n in CANON_N:
            got = counts.get((tp, n), 0)
            if got < REPS_TARGET:
                gaps.append(f"TP{tp}/N{n}:{got}/{REPS_TARGET}")
    return model, fmt, gaps


def main():
    print(f"Canonical §3.3 ladder N={CANON_N}, target n={REPS_TARGET}/cell\n")
    all_ok = True
    for label, models, tps in [
        ("70B AWQ (TP=2)", BIG_MODELS, BIG_TPS),
        ("Small/mid (TP1,2)", SMALL_MODELS, SMALL_TPS),
    ]:
        print(f"=== {label} ===")
        for m in models:
            name, fmt, gaps = audit(m, tps)
            if gaps == []:
                print(f"  ✓ {m:40s} [{fmt}] COMPLETE")
            elif isinstance(gaps, str):
                print(f"  ⚠ {m:40s} {gaps}")
                all_ok = False
            else:
                all_ok = False
                ncells = len(tps) * len(CANON_N)
                print(
                    f"  ✗ {m:40s} [{fmt}] {len(gaps)}/{ncells} cells short: {', '.join(gaps[:8])}{' ...' if len(gaps) > 8 else ''}"
                )
        print()
    print("ALL COMPLETE" if all_ok else "GAPS PRESENT — see above")


if __name__ == "__main__":
    sys.exit(main())
