#!/usr/bin/env bash
# =============================================================================
# sanity_sweep_pllum70b_awq.sh
# Three-stage test runner for the 8 AWQ Llama-PLLuM-70B checkpoints
# (compressed-tensors W4A16), quantized on AMD compute (§4.3 errata).
#
# THREE EXPLICIT STAGES — each launched on its own. There is NO auto-chain:
# the long, embargoed sweep starts only after a human reviews the Gate-2 probe.
#
#   --stage sanity   Gate 1 — Hardware envelope. vllm serve TP=2, poll
#                    readiness, single probe, 3-state classify -> JSON + log.
#                    PUBLIC §11.1. Default stage if --stage is omitted.
#
#   --stage probe    Gate 2 — AWQ-QA Polish coherence probe. For every model
#                    with a sanity JSON verdict PASS, runs
#                    scripts/awq_coherence_probe.py: ~5 varied Polish prompts,
#                    mechanical auto-flags (language / non-degeneracy /
#                    length), raw outputs retained for human spot-check.
#                    Vehicle-integrity check, NOT a model-quality eval —
#                    METHODOLOGY §8 boundary preserved. PUBLIC §11.1.
#
#   --stage sweep    Gate 3 — Phase 2 scaling sweep via
#                    throughput_scaling_phase2.py (knee / plateau). Runs ONLY
#                    for models that are BOTH sanity-PASS AND coherence-probe
#                    PASS. MUST be launched explicitly, after Gate-2 review.
#                    Output EMBARGOED §11.2 / §11.3 (Polish models, scoop risk).
#
# Intended flow:  sanity  ->  probe  ->  (human review)  ->  sweep
#
# Reuse:
#   - scripts/_env.sh                  — env §3.1 (AITER off, ROCR filter, venv)
#   - scripts/kill_port.sh             — isolated process cleanup (NOT pkill -f)
#   - scripts/awq_coherence_probe.py   — Gate-2 probe (this branch)
#   - throughput_scaling_phase2.py     — sweep harness (METHODOLOGY §5.2/§6/§7)
#
# METHODOLOGY-compliant: TP=2 mandatory for 70B (§4.3), enforce_eager (§3.2
# conservative default), embargo split per artifact — sanity + probe PUBLIC
# §11.1, sweep numbers EMBARGOED §11.2/§11.3.
#
# Idempotent: a model with an existing sanity JSON is skipped in --stage
# sanity; with an existing probe JSON, skipped in --stage probe; with an
# existing scaling/results_table.csv, skipped in --stage sweep.
#
# Usage:
#   bash scripts/sanity_sweep_pllum70b_awq.sh                      # = --stage sanity
#   bash scripts/sanity_sweep_pllum70b_awq.sh --stage sanity
#   bash scripts/sanity_sweep_pllum70b_awq.sh --stage probe
#   bash scripts/sanity_sweep_pllum70b_awq.sh --stage sweep
#   SWEEP_NS=350,500,750,1000 bash scripts/sanity_sweep_pllum70b_awq.sh --stage sweep
# =============================================================================
# NIE set -e/-u/pipefail — batch musi przeżyć błędy pojedynczych modeli
# i kontynuować kolejne (wzorzec z batch_sanity_v0.3.sh).
set +e

NAVIMED_ROOT="/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb"  # pragma: allowlist secret
MODELS_DIR="$HOME/models"
SANITY_DIR="$NAVIMED_ROOT/environment/sanity-tests"
PROBE_DIR="$NAVIMED_ROOT/environment/coherence-probes"
SCALER="$NAVIMED_ROOT/benchmarks/scripts/runners/throughput_scaling_phase2.py"
PROBE_PY="$NAVIMED_ROOT/scripts/awq_coherence_probe.py"
KILL_PORT="$NAVIMED_ROOT/scripts/kill_port.sh"
PORT=8100
TP=2                                  # §4.3 — TP=2 mandatory dla Llama-PLLuM-70B
QUANT_LABEL="compressed-tensors"       # W4A16, auto-wykrywany przez vLLM z config.json
# DATE — date key for sanity/probe JSON filenames. Defaults to today; can be
# overridden via `DATE=2026-05-23 bash ... --stage sweep` to consume artifacts
# produced on an earlier day (stack-stable carry-over) without forcing a fresh
# sanity+probe re-run. Use with care: this trusts the operator's judgment that
# the hardware/software stack has not changed since the named date.
DATE="${DATE:-$(date +%Y-%m-%d)}"
PROGRESS_LOG="$NAVIMED_ROOT/logs/downloads/sanity-sweep-pllum70b-awq-${DATE}.log"
SANITY_PROMPT="Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."
SWEEP_NS="${SWEEP_NS:-200,350,500,750,1000}"       # extended N>200 — knee/plateau

