#!/usr/bin/env python3
"""Paper #1 — unified canonical §3.3 dataset builder (cross-model, n=10).

Merges the two on-disk result formats into ONE tidy long-form table keyed by
(model, family, tier, TP, N), with the n=10 aggregate throughput statistics:

  Format A — small/mid : benchmarks/results/<dir>/phase2_sweep.csv
                         (pre-aggregated; one row per (TP,N) with *_median/min/max)
  Format B — 70B AWQ   : benchmarks/results/<dir>/scaling/rep*/results_table.csv
                         (raw per-run; aggregated here across reps per (TP,N))

Canonical ladder: N in {10,25,50,100,200,500,1000}, target n=10/cell.

The SCRIPT is PUBLIC (§11.1). The OUTPUT (real throughput numbers) is EMBARGOED
(§11.3, Polish models, paper-bound) → written under paper/figures/ which is the
local-only, never-pushed draft tree (figure-plan §7).

Output: paper/figures/canonical_dataset.csv  (+ stderr coverage summary)

Usage:
    python benchmarks/scripts/analysis/build_canonical_dataset.py
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "benchmarks" / "results"
OUT_DIR = REPO / "paper" / "figures"
CANON_N = [10, 25, 50, 100, 200, 500, 1000]

# (display model, result-dir, family, tier, quant, [canonical TPs])
# tier: big = 70B (TP2 only, scaling format); small = <=12B (TP1,2, phase2 format)
MODELS = [
    # 70B AWQ family (TP2 only) — scaling format
    (
        "PLLuM-70B-base-2412",
        "Llama-PLLuM-70B-base-2412-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-base-2508",
        "Llama-PLLuM-70B-base-2508-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-chat-2412",
        "Llama-PLLuM-70B-chat-2412-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-chat-2508",
        "Llama-PLLuM-70B-chat-2508-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-chat-2512",
        "Llama-PLLuM-70B-chat-2512-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-instruct-2412",
        "Llama-PLLuM-70B-instruct-2412-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-instruct-2508",
        "Llama-PLLuM-70B-instruct-2508-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    (
        "PLLuM-70B-instruct-2512",
        "Llama-PLLuM-70B-instruct-2512-awq",
        "PLLuM",
        "70B",
        "AWQ",
        [2],
    ),
    # small / mid — phase2 format
    ("Bielik-11B-v2.3", "bielik-11b-v23", "Bielik", "11B", "FP16", [1, 2]),
    ("Bielik-11B-v3.0", "bielik-11b-v30", "Bielik", "11B", "BF16", [1, 2]),
    ("Bielik-4.5B-v3.0", "bielik-4.5b-v30", "Bielik", "4.5B", "BF16", [1, 2]),
    (
        "Bielik-PL-11B-v3.0-Instr",
        "bielik-pl-11b-v30-instruct",
        "Bielik",
        "11B",
        "BF16",
        [1, 2],
    ),
    (
        "Bielik-11B-v3.0-Instr-AWQ",
        "bielik-11b-v30-instruct-awq",
        "Bielik",
        "11B",
        "AWQ",
        [1, 2],
    ),
    (
        "PLLuM-8B-chat-2512",
        "Llama-PLLuM-8B-chat-2512-awq",
        "PLLuM",
        "8B",
        "AWQ",
        [1, 2],
    ),
    ("PLLuM-12B-chat-2512", "PLLuM-12B-chat-2512-awq", "PLLuM", "12B", "AWQ", [1, 2]),
]


def _read_noncomment(path: Path):
    with open(path) as f:
        return [ln for ln in f if not ln.startswith("#")]


def load_phase2(model_dir: Path):
    """Format A. Return {(tp,N): {median,min,max,n_ok}} from phase2_sweep.csv."""
    p = model_dir / "phase2_sweep.csv"
    if not p.exists():
        return {}
    out = {}
    for r in csv.DictReader(_read_noncomment(p)):
        try:
            tp = int(r["TP"])
            n = int(r["N"])
            nok = int(r["n_runs_ok"])
            med = float(r["tok_s_out_median"])
        except (KeyError, ValueError, TypeError):
            continue
        lo = _f(r.get("tok_s_out_min"))
        hi = _f(r.get("tok_s_out_max"))
        out[(tp, n)] = {"median": med, "min": lo, "max": hi, "n_ok": nok}
    return out


def load_scaling(model_dir: Path):
    """Format B. Aggregate scaling/rep*/results_table.csv across reps per (tp,N)."""
    acc = {}  # (tp,n) -> [tok_s_out per ok rep]
    for rep in sorted(model_dir.glob("scaling/rep*")):
        tbl = rep / "results_table.csv"
        if not tbl.exists():
            continue
        for r in csv.DictReader(_read_noncomment(tbl)):
            try:
                tp = int(r["TP"])
                n = int(r["N"])
                ok = str(r.get("ok", "")).strip().lower() in ("true", "1", "ok")
                v = float(r["tok_s_out"])
            except (KeyError, ValueError, TypeError):
                continue
            if ok:
                acc.setdefault((tp, n), []).append(v)
    out = {}
    for k, vals in acc.items():
        if vals:
            out[k] = {
                "median": statistics.median(vals),
                "min": min(vals),
                "max": max(vals),
                "n_ok": len(vals),
            }
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    cover = []
    for disp, rdir, fam, tier, quant, tps in MODELS:
        d = RESULTS / rdir
        cells = load_phase2(d) or load_scaling(d)
        fmt = "phase2" if (d / "phase2_sweep.csv").exists() else "scaling"
        got = 0
        for tp in tps:
            for n in CANON_N:
                c = cells.get((tp, n))
                if c is None:
                    continue
                got += 1
                rows.append(
                    {
                        "model": disp,
                        "result_dir": rdir,
                        "family": fam,
                        "tier": tier,
                        "quant": quant,
                        "TP": tp,
                        "N": n,
                        "tok_s_out_median": round(c["median"], 3),
                        "tok_s_out_min": round(c["min"], 3)
                        if c["min"] is not None
                        else "",
                        "tok_s_out_max": round(c["max"], 3)
                        if c["max"] is not None
                        else "",
                        "n_ok": c["n_ok"],
                    }
                )
        cover.append((disp, fmt, got, len(tps) * len(CANON_N)))

    out_csv = OUT_DIR / "canonical_dataset.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "result_dir",
                "family",
                "tier",
                "quant",
                "TP",
                "N",
                "tok_s_out_median",
                "tok_s_out_min",
                "tok_s_out_max",
                "n_ok",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    # coverage summary to stderr (no throughput numbers → safe to show)
    print(
        f"WROTE {out_csv}  ({len(rows)} cells, {len(MODELS)} models)", file=sys.stderr
    )
    print(f"{'model':28} {'fmt':8} cells", file=sys.stderr)
    full = 0
    for disp, fmt, got, exp in cover:
        tag = "OK" if got == exp else "SHORT"
        if got == exp:
            full += 1
        print(f"  {disp:28} {fmt:8} {got}/{exp} {tag}", file=sys.stderr)
    print(f"\n{full}/{len(MODELS)} models fully populated", file=sys.stderr)


if __name__ == "__main__":
    main()
