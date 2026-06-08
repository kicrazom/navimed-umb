#!/usr/bin/env python3
"""Paper #1 — F6: throughput decomposition, PLLuM-70B chat-2508 vs chat-2512 (§5.1).

Two panels (70B, TP2, AWQ — fixed identity except checkpoint version):
  A · throughput vs N, both versions overlaid (median of n=10 + min–max band).
  B · per-N ratio 2512/2508 with the 1.0 reference line; markers filled where the
      Holm-corrected Mann–Whitney test (T1) flags the N-point as significant.

Pairs with stats_holm_bonferroni.py (contrast "70B-chat: 2508 vs 2512").
SCRIPT public (§11.1); OUTPUT embargoed (§11.3) → paper/figures/ (local-only).

Usage:
    python benchmarks/scripts/analysis/plot_decomposition.py
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "benchmarks" / "results"
FIG = REPO / "paper" / "figures"
CANON_N = [10, 25, 50, 100, 200, 500, 1000]

A_DIR = "Llama-PLLuM-70B-chat-2508-awq"  # baseline
B_DIR = "Llama-PLLuM-70B-chat-2512-awq"  # newer
TP = 2


def load_raw(result_dir):
    d = RESULTS / result_dir
    out = defaultdict(list)
    for rep in sorted(d.glob("scaling/rep*")):
        tbl = rep / "results_table.csv"
        if not tbl.exists():
            continue
        with open(tbl) as f:
            for r in csv.DictReader(ln for ln in f if not ln.startswith("#")):
                try:
                    if str(r.get("ok", "")).strip().lower() not in ("true", "1", "ok"):
                        continue
                    if int(r["TP"]) != TP:
                        continue
                    out[int(r["N"])].append(float(r["tok_s_out"]))
                except (KeyError, ValueError, TypeError):
                    continue
    return out


def sig_points():
    """N-points flagged significant for the 2508-vs-2512 contrast in T1."""
    t1 = FIG / "T1_holm_bonferroni.csv"
    sig = set()
    if t1.exists():
        for r in csv.DictReader(open(t1)):
            if r["contrast"] == "70B-chat: 2508 vs 2512" and r["sig_0.05"] == "yes":
                sig.add(int(r["N"]))
    return sig


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    A, B = load_raw(A_DIR), load_raw(B_DIR)
    sig = sig_points()
    ns = [n for n in CANON_N if A.get(n) and B.get(n)]
    a_med = [statistics.median(A[n]) for n in ns]
    a_lo = [min(A[n]) for n in ns]
    a_hi = [max(A[n]) for n in ns]
    b_med = [statistics.median(B[n]) for n in ns]
    b_lo = [min(B[n]) for n in ns]
    b_hi = [max(B[n]) for n in ns]
    ratio = [bm / am if am else float("nan") for am, bm in zip(a_med, b_med)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(ns, a_med, "-o", color="#1f77b4", label="chat-2508")
    ax1.fill_between(ns, a_lo, a_hi, color="#1f77b4", alpha=0.15)
    ax1.plot(ns, b_med, "-s", color="#d62728", label="chat-2512")
    ax1.fill_between(ns, b_lo, b_hi, color="#d62728", alpha=0.15)
    ax1.set_xscale("log")
    ax1.set_xticks(ns)
    ax1.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax1.set_xlabel("Concurrency N")
    ax1.set_ylabel("Output throughput (tok/s, median n=10)")
    ax1.set_title("A · PLLuM-70B chat 2508 vs 2512 (TP2)")
    ax1.grid(True, which="both", ls=":", alpha=0.4)
    ax1.legend()

    ax2.axhline(1.0, color="#888", ls="--", lw=1)
    for n, rv in zip(ns, ratio):
        filled = n in sig
        ax2.plot(
            [n],
            [rv],
            "o",
            ms=8,
            color="#2ca02c",
            markerfacecolor="#2ca02c" if filled else "white",
            markeredgecolor="#2ca02c",
        )
    ax2.plot(ns, ratio, "-", color="#2ca02c", alpha=0.5)
    ax2.set_xscale("log")
    ax2.set_xticks(ns)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_xlabel("Concurrency N")
    ax2.set_ylabel("Throughput ratio 2512 / 2508")
    ax2.set_title("B · per-N ratio (filled = Holm-sig, T1)")
    ax2.grid(True, which="both", ls=":", alpha=0.4)

    fig.suptitle(
        "F6 · Checkpoint-version throughput decomposition (EMBARGOED §11.3)",
        fontweight="bold",
    )
    fig.tight_layout()
    out = FIG / "F6_decomposition_chat2508_2512.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