# --- Stage flag --------------------------------------------------------------
# --stage {sanity,probe,sweep}. Default sanity. NO 'full' mode — the sweep
# never auto-chains; it must be requested explicitly after Gate-2 review.
STAGE="sanity"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage)
      STAGE="${2:-}"; shift 2 ;;
    --stage=*)
      STAGE="${1#*=}"; shift ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)
      echo "ERROR: unknown argument '$1' (expected --stage {sanity,probe,sweep})" >&2
      exit 2 ;;
  esac
done
case "$STAGE" in
  sanity|probe|sweep) ;;
  *)
    echo "ERROR: --stage must be one of: sanity, probe, sweep (got '$STAGE')" >&2
    exit 2 ;;
esac

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
mkdir -p "$SANITY_DIR" "$PROBE_DIR" "$(dirname "$PROGRESS_LOG")"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$PROGRESS_LOG"; }

# shellcheck disable=SC1090  # venv activate path is non-constant by design
source ~/venvs/vllm/bin/activate
# shellcheck disable=SC1091  # _env.sh resolved at runtime, not a build input
source "$NAVIMED_ROOT/scripts/_env.sh"
# _env.sh włącza `set -euo pipefail` — wyłącz: set -u zabija subshelle $(...).
set +euo pipefail

# -----------------------------------------------------------------------------
# verdict_of — read the "verdict" field from a JSON record, or "" if absent.
# -----------------------------------------------------------------------------
verdict_of() {
  grep -oP '"verdict"\s*:\s*"\K[A-Z]+' "$1" 2>/dev/null | head -1
}

