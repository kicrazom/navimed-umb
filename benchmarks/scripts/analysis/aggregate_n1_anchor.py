#!/usr/bin/env python3
"""Aggregate the N=1 single-stream anchor runs into a canonical-schema CSV.

Sources (whatever exists; partial is fine while the sweep is still running):
  - small/mid : benchmarks/results/<key>/n1-anchor/<quant>-tp<TP>-n1-r<rep>-bench.log
                (tok/s from the "Output throughput:" line; result_dir = the vLLM
                 model-path basename, which equals the canonical result_dir)
  - 70B       : benchmarks/results/<dir>/scaling-n1/rep<NN>/results_table.csv
                (tok_s_out where N==1; result_dir = the CSV "model" column)

Each run's identity (model, family, tier, quant) is taken from the canonical
dataset keyed by result_dir, so the emitted N=1 row lands on the SAME curve as
the {10..1000} ladder. Writes paper/figures/n1_anchor_dataset.csv (median/min/max
over reps), which ladder_table_plots.R joins automatically.

EMBARGO §11.3 (paper/figures gitignored). Run from repo root.
"""

import csv
import glob
import os
import re
import statistics as st
from collections import defaultdict

FIG = "paper/figures"
RES = "benchmarks/results"

# canonical identity: result_dir -> (model, family, tier, quant)
ident = {}
for r in csv.DictReader(open(f"{FIG}/canonical_dataset.csv")):
    ident[r["result_dir"]] = (r["model"], r["family"], r["tier"], r["quant"])

groups = defaultdict(list)  # (result_dir, TP) -> [tok/s per rep]

# --- small/mid: parse each bench.log ---
for bl in glob.glob(f"{RES}/*/n1-anchor/*-bench.log"):
    m = re.search(r"-tp(\d+)-n1-r\d+-bench\.log$", os.path.basename(bl))
    if not m:
        continue
    tp = m.group(1)
    rdir = tps = None
    with open(bl) as fh:
        for ln in fh:
            if rdir is None:
                mm = re.search(r"model='([^']*)'", ln)
                if mm:
                    rdir = os.path.basename(mm.group(1))
            if ln.startswith("Output throughput:"):
                tps = float(re.search(r"([0-9.]+)", ln).group(1))
    if rdir and tps is not None:
        groups[(rdir, tp)].append(tps)

# --- 70B: parse N==1 row from each rep's results_table.csv ---
for ct in glob.glob(f"{RES}/*/scaling-n1/rep*/results_table.csv"):
    with open(ct) as fh:
        for r in csv.DictReader(fh):
            if (
                r.get("N") == "1"
                and r.get("ok", "True") == "True"
                and r.get("tok_s_out")
            ):
                groups[(r["model"], r["TP"])].append(float(r["tok_s_out"]))

# --- emit canonical-schema rows ---
cols = [
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
]
out = []
for (rdir, tp), v in groups.items():
    if rdir not in ident:
        print(f"WARN: no canonical identity for result_dir={rdir} (skipped)")
        continue
    model, family, tier, quant = ident[rdir]
    out.append(
        {
            "model": model,
            "result_dir": rdir,
            "family": family,
            "tier": tier,
            "quant": quant,
            "TP": tp,
            "N": "1",
            "tok_s_out_median": round(st.median(v), 3),
            "tok_s_out_min": round(min(v), 3),
            "tok_s_out_max": round(max(v), 3),
            "n_ok": len(v),
        }
    )
out.sort(key=lambda r: (r["family"], r["tier"], r["model"], r["TP"]))

dst = f"{FIG}/n1_anchor_dataset.csv"
with open(dst, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(out)
print(f"wrote {dst}: {len(out)} N=1 rows ({sum(r['n_ok'] for r in out)} reps total)")
