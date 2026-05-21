#!/usr/bin/env bash
# =============================================================================
# sanity_sweep_pllum70b_awq.sh
# Sanity + Phase 2 sweep dla 8 modeli AWQ Llama-PLLuM-70B (compressed-tensors
# W4A16), kwantyzowanych na AMD compute (§4.3 errata).
#
# Per model:
#   1. SANITY  — vllm serve TP=2 + AITER off + krótki probe → JSON record + log.
#   2. SWEEP   — TYLKO gdy sanity PASS → throughput_scaling_phase2.py (knee/plateau).
#
# Reużycie:
#   - scripts/_env.sh           — env §3.1 (AITER off, ROCR_VISIBLE_DEVICES, venv)
#   - scripts/kill_port.sh      — izolowany cleanup procesów (NIE pkill -f)
#   - batch_sanity_v0.3.sh      — logika serve/poll/probe/klasyfikacja odpowiedzi
#   - throughput_scaling_phase2.py — sweep harness (METHODOLOGY §5.2/§6/§7)
#
# METHODOLOGY-compliant: TP=2 mandatory dla 70B (§4.3), enforce_eager (§3.2
# conservative default), embargo split per artefakt (sanity PUBLIC §11.1,
# sweep numbers EMBARGOED §11.2).
#
# Idempotent: model z istniejącym JSON sanity recordem jest pomijany; sweep
# z istniejącym scaling/results_table.csv jest pomijany.
#
# Użycie:
#   bash scripts/sanity_sweep_pllum70b_awq.sh              # sanity + sweep
#   bash scripts/sanity_sweep_pllum70b_awq.sh sanity-only  # tylko sanity
#   SWEEP_NS=350,500,750,1000 bash scripts/sanity_sweep_pllum70b_awq.sh
# =============================================================================
# NIE set -e/-u/pipefail — batch musi przeżyć błędy pojedynczych modeli
# i kontynuować kolejne (wzorzec z batch_sanity_v0.3.sh).
set +e

NAVIMED_ROOT="/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb"  # pragma: allowlist secret
MODELS_DIR="$HOME/models"
SANITY_DIR="$NAVIMED_ROOT/environment/sanity-tests"
SCALER="$NAVIMED_ROOT/benchmarks/scripts/runners/throughput_scaling_phase2.py"
KILL_PORT="$NAVIMED_ROOT/scripts/kill_port.sh"
PORT=8100
TP=2                                  # §4.3 — TP=2 mandatory dla Llama-PLLuM-70B
QUANT_LABEL="compressed-tensors"       # W4A16, auto-wykrywany przez vLLM z config.json
DATE=$(date +%Y-%m-%d)
PROGRESS_LOG="$NAVIMED_ROOT/logs/downloads/sanity-sweep-pllum70b-awq-${DATE}.log"
SANITY_PROMPT="Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."
MODE="${1:-full}"                                  # full | sanity-only
SWEEP_NS="${SWEEP_NS:-200,350,500,750,1000}"       # extended N>200 — knee/plateau

# 8 modeli AWQ Llama-PLLuM-70B. compressed-tensors W4A16 — vLLM auto-wykrywa
# kwantyzację z config.json (quant_method: compressed-tensors), bez --quantization.
MODELS=(
  "Llama-PLLuM-70B-base-2412-awq"
  "Llama-PLLuM-70B-instruct-2412-awq"
  "Llama-PLLuM-70B-chat-2412-awq"
  "Llama-PLLuM-70B-base-2508-awq"
  "Llama-PLLuM-70B-chat-2508-awq"
  "Llama-PLLuM-70B-instruct-2508-awq"
  "Llama-PLLuM-70B-chat-2512-awq"
  "Llama-PLLuM-70B-instruct-2512-awq"
)

cd "$NAVIMED_ROOT" || exit 1
mkdir -p "$SANITY_DIR" "$(dirname "$PROGRESS_LOG")"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$PROGRESS_LOG"; }

# shellcheck disable=SC1090  # venv activate path is non-constant by design
source ~/venvs/vllm/bin/activate
# shellcheck disable=SC1091  # _env.sh resolved at runtime, not a build input
source "$NAVIMED_ROOT/scripts/_env.sh"
# _env.sh włącza `set -euo pipefail` — wyłącz: set -u zabija subshelle $(...).
set +euo pipefail

