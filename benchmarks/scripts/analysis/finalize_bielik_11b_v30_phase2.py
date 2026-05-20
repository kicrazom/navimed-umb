"""
NaviMed-UMB Phase 2 finalize — Bielik 11B v3.0 BF16 TP={1,2} max_len=8192,
n=10 reps per cell.

Sibling of finalize_bielik_phase2.py (which is v2.3 TP=2 single-rep). This
script:
  - Reads benchmarks/results/bielik-11b-v30/thermal-runs/{quant}-tp{TP}-n{N}-r{REP}-*
  - Aggregates n=10 reps per (TP, N) cell → median + p95 + p99 + min/max
  - Emits:
      - phase2_sweep.csv          (per-cell aggregates, METHODOLOGY §7.1 + n_runs)
      - phase2_sweep_tp1.csv      (TP=1 only)
      - phase2_sweep_tp2.csv      (TP=2 only)
      - phase2_sweep_raw.csv      (per-rep, all rows)
      - scaling_curve.png         (throughput vs N, both TPs)
      - latency_p99.png           (p99 wall time / req vs N)
      - thermal_gallery.png       (per-cell temp/power traces, both TPs)
      - power_efficiency.png      (tok/s/W vs N, both TPs)
      - SUMMARY.md                (METHODOLOGY §7.3 narrative + embargo split)
      - methodology_compliance.json (Kim et al. 2026 disclosure +
                                     Lerchner 2026 humility)

Embargo: SCRIPT itself is PUBLIC, OUTPUTS are EMBARGO_paper_bound (§11.3).
Per-file EMBARGO=YES header is written into CSV/MD outputs.

Author: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ============================================================
# Paths and constants
# ============================================================

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_DIR = REPO_ROOT / "benchmarks/results/bielik-11b-v30"
THERMAL_DIR = RESULTS_DIR / "thermal-runs"

MODEL_NAME = "speakleash/Bielik-11B-v3.0-Instruct"
MODEL_LABEL = "bielik-11b-v30"
QUANT = "BF16"
BACKEND = "vllm-0.19.0+rocm721"
MAX_LEN = 8192
UTIL = 0.90
KV_DTYPE = "auto"
TUNING = "stock"
N_LADDER = [5, 10, 25, 50, 100, 250]
TP_LADDER = [1, 2]
REPS_EXPECTED = 10

EMBARGO_HEADER = (
    "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.3)\n"
    "# DO NOT COMMIT until paper acceptance.\n"
)

RE_RUN = re.compile(
    r"^(?P<quant>[a-z0-9]+)-tp(?P<tp>\d+)-n(?P<n>\d+)-r(?P<rep>\d+)-bench\.log$"
)

# ============================================================
# Per-rep record (raw)
# ============================================================


@dataclass
class RepRecord:
    tp: int
    n: int
    rep: int
    load_time_s: Optional[float] = None
    total_s: Optional[float] = None
    tok_s_out: Optional[float] = None
    tok_s_tot: Optional[float] = None
    req_s: Optional[float] = None
    total_out_tokens: Optional[int] = None
    total_in_tokens: Optional[int] = None
    mean_output_len: Optional[float] = None
    vram_peak_gib: Optional[float] = None
    t_peak_c: Optional[float] = None
    w_mean: Optional[float] = None
    w_peak: Optional[float] = None
    w_per_tok_wh: Optional[float] = None
    ok: bool = False


# ============================================================
# Per-cell aggregate (median + p95 + p99)
# ============================================================


@dataclass
class CellAggregate:
    tp: int
    n: int
    n_runs_ok: int = 0
    n_runs_fail: int = 0
    # Throughput aggregates
    tok_s_out_median: Optional[float] = None
    tok_s_out_min: Optional[float] = None
    tok_s_out_max: Optional[float] = None
    tok_s_tot_median: Optional[float] = None
    # Latency aggregates (total wall time per request as proxy)
    total_s_median: Optional[float] = None
    total_s_p95: Optional[float] = None
    total_s_p99: Optional[float] = None
    req_s_median: Optional[float] = None
    # Per-request latency proxy: total_s / n
    per_req_latency_median: Optional[float] = None
    per_req_latency_p95: Optional[float] = None
    per_req_latency_p99: Optional[float] = None
    # Thermal aggregates
    vram_peak_gib_median: Optional[float] = None
    t_peak_c_median: Optional[float] = None
    t_peak_c_max: Optional[float] = None
    w_mean_median: Optional[float] = None
    w_peak_max: Optional[float] = None
    # Energy
    w_per_tok_wh_median: Optional[float] = None
    # Tokens
    output_tok_total_median: Optional[float] = None
    load_time_s_median: Optional[float] = None
    # Raw reps for downstream stats
    reps: list[RepRecord] = field(default_factory=list)


# ============================================================
# Parsing
# ============================================================


BENCH_PATTERNS = {
    "load_time_s": r"Load time:\s+([\d.]+)s",
    "total_s": r"Total time:\s+([\d.]+)s",
    "total_out_tokens": r"Total output tokens:\s+(\d+)",
    "total_in_tokens": r"Total input tokens:\s+(\d+)",
    "tok_s_out": r"Output throughput:\s+([\d.]+)\s+tok/s",
    "tok_s_tot": r"Total throughput:\s+([\d.]+)\s+tok/s",
    "req_s": r"Requests/second:\s+([\d.]+)",
    "mean_output_len": r"Mean output len:\s+([\d.]+)",
}


def parse_bench_log(path: Path) -> dict:
    data: dict = {}
    if not path.exists():
        return data
    text = path.read_text(errors="ignore")
    for key, pat in BENCH_PATTERNS.items():
        m = re.search(pat, text)
        if m:
            val_str = m.group(1)
            data[key] = int(val_str) if "tokens" in key else float(val_str)
    return data


def parse_thermals_window(jsonl_path: Path, events_path: Path) -> dict:
    if not jsonl_path.exists() or not events_path.exists():
        return {}

    try:
        events = json.loads(events_path.read_text())
    except json.JSONDecodeError:
        return {}

    t_start = next((e["t"] for e in events if "bench start" in e["label"]), None)
    t_end = next((e["t"] for e in events if "bench end" in e["label"]), None)
    if t_start is None or t_end is None:
        return {}

    samples = []
    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    win = [s for s in samples if t_start <= s.get("t", -1) <= t_end]
    if not win:
        return {}

    vram_max = 0.0
    t_max = 0.0
    w_samples_total = []

    for s in win:
        gpus = s.get("gpus", []) or []
        if not gpus:
            continue
        sum_w = 0.0
        for g in gpus:
            if g.get("is_igpu"):
                continue
            vram_b = g.get("vram_used_b") or 0
            vram_gib = vram_b / (1024**3)
            if vram_gib > vram_max:
                vram_max = vram_gib
            tc = g.get("temp") or 0.0
            if tc > t_max:
                t_max = tc
            pw = g.get("power_w") or 0.0
            sum_w += pw
        if sum_w > 0:
            w_samples_total.append(sum_w)

    return {
        "vram_peak_gib": round(vram_max, 3) if vram_max > 0 else None,
        "t_peak_c": round(t_max, 1) if t_max > 0 else None,
        "w_mean": round(statistics.mean(w_samples_total), 1)
        if w_samples_total
        else None,
        "w_peak": round(max(w_samples_total), 1) if w_samples_total else None,
    }


def build_reps() -> list[RepRecord]:
    reps: list[RepRecord] = []
    if not THERMAL_DIR.exists():
        return reps

    for log_path in sorted(THERMAL_DIR.glob("*-bench.log")):
        m = RE_RUN.match(log_path.name)
        if not m:
            continue
        tp = int(m.group("tp"))
        n = int(m.group("n"))
        rep_idx = int(m.group("rep"))

        rec = RepRecord(tp=tp, n=n, rep=rep_idx)
        bench_data = parse_bench_log(log_path)
        for k, v in bench_data.items():
            setattr(rec, k, v)

        base = log_path.name.removesuffix("-bench.log")
        events_p = THERMAL_DIR / f"{base}-events.json"
        thermals_p = THERMAL_DIR / f"{base}-thermals.jsonl"
        therm = parse_thermals_window(thermals_p, events_p)
        for k, v in therm.items():
            setattr(rec, k, v)

        # Energy per token (Wh)
        if rec.w_mean and rec.total_s and rec.total_out_tokens:
            energy_wh = rec.w_mean * rec.total_s / 3600.0
            rec.w_per_tok_wh = round(energy_wh / rec.total_out_tokens, 6)

        rec.ok = rec.tok_s_out is not None and rec.total_s is not None
        reps.append(rec)

    return reps


# ============================================================
# Aggregation
# ============================================================


def _pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    s = sorted(xs)
    # Nearest-rank percentile (suitable for small n=10 samples; documented in SUMMARY)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def aggregate_cells(reps: list[RepRecord]) -> list[CellAggregate]:
    cells: dict[tuple[int, int], CellAggregate] = {}
    for r in reps:
        key = (r.tp, r.n)
        c = cells.setdefault(key, CellAggregate(tp=r.tp, n=r.n))
        c.reps.append(r)
        if r.ok:
            c.n_runs_ok += 1
        else:
            c.n_runs_fail += 1

    for c in cells.values():
        ok_reps = [r for r in c.reps if r.ok]
        if not ok_reps:
            continue

        tok_s_out = [r.tok_s_out for r in ok_reps if r.tok_s_out is not None]
        tok_s_tot = [r.tok_s_tot for r in ok_reps if r.tok_s_tot is not None]
        total_s = [r.total_s for r in ok_reps if r.total_s is not None]
        req_s = [r.req_s for r in ok_reps if r.req_s is not None]
        per_req_lat = [r.total_s / r.n for r in ok_reps if r.total_s]
        vram = [r.vram_peak_gib for r in ok_reps if r.vram_peak_gib is not None]
        temps = [r.t_peak_c for r in ok_reps if r.t_peak_c is not None]
        w_mean = [r.w_mean for r in ok_reps if r.w_mean is not None]
        w_peak = [r.w_peak for r in ok_reps if r.w_peak is not None]
        w_per_tok = [r.w_per_tok_wh for r in ok_reps if r.w_per_tok_wh is not None]
        out_toks = [
            r.total_out_tokens for r in ok_reps if r.total_out_tokens is not None
        ]
        load_t = [r.load_time_s for r in ok_reps if r.load_time_s is not None]

        c.tok_s_out_median = statistics.median(tok_s_out) if tok_s_out else None
        c.tok_s_out_min = min(tok_s_out) if tok_s_out else None
        c.tok_s_out_max = max(tok_s_out) if tok_s_out else None
        c.tok_s_tot_median = statistics.median(tok_s_tot) if tok_s_tot else None
        c.total_s_median = statistics.median(total_s) if total_s else None
        c.total_s_p95 = _pct(total_s, 95.0)
        c.total_s_p99 = _pct(total_s, 99.0)
        c.req_s_median = statistics.median(req_s) if req_s else None
        c.per_req_latency_median = (
            statistics.median(per_req_lat) if per_req_lat else None
        )
        c.per_req_latency_p95 = _pct(per_req_lat, 95.0)
        c.per_req_latency_p99 = _pct(per_req_lat, 99.0)
        c.vram_peak_gib_median = statistics.median(vram) if vram else None
        c.t_peak_c_median = statistics.median(temps) if temps else None
        c.t_peak_c_max = max(temps) if temps else None
        c.w_mean_median = statistics.median(w_mean) if w_mean else None
        c.w_peak_max = max(w_peak) if w_peak else None
        c.w_per_tok_wh_median = statistics.median(w_per_tok) if w_per_tok else None
        c.output_tok_total_median = statistics.median(out_toks) if out_toks else None
        c.load_time_s_median = statistics.median(load_t) if load_t else None

    return sorted(cells.values(), key=lambda c: (c.tp, c.n))


# ============================================================
# CSV emission
# ============================================================


CELL_CSV_COLUMNS = [
    "model",
    "quant",
    "backend",
    "TP",
    "max_len",
    "util",
    "KV_dtype",
    "N",
    "n_runs_ok",
    "n_runs_fail",
    "tok_s_out_median",
    "tok_s_out_min",
    "tok_s_out_max",
    "tok_s_tot_median",
    "total_s_median",
    "total_s_p95",
    "total_s_p99",
    "req_s_median",
    "per_req_latency_median",
    "per_req_latency_p95",
    "per_req_latency_p99",
    "VRAM_peak_GB_median",
    "T_peak_C_median",
    "T_peak_C_max",
    "W_mean_median",
    "W_peak_max",
    "W_per_tok_Wh_median",
    "output_tok_total_median",
    "load_time_s_median",
    "tuning",
]


def _fmt(v, d=2) -> str:
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def _emit_cell_csv(cells: list[CellAggregate], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        f.write(EMBARGO_HEADER)
        w = csv.writer(f)
        w.writerow(CELL_CSV_COLUMNS)
        for c in cells:
            w.writerow(
                [
                    MODEL_LABEL,
                    QUANT,
                    BACKEND,
                    c.tp,
                    MAX_LEN,
                    UTIL,
                    KV_DTYPE,
                    c.n,
                    c.n_runs_ok,
                    c.n_runs_fail,
                    _fmt(c.tok_s_out_median, 2),
                    _fmt(c.tok_s_out_min, 2),
                    _fmt(c.tok_s_out_max, 2),
                    _fmt(c.tok_s_tot_median, 2),
                    _fmt(c.total_s_median, 3),
                    _fmt(c.total_s_p95, 3),
                    _fmt(c.total_s_p99, 3),
                    _fmt(c.req_s_median, 3),
                    _fmt(c.per_req_latency_median, 4),
                    _fmt(c.per_req_latency_p95, 4),
                    _fmt(c.per_req_latency_p99, 4),
                    _fmt(c.vram_peak_gib_median, 2),
                    _fmt(c.t_peak_c_median, 1),
                    _fmt(c.t_peak_c_max, 1),
                    _fmt(c.w_mean_median, 1),
                    _fmt(c.w_peak_max, 1),
                    _fmt(c.w_per_tok_wh_median, 6),
                    _fmt(c.output_tok_total_median, 0),
                    _fmt(c.load_time_s_median, 1),
                    TUNING,
                ]
            )
    print(f"  CSV → {path.relative_to(REPO_ROOT)}")


def emit_csvs(cells: list[CellAggregate], reps: list[RepRecord]) -> None:
    _emit_cell_csv(cells, RESULTS_DIR / "phase2_sweep.csv")
    _emit_cell_csv(
        [c for c in cells if c.tp == 1], RESULTS_DIR / "phase2_sweep_tp1.csv"
    )
    _emit_cell_csv(
        [c for c in cells if c.tp == 2], RESULTS_DIR / "phase2_sweep_tp2.csv"
    )

    # Raw per-rep CSV
    raw_path = RESULTS_DIR / "phase2_sweep_raw.csv"
    with raw_path.open("w", newline="") as f:
        f.write(EMBARGO_HEADER)
        w = csv.writer(f)
        w.writerow(
            [
                "TP",
                "N",
                "rep",
                "ok",
                "load_time_s",
                "total_s",
                "tok_s_out",
                "tok_s_tot",
                "req_s",
                "total_out_tokens",
                "total_in_tokens",
                "mean_output_len",
                "VRAM_peak_GB",
                "T_peak_C",
                "W_mean",
                "W_peak",
                "W_per_tok_Wh",
            ]
        )
        for r in sorted(reps, key=lambda x: (x.tp, x.n, x.rep)):
            w.writerow(
                [
                    r.tp,
                    r.n,
                    r.rep,
                    int(r.ok),
                    _fmt(r.load_time_s, 2),
                    _fmt(r.total_s, 3),
                    _fmt(r.tok_s_out, 2),
                    _fmt(r.tok_s_tot, 2),
                    _fmt(r.req_s, 3),
                    _fmt(r.total_out_tokens, 0),
                    _fmt(r.total_in_tokens, 0),
                    _fmt(r.mean_output_len, 1),
                    _fmt(r.vram_peak_gib, 2),
                    _fmt(r.t_peak_c, 1),
                    _fmt(r.w_mean, 1),
                    _fmt(r.w_peak, 1),
                    _fmt(r.w_per_tok_wh, 6),
                ]
            )
    print(f"  CSV → {raw_path.relative_to(REPO_ROOT)}")


# ============================================================
# Plots
# ============================================================


def _by_tp(cells: list[CellAggregate]) -> dict[int, list[CellAggregate]]:
    out: dict[int, list[CellAggregate]] = {}
    for c in cells:
        out.setdefault(c.tp, []).append(c)
    for tp in out:
        out[tp].sort(key=lambda c: c.n)
    return out


def plot_scaling(cells: list[CellAggregate], path: Path) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    markers = {1: "o", 2: "s"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs = [c.n for c in tp_cells if c.tok_s_out_median is not None]
        ys = [c.tok_s_out_median for c in tp_cells if c.tok_s_out_median is not None]
        ymin = [c.tok_s_out_min for c in tp_cells if c.tok_s_out_min is not None]
        ymax = [c.tok_s_out_max for c in tp_cells if c.tok_s_out_max is not None]
        if not xs:
            continue
        ax.plot(
            xs,
            ys,
            marker=markers.get(tp, "x"),
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp} (median, n_reps={REPS_EXPECTED})",
        )
        if len(ymin) == len(xs):
            ax.fill_between(xs, ymin, ymax, color=colors.get(tp, "black"), alpha=0.15)

    ax.set_xscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Output throughput (tok/s, median across reps)")
    ax.set_title(
        "Bielik 11B v3.0 BF16 — Phase 2 scaling (TP=1 vs TP=2, 2× R9700 gfx1201)"
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {path.relative_to(REPO_ROOT)}")


def plot_latency_p99(cells: list[CellAggregate], path: Path) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs = [c.n for c in tp_cells if c.per_req_latency_p99 is not None]
        ys99 = [
            c.per_req_latency_p99 for c in tp_cells if c.per_req_latency_p99 is not None
        ]
        ys50 = [
            c.per_req_latency_median
            for c in tp_cells
            if c.per_req_latency_p99 is not None
        ]
        if not xs:
            continue
        ax.plot(
            xs,
            ys99,
            marker="o",
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp} p99",
        )
        ax.plot(
            xs,
            ys50,
            marker="o",
            linewidth=1,
            linestyle="--",
            color=colors.get(tp, "black"),
            alpha=0.6,
            label=f"TP={tp} median",
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Per-request wall time proxy (s) — total_s / N")
    ax.set_title("Bielik 11B v3.0 BF16 — Tail latency (median + p99 across reps)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {path.relative_to(REPO_ROOT)}")


def plot_power_efficiency(cells: list[CellAggregate], path: Path) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs, ys = [], []
        for c in tp_cells:
            if c.tok_s_out_median and c.w_mean_median:
                xs.append(c.n)
                ys.append(c.tok_s_out_median / c.w_mean_median)
        if not xs:
            continue
        ax.plot(
            xs,
            ys,
            marker="^",
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp}",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Aggregate efficiency (tok/s per W)")
    ax.set_title("Bielik 11B v3.0 BF16 — Power efficiency (tok/s/W, median)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {path.relative_to(REPO_ROOT)}")


def plot_thermal_gallery(cells: list[CellAggregate], path: Path) -> None:
    by_tp = _by_tp(cells)
    n_rows = max(len(by_tp.get(tp, [])) for tp in TP_LADDER)
    n_cols = len(TP_LADDER)
    if n_rows == 0:
        return

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(6 * n_cols, 1.8 * n_rows), sharex=False, squeeze=False
    )

    for col, tp in enumerate(TP_LADDER):
        tp_cells = by_tp.get(tp, [])
        for row, c in enumerate(tp_cells):
            ax = axes[row][col]
            # Use first OK rep for the trace (the median run is harder to ID
            # without re-scanning; the gallery shows representative shape).
            ok_reps = [r for r in c.reps if r.ok]
            if not ok_reps:
                ax.set_title(f"TP={tp} N={c.n} (no data)")
                continue
            r0 = ok_reps[0]
            base = f"bf16-tp{tp}-n{c.n}-r{r0.rep:02d}"
            jp = THERMAL_DIR / f"{base}-thermals.jsonl"
            if not jp.exists():
                ax.set_title(f"TP={tp} N={c.n} (no thermals file)")
                continue
            rows_t = []
            for line in jp.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows_t.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if not rows_t:
                ax.set_title(f"TP={tp} N={c.n} (empty thermals)")
                continue
            ts = [r["t"] for r in rows_t]
            non_igpu_idx = [
                i
                for i, g in enumerate(rows_t[0].get("gpus", []) or [])
                if not g.get("is_igpu")
            ]
            colors_g = ["#1f77b4", "#ff7f0e"]
            for k, list_idx in enumerate(non_igpu_idx[:2]):
                temps = [
                    (
                        r["gpus"][list_idx]["temp"]
                        if len(r.get("gpus", [])) > list_idx
                        else None
                    )
                    for r in rows_t
                ]
                ax.plot(
                    ts,
                    temps,
                    color=colors_g[k % len(colors_g)],
                    linewidth=1.2,
                    label=f"GPU{k} T",
                )
            ax.set_ylabel("Temp °C", fontsize=8)
            ax.grid(True, alpha=0.3)

            ax2 = ax.twinx()
            for k, list_idx in enumerate(non_igpu_idx[:2]):
                powers = [
                    (
                        r["gpus"][list_idx]["power_w"]
                        if len(r.get("gpus", [])) > list_idx
                        else None
                    )
                    for r in rows_t
                ]
                ax2.plot(
                    ts,
                    powers,
                    color=colors_g[k % len(colors_g)],
                    linewidth=1.0,
                    linestyle="--",
                    alpha=0.7,
                )
            ax2.set_ylabel("W", fontsize=8)
            ax.set_title(f"TP={tp} N={c.n}", loc="left", fontsize=9)

        # Hide unused subplots
        for row in range(len(tp_cells), n_rows):
            axes[row][col].set_visible(False)

    fig.suptitle(
        "Bielik 11B v3.0 BF16 — Thermal gallery (first OK rep per cell)",
        fontsize=11,
        y=1.0,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  PNG → {path.relative_to(REPO_ROOT)}")


# ============================================================
# SUMMARY.md
# ============================================================


def _detect_knee(tp_cells: list[CellAggregate]) -> Optional[int]:
    """Return N at which efficiency drops below 50% of N-doubled extrapolation."""
    ok = [c for c in tp_cells if c.tok_s_out_median is not None]
    if len(ok) < 2:
        return None
    for i in range(1, len(ok)):
        n_ratio = ok[i].n / ok[i - 1].n
        tp_ratio = ok[i].tok_s_out_median / ok[i - 1].tok_s_out_median
        if (tp_ratio / n_ratio) < 0.5:
            return ok[i - 1].n
    return None


def _detect_crossover(cells: list[CellAggregate]) -> Optional[int]:
    by_tp = _by_tp(cells)
    if 1 not in by_tp or 2 not in by_tp:
        return None
    by_n_tp1 = {c.n: c.tok_s_out_median for c in by_tp[1] if c.tok_s_out_median}
    by_n_tp2 = {c.n: c.tok_s_out_median for c in by_tp[2] if c.tok_s_out_median}
    common = sorted(set(by_n_tp1) & set(by_n_tp2))
    for n in common:
        if by_n_tp2[n] > by_n_tp1[n]:
            return n
    return None


def emit_summary(cells: list[CellAggregate], reps: list[RepRecord]) -> None:
    by_tp = _by_tp(cells)
    knees = {tp: _detect_knee(by_tp.get(tp, [])) for tp in TP_LADDER}
    crossover = _detect_crossover(cells)

    # Max thermal observation across all reps
    all_temps = [r.t_peak_c for r in reps if r.t_peak_c is not None]
    max_temp = max(all_temps) if all_temps else None
    throttle_events = sum(1 for t in all_temps if t > 95.0)

    # Power envelope
    all_w_peak = [r.w_peak for r in reps if r.w_peak is not None]
    all_w_mean = [r.w_mean for r in reps if r.w_mean is not None]
    avg_w = statistics.mean(all_w_mean) if all_w_mean else None
    peak_w = max(all_w_peak) if all_w_peak else None

    # Best tok/s/W per TP
    best_eff = {}
    for tp, tp_cells in by_tp.items():
        eff_pairs = [
            (c.n, c.tok_s_out_median / c.w_mean_median)
            for c in tp_cells
            if c.tok_s_out_median and c.w_mean_median
        ]
        if eff_pairs:
            best = max(eff_pairs, key=lambda x: x[1])
            best_eff[tp] = best

    # Build per-TP markdown tables
    def _fmt_table(tp_cells: list[CellAggregate]) -> str:
        if not tp_cells:
            return "_no data_"
        header = (
            "| N | n_ok | tok/s out (median) | min | max | "
            "total_s (median) | p95 | p99 | "
            "req/s | per_req_s p99 | "
            "VRAM_GB | T_peak | W_mean | W_peak | mWh/tok |"
        )
        sep = "|" + "|".join(["---"] * 15) + "|"
        rows = []
        for c in tp_cells:
            mwh = (
                f"{c.w_per_tok_wh_median * 1000:.3f}"
                if c.w_per_tok_wh_median is not None
                else "n/a"
            )
            rows.append(
                f"| {c.n} | {c.n_runs_ok} | "
                f"{_fmt(c.tok_s_out_median, 1)} | "
                f"{_fmt(c.tok_s_out_min, 1)} | "
                f"{_fmt(c.tok_s_out_max, 1)} | "
                f"{_fmt(c.total_s_median, 2)} | "
                f"{_fmt(c.total_s_p95, 2)} | "
                f"{_fmt(c.total_s_p99, 2)} | "
                f"{_fmt(c.req_s_median, 3)} | "
                f"{_fmt(c.per_req_latency_p99, 3)} | "
                f"{_fmt(c.vram_peak_gib_median, 1)} | "
                f"{_fmt(c.t_peak_c_max, 1)} | "
                f"{_fmt(c.w_mean_median, 0)} | "
                f"{_fmt(c.w_peak_max, 0)} | "
                f"{mwh} |"
            )
        return "\n".join([header, sep, *rows])

    knee_text_tp1 = (
        f"Knee at N={knees[1]}"
        if knees.get(1)
        else "No clear knee within tested range — scales sub-linearly throughout"
    )
    knee_text_tp2 = (
        f"Knee at N={knees[2]}"
        if knees.get(2)
        else "No clear knee within tested range — scales sub-linearly throughout"
    )
    crossover_text = (
        f"TP=2 first exceeds TP=1 throughput at N={crossover}"
        if crossover
        else "TP=2 did not exceed TP=1 throughput at any tested N "
        "(possible: crossover occurs outside the tested range, "
        "or TP=2 AllReduce overhead dominates throughout)"
    )

    best_eff_text = "\n".join(
        f"  - TP={tp}: best at N={n}, {eff:.3f} tok/s per W"
        for tp, (n, eff) in sorted(best_eff.items())
    )

    md = f"""{EMBARGO_HEADER.rstrip()}

