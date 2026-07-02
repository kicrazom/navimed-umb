#!/usr/bin/env python3
"""Aggregate energy efficiency: throughput from canonical, power from RAW thermals.

Decoupled best-source design:
  - throughput tok_s : canonical_dataset.csv tok_s_out_median (trusted, aggregated;
                       same number behind the throughput figures).
  - power_total_W    : mean over the inference window [events bench start..end] of
                       sum(power_w over discrete GPUs, skip igpu/null) = TOTAL system
                       GPU draw, median over reps. Read from raw thermals only.
  tok_per_J = tok_s / power_total_W ;  J_per_tok = power_total_W / tok_s (Joules/token).

Why raw power, not results_table.csv power_mean_w: that column is mean PER-GPU
(= total/2), verified buggy (70B base TP2 N10: raw 424 W vs results_table 210 W;
small/mid 4.5b TP1 N200: raw 133 W vs results_table 61 W). Raw-window total matches
phase2_sweep W_mean_median for small/mid. Single source of truth = raw thermals.

Sources of raw telemetry:
  - small/mid : results/<dir>/thermal-runs/<q>-tp<TP>-n<N>-r<rep>-{thermals.jsonl,events.json}
  - 70B       : results/<dir>/scaling/rep*/thermal-runs/<q>-tp<TP>-n<N>-{...}
Join key = (result_dir, TP, N). EMBARGO §11.3. Run from repo root.
"""

import csv
import glob
import json
import os
import re
import statistics as st
from collections import defaultdict

FIG = "paper/figures"
RES = "benchmarks/results"

ident, ctput = {}, {}
for r in csv.DictReader(open(f"{FIG}/canonical_dataset.csv")):
    ident[r["result_dir"]] = (r["model"], r["family"], r["tier"], r["quant"])
    ctput[(r["result_dir"], r["TP"], r["N"])] = float(r["tok_s_out_median"])


def window_power(thermals, events):
    """Mean TOTAL GPU power (sum of discrete GPUs) over the bench window."""
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


powr = defaultdict(list)
patterns = [
    f"{RES}/*/thermal-runs/*-thermals.jsonl",
    f"{RES}/*/scaling/rep*/thermal-runs/*-thermals.jsonl",
]
for pat in patterns:
    for tf in glob.glob(pat):
        m = re.search(r"-tp(\d+)-n(\d+)", os.path.basename(tf))
        if not m:
            continue
        tp, n = m.group(1), m.group(2)
        rdir = tf.split("benchmarks/results/")[1].split("/")[0]
        k = (rdir, tp, n)
        if rdir not in ident or k not in ctput:  # canonical N + known model only
            continue
        pw = window_power(tf, tf[: -len("-thermals.jsonl")] + "-events.json")
        if pw and pw > 0:
            powr[k].append(pw)

cols = [
    "model",
    "result_dir",
    "family",
    "tier",
    "quant",
    "TP",
    "N",
    "tok_s_med",
    "power_w_med",
    "tok_per_J_med",
    "J_per_tok_med",
    "n",
]
out = []
for k, pws in powr.items():
    rdir, tp, n = k
    model, family, tier, quant = ident[rdir]
    tsm = ctput[k]
    pwm = st.median(pws)
    out.append(
        {
            "model": model,
            "result_dir": rdir,
            "family": family,
            "tier": tier,
            "quant": quant,
            "TP": tp,
            "N": int(n),
            "tok_s_med": round(tsm, 2),
            "power_w_med": round(pwm, 1),
            "tok_per_J_med": round(tsm / pwm, 4),
            "J_per_tok_med": round(pwm / tsm, 4),
            "n": len(pws),
        }
    )
out.sort(key=lambda r: (r["family"], r["tier"], r["model"], r["TP"], r["N"]))

dst = f"{FIG}/power_efficiency_dataset.csv"
with open(dst, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(out)
print(f"wrote {dst}: {len(out)} cells, {len(set(r['model'] for r in out))} models")
