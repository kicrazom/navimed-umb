#!/usr/bin/env python3
"""§5.3 precision-ablation aggregation — same-checkpoint BF16 <-> AWQ comparison.

Pure CPU / file-parsing. Reads only already-computed bench + thermal telemetry
from the three ablation-pair sweeps (PLAN-2026-06-30, Faza 3). NO GPU / vLLM /
model loading. EMBARGO §11.2/§11.3 — outputs stay LOCAL (gitignored results tree),
no commit / push / deploy.

Pairs (result_dir + quant from the three run_ablation_* orchestrators):
  Bielik-4.5B : bf16 = bielik-4.5b-v30      | awq = bielik-4.5b-v30-awq
  PLLuM-8B    : bf16 = pllum-8b             | awq = pllum-8b-awq
  PLLuM-12B   : bf16 = pllum-12b            | awq = pllum-12b-awq

Per member, per (TP in {1,2}), per N in {1,10,25,50,100,200,500,1000} where the
raw reps exist:
  tok_s   = median over reps of "Output throughput: X tok/s" (from *-bench.log)
  power_w = median over reps of window-mean TOTAL discrete-GPU draw
            (sum power_w over gpus where is_igpu is False, within events start/end
             window). window_power copied verbatim from add_n1_energy_smallmid.py.
  tok_per_J = tok_s / power_w ; J_per_tok = power_w / tok_s

MATCHED-TP comparison. The same-checkpoint BF16<->AWQ ratio is taken at a FIXED
tensor-parallel degree (both precisions on the same #GPUs). Mixing parallelism
(e.g. BF16 at TP1 vs AWQ at TP2) is apples-to-oranges: the tiny 4.5B BF16 loses
heavily to TP2 comm overhead (3599 tok/s at TP1 -> 2593 at TP2) while AWQ prefers
TP2, which would inflate the "penalty". The headline §5.3 figure is TP=2 (the
2x R9700 deployment; also the AWQ-throughput-optimal TP for every pair here).
A TP=1 comparison is emitted alongside for completeness.

N=1 lives in a separate <dir>/n1-anchor/ for the pair sweeps (N=1 was a separate
anchor, not part of the {10..1000} ladder loop); bielik-4.5b-v30 (BF16) also has
it under thermal-runs. We prefer n1-anchor/ when present. N=1 ratio is only
computable where BOTH sides have the anchor.
"""

import csv
import glob
import json
import os
import re
import statistics as st

import numpy as np
from scipy.stats import mannwhitneyu

BASE = "/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb"  # pragma: allowlist secret
RES = f"{BASE}/benchmarks/results"
OUT_DIR = f"{RES}/_ablation_summary"
LADDER_WIDE = f"{BASE}/paper/figures/R/ladder_median_wide.csv"

N_LADDER = [1, 10, 25, 50, 100, 200, 500, 1000]
TPS = [1, 2]
HEADLINE_TP = 2  # 2x R9700 deployment / AWQ-optimal parallelism

# ---- statistical layer (P1'): reproducible bootstrap CI + Holm-Bonferroni ----
# Seed shared with paper/figures/plot_style.py (SEED) so the CI on the ablation
# TABLE and the CI on the ablation FIGURE come from the same RNG stream.
SEED = 20260715
N_BOOT = 10000  # bootstrap resamples for a CI of the median
CI_PCT = 95  # central 95 % percentile interval
ALPHA = 0.05  # family-wise significance after Holm correction


def boot_ci_median(vals, rng, n_boot=N_BOOT, ci=CI_PCT):
    """Percentile bootstrap 95 % CI of the MEDIAN. (None, None) if <2 finite."""
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    if a.size < 2:
        return (None, None)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    meds = np.median(a[idx], axis=1)
    return (
        round(float(np.percentile(meds, (100 - ci) / 2)), 4),
        round(float(np.percentile(meds, 100 - (100 - ci) / 2)), 4),
    )