# =============================================================================
# STAGE 1 — SANITY (Gate 1, hardware envelope)
# =============================================================================
# sanity_one — serve TP=2, poll readiness, probe, klasyfikuj odpowiedź.
# Echo: "PASS" lub "FAIL" na stdout. Reszta → log/JSON. PUBLIC §11.1.
# -----------------------------------------------------------------------------
sanity_one() {
  local mdir="$1"
  local model_path="$MODELS_DIR/$mdir"
  local json_out="$SANITY_DIR/${DATE}-${mdir}-tp${TP}.json"
  local raw_log="$SANITY_DIR/${DATE}-${mdir}-vllm-tp${TP}.log"

  if [[ -f "$json_out" ]]; then
    local prev
    prev=$(verdict_of "$json_out")
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

run_stage_sanity() {
  log "=== STAGE 1/3 SANITY (Gate 1) — ${#MODELS[@]} modeli ==="
  local passed=()
  for mdir in "${MODELS[@]}"; do
    local verdict
    verdict=$(sanity_one "$mdir")
    [[ "$verdict" == "PASS" ]] && passed+=("$mdir")
  done
  log "=== SANITY KONIEC — ${#passed[@]}/${#MODELS[@]} PASS: ${passed[*]:-(brak)} ==="
  log "Następny etap (po przeglądzie): bash $0 --stage probe"
}

# =============================================================================
# STAGE 2 — COHERENCE PROBE (Gate 2, AWQ-QA)
# =============================================================================
# probe_one — Polish coherence probe dla jednego modelu sanity-PASS.
# Delegated to awq_coherence_probe.py (vehicle-integrity check, §8 boundary).
# -----------------------------------------------------------------------------
probe_one() {
  local mdir="$1"
  local sanity_json="$SANITY_DIR/${DATE}-${mdir}-tp${TP}.json"
  local probe_json="$PROBE_DIR/${DATE}-${mdir}-coherence-probe.json"

  if [[ ! -f "$sanity_json" ]]; then
    log "[skip] $mdir — brak sanity JSON ($DATE); uruchom najpierw --stage sanity"
    return
  fi
  local sv
  sv=$(verdict_of "$sanity_json")
  if [[ "$sv" != "PASS" ]]; then
    log "[skip] $mdir — sanity verdict ${sv:-?} (≠PASS); probe pominięty"
    return
  fi
  if [[ -f "$probe_json" ]]; then
    log "[skip] $mdir — probe JSON już istnieje (verdict $(verdict_of "$probe_json"))"
    return
  fi

  log "--- PROBE $mdir (Gate 2 AWQ-QA, TP=$TP) ---"
  # awq_coherence_probe.py serwuje model, odpytuje, sprząta przez kill_port.sh.
  python3 "$PROBE_PY" "$mdir" --tp "$TP" --port "$PORT" 2>&1 | tee -a "$PROGRESS_LOG"
  log "  $mdir → probe verdict $(verdict_of "$probe_json")"
}

run_stage_probe() {
  log "=== STAGE 2/3 COHERENCE PROBE (Gate 2 AWQ-QA) — ${#MODELS[@]} modeli ==="
  log "Vehicle-integrity check (czy AWQ nie zepsuł modelu), NIE ocena jakości — §8."
  for mdir in "${MODELS[@]}"; do
    probe_one "$mdir"
  done
  log "=== COHERENCE PROBE KONIEC — JSON+raw w $PROBE_DIR ==="
  log "PRZEGLĄD: spot-check raw outputs, potem (jeśli OK): bash $0 --stage sweep"
}

# =============================================================================
# STAGE 3 — SWEEP (Gate 3, Phase 2 scaling) — EMBARGOED §11.2/§11.3
# =============================================================================
# sweep_one — Phase 2 scaling sweep przez throughput_scaling_phase2.py.
# Wywoływane TYLKO dla modeli sanity-PASS ORAZ probe-PASS.
# -----------------------------------------------------------------------------
sweep_one() {
  local mdir="$1"
  local sanity_json="$SANITY_DIR/${DATE}-${mdir}-tp${TP}.json"
  local probe_json="$PROBE_DIR/${DATE}-${mdir}-coherence-probe.json"
  local result_csv="$NAVIMED_ROOT/benchmarks/results/$mdir/scaling/results_table.csv"

  # Gate 1 — sanity PASS wymagany.
  if [[ "$(verdict_of "$sanity_json")" != "PASS" ]]; then
    log "[skip] $mdir — brak sanity-PASS ($DATE); sweep pominięty"
    return
  fi
  # Gate 2 — probe PASS wymagany. REVIEW/FAIL/brak → sweep wstrzymany.
  # Human override (METHODOLOGY §8 — auto-flags are mechanical; human spot-check
  # is part of the gate). If a sibling file <probe>.human_verdict.json exists with
  # verdict=PASS, it overrides the auto verdict — e.g. when the n-gram heuristic
  # returns REVIEW false-positive on short correct answers
  # ("Stolicą Polski jest Warszawa." — 4 words, top_ngram_share 0.5 → coherent=false
  # despite being perfectly correct).
  local pv pv_auto probe_override
  probe_override="${probe_json%.json}.human_verdict.json"
  pv_auto=$(verdict_of "$probe_json")
  if [[ -f "$probe_override" ]]; then
    pv=$(verdict_of "$probe_override")
    log "[note] $mdir — using human_verdict.json override (auto=${pv_auto:-brak}, human=${pv:-brak})"
  else
    pv="$pv_auto"
  fi
  if [[ "$pv" != "PASS" ]]; then
    log "[skip] $mdir — coherence probe verdict ${pv:-brak} (≠PASS); sweep wstrzymany"
    return
  fi
  if [[ -f "$result_csv" ]]; then
    log "[skip] $mdir — sweep scaling/results_table.csv już istnieje"
    return
  fi

  log "--- SWEEP $mdir (TP=$TP, $QUANT_LABEL, N=$SWEEP_NS) — EMBARGO §11.2/§11.3 ---"
  bash "$KILL_PORT" "$PORT"

  # compressed-tensors W4A16 → vLLM auto-wykrywa kwantyzację, --extra puste.
  python3 "$SCALER" "$mdir" "$TP" \
    --quant "$QUANT_LABEL" --ns "$SWEEP_NS" \
    2>&1 | tee -a "$PROGRESS_LOG"

  bash "$KILL_PORT" "$PORT"
  log "  $mdir — sweep cleanup done, GPU released"
}

run_stage_sweep() {
  log "=== STAGE 3/3 SWEEP (Gate 3, Phase 2 scaling) — EMBARGO §11.2/§11.3 ==="
  log "Sweep wymaga sanity-PASS ORAZ coherence-probe-PASS dla każdego modelu."
  for mdir in "${MODELS[@]}"; do
    sweep_one "$mdir"
  done
  log "=== SWEEP KONIEC — wyniki w $NAVIMED_ROOT/benchmarks/results/<model>/scaling/ ==="
}

# =============================================================================
# Dispatch — dokładnie jeden etap per uruchomienie. NIE auto-chain.
# =============================================================================
case "$STAGE" in
  sanity) run_stage_sanity ;;
  probe)  run_stage_probe  ;;
  sweep)  run_stage_sweep  ;;
esac