# Bielik 11B v3.0 BF16 — Phase 2 sweep summary

**Sweep ID:** `bielik-11b-v30-bf16-tp{{1,2}}-max8192-n{{5,10,25,50,100,250}}-r10`
**Date:** {Path(RESULTS_DIR / "logs/orchestrator.log").stat().st_mtime if (RESULTS_DIR / "logs/orchestrator.log").exists() else "(in-progress)"}
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** METHODOLOGY.md v1.0 §5.2 (Phase 2 scaling sweep)
**Embargo:** Mixed per §11.1/§11.2/§11.3 — see classification below.

## ⚠ Embargo classification (METHODOLOGY §11.4)

**EMBARGO_paper_bound** for all concrete throughput, latency, thermal, and
power numbers (Polish model, stricter embargo per §11.3). Engineering
observations (knee shape, vLLM scheduler robustness, preemption regime onset,
TP=1 vs TP=2 trade-off, thermal headroom) are PUBLIC.

## N-ladder deviation from METHODOLOGY §5.2 (transparency note)

The canonical Phase 2 ladder is N ∈ {{10, 25, 50, 100, 200, 500, 1000}}.
This sweep used N ∈ {{5, 10, 25, 50, 100, 250}} to fit the overnight wall
time budget while maintaining n_reps=10 per cell (median + p95/p99 stats).
The lower-bound point (N=5) extends below the canonical floor to probe
sub-`max_concurrency` linear regime for TP=2 (max_concurrency 22.46×).
The upper-bound point (N=250) is ~11× max_concurrency for TP=2 and ~55×
for TP=1, covering deep preemption regime. Cross-suite comparability with
Qwen 7B/27B/72B aggregate plots will require re-running at the canonical
ladder before paper synthesis — flagged as paper TODO.

