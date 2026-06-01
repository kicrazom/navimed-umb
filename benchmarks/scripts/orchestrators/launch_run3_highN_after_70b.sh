#!/usr/bin/env bash
# Chained launcher: wait for the 70B n=10 rerun to finish, then run the Run-3
# high-N extension (N={500,1000}) for the 8B/12B consumer-GPU models.
#
# Sequence: poll the 70B sentinel (read-only) → 30 s settle → exec the high-N
# sweep under systemd-inhibit. NEVER pkill/kill; the high-N sweep's own pre-flight
# refuses on stale vLLM. Paths derive from $REPO_ROOT (NOT $SCRIPT_DIR — avoids the
# _env.sh SCRIPT_DIR-clobber gotcha, even though this launcher does not source it).
#
# Arm DETACHED (survives terminal close):
#   setsid bash benchmarks/scripts/orchestrators/launch_run3_highN_after_70b.sh \
#       >benchmarks/results/_run3_highN_logs/launch.out 2>&1 < /dev/null &

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

SEVENTYB_SENTINEL="$REPO_ROOT/benchmarks/results/_pllum70b_rerun_logs/SWEEP_COMPLETE"
HIGHN_SWEEP="$REPO_ROOT/benchmarks/scripts/orchestrators/run_pllum_run3_highN_sweep.sh"
LOG_DIR="$REPO_ROOT/benchmarks/results/_run3_highN_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/launch_chain.log"
POLL_S=600

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

if [[ ! -f "$HIGHN_SWEEP" ]]; then
    log "ERROR: high-N sweep script not found: $HIGHN_SWEEP"
    exit 1
fi

log "============================================================"
log "Run-3 high-N launcher armed."
log "Waiting on 70B sentinel: $SEVENTYB_SENTINEL  (poll ${POLL_S}s)"
log "============================================================"

while [[ ! -f "$SEVENTYB_SENTINEL" ]]; do
    sleep "$POLL_S"
done

log "70B rerun sentinel detected:"
log "  $(cat "$SEVENTYB_SENTINEL" 2>/dev/null || echo '(unreadable)')"
sleep 30   # let the 70B engine fully release VRAM before loading 8B/12B

log "Launching Run-3 high-N sweep under systemd-inhibit ..."
exec systemd-inhibit \
    --what=sleep:idle \
    --who=navimed-run3-highN \
    --why="Run-3 high-N {500,1000} extension" \
    --mode=block \
    bash "$HIGHN_SWEEP"
