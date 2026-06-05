#!/usr/bin/env bash
# =============================================================================
# launch_bielik_highN_after_tierA.sh
#
# CHAINED launcher: wait for the running Bielik Tier-A {5..250} sweep to finish,
# then run the Bielik HIGH-N {500,1000} extension so every Polish Bielik variant
# ends up on the same uniform 8-point N ladder as the 70B family and the 8B/12B
# PLLuM AWQ models (which already carry n500/n1000).
#
# Sequence:
#   1. POLL for the Tier-A sentinel
#        benchmarks/results/_bielik_tierA_logs/SWEEP_COMPLETE
#      (loop, sleep 600 s, read-only test -f). Do NOT touch the live sweep.
#   2. Once present → 30 s settle (let the Tier-A engine release VRAM).
#   3. exec the FULL run_bielik_tierA_highN_sweep.sh wrapped in systemd-inhibit
#      (sleep:idle blocked) so the overnight/morning extension survives suspend.
#      exec replaces this process so the inhibit lock is held for the whole run.
#
# NO smoke gate: the four variants are already proven by the live {5..250} sweep,
# and an N=5 smoke would not validate the N=1000 regime anyway. OOM at N=1000 is
# caught by the harness (catch_timeout → rc=124) and never aborts the sweep.
#
# HARD RULES: never pkill/kill. Poll is read-only. The high-N sweep's own
# pre-flight REFUSES on stale vllm.
#
# Paths: $REPO_ROOT is captured BEFORE `source _env.sh` (which CLOBBERS
# SCRIPT_DIR), so all sibling-script paths derive from $REPO_ROOT.
#
# Arm DETACHED:
#   setsid bash benchmarks/scripts/orchestrators/launch_bielik_highN_after_tierA.sh \
#       >/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/benchmarks/results/_bielik_tierA_highN_logs/launch.out 2>&1 < /dev/null &
#   disown
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

TIERA_SENTINEL="$REPO_ROOT/benchmarks/results/_bielik_tierA_logs/SWEEP_COMPLETE"
HIGHN_SWEEP="$REPO_ROOT/benchmarks/scripts/orchestrators/run_bielik_tierA_highN_sweep.sh"

LOG_DIR="$REPO_ROOT/benchmarks/results/_bielik_tierA_highN_logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launch_chain.log"
POLL_INTERVAL_S=600

log() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$LAUNCH_LOG"
}

# Pre-flight (no-kill): sweep script present.
if [[ ! -f "$HIGHN_SWEEP" ]]; then
    log "ERROR: high-N sweep script not found: $HIGHN_SWEEP"
    exit 1
fi

log "============================================================"
log "Bielik HIGH-N {500,1000} chained launcher armed."
log "Waiting on Tier-A sentinel: $TIERA_SENTINEL"
log "Poll interval: ${POLL_INTERVAL_S}s"
log "============================================================"

# STEP 1 — poll for the Tier-A {5..250} sentinel (read-only).
while [[ ! -f "$TIERA_SENTINEL" ]]; do
    sleep "$POLL_INTERVAL_S"
done
log "Tier-A sentinel detected:"
log "  $(cat "$TIERA_SENTINEL" 2>/dev/null || echo '(unreadable)')"

# STEP 2 — settle so the Tier-A engine fully releases VRAM.
sleep 30

# STEP 3 — exec the high-N sweep under systemd-inhibit (hold lock for whole run).
log "Launching Bielik high-N {500,1000} sweep under systemd-inhibit ..."
exec systemd-inhibit \
    --what=sleep:idle \
    --who=navimed-bielik-highN \
    --why="Bielik Tier-A high-N {500,1000} statistical sweep" \
    --mode=block \
    bash "$HIGHN_SWEEP"
