#!/usr/bin/env bash
# =============================================================================
# run_pllum70b_n10_rerun_sweep.sh
#
# NaviMed-UMB Phase 2 *RERUN* — Llama-PLLuM-70B AWQ family at n=10 reps/cell.
#
# WHY: the 6 swept 70B variants currently have SINGLE-SHOT data from the
# path-based runner throughput_scaling_phase2.py. The owner approved a
# statistical re-run at n=10 so we can report median / p95 / p99 per (N) cell.
# This is a FAITHFUL statistical upgrade of the SAME experiment — NOT a switch
# to the Run-3 {5..250} ladder. Config below is replicated 1:1 from the
# original 70B artifacts in benchmarks/results/Llama-PLLuM-70B-chat-2512-awq/
# scaling/results_table.csv:
#     TP=2, max_model_len=8192, gpu_memory_utilization=0.90, enforce_eager,
#     quant label "compressed-tensors" (W4A16 pack-quantized, ~37 GB each),
#     N ladder {10,25,50,100,200,500,1000}, COOLDOWN 15 s (METHODOLOGY §5.2).
#
# 6 models (compressed-tensors W4A16, TP=2 ONLY — ~37 GB won't fit one 32 GB
# R9700):
#   Llama-PLLuM-70B-{chat,instruct}-{2412,2508,2512}-awq
#
# ---------------------------------------------------------------------------
# PRIMITIVE — path-based runner (NOT the keyed run_concurrent.py)
# ---------------------------------------------------------------------------
# We build ON TOP of the path-based scaling primitive:
#   throughput_scaling_phase2.py <model_dir> <tp> --quant Q --ns <ladder>
#     → imports throughput_sweep_v0.3.py (H.run_n / H.write_summary)
#     → writes benchmarks/results/<model_dir>/scaling/{thermal-runs/, CSV, MD}
# We DO NOT touch run_concurrent.py / bench_with_thermals.py — those are spawned
# live every ~60 s by the Run-3 keyed sweep and editing them risks corruption.
# Zero edits to any runner: this orchestrator only CALLS the path runner and
# moves its output between reps.
#
# ---------------------------------------------------------------------------
# REP MECHANISM (documented decision — lower-risk option)
# ---------------------------------------------------------------------------
# The path runner is SINGLE-SHOT per N: it writes a FIXED output tree
#   benchmarks/results/<model>/scaling/{thermal-runs/<quant>-tp<TP>-n<N>-*,
#                                        results_table.csv, SUMMARY.md}
# and OVERWRITES it on every invocation (no rep/-rNN suffix in the runner, and
# no CLI flag to redirect the output dir). Editing the runner to add a rep
# suffix is OUT (the task forbids touching runners, and the wrapper is shared).
#
# Chosen mechanism — REP-DIR ISOLATION VIA MOVE (no Python edits):
#   For each model, for each rep r in 0..9:
#     1. run the FULL N ladder once   (one throughput_scaling_phase2.py call,
#        which loops N internally with H.COOLDOWN_S=15 s between N cells);
#     2. MOVE the produced scaling/{thermal-runs,results_table.csv,SUMMARY.md}
#        into scaling/rep<NN>/  so the next rep starts from a clean scaling/
#        and nothing is overwritten.
#   Reps are isolated, each carries its own full §7.1 artifact set, and the
#   per-N process isolation / thermal sampling inside the runner is unchanged.
#   Cross-rep aggregation (median/p95/p99) is a SEPARATE later step over the
#   rep<NN>/results_table.csv files (NOT done here — raw data is the deliverable).
#
# WHY this over "call per-N 10× with -rNN": the runner has no public per-N
# entry that takes a custom output NAME (H.run_n needs an out_dir AND the
# filename is derived as "<quant>-tp<TP>-n<N>" with no rep token), so suffixing
# would require either editing the runner (forbidden) or re-implementing run_n
# here (duplication + drift risk). Moving whole-ladder output per rep keeps the
# runner pristine and the artifacts faithful. The only cost: load_time_s is paid
# once per (rep × N) instead of being amortised — that's correct for honest
# per-run statistics anyway (cold-ish engine each cell, as in the original).
#
# ---------------------------------------------------------------------------
# Output (gitignored — benchmarks/results/ is fully ignored, EMBARGO-safe):
#   benchmarks/results/<model>/scaling/rep<NN>/thermal-runs/
#       compressed-tensors-tp2-n{10,25,50,100,200,500,1000}-{bench.log,events.json,thermals.jsonl}
#   benchmarks/results/<model>/scaling/rep<NN>/{results_table.csv,SUMMARY.md}
#
# NOTE: this rerun moves the ORIGINAL single-shot scaling/ artifacts (the
# 2026-05-23 run) into scaling/rep00/ on the FIRST rep of the FIRST model only
# if they are still in scaling/ root — see archive_preexisting() below. They are
# preserved, not destroyed.
#
# Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.2/§11.3).
# Per-file EMBARGO=YES headers written to progress/orchestrator logs.
#
# Usage from repo root (wrap in systemd-inhibit to survive idle-suspend; the
# chained launcher launch_70b_rerun_after_run3.sh already does this for you):
#   systemd-inhibit --what=sleep:idle --who=navimed-70b-rerun \
#       --why="70B n=10 rerun" --mode=block \
#       bash benchmarks/scripts/orchestrators/run_pllum70b_n10_rerun_sweep.sh
#
# HARD RULES: never pkill/kill (pre-flight REFUSES on stale vllm, per memory
# feedback_kill_isolation). Per-N cleanup uses scripts/kill_port.sh (setsid).
# =============================================================================

