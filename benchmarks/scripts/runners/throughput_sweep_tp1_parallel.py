#!/usr/bin/env python3
"""
throughput_sweep_tp1_parallel.py — KROK C (#3, wariant TP=1‖TP=1).

Co-located dual-instance throughput sweep: TWO independent vLLM engines, each
TP=1, each pinned to one physical R9700 via HIP_VISIBLE_DEVICES (0 and 1), run
*simultaneously* — each benchmarking a DIFFERENT model. This measures the v0.3
suite under the "two single-GPU servers" deployment pattern (kyuz0 models.py
TP:[1,2]), the complement to the sequential TP=2 / TP=1 sweep produced by
throughput_sweep_v0.3.py.

Why a separate harness (METHODOLOGY §5.2):
  - throughput_sweep_v0.3.py runs one model at a time on whatever TP its sanity
    record used. The TP=1 numbers it produces are *isolated* TP=1 (the second
    R9700 idle). This harness produces *co-located* TP=1: both cards loaded at
    once, so memory-bus / PCIe / power-budget contention is captured. Different
    deployment, different dataset — kept in benchmarks/results/<model>/tp1-parallel/.
  - Child benchmark logic is reused byte-for-byte from throughput_sweep_v0.3.py
    (imported as a module) so workload §6 and metrics §7.1 are identical.

Pinning: each instance gets HIP_VISIBLE_DEVICES=<0|1> in its env, which makes
vLLM see exactly one R9700 → tensor_parallel_size=1 lands on that physical card.
ROCR_VISIBLE_DEVICES (set 0,1 by _env.sh) is removed from the child env so the
HIP_VISIBLE_DEVICES pin is authoritative.

Per pair: for each N in the ladder, the two model children are launched
concurrently and joined. A single background sample_system.py captures 1 Hz
thermals for the whole pair window (it samples both GPUs; each model's row
records its own physical GPU's peak).

Output per model (distinct from sequential sweep):
  benchmarks/results/<model>/tp1-parallel/<quant>-tp1par-gpu<G>-n<N>-bench.log
  benchmarks/results/<model>/tp1-parallel/<quant>-tp1par-n<N>-thermals.jsonl  (shared per pair/N)
  benchmarks/results/<model>/tp1-parallel/results_table.csv     (§7.1 schema + co_model col)
  benchmarks/results/<model>/tp1-parallel/SUMMARY.md

Embargo: Phase 2 scaling numbers EMBARGOED §11.2 (Polish models §11.3).
benchmarks/results/ is fully gitignored — outputs stay local.

Usage:
    python throughput_sweep_tp1_parallel.py \
        --gpu0 "model_dir|quant|extra" --gpu1 "model_dir|quant|extra" \
        [--ns 10,25,50,100,200]

Author: Claude Code (navimed-umb idle-GPU subagent, re-dispatch), 2026-05-20.
"""

import argparse
import csv
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Reuse the validated sequential harness: identical workload §6, child logic,
# thermal aggregation, CSV schema. Single source of truth. The filename
# contains a dot ("throughput_sweep_v0.3.py") so it cannot be `import`-ed by
# name — load it explicitly via importlib from its file path.
_RUNNERS = Path(__file__).resolve().parent
_SEQ_PATH = _RUNNERS / "throughput_sweep_v0.3.py"
_spec = importlib.util.spec_from_file_location("throughput_sweep_v03", _SEQ_PATH)
seq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seq)

REPO = Path(__file__).resolve().parents[3]
MODELS_DIR = Path.home() / "models"
RESULTS_DIR = REPO / "benchmarks" / "results"
SAMPLER = REPO / "benchmarks" / "scripts" / "instrumentation" / "sample_system.py"
KILL_PORT = REPO / "scripts" / "kill_port.sh"

