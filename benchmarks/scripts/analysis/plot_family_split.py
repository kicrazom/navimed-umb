#!/usr/bin/env python3
"""Paper #1 — family-split panels: knee (throughput) + energy (J/token).

Renders the cross-model canonical §3.3 data FACETED BY MODEL FAMILY (one panel
per family: Bielik / PLLuM / Qwen) so the knee location and the energy-per-token
behaviour are legible without 16 overlapping lines on one axis.

Two figures, each a row of per-family panels:

  FA_family_knee.png    throughput (tok/s, median n=10) vs N, log-x, knee marker
                        at argmax-N per model. Shows where each family saturates.
  FB_family_energy.png  energy per output token (J/token, median n=10) vs N.
                        Falling curve = batching amortises fixed power over more
                        tokens; the floor is the family's serving-efficiency limit.

Energy unit is unified to JOULES per output token across both on-disk formats:
  phase2 raw : W_per_tok_Wh  (Wh/token)  -> J/token  = value * 3600
  70B scaling: w_per_tok     (J/token already)        -> J/token  = value

The SCRIPT is PUBLIC (§11.1). The OUTPUT (real throughput + power numbers) is
EMBARGOED (§11.3) -> paper/figures/family-split/ (local-only, never pushed).

Usage:
    python benchmarks/scripts/analysis/plot_family_split.py
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "benchmarks" / "results"
OUT = REPO / "paper" / "figures" / "family-split"
CANON_N = [10, 25, 50, 100, 200, 500, 1000]
WH_TO_J = 3600.0


def _load_energy():
    """Authoritative J/token (Joules/token) from raw-thermals TOTAL power
    (aggregate_power_efficiency.py). Single source of truth for both figures —
    results_table w_per_tok is mean PER-GPU (= total/2, buggy) and phase2
    W_per_tok_Wh is Wh/token; neither is used here anymore."""
    p = REPO / "paper" / "figures" / "power_efficiency_dataset.csv"
    e = {}
    if p.exists():
        for r in csv.DictReader(open(p)):
            e[(r["result_dir"], r["TP"], int(r["N"]))] = float(r["J_per_tok_med"])
    return e


ENERGY = _load_energy()

# (display, result-dir, family, tier, primary canonical TP)
# 70B -> TP2 (single-card infeasible); small/mid -> TP1 (single-card primary view).
MODELS = [
    ("PLLuM-70B-base-2412", "Llama-PLLuM-70B-base-2412-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-base-2508", "Llama-PLLuM-70B-base-2508-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-chat-2412", "Llama-PLLuM-70B-chat-2412-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-chat-2508", "Llama-PLLuM-70B-chat-2508-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-chat-2512", "Llama-PLLuM-70B-chat-2512-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-instruct-2412", "Llama-PLLuM-70B-instruct-2412-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-instruct-2508", "Llama-PLLuM-70B-instruct-2508-awq", "PLLuM", "70B", 2),
    ("PLLuM-70B-instruct-2512", "Llama-PLLuM-70B-instruct-2512-awq", "PLLuM", "70B", 2),
    ("PLLuM-8B-chat-2512", "Llama-PLLuM-8B-chat-2512-awq", "PLLuM", "8B", 1),
    ("PLLuM-12B-chat-2512", "PLLuM-12B-chat-2512-awq", "PLLuM", "12B", 1),
    ("Bielik-11B-v2.3", "bielik-11b-v23", "Bielik", "11B", 1),
    ("Bielik-11B-v3.0", "bielik-11b-v30", "Bielik", "11B", 1),
    ("Bielik-4.5B-v3.0", "bielik-4.5b-v30", "Bielik", "4.5B", 1),
    ("Bielik-PL-11B-v3.0-Instr", "bielik-pl-11b-v30-instruct", "Bielik", "11B", 1),
    ("Bielik-11B-v3.0-Instr-AWQ", "bielik-11b-v30-instruct-awq", "Bielik", "11B", 1),
    ("Qwen3.5-9B", "qwen3.5-9b", "Qwen", "9B", 1),
]
FAMILY_ORDER = ["Bielik", "PLLuM", "Qwen"]


def _rows(path: Path):
    with open(path) as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith("#")))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cells_phase2(d: Path, tp_want: int):
    """phase2_sweep_raw.csv -> {N: (tok_s_median, J_per_tok_median)} at tp_want."""
    p = d / "phase2_sweep_raw.csv"
    if not p.exists():
        return {}
    tput = defaultdict(list)
    for r in _rows(p):
        if int(r["TP"]) != tp_want or str(r.get("ok", "")).strip() not in ("1", "True"):
            continue
        tput[int(r["N"])].append(_f(r.get("tok_s_out")))
    return {n: (_med(tput[n]), ENERGY.get((d.name, str(tp_want), n))) for n in tput}


def cells_scaling(d: Path, tp_want: int):
    """scaling/rep*/results_table.csv -> {N: (tok_s_median, J_per_tok_median)}."""
    tput = defaultdict(list)
    for rep in sorted(d.glob("scaling/rep*")):
        tbl = rep / "results_table.csv"
        if not tbl.exists():
            continue
        for r in _rows(tbl):
            if int(r["TP"]) != tp_want:
                continue
            if str(r.get("ok", "")).strip().lower() not in ("true", "1", "ok"):
                continue
            tput[int(r["N"])].append(_f(r.get("tok_s_out")))
    return {n: (_med(tput[n]), ENERGY.get((d.name, str(tp_want), n))) for n in tput}


def collect():
    """[(disp, family, tier, {N:(tput,J)})...] restricted to the canonical ladder."""
    out = []
    for disp, rdir, fam, tier, tp in MODELS:
        d = RESULTS / rdir
        cells = cells_phase2(d, tp) or cells_scaling(d, tp)
        cells = {n: v for n, v in cells.items() if n in CANON_N and v[0] is not None}
        if cells:
            out.append((disp, fam, tier, cells))
        else:
            print(f"  WARN no data: {disp} (tp{tp})", file=sys.stderr)
    return out


def _xaxis(ax):
    ax.set_xscale("log")
    ax.set_xticks(CANON_N)
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.set_xlabel("Concurrency N (prompts in flight)")
    ax.grid(True, which="both", alpha=0.25)


def panel(metric_idx, ylabel, title, fname, mark_knee, logy):
    data = collect()
    fams = [f for f in FAMILY_ORDER if any(d[1] == f for d in data)]
    fig, axes = plt.subplots(
        1, len(fams), figsize=(5.2 * len(fams), 4.6), squeeze=False
    )
    cmap = plt.get_cmap("tab10")
    for col, fam in enumerate(fams):
        ax = axes[0][col]
        members = [d for d in data if d[1] == fam]
        for i, (disp, _f0, tier, cells) in enumerate(
            sorted(members, key=lambda d: d[0])
        ):
            ns = sorted(cells)
            ys = [cells[n][metric_idx] for n in ns]
            ax.plot(
                ns,
                ys,
                marker="o",
                ms=3.5,
                lw=1.4,
                color=cmap(i % 10),
                label=disp.replace(f"{fam}-", "").replace("Llama-", ""),
            )
            if mark_knee:
                tputs = [cells[n][0] for n in ns]
                kn = ns[max(range(len(ns)), key=lambda j: tputs[j])]
                ax.axvline(kn, color=cmap(i % 10), ls=":", lw=0.8, alpha=0.5)
        _xaxis(ax)
        if logy:
            ax.set_yscale("log")
        if col == 0:
            ax.set_ylabel(ylabel)
        ax.set_title(f"{fam}  (n={len(members)})")
        ax.legend(fontsize=7, framealpha=0.9, loc="best")
    fig.suptitle(title, fontsize=13, y=1.02)
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / fname
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"WROTE {p}", file=sys.stderr)


def dump_csv():
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "family_split_dataset.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["model", "family", "tier", "N", "tok_s_out_median", "J_per_tok_median"]
        )
        for disp, fam, tier, cells in collect():
            for n in sorted(cells):
                tput, j = cells[n]
                w.writerow(
                    [
                        disp,
                        fam,
                        tier,
                        n,
                        round(tput, 3) if tput else "",
                        round(j, 4) if j else "",
                    ]
                )
    print(f"WROTE {p}", file=sys.stderr)


def main():
    panel(
        0,
        "Output throughput (tok/s, median n=10)",
        "Throughput vs concurrency — knee location per model family (dotted = per-model knee)",
        "FA_family_knee.png",
        mark_knee=True,
        logy=False,
    )
    panel(
        1,
        "Energy per output token (J/token, median n=10)",
        "Energy efficiency vs concurrency — J per output token per model family",
        "FB_family_energy.png",
        mark_knee=False,
        logy=True,
    )
    dump_csv()


if __name__ == "__main__":
    main()
