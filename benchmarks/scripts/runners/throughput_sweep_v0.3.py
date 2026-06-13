#!/usr/bin/env python3
"""
throughput_sweep_v0.3.py — KROK B (#3): throughput sweep for navimed-umb v0.3.

Model-generic Phase 2 scaling sweep (METHODOLOGY §5.2). Existing per-model
runners (test_concurrent_bielik_11b_v30.py etc.) hardcode model_path; this is
the parameterized sibling that takes the model on the CLI so the whole v0.3
PASS suite can be swept with one harness — same workload (§6, make_prompts is
byte-for-byte identical), same reporting schema (§7.1).

Per model: for each N in the ladder, ONE LLM() process is spawned (vLLM TP
worker re-import requires process isolation; engine state is unrecoverable
after a high-N preemption run). A background sample_system.py captures 1 Hz
thermals/power across the run window.

Workload (METHODOLOGY §6): 8 templates × 20 topics, temperature=0.7,
max_tokens=128, warmup=min(5,N) discarded.

N ladder default: {10,25,50,100,200} — conservative for an idle-GPU sweep
across 11 models. {500,1000} omitted to bound total wall time; knee for these
small/mid models sits well below 200 (max_concurrency from Phase 1 sanity is
4-29x at 8192 ctx → knee at N≈40-240). The ladder still spans linear region,
knee, and into preemption for every model.

Output per model (METHODOLOGY §7.3):
  benchmarks/results/<model>/thermal-runs/<quant>-tp<TP>-n<N>-bench.log
  benchmarks/results/<model>/thermal-runs/<quant>-tp<TP>-n<N>-thermals.jsonl
  benchmarks/results/<model>/thermal-runs/<quant>-tp<TP>-n<N>-events.json
  benchmarks/results/<model>/results_table.csv      (flat §7.1 schema)
  benchmarks/results/<model>/SUMMARY.md             (narrative + table)

Embargo: Phase 2 scaling numbers EMBARGOED §11.2 (Polish models §11.3).
benchmarks/results/ is fully gitignored — outputs stay local.

Usage:
    python throughput_sweep_v0.3.py <model_dir> <tp> --quant Q [--extra "..."]
                                    [--ns 10,25,50,100,200]

Author: Claude Code (navimed-umb idle-GPU subagent), 2026-05-20.
"""

import argparse
import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# vLLM logs KV pool + max_concurrency at engine init; the attribute path is
# version-fragile, so parse the log lines (same approach as batch_sanity_v0.3.sh).
RE_KV = re.compile(r"GPU KV cache size:\s*([\d,]+)\s*tokens")
RE_MAXC = re.compile(r"Maximum concurrency for [\d,]+ tokens per request:\s*([\d.]+)x")


def parse_kv_maxc(text: str) -> tuple[int | None, float | None]:
    """Extract (kv_cache_tokens, max_concurrency) from vLLM engine log text."""
    kv = maxc = None
    m = RE_KV.search(text)
    if m:
        kv = int(m.group(1).replace(",", ""))
    m = RE_MAXC.search(text)
    if m:
        maxc = float(m.group(1))
    return kv, maxc


REPO = Path(__file__).resolve().parents[3]
MODELS_DIR = Path.home() / "models"
RESULTS_DIR = REPO / "benchmarks" / "results"
SAMPLER = REPO / "benchmarks" / "scripts" / "instrumentation" / "sample_system.py"
KILL_PORT = REPO / "scripts" / "kill_port.sh"

DEFAULT_NS = [10, 25, 50, 100, 200]
UTIL = 0.90
MAX_LEN = 8192  # sweep at suite-standard context (matches sanity envelope)
COOLDOWN_S = 15  # METHODOLOGY §5.2


def _read_bios_version() -> str:
    """Motherboard BIOS version from DMI (e.g. '2202'). 'unknown' on failure."""
    try:
        return Path("/sys/class/dmi/id/bios_version").read_text().strip() or "unknown"
    except Exception:
        return "unknown"


def _read_bios_date() -> str:
    """BIOS release date from DMI (e.g. '04/15/2026'). 'unknown' on failure."""
    try:
        return Path("/sys/class/dmi/id/bios_date").read_text().strip() or "unknown"
    except Exception:
        return "unknown"


