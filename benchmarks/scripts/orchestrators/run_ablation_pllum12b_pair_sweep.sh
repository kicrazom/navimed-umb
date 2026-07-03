#!/usr/bin/env bash
# Precision-ablation sweep — PLLuM-12B same-checkpoint pair (PLAN-2026-06-30, Faza 3,
# split #2). PLLuM-12B-chat-2512: BF16 (pllum-12b) then AWQ (pllum-12b-awq).
# Tier-A REPS=10, N {10,25,50,100,200,500,1000}, TP {1,2}. Inner path:
# bench_with_thermals.py <key> <tp> <n> (offline gen + 1 Hz thermals for W/tok).
# Continue-on-fail. EMBARGO §11.2/§11.3 (Polish model).
set -uo pipefail
REPO=/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb
BENCH="$REPO/benchmarks/scripts/instrumentation/bench_with_thermals.py"
LOG_DIR="$REPO/benchmarks/results/_ablation_pllum12b_pair_logs"
LOG="$LOG_DIR/sweep.log"
mkdir -p "$LOG_DIR"
# shellcheck disable=SC1091
source "$REPO/scripts/_env.sh" 2>/dev/null || true

# "key quant" — BF16 first, then AWQ (same checkpoint)
CELLS=("pllum-12b bf16" "pllum-12b-awq awq")
N_LADDER=(10 25 50 100 200 500 1000)
TP_LADDER=(1 2)
REPS=10
MAX_LEN=8192
UTIL=0.90
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800

TOTAL=$(( ${#CELLS[@]} * ${#N_LADDER[@]} * ${#TP_LADDER[@]} * REPS ))
done_n=0
echo "[$(date -Is)] ABLATION pllum-12b pair sweep START — $TOTAL runs (${#CELLS[@]} cells)" | tee -a "$LOG"
for cell in "${CELLS[@]}"; do
  # shellcheck disable=SC2086
  set -- $cell; KEY="$1"; QUANT="$2"
  OUT_DIR="$REPO/benchmarks/results/$KEY/thermal-runs"
  mkdir -p "$OUT_DIR"
  echo "[$(date -Is)] ####### CELL $KEY ($QUANT) #######" | tee -a "$LOG"
  for TP in "${TP_LADDER[@]}"; do
    for N in "${N_LADDER[@]}"; do
      for ((REP=0; REP<REPS; REP++)); do
        NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
        done_n=$((done_n+1))
        echo "[$(date -Is)] [$done_n/$TOTAL] $KEY/$NAME ..." | tee -a "$LOG"
        if timeout $((PER_RUN_TIMEOUT_S+120)) python3 "$BENCH" \
            "$KEY" "$TP" "$N" --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
            --name "$NAME" --out-dir "$OUT_DIR" --interval 1.0 --timeout "$PER_RUN_TIMEOUT_S" \
            >> "$LOG_DIR/orchestrator.log" 2>&1; then
          echo "[$(date -Is)]   OK $KEY/$NAME" | tee -a "$LOG"
        else
          echo "[$(date -Is)]   FAIL $KEY/$NAME (rc=$?)" | tee -a "$LOG"
        fi
        (( done_n < TOTAL )) && sleep "$COOLDOWN_S"
      done
    done
  done
done
echo "[$(date -Is)] ABLATION pllum-12b pair sweep DONE" | tee -a "$LOG"
date -Is > "$LOG_DIR/SWEEP_COMPLETE"
