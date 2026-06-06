#!/usr/bin/env bash
# =============================================================================
# launch_n200_after_bielik_highN.sh
#
# CHAINED launcher: wait for the Bielik high-N {500,1000} sweep to finish, then
# run the n200 UNIFORMITY extension for the models that lack it — the four Bielik
# variants and the 8B/12B PLLuM AWQ models. This fills the paper §3.3 canonical
# point N=200 (which the 70B family already carries), so every Polish model
# covers {10,25,50,100,200,500,1000}.
#
# Sequence:
#   1. POLL for the Bielik high-N sentinel
#        benchmarks/results/_bielik_tierA_highN_logs/SWEEP_COMPLETE
#      (loop, sleep 600 s, read-only).
#   2. Once present → 30 s settle.
#   3. Run run_bielik_n200_sweep.sh under systemd-inhibit (4 Bielik × TP{1,2} ×
#      {200} × 10 = 80 runs).
#   4. 30 s settle → run run_pllum_8b12b_n200_sweep.sh under systemd-inhibit
#      (2 PLLuM × TP{1,2} × {200} × 10 = 40 runs).
#
# Each sweep has its OWN systemd-inhibit (held for its duration) and its OWN
# no-kill pre-flight (REFUSE on stale vllm). They run sequentially with a `;`
# (not &&) so the 8B/12B leg still runs even if the Bielik leg exits non-zero.
#
# HARD RULES: never pkill/kill. Poll is read-only.
#
# Paths: $REPO_ROOT captured BEFORE `source _env.sh` (which clobbers SCRIPT_DIR).
#
# Arm DETACHED:
#   setsid bash benchmarks/scripts/orchestrators/launch_n200_after_bielik_highN.sh \
#       >.../benchmarks/results/_n200_chain_logs/launch.out 2>&1 < /dev/null &
#   disown
# =============================================================================

set -uo pipefail   # NOT -e: a non-zero from the first sweep must not skip the second.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT" || exit 1

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

HIGHN_SENTINEL="$REPO_ROOT/benchmarks/results/_bielik_tierA_highN_logs/SWEEP_COMPLETE"
BIELIK_N200="$REPO_ROOT/benchmarks/scripts/orchestrators/run_bielik_n200_sweep.sh"
PLLUM_N200="$REPO_ROOT/benchmarks/scripts/orchestrators/run_pllum_8b12b_n200_sweep.sh"

LOG_DIR="$REPO_ROOT/benchmarks/results/_n200_chain_logs"
mkdir -p "$LOG_DIR"
LAUNCH_LOG="$LOG_DIR/launch_chain.log"
POLL_INTERVAL_S=600

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LAUNCH_LOG"; }

inhibit_run() {
    local who="$1" script="$2"
    log "Launching $(basename "$script") under systemd-inhibit ..."
    systemd-inhibit \
        --what=sleep:idle \
        --who="$who" \
        --why="n200 uniformity sweep" \
        --mode=block \
        bash "$script"
    log "$(basename "$script") exited rc=$?."
}

for s in "$BIELIK_N200" "$PLLUM_N200"; do
    if [[ ! -f "$s" ]]; then log "ERROR: sweep script not found: $s"; exit 1; fi
done

log "============================================================"
log "n200 uniformity chained launcher armed."
log "Waiting on Bielik high-N sentinel: $HIGHN_SENTINEL"
log "============================================================"

# STEP 1 — poll for the Bielik high-N sentinel (read-only).
while [[ ! -f "$HIGHN_SENTINEL" ]]; do
    sleep "$POLL_INTERVAL_S"
done
log "Bielik high-N sentinel detected:"
log "  $(cat "$HIGHN_SENTINEL" 2>/dev/null || echo '(unreadable)')"

sleep 30
inhibit_run "navimed-bielik-n200" "$BIELIK_N200"

sleep 30
inhibit_run "navimed-pllum-n200" "$PLLUM_N200"

log "n200 uniformity chain complete."
echo "DONE $(date -Iseconds)" > "$LOG_DIR/N200_CHAIN_COMPLETE"