## Methodological humility (METHODOLOGY §8, Lerchner 2026)

We measure inference *throughput*, *latency*, *thermal envelope*, and *power
efficiency* under varying concurrent load. We do not measure model quality,
reasoning capability, factual accuracy, or downstream clinical utility.
Following Lerchner (2026), these are extrinsic computational properties of
the inference vehicle, not constitutive properties of cognition. Our claims
terminate at the hardware-software interface.

## Configuration

- Model: `{MODEL_NAME}` (Polish-language, Mistral-based, 11B params)
- Local path: `/home/mozarcik/models/bielik-11b-v30`
- Quantization: {QUANT}
- Backend: {BACKEND}
- Tensor parallel sizes: {TP_LADDER}
- max_model_len: {MAX_LEN}
- gpu_memory_utilization: {UTIL}
- KV cache dtype: {KV_DTYPE}
- enforce_eager: True (graphs path segfaults on gfx1201; per METHODOLOGY §3.2)
- N ladder: {N_LADDER}
- Reps per cell: {REPS_EXPECTED} (median + p95/p99 statistics)
- Cooldown between runs: 30s

## Phase 1 envelope rationale (PUBLIC, METHODOLOGY §5.1)

Reference: `environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp{{1,2}}-bf16.json`

| Metric | TP=1 | TP=2 | Ratio |
|---|---|---|---|
| VRAM per GPU | 28.88 GiB | 31.06 GiB (×2) | 2.15× total |
| Model footprint per worker | 20.9 GiB | 10.46 GiB | 0.50× |
| KV cache per worker | 7.17 GiB | 17.55 GiB | 2.45× |
| KV cache tokens | 37,584 | 183,968 | 4.90× |
| `max_concurrency` | 4.59× | 22.46× | 4.89× |
| Single-stream gen tok/s | 12.8 | 7.3 | 0.57× |

