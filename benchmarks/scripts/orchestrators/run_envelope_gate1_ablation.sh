#!/usr/bin/env bash
# Envelope probe + Gate-1 for the 3 NEW precision-ablation AWQ quants (Faza 1/2,
# PLAN-2026-06-30). Envelope = PUBLIC §11.1 (footprint, KV tokens, max_concurrency);
# Gate-1 records 5 clinical completions (human confirms coherence, no auto-stamp).
# Mirrors run_envelope_probe_sweep.sh (proven), swapped TARGETS. Continue-on-fail.
set -uo pipefail
REPO=/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb
PY=/home/mozarcik/venvs/vllm/bin/python3
PROBE="$REPO/benchmarks/scripts/runners/probe_max_context.py"
GATE="$REPO/benchmarks/scripts/runners/gate1_grid.py"
OUT="$REPO/benchmarks/results/_ablation_envelope_gate1"
LOG="$OUT/sweep.log"
mkdir -p "$OUT"

# "model_dir tp" — fresh AWQ quants (30.06→01.07), all fit TP=1
TARGETS=(
  "bielik-4.5b-v30-awq 1"
  "qwen25-7b-instruct-awq 1"
  "mistral-nemo-instruct-2407-awq 1"
)

echo "[$(date -Is)] ABLATION ENVELOPE+GATE1 START — ${#TARGETS[@]} models" | tee -a "$LOG"
i=0
for t in "${TARGETS[@]}"; do
  # shellcheck disable=SC2086 # intentional word-split: "dir tp" pair → positional params
  set -- $t; dir="$1"; tp="$2"; i=$((i+1))
  if [ ! -d "$HOME/models/$dir" ]; then echo "[$(date -Is)] [$i/${#TARGETS[@]}] SKIP missing $dir" | tee -a "$LOG"; continue; fi
  echo "[$(date -Is)] [$i/${#TARGETS[@]}] probe $dir tp=$tp ..." | tee -a "$LOG"
  timeout 1200 "$PY" "$PROBE" "$dir" "$tp" > "$OUT/$dir.probe.log" 2>&1
  grep -h 'PROBE_RESULT_JSON=' "$OUT/$dir.probe.log" 2>/dev/null | tail -1 | sed 's/.*PROBE_RESULT_JSON=//' > "$OUT/$dir.json"
  if [ -s "$OUT/$dir.json" ]; then
    echo "[$(date -Is)]   envelope OK $dir -> $(cat "$OUT/$dir.json")" | tee -a "$LOG"
  else
    echo "[$(date -Is)]   envelope FAIL $dir (see $dir.probe.log)" | tee -a "$LOG"
  fi
  echo "[$(date -Is)]   gate1 $dir ..." | tee -a "$LOG"
  timeout 900 "$PY" "$GATE" "$dir" "$tp" > "$OUT/$dir.gate.log" 2>&1
  grep -h 'GATE_RESULT_JSON=' "$OUT/$dir.gate.log" 2>/dev/null | tail -1 | sed 's/.*GATE_RESULT_JSON=//' > "$OUT/$dir.gate.json"
  if [ -s "$OUT/$dir.gate.json" ]; then
    echo "[$(date -Is)]   gate1 recorded $dir (auto-coherent $(python3 -c "import json;print(json.load(open('$OUT/$dir.gate.json'))['auto_coherent_count'])" 2>/dev/null)/5 — awaiting human review)" | tee -a "$LOG"
  else
    echo "[$(date -Is)]   gate1 FAIL $dir (see $dir.gate.log)" | tee -a "$LOG"
  fi
done
echo "[$(date -Is)] ABLATION ENVELOPE+GATE1 DONE" | tee -a "$LOG"
date -Is > "$OUT/PROBE_COMPLETE"
