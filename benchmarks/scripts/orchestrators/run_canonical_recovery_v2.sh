#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — canonical-ladder GAP RECOVERY v2 (OOM-hardened).
#
# WHY v2: the 2026-06-07/08 canonical_recovery run (v1) died silently. Root
# cause (from bench logs, 2026-06-08 incident): a crashed high-N run left a
# leaked vLLM EngineCore child holding ~28 GiB on cuda:0. Every subsequent
# launch then OOM'd at startup:
#   ValueError: Free memory on device cuda:0 (2.86/31.86 GiB) < desired 0.9 (28.67 GiB)
# yet the orchestrator counted rc=0 as "ok" → progress.log said ok=10 while
# finalize (authoritative) recorded 0/10 (silent-fail). v1 also bundled 2 already-
# COMPLETE models (bielik-11b v23/v30) — wasted compute.
#
# v2 fixes (orchestrator-level, bench_with_thermals.py untouched — lower blast radius):
#   1. PRE-RUN VRAM GATE   — require ≥ MIN_FREE_GIB free on the GPU(s) the run
#                            needs (cuda:0 for TP1; cuda:0+cuda:1 for TP2).
#                            If short → teardown leaked vLLM (setsid, never
#                            pkill -f, per memory feedback_kill_isolation), settle,
#                            re-check. Abort the run (count FAIL) if still poisoned —
#                            NEVER produce garbage labelled "ok".
#   2. POST-RUN VALIDATION — a run counts OK only if rc==0 AND its bench.log has
#                            "Output throughput: … tok/s" AND has NO OOM string.
#                            Kills the silent-fail that fooled v1.
#   3. POST-RUN LEAK SWEEP — if free VRAM is low after a run, setsid-teardown the
#                            leaked engine before the next launch.
#
# SCOPE — ONLY the cells the 2026-06-08 audit (audit_paper1_completeness.py) still
# reports short. The 8× 70B family + bielik-11b v23/v30 + the 2 Bielik v3.0
# refresh models are COMPLETE and NOT touched. Canonical ladder N ∈
# {10,25,50,100,200,500,1000}; non-canonical N=250 left as-is (supplementary).
#
# Missing-cell matrix (TP:N), n=10 reps each (audit verdict 2026-06-08):
#   bielik-4.5b-v30 (bf16): 1:500 1:1000 2:10 2:25 2:50 2:100 2:200 2:500 2:1000   (9)
#   pllum-8b-awq    (awq):  1:200 2:200                                            (2)
#   pllum-12b-awq   (awq):  1:200 2:200   (TP2/200 was 9/10 — full re-run cleaner) (2)
#   → 13 cells × 10 reps = 130 runs.
#
# Embargo: EMBARGO_paper_bound (Polish models, METHODOLOGY §11.3).
#
# Usage (GPU must be idle; gsettings sleep already set to 'nothing' for this box):
#   systemd-inhibit --what=sleep:idle --mode=block \
#     bash benchmarks/scripts/orchestrators/run_canonical_recovery_v2.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# ===========================================================================
# Configuration
# ===========================================================================
MAX_LEN=8192
UTIL=0.90
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800

# OOM-hardening knobs. 32 GiB card; util 0.9 wants 28.67 GiB → gate at 29.
MIN_FREE_GIB=29
GPU_SETTLE_S=20
GPU_GATE_TRIES=3

# Parallel arrays — index-aligned. CELLS = space-separated TP:N pairs to recover.
MODEL_KEYS=(
    "bielik-4.5b-v30"
    "pllum-8b-awq"
    "pllum-12b-awq"
)
RESULT_DIRS=(
    "bielik-4.5b-v30"
    "Llama-PLLuM-8B-chat-2512-awq"
    "PLLuM-12B-chat-2512-awq"
)
MODEL_QUANTS=(
    "bf16"
    "awq"
    "awq"
)
MODEL_PATHS=(
    "/home/mozarcik/models/bielik-4.5b-v30"
    "/home/mozarcik/models/Llama-PLLuM-8B-chat-2512-awq"
    "/home/mozarcik/models/PLLuM-12B-chat-2512-awq"
)
MODEL_HF_NAMES=(
    "speakleash/Bielik-4.5B-v3-Instruct"
    "mozarcik/Llama-PLLuM-8B-chat-2512-awq"
    "mozarcik/PLLuM-12B-chat-2512-awq"
)
MODEL_CELLS=(
    "1:500 1:1000 2:10 2:25 2:50 2:100 2:200 2:500 2:1000"
    "1:200 2:200"
    "1:200 2:200"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"

GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_canonical_recovery_v2_logs"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
mkdir -p "$GLOBAL_LOG_DIR"

# ===========================================================================
# Pre-flight: models present; no stale vLLM (REFUSE — never pkill -f).
# ===========================================================================
for mp in "${MODEL_PATHS[@]}"; do
    [[ -d "$mp" ]] || { echo "ERROR: model not found at $mp" >&2; exit 1; }
done
stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py|bench_with_thermals.py' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: vllm/bench processes present — refusing to start (avoid GPU collision):" >&2
    echo "$stale_pids" >&2
    exit 1
fi

write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish models, METHODOLOGY §11.3)"
        echo "# Sweep: canonical-ladder gap recovery v2 (OOM-hardened, targeted cells)"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT until paper acceptance."
        echo "#"
    } > "$f"
}
write_embargo_header "$PROGRESS_LOG"
write_embargo_header "$ORCHESTRATOR_LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$ORCHESTRATOR_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROGRESS_LOG"; }

