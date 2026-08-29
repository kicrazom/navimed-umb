#!/usr/bin/env python3
"""Paper #1 — T1: Holm–Bonferroni FWER comparison table (METHODOLOGY §7.4 / §7.5).

For each pre-specified contrast (two configurations that share the canonical
N-ladder), compare the n=10 throughput distributions per N with a two-sided
Mann–Whitney U test (non-parametric; throughput is right-skewed, §7.5), then
control the family-wise error rate ACROSS THE N-LADDER with Holm–Bonferroni
(§7.4). Report an effect size beside every p: median ratio (B/A) and the
Hodges–Lehmann shift (median of pairwise B−A differences).

CONTRASTS — only methodologically clean ones (§8.9: cross-quant comparisons valid
only at fixed model identity):
  • TP1 vs TP2 at fixed model identity (the core tensor-parallel question), per
    small/mid model.
  • Version effects within the 70B family at fixed role/quant/TP (feeds F6 +
    Discussion): chat-2412/2508/2512 pairwise, instruct-2508 vs 2512, base 2412 vs 2508.

Raw per-rep sources:
  small/mid : benchmarks/results/<dir>/phase2_sweep_raw.csv (cols TP,N,rep,ok,tok_s_out)
  70B       : benchmarks/results/<dir>/scaling/rep*/results_table.csv (1 tok_s_out/rep)

SCRIPT public (§11.1); OUTPUT embargoed (§11.3) → paper/figures/ (local-only).
Output: paper/figures/T1_holm_bonferroni.csv  (+ stderr qualitative summary)

Usage:
    python benchmarks/scripts/analysis/stats_holm_bonferroni.py
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

from scipy.stats import mannwhitneyu

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "benchmarks" / "results"
FIG = REPO / "paper" / "figures"
# 2026-08-29: N=1 wlaczone do drabiny — jeden ciag pomiarowy, nie osobna kotwica.
# Decyzja LM. Dane N=1 leza poza phase2_sweep_raw.csv (scaling-n1/ i n1-anchor/),
# dlatego load_raw ma dla nich osobna sciezke ponizej.
CANON_N = [1, 10, 25, 50, 100, 200, 500, 1000]
ALPHA = 0.05


def _noncomment(path):
    with open(path) as f:
        return [ln for ln in f if not ln.startswith("#")]


def load_raw(result_dir: str):
    """Return {(tp,N): [tok_s_out per ok rep]} from whichever format exists."""
    d = RESULTS / result_dir
    out = {}
    raw = d / "phase2_sweep_raw.csv"
    if raw.exists():
        for r in csv.DictReader(_noncomment(raw)):
            try:
                if str(r.get("ok", "")).strip().lower() not in ("true", "1", "ok"):
                    continue
                tp = int(r["TP"])
                n = int(r["N"])
                v = float(r["tok_s_out"])
            except (KeyError, ValueError, TypeError):
                continue
            out.setdefault((tp, n), []).append(v)
        _load_n1(d, out)
        return out
    for rep in sorted(d.glob("scaling/rep*")):
        tbl = rep / "results_table.csv"
        if not tbl.exists():
            continue
        for r in csv.DictReader(_noncomment(tbl)):
            try:
                if str(r.get("ok", "")).strip().lower() not in ("true", "1", "ok"):
                    continue
                tp = int(r["TP"])
                n = int(r["N"])
                v = float(r["tok_s_out"])
            except (KeyError, ValueError, TypeError):
                continue
            out.setdefault((tp, n), []).append(v)
    _load_n1(d, out)
    return out


# Katalogi z pomiarami N=1 nie zawsze nazywaja sie tak samo jak katalogi drabiny.
N1_ALIAS = {
    "bielik-11b-v23": "bielik-11b",
    "Llama-PLLuM-8B-chat-2512-awq": "pllum-8b-awq",
    "PLLuM-12B-chat-2512-awq": "pllum-12b-awq",
}


def _load_n1(d, out):
    """Dociaga per-replikowe pomiary N=1, ktorych nie ma w phase2_sweep_raw.csv.

    Dwa formaty: 70B ma scaling-n1/rep*/results_table.csv, small/mid ma
    n1-anchor/<quant>-tp<N>-n1-r<NN>-bench.log z linia 'Output throughput:'.
    """
    import re as _re

    alias = N1_ALIAS.get(d.name)
    if alias and not (d / "n1-anchor").exists() and not (d / "scaling-n1").exists():
        alt = d.parent / alias
        if alt.exists():
            d = alt
    for rep_dir in sorted(d.glob("scaling-n1/rep*")):
        tbl = rep_dir / "results_table.csv"
        if not tbl.exists():
            continue
        for r in csv.DictReader(_noncomment(tbl)):
            try:
                if str(r.get("ok", "")).strip().lower() not in ("true", "1", "ok"):
                    continue
                if int(r["N"]) != 1:
                    continue
                out.setdefault((int(r["TP"]), 1), []).append(float(r["tok_s_out"]))
            except (KeyError, ValueError, TypeError):
                continue
    for lg in sorted(d.glob("n1-anchor/*-n1-r*-bench.log")):
        m = _re.search(r"-tp(\d)-n1-r\d+-", lg.name)
        if not m:
            continue
        try:
            txt = lg.read_text(errors="ignore")
        except OSError:
            continue
        v = _re.search(r"Output throughput:\s*([\d.]+)", txt)
        if v:
            out.setdefault((int(m.group(1)), 1), []).append(float(v.group(1)))


def hodges_lehmann(a, b):
    """Median of all pairwise (b - a) differences."""
    diffs = [bi - ai for bi in b for ai in a]
    return statistics.median(diffs) if diffs else float("nan")


def holm(pvals):
    """Holm–Bonferroni adjusted p-values for a family of raw p-values."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(running, 1.0)
    return adj


