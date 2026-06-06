#!/usr/bin/env bash
# =============================================================================
# launch_70b_base_after_highN_then_bielik.sh
#
# Inserts the 70B base-AWQ n=10 sweep AHEAD of the Bielik Tier-A sweep, so the
# full 8x70B AWQ family (base x{2412,2508} + instruct/chat x{2412,2508,2512})
# is completed for Paper #1 before the Phase-B Bielik follow-up runs.
#
# New chain order:  high-N (running) -> 70B base x2 -> Bielik Tier-A
#
# Sequence:
#   1. POLL for the high-N sentinel benchmarks/results/_run3_highN_logs/HIGHN_COMPLETE
#      (read-only; never touch the live high-N sweep).
#   2. 30 s settle (let high-N's 8B/12B engine release VRAM before loading 70B).
#   3. Run run_pllum70b_n10_base.sh under systemd-inhibit (block idle-suspend).
#      No smoke gate: base-AWQ uses the exact engine path as the six already
#      sanity-/sweep-passed 70B chat/instruct AWQ models.
#   4. When base completes (writes _pllum70b_base_logs/SWEEP_COMPLETE), exec the
#      Bielik launcher, which sees the already-present HIGHN_COMPLETE and runs.
#
# HARD RULES: poll is read-only (test -f); never pkill/kill. Detached launch:
#   setsid bash benchmarks/scripts/orchestrators/launch_70b_base_after_highN_then_bielik.sh \
#       >benchmarks/results/_pllum70b_base_logs/launch.out 2>&1 &
#   disown
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

HIGHN_SENTINEL="$REPO_ROOT/benchmarks/results/_run3_highN_logs/HIGHN_COMPLETE"
BASE_SWEEP="$REPO_ROOT/benchmarks/scripts/orchestrators/run_pllum70b_n10_base.sh"
BIELIK_LAUNCHER="$REPO_ROOT/benchmarks/scripts/orchestrators/launch_bielik_tierA_after_highN.sh"

LOG_DIR="$REPO_ROOT/benchmarks/results/_pllum70b_base_logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launch_chain.log"
POLL_S=600

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LAUNCH_LOG"; }

[[ -f "$BASE_SWEEP" ]]      || { log "ERROR: base sweep missing: $BASE_SWEEP"; exit 1; }
[[ -f "$BIELIK_LAUNCHER" ]] || { log "ERROR: bielik launcher missing: $BIELIK_LAUNCHER"; exit 1; }

log "============================================================"
log "70B base -> Bielik chain armed."
log "Waiting on high-N sentinel: $HIGHN_SENTINEL  (poll ${POLL_S}s)"
log "============================================================"

while [[ ! -f "$HIGHN_SENTINEL" ]]; do
    sleep "$POLL_S"
done
log "high-N sentinel detected:"
log "  $(cat "$HIGHN_SENTINEL" 2>/dev/null || echo '(unreadable)')"

sleep 30   # let the 8B/12B engine fully release VRAM before loading 70B base

log "Launching 70B base x2 n=10 sweep under systemd-inhibit ..."
systemd-inhibit \
    --what=sleep:idle \
    --who=navimed-70b-base \
    --why="70B PLLuM base-AWQ n=10 sweep (complete 8x70B family)" \
    --mode=block \
    bash "$BASE_SWEEP"
BASE_RC=$?
log "70B base sweep returned rc=$BASE_RC."

log "Chaining Bielik Tier-A launcher (sees existing HIGHN_COMPLETE -> runs) ..."
exec setsid bash "$BIELIK_LAUNCHER" \
    > "$REPO_ROOT/benchmarks/results/_bielik_tierA_logs/launch.out" 2>&1