def boot_ci_ratio(num_vals, den_vals, rng, n_boot=N_BOOT, ci=CI_PCT):
    """Percentile bootstrap 95 % CI of median(num)/median(den), arms resampled
    independently. (None, None) if either arm has <2 finite values."""
    a = np.asarray([v for v in num_vals if v is not None and np.isfinite(v)], float)
    b = np.asarray([v for v in den_vals if v is not None and np.isfinite(v)], float)
    if a.size < 2 or b.size < 2:
        return (None, None)
    ia = rng.integers(0, a.size, size=(n_boot, a.size))
    ib = rng.integers(0, b.size, size=(n_boot, b.size))
    r = np.median(a[ia], axis=1) / np.median(b[ib], axis=1)
    return (
        round(float(np.percentile(r, (100 - ci) / 2)), 4),
        round(float(np.percentile(r, 100 - (100 - ci) / 2)), 4),
    )


def mannwhitney_p(a_vals, b_vals):
    """Two-sided Mann-Whitney U p-value between two independent rep samples.
    None if either arm has <2 values or they are perfectly identical/degenerate."""
    a = [v for v in a_vals if v is not None and np.isfinite(v)]
    b = [v for v in b_vals if v is not None and np.isfinite(v)]
    if len(a) < 2 or len(b) < 2:
        return None
    try:
        return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except ValueError:
        return None


def holm_bonferroni(pvals):
    """Holm step-down adjusted p-values for a list of raw p-values (order
    preserved). Returns a list of adjusted p in the same order as input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [None] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# pair -> (label, bf16_dir, awq_dir)
PAIRS = [
    ("Bielik-4.5B", "bielik-4.5b-v30", "bielik-4.5b-v30-awq"),
    ("PLLuM-8B", "pllum-8b", "pllum-8b-awq"),
    ("PLLuM-12B", "pllum-12b", "pllum-12b-awq"),
]

TPUT_RE = re.compile(r"Output throughput:\s+([\d.]+)\s+tok/s")


def window_power(thermals, events):
    """Window-mean TOTAL discrete-GPU draw over the events start->end window.
    Copied verbatim from add_n1_energy_smallmid.py (same telemetry schema)."""
    try:
        ev = json.load(open(events))
        t0 = next((e["t"] for e in ev if "start" in e["label"].lower()), None)
        t1 = next((e["t"] for e in ev if "end" in e["label"].lower()), None)
    except Exception:
        t0 = t1 = None
    vals = []
    for line in open(thermals):
        try:
            s = json.loads(line)
        except Exception:
            continue
        if t0 is not None and t1 is not None and not (t0 <= s.get("t", -1) <= t1):
            continue
        p = sum(
            g["power_w"]
            for g in s.get("gpus", [])
            if not g.get("is_igpu") and g.get("power_w") is not None
        )
        if p > 0:
            vals.append(p)
    return st.mean(vals) if vals else None


def parse_tput(bench_log):
    """Last 'Output throughput' line in a bench log = the measured (non-warmup) run."""
    val = None
    try:
        for line in open(bench_log):
            m = TPUT_RE.search(line)
            if m:
                val = float(m.group(1))
    except Exception:
        return None
    return val


def cell_bench_logs(base_dir, quant, tp, n):
    """Rep bench logs for one (member, TP, N) cell. N=1 for the pair sweeps lives
    in n1-anchor/; prefer it when present."""
    if n == 1:
        anchor = sorted(
            glob.glob(f"{base_dir}/n1-anchor/{quant}-tp{tp}-n1-r*-bench.log")
        )
        if anchor:
            return anchor
    return sorted(
        glob.glob(f"{base_dir}/thermal-runs/{quant}-tp{tp}-n{n}-r*-bench.log")
    )


def cell_stats(pair_root, quant, tp, n):
    """Median tok/s and median window-power for one cell, PLUS the per-rep
    samples (paired per bench log) needed for bootstrap CI and Mann-Whitney.
    None if no reps.

    Per-rep energy (J/tok) is paired WITHIN a rep: J/tok_rep = W_rep / tok_s_rep,
    kept only for reps where both the throughput parse and the window-power
    succeeded — so the energy CI never mixes a rep's throughput with another
    rep's power."""
    logs = cell_bench_logs(pair_root, quant, tp, n)
    if not logs:
        return None
    tputs, powers, jtoks = [], [], []
    for bl in logs:
        t = parse_tput(bl)
        stem = bl[: -len("-bench.log")]
        th, ev = stem + "-thermals.jsonl", stem + "-events.json"
        pw = window_power(th, ev) if os.path.exists(th) else None
        if t and t > 0:
            tputs.append(t)
        if pw and pw > 0:
            powers.append(pw)
        if t and t > 0 and pw and pw > 0:
            jtoks.append(pw / t)
    if not tputs:
        return None
    tok_s = st.median(tputs)
    pw = st.median(powers) if powers else None
    # Punkt J/tok = mediana per-rep ilorazów (spójna z CI = boot_ci_median(jtok_reps));
    # ratio-of-medians (pw/tok_s) dawał punkt poza własnym CI (audyt 2026-07-16, WARNING-1).
    j_per_tok = st.median(jtoks) if jtoks else ((pw / tok_s) if pw else None)
    return {
        "tok_s": tok_s,
        "power_w": pw,
        "tok_per_J": (1.0 / j_per_tok) if j_per_tok else None,
        "J_per_tok": j_per_tok,
        "n_tput": len(tputs),
        "n_pow": len(powers),
        "tput_reps": tputs,
        "pow_reps": powers,
        "jtok_reps": jtoks,
    }


