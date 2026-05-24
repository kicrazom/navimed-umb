#!/bin/bash
# Run-3: rozszerzenie rodziny PLLuM AWQ poza 70B — chat-2512 w rozmiarach
# 12B (mistral / Mistral-Nemo-Base-2407, apache-2.0) i 8B (llama / Llama-3.1-8B, llama3.1).
# Runs INSIDE navimed-quant container. Reużywa corpus.jsonl + quant_llmc.py.
#
# Cel: democratize Polish clinical LLM access — 12B AWQ ~6 GB → fits RTX 3060 12 GB / RDNA3 16 GB,
# 8B AWQ ~4 GB → fits RTX 3060 8 GB / laptop GPU. Pierwsza publiczna AWQ vLLM-native dla obu.
#
# Walltime estimate MI300X: ~10 min (8B) + ~15 min (12B) ≈ 30 min total + 2× download.
set -u
LOG=/scratch/run3.log
exec > >(tee -a "$LOG") 2>&1
echo "================ AWQ QUANT RUN-3 START $(date -u) ================"

MODELS="CYFRAGOVPL/Llama-PLLuM-8B-chat-2512 \
CYFRAGOVPL/PLLuM-12B-chat-2512"

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

echo; echo "================ RUN-3 DONE $(date -u) | OK=$OK FAIL=$FAIL ================"
ls -la /scratch/out/ 2>/dev/null
touch /scratch/RUN3_COMPLETE