Engineering observation (PUBLIC): TP=2 trades 43% single-stream throughput
for 4.9× concurrent-request capacity. Phase 2 quantifies where the crossover
occurs in aggregate throughput.

## Results — TP=1 (EMBARGO_paper_bound — Polish model, §11.3)

{_fmt_table(by_tp.get(1, []))}

## Results — TP=2 (EMBARGO_paper_bound — Polish model, §11.3)

{_fmt_table(by_tp.get(2, []))}

## Engineering observations (PUBLIC)

- **TP=1 scaling regime:** {knee_text_tp1}.
- **TP=2 scaling regime:** {knee_text_tp2}.
- **TP=1 vs TP=2 crossover:** {crossover_text}.
- **Thermal envelope:** peak GPU temperature across all {len(reps)} runs was
  {f'{max_temp:.1f}°C' if max_temp else 'n/a'}. Throttle events
  (>95°C): {throttle_events}.
- **Power envelope:** mean {f'{avg_w:.0f} W' if avg_w else 'n/a'} across run windows,
  peak {f'{peak_w:.0f} W' if peak_w else 'n/a'}. 1650 W PSU headroom comfortable for 2× R9700.
- **Best efficiency (tok/s per W) operating points:**
{best_eff_text or "  - (no efficiency data)"}

