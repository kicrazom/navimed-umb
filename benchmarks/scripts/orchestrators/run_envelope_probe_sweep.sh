#!/usr/bin/env bash
# Envelope-only probe sweep (PUBLIC data §11.1): footprint, KV tokens, max_concurrency.
# Uses the proven probe_max_context.py (auto ctx-ladder, handles 70B fit). NO throughput,
# NO embargoed perf. Continue-on-fail per model. Fills the conc/weight/KV dashboard gaps.
set -uo pipefail
REPO=/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb
PY=/home/mozarcik/venvs/vllm/bin/python3
PROBE="$REPO/benchmarks/scripts/runners/probe_max_context.py"
GATE="$REPO/benchmarks/scripts/runners/gate1_grid.py"
OUT="$REPO/benchmarks/results/_envelope_probe"
LOG="$OUT/sweep.log"
mkdir -p "$OUT"

# "model_dir tp" — all confirmed present in ~/models (2026-06-08)
TARGETS=(
  "Llama-PLLuM-70B-base-2412-awq 2"
  "Llama-PLLuM-70B-base-2508-awq 2"
  "Llama-PLLuM-70B-chat-2412-awq 2"
  "Llama-PLLuM-70B-chat-2508-awq 2"
  "Llama-PLLuM-70B-instruct-2412-awq 2"
  "Llama-PLLuM-70B-instruct-2508-awq 2"
  "Llama-PLLuM-70B-instruct-2512-awq 2"
  "qwen25-72b-awq 2"
  "qwen36-27b 2"
  "qwen36-27b-fp8 2"
  "qwen3.5-9b 1"
)

echo "[$(date -Is)] ENVELOPE PROBE SWEEP START — ${#TARGETS[@]} models" | tee -a "$LOG"
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
  # Gate-1 grid (records outputs; human confirms coherence before any dashboard stamp)
  echo "[$(date -Is)]   gate1 $dir ..." | tee -a "$LOG"
  timeout 900 "$PY" "$GATE" "$dir" "$tp" > "$OUT/$dir.gate.log" 2>&1
  grep -h 'GATE_RESULT_JSON=' "$OUT/$dir.gate.log" 2>/dev/null | tail -1 | sed 's/.*GATE_RESULT_JSON=//' > "$OUT/$dir.gate.json"
  if [ -s "$OUT/$dir.gate.json" ]; then
    echo "[$(date -Is)]   gate1 recorded $dir (auto-coherent $(python3 -c "import json;print(json.load(open('$OUT/$dir.gate.json'))['auto_coherent_count'])" 2>/dev/null)/5 — awaiting human review)" | tee -a "$LOG"
  else
    echo "[$(date -Is)]   gate1 FAIL $dir (see $dir.gate.log)" | tee -a "$LOG"
  fi
done
echo "[$(date -Is)] ENVELOPE PROBE SWEEP DONE" | tee -a "$LOG"
date -Is > "$OUT/PROBE_COMPLETE"