set -euo pipefail

# ===========================================================================
# Source the single canonical environment (METHODOLOGY §3.1)
# ===========================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# TP=2 dual-R9700 REQUIRES NCCL P2P disabled (gfx1201 P2P path unstable);
# this var is NOT in _env.sh, so set it here explicitly for the TP=2 sweep.
export NCCL_P2P_DISABLE=1

# ===========================================================================
# Configuration — REPLICATED 1:1 from original 70B artifacts
# ===========================================================================
QUANT="compressed-tensors"        # filename prefix + CSV label (matches original
                                  # run; vLLM auto-detects compressed-tensors when
                                  # --extra is empty, so engine behaviour is
                                  # identical to the single-shot run).
TP=2                              # 70B AWQ ~37 GB → TP=2 ONLY (won't fit one 32 GB R9700)
MAX_LEN=8192
UTIL=0.90                         # the runner hardcodes UTIL=0.90 / MAX_LEN=8192 internally;
                                  # declared here for logs/headers (single source of truth)
N_LADDER_CSV="10,25,50,100,200,500,1000"   # original 7-point ladder (NOT Run-3 {5..250})
REPS=10
# COOLDOWN between N cells is owned by the runner (H.COOLDOWN_S=15 s); we add a
# longer inter-REP cooldown to let the 2× R9700 cool between full ladders.
INTER_REP_COOLDOWN_S=30

# RESUME variant 2026-06-02: chat-{2412,2508,2512} already DONE (10 reps each,
# n=10 complete). Only the 3 instruct models remain (killed in-flight at the
# 01:23 thermal stop, 0 partial). chat lines intentionally removed so they are
# NOT re-swept / clobbered. Canonical run_pllum70b_n10_rerun_sweep.sh keeps all 6.
MODEL_DIRS=(
    "Llama-PLLuM-70B-instruct-2412-awq"
    "Llama-PLLuM-70B-instruct-2508-awq"
    "Llama-PLLuM-70B-instruct-2512-awq"
)

RUNNER="$REPO_ROOT/benchmarks/scripts/runners/throughput_scaling_phase2.py"
KILL_PORT="$REPO_ROOT/scripts/kill_port.sh"
RESULTS_ROOT="$REPO_ROOT/benchmarks/results"
GLOBAL_LOG_DIR="$RESULTS_ROOT/_pllum70b_rerun_logs"
mkdir -p "$GLOBAL_LOG_DIR"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
SENTINEL="$GLOBAL_LOG_DIR/SWEEP_COMPLETE"

# ===========================================================================
# Embargo headers (per METHODOLOGY §11.4)
# ===========================================================================
write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.2/§11.3)"
        echo "# Sweep: 70B n=10 RERUN, TP=$TP, N={$N_LADDER_CSV}, reps=$REPS, quant=$QUANT"
        echo "# Primitive: throughput_scaling_phase2.py (path-based), rep-dir isolation via move"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT raw scaling/rep*/thermal-runs/ until paper acceptance."
        echo "#"
    } > "$f"
}
write_embargo_header "$ORCHESTRATOR_LOG"
write_embargo_header "$PROGRESS_LOG"

log() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$ORCHESTRATOR_LOG"
}
progress() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" >> "$PROGRESS_LOG"
}

# ===========================================================================
# Pre-flight: models present, runner present, no stale vLLM.
# REFUSE on stale vllm — NEVER pkill/kill (memory feedback_kill_isolation).
# We MUST NOT trip on the live Run-3 sweep's run_concurrent.py either; we only
# refuse on a *bare* `vllm serve` (none is expected — the suite uses offline
# LLM.generate) or a stale 70B child. We do NOT match run_concurrent.py so the
# live Run-3 keyed sweep is left strictly alone.
# ===========================================================================
if [[ ! -f "$RUNNER" ]]; then
    echo "ERROR: path runner not found: $RUNNER" >&2
    exit 1
fi
for md in "${MODEL_DIRS[@]}"; do
    if [[ ! -f "$HOME/models/$md/config.json" ]]; then
        echo "ERROR: model dir missing config.json: $HOME/models/$md" >&2
        exit 1
    fi
done

# Refuse only on a stale bare `vllm serve` or a stale 70B scaling child of THIS
# harness — explicitly NOT run_concurrent.py (that belongs to live Run-3).
stale_pids="$(pgrep -af 'vllm serve|throughput_scaling_phase2.py|throughput_sweep_v0.3.py.*--child.*70B' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: stale vllm / 70B-scaling processes present — refusing to start (NEVER kill):" >&2
    echo "$stale_pids" >&2
    exit 1
fi

# vLLM version pin assert (per METHODOLOGY — 0.19.0+rocm721 PINNED)
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"
log "NCCL_P2P_DISABLE=$NCCL_P2P_DISABLE (required for TP=$TP dual-R9700)"

# ===========================================================================
# archive_preexisting — preserve the ORIGINAL single-shot scaling/ artifacts.
# If scaling/results_table.csv exists in the scaling/ ROOT (the 2026-05-23
# single-shot run), move that whole set into scaling/_preexisting_singleshot/
# ONCE, before any rep writes. Never deletes data.
# ===========================================================================
archive_preexisting() {
    local sdir="$1"
    if [[ -f "$sdir/results_table.csv" || -d "$sdir/thermal-runs" ]]; then
        local arch="$sdir/_preexisting_singleshot"
        if [[ ! -e "$arch" ]]; then
            mkdir -p "$arch"
            # Move only the runner-produced artifacts; leave rep*/ and plots be.
            for item in thermal-runs results_table.csv SUMMARY.md; do
                if [[ -e "$sdir/$item" ]]; then
                    mv "$sdir/$item" "$arch/" 2>/dev/null || true
                fi
            done
            log "  archived pre-existing single-shot artifacts → $arch"
        fi
    fi
}

# ===========================================================================
# move_rep_output — after one full-ladder run, move scaling/{thermal-runs,
# results_table.csv,SUMMARY.md} into scaling/rep<NN>/. Idempotent-safe: target
# rep dir is created fresh; refuse to clobber an existing populated rep dir.
# ===========================================================================
move_rep_output() {
    local sdir="$1" rep="$2"
    local repdir; repdir="$(printf '%s/rep%02d' "$sdir" "$rep")"
    mkdir -p "$repdir"
    local moved=0
    for item in thermal-runs results_table.csv SUMMARY.md; do
        if [[ -e "$sdir/$item" ]]; then
            mv "$sdir/$item" "$repdir/" && moved=$((moved + 1))
        fi
    done
    log "  rep$(printf '%02d' "$rep"): moved $moved artifact(s) → $repdir"
}