# -----------------------------------------------------------------------------
# sanity_one — serve TP=2, poll readiness, probe, klasyfikuj odpowiedź.
# Echo: "PASS" lub "FAIL" na stdout (do sterowania sweepem). Reszta → log/JSON.
# -----------------------------------------------------------------------------
sanity_one() {
  local mdir="$1"
  local model_path="$MODELS_DIR/$mdir"
  local json_out="$SANITY_DIR/${DATE}-${mdir}-tp${TP}.json"
  local raw_log="$SANITY_DIR/${DATE}-${mdir}-vllm-tp${TP}.log"

  if [[ -f "$json_out" ]]; then
    local prev
    prev=$(grep -oP '"verdict"\s*:\s*"\K[A-Z]+' "$json_out" | head -1)
    log "[skip] $mdir — sanity JSON już istnieje (verdict ${prev:-?})"
    echo "${prev:-FAIL}"
    return
  fi
  if [[ ! -f "$model_path/config.json" ]] || ! compgen -G "$model_path/*.safetensors" >/dev/null; then
    log "[skip] $mdir — niekompletny (brak config.json lub *.safetensors)"
    echo "FAIL"
    return
  fi

  log "--- SANITY $mdir (TP=$TP, $QUANT_LABEL) ---"
  bash "$KILL_PORT" "$PORT"

  # compressed-tensors W4A16 — bez --quantization (auto z config.json).
  # --enforce-eager: suite-wide conservative default §3.2.
  nohup vllm serve "$model_path" \
    --tensor-parallel-size "$TP" --port "$PORT" \
    --max-model-len 8192 --gpu-memory-utilization 0.9 \
    --enforce-eager --served-model-name "$mdir" \
    > "$raw_log" 2>&1 &

  # Poll readiness — timeout 10 min (70B AWQ ładuje się długo).
  local ready=0 i
  for i in $(seq 1 120); do
    if curl -s --max-time 3 "localhost:$PORT/v1/models" 2>/dev/null | grep -q "$mdir"; then
      ready=1; log "  ready po ~$((i*5))s"; break
    fi
    if ! pgrep -f "vllm serve.*$mdir" >/dev/null 2>&1; then
      log "  [FAIL] proces vllm padł podczas load — patrz $raw_log"; break
    fi
    sleep 5
  done

  local verdict resp_status
  if [[ "$ready" -eq 1 ]]; then
    local t0 t1 rtime resp
    t0=$(date +%s.%N)
    resp=$(curl -s --max-time 90 "localhost:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"model\":\"$mdir\",\"messages\":[{\"role\":\"user\",\"content\":\"$SANITY_PROMPT\"}],\"max_tokens\":128,\"temperature\":0.7}" 2>&1)
    t1=$(date +%s.%N)
    rtime=$(echo "$t1 - $t0" | bc 2>/dev/null || echo "NA")

    # Klasyfikacja odpowiedzi — 3 stany (jak w batch_sanity_v0.3.sh):
    #   ok         — content niepusty (model działa)
    #   degenerate — HTTP 200, completion_tokens>0, content pusty (śmieci)
    #   parse_fail — brak struktury choices[0].message.content
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
        print("degenerate" if ctoks else "parse_fail", "")
except Exception:
    print("parse_fail", "")
' 2>/dev/null)"
    [[ -z "$resp_status" ]] && resp_status="parse_fail"
    case "$resp_status" in
      ok) verdict="PASS" ;;
      *)  verdict="FAIL" ;;          # degenerate | parse_fail
    esac

    # Metryki z raw log.
    local load_s foot_g kv_tok maxc
    load_s=$(grep -oP 'Model loading took [0-9.]+ GiB memory and \K[0-9.]+' "$raw_log" | head -1)
    foot_g=$(grep -oP 'Model loading took \K[0-9.]+(?= GiB)' "$raw_log" | head -1)
    kv_tok=$(grep -oP 'GPU KV cache size: \K[0-9,]+' "$raw_log" | head -1)
    maxc=$(grep -oP 'Maximum concurrency for [0-9,]+ tokens per request: \K[0-9.]+' "$raw_log" | head -1)

    python3 - "$json_out" "$mdir" "$TP" "$QUANT_LABEL" "$verdict" \
      "${load_s:-NA}" "${foot_g:-NA}" "${kv_tok:-NA}" "${maxc:-NA}" \
      "${rtime:-NA}" "$resp_status" <<'PYEOF'
