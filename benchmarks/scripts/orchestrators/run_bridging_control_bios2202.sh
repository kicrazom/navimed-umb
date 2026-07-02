#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — FIRMWARE-BOUNDARY BRIDGING CONTROL (BIOS 1715 -> 2202).
#
# WHY THIS SCRIPT EXISTS
#   On 2026-06-13 the platform BIOS was flashed 1715 -> 2202 (AGESA 1.2.0.3g ->
#   1.3.0.1) in the clean window between Phase 1 and the Phase-2 paper cut.
#   METHODOLOGY §2.1 now declares a platform version boundary. To convert that
#   boundary from a reviewer objection into a DOCUMENTED CONTROL, we re-measure
#   the headline TP×quantisation pair under 2202 with EVERYTHING ELSE identical
#   to the 1715 baseline (same runner = bench_with_thermals.py -> run_concurrent.py,
#   same N ladder, same reps, same _env.sh) and show throughput matches within the
#   per-cell CV (~1%). Firmware is the ONLY changed variable.
#
#   Vehicle-identity is deliberate: we do NOT switch to throughput_sweep_v0.3.py
#   (which per-record-tags firmware) because changing the runner would confound
#   runner+firmware and break the control. Firmware provenance is captured ONCE
#   here (firmware.json + embargo header) since it is constant for the whole sweep.
#
# SCOPE — the headline TP×quant pair (v3.0 Instruct family, same keys as the
# 2026-06-07 refresh re-run so the 1715 baseline is directly comparable):
#   1. bielik-pl-11b-v30-instruct   (speakleash/Bielik-PL-11B-v3.0-Instruct, bf16) -> 1715: TP=1 wins
#   2. bielik-11b-v30-instruct-awq  (speakleash/Bielik-11B-v3.0-Instruct, awq W4A16) -> 1715: TP=2 wins
#   Canonical paper ladder N={10,25,50,100,200,500,1000}, TP={1,2}, reps=10.
#
# OUTPUT — NEW dirs (*-bios2202) so the 1715 baseline (735 files each) is NEVER
# overwritten; the comparison needs both halves.
#
# Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.3). DO NOT COMMIT.
#
# Usage (already wrapped in a sentinel-gated systemd-inhibit by the operator):
#   bash benchmarks/scripts/orchestrators/run_bridging_control_bios2202.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# --- Config (matches the 1715 baseline vehicle exactly) ---
MAX_LEN=8192
UTIL=0.90
N_LADDER=(10 25 50 100 200 500 1000)
TP_LADDER=(1 2)
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800       # N=1000 reps are LONG; rc=124 caught, never kills sweep

# Parallel arrays — index-aligned (load-bearing).
MODEL_KEYS=(
    "bielik-pl-11b-v30-instruct"
    "bielik-11b-v30-instruct-awq"
)
RESULT_DIRS=(
    "bielik-pl-11b-v30-instruct-bios2202"
    "bielik-11b-v30-instruct-awq-bios2202"
)
MODEL_QUANTS=(
    "bf16"
    "awq"
)
MODEL_PATHS=(
    "/home/mozarcik/models/bielik-pl-11b-v30-instruct"
    "/home/mozarcik/models/bielik-11b-v30-instruct-awq"
)
MODEL_HF_NAMES=(
    "speakleash/Bielik-PL-11B-v3.0-Instruct"
    "speakleash/Bielik-11B-v3.0-Instruct"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"

GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_bridging_2026-06-13_logs"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
mkdir -p "$GLOBAL_LOG_DIR"

# --- Pre-flight: models present; no stale vLLM/bench/canary (REFUSE — never pkill,
#     per memory feedback_kill_isolation). ---
for mp in "${MODEL_PATHS[@]}"; do
    if [[ ! -d "$mp" ]]; then
        echo "ERROR: model not found at $mp" >&2
        exit 1
    fi
done
stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py|bench_with_thermals.py|gate1_grid.py' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: vllm/bench/canary processes present — refusing to start (avoid GPU collision):" >&2
    echo "$stale_pids" >&2
    exit 1
fi

# --- Embargo headers (METHODOLOGY §11.4) ---
write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.3)"
        echo "# Sweep: FIRMWARE-BOUNDARY bridging control under BIOS 2202"
        echo "# Pair: {bielik-pl-11b-v30-instruct bf16, bielik-11b-v30-instruct-awq awq}"
        echo "# Ladder: TP={1,2}, N={10,25,50,100,200,500,1000}, reps=10"
        echo "# Baseline to compare: benchmarks/results/<model>/ (BIOS 1715)"
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

# --- vLLM version pin (per METHODOLOGY §3.1) ---
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# --- Firmware provenance (captured ONCE; constant for the whole sweep — §2.1/§3.3) ---
BIOS_VERSION="$(cat /sys/class/dmi/id/bios_version 2>/dev/null || echo unknown)"
BIOS_DATE="$(cat /sys/class/dmi/id/bios_date 2>/dev/null || echo unknown)"
AGESA="$(timeout 15 fwupdmgr get-devices --no-authenticate 2>/dev/null | grep -iom1 'AGESA ComboAm5Pi [0-9.]*' || true)"
AGESA="${AGESA:-unknown}"
printf '{"bios_version":"%s","bios_date":"%s","agesa":"%s","captured_at":"%s"}\n' \
    "$BIOS_VERSION" "$BIOS_DATE" "$AGESA" "$(date -Iseconds)" > "$GLOBAL_LOG_DIR/firmware.json"