DEFAULT_NS = [10, 25, 50, 100, 200]
UTIL = seq.UTIL
MAX_LEN = seq.MAX_LEN
COOLDOWN_S = seq.COOLDOWN_S
IDLE_BEFORE_S = seq.IDLE_BEFORE_S
IDLE_AFTER_S = seq.IDLE_AFTER_S
PER_RUN_TIMEOUT_S = seq.PER_RUN_TIMEOUT_S
CHILD_SCRIPT = _RUNNERS / "throughput_sweep_v0.3.py"


def run_child_pinned(
    model_dir: str, model_path: Path, n: int, extra: str, hip_dev: int, bench_log: Path
) -> dict:
    """Spawn ONE pinned vLLM child (TP=1 on physical GPU hip_dev). Blocking.

    Reuses throughput_sweep_v0.3.py --child verbatim — same engine kwargs,
    same workload, same BENCH_METRICS_JSON contract."""
    env = os.environ.copy()
    # Pin authoritative: HIP_VISIBLE_DEVICES wins; drop ROCR pin from _env.sh.
    env.pop("ROCR_VISIBLE_DEVICES", None)
    env["HIP_VISIBLE_DEVICES"] = str(hip_dev)
    cmd = [
        sys.executable,
        "-u",
        str(CHILD_SCRIPT),
        "--child",
        "--model-path",
        str(model_path),
        "--tp",
        "1",
        "--n",
        str(n),
        "--extra",
        extra,
    ]
    metrics = {"ok": False, "error": "not run"}
    with open(bench_log, "w") as f:
        f.write(f"# pinned HIP_VISIBLE_DEVICES={hip_dev} model={model_dir} N={n}\n")
        f.flush()
        try:
            cp = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=PER_RUN_TIMEOUT_S,
            )
            rc = cp.returncode
        except subprocess.TimeoutExpired:
            rc = 124
            f.write(f"\nTIMEOUT after {PER_RUN_TIMEOUT_S}s\n")
    text = bench_log.read_text()
    for line in text.splitlines():
        if line.startswith("BENCH_METRICS_JSON="):
            metrics = json.loads(line[len("BENCH_METRICS_JSON=") :])
            break
    else:
        metrics = {"ok": False, "error": f"no metrics (rc={rc})"}
    kv_log, maxc_log = seq.parse_kv_maxc(text)
    if kv_log is not None:
        metrics["kv_cache_tokens"] = kv_log
    if maxc_log is not None:
        metrics["max_concurrency"] = maxc_log
    return metrics


def make_row(
    model_dir: str,
    quant: str,
    n: int,
    metrics: dict,
    therm: dict,
    co_model: str,
    hip_dev: int,
) -> dict:
    """§7.1 schema row + tp1-parallel-specific columns (co_model, gpu)."""
    row = {
        "model": model_dir,
        "quant": quant,
        "backend": "vLLM",
        "TP": 1,
        "config": "tp1-parallel",
        "co_model": co_model,
        "gpu": hip_dev,
        "max_len": MAX_LEN,
        "util": UTIL,
        "kv_dtype": "default",
        "N": n,
        "ok": metrics.get("ok", False),
        "error": metrics.get("error"),
        "load_time_s": metrics.get("load_time_s"),
        "kv_cache_tokens": metrics.get("kv_cache_tokens"),
        "max_concurrency": metrics.get("max_concurrency"),
        "total_time_s": metrics.get("total_time_s"),
        "tok_s_out": metrics.get("tok_s_out"),
        "tok_s_tot": metrics.get("tok_s_tot"),
        "req_s": metrics.get("req_s"),
        "total_output_tokens": metrics.get("total_output_tokens"),
        "mean_output_len": metrics.get("mean_output_len"),
        "vram_peak_gb": therm.get("vram_peak_gb"),
        "temp_peak_c": therm.get("temp_peak_c"),
        "power_mean_w": therm.get("power_mean_w"),
        "power_peak_w": therm.get("power_peak_w"),
        "tuning": "stock",
    }
    if (
        therm.get("power_mean_w")
        and metrics.get("total_time_s")
        and metrics.get("total_output_tokens")
    ):
        row["w_per_tok"] = round(
            therm["power_mean_w"]
            * metrics["total_time_s"]
            / metrics["total_output_tokens"],
            5,
        )
    else:
        row["w_per_tok"] = None
    return row