def load_ladder_check():
    """Ground-truth throughput cross-check from the published ladder."""
    out = {}
    if not os.path.exists(LADDER_WIDE):
        return out
    for r in csv.DictReader(open(LADDER_WIDE)):
        if r.get("model") == "model":
            continue
        for col, n in [
            ("N1", 1),
            ("N10", 10),
            ("N25", 25),
            ("N50", 50),
            ("N100", 100),
            ("N200", 200),
            ("N500", 500),
            ("N1000", 1000),
        ]:
            v = (r.get(col) or "").strip()
            if v and v.upper() != "NA":
                try:
                    out[(r["model"], r["quant"], str(r["TP"]), n)] = float(v)
                except ValueError:
                    pass
    return out


def rr(x, d):
    return round(x, d) if x is not None else ""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ladder = load_ladder_check()

    # 1) atomic per-cell grid (pair, precision, TP, N)
    grid = {}
    for label, bf16_dir, awq_dir in PAIRS:
        for precision, d in (("BF16", bf16_dir), ("AWQ", awq_dir)):
            root = f"{RES}/{d}"
            quant = "bf16" if precision == "BF16" else "awq"
            for tp in TPS:
                for n in N_LADDER:
                    s = cell_stats(root, quant, tp, n)
                    if s:
                        grid[(label, precision, tp, n)] = s

    # 2) MATCHED-TP long comparison table + statistical layer (P1')
    #    - bootstrap 95 % CI of each median (throughput, J/tok)
    #    - bootstrap 95 % CI of the BF16/AWQ throughput ratio and the AWQ/BF16
    #      energy ratio (arms resampled independently)
    #    - Mann-Whitney U (two-sided) BF16 vs AWQ per cell -> Holm-Bonferroni
    #      across the family of cells (throughput and energy as separate families)
    rng = np.random.default_rng(SEED)  # one stream, deterministic given call order
    table_rows = []
    for label, _, _ in PAIRS:
        for tp in TPS:
            for n in N_LADDER:
                b = grid.get((label, "BF16", tp, n))
                a = grid.get((label, "AWQ", tp, n))
                if not b and not a:
                    continue
                # CI of individual medians (from per-rep samples)
                b_tp_ci = boot_ci_median(b["tput_reps"], rng) if b else (None, None)
                a_tp_ci = boot_ci_median(a["tput_reps"], rng) if a else (None, None)
                b_je_ci = boot_ci_median(b["jtok_reps"], rng) if b else (None, None)
                a_je_ci = boot_ci_median(a["jtok_reps"], rng) if a else (None, None)
                # CI of the ratios (both arms present)
                tput_ratio_ci = (
                    boot_ci_ratio(b["tput_reps"], a["tput_reps"], rng)
                    if (b and a)
                    else (None, None)
                )
                energy_ratio_ci = (
                    boot_ci_ratio(a["jtok_reps"], b["jtok_reps"], rng)
                    if (b and a and a["jtok_reps"] and b["jtok_reps"])
                    else (None, None)
                )
                # raw Mann-Whitney p (Holm applied after the full family is built)
                p_tput = (
                    mannwhitney_p(b["tput_reps"], a["tput_reps"]) if (b and a) else None
                )
                p_energy = (
                    mannwhitney_p(b["jtok_reps"], a["jtok_reps"])
                    if (b and a and b["jtok_reps"] and a["jtok_reps"])
                    else None
                )
                row = {
                    "pair": label,
                    "TP": tp,
                    "N": n,
                    "bf16_tok_s": rr(b["tok_s"], 2) if b else "",
                    "bf16_tok_s_ci_lo": rr(b_tp_ci[0], 2),
                    "bf16_tok_s_ci_hi": rr(b_tp_ci[1], 2),
                    "awq_tok_s": rr(a["tok_s"], 2) if a else "",
                    "awq_tok_s_ci_lo": rr(a_tp_ci[0], 2),
                    "awq_tok_s_ci_hi": rr(a_tp_ci[1], 2),
                    "tput_ratio_bf16_over_awq": round(b["tok_s"] / a["tok_s"], 3)
                    if (b and a)
                    else "",
                    "tput_ratio_ci_lo": rr(tput_ratio_ci[0], 3),
                    "tput_ratio_ci_hi": rr(tput_ratio_ci[1], 3),
                    "bf16_power_w": rr(b["power_w"], 1) if b else "",
                    "awq_power_w": rr(a["power_w"], 1) if a else "",
                    "bf16_J_per_tok": rr(b["J_per_tok"], 4) if b else "",
                    "bf16_J_per_tok_ci_lo": rr(b_je_ci[0], 4),
                    "bf16_J_per_tok_ci_hi": rr(b_je_ci[1], 4),
                    "awq_J_per_tok": rr(a["J_per_tok"], 4) if a else "",
                    "awq_J_per_tok_ci_lo": rr(a_je_ci[0], 4),
                    "awq_J_per_tok_ci_hi": rr(a_je_ci[1], 4),
                    "energy_ratio_Jtok_awq_over_bf16": round(
                        a["J_per_tok"] / b["J_per_tok"], 3
                    )
                    if (b and a and b["J_per_tok"] and a["J_per_tok"])
                    else "",
                    "energy_ratio_ci_lo": rr(energy_ratio_ci[0], 3),
                    "energy_ratio_ci_hi": rr(energy_ratio_ci[1], 3),
                    "mw_p_tput_raw": p_tput,
                    "mw_p_energy_raw": p_energy,
                    "bf16_reps": b["n_tput"] if b else "",
                    "awq_reps": a["n_tput"] if a else "",
                }
                table_rows.append(row)

    # Holm-Bonferroni across the two comparison families (throughput, energy)
    for fam_key, holm_key, sig_key in [
        ("mw_p_tput_raw", "mw_p_tput_holm", "sig_tput_holm"),
        ("mw_p_energy_raw", "mw_p_energy_holm", "sig_energy_holm"),
    ]:
        idx = [i for i, r in enumerate(table_rows) if r[fam_key] is not None]
        adj = holm_bonferroni([table_rows[i][fam_key] for i in idx])
        for i in range(len(table_rows)):
            table_rows[i][holm_key] = ""
            table_rows[i][sig_key] = ""
        for j, i in enumerate(idx):
            table_rows[i][holm_key] = round(adj[j], 6)
            table_rows[i][sig_key] = "yes" if adj[j] < ALPHA else "no"
    # round the raw p last (kept numeric for Holm, now formatted for output)
    for r in table_rows:
        r["mw_p_tput_raw"] = (
            round(r["mw_p_tput_raw"], 6) if r["mw_p_tput_raw"] is not None else ""
        )
        r["mw_p_energy_raw"] = (
            round(r["mw_p_energy_raw"], 6) if r["mw_p_energy_raw"] is not None else ""
        )

    cols = [
        "pair",
        "TP",
        "N",
        "bf16_tok_s",
        "bf16_tok_s_ci_lo",
        "bf16_tok_s_ci_hi",
        "awq_tok_s",
        "awq_tok_s_ci_lo",
        "awq_tok_s_ci_hi",
        "tput_ratio_bf16_over_awq",
        "tput_ratio_ci_lo",
        "tput_ratio_ci_hi",
        "bf16_power_w",
        "awq_power_w",
        "bf16_J_per_tok",
        "bf16_J_per_tok_ci_lo",
        "bf16_J_per_tok_ci_hi",
        "awq_J_per_tok",
        "awq_J_per_tok_ci_lo",
        "awq_J_per_tok_ci_hi",
        "energy_ratio_Jtok_awq_over_bf16",
        "energy_ratio_ci_lo",
        "energy_ratio_ci_hi",
        "mw_p_tput_raw",
        "mw_p_tput_holm",
        "sig_tput_holm",
        "mw_p_energy_raw",
        "mw_p_energy_holm",
        "sig_energy_holm",
        "bf16_reps",
        "awq_reps",
    ]
    table_path = f"{OUT_DIR}/precision_ablation_table.csv"
    with open(table_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(table_rows)

    # 3) atomic per-cell grid CSV (provenance)
    grid_path = f"{OUT_DIR}/precision_ablation_cells.csv"
    with open(grid_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "pair",
                "precision",
                "TP",
                "N",
                "tok_s",
                "power_w",
                "tok_per_J",
                "J_per_tok",
                "reps_tput",
                "reps_pow",
            ]
        )
        for (label, precision, tp, n), s in sorted(grid.items()):
            w.writerow(
                [
                    label,
                    precision,
                    tp,
                    n,
                    rr(s["tok_s"], 2),
                    rr(s["power_w"], 1),
                    rr(s["tok_per_J"], 4),
                    rr(s["J_per_tok"], 4),
                    s["n_tput"],
                    s["n_pow"],
                ]
            )

    # helpers over the grid
    def peak_tput(label, precision, tp):
        c = [
            (n, grid[(label, precision, tp, n)]["tok_s"])
            for n in N_LADDER
            if (label, precision, tp, n) in grid
        ]
        return max(c, key=lambda x: x[1]) if c else None  # (N, tok_s)

    def peak_tput_cell(label, precision, tp):
        c = [
            (n, grid[(label, precision, tp, n)])
            for n in N_LADDER
            if (label, precision, tp, n) in grid
        ]
        return max(c, key=lambda x: x[1]["tok_s"]) if c else None

    def best_energy(label, precision, tp):
        c = [
            (n, grid[(label, precision, tp, n)]["J_per_tok"])
            for n in N_LADDER
            if (label, precision, tp, n) in grid
            and grid[(label, precision, tp, n)]["J_per_tok"] is not None
        ]
        return min(c, key=lambda x: x[1]) if c else None  # (N, J/tok)

    # 4) markdown summary + peak/energy per pair
    print("\n# §5.3 Precision ablation — same-checkpoint BF16 <-> AWQ (matched TP)\n")
    print(f"table : {table_path}")
    print(f"cells : {grid_path}\n")

    summary = []
    for label, bf16_dir, awq_dir in PAIRS:
        print(f"## {label}   (BF16 `{bf16_dir}`  |  AWQ `{awq_dir}`)\n")
        print(
            "| TP | N | BF16 tok/s | AWQ tok/s | tput ratio BF16/AWQ "
            "| BF16 J/tok | AWQ J/tok | energy ratio AWQ/BF16 |"
        )
        print("|---|---|---|---|---|---|---|---|")
        for r in table_rows:
            if r["pair"] != label:
                continue
            print(
                f"| {r['TP']} | {r['N']} | {r['bf16_tok_s'] or '—'} | {r['awq_tok_s'] or '—'} "
                f"| {r['tput_ratio_bf16_over_awq'] or '—'} | {r['bf16_J_per_tok'] or '—'} "
                f"| {r['awq_J_per_tok'] or '—'} | {r['energy_ratio_Jtok_awq_over_bf16'] or '—'} |"
            )

        # headline peak throughput ratio at HEADLINE_TP (matched parallelism)
        bt = peak_tput_cell(label, "BF16", HEADLINE_TP)
        at = peak_tput_cell(label, "AWQ", HEADLINE_TP)
        pr = round(bt[1]["tok_s"] / at[1]["tok_s"], 3) if (bt and at) else None
        # most energy-efficient operating point each precision at HEADLINE_TP
        be = best_energy(label, "BF16", HEADLINE_TP)
        ae = best_energy(label, "AWQ", HEADLINE_TP)
        er = round(ae[1] / be[1], 3) if (be and ae) else None

        # secondary: throughput-optimal independent TP (may differ in parallelism)
        def gpeak(label, precision):
            c = [
                (tp, n, grid[(label, precision, tp, n)]["tok_s"])
                for tp in TPS
                for n in N_LADDER
                if (label, precision, tp, n) in grid
            ]
            return max(c, key=lambda x: x[2]) if c else None

        gb, ga = gpeak(label, "BF16"), gpeak(label, "AWQ")
        gpr = round(gb[2] / ga[2], 3) if (gb and ga) else None

        print(
            f"\n**PEAK throughput @ matched TP{HEADLINE_TP}:** "
            f"BF16 {rr(bt[1]['tok_s'], 1)} tok/s (N{bt[0]}) | AWQ {rr(at[1]['tok_s'], 1)} tok/s (N{at[0]})"
            f"  ->  **ratio BF16/AWQ = {pr}**"
        )
        print(
            f"**Most energy-efficient @ TP{HEADLINE_TP}:** "
            f"BF16 {rr(be[1], 4)} J/tok (N{be[0]}) | AWQ {rr(ae[1], 4)} J/tok (N{ae[0]})"
            f"  ->  **energy penalty AWQ/BF16 = {er}x**"
        )
        print(
            f"_(secondary — throughput-optimal, independent TP: BF16 {rr(gb[2], 1)} tok/s "
            f"@TP{gb[0]}/N{gb[1]} vs AWQ {rr(ga[2], 1)} @TP{ga[0]}/N{ga[1]} = {gpr})_\n"
        )
        summary.append(
            (label, pr, er, be[1] if be else None, ae[1] if ae else None, gpr)
        )

    # 5) headline recap
    print("## Headline recap (matched TP2 = 2x R9700 deployment)\n")
    print(
        "| pair | peak tput ratio BF16/AWQ | BF16 J/tok (best) | AWQ J/tok (best) | energy penalty AWQ/BF16 | throughput-optimal ratio |"
    )
    print("|---|---|---|---|---|---|")
    for label, pr, er, bj, aj, gpr in summary:
        print(f"| {label} | {pr} | {rr(bj, 4)} | {rr(aj, 4)} | {er}x | {gpr} |")

    # 5b) Markdown table FILE (P1' deliverable) — CI + Holm, ready to paste in §5.3
    md_path = f"{OUT_DIR}/precision_ablation_table.md"

    def ci(lo, hi):
        return f"[{lo}, {hi}]" if (lo != "" and hi != "") else "—"

    with open(md_path, "w") as md:
        md.write(
            "# §5.3 Precision ablation — same-checkpoint BF16 ↔ AWQ (matched TP)\n\n"
        )
        md.write(
            f"Reproducibility: bootstrap seed = {SEED}, {N_BOOT} resamples, "
            f"{CI_PCT}% percentile CI of the median; Holm–Bonferroni at "
            f"α = {ALPHA} over the family of BF16-vs-AWQ cells "
            f"(Mann–Whitney U, two-sided, n = 10 vs 10). Source CSV: "
            f"`benchmarks/results/_ablation_summary/precision_ablation_table.csv`.\n\n"
        )
        md.write(
            "Throughput ratio = median(BF16 tok/s) ÷ median(AWQ tok/s). "
            "Energy ratio = median(AWQ J/tok) ÷ median(BF16 J/tok). "
            "Bracketed values are 95% bootstrap CIs.\n\n"
        )
        for label, bf16_dir, awq_dir in PAIRS:
            md.write(f"## {label}  (BF16 `{bf16_dir}` | AWQ `{awq_dir}`)\n\n")
            md.write(
                "| TP | N | BF16 tok/s [CI] | AWQ tok/s [CI] | tput ratio BF16/AWQ [CI] "
                "| energy ratio AWQ/BF16 [CI] | Holm p (tput) | sig |\n"
            )
            md.write("|---|---|---|---|---|---|---|---|\n")
            for r in table_rows:
                if r["pair"] != label:
                    continue
                bt = f"{r['bf16_tok_s'] or '—'} {ci(r['bf16_tok_s_ci_lo'], r['bf16_tok_s_ci_hi'])}"
                at = f"{r['awq_tok_s'] or '—'} {ci(r['awq_tok_s_ci_lo'], r['awq_tok_s_ci_hi'])}"
                tr = f"{r['tput_ratio_bf16_over_awq'] or '—'} {ci(r['tput_ratio_ci_lo'], r['tput_ratio_ci_hi'])}"
                en = f"{r['energy_ratio_Jtok_awq_over_bf16'] or '—'} {ci(r['energy_ratio_ci_lo'], r['energy_ratio_ci_hi'])}"
                md.write(
                    f"| {r['TP']} | {r['N']} | {bt} | {at} | {tr} | {en} "
                    f"| {r['mw_p_tput_holm'] or '—'} | {r['sig_tput_holm'] or '—'} |\n"
                )
            md.write("\n")
        md.write("## Headline recap (matched TP2 = 2× R9700 deployment)\n\n")
        md.write(
            "| pair | peak tput ratio BF16/AWQ | BF16 J/tok (best) | AWQ J/tok (best) "
            "| energy penalty AWQ/BF16 | throughput-optimal ratio |\n"
        )
        md.write("|---|---|---|---|---|---|\n")
        for label, pr, er, bj, aj, gpr in summary:
            md.write(
                f"| {label} | {pr} | {rr(bj, 4)} | {rr(aj, 4)} | {er}× | {gpr} |\n"
            )
    print(f"\nmarkdown table written: {md_path}")

    # 6) validation vs published ladder for BF16 members present there
    print("\n## Validation vs published ladder_median_wide.csv (BF16 throughput)\n")
    model_map = {"Bielik-4.5B": ("bielik-4.5b-v30", "Bielik-4.5B-v3.0", "BF16")}
    any_delta = False
    for label, (d, mdl, q) in model_map.items():
        for tp in TPS:
            for n in N_LADDER:
                s = grid.get((label, "BF16", tp, n))
                lv = ladder.get((mdl, q, str(tp), n))
                if s and lv:
                    delta = 100 * (s["tok_s"] - lv) / lv
                    if abs(delta) > 1.0:
                        any_delta = True
                        print(
                            f"  {label} BF16 TP{tp} N{n}: raw {s['tok_s']:.2f} vs ladder {lv:.2f} ({delta:+.1f}%)"
                        )
    if not any_delta:
        print(
            "  OK — raw parse reproduces the published Bielik-4.5B BF16 ladder to <1% at every cell.\n"
        )


if __name__ == "__main__":
    main()