log "Firmware: BIOS=$BIOS_VERSION ($BIOS_DATE) AGESA=$AGESA"
if [[ "$BIOS_VERSION" != "2202" ]]; then
    log "WARN: expected BIOS 2202, got '$BIOS_VERSION' — bridging premise may be wrong"
fi

# --- Main sweep — model (outer) -> TP -> N -> reps ---
T_START_GLOBAL=$(date +%s)
TOTAL_RUNS=$(( ${#MODEL_KEYS[@]} * ${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS ))
RUNS_DONE=0

log "============================================================"
log "Phase 2 — firmware-boundary bridging control (BIOS $BIOS_VERSION)"
log "Models:     ${MODEL_KEYS[*]}"
log "TP ladder:  ${TP_LADDER[*]}"
log "N ladder:   ${N_LADDER[*]}"
log "Reps/cell:  $REPS"
log "Total runs: $TOTAL_RUNS   (${#MODEL_KEYS[@]} models × ${#TP_LADDER[@]} TP × ${#N_LADDER[@]} N × $REPS reps)"
log "Output:     benchmarks/results/<model>-bios2202/  (1715 baseline preserved)"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL_RUNS bios=$BIOS_VERSION"

for ((m=0; m<${#MODEL_KEYS[@]}; m++)); do
    KEY="${MODEL_KEYS[$m]}"
    RESULT_DIR="${RESULT_DIRS[$m]}"
    QUANT="${MODEL_QUANTS[$m]}"
    OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
    mkdir -p "$OUT_DIR"

    log "################  MODEL: $KEY ($QUANT) → $RESULT_DIR  ################"
    progress "MODEL_BEGIN key=$KEY quant=$QUANT result_dir=$RESULT_DIR"
    T_MODEL_START=$(date +%s)

    for TP in "${TP_LADDER[@]}"; do
        log "================  $KEY  TP=$TP  ================"
        progress "TP_BEGIN key=$KEY tp=$TP"

        for N in "${N_LADDER[@]}"; do
            log "----  $KEY N=$N (TP=$TP)  ----"
            T_N_START=$(date +%s)
            N_OK=0; N_FAIL=0

            for ((REP=0; REP<REPS; REP++)); do
                NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
                RUNS_DONE=$((RUNS_DONE + 1))
                log "[$RUNS_DONE/$TOTAL_RUNS] starting $KEY/$NAME"
                RUN_START=$(date +%s)

                # continue-on-fail: a transient HIP OOM at large N must not abort.
                if python3 "$BENCH" \
                    "$KEY" "$TP" "$N" \
                    --quant "$QUANT" \
                    --max-len "$MAX_LEN" \
                    --util "$UTIL" \
                    --name "$NAME" \
                    --out-dir "$OUT_DIR" \
                    --interval 1.0 \
                    --timeout "$PER_RUN_TIMEOUT_S" \
                    >> "$ORCHESTRATOR_LOG" 2>&1
                then
                    N_OK=$((N_OK + 1))
                    RUN_S=$(( $(date +%s) - RUN_START ))
                    log "  OK  $KEY/$NAME (${RUN_S}s wall)"
                else
                    N_FAIL=$((N_FAIL + 1))
                    RUN_S=$(( $(date +%s) - RUN_START ))
                    log "  FAIL $KEY/$NAME (${RUN_S}s wall) — see ${OUT_DIR}/${NAME}-bench.log"
                fi

                if (( RUNS_DONE < TOTAL_RUNS )); then
                    sleep "$COOLDOWN_S"
                fi

                T_NOW=$(date +%s)
                ELAPSED=$((T_NOW - T_START_GLOBAL))
                AVG_S=$((ELAPSED / RUNS_DONE))
                REMAINING=$((TOTAL_RUNS - RUNS_DONE))
                ETA_S=$((AVG_S * REMAINING))
                progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS key=$KEY tp=$TP n=$N rep=$REP last_run_s=$RUN_S elapsed_s=$ELAPSED eta_s=$ETA_S"
            done

            T_N_END=$(date +%s)
            log "----  $KEY N=$N (TP=$TP) DONE: $N_OK ok, $N_FAIL fail, $((T_N_END - T_N_START))s  ----"
            progress "N_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK fail=$N_FAIL"
        done
    done

    T_MODEL_END=$(date +%s)
    log "########  MODEL $KEY DONE: $(( (T_MODEL_END - T_MODEL_START) / 60 )) min  ########"

    # Finalize this model -> regenerate phase2_sweep.csv + SUMMARY.md from raw runs.
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
log "Bridging control complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "Compare: benchmarks/results/<model>-bios2202/SUMMARY.md vs benchmarks/results/<model>/SUMMARY.md"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

echo "DONE $(date -Iseconds) runs=$RUNS_DONE/$TOTAL_RUNS wall_s=$T_TOTAL bios=$BIOS_VERSION" > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