def aggregate_thermals_gpu(jsonl: Path, t0: float, t1: float, hip_dev: int) -> dict:
    """Peak VRAM/temp + mean/peak power for ONE physical GPU in window.

    Co-located runs put two models on two cards; each model's row must reflect
    only its own card. sample_system.py emits gpus[] in stable index order
    (R9700 pair = 0,1; iGPU filtered by is_igpu)."""
    vram_peak = temp_peak = pw_peak = 0.0
    pw_sum = 0.0
    pw_n = 0
    try:
        for line in jsonl.read_text().splitlines():
            s = json.loads(line)
            t = s.get("t", -1)
            in_window = t0 <= t <= t1
            real_gpus = [g for g in s.get("gpus", []) if not g.get("is_igpu")]
            if hip_dev >= len(real_gpus):
                continue
            g = real_gpus[hip_dev]
            vb = g.get("vram_used_b")
            if vb:
                vram_peak = max(vram_peak, vb / 1e9)
            if in_window:
                tp_ = g.get("temp")
                pw = g.get("power_w")
                if tp_:
                    temp_peak = max(temp_peak, tp_)
                if pw:
                    pw_peak = max(pw_peak, pw)
                    pw_sum += pw
                    pw_n += 1
    except Exception:
        pass
    return {
        "vram_peak_gb": round(vram_peak, 3) if vram_peak else None,
        "temp_peak_c": round(temp_peak, 1) if temp_peak else None,
        "power_mean_w": round(pw_sum / pw_n, 1) if pw_n else None,
        "power_peak_w": round(pw_peak, 1) if pw_peak else None,
    }


