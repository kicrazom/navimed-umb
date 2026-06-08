#!/usr/bin/env python3
"""Paper #1 — F1 (cross-model throughput vs N) + F8 (knee location across tiers).

Reads the unified tidy table from build_canonical_dataset.py
(paper/figures/canonical_dataset.csv) and renders the two headline canonical
figures plus a knee table.

F1 — one throughput-vs-N line per model at its DEPLOYABLE canonical TP:
     70B → TP2 (TP1 infeasible >32 GiB/card); small/mid → TP1 (single-card primary).
     A second panel overlays the small/mid TP2 lines for the multi-card view.
F8 — knee location (argmax-N of median throughput) per model, grouped by tier;
     plus plateau flag (throughput within PLATEAU_FRAC of peak at the next N up).

SCRIPT public (§11.1); OUTPUT embargoed (§11.3) → paper/figures/ (local-only).

Usage:
    python benchmarks/scripts/analysis/plot_canonical.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
FIG = REPO / "paper" / "figures"
DATASET = FIG / "canonical_dataset.csv"
PLATEAU_FRAC = 0.95  # within 5% of peak ⇒ plateaued

TIER_ORDER = ["4.5B", "8B", "11B", "12B", "70B"]
FAMILY_COLOR = {"PLLuM": "#1f77b4", "Bielik": "#d62728"}


def load():
    if not DATASET.exists():
        sys.exit(f"missing {DATASET} — run build_canonical_dataset.py first")
    rows = list(csv.DictReader(open(DATASET)))
    for r in rows:
        r["TP"] = int(r["TP"])
        r["N"] = int(r["N"])
        r["median"] = float(r["tok_s_out_median"])
    return rows


def series(rows, tp):
    """{model: [(N, median), ...] sorted} for a given TP."""
    s = defaultdict(list)
    meta = {}
    for r in rows:
        if r["TP"] == tp:
            s[r["model"]].append((r["N"], r["median"]))
            meta[r["model"]] = (r["family"], r["tier"])
    return {m: sorted(v) for m, v in s.items()}, meta


def knee_of(pts):
    """argmax-N of median throughput; plateaued if next-N still ≥ frac*peak."""
    peak_n, peak_v = max(pts, key=lambda t: t[1])
    return peak_n, peak_v


def plot_f1(rows):
    small_tp1, meta1 = series(rows, 1)
    small_tp2, meta2 = series(rows, 2)
    big_tp2 = {m: v for m, v in small_tp2.items() if meta2[m][1] == "70B"}
    small1 = {m: v for m, v in small_tp1.items()}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), sharex=True)

    # Panel A: deployable canonical config — small/mid TP1 + 70B TP2
    def style(model, fam, tier):
        color = FAMILY_COLOR.get(fam, "#555")
        ls = "--" if tier == "70B" else "-"
        return color, ls

    for m, pts in sorted(
        small1.items(), key=lambda kv: TIER_ORDER.index(meta1[kv[0]][1])
    ):
        fam, tier = meta1[m]
        if tier == "70B":
            continue
        c, ls = style(m, fam, tier)
        xs, ys = zip(*pts)
        ax1.plot(xs, ys, ls, marker="o", ms=4, color=c, alpha=0.85, label=f"{m} (TP1)")
    for m, pts in big_tp2.items():
        fam, tier = meta2[m]
        c, ls = style(m, fam, tier)
        xs, ys = zip(*pts)
        ax1.plot(
            xs, ys, ls, marker="s", ms=4, color="#2ca02c", alpha=0.6, label=f"{m} (TP2)"
        )
    ax1.set_title("A · Deployable config: small/mid TP1, 70B TP2")

    # Panel B: small/mid TP2 (multi-card)
    for m, pts in sorted(
        small_tp2.items(), key=lambda kv: TIER_ORDER.index(meta2[kv[0]][1])
    ):
        fam, tier = meta2[m]
        if tier == "70B":
            continue
        c, _ = style(m, fam, tier)
        xs, ys = zip(*pts)
        ax2.plot(xs, ys, "-", marker="s", ms=4, color=c, alpha=0.85, label=f"{m} (TP2)")
    ax2.set_title("B · small/mid TP2 (multi-card)")

    for ax in (ax1, ax2):
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.set_xticks([10, 25, 50, 100, 200, 500, 1000])
        ax.set_xlabel("Concurrency N (requests)")
        ax.set_ylabel("Output throughput (tok/s, median of n=10)")
        ax.grid(True, which="both", ls=":", alpha=0.4)
        ax.legend(fontsize=6, ncol=2, loc="upper left")
    fig.suptitle(
        "F1 · Canonical §3.3 throughput scaling — 15 Polish LLMs " "(EMBARGOED §11.3)",
        fontweight="bold",
    )
    fig.tight_layout()
    out = FIG / "F1_canonical_throughput.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_f8(rows):
    # knee per (model, tp)
    knees = []
    for tp in (1, 2):
        s, meta = series(rows, tp)
        for m, pts in s.items():
            peak_n, peak_v = knee_of(pts)
            # plateau: is there an N>peak_n still within frac of peak?
            higher = [v for (n, v) in pts if n > peak_n]
            plateaued = (
                any(v >= PLATEAU_FRAC * peak_v for v in higher) if higher else False
            )
            knees.append(
                {
                    "model": m,
                    "family": meta[m][0],
                    "tier": meta[m][1],
                    "TP": tp,
                    "knee_N": peak_n,
                    "peak_tok_s": round(peak_v, 1),
                    "plateaued": plateaued,
                }
            )

    # write knee table
    kt = FIG / "knee_table.csv"
    with open(kt, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "family",
                "tier",
                "TP",
                "knee_N",
                "peak_tok_s",
                "plateaued",
            ],
        )
        w.writeheader()
        w.writerows(knees)

    # figure: knee_N per model, grouped by tier, marker by TP
    fig, ax = plt.subplots(figsize=(11, 5.5))
    order = sorted(
        knees, key=lambda k: (TIER_ORDER.index(k["tier"]), k["model"], k["TP"])
    )
    ylabels, yi = [], 0
    seen = {}
    for k in order:
        key = f"{k['model']} TP{k['TP']}"
        seen[key] = yi
        ylabels.append(key)
        color = FAMILY_COLOR.get(k["family"], "#555")
        mk = "o" if k["TP"] == 1 else "s"
        ax.scatter(
            k["knee_N"],
            yi,
            color=color,
            marker=mk,
            s=70,
            edgecolor="k" if k["plateaued"] else "none",
            zorder=3,
        )
        yi += 1
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=7)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.set_xticks([10, 25, 50, 100, 200, 500, 1000])
    ax.set_xlabel("Knee location — N at peak throughput (log)")
    ax.grid(True, axis="x", ls=":", alpha=0.4)
    ax.set_title(
        "F8 · Throughput-knee location across tiers (○ TP1, □ TP2; "
        "black edge = plateau beyond knee) — EMBARGOED §11.3",
        fontsize=10,
        fontweight="bold",
    )
    fig.tight_layout()
    out = FIG / "F8_knee.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out, kt, knees


def main():
    rows = load()
    f1 = plot_f1(rows)
    f8, kt, knees = plot_f8(rows)
    print(f"WROTE {f1}")
    print(f"WROTE {f8}")
    print(f"WROTE {kt}")
    # qualitative-only summary (knee N + plateau; NO throughput numbers)
    print(
        "\nKnee summary (N at peak; plateau=within 5% beyond knee) — shapes only:",
        file=sys.stderr,
    )
    for k in sorted(knees, key=lambda x: (x["tier"], x["model"], x["TP"])):
        print(
            f"  {k['model']:28} TP{k['TP']}  knee@N={k['knee_N']:<5} "
            f"plateau={'yes' if k['plateaued'] else 'no'}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
