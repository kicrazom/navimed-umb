#!/usr/bin/env python3
"""Scaling line plot of Phase 2 Tier-A (n=10) per-cell results, with min–max band.

Median of the metric vs concurrency N, connected per TP, with a shaded min–max
band over the ten reps. Preferred over a box-and-whisker when run-to-run variance
is very small (boxes collapse below marker size and individual reps overlap): the
line shows the scaling trend (knee / plateau), the thin band shows the spread
honestly. Each marker is the **median of n=10 reps** at that N (METHODOLOGY §7.5).

The SCRIPT is PUBLIC (§11.1); the rendered OUTPUT is EMBARGOED (§11.2; stricter
§11.3 for Polish models) and is written under the gitignored
``benchmarks/results/<model>/`` tree.

Usage:
    python plot_scaling_band.py <model_results_dir> [--metric tok_s_out]
        [--ylabel "..."] [--label "..."] [--out PNG]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

TP_COLORS = {1: "#1f77b4", 2: "#ff7f0e"}
TP_MARKERS = {1: "o", 2: "s"}


def load_rows(csv_path: Path) -> list[dict]:
    """Parse the raw sweep CSV, skipping the embargo comment header lines."""
    rows: list[dict] = []
    header: list[str] | None = None
    with open(csv_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cells = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None:
                header = cells
                continue
            if len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results_dir")
    ap.add_argument("--metric", default="tok_s_out")
    ap.add_argument("--ylabel", default="Output throughput  (tok·s⁻¹)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rdir = Path(args.results_dir)
    csv_path = rdir / "phase2_sweep_raw.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} missing", file=sys.stderr)
        return 1

    data: dict[tuple[int, int], list[float]] = defaultdict(list)
    tps: set[int] = set()
    for r in load_rows(csv_path):
        if r.get("ok") != "1":
            continue
        try:
            tp, n, val = int(r["TP"]), int(r["N"]), float(r[args.metric])
        except (KeyError, ValueError):
            continue
        data[(tp, n)].append(val)
        tps.add(tp)
    if not data:
        print(f"ERROR: no usable rows for metric '{args.metric}'", file=sys.stderr)
        return 1

    label = args.label or rdir.name
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for tp in sorted(tps):
        ns = sorted({n for (t, n) in data if t == tp})
        med = [statistics.median(data[(tp, n)]) for n in ns]
        lo = [min(data[(tp, n)]) for n in ns]
        hi = [max(data[(tp, n)]) for n in ns]
        col = TP_COLORS.get(tp, "#888888")
        ax.fill_between(ns, lo, hi, color=col, alpha=0.20, linewidth=0)
        ax.plot(
            ns,
            med,
            marker=TP_MARKERS.get(tp, "o"),
            markersize=7,
            color=col,
            linewidth=2,
            markeredgecolor="white",
            markeredgewidth=0.6,
            label=f"TP={tp}",
            zorder=3,
        )

    ax.set_xscale("log")
    all_ns = sorted({n for (_, n) in data})
    ax.set_xticks(all_ns)
    ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.minorticks_off()
    ax.set_xlabel("Concurrent prompts  N  (log scale)")
    ax.set_ylabel(args.ylabel)
    ax.set_title(f"Run-3  {label} — {args.metric} scaling  (Tier-A, n=10)")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend(loc="upper left", framealpha=0.9)
    ax.text(
        0.995,
        -0.12,
        "EMBARGOED §11.2/§11.3 — local-only.  Marker = median of n=10 reps at N;  "
        "band = min–max across the 10 reps.",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="#888888",
    )
    fig.tight_layout()
    out = Path(args.out) if args.out else rdir / f"scaling_{args.metric}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  wrote {out}  (cells={len(data)}, N={all_ns}, TP={sorted(tps)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