import json, sys, datetime
out, mdir, tp, quant, verdict, load_s, foot_g, kv_tok, maxc, rtime, resp_status = sys.argv[1:12]
json.dump({
  "test_type": "sanity", "date": datetime.date.today().isoformat(),
  "model": mdir, "tensor_parallel_size": int(tp),
  "quantization": quant, "enforce_eager": True,
  "metrics": {
    "model_loading_sec": load_s, "model_footprint_gib": foot_g,
    "kv_cache_tokens": kv_tok, "max_concurrency_8192tok": maxc,
    "sanity_response_time_sec": rtime,
  },
  "verdict": verdict,
  "response_status": resp_status,
  "embargo": "PUBLIC engineering §11.1",
  "orchestrated_by": "Claude Code sanity_sweep_pllum70b_awq.sh",
}, open(out, "w"), indent=2, ensure_ascii=False)
PYEOF
    log "  $mdir → $verdict [$resp_status] (load ${load_s:-NA}s, KV ${kv_tok:-NA}, maxc ${maxc:-NA}x, resp ${rtime:-NA}s)"
  else
    verdict="FAIL"
    log "  $mdir → FAIL (nie osiągnął readiness)"
    echo "{\"test_type\":\"sanity\",\"model\":\"$mdir\",\"tensor_parallel_size\":$TP,\"verdict\":\"FAIL\",\"reason\":\"readiness timeout / process died\",\"raw_log\":\"$raw_log\"}" > "$json_out"
  fi

  bash "$KILL_PORT" "$PORT"
  log "  $mdir — sanity cleanup done, GPU released"
  echo "$verdict"
}

# -----------------------------------------------------------------------------
# sweep_one — Phase 2 scaling sweep przez throughput_scaling_phase2.py.
# Wywoływane TYLKO po sanity PASS. Idempotent: pomija jeśli wynik już istnieje.
# -----------------------------------------------------------------------------
sweep_one() {
  local mdir="$1"
  local result_csv="$NAVIMED_ROOT/benchmarks/results/$mdir/scaling/results_table.csv"

  if [[ -f "$result_csv" ]]; then
    log "[skip] $mdir — sweep scaling/results_table.csv już istnieje"
    return
  fi

  log "--- SWEEP $mdir (TP=$TP, $QUANT_LABEL, N=$SWEEP_NS) ---"
  bash "$KILL_PORT" "$PORT"

  # compressed-tensors W4A16 → vLLM auto-wykrywa kwantyzację, --extra puste.
  python3 "$SCALER" "$mdir" "$TP" \
    --quant "$QUANT_LABEL" --ns "$SWEEP_NS" \
    2>&1 | tee -a "$PROGRESS_LOG"

  bash "$KILL_PORT" "$PORT"
  log "  $mdir — sweep cleanup done, GPU released"
}

# -----------------------------------------------------------------------------
# Main — sanity wszystkich 8, sweep tylko dla PASS.
# -----------------------------------------------------------------------------
log "=== SANITY+SWEEP PLLuM-70B AWQ START — ${#MODELS[@]} modeli, mode=$MODE ==="

PASSED=()
for mdir in "${MODELS[@]}"; do
  verdict=$(sanity_one "$mdir")
  if [[ "$verdict" == "PASS" ]]; then
    PASSED+=("$mdir")
  fi
done

log "=== SANITY KONIEC — ${#PASSED[@]}/${#MODELS[@]} PASS: ${PASSED[*]:-(brak)} ==="

if [[ "$MODE" == "sanity-only" ]]; then
  log "=== mode=sanity-only — sweep pominięty ==="
  exit 0
fi

if [[ ${#PASSED[@]} -eq 0 ]]; then
  log "=== Brak modeli sanity-PASS — sweep pominięty ==="
  exit 0
fi

log "=== SWEEP START — ${#PASSED[@]} modeli sanity-PASS ==="
for mdir in "${PASSED[@]}"; do
  sweep_one "$mdir"
done

log "=== SANITY+SWEEP PLLuM-70B AWQ KONIEC ==="
log "  sanity JSON:  $SANITY_DIR/${DATE}-Llama-PLLuM-70B-*-tp${TP}.json"
log "  sweep wyniki: $NAVIMED_ROOT/benchmarks/results/<model>/scaling/"
