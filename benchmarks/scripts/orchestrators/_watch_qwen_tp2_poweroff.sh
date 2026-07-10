#!/usr/bin/env bash
# Detached overnight watcher: wait for the Qwen TP2 sweep sentinel, then power off.
# Authorised explicitly by Łukasz 2026-07-05 ("jak skończy obliczenia wyłącz komputer").
# Runs OUTSIDE the Claude session (setsid) so it survives session end and does the
# shutdown itself. If the sweep dies without a sentinel, this waits forever and the
# machine stays ON (safe: never shuts down mid-compute or on a crash).
set -uo pipefail
SENT="/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/benchmarks/results/_qwen35_tp2_logs/SWEEP_COMPLETE"
LOG="/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/benchmarks/results/_qwen35_tp2_logs/poweroff_watch.log"
mkdir -p "$(dirname "$LOG")"
echo "[watch $(date -Is)] armed; waiting for $SENT" >> "$LOG"
while [[ ! -f "$SENT" ]]; do sleep 60; done
{ echo "[watch $(date -Is)] sentinel present:"; cat "$SENT" 2>&1; } >> "$LOG"
echo "[watch $(date -Is)] flushing disks (sync), 45s grace" >> "$LOG"
sync; sleep 45
echo "[watch $(date -Is)] powering off now" >> "$LOG"
systemctl poweroff       >> "$LOG" 2>&1 && exit 0
echo "[watch $(date -Is)] plain poweroff failed, trying -i" >> "$LOG"
systemctl -i poweroff    >> "$LOG" 2>&1 && exit 0
echo "[watch $(date -Is)] POWEROFF FAILED (no polkit/priv) — machine stays ON, sweep is done" >> "$LOG"
exit 1