# contrast = (label, (dirA, tpA), (dirB, tpB))
SMALL = [
    ("Bielik-11B-v2.3", "bielik-11b-v23"),
    ("Bielik-11B-v3.0", "bielik-11b-v30"),
    ("Bielik-4.5B-v3.0", "bielik-4.5b-v30"),
    ("Bielik-PL-11B-v3.0-Instr", "bielik-pl-11b-v30-instruct"),
    ("Bielik-11B-v3.0-Instr-AWQ", "bielik-11b-v30-instruct-awq"),
    ("PLLuM-8B-chat-2512", "Llama-PLLuM-8B-chat-2512-awq"),
    ("PLLuM-12B-chat-2512", "PLLuM-12B-chat-2512-awq"),
]
CONTRASTS = []
for disp, d in SMALL:
    CONTRASTS.append((f"{disp}: TP1 vs TP2", (d, 1), (d, 2)))
# 70B version contrasts (TP2, fixed role/quant)
V = "Llama-PLLuM-70B"
CONTRASTS += [
    ("70B-chat: 2412 vs 2508", (f"{V}-chat-2412-awq", 2), (f"{V}-chat-2508-awq", 2)),
    ("70B-chat: 2508 vs 2512", (f"{V}-chat-2508-awq", 2), (f"{V}-chat-2512-awq", 2)),
    (
        "70B-instruct: 2508 vs 2512",
        (f"{V}-instruct-2508-awq", 2),
        (f"{V}-instruct-2512-awq", 2),
    ),
    ("70B-base: 2412 vs 2508", (f"{V}-base-2412-awq", 2), (f"{V}-base-2508-awq", 2)),
]


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    cache = {}

    def get(d):
        if d not in cache:
            cache[d] = load_raw(d)
        return cache[d]

    table = []
    summary = []
    for label, (dA, tpA), (dB, tpB) in CONTRASTS:
        rawA, rawB = get(dA), get(dB)
        per_n = []
        pvals = []
        for n in CANON_N:
            a = rawA.get((tpA, n), [])
            b = rawB.get((tpB, n), [])
            if len(a) < 3 or len(b) < 3:
                per_n.append((n, len(a), len(b), None, None, None, None, None))
                continue
            try:
                u, p = mannwhitneyu(a, b, alternative="two-sided")
            except ValueError:
                p = 1.0
            ratio = (
                statistics.median(b) / statistics.median(a)
                if statistics.median(a)
                else float("nan")
            )
            hl = hodges_lehmann(a, b)
            per_n.append(
                (
                    n,
                    len(a),
                    len(b),
                    statistics.median(a),
                    statistics.median(b),
                    ratio,
                    hl,
                    p,
                )
            )
            pvals.append(p)
        # Holm across the N-ladder (only the cells that had a test)
        idx = [i for i, row in enumerate(per_n) if row[7] is not None]
        adj = holm([per_n[i][7] for i in idx]) if idx else []
        adjmap = {idx[k]: adj[k] for k in range(len(idx))}
        nsig = 0
        for i, row in enumerate(per_n):
            n, na, nb, ma, mb, ratio, hl, p = row
            padj = adjmap.get(i)
            sig = padj is not None and padj < ALPHA
            if sig:
                nsig += 1
            table.append(
                {
                    "contrast": label,
                    "N": n,
                    "n_A": na,
                    "n_B": nb,
                    "median_A": round(ma, 2) if ma is not None else "",
                    "median_B": round(mb, 2) if mb is not None else "",
                    "ratio_B_over_A": round(ratio, 4) if ratio is not None else "",
                    "HL_shift": round(hl, 2) if hl is not None else "",
                    "p_raw": round(p, 6) if p is not None else "",
                    "p_holm": round(padj, 6) if padj is not None else "",
                    "sig_0.05": "yes" if sig else ("no" if padj is not None else "n/a"),
                }
            )
        ntot = len(idx)
        # direction by median ratio at the largest tested N
        direction = ""
        for row in reversed(per_n):
            if row[5] is not None:
                direction = "B>A" if row[5] > 1 else ("B<A" if row[5] < 1 else "B=A")
                break
        summary.append((label, nsig, ntot, direction))

    out = FIG / "T1_holm_bonferroni.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "contrast",
                "N",
                "n_A",
                "n_B",
                "median_A",
                "median_B",
                "ratio_B_over_A",
                "HL_shift",
                "p_raw",
                "p_holm",
                "sig_0.05",
            ],
        )
        w.writeheader()
        w.writerows(table)

    print(f"WROTE {out}  ({len(table)} rows, {len(CONTRASTS)} contrasts)")
    print(
        "\nQualitative summary (sig N-points / tested; direction at top N) — "
        "no throughput values:",
        file=sys.stderr,
    )
    for label, nsig, ntot, direction in summary:
        print(
            f"  {label:34} {nsig}/{ntot} N-points sig (Holm)  dir={direction}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
