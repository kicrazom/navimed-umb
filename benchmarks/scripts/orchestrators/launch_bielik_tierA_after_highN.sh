#!/usr/bin/env bash
# =============================================================================
# launch_bielik_tierA_after_highN.sh
#
# CHAINED, SMOKE-GATED launcher: wait for the Run-3 high-N sweep to finish, run
# ONE Bielik smoke, and ONLY if the smoke passes, exec the full Bielik Tier-A
# n=10 sweep.
#
# Sequence:
#   1. POLL for the high-N sentinel
#        benchmarks/results/_run3_highN_logs/HIGHN_COMPLETE
#      (loop, sleep 600 s between checks) — read-only (test -f). Do NOT touch
#      the live high-N sweep or its run_concurrent.py / bench_with_thermals.py
#      while waiting.
#   2. Once present → 30 s settle (let the high-N engine release VRAM) → run ONE
#      Bielik SMOKE: smallest variant (bielik-4.5b-v30), TP=1, smallest N (5),
#      1 rep, SHORT timeout. This validates the offline LLM.generate path on the
#      2× R9700 before committing the full grid.
#   3. Smoke PASS requires BOTH: rc=0 AND an "Output throughput" line present in
#      the smoke bench.log (rc=0 alone isn't enough — bench_with_thermals exits 0
#      on a caught timeout/rc, so confirm real throughput was produced).
#   4. ONLY if smoke passes → exec the FULL run_bielik_tierA_n10_sweep.sh wrapped
#      in systemd-inhibit (sleep:idle blocked) so an overnight grid survives
#      idle-suspend. exec replaces this process so the inhibit lock is held for
#      the whole sweep.
#   5. If smoke FAILS → write BIELIK_TIERA_SMOKE_FAILED sentinel + exit. Do NOT
#      run the full grid.
#
# Smoke output lands in <result>/thermal-runs/_smoke/ (moved aside) so it never
# pollutes the rep dirs the full sweep will write.
#
# HARD RULES: never pkill/kill. Poll is read-only. The full sweep's own
# pre-flight REFUSES on stale vllm.
#
# Paths: $REPO_ROOT is captured BEFORE `source _env.sh`. _env.sh CLOBBERS
# SCRIPT_DIR (sets its own SCRIPT_DIR=.../scripts), so ALL sibling-script paths
# derive from $REPO_ROOT, never $SCRIPT_DIR. (This bit the 70B launcher.)
#
# Arm DETACHED (survives terminal close) AFTER high-N is armed:
#   setsid bash benchmarks/scripts/orchestrators/launch_bielik_tierA_after_highN.sh \
#       >/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/benchmarks/results/_bielik_tierA_logs/launch.out 2>&1 < /dev/null &
#   disown
# (The inner full sweep is itself wrapped in systemd-inhibit by this script.)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# ---------------------------------------------------------------------------
# Paths / config — all derived from $REPO_ROOT (NOT $SCRIPT_DIR; _env.sh
# clobbered it above).
# ---------------------------------------------------------------------------
HIGHN_SENTINEL="$REPO_ROOT/benchmarks/results/_run3_highN_logs/HIGHN_COMPLETE"
FULL_SWEEP="$REPO_ROOT/benchmarks/scripts/orchestrators/run_bielik_tierA_n10_sweep.sh"
BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"

LOG_DIR="$REPO_ROOT/benchmarks/results/_bielik_tierA_logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launch_chain.log"
SMOKE_FAIL_SENTINEL="$LOG_DIR/BIELIK_TIERA_SMOKE_FAILED"
SMOKE_OK_SENTINEL="$LOG_DIR/BIELIK_TIERA_SMOKE_OK"

# Smoke = smallest, fastest Bielik variant so the gate is quick and cheap.
SMOKE_KEY="bielik-4.5b-v30"
SMOKE_QUANT="bf16"
SMOKE_RESULT_DIR="bielik-4.5b-v30"
SMOKE_MODEL_PATH="/home/mozarcik/models/bielik-4.5b-v30"
SMOKE_TP=1
SMOKE_N=5                     # smallest N in the ladder (single cell, 1 rep)
SMOKE_MAX_LEN=8192
SMOKE_UTIL=0.90
POLL_INTERVAL_S=600           # 10 min between high-N sentinel checks
SMOKE_TIMEOUT_S=600           # 4.5B BF16 load (~10-20 s) + N=5 gen (~5-10 s) ≪ 600 s

log() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$LAUNCH_LOG"
}

# ---------------------------------------------------------------------------
# Pre-flight (no-kill): scripts + smoke model present.
# ---------------------------------------------------------------------------
if [[ ! -x "$FULL_SWEEP" && ! -f "$FULL_SWEEP" ]]; then
    log "ERROR: full sweep script not found: $FULL_SWEEP"
    exit 1
fi
if [[ ! -f "$BENCH" ]]; then
    log "ERROR: bench wrapper not found: $BENCH"
    exit 1
fi
if [[ ! -f "$SMOKE_MODEL_PATH/config.json" ]]; then
    log "ERROR: smoke model missing: $SMOKE_MODEL_PATH"
    exit 1
fi

# No-kill stale-process guard: REFUSE if a vllm/run_concurrent is already up
# (mirrors the full sweep's policy; we never pkill).
stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py (bielik-11b|bielik-4.5b-v30|bielik-pl-11b-v30-instruct|bielik-11b-v30-instruct-awq)' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    log "ERROR: stale vllm/run_concurrent present — refusing to arm smoke:"
    log "$stale_pids"
    exit 1
