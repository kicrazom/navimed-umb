#!/bin/bash
# Master orchestrator — runs INSIDE navimed-quant container.
# Sekwencyjnie: download BF16 -> AWQ quant -> zostaw w /scratch/out -> usuń BF16.
set -u
LOG=/scratch/run.log
exec > >(tee -a "$LOG") 2>&1
echo "================ AWQ QUANT RUN START $(date -u) ================"

MODELS="CYFRAGOVPL/Llama-PLLuM-70B-base \
CYFRAGOVPL/Llama-PLLuM-70B-instruct \
CYFRAGOVPL/Llama-PLLuM-70B-chat \
CYFRAGOVPL/Llama-PLLuM-70B-base-250801 \
CYFRAGOVPL/Llama-PLLuM-70B-chat-250801"

OK=0; FAIL=0
for REPO in $MODELS; do
  NAME=$(basename "$REPO")
  IN=/scratch/in/$NAME
  OUT=/scratch/out/${NAME}-awq
  echo; echo "######## $NAME  ::  $(date -u) ########"
  if [ -f "$OUT/config.json" ]; then echo "[$NAME] AWQ już gotowy — pomijam"; OK=$((OK+1)); continue; fi
  echo "[$NAME] >>> download $REPO"
  if ! hf download "$REPO" --local-dir "$IN" ; then
    echo "[$NAME] !!! DOWNLOAD FAIL (sprawdź ID repo)"; FAIL=$((FAIL+1)); continue
  fi
  du -sh "$IN" 2>/dev/null
  echo "[$NAME] >>> quant (llm-compressor AWQ W4A16)"
  if ! python3 /scratch/quant_llmc.py "$IN" "$OUT" /scratch/corpus.jsonl ; then
    echo "[$NAME] !!! QUANT FAIL"; FAIL=$((FAIL+1)); continue
  fi
  echo "[$NAME] === OK ==="; du -sh "$OUT" 2>/dev/null
  rm -rf "$IN"   # zwolnij miejsce
  OK=$((OK+1))
done

echo; echo "================ DONE $(date -u) | OK=$OK FAIL=$FAIL ================"
ls -la /scratch/out/ 2>/dev/null
touch /scratch/RUN_COMPLETE