## Statistical methodology

- Per-cell aggregates use **median** across {REPS_EXPECTED} reps (robust to
  outliers from one-shot vLLM cold-start variance).
- p95 / p99 computed by **nearest-rank percentile** on n={REPS_EXPECTED}
  samples (suitable for small n; p99 ≈ max). For paper-grade tail latency
  characterization, per-request timestamps from vLLM AsyncEngine logging
  will be required (future enhancement, flagged in §10).
- No formal statistical test (Holm-Bonferroni) is applied at this stage —
  the small n_reps=10 per cell is intended for **point estimate stability**,
  not for inferential tests across N. Cross-N or cross-TP significance
  testing belongs to the paper-grade analysis with larger n_reps or
  bootstrap CIs.
- `per_req_latency` is computed as `total_s / N` (i.e. aggregate wall time
  divided by request count) as a **proxy** for per-request latency. True
  per-request P50/P95/P99 requires AsyncEngine timestamp extraction.

## Plots

- `scaling_curve.png` — `tok/s_out_median` vs `N` (log-x), both TPs with
  min/max ribbon
- `latency_p99.png` — per-request wall time proxy, median + p99, both TPs
- `power_efficiency.png` — `tok/s_median / W_mean_median` vs `N`, both TPs
- `thermal_gallery.png` — per-cell temperature + power traces (first OK rep
  per cell), TP=1 left column, TP=2 right column

