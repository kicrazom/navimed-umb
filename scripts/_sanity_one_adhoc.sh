#!/usr/bin/env bash
# =============================================================================
# _sanity_one_adhoc.sh — JEDEN model, TP=2, jednorazowy sanity (post-BIOS).
# Mirror 1:1 sanity_one() z sanity_sweep_pllum70b_awq.sh, ale dla 1 modelu.
# NIE committować — scratch. Flagi/metryki/klasyfikacja identyczne z harnessem.
#
# Użycie: bash scripts/_sanity_one_adhoc.sh <model_dir_name>
# =============================================================================
MDIR="${1:?podaj nazwę katalogu modelu w ~/models}"
PORT=8100
TP=2
DATE="$(date +%Y-%m-%d)"

NAVIMED_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="$HOME/models"
MODEL_PATH="$MODELS_DIR/$MDIR"
KILL_PORT="$NAVIMED_ROOT/scripts/kill_port.sh"
OUT_DIR="$NAVIMED_ROOT/logs/downloads"
RAW_LOG="$OUT_DIR/adhoc-sanity-${MDIR}-tp${TP}-${DATE}-vllm.log"
JSON_OUT="$OUT_DIR/adhoc-sanity-${MDIR}-tp${TP}-${DATE}.json"
SANITY_PROMPT="Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."

mkdir -p "$OUT_DIR"
log() { echo "[$(date +%H:%M:%S)] $*"; }

# shellcheck disable=SC1090
source ~/venvs/vllm/bin/activate
# shellcheck disable=SC1091
source "$NAVIMED_ROOT/scripts/_env.sh"
set +euo pipefail   # _env.sh włącza -euo; wyłącz by subshelle $(...) nie zabijały skryptu

if [[ ! -f "$MODEL_PATH/config.json" ]] || ! compgen -G "$MODEL_PATH/*.safetensors" >/dev/null; then
  log "[FAIL] $MDIR niekompletny (brak config.json lub *.safetensors)"; exit 1
fi

log "=== SANITY $MDIR (TP=$TP, compressed-tensors W4A16) — post-BIOS ==="
log "model_path=$MODEL_PATH  port=$PORT  raw_log=$RAW_LOG"
bash "$KILL_PORT" "$PORT"

# serve — flagi identyczne z sanity_one (§3.2 enforce_eager, §4.3 TP=2)
nohup vllm serve "$MODEL_PATH" \
  --tensor-parallel-size "$TP" --port "$PORT" \
  --max-model-len 8192 --gpu-memory-utilization 0.9 \
  --enforce-eager --served-model-name "$MDIR" \
  > "$RAW_LOG" 2>&1 &
SERVE_PID=$!
log "vllm serve PID=$SERVE_PID — czekam na readiness (timeout 10 min)…"

ready=0
for i in $(seq 1 120); do
  if curl -s --max-time 3 "localhost:$PORT/v1/models" 2>/dev/null | grep -q "$MDIR"; then
    ready=1; log "READY po ~$((i*5))s"; break
  fi
  if ! kill -0 "$SERVE_PID" 2>/dev/null; then
    log "[FAIL] proces vllm padł podczas load — patrz $RAW_LOG"; break
  fi
  sleep 5
done

verdict="FAIL"; resp_status="na"; rtime="NA"; excerpt=""
if [[ "$ready" -eq 1 ]]; then
  t0=$(date +%s.%N)
  resp=$(curl -s --max-time 90 "localhost:$PORT/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MDIR\",\"messages\":[{\"role\":\"user\",\"content\":\"$SANITY_PROMPT\"}],\"max_tokens\":128,\"temperature\":0.7}" 2>&1)
  t1=$(date +%s.%N)
  rtime=$(echo "$t1 - $t0" | bc 2>/dev/null || echo "NA")
  read -r resp_status excerpt <<<"$(echo "$resp" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin); ch=d["choices"][0]; c=(ch["message"].get("content") or "")
    if c.strip(): print("ok", c[:400].replace("\n"," "))
    else:
        ct=(d.get("usage") or {}).get("completion_tokens",0)
        print("degenerate" if ct else "parse_fail","")
except Exception: print("parse_fail","")
' 2>/dev/null)"
  [[ -z "$resp_status" ]] && resp_status="parse_fail"
  [[ "$resp_status" == "ok" ]] && verdict="PASS"

  load_s=$(grep -oP 'Model loading took [0-9.]+ GiB memory and \K[0-9.]+' "$RAW_LOG" | head -1)
  foot_g=$(grep -oP 'Model loading took \K[0-9.]+(?= GiB)' "$RAW_LOG" | head -1)
  kv_tok=$(grep -oP 'GPU KV cache size: \K[0-9,]+' "$RAW_LOG" | head -1)
  maxc=$(grep -oP 'Maximum concurrency for [0-9,]+ tokens per request: \K[0-9.]+' "$RAW_LOG" | head -1)

  python3 - "$JSON_OUT" "$MDIR" "$TP" "$verdict" "${load_s:-NA}" "${foot_g:-NA}" \
    "${kv_tok:-NA}" "${maxc:-NA}" "${rtime:-NA}" "$resp_status" "$excerpt" <<'PYEOF'
import json,sys,datetime
out,mdir,tp,verdict,load_s,foot_g,kv_tok,maxc,rtime,resp_status,excerpt=sys.argv[1:12]
json.dump({"test_type":"sanity_adhoc_postBIOS","date":datetime.date.today().isoformat(),
  "model":mdir,"tensor_parallel_size":int(tp),"quantization":"compressed-tensors",
  "enforce_eager":True,"metrics":{"model_loading_sec":load_s,"model_footprint_gib":foot_g,
  "kv_cache_tokens":kv_tok,"max_concurrency_8192tok":maxc,"sanity_response_time_sec":rtime},
  "verdict":verdict,"response_status":resp_status,"response_excerpt":excerpt,
  "orchestrated_by":"Claude Code _sanity_one_adhoc.sh (post-BIOS verify)"},
  open(out,"w"),indent=2,ensure_ascii=False)
PYEOF
  log "  $MDIR → $verdict [$resp_status] (load ${load_s:-NA}s, footprint ${foot_g:-NA}GiB, KV ${kv_tok:-NA}, maxc ${maxc:-NA}x, resp ${rtime:-NA}s)"
  log "  RESPONSE: $excerpt"
else
  log "  $MDIR → FAIL (nie osiągnął readiness)"
  echo "{\"verdict\":\"FAIL\",\"reason\":\"readiness timeout / process died\",\"raw_log\":\"$RAW_LOG\"}" > "$JSON_OUT"
fi

bash "$KILL_PORT" "$PORT"
log "cleanup done — GPU released. JSON=$JSON_OUT"
log "=== VERDICT: $verdict ==="