def _read_agesa_version() -> str:
    """AGESA version from fwupd's Secure Processor summary, e.g.
    'AGESA ComboAm5PI 1.3.0.1'. Returns 'unknown' if fwupd is absent or
    no match is found.

    AGESA is not exposed via sysfs DMI; fwupd's Secure Processor device
    reports it in its Summary field. Read-only, --no-authenticate, best-effort.
    """
    try:
        r = subprocess.run(
            ["fwupdmgr", "get-devices", "--no-authenticate"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        clean = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)  # strip ANSI colour codes
        m = re.search(r"AGESA\s+(\S+)\s+(\S+)", clean)
        if m:
            return f"AGESA {m.group(1)} {m.group(2)}"
    except Exception:
        pass
    return "unknown"


# Host firmware is constant per run — capture once at module load. Per the
# Lerchner (2026) "complete vehicle specification" principle (METHODOLOGY §3),
# BIOS/AGESA complete the provenance that the software version triple omits.
BIOS_VERSION = _read_bios_version()
BIOS_DATE = _read_bios_date()
AGESA_VERSION = _read_agesa_version()
IDLE_BEFORE_S = 5.0
IDLE_AFTER_S = 5.0
PER_RUN_TIMEOUT_S = 900

TEMPLATES = [
    "Explain {} in simple terms, with an example:",
    "Write a short story (about 100 words) involving {}:",
    "What are the three key benefits of {}? Give specific reasons:",
    "Summarize the history of {} in 3-4 sentences:",
    "Compare {} with a related concept, highlighting differences:",
    "Describe how {} works from first principles:",
    "What are common misconceptions about {}? Address them:",
    "Give a practical example of using {} in everyday life:",
]
TOPICS = [
    "quantum entanglement",
    "photosynthesis",
    "machine learning",
    "the TCP/IP protocol",
    "black holes",
    "mRNA vaccines",
    "distributed systems",
    "neural plasticity",
    "supply chain logistics",
    "tensor parallelism",
    "climate feedback loops",
    "the Krebs cycle",
    "cryptographic hashing",
    "CRISPR gene editing",
    "monetary policy",
    "reinforcement learning",
    "ocean currents",
    "magnetic resonance imaging",
    "fermentation",
    "GPS triangulation",
]


def make_prompts(n: int) -> list[str]:
    """METHODOLOGY §6 — identical to test_concurrent_*.py. DO NOT MODIFY."""
    return [TEMPLATES[i % 8].format(TOPICS[i % 20]) for i in range(n)]


# ---------------------------------------------------------------------------
# Child: one (model, TP, N) benchmark run. Spawned per N. Prints metrics JSON.
# ---------------------------------------------------------------------------
def run_child(model_path: str, tp: int, n: int, extra: str) -> int:
    metrics = {"ok": False, "error": None}
    try:
        from vllm import LLM, SamplingParams

        kwargs = dict(
            model=model_path,
            max_model_len=MAX_LEN,
            gpu_memory_utilization=UTIL,
            enforce_eager=True,
            tensor_parallel_size=tp,
        )
        if "awq_marlin" in extra:
            kwargs["quantization"] = "awq_marlin"
        if "--no-enable-prefix-caching" in extra:
            kwargs["enable_prefix_caching"] = False

        t0 = time.time()
        llm = LLM(**kwargs)
        load_s = time.time() - t0

        kv_tokens = None
        max_conc = None
        try:
            ec = llm.llm_engine.cache_config
            nb = getattr(ec, "num_gpu_blocks", None)
            bs = getattr(ec, "block_size", None)
            if nb and bs:
                kv_tokens = int(nb) * int(bs)
                max_conc = round(kv_tokens / MAX_LEN, 2)
        except Exception:
            pass

        sp = SamplingParams(temperature=0.7, max_tokens=128)
        prompts = make_prompts(n)
        warmup = min(5, n)
        llm.generate(prompts[:warmup], sp)  # discarded

        tb0 = time.time()
        outs = llm.generate(prompts, sp)
        t_gen = time.time() - tb0

        out_lens = [len(o.outputs[0].token_ids) for o in outs]
        in_lens = [len(o.prompt_token_ids) for o in outs]
        total_out = sum(out_lens)
        total_in = sum(in_lens)
        metrics.update(
            ok=True,
            load_time_s=round(load_s, 2),
            kv_cache_tokens=kv_tokens,
            max_concurrency=max_conc,
            n=n,
            total_time_s=round(t_gen, 3),
            total_output_tokens=total_out,
            total_input_tokens=total_in,
            tok_s_out=round(total_out / t_gen, 2) if t_gen else None,
            tok_s_tot=round((total_out + total_in) / t_gen, 2) if t_gen else None,
            req_s=round(n / t_gen, 3) if t_gen else None,
            mean_output_len=round(total_out / n, 1) if n else None,
        )
    except Exception as e:  # noqa: BLE001
        metrics["error"] = f"{type(e).__name__}: {str(e)[:500]}"
    print("BENCH_METRICS_JSON=" + json.dumps(metrics))
    return 0 if metrics["ok"] else 1


# ---------------------------------------------------------------------------
# Thermal aggregation from a sampler JSONL over [t_bench_start, t_bench_end].
# ---------------------------------------------------------------------------
def aggregate_thermals(jsonl: Path, t0: float, t1: float) -> dict:
    """Peak VRAM (max over both GPUs), peak temp, mean/peak power in window."""
    vram_peak = temp_peak = pw_peak = 0.0
    pw_sum = 0.0
    pw_n = 0
    try:
        for line in jsonl.read_text().splitlines():
            s = json.loads(line)
            t = s.get("t", -1)
            in_window = t0 <= t <= t1
            for g in s.get("gpus", []):
                if g.get("is_igpu"):
                    continue
                vb = g.get("vram_used_b")
                if vb:
                    vram_peak = max(vram_peak, vb / 1e9)
                tp_ = g.get("temp")
                pw = g.get("power_w")
                if in_window:
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


def run_n(
    model_dir: str,
    model_path: Path,
    tp: int,
    n: int,
    quant: str,
    extra: str,
    out_dir: Path,
) -> dict:
    """Run one N point with thermal sampling. Returns the §7.1 row dict."""
    name = f"{quant}-tp{tp}-n{n}"
    jsonl = out_dir / f"{name}-thermals.jsonl"
    events_json = out_dir / f"{name}-events.json"
    bench_log = out_dir / f"{name}-bench.log"

    subprocess.run([str(KILL_PORT), "8100"], check=False, capture_output=True)

    sampler = subprocess.Popen(
        [sys.executable, str(SAMPLER), str(jsonl), "--interval", "1.0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    t_wall0 = time.time()
    events = []
    metrics = {"ok": False, "error": "not run"}
    try:
        time.sleep(IDLE_BEFORE_S)
        t_bs = time.time() - t_wall0
        events.append(
            {
                "t": round(t_bs, 2),
                "label": f"bench start ({quant} TP={tp} N={n})",
                "color": "#2ca02c",
            }
        )
        env = os.environ.copy()
        env.pop("ROCR_VISIBLE_DEVICES", None)
        cmd = [
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "--child",
            "--model-path",
            str(model_path),
            "--tp",
            str(tp),
            "--n",
            str(n),
            "--extra",
            extra,
        ]
        with open(bench_log, "w") as f:
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
        t_be = time.time() - t_wall0
        events.append({"t": round(t_be, 2), "label": "bench end", "color": "#d62728"})
        # parse child metrics + KV/maxc (log lines) from bench_log
        bench_text = bench_log.read_text()
        for line in bench_text.splitlines():
            if line.startswith("BENCH_METRICS_JSON="):
                metrics = json.loads(line[len("BENCH_METRICS_JSON=") :])
                break
        else:
            metrics = {"ok": False, "error": f"no metrics (rc={rc})"}
        kv_log, maxc_log = parse_kv_maxc(bench_text)
        if kv_log is not None:
            metrics["kv_cache_tokens"] = kv_log
        if maxc_log is not None:
            metrics["max_concurrency"] = maxc_log
        time.sleep(IDLE_AFTER_S)
    finally:
        sampler.send_signal(signal.SIGINT)
        try:
            sampler.wait(timeout=8)
        except subprocess.TimeoutExpired:
            sampler.kill()

    events_json.write_text(json.dumps(events, indent=2))

    # thermal window = [bench start, bench end]
    therm = {}
    if len(events) == 2:
        therm = aggregate_thermals(jsonl, events[0]["t"], events[1]["t"])

    row = {
        "model": model_dir,
        "quant": quant,
        "backend": "vLLM",
        "TP": tp,
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
        "bios_version": BIOS_VERSION,
        "bios_date": BIOS_DATE,
        "agesa_version": AGESA_VERSION,
    }
    # W/tok energy efficiency (§7.1)
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

    subprocess.run([str(KILL_PORT), "8100"], check=False, capture_output=True)
    return row


CSV_COLS = [
    "model",
    "quant",
    "backend",
    "TP",
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
    "bios_version",
    "bios_date",
    "agesa_version",
    "error",
]


def write_summary(
    model_dir: str,
    tp: int,
    quant: str,
    rows: list[dict],
    results_dir: Path,
    wall_s: float,
):
    md = results_dir / "SUMMARY.md"
    csv_path = results_dir / "results_table.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    ok_rows = [r for r in rows if r["ok"]]
    best = max(ok_rows, key=lambda r: r["tok_s_out"] or 0, default=None)
    lines = [
        f"# Phase 2 throughput sweep — {model_dir}",
        "",
        "> **EMBARGO §11.2** — Phase 2 scaling numbers (throughput@N, KV curves,"
        " W/tok) are EMBARGOED until paper acceptance. Polish models carry"
        " stricter embargo §11.3. `benchmarks/results/` is gitignored.",
        "",
        "> Following Lerchner (2026): we measure inference *throughput*,"
        " *latency*, *thermal envelope*, *power efficiency* under concurrent"
        " load. We do not measure model quality, reasoning, or clinical"
        " utility. Claims terminate at the hardware-software interface.",
        "",
        f"- **Model:** `{model_dir}` quant=`{quant}` TP={tp}",
        "- **Workload:** METHODOLOGY §6 synthetic (8 templates × 20 topics,"
        " temp=0.7, max_tokens=128)",
        f"- **Config:** max_model_len={MAX_LEN}, util={UTIL}, enforce_eager=True",
        f"- **Sweep wall time:** {wall_s/60:.1f} min",
        "- **Stack:** vLLM 0.19.0+rocm721, transformers 5.8.1, ROCm 7.2,"
        " 2× R9700 gfx1201",
        f"- **Firmware:** BIOS {BIOS_VERSION} ({BIOS_DATE}), {AGESA_VERSION}",
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
            f"- **Peak output throughput:** {best['tok_s_out']} tok/s at"
            f" N={best['N']}"
        )
    if ok_rows and ok_rows[0].get("max_concurrency"):
        lines.append(
            f"- **Phase 1 max_concurrency (engine est., {MAX_LEN} ctx):**"
            f" {ok_rows[0]['max_concurrency']}× — knee expected near"
            f" N≈{ok_rows[0]['max_concurrency']*MAX_LEN/MAX_LEN:.0f}"
        )
    fails = [r for r in rows if not r["ok"]]
    if fails:
        lines.append("")
        lines.append("## Failures")
        for r in fails:
            lines.append(f"- N={r['N']}: {r['error']}")
    lines += [
        "",
        "## AI disclosure (METHODOLOGY §9)",
        "",
        "Layer 2 (experimental pipeline): sweep orchestrated by Claude Code"
        " (Anthropic, Opus 4.7) as an idle-GPU subagent, 2026-05-20. Harness"
        " `throughput_sweep_v0.3.py` reuses navimed METHODOLOGY §5.2/§6/§7."
        " No AI involvement in data generation (synthetic prompts are"
        " deterministic, §6). Layer 1: not applicable.",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()}_",
    ]
    md.write_text("\n".join(lines))
    return csv_path, md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir", nargs="?")
    ap.add_argument("tp", nargs="?", type=int)
    ap.add_argument("--quant", default="auto")
    ap.add_argument("--extra", default="")
    ap.add_argument("--ns", default=None, help="comma list, default 10,25,50,100,200")
    # child mode
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--model-path")
    ap.add_argument("--tp", dest="tp_opt", type=int, help="child-mode TP")
    ap.add_argument("--n", type=int)
    args = ap.parse_args()

    if args.child:
        return run_child(args.model_path, args.tp_opt, args.n, args.extra)

    if not args.model_dir or args.tp is None:
        ap.error("model_dir and tp required")

    model_path = MODELS_DIR / args.model_dir
    if not (model_path / "config.json").exists():
        print(f"ERROR: {model_path}/config.json missing", file=sys.stderr)
        return 1

    ns = [int(x) for x in args.ns.split(",")] if args.ns else DEFAULT_NS
    results_dir = RESULTS_DIR / args.model_dir
    out_dir = results_dir / "thermal-runs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[sweep] {args.model_dir} TP={args.tp} quant={args.quant} N={ns}")
    t_start = time.time()
    rows = []
    for n in ns:
        print(f"[sweep]   N={n} ...", flush=True)
        tr0 = time.time()
        row = run_n(
            args.model_dir, model_path, args.tp, n, args.quant, args.extra, out_dir
        )
        rows.append(row)
        dt = time.time() - tr0
        if row["ok"]:
            print(
                f"[sweep]   N={n} -> {row['tok_s_out']} tok/s_out, "
                f"{row['req_s']} req/s, VRAM {row['vram_peak_gb']}GB, "
                f"T {row['temp_peak_c']}C ({dt:.0f}s)"
            )
        else:
            print(f"[sweep]   N={n} -> FAIL: {row['error']} ({dt:.0f}s)")
        if n != ns[-1]:
            time.sleep(COOLDOWN_S)

    wall = time.time() - t_start
    csv_path, md = write_summary(
        args.model_dir, args.tp, args.quant, rows, results_dir, wall
    )
    print(f"[sweep] {args.model_dir} done — wall {wall/60:.1f} min")
    print(f"[sweep] CSV: {csv_path}")
    print(f"[sweep] SUMMARY: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
