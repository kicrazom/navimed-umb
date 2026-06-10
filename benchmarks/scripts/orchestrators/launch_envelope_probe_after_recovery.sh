#!/usr/bin/env bash
# Sentinel/process-gated chain: wait for the canonical-recovery chain to finish (its launcher
# process gone), settle, then run the envelope-only probe sweep. Keeps GPU busy productively
# after recovery without manual intervention. Idle-sleep inhibited while running.
set -uo pipefail
REPO=/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb
SWEEP="$REPO/benchmarks/scripts/orchestrators/run_envelope_probe_sweep.sh"
LOGDIR="$REPO/benchmarks/results/_envelope_probe"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/chain_launcher.log"

log(){ echo "[$(date -Is)] $*" | tee -a "$LOG"; }
log "Envelope-probe chain launcher armed; waiting for canonical recovery to finish."

# wait until no canonical-recovery launcher process remains
while pgrep -f 'launch_canonical_recovery_after_v30.sh|run_bielik_pllum_canonical_recovery.sh' >/dev/null 2>&1; do
  sleep 120
done
log "Canonical recovery finished (no launcher process). Settling 90s ..."
sleep 90
log "Launching envelope probe sweep ..."
bash "$SWEEP"
log "Envelope probe chain finished."