# ---------------------------------------------------------------------------
# GPU helpers (OOM hardening)
# ---------------------------------------------------------------------------
# Free VRAM (integer GiB) for a card index (0/1), via rocm-smi JSON.
free_gib() {
    rocm-smi --showmeminfo vram --json 2>/dev/null | python3 -c '
import json,sys
i=int(sys.argv[1])
try:
    d=json.load(sys.stdin); c=d[f"card{i}"]
    tot=int(c["VRAM Total Memory (B)"]); used=int(c["VRAM Total Used Memory (B)"])
    print(int((tot-used)//(1024**3)))
except Exception:
    print(0)
' "$1"
}

# PIDs holding GPU memory that are vLLM/bench leaks (defensive: only python procs
# whose cmdline matches our stack). Sources: rocm-smi --showpids + pgrep fallback.
leaked_gpu_pids() {
    {
        rocm-smi --showpids 2>/dev/null | grep -oE '^[0-9]+' || true
        pgrep -f 'run_concurrent.py|vllm|multiprocessing.spawn|EngineCore' 2>/dev/null || true
    } | sort -un | while read -r pid; do
        [[ -r "/proc/$pid/cmdline" ]] || continue
        if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null \
             | grep -qE 'run_concurrent\.py|vllm|multiprocessing\.spawn'; then
            echo "$pid"
        fi
    done
}

# setsid-teardown leaked engine procs (never pkill -f; signal won't reach caller).
teardown_leaks() {
    local pids; pids="$(leaked_gpu_pids | sort -un)"
    [[ -z "$pids" ]] && return 0
    log "  TEARDOWN leaked GPU pids: $(echo "$pids" | tr '\n' ' ')"
    local pid
    for pid in $pids; do
        setsid sh -c "kill $pid 2>/dev/null; sleep 3; kill -9 $pid 2>/dev/null" &
    done
    sleep "$GPU_SETTLE_S"
}

# Require clean GPU for a run of tensor-parallel degree TP. Returns 0 clean, 1 not.
ensure_clean_gpu() {
    local tp="$1" tries=0 f0 f1 ok
    while (( tries < GPU_GATE_TRIES )); do
        f0="$(free_gib 0)"; f1="$(free_gib 1)"; ok=1
        (( f0 < MIN_FREE_GIB )) && ok=0
        if [[ "$tp" == "2" ]] && (( f1 < MIN_FREE_GIB )); then ok=0; fi
        if (( ok == 1 )); then return 0; fi
        log "  GPU not clean (free0=${f0}GiB free1=${f1}GiB, need ${MIN_FREE_GIB}; TP=$tp) — teardown attempt $((tries+1))/$GPU_GATE_TRIES"
        teardown_leaks
        tries=$((tries+1))
    done
    f0="$(free_gib 0)"; f1="$(free_gib 1)"
    log "  GPU STILL POISONED after $GPU_GATE_TRIES attempts (free0=${f0}GiB free1=${f1}GiB)"
    return 1
}

# A run is valid iff it produced a throughput number AND has no OOM marker.
run_is_valid() {
    local f="$1"
    [[ -s "$f" ]] || return 1
    grep -qE 'Output throughput:[[:space:]]+[0-9].*tok/s' "$f" 2>/dev/null || return 1
    grep -qE 'Free memory on device.*less than|Engine core initialization failed' "$f" 2>/dev/null && return 1
    return 0
}

python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# Total run count for ETA.
TOTAL_RUNS=0
for cells in "${MODEL_CELLS[@]}"; do
    # shellcheck disable=SC2206
    arr=($cells)
    TOTAL_RUNS=$(( TOTAL_RUNS + ${#arr[@]} * REPS ))
done
RUNS_DONE=0
T_START_GLOBAL=$(date +%s)

log "============================================================"
log "Phase 2 — canonical-ladder gap recovery v2 (OOM-hardened)"
log "Models:        ${MODEL_KEYS[*]}"
log "Total runs:    $TOTAL_RUNS   (13 cells × $REPS reps)"
log "VRAM gate:     ≥ ${MIN_FREE_GIB} GiB free / needed card(s)"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL_RUNS"

for ((m=0; m<${#MODEL_KEYS[@]}; m++)); do
    KEY="${MODEL_KEYS[$m]}"
    RESULT_DIR="${RESULT_DIRS[$m]}"
    QUANT="${MODEL_QUANTS[$m]}"
    OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
    mkdir -p "$OUT_DIR"
    # shellcheck disable=SC2206
    CELLS=(${MODEL_CELLS[$m]})

    log "################  MODEL: $KEY ($QUANT) → $RESULT_DIR — ${#CELLS[@]} cells  ################"
    progress "MODEL_BEGIN key=$KEY quant=$QUANT cells=${#CELLS[@]}"
    T_MODEL_START=$(date +%s)

    for cell in "${CELLS[@]}"; do
        TP="${cell%%:*}"
        N="${cell##*:}"
        log "----  $KEY TP=$TP N=$N  ----"
        N_OK=0; N_FAIL=0

        for ((REP=0; REP<REPS; REP++)); do
            NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
            RUNS_DONE=$((RUNS_DONE + 1))
            BENCH_LOG="$OUT_DIR/${NAME}-bench.log"

            # --- PRE-RUN VRAM GATE -------------------------------------------
            if ! ensure_clean_gpu "$TP"; then
                N_FAIL=$((N_FAIL + 1))
                log "  FAIL $KEY/$NAME — GPU poisoned, run skipped (NOT counted ok)"
                progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS key=$KEY tp=$TP n=$N rep=$REP status=skip_gpu_poisoned"
                continue
            fi

            log "[$RUNS_DONE/$TOTAL_RUNS] starting $KEY/$NAME"
            RUN_START=$(date +%s)
            bench_rc=0
            python3 "$BENCH" \
                "$KEY" "$TP" "$N" \
                --quant "$QUANT" \
                --max-len "$MAX_LEN" \
                --util "$UTIL" \
                --name "$NAME" \
                --out-dir "$OUT_DIR" \
                --interval 1.0 \
                --timeout "$PER_RUN_TIMEOUT_S" \
                >> "$ORCHESTRATOR_LOG" 2>&1 || bench_rc=$?

            # --- POST-RUN VALIDATION (kills silent-fail) ---------------------
            if (( bench_rc == 0 )) && run_is_valid "$BENCH_LOG"; then
                N_OK=$((N_OK + 1))
                log "  OK  $KEY/$NAME ($(( $(date +%s) - RUN_START ))s wall)"
            else
                N_FAIL=$((N_FAIL + 1))
                log "  FAIL $KEY/$NAME (rc=$bench_rc, valid=$(run_is_valid "$BENCH_LOG" && echo y || echo n), $(( $(date +%s) - RUN_START ))s wall) — see $BENCH_LOG"
            fi

            # --- POST-RUN LEAK SWEEP (pre-empt the next-run OOM) -------------
            if (( $(free_gib 0) < MIN_FREE_GIB )); then
                log "  post-run cuda:0 low (free0=$(free_gib 0)GiB) — sweeping leaks"
                teardown_leaks
            fi

            if (( RUNS_DONE < TOTAL_RUNS )); then sleep "$COOLDOWN_S"; fi

            ELAPSED=$(( $(date +%s) - T_START_GLOBAL ))
            AVG_S=$((ELAPSED / RUNS_DONE))
            ETA_S=$(( AVG_S * (TOTAL_RUNS - RUNS_DONE) ))
            progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS key=$KEY tp=$TP n=$N rep=$REP ok=$N_OK fail=$N_FAIL elapsed_s=$ELAPSED eta_s=$ETA_S"
        done
        log "----  $KEY TP=$TP N=$N DONE: $N_OK ok, $N_FAIL fail  ----"
        progress "CELL_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK fail=$N_FAIL"
    done

    log "########  MODEL $KEY DONE: $(( ( $(date +%s) - T_MODEL_START ) / 60 )) min  ########"
    log "Finalizing $KEY ..."
    if python3 "$FINALIZE" \
        --results-dir "$REPO_ROOT/benchmarks/results/$RESULT_DIR" \
        --model-label "$KEY" \
        --model-name "${MODEL_HF_NAMES[$m]}" \
        --quant "$QUANT" \
        --max-len "$MAX_LEN" \
        --util "$UTIL" \
        >> "$ORCHESTRATOR_LOG" 2>&1
    then
        log "Finalize OK — see benchmarks/results/$RESULT_DIR/SUMMARY.md"
    else
        log "WARN: finalize failed for $KEY; raw data preserved in $OUT_DIR"
    fi
done

T_TOTAL=$(( $(date +%s) - T_START_GLOBAL ))
log "============================================================"
log "Recovery v2 complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

echo "DONE $(date -Iseconds) runs=$RUNS_DONE/$TOTAL_RUNS wall_s=$T_TOTAL" > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
