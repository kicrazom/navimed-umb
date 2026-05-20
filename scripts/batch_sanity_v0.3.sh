#!/usr/bin/env bash
# =============================================================================
# batch_sanity_v0.3.sh
# Sekwencyjny sanity envelope dla modeli navimed Phase 2 v0.3 bez sanity recordu.
#
# Per model: launch vllm serve -> poll /v1/models -> curl sanity prompt ->
# capture metryk z log -> targeted kill APIServer PID -> JSON record + raw log.
#
# METHODOLOGY-compliant: env via _env.sh, enforce_eager (suite-wide conservative
# default §3.2), embargo PUBLIC §11.1 (load/VRAM/KV/max_concurrency/response).
# Idempotent: model z istniejącym JSON recordem jest pomijany.
#
# NIE pkill -f (Debug-watch forbidden) — kill po konkretnym PID/porcie.
# =============================================================================
# NIE set -e/-u/pipefail — batch musi przeżyć błędy pojedynczych modeli
# (pgrep no-match, venv activate edge cases) i kontynuować kolejne.
set +e

NAVIMED_ROOT="/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb"  # pragma: allowlist secret
MODELS_DIR="$HOME/models"
SANITY_DIR="$NAVIMED_ROOT/environment/sanity-tests"
PORT=8100
DATE=$(date +%Y-%m-%d)
PROGRESS_LOG="$NAVIMED_ROOT/logs/downloads/batch-sanity-${DATE}.log"
SANITY_PROMPT="Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."

cd "$NAVIMED_ROOT" || exit 1
mkdir -p "$SANITY_DIR" "$(dirname "$PROGRESS_LOG")"

# format: "model_dir|TP|extra_flags"  (wszystkie dostają --enforce-eager)
# TYLKO modele bez ŻADNEGO testu (sanity/envelope/sweep/benchmarks-results).
# WYKLUCZONE jako już-testowane: qwen2.5-7b, qwen2.5-72b-awq, qwen36-27b,
# qwen36-27b-fp8, bielik-11b-v23, bielik-4.5b-v30, bielik-11b-v30, bielik-pl-11b-v30.
# WYKLUCZONE: qwen3.5-9b (FAIL — Qwen3_5Config unsupported w transformers/vLLM 0.19).
MODELS=(
  "qwen3.5-9b|1|"
  "bielik-11b-v23-awq|1|"
  "bielik-11b-v30-instruct-awq|1|"
  "llama-pllum-8b-instruct|1|"
  "pllum-12b-chat|1|"
  "mistral-nemo-instruct-2407|1|"
  "mixtral-8x7b-awq|2|"
  "llama-pllum-70b-base|2|"
  "llama-pllum-70b-instruct|2|"
  "llama-pllum-70b-chat|2|"
  "llama-pllum-70b-base-250801|2|"
  "llama-pllum-70b-chat-250801|2|"
  "kimi-dev-72b|2|--quantization awq_marlin"
  "kimi-linear-48b-a3b-instruct|2|--no-enable-prefix-caching"
)

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$PROGRESS_LOG"; }

# Kill vllm na porcie PORT po konkretnym PID (NIE pkill -f).
kill_vllm() {
  local pids
  pids=$(ss -ltnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u)
  for p in $pids; do
    kill "$p" 2>/dev/null
  done
  # APIServer fork — znajdź po dokładnym wzorcu cmdline, kill po PID
  for p in $(pgrep -f "vllm serve.*--port $PORT" 2>/dev/null); do
    kill "$p" 2>/dev/null
  done
  sleep 6
}

# shellcheck disable=SC1090  # venv activate path is non-constant by design
source ~/venvs/vllm/bin/activate
# shellcheck disable=SC1091  # _env.sh resolved at runtime, not a build input
source "$NAVIMED_ROOT/scripts/_env.sh"
# _env.sh włącza `set -euo pipefail` — wyłącz: set -u zabija subshelle $(...)
# bo harness shell-snapshot (line 129) ma niezabezpieczony $ZSH_VERSION.
set +euo pipefail

log "=== BATCH SANITY v0.3 START — ${#MODELS[@]} modeli w kolejce ==="