def run_pair_n(spec0: dict, spec1: dict, n: int) -> tuple[dict, dict]:
    """Run ONE N point for the pair: both children concurrent, one sampler.

    Returns (row_gpu0, row_gpu1)."""
    # Shared thermal sampler for the pair window; named after both models.
    therm_dir = spec0["out_dir"]
    jsonl = therm_dir / f"{spec0['quant']}-tp1par-n{n}-thermals.jsonl"
    log0 = spec0["out_dir"] / f"{spec0['quant']}-tp1par-gpu0-n{n}-bench.log"
    log1 = spec1["out_dir"] / f"{spec1['quant']}-tp1par-gpu1-n{n}-bench.log"

    subprocess.run([str(KILL_PORT), "8101"], check=False, capture_output=True)
    subprocess.run([str(KILL_PORT), "8102"], check=False, capture_output=True)

    sampler = subprocess.Popen(
        [sys.executable, str(SAMPLER), str(jsonl), "--interval", "1.0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    t_wall0 = time.time()
    res = {0: None, 1: None}
    try:
        time.sleep(IDLE_BEFORE_S)
        t_bs = time.time() - t_wall0

        def _worker(slot: int, spec: dict, hip_dev: int, log: Path):
            res[slot] = run_child_pinned(
                spec["model_dir"], spec["model_path"], n, spec["extra"], hip_dev, log
            )

        th0 = threading.Thread(target=_worker, args=(0, spec0, 0, log0))
        th1 = threading.Thread(target=_worker, args=(1, spec1, 1, log1))
        th0.start()
        th1.start()
        th0.join()
        th1.join()
        t_be = time.time() - t_wall0
        time.sleep(IDLE_AFTER_S)
    finally:
        sampler.send_signal(signal.SIGINT)
        try:
            sampler.wait(timeout=8)
        except subprocess.TimeoutExpired:
            sampler.kill()

    therm0 = aggregate_thermals_gpu(jsonl, t_bs, t_be, 0)
    therm1 = aggregate_thermals_gpu(jsonl, t_bs, t_be, 1)
    row0 = make_row(
        spec0["model_dir"],
        spec0["quant"],
        n,
        res[0] or {},
        therm0,
        spec1["model_dir"],
        0,
    )
    row1 = make_row(
        spec1["model_dir"],
        spec1["quant"],
        n,
        res[1] or {},
        therm1,
        spec0["model_dir"],
        1,
    )

    subprocess.run([str(KILL_PORT), "8101"], check=False, capture_output=True)
    subprocess.run([str(KILL_PORT), "8102"], check=False, capture_output=True)
    return row0, row1


CSV_COLS = [
    "model",
    "quant",
    "backend",
    "TP",
    "config",
    "co_model",
    "gpu",
    "max_len",
    "util",
    "kv_dtype",
    "N",
    "ok",
    "load_time_s",
    "kv_cache_tokens",
    "max_concurrency",
    "total_time_s",
    "tok_s_out",
    "tok_s_tot",
    "req_s",
    "total_output_tokens",
    "mean_output_len",
    "vram_peak_gb",
    "temp_peak_c",
    "power_mean_w",
    "power_peak_w",
    "w_per_tok",
    "tuning",
    "error",
]


def write_summary(spec: dict, rows: list[dict], wall_s: float):
    out_dir = spec["out_dir"]
    csv_path = out_dir / "results_table.csv"
    md = out_dir / "SUMMARY.md"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    ok_rows = [r for r in rows if r["ok"]]
    best = max(ok_rows, key=lambda r: r["tok_s_out"] or 0, default=None)
    co = rows[0]["co_model"] if rows else "?"
    lines = [
        f"# Phase 2 throughput sweep — {spec['model_dir']} (TP=1‖TP=1 co-located)",
        "",
        "> **EMBARGO §11.2** — Phase 2 scaling numbers (throughput@N, KV"
        " curves, W/tok) EMBARGOED until paper acceptance. Polish models"
        " carry stricter embargo §11.3. `benchmarks/results/` is gitignored.",
        "",
        "> **Config:** co-located dual-instance — this model runs TP=1 pinned"
        f" to one R9700 *while* `{co}` runs TP=1 on the other R9700"
        " simultaneously. Captures memory-bus / power-budget contention vs the"
        " isolated TP=1 / TP=2 numbers from throughput_sweep_v0.3.py.",
        "",
        "> Following Lerchner (2026): we measure inference *throughput*,"
        " *latency*, *thermal envelope*, *power efficiency* under concurrent"
        " load. We do not measure model quality. Claims terminate at the"
        " hardware-software interface.",
        "",
        f"- **Model:** `{spec['model_dir']}` quant=`{spec['quant']}` TP=1"
        f" (pinned GPU{rows[0]['gpu'] if rows else '?'})",
        f"- **Co-located with:** `{co}` on the other R9700",
        "- **Workload:** METHODOLOGY §6 synthetic (8 templates × 20 topics,"
        " temp=0.7, max_tokens=128)",
        f"- **Config:** max_model_len={MAX_LEN}, util={UTIL}, enforce_eager=True",
        f"- **Sweep wall time (this model):** {wall_s/60:.1f} min",
        "- **Stack:** vLLM 0.19.0+rocm721, transformers 5.8.1, ROCm 7.2,"
        " 2× R9700 gfx1201",
        "",
        "## Results table (§7.1 schema)",
        "",
        "| N | tok/s_out | tok/s_tot | req/s | total_s | VRAM_GB | T_peak_C |"
        " W_mean | W_peak | W/tok | load_s | ok |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['N']} | {r['tok_s_out']} | {r['tok_s_tot']} | {r['req_s']}"
            f" | {r['total_time_s']} | {r['vram_peak_gb']} | {r['temp_peak_c']}"
            f" | {r['power_mean_w']} | {r['power_peak_w']} | {r['w_per_tok']}"
            f" | {r['load_time_s']} | {'OK' if r['ok'] else 'FAIL'} |"
        )
    lines += [""]
    if best:
        lines.append(
            f"- **Peak output throughput (co-located TP=1):**"
            f" {best['tok_s_out']} tok/s at N={best['N']}"
        )
    fails = [r for r in rows if not r["ok"]]
    if fails:
        lines += ["", "## Failures"]
        for r in fails:
            lines.append(f"- N={r['N']}: {r['error']}")
    lines += [
        "",
        "## AI disclosure (METHODOLOGY §9)",
        "",
        "Layer 2 (experimental pipeline): co-located TP=1‖TP=1 sweep"
        " orchestrated by Claude Code (Anthropic, Opus 4.7) as an idle-GPU"
        " subagent re-dispatch, 2026-05-20. Harness"
        " `throughput_sweep_tp1_parallel.py` reuses the validated"
        " `throughput_sweep_v0.3.py` child (METHODOLOGY §5.2/§6/§7"
        " unchanged). No AI involvement in data generation (synthetic"
        " prompts deterministic, §6). Layer 1: not applicable.",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()}_",
    ]
    md.write_text("\n".join(lines))
    return csv_path, md


def parse_spec(s: str) -> dict:
    """'model_dir|quant|extra' -> dict with resolved paths."""
    parts = (s.split("|") + ["", "", ""])[:3]
    mdir, quant, extra = parts[0].strip(), parts[1].strip(), parts[2].strip()
    mpath = MODELS_DIR / mdir
    out_dir = RESULTS_DIR / mdir / "tp1-parallel"
    return {
        "model_dir": mdir,
        "quant": quant or "auto",
        "extra": extra,
        "model_path": mpath,
        "out_dir": out_dir,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu0", required=True, help="'model_dir|quant|extra'")
    ap.add_argument("--gpu1", required=True, help="'model_dir|quant|extra'")
    ap.add_argument("--ns", default=None, help="comma list, default 10,25,50,100,200")
    args = ap.parse_args()

    spec0 = parse_spec(args.gpu0)
    spec1 = parse_spec(args.gpu1)
    for sp in (spec0, spec1):
        if not (sp["model_path"] / "config.json").exists():
            print(f"ERROR: {sp['model_path']}/config.json missing", file=sys.stderr)
            return 1
        sp["out_dir"].mkdir(parents=True, exist_ok=True)

    ns = [int(x) for x in args.ns.split(",")] if args.ns else DEFAULT_NS
    print(f"[tp1par] GPU0={spec0['model_dir']} ‖ GPU1={spec1['model_dir']} N={ns}")
    t_start = time.time()
    rows0, rows1 = [], []
    for n in ns:
        print(f"[tp1par]   N={n} (both engines concurrent) ...", flush=True)
        tr0 = time.time()
        r0, r1 = run_pair_n(spec0, spec1, n)
        rows0.append(r0)
        rows1.append(r1)
        dt = time.time() - tr0
        for tag, r in (("GPU0", r0), ("GPU1", r1)):
            if r["ok"]:
                print(
                    f"[tp1par]   {tag} {r['model']} N={n} -> "
                    f"{r['tok_s_out']} tok/s_out, {r['req_s']} req/s, "
                    f"VRAM {r['vram_peak_gb']}GB, T {r['temp_peak_c']}C"
                )
            else:
                print(f"[tp1par]   {tag} {r['model']} N={n} -> FAIL: {r['error']}")
        print(f"[tp1par]   N={n} pair wall {dt:.0f}s")
        if n != ns[-1]:
            time.sleep(COOLDOWN_S)

    wall = time.time() - t_start
    c0, m0 = write_summary(spec0, rows0, wall)
    c1, m1 = write_summary(spec1, rows1, wall)
    print(f"[tp1par] pair done — wall {wall/60:.1f} min")
    print(f"[tp1par] {spec0['model_dir']}: {c0}")
    print(f"[tp1par] {spec1['model_dir']}: {c1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
