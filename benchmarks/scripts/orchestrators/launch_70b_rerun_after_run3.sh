#!/usr/bin/env bash
# =============================================================================
# launch_70b_rerun_after_run3.sh
#
# CHAINED launcher: wait for the live Run-3 sweep to finish, run ONE 70B smoke,
# and ONLY if the smoke passes, exec the full 70B n=10 rerun grid.
#
# Sequence:
#   1. POLL for the Run-3 sentinel
#        benchmarks/results/_run3_orchestrator_logs/SWEEP_COMPLETE
#      (loop, sleep ~300 s between checks) — do NOT touch the live Run-3 sweep
#      or its run_concurrent.py / bench_with_thermals.py while waiting.
#   2. Once present → run ONE 70B SMOKE: one model (chat-2412), TP=2, smallest
#      N (10), 1 rep, SHORT timeout. This validates that TP=2 + NCCL_P2P_DISABLE
#      + ~37 GB AWQ load actually works on the 2× R9700 before committing hours.
#   3. ONLY if smoke rc=0 → exec the FULL run_pllum70b_n10_rerun_sweep.sh,
#      wrapped in systemd-inhibit (sleep:idle blocked) so an overnight grid
#      survives idle-suspend.
#   4. If smoke FAILS → write 70B_RERUN_SMOKE_FAILED sentinel + exit. Do NOT
#      run the full grid.
#
# The smoke uses the SAME path primitive (throughput_scaling_phase2.py) with a
# 1-element N ladder so it exercises the exact engine path the full grid uses.
# Smoke output lands in scaling/_smoke/ (moved aside) so it never pollutes rep
# dirs. run_concurrent.py / bench_with_thermals.py are NEVER touched.
#
# HARD RULES: never pkill/kill. Poll is read-only (test -f). The full sweep's
# own pre-flight REFUSES on stale vllm.
#
# Launch DETACHED (survives terminal close) AFTER Run-3 is armed:
#   setsid bash benchmarks/scripts/orchestrators/launch_70b_rerun_after_run3.sh \
#       >/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/benchmarks/results/_pllum70b_rerun_logs/launch.out 2>&1 &
#   disown
# (The inner full sweep is itself wrapped in systemd-inhibit by this script.)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# Required for the TP=2 smoke on dual-R9700 (mirrors the full sweep).
export NCCL_P2P_DISABLE=1

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
RUN3_SENTINEL="$REPO_ROOT/benchmarks/results/_run3_orchestrator_logs/SWEEP_COMPLETE"
FULL_SWEEP="$SCRIPT_DIR/run_pllum70b_n10_rerun_sweep.sh"
RUNNER="$REPO_ROOT/benchmarks/scripts/runners/throughput_scaling_phase2.py"
KILL_PORT="$REPO_ROOT/scripts/kill_port.sh"

LOG_DIR="$REPO_ROOT/benchmarks/results/_pllum70b_rerun_logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launch_chain.log"
SMOKE_FAIL_SENTINEL="$LOG_DIR/70B_RERUN_SMOKE_FAILED"
SMOKE_OK_SENTINEL="$LOG_DIR/70B_RERUN_SMOKE_OK"

SMOKE_MODEL="Llama-PLLuM-70B-chat-2412-awq"
SMOKE_TP=2
SMOKE_N="10"                 # smallest N (single-element ladder)
POLL_INTERVAL_S=300          # ~5 min between Run-3 sentinel checks
SMOKE_TIMEOUT_S=900          # short: 70B AWQ load (~60-75 s) + N=10 gen (~55 s) ≪ 900 s

log() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$LAUNCH_LOG"
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if [[ ! -x "$FULL_SWEEP" && ! -f "$FULL_SWEEP" ]]; then
    log "ERROR: full sweep script not found: $FULL_SWEEP"
    exit 1
fi
if [[ ! -f "$RUNNER" ]]; then
    log "ERROR: path runner not found: $RUNNER"
    exit 1
fi
if [[ ! -f "$HOME/models/$SMOKE_MODEL/config.json" ]]; then
    log "ERROR: smoke model missing: $HOME/models/$SMOKE_MODEL"
    exit 1
fi

