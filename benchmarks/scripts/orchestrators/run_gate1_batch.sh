#!/usr/bin/env bash
# NaviMed-UMB — Gate-1 batch (PLLuM 70B family + Qwen baselines/smoke).
#
# Runs gate1_grid.py per model: loads vLLM offline, emits the 5 Polish clinical
# completions (METHODOLOGY §4.3) as GATE_RESULT_JSON. The model LOAD doubles as a
# gfx1201 feasibility smoke — a model that OOMs / kernel-fails is recorded as
# "not deployable" and the batch continues (Mixtral/Kimi precedent).
#
# gate_stamp stays null — the public "5/5" is a CLINICAL coherence judgement that
# Łukasz confirms before any dashboard cell is set.
#
# GPU hygiene between models: free-VRAM gate + setsid teardown of leaked KFD
# holders (never pkill -f, per memory feedback_kill_isolation).
#
# Output: benchmarks/results/_gate1_batch/<model_dir>.json (+ orchestrator log).
# SCRIPT public §11.1; outputs are clinical completions §11.1 (envelope).

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT" || exit 1
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

GATE="$REPO_ROOT/benchmarks/scripts/runners/gate1_grid.py"
OUT="$REPO_ROOT/benchmarks/results/_gate1_batch"
LOG="$OUT/orchestrator.log"
mkdir -p "$OUT"
MAX_LEN=4096
MIN_FREE_GIB=29
CLEAR_TRIES=6
SETTLE=10
PER_MODEL_TIMEOUT=900

# (model_dir under ~/models : TP)  — PLLuM 70B AWQ ×8 (missing gate) + Qwen baselines
MODELS=(
  "Llama-PLLuM-70B-base-2412-awq:2"
  "Llama-PLLuM-70B-base-2508-awq:2"
  "Llama-PLLuM-70B-chat-2412-awq:2"
  "Llama-PLLuM-70B-chat-2508-awq:2"
  "Llama-PLLuM-70B-chat-2512-awq:2"
  "Llama-PLLuM-70B-instruct-2412-awq:2"
  "Llama-PLLuM-70B-instruct-2508-awq:2"
  "Llama-PLLuM-70B-instruct-2512-awq:2"
  "qwen3.5-9b:1"
  "qwen25-72b-awq:2"
  "qwen3.6-35b-a3b-fp8:2"
)

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

free_gib() {
  rocm-smi --showmeminfo vram --json 2>/dev/null | python3 -c '
import json,sys
i=int(sys.argv[1])
try:
    d=json.load(sys.stdin); c=d[f"card{i}"]
    print(int((int(c["VRAM Total Memory (B)"])-int(c["VRAM Total Used Memory (B)"]))//(1024**3)))
except Exception: print(0)
' "$1"
}
kfd_pids() { rocm-smi --showpids 2>/dev/null | awk '/^[0-9]+[[:space:]]/{print $1}'; }
clear_gpu() {
  local tp="$1" t pids pid
  for ((t=1;t<=CLEAR_TRIES;t++)); do
    local f0 f1; f0=$(free_gib 0); f1=$(free_gib 1)
    if (( f0>=MIN_FREE_GIB )) && { [[ "$tp" != "2" ]] || (( f1>=MIN_FREE_GIB )); }; then return 0; fi
    pids="$(kfd_pids)"
    if [[ -n "$pids" ]]; then
      log "  clear_gpu: kill KFD [$(echo "$pids"|tr '\n' ' ')] (free0=$f0 free1=$f1, try $t)"
      for pid in $pids; do setsid sh -c "kill -9 $pid 2>/dev/null" & done
    fi
    sleep "$SETTLE"
  done
  return 1
}

# pre-flight
stale="$(pgrep -af 'vllm serve|gate1_grid.py|run_concurrent.py|bench_with_thermals.py' 2>/dev/null || true)"
[[ -n "$stale" ]] && { echo "ERROR: vllm/bench present — refuse:" >&2; echo "$stale" >&2; exit 1; }
python3 -c "import vllm" 2>/dev/null || { echo "ERROR: vllm import failed (venv?)" >&2; exit 1; }

log "============================================================"
log "Gate-1 batch — ${#MODELS[@]} models (load=feasibility smoke; gate_stamp=null→human)"
log "============================================================"

ok=0; broken=0
for entry in "${MODELS[@]}"; do
  MD="${entry%%:*}"; TP="${entry##*:}"
  RESULT="$OUT/${MD}.json"
  log "----  $MD (TP=$TP)  ----"
  if ! clear_gpu "$TP"; then log "  SKIP $MD — GPU unclearable"; continue; fi
  rc=0
  timeout --signal=TERM --kill-after=30 "$PER_MODEL_TIMEOUT" \
    python3 "$GATE" "$MD" "$TP" --max-len "$MAX_LEN" > "$OUT/${MD}.stdout" 2> "$OUT/${MD}.stderr" || rc=$?
  if (( rc==0 )) && grep -q "GATE_RESULT_JSON=" "$OUT/${MD}.stdout"; then
    grep "GATE_RESULT_JSON=" "$OUT/${MD}.stdout" | sed 's/^GATE_RESULT_JSON=//' > "$RESULT"
    ac=$(python3 -c "import json;print(json.load(open('$RESULT'))['auto_coherent_count'])" 2>/dev/null || echo "?")
    log "  OK  $MD — auto_coherent=$ac/5 (human review pending) → $RESULT"
    ok=$((ok+1))
  else
    log "  BROKEN $MD (rc=$rc) — likely not deployable on gfx1201; see ${MD}.stderr"
    broken=$((broken+1))
  fi
  if (( $(free_gib 0) < MIN_FREE_GIB )); then clear_gpu "$TP" || true; fi
  sleep 5
done

log "============================================================"
log "Gate-1 batch DONE: $ok ok, $broken broken/not-deployable"
log "============================================================"
echo "DONE $(date -Iseconds) ok=$ok broken=$broken" > "$OUT/BATCH_COMPLETE"