# ===========================================================================
# ETA bookkeeping — one "run" = one full N-ladder for one (model, rep).
# ===========================================================================
T_START_GLOBAL=$(date +%s)
TOTAL_LADDERS=$(( ${#MODEL_DIRS[@]} * REPS ))
LADDERS_DONE=0

log "============================================================"
log "Phase 2 RERUN — Llama-PLLuM-70B AWQ family, n=$REPS reps/cell"
log "Models:     ${MODEL_DIRS[*]}"
log "TP:         $TP   (70B AWQ ~37 GB — TP=2 only)"
log "N ladder:   $N_LADDER_CSV   (original 7-point — faithful, NOT Run-3)"
log "Reps:       $REPS    max_len: $MAX_LEN    util: $UTIL    quant: $QUANT"
log "Total full-ladder runs: $TOTAL_LADDERS   (${#MODEL_DIRS[@]} models × $REPS reps)"
log "Inter-rep cooldown: ${INTER_REP_COOLDOWN_S}s (inner per-N cooldown owned by runner = 15s)"
log "Primitive: $RUNNER  (path-based; run_concurrent.py untouched)"
log "============================================================"
progress "SWEEP_START total_ladders=$TOTAL_LADDERS"

# ===========================================================================
# Main sweep — model (outer) → rep (inner). Each rep = one full N ladder.
# ===========================================================================
for md in "${MODEL_DIRS[@]}"; do
    SDIR="$RESULTS_ROOT/$md/scaling"
    mkdir -p "$SDIR"
    log "################  MODEL: $md  ################"
    progress "MODEL_BEGIN model=$md"
    archive_preexisting "$SDIR"
    T_MODEL_START=$(date +%s)

    for ((REP=0; REP<REPS; REP++)); do
        LADDERS_DONE=$((LADDERS_DONE + 1))
        log "----  $md rep$(printf '%02d' "$REP")  [$LADDERS_DONE/$TOTAL_LADDERS]  ----"
        progress "LADDER_BEGIN model=$md rep=$REP done=$LADDERS_DONE/$TOTAL_LADDERS"
        RUN_START=$(date +%s)

        # Port cleanup BEFORE each ladder (setsid-isolated, never kills caller).
        bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true

        # 'continue' on failure: a transient HIP OOM at N=1000 must not abort the
        # whole multi-hour grid. The runner itself catches per-N timeouts (rc=124)
        # and records FAIL rows, so a single bad cell is already non-fatal; this
        # guards a hard runner crash too.
        if python3 "$RUNNER" \
            "$md" "$TP" \
            --quant "$QUANT" \
            --ns "$N_LADDER_CSV" \
            >> "$ORCHESTRATOR_LOG" 2>&1
        then
            RUN_S=$(( $(date +%s) - RUN_START ))
            log "  OK   $md rep$(printf '%02d' "$REP") full ladder (${RUN_S}s wall)"
            move_rep_output "$SDIR" "$REP"
        else
            RUN_S=$(( $(date +%s) - RUN_START ))
            log "  FAIL $md rep$(printf '%02d' "$REP") runner rc!=0 (${RUN_S}s wall) — see $ORCHESTRATOR_LOG"
            # Still move whatever partial artifacts exist so they aren't clobbered.
            move_rep_output "$SDIR" "$REP"
        fi

        # Cleanup again post-ladder, then cool down before the next rep.
        bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true

        T_NOW=$(date +%s)
        ELAPSED=$((T_NOW - T_START_GLOBAL))
        AVG_S=$((ELAPSED / LADDERS_DONE))
        REMAINING=$((TOTAL_LADDERS - LADDERS_DONE))
        ETA_S=$((AVG_S * REMAINING))
        progress "LADDER_COMPLETE model=$md rep=$REP run_s=$RUN_S elapsed_s=$ELAPSED eta_s=$ETA_S"

        if (( LADDERS_DONE < TOTAL_LADDERS )); then
            sleep "$INTER_REP_COOLDOWN_S"
        fi
    done

    T_MODEL_WALL=$(( $(date +%s) - T_MODEL_START ))
    log "################  $md DONE: ${T_MODEL_WALL}s ($((T_MODEL_WALL / 60)) min)  ################"
    progress "MODEL_COMPLETE model=$md wall_s=$T_MODEL_WALL"
done

T_TOTAL=$(( $(date +%s) - T_START_GLOBAL ))
log "============================================================"
log "70B n=$REPS rerun complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Full-ladder runs completed: $LADDERS_DONE / $TOTAL_LADDERS"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL ladders_done=$LADDERS_DONE total_ladders=$TOTAL_LADDERS"

# Sentinel for the orchestrator/monitor — mirrors Run-3 + hf-download-watchdog.
echo "DONE $(date -Iseconds) ladders=$LADDERS_DONE/$TOTAL_LADDERS wall_s=$T_TOTAL" \
    > "$SENTINEL"
log "Sentinel written: $SENTINEL"