## Files

- `phase2_sweep.csv` — per-cell aggregates, all TPs
- `phase2_sweep_tp1.csv` — TP=1 cells only
- `phase2_sweep_tp2.csv` — TP=2 cells only
- `phase2_sweep_raw.csv` — per-rep raw data (n={REPS_EXPECTED} × N × TP)
- `logs/orchestrator.log` — orchestrator wall log
- `thermal-runs/` — per-run bench.log, events.json, thermals.jsonl, thermals.png
- `methodology_compliance.json` — Kim et al. 2026 AI disclosure + Lerchner 2026 humility

## Limitations (METHODOLOGY §10)

All ten standing limitations from METHODOLOGY §10 apply. Specific emphases:
- §10.1 synthetic prompts (apples-to-apples cross-model, not clinical)
- §10.5 single-batch concurrency (not Poisson arrival)
- §10.6 1 Hz power sampling (sub-second transients lost)
- §10.10 Polish-language model lacks public R9700 baseline — comparisons
  are within-model only

## AI usage disclosure (METHODOLOGY §9, Kim et al. 2026)

| Layer | Disclosure |
|---|---|
| 1 — Dataset / data generation | N/A. Synthetic prompts per §6, deterministic from human-curated templates × topics, byte-for-byte identical to other model sweeps. |
| 2 — Experimental pipeline | Claude Opus 4.7 (Anthropic, via Claude Code) used 2026-05-17 (overnight) as Phase 2 sweep sub-orchestrator. Specific role: orchestrator + finalize script generation following METHODOLOGY.md §5.2/§7. All decision criteria (N ladder, n_reps, statistical aggregation method) pre-specified in task brief before sweep launch. No autonomous decisions on experimental design. |
| 3 — Manuscript editing | TBD per paper submission. |

