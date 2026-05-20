#!/usr/bin/env bash
# =============================================================================
# kill_port.sh — izolowany cleanup procesów na porcie.
#
# Problem: `kill`/`pkill` w komendzie ad-hoc propaguje sygnał przez
# process-group i ucina proces wywołujący (exit 144). `pkill -f` dodatkowo
# łapie własną komendę (collateral kill — Debug-watch forbidden).
#
# Rozwiązanie: każdy kill leci w `setsid` (nowa sesja — sygnał NIE wraca do
# callera) + w tle. Skrypt zawsze `exit 0` — cleanup nie wywraca automatyzacji.
#
# Użycie:  bash scripts/kill_port.sh [PORT]      (domyślnie 8100)
# =============================================================================
PORT="${1:-8100}"

# PID-y nasłuchujące na porcie (ss) + procesy vllm serve na tym porcie (pgrep)
pids=$(
  { ss -ltnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+'
    pgrep -f "vllm serve.*--port $PORT" 2>/dev/null
  } | sort -u
)

for pid in $pids; do
  # setsid → kill w odrębnej sesji; gentle TERM, po 3 s twardy KILL; całość w tle
  setsid sh -c "kill $pid 2>/dev/null; sleep 3; kill -9 $pid 2>/dev/null" &
done

# Daj procesom czas na zwolnienie portu/VRAM
sleep 5
exit 0
