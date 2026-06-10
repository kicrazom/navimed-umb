#!/usr/bin/env bash
# Sentinel-gated chain: wait for the Bielik v3.0 refresh re-run to finish, THEN
# run the canonical-ladder gap recovery. Sequential by design — the bug being
# recovered from was a GPU collision between overlapping sweeps, so the recovery
# must NOT start while v3.0 still holds the GPU.
#
# Run under systemd-inhibit (no idle-suspend) so the whole wait+run survives:
#   systemd-inhibit --what=sleep:idle --who=navimed-canonical-recovery \
#       --why="Bielik/PLLuM canonical gap recovery (chained after v3.0)" --mode=block \
#       bash benchmarks/scripts/orchestrators/launch_canonical_recovery_after_v30.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

V30_SENTINEL="$REPO_ROOT/benchmarks/results/_bielik_v30_refresh_rerun_logs/SWEEP_COMPLETE"
RECOVERY="$SCRIPT_DIR/run_bielik_pllum_canonical_recovery.sh"
LOG_DIR="$REPO_ROOT/benchmarks/results/_canonical_recovery_logs"
CHAIN_LOG="$LOG_DIR/chain_launcher.log"
POLL_S=600

mkdir -p "$LOG_DIR"
log() { echo "[$(date -Iseconds)] $*" | tee -a "$CHAIN_LOG"; }

log "============================================================"
log "Canonical recovery chain launcher armed."
log "Waiting on v3.0 sentinel: $V30_SENTINEL"
log "Poll interval: ${POLL_S}s"
log "============================================================"

while [[ ! -f "$V30_SENTINEL" ]]; do
    sleep "$POLL_S"
done

log "v3.0 sentinel detected:"
log "  $(cat "$V30_SENTINEL")"

# Safety settle: let vLLM fully tear down + VRAM free before the recovery
# preflight runs (recovery also refuses-on-stale as a second guard).
log "Settling 60s before recovery launch ..."
sleep 60

log "Launching canonical gap recovery ..."
bash "$RECOVERY"
log "Canonical recovery chain finished."