log "============================================================"
log "Chained launcher armed."
log "Waiting on Run-3 sentinel: $RUN3_SENTINEL"
log "Poll interval: ${POLL_INTERVAL_S}s"
log "Smoke: $SMOKE_MODEL TP=$SMOKE_TP N=$SMOKE_N (1 rep, timeout ${SMOKE_TIMEOUT_S}s)"
log "============================================================"

# ---------------------------------------------------------------------------
# STEP 1 — poll for the Run-3 sentinel (read-only; never touch the live sweep)
# ---------------------------------------------------------------------------
while [[ ! -f "$RUN3_SENTINEL" ]]; do
    sleep "$POLL_INTERVAL_S"
done
log "Run-3 sentinel detected:"
log "  $(cat "$RUN3_SENTINEL" 2>/dev/null || echo '(unreadable)')"

# Brief settle so the Run-3 engine fully releases VRAM before we load 70B.
sleep 30

# ---------------------------------------------------------------------------
# STEP 2 — ONE 70B smoke (single-element ladder via the path runner).
# Output goes to scaling/<runner default> then is moved to scaling/_smoke/.
# ---------------------------------------------------------------------------
SMOKE_SDIR="$REPO_ROOT/benchmarks/results/$SMOKE_MODEL/scaling"
mkdir -p "$SMOKE_SDIR"
bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true

log "Running 70B smoke ..."
SMOKE_RC=0
# timeout(1) as a hard outer bound; the runner also has its own PER_RUN_TIMEOUT.
if timeout "$SMOKE_TIMEOUT_S" python3 "$RUNNER" \
    "$SMOKE_MODEL" "$SMOKE_TP" \
    --quant compressed-tensors \
    --ns "$SMOKE_N" \
    >> "$LAUNCH_LOG" 2>&1
then
    SMOKE_RC=0
else
    SMOKE_RC=$?
fi
bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true

# Move smoke artifacts aside so they never collide with rep dirs of the full grid.
SMOKE_ARCH="$SMOKE_SDIR/_smoke"
mkdir -p "$SMOKE_ARCH"
for item in thermal-runs results_table.csv SUMMARY.md; do
    if [[ -e "$SMOKE_SDIR/$item" ]]; then
        mv "$SMOKE_SDIR/$item" "$SMOKE_ARCH/" 2>/dev/null || true
    fi
done

# Verify the smoke actually produced an OK row (rc=0 alone isn't enough — the
# runner returns 0 even if a cell FAILs; confirm an ok=True row in the CSV).
SMOKE_OK_ROW=0
if [[ -f "$SMOKE_ARCH/results_table.csv" ]]; then
    if grep -q ',True,' "$SMOKE_ARCH/results_table.csv" 2>/dev/null; then
        SMOKE_OK_ROW=1
    fi
fi

if [[ "$SMOKE_RC" -eq 0 && "$SMOKE_OK_ROW" -eq 1 ]]; then
    log "SMOKE PASS (rc=0, ok=True row present)."
    echo "SMOKE_OK $(date -Iseconds) model=$SMOKE_MODEL tp=$SMOKE_TP n=$SMOKE_N" > "$SMOKE_OK_SENTINEL"
else
    log "SMOKE FAIL (rc=$SMOKE_RC, ok_row=$SMOKE_OK_ROW) — NOT launching the full grid."
    {
        echo "SMOKE_FAILED $(date -Iseconds)"
        echo "model=$SMOKE_MODEL tp=$SMOKE_TP n=$SMOKE_N rc=$SMOKE_RC ok_row=$SMOKE_OK_ROW"
        echo "See $LAUNCH_LOG (and $SMOKE_ARCH/ if any artifacts) for diagnosis."
    } > "$SMOKE_FAIL_SENTINEL"
    exit 1
fi

# ---------------------------------------------------------------------------
# STEP 3 — exec the FULL grid, wrapped in systemd-inhibit (block idle-suspend).
# exec replaces this process so the inhibit lock is held for the whole sweep.
# ---------------------------------------------------------------------------
log "Launching full 70B n=10 rerun under systemd-inhibit ..."
exec systemd-inhibit \
    --what=sleep:idle \
    --who=navimed-70b-rerun \
    --why="70B PLLuM AWQ n=10 statistical rerun" \
    --mode=block \
    bash "$FULL_SWEEP"
