#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — canonical-ladder GAP RECOVERY v3 (robust teardown + retry).
#
# WHY v3: v2 (2026-06-08 15:01) correctly KILLED the silent-fail (audit and
# orchestrator finally agreed: 0 ok / 130 fail) but the actual compute still
# failed because:
#   (a) run #1 (bielik-4.5b tp1 n500) HUNG to the 1800s timeout — KV thrashing
#       cliff: KV holds ~39.58× concurrency @ 8192 ctx, but the bench fires 500
#       prompts at once → preemption storm → pathologically low throughput → timeout.
#   (b) the hung run left an ORPHANED VLLM::EngineCore child (pid 15486) holding
#       ~30.8 GiB; v2 teardown killed the wrapper (15485) but not the child, so
#       every subsequent run was (correctly) skipped as GPU-poisoned.
#
# v3 fixes:
#   1. force_clear_gpu() — kill the ACTUAL GPU holders from `rocm-smi --showpids`
#      (KFD PID column), setsid, loop until VRAM is verified freed. No cmdline
#      guessing (v2's bug). Between runs the only KFD GPU user is a leak, so this
#      is safe. Never pkill -f (memory feedback_kill_isolation).
#   2. RETRY-TO-N10 — accumulate REPS *valid* reps per cell; a failed/timed-out
#      attempt is retried (GPU cleared first) up to ATTEMPT_CAP. Valid reps are
#      named r00..r(REPS-1) so finalize globs exactly REPS good ones.
#   3. PER_RUN_TIMEOUT_S = 420 (a good run finishes ~18s; 420s cleanly separates
#      "will complete" from "thrashing" without burning 30 min/hang). Timeout is
#      only a failure detector — it changes NO recorded number, only detection speed.
#   4. SATURATION verdict — if a cell can't reach REPS valid within ATTEMPT_CAP,
#      it is recorded as saturated (N_OK valid reps kept + SATURATED progress tag).
#      This is the legitimate scientific finding for KV-bound high-N small-model cells.
#
# SCOPE (audit 2026-06-08, after v2): same 13 cells. bielik-4.5b TP1 N500/N1000
# are the saturation-risk cells; everything else is a clean-GPU victim of the v2
# zombie and should reach n=10 normally.
#
# Embargo: EMBARGO_paper_bound (Polish models, METHODOLOGY §11.3).
#
# Usage (GPU idle; gsettings sleep already 'nothing'):
#   systemd-inhibit --what=sleep:idle --mode=block \
#     bash benchmarks/scripts/orchestrators/run_canonical_recovery_v3.sh [SMOKE]
#   SMOKE (optional 1st arg) = only run the smoke cell (pllum-8b TP1 N200) and exit.

set -uo pipefail   # NOT -e: a single failed run must not abort the sweep

SMOKE="${1:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT" || exit 1
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# ===========================================================================
# Configuration
# ===========================================================================
MAX_LEN=8192
UTIL=0.90
REPS=10
COOLDOWN_S=20
PER_RUN_TIMEOUT_S=420

MIN_FREE_GIB=29
GPU_SETTLE_S=10
CLEAR_TRIES=6
ATTEMPT_CAP=$(( REPS + 10 ))     # max attempts per cell to reach REPS valid reps
EARLY_SAT_LIMIT=5                 # 0 valid after this many attempts → declare saturated early

if [[ "$SMOKE" == "SMOKE" ]]; then
    MODEL_KEYS=("pllum-8b-awq")
    RESULT_DIRS=("Llama-PLLuM-8B-chat-2512-awq")
    MODEL_QUANTS=("awq")
    MODEL_PATHS=("/home/mozarcik/models/Llama-PLLuM-8B-chat-2512-awq")
    MODEL_HF_NAMES=("mozarcik/Llama-PLLuM-8B-chat-2512-awq")
    MODEL_CELLS=("1:200")
    GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_canonical_recovery_v3_smoke_logs"
else
    MODEL_KEYS=("bielik-4.5b-v30" "pllum-8b-awq" "pllum-12b-awq")
    RESULT_DIRS=("bielik-4.5b-v30" "Llama-PLLuM-8B-chat-2512-awq" "PLLuM-12B-chat-2512-awq")
    MODEL_QUANTS=("bf16" "awq" "awq")
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
    GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_canonical_recovery_v3_logs"