## Reproducibility (METHODOLOGY §3.3)

- ROCm 7.2.0 (rocm-smi 4.0.0+fc0010cf6a, ROCM-SMI-LIB 7.8.0)
- vLLM 0.19.0+rocm721 (pinned)
- PyTorch 2.10.0+git8514f05 (HIP 7.2.53211)
- Env (per `scripts/_env.sh`): `AMD_SERIALIZE_KERNEL=1`,
  `ROCR_VISIBLE_DEVICES=0,1`, `VLLM_ROCM_USE_AITER=0`,
  `HIP_LAUNCH_BLOCKING=1`, `PYTORCH_ALLOC_CONF=unset`
- Hardware: 2× AMD Radeon AI PRO R9700 (gfx1201, 32 GiB each), 1650 W PSU
- iGPU (RAPHAEL) excluded from sampling per METHODOLOGY §2

## Next steps (paper-bound, EMBARGOED)

1. Re-run at canonical METHODOLOGY ladder N ∈ {{10, 25, 50, 100, 200, 500, 1000}}
   for cross-model paper figures
2. Extract per-request P50/P95/P99 latency from vLLM AsyncEngine logs
   (currently using aggregate total_s/N proxy)
3. Cross-quantization comparison with v2.3 FP16 (apples-to-apples on
   identical N ladder)