fi

log "============================================================"
log "Bielik Tier-A chained launcher armed (smoke-gated)."
log "Waiting on high-N sentinel: $HIGHN_SENTINEL"
log "Poll interval: ${POLL_INTERVAL_S}s"
log "Smoke: $SMOKE_KEY ($SMOKE_QUANT) TP=$SMOKE_TP N=$SMOKE_N (1 rep, timeout ${SMOKE_TIMEOUT_S}s)"
log "============================================================"

# ---------------------------------------------------------------------------
# STEP 1 — poll for the high-N sentinel (read-only; never touch the live sweep)
# ---------------------------------------------------------------------------
while [[ ! -f "$HIGHN_SENTINEL" ]]; do
    sleep "$POLL_INTERVAL_S"
done
log "High-N sentinel detected:"
log "  $(cat "$HIGHN_SENTINEL" 2>/dev/null || echo '(unreadable)')"

# Brief settle so the high-N engine fully releases VRAM before we load Bielik.
sleep 30

# ---------------------------------------------------------------------------
# STEP 2 — ONE Bielik smoke via bench_with_thermals.py (same inner path the
# full sweep uses). Output goes to the smoke result dir, then is moved aside.
# ---------------------------------------------------------------------------
SMOKE_OUT="$REPO_ROOT/benchmarks/results/$SMOKE_RESULT_DIR/thermal-runs"
mkdir -p "$SMOKE_OUT"
SMOKE_NAME="$(printf 'smoke-%s-tp%d-n%d-r00' "$SMOKE_QUANT" "$SMOKE_TP" "$SMOKE_N")"
SMOKE_BENCH_LOG="$SMOKE_OUT/${SMOKE_NAME}-bench.log"

log "Running Bielik smoke ($SMOKE_KEY $SMOKE_QUANT TP=$SMOKE_TP N=$SMOKE_N) ..."
SMOKE_RC=0
if python3 "$BENCH" \
    "$SMOKE_KEY" "$SMOKE_TP" "$SMOKE_N" \
    --quant "$SMOKE_QUANT" \
    --max-len "$SMOKE_MAX_LEN" \
    --util "$SMOKE_UTIL" \
    --name "$SMOKE_NAME" \
    --out-dir "$SMOKE_OUT" \
    --interval 1.0 \
    --timeout "$SMOKE_TIMEOUT_S" \
    >> "$LAUNCH_LOG" 2>&1
then
    SMOKE_RC=0
else
    SMOKE_RC=$?
fi

# Verify the smoke produced REAL throughput (rc=0 alone isn't enough —
# bench_with_thermals exits 0 on a caught timeout too; confirm a throughput
# line is present in the bench.log).
SMOKE_HAS_TPUT=0
if [[ -f "$SMOKE_BENCH_LOG" ]] && grep -q "Output throughput" "$SMOKE_BENCH_LOG" 2>/dev/null; then
    SMOKE_HAS_TPUT=1
fi

# Move smoke artifacts aside so they never collide with the full sweep's rep
# files (the full sweep writes <quant>-tp1-n5-r00..r09; smoke uses a 'smoke-'
# prefix already, but archive it to be safe).
SMOKE_ARCH="$SMOKE_OUT/_smoke"
mkdir -p "$SMOKE_ARCH"
for ext in bench.log events.json thermals.jsonl thermals.png; do
    if [[ -e "$SMOKE_OUT/${SMOKE_NAME}-${ext}" ]]; then
        mv "$SMOKE_OUT/${SMOKE_NAME}-${ext}" "$SMOKE_ARCH/" 2>/dev/null || true
    fi
done

if [[ "$SMOKE_RC" -eq 0 && "$SMOKE_HAS_TPUT" -eq 1 ]]; then
    log "SMOKE PASS (rc=0, 'Output throughput' line present)."
    echo "SMOKE_OK $(date -Iseconds) key=$SMOKE_KEY quant=$SMOKE_QUANT tp=$SMOKE_TP n=$SMOKE_N" \
        > "$SMOKE_OK_SENTINEL"
else
    log "SMOKE FAIL (rc=$SMOKE_RC, has_throughput=$SMOKE_HAS_TPUT) — NOT launching the full grid."
    {
        echo "SMOKE_FAILED $(date -Iseconds)"
        echo "key=$SMOKE_KEY quant=$SMOKE_QUANT tp=$SMOKE_TP n=$SMOKE_N rc=$SMOKE_RC has_throughput=$SMOKE_HAS_TPUT"
        echo "See $LAUNCH_LOG (and $SMOKE_ARCH/ for the smoke bench.log) for diagnosis."
    } > "$SMOKE_FAIL_SENTINEL"
    exit 1
fi

# ---------------------------------------------------------------------------
# STEP 3 — exec the FULL grid, wrapped in systemd-inhibit (block idle-suspend).
# exec replaces this process so the inhibit lock is held for the whole sweep.
# ---------------------------------------------------------------------------
log "Launching full Bielik Tier-A n=10 sweep under systemd-inhibit ..."
exec systemd-inhibit \
    --what=sleep:idle \
    --who=navimed-bielik-tierA \
    --why="Bielik Tier-A n=10 statistical sweep" \
    --mode=block \
    bash "$FULL_SWEEP"