fi

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
mkdir -p "$GLOBAL_LOG_DIR"

# ===========================================================================
# Pre-flight
# ===========================================================================
for mp in "${MODEL_PATHS[@]}"; do
    [[ -d "$mp" ]] || { echo "ERROR: model not found at $mp" >&2; exit 1; }
done
stale="$(pgrep -af 'vllm serve|run_concurrent.py|bench_with_thermals.py' 2>/dev/null || true)"
if [[ -n "$stale" ]]; then
    echo "ERROR: vllm/bench processes present — refusing to start:" >&2
    echo "$stale" >&2; exit 1
fi

write_header() {
    {
        echo "# EMBARGO=YES — paper-bound (Polish models, METHODOLOGY §11.3)"
        echo "# Sweep: canonical-ladder gap recovery v3 (robust teardown + retry-to-n${REPS})"
        echo "# Started: $(date -Iseconds)"
        echo "# DO NOT COMMIT until paper acceptance."
        echo "#"
    } > "$1"
}
write_header "$PROGRESS_LOG"
write_header "$ORCHESTRATOR_LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$ORCHESTRATOR_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROGRESS_LOG"; }

# ---------------------------------------------------------------------------
# GPU helpers
# ---------------------------------------------------------------------------
free_gib() {
    rocm-smi --showmeminfo vram --json 2>/dev/null | python3 -c '
import json,sys
i=int(sys.argv[1])
try:
    d=json.load(sys.stdin); c=d[f"card{i}"]
    print(int((int(c["VRAM Total Memory (B)"])-int(c["VRAM Total Used Memory (B)"]))//(1024**3)))
except Exception: print(0)
' "$1"
}

# PIDs actually holding GPU memory, from the KFD process table (authoritative).
kfd_holder_pids() {
    rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/{print $1}'
}

# Kill the real GPU holders (setsid) until VRAM is verified freed. Returns 0/1.
force_clear_gpu() {
    local tp="$1" t pids pid f0 f1
    for ((t=1; t<=CLEAR_TRIES; t++)); do
        f0="$(free_gib 0)"; f1="$(free_gib 1)"
        if (( f0 >= MIN_FREE_GIB )) && { [[ "$tp" != "2" ]] || (( f1 >= MIN_FREE_GIB )); }; then
            return 0
        fi
        pids="$(kfd_holder_pids)"
        if [[ -n "$pids" ]]; then
            log "  force_clear: killing KFD holders [$(echo "$pids" | tr '\n' ' ')] (free0=${f0} free1=${f1}, try $t/$CLEAR_TRIES)"
            for pid in $pids; do
                setsid sh -c "kill -9 $pid 2>/dev/null" &
            done
        else
            log "  force_clear: VRAM low (free0=${f0} free1=${f1}) but no KFD pid — waiting (try $t/$CLEAR_TRIES)"
        fi
        sleep "$GPU_SETTLE_S"
    done
    f0="$(free_gib 0)"; f1="$(free_gib 1)"
    (( f0 >= MIN_FREE_GIB )) && { [[ "$tp" != "2" ]] || (( f1 >= MIN_FREE_GIB )); } && return 0
    log "  force_clear FAILED (free0=${f0} free1=${f1})"
    return 1
}

run_is_valid() {
    local f="$1"
    [[ -s "$f" ]] || return 1
    grep -qE 'Output throughput:[[:space:]]+[0-9].*tok/s' "$f" 2>/dev/null || return 1
    grep -qE 'Free memory on device.*less than|Engine core initialization failed' "$f" 2>/dev/null && return 1
    return 0
}

python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

log "============================================================"
log "Phase 2 — canonical recovery v3 (robust teardown + retry-to-n${REPS})"
log "Mode:       ${SMOKE:-FULL}"
log "Models:     ${MODEL_KEYS[*]}"
log "Timeout:    ${PER_RUN_TIMEOUT_S}s/run   VRAM gate: ≥${MIN_FREE_GIB}GiB   attempt cap: ${ATTEMPT_CAP}/cell"
log "============================================================"
progress "SWEEP_START mode=${SMOKE:-FULL}"

T_START_GLOBAL=$(date +%s)

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

    for cell in "${CELLS[@]}"; do
        TP="${cell%%:*}"
        N="${cell##*:}"
        log "----  $KEY TP=$TP N=$N  (target ${REPS} valid reps)  ----"
        N_OK=0; ATTEMPT=0

        while (( N_OK < REPS && ATTEMPT < ATTEMPT_CAP )); do
            ATTEMPT=$((ATTEMPT + 1))
            NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$N_OK")"
            BENCH_LOG="$OUT_DIR/${NAME}-bench.log"

            if ! force_clear_gpu "$TP"; then
                log "  ABORT cell $KEY TP=$TP N=$N — GPU unclearable"
                progress "CELL_ABORT key=$KEY tp=$TP n=$N ok=$N_OK reason=gpu_unclearable"
                break
            fi

            log "  [attempt $ATTEMPT/$ATTEMPT_CAP, valid=$N_OK/$REPS] $KEY/$NAME"
            RUN_START=$(date +%s)
            bench_rc=0
            timeout --signal=TERM --kill-after=30 "$((PER_RUN_TIMEOUT_S + 60))" \
                python3 "$BENCH" \
                "$KEY" "$TP" "$N" \
                --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
                --name "$NAME" --out-dir "$OUT_DIR" --interval 1.0 \
                --timeout "$PER_RUN_TIMEOUT_S" \
                >> "$ORCHESTRATOR_LOG" 2>&1 || bench_rc=$?

            if (( bench_rc == 0 )) && run_is_valid "$BENCH_LOG"; then
                N_OK=$((N_OK + 1))
                log "  OK   $KEY/$NAME ($(( $(date +%s) - RUN_START ))s) → valid=$N_OK/$REPS"
            else
                log "  FAIL $KEY/$NAME (rc=$bench_rc, $(( $(date +%s) - RUN_START ))s) — retry"
            fi

            # always sweep any leak before next attempt
            if (( $(free_gib 0) < MIN_FREE_GIB )); then force_clear_gpu "$TP" || true; fi
            sleep "$COOLDOWN_S"
            ELAPSED=$(( $(date +%s) - T_START_GLOBAL ))
            progress "PROGRESS key=$KEY tp=$TP n=$N valid=$N_OK attempt=$ATTEMPT elapsed_s=$ELAPSED"

            # early-saturation: if nothing valid after EARLY_SAT_LIMIT tries, this
            # cell is KV-bound (thrashing) — stop grinding, record the finding.
            if (( N_OK == 0 && ATTEMPT >= EARLY_SAT_LIMIT )); then
                log "  EARLY-SAT $KEY TP=$TP N=$N — 0 valid in $ATTEMPT attempts; declaring saturated"
                break
            fi
        done

        if (( N_OK >= REPS )); then
            log "----  $KEY TP=$TP N=$N COMPLETE: ${N_OK}/${REPS} valid in $ATTEMPT attempts  ----"
            progress "CELL_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK attempts=$ATTEMPT"
        else
            log "----  $KEY TP=$TP N=$N SATURATED: only ${N_OK}/${REPS} valid in $ATTEMPT attempts (KV-bound finding)  ----"
            progress "CELL_SATURATED key=$KEY tp=$TP n=$N ok=$N_OK attempts=$ATTEMPT"
        fi
    done

    log "Finalizing $KEY ..."
    if python3 "$FINALIZE" \
        --results-dir "$REPO_ROOT/benchmarks/results/$RESULT_DIR" \
        --model-label "$KEY" --model-name "${MODEL_HF_NAMES[$m]}" \
        --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
        >> "$ORCHESTRATOR_LOG" 2>&1
    then
        log "Finalize OK — benchmarks/results/$RESULT_DIR/SUMMARY.md"
    else
        log "WARN: finalize failed for $KEY; raw data preserved"
    fi
done

T_TOTAL=$(( $(date +%s) - T_START_GLOBAL ))
log "============================================================"
log "Recovery v3 (${SMOKE:-FULL}) complete. Total wall: ${T_TOTAL}s ($((T_TOTAL/60)) min)"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL"
echo "DONE $(date -Iseconds) mode=${SMOKE:-FULL} wall_s=$T_TOTAL" > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