4. Energy-optimal operating point identification across full N grid
   (currently best within tested points only)
"""
    path = RESULTS_DIR / "SUMMARY.md"
    path.write_text(md)
    print(f"  MD  → {path.relative_to(REPO_ROOT)}")


# ============================================================
# Methodology compliance JSON
# ============================================================


def emit_methodology_compliance(reps: list[RepRecord]) -> None:
    n_total = len(reps)
    n_ok = sum(1 for r in reps if r.ok)
    out = {
        "embargo": "EMBARGO_paper_bound",
        "embargo_rationale": "Polish-language model per METHODOLOGY §11.3 (Bielik scoop risk).",
        "methodology_version": "v1.0",
        "phase": "2_scaling_sweep",
        "n_reps_per_cell_target": REPS_EXPECTED,
        "n_runs_total_planned": REPS_EXPECTED * len(N_LADDER) * len(TP_LADDER),
        "n_runs_completed": n_ok,
        "n_runs_failed": n_total - n_ok,
        "n_ladder": N_LADDER,
        "tp_ladder": TP_LADDER,
        "kim_2026_disclosure": {
            "layer_1_data": "N/A — synthetic prompts per METHODOLOGY §6",
            "layer_2_pipeline": (
                "Claude Opus 4.7 (Anthropic, via Claude Code) generated "
                "orchestrator + finalize scripts following METHODOLOGY.md "
                "§5.2/§7. All design parameters (N ladder, n_reps, stats) "
                "pre-specified in human task brief before sweep launch."
            ),
            "layer_3_manuscript": "TBD per paper submission",
        },
        "lerchner_2026_humility": (
            "Measurements are extrinsic computational properties of the "
            "inference vehicle (throughput, latency, power, thermal). They "
            "do not constitute claims about model quality, reasoning, "
            "factual accuracy, or downstream clinical utility. All claims "
            "terminate at the hardware-software interface."
        ),
    }
    path = RESULTS_DIR / "methodology_compliance.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"  JSON → {path.relative_to(REPO_ROOT)}")


# ============================================================
# Main
# ============================================================


def main() -> int:
    if not THERMAL_DIR.exists():
        print(f"ERROR: missing {THERMAL_DIR}", file=sys.stderr)
        return 2

    print("=" * 60)
    print("Bielik 11B v3.0 Phase 2 finalize")
    print(f"Reading from: {THERMAL_DIR.relative_to(REPO_ROOT)}")
    print(f"Writing to:   {RESULTS_DIR.relative_to(REPO_ROOT)}")
    print("=" * 60)

    reps = build_reps()
    if not reps:
        print("ERROR: no rep records parsed", file=sys.stderr)
        return 3

    cells = aggregate_cells(reps)

    print(f"\nParsed {len(reps)} rep runs into {len(cells)} cells:")
    for c in cells:
        print(
            f"  TP={c.tp} N={c.n:4d}  n_ok={c.n_runs_ok:2d} "
            f"tok/s median={c.tok_s_out_median} "
            f"(min={c.tok_s_out_min}, max={c.tok_s_out_max}) "
            f"T_peak_max={c.t_peak_c_max}"
        )

    print("\nEmitting outputs:")
    emit_csvs(cells, reps)
    plot_scaling(cells, RESULTS_DIR / "scaling_curve.png")
    plot_latency_p99(cells, RESULTS_DIR / "latency_p99.png")
    plot_power_efficiency(cells, RESULTS_DIR / "power_efficiency.png")
    plot_thermal_gallery(cells, RESULTS_DIR / "thermal_gallery.png")
    emit_summary(cells, reps)
    emit_methodology_compliance(reps)

    print("\n" + "=" * 60)
    print("Phase 2 finalize complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