for entry in "${MODELS[@]}"; do
  IFS='|' read -r mdir tp extra <<< "$entry"
  model_path="$MODELS_DIR/$mdir"
  json_out="$SANITY_DIR/${DATE}-${mdir}-tp${tp}.json"
  raw_log="$SANITY_DIR/${DATE}-${mdir}-vllm-tp${tp}.log"

  if [[ -f "$json_out" ]]; then
    log "[skip] $mdir — JSON record już istnieje"
    continue
  fi
  if [[ ! -f "$model_path/config.json" ]]; then
    log "[skip] $mdir — brak config.json (model nie pobrany?)"
    continue
  fi

  log "--- $mdir (TP=$tp ${extra:-}) ---"
  kill_vllm

  # shellcheck disable=SC2086  # intentional word splitting of extra_flags
  nohup vllm serve "$model_path" \
    --tensor-parallel-size "$tp" --port "$PORT" \
    --max-model-len 8192 --gpu-memory-utilization 0.9 \
    --enforce-eager --served-model-name "$mdir" $extra \
    > "$raw_log" 2>&1 &

  # Poll readiness — timeout 10 min (duże 70B ładują się długo)
  ready=0
  for i in $(seq 1 120); do
    if curl -s --max-time 3 "localhost:$PORT/v1/models" 2>/dev/null | grep -q "$mdir"; then
      ready=1; log "  ready po ~$((i*5))s"; break
    fi
    # wczesny abort jeśli proces padł
    if ! pgrep -f "vllm serve.*$mdir" >/dev/null 2>&1; then
      log "  [FAIL] proces vllm padł podczas load — patrz $raw_log"; break
    fi
    sleep 5
  done

  if [[ "$ready" -eq 1 ]]; then
    t0=$(date +%s.%N)
    resp=$(curl -s --max-time 90 "localhost:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"model\":\"$mdir\",\"messages\":[{\"role\":\"user\",\"content\":\"$SANITY_PROMPT\"}],\"max_tokens\":128,\"temperature\":0.7}" 2>&1)
    t1=$(date +%s.%N)
    rtime=$(echo "$t1 - $t0" | bc 2>/dev/null || echo "NA")

    # Klasyfikacja odpowiedzi sanity — rozróżnia 3 stany które wcześniej
    # zlewały się do jednego "FAIL" bez diagnostyki:
    #   ok        — content niepusty (model działa)
    #   degenerate — HTTP 200, completion_tokens>0 ale content pusty
    #                (model generuje śmieci, np. all-<unk> spam — kernel/quant
    #                 niezgodność; infra OK, inference broken)
    #   parse_fail — brak struktury choices[0].message.content (HTTP error,
    #                truncated body, niepoprawny JSON)
    # diag-status zapisywany do JSON żeby nie mylić degenerate z infra-fail.
    read -r resp_status _ <<<"$(echo "$resp" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    ch = d["choices"][0]
    c = (ch["message"].get("content") or "")
    if c.strip():
        print("ok", c[:400].replace("\n", " "))
    else:
        ctoks = (d.get("usage") or {}).get("completion_tokens", 0)
        # content pusty: degenerate jeśli model jednak coś wygenerował
        print("degenerate" if ctoks else "parse_fail", "")
except Exception:
    print("parse_fail", "")
' 2>/dev/null)"
    [[ -z "$resp_status" ]] && resp_status="parse_fail"
    case "$resp_status" in
      ok)         verdict="PASS" ;;
      degenerate) verdict="FAIL" ;;   # inference broken mimo HTTP 200
      *)          verdict="FAIL" ;;   # parse_fail
    esac

    # metryki z raw log
    load_s=$(grep -oP 'Model loading took [0-9.]+ GiB memory and \K[0-9.]+' "$raw_log" | head -1)
    foot_g=$(grep -oP 'Model loading took \K[0-9.]+(?= GiB)' "$raw_log" | head -1)
    kv_tok=$(grep -oP 'GPU KV cache size: \K[0-9,]+' "$raw_log" | head -1)
    maxc=$(grep -oP 'Maximum concurrency for [0-9,]+ tokens per request: \K[0-9.]+' "$raw_log" | head -1)

    python3 - "$json_out" "$mdir" "$tp" "$extra" "$verdict" "${load_s:-NA}" "${foot_g:-NA}" "${kv_tok:-NA}" "${maxc:-NA}" "${rtime:-NA}" "$resp_status" <<'PYEOF'
import json, sys
out, mdir, tp, extra, verdict, load_s, foot_g, kv_tok, maxc, rtime, resp_status = sys.argv[1:12]
json.dump({
  "test_type": "sanity", "date": __import__("datetime").date.today().isoformat(),
  "model": mdir, "tensor_parallel_size": int(tp),
  "extra_flags": extra.strip(), "enforce_eager": True,
  "metrics": {
    "model_loading_sec": load_s, "model_footprint_gib": foot_g,
    "kv_cache_tokens": kv_tok, "max_concurrency_8192tok": maxc,
    "sanity_response_time_sec": rtime
  },
  "verdict": verdict,
  "response_status": resp_status,
  "embargo": "PUBLIC engineering §11.1",
  "orchestrated_by": "Claude Code batch_sanity_v0.3.sh"
}, open(out, "w"), indent=2, ensure_ascii=False)
PYEOF
    log "  $mdir → $verdict [$resp_status] (load ${load_s:-NA}s, KV ${kv_tok:-NA}, maxc ${maxc:-NA}x, resp ${rtime:-NA}s)"
  else
    log "  $mdir → FAIL (nie osiągnął readiness)"
    echo "{\"test_type\":\"sanity\",\"model\":\"$mdir\",\"tensor_parallel_size\":$tp,\"verdict\":\"FAIL\",\"reason\":\"readiness timeout / process died\",\"raw_log\":\"$raw_log\"}" > "$json_out"
  fi

  kill_vllm
  log "  $mdir — cleanup done, GPU released"
done

log "=== BATCH SANITY v0.3 KONIEC — JSON records w $SANITY_DIR ==="
