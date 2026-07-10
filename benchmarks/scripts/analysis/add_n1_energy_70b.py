#!/usr/bin/env python3
"""Append REAL N=1 energy rows for the 70B family to power_efficiency_dataset.csv.

The N=1 single-stream anchor logged full raw thermal telemetry for the 70B family
(scaling-n1/rep*/thermal-runs/*-n1-thermals.jsonl + -events.json) — the standard
aggregator just didn't glob that path. This fills N=1 for 70B from the SAME
ground-truth source (window-mean TOTAL GPU draw, median over reps) that the
N>=10 energy points use. No estimation. Throughput at N=1 from ladder_median_wide.
Small/mid have no N=1 telemetry -> not touched here (need a short re-run).
EMBARGO §11.3.
"""

import csv
import glob
import json
import statistics as st

BASE = "/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb"
FIG = f"{BASE}/paper/figures"
RES = f"{BASE}/benchmarks/results"

# N=1 throughput per (model, TP) from the ladder (ground-truth medians)
tput = {}
for r in csv.DictReader(open(f"{FIG}/R/ladder_median_wide.csv")):
    v = (r.get("N1") or "").strip()
    if v and v.upper() != "NA":
        try:
            tput[(r["model"], str(r["TP"]))] = float(v)
        except ValueError:
            pass


def window_power(thermals, events):
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


rows = list(csv.DictReader(open(f"{FIG}/power_efficiency_dataset.csv")))
cols = list(rows[0].keys())
have_n1 = {(r["result_dir"], str(r["TP"])) for r in rows if str(r["N"]) == "1"}
meta70 = {}
for r in rows:
    if r["tier"] == "70B":
        meta70[(r["result_dir"], str(r["TP"]))] = (
            r["model"],
            r["family"],
            r["tier"],
            r["quant"],
        )

added = []
for (rdir, tp), (model, fam, tier, quant) in meta70.items():
    if (rdir, tp) in have_n1:
        continue
    pws = []
    for tf in glob.glob(
        f"{RES}/{rdir}/scaling-n1/rep*/thermal-runs/*-tp{tp}-n1-thermals.jsonl"
    ):
        pw = window_power(tf, tf[: -len("-thermals.jsonl")] + "-events.json")
        if pw and pw > 0:
            pws.append(pw)
    ts = tput.get((model, tp))
    if not pws or ts is None:
        print(f"SKIP {model} TP{tp}: reps={len(pws)} tput={ts}")
        continue
    pwm = st.median(pws)
    added.append(
        {
            "model": model,
            "result_dir": rdir,
            "family": fam,
            "tier": tier,
            "quant": quant,
            "TP": tp,
            "N": "1",
            "tok_s_med": round(ts, 2),
            "power_w_med": round(pwm, 1),
            "tok_per_J_med": round(ts / pwm, 4),
            "J_per_tok_med": round(pwm / ts, 4),
            "n": len(pws),
        }
    )
    print(
        f"ADD N=1 {model} TP{tp}: {round(pwm,1)} W, {round(ts/pwm,4)} tok/J (reps={len(pws)})"
    )

allrows = rows + added
allrows.sort(
    key=lambda r: (r["family"], r["tier"], r["model"], str(r["TP"]), int(r["N"]))
)
with open(f"{FIG}/power_efficiency_dataset.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(allrows)
print(
    f"\nappended {len(added)} real N=1 energy rows (70B); dataset now {len(allrows)} rows"
)
