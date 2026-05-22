#!/bin/bash
# Run-2: domknięcie rodziny Llama-PLLuM-70B AWQ — 3 brakujące modele.
# Runs INSIDE navimed-quant container. Reużywa corpus.jsonl + quant_llmc.py.
set -u
LOG=/scratch/run2.log
exec > >(tee -a "$LOG") 2>&1
echo "================ AWQ QUANT RUN-2 START $(date -u) ================"

MODELS="CYFRAGOVPL/Llama-PLLuM-70B-instruct-2508 \
CYFRAGOVPL/Llama-PLLuM-70B-chat-2512 \
CYFRAGOVPL/Llama-PLLuM-70B-instruct-2512"

OK=0; FAIL=0
for REPO in $MODELS; do
  NAME=$(basename "$REPO")
  IN=/scratch/in/$NAME
  OUT=/scratch/out/${NAME}-awq
  echo; echo "######## $NAME  ::  $(date -u) ########"
  if [ -f "$OUT/config.json" ]; then echo "[$NAME] AWQ już gotowy — pomijam"; OK=$((OK+1)); continue; fi
  echo "[$NAME] >>> download $REPO"
  if ! hf download "$REPO" --local-dir "$IN" ; then
    echo "[$NAME] !!! DOWNLOAD FAIL"; FAIL=$((FAIL+1)); continue
  fi
  du -sh "$IN" 2>/dev/null
  echo "[$NAME] >>> quant (llm-compressor AWQ W4A16)"
  if ! python3 /scratch/quant_llmc.py "$IN" "$OUT" /scratch/corpus.jsonl ; then
    echo "[$NAME] !!! QUANT FAIL"; FAIL=$((FAIL+1)); continue
  fi
  echo "[$NAME] === OK ==="; du -sh "$OUT" 2>/dev/null
  rm -rf "$IN"
  OK=$((OK+1))
done

echo; echo "================ RUN-2 DONE $(date -u) | OK=$OK FAIL=$FAIL ================"
ls -la /scratch/out/ 2>/dev/null
touch /scratch/RUN2_COMPLETE
