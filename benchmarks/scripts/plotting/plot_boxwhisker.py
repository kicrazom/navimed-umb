#!/usr/bin/env python3
"""Box-and-whisker plots of Phase 2 Tier-A (n=10) per-cell results.

Reads ``benchmarks/results/<model>/phase2_sweep_raw.csv`` (per-rep rows) and, for
each concurrency level N, draws a box-and-whisker of the ten reps' values with
TP=1 and TP=2 dodged side-by-side and **every individual rep overlaid** (jittered).

Presentation follows METHODOLOGY §7.5: box = IQR (Q1-Q3), centre line = median,
whiskers = 1.5x IQR (Tukey), points beyond = outliers; individual observations are
shown because n=10 is too small to hide behind summary glyphs (Weissgerber et al.
2015, "show the data"). The median/IQR summary is used rather than mean +/- SD
because aggregate-throughput and latency distributions are right-skewed.

The SCRIPT is PUBLIC (engineering, §11.1). Its OUTPUT (rendered numbers) is
EMBARGOED (§11.2; stricter §11.3 for Polish models) and is written under the
gitignored ``benchmarks/results/<model>/`` tree.

Usage:
    python plot_boxwhisker.py <model_results_dir> [--metric tok_s_out]
        [--ylabel "..."] [--label "..."] [--out PNG]
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

TP_COLORS = {1: "#1f77b4", 2: "#ff7f0e"}


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
    ns: set[int] = set()
    tps: set[int] = set()
    for r in load_rows(csv_path):
        if r.get("ok") != "1":
            continue
        try:
            tp, n, val = int(r["TP"]), int(r["N"]), float(r[args.metric])
        except (KeyError, ValueError):
            continue
        data[(tp, n)].append(val)
        ns.add(n)
        tps.add(tp)
    if not data:
        print(f"ERROR: no usable rows for metric '{args.metric}'", file=sys.stderr)
        return 1

    ns_sorted = sorted(ns)
    tps_sorted = sorted(tps)
    offs = {tp: (-0.17 if tp == tps_sorted[0] else 0.17) for tp in tps_sorted}
    if len(tps_sorted) == 1:
        offs = {tps_sorted[0]: 0.0}
    label = args.label or rdir.name
    rnd = random.Random(0)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    for tp in tps_sorted:
        positions, series = [], []
        for i, n in enumerate(ns_sorted):
            vals = data.get((tp, n))
            if vals:
                positions.append(i + offs[tp])
                series.append(vals)
        bp = ax.boxplot(
            series,
            positions=positions,
            widths=0.30,
            whis=1.5,
            patch_artist=True,
            manage_ticks=False,
            medianprops=dict(color="black", linewidth=2),
            flierprops=dict(marker="o", markersize=3, alpha=0.5),
        )
        for box in bp["boxes"]:
            box.set(facecolor=TP_COLORS.get(tp, "#888888"), alpha=0.35)
        for pos, vals in zip(positions, series):
            xs = [pos + rnd.uniform(-0.06, 0.06) for _ in vals]
            ax.scatter(
                xs,
                vals,
                s=14,
                color=TP_COLORS.get(tp, "#888888"),
                edgecolor="white",
                linewidth=0.4,
                zorder=3,
                alpha=0.9,
            )

    ax.set_xticks(range(len(ns_sorted)))
    ax.set_xticklabels([str(n) for n in ns_sorted])
    ax.set_xlabel("Concurrent prompts  N")
    ax.set_ylabel(args.ylabel)
    ax.set_title(f"Run-3  {label} — {args.metric}  (Tier-A, n=10 reps/cell)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(
        handles=[
            Patch(facecolor=TP_COLORS.get(tp, "#888888"), alpha=0.35, label=f"TP={tp}")
            for tp in tps_sorted
        ],
        loc="upper left",
        framealpha=0.9,
    )
    ax.text(
        0.995,
        -0.12,
        "EMBARGOED §11.2/§11.3 — local-only.  Box: IQR;  line: median;  "
        "whiskers: 1.5×IQR (Tukey);  points: individual reps (n=10).",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="#888888",
    )
    fig.tight_layout()
    out = Path(args.out) if args.out else rdir / f"boxwhisker_{args.metric}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  wrote {out}  (cells={len(data)}, N={ns_sorted}, TP={tps_sorted})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
