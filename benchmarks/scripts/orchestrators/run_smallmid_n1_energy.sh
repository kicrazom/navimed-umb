#!/usr/bin/env bash
# Small/mid N=1 energy fill — the single-stream anchor logged throughput but NOT
# power for the 8 small/mid models (only the 70B family did). This runs N=1 with
# 1 Hz thermal sampling so the energy figures get a REAL N=1 point (no estimation),
# presented like the N=1 throughput anchor (single point, no SD band).
# Tier-A REPS=10 (same-test-everywhere). N=1 only. Both TP where the ladder has both;
# Qwen TP1 only (single-GPU). Continue-on-fail. EMBARGO §11.2/§11.3.
set -uo pipefail
REPO=/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb
BENCH="$REPO/benchmarks/scripts/instrumentation/bench_with_thermals.py"
LOG_DIR="$REPO/benchmarks/results/_smallmid_n1_energy_logs"
LOG="$LOG_DIR/sweep.log"
mkdir -p "$LOG_DIR"
# shellcheck disable=SC1091
source "$REPO/scripts/_env.sh" 2>/dev/null || true

REPS=10; N=1; MAX_LEN=8192; UTIL=0.90; COOLDOWN_S=20; TO=1800

# key | quant | result_dir (out-dir base) | tps(space-sep)
CELLS=(
  "bielik-4.5b-v30|bf16|bielik-4.5b-v30|1 2"
  "bielik-11b|fp16|bielik-11b-v23|1 2"
  "bielik-11b-v30|bf16|bielik-11b-v30|1 2"
  "bielik-pl-11b-v30-instruct|bf16|bielik-pl-11b-v30-instruct|1 2"
  "bielik-11b-v30-instruct-awq|awq|bielik-11b-v30-instruct-awq|1 2"
  "pllum-8b-awq|awq|Llama-PLLuM-8B-chat-2512-awq|1 2"
  "pllum-12b-awq|awq|PLLuM-12B-chat-2512-awq|1 2"
  "qwen3.5-9b|bf16|qwen3.5-9b|1"
)

TOTAL=0
for c in "${CELLS[@]}"; do IFS='|' read -r _k _q _d tps <<<"$c"; for _ in $tps; do TOTAL=$((TOTAL+REPS)); done; done
done_n=0
echo "[$(date -Is)] SMALLMID N=1 ENERGY sweep START — $TOTAL runs" | tee -a "$LOG"

for c in "${CELLS[@]}"; do
  IFS='|' read -r key quant outdir tps <<<"$c"
  OUT_DIR="$REPO/benchmarks/results/$outdir/thermal-runs"
  mkdir -p "$OUT_DIR"
  for TP in $tps; do
    for ((REP=0; REP<REPS; REP++)); do
      NAME="$(printf '%s-tp%s-n1-r%02d' "$quant" "$TP" "$REP")"
      done_n=$((done_n+1))
      echo "[$(date -Is)] [$done_n/$TOTAL] $outdir $NAME ..." | tee -a "$LOG"
      if timeout $((TO+120)) python3 "$BENCH" \
          "$key" "$TP" "$N" --quant "$quant" --max-len "$MAX_LEN" --util "$UTIL" \
          --name "$NAME" --out-dir "$OUT_DIR" --interval 1.0 --timeout "$TO" \
          >> "$LOG_DIR/orchestrator.log" 2>&1; then
        echo "[$(date -Is)]   OK $outdir/$NAME" | tee -a "$LOG"
      else
        echo "[$(date -Is)]   FAIL $outdir/$NAME (rc=$?)" | tee -a "$LOG"
      fi
      (( done_n < TOTAL )) && sleep "$COOLDOWN_S"
    done
  done
done
echo "[$(date -Is)] SMALLMID N=1 ENERGY sweep DONE" | tee -a "$LOG"
date -Is > "$LOG_DIR/SMALLMID_N1_COMPLETE"
