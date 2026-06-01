#!/bin/bash
# Run-4: AWQ W4A16 dla medadapt (polski kliniczny) — rozszerzenie rodziny.
#   jmajkutewicz/Bielik-11B-v3.0-medadapt  (llama, polski KLINICZNY CPT+SFT na Bielik-11B-v3.0)
#   (ALIA-40b dropped+usunięta 2026-06-01: iberyjski nie-PL, już vLLM-quant NVFP4, off-mission)
#
# Runs INSIDE navimed-quant container na MI300X (DigitalOcean / AMD Dev Program).
# Reużywa quant_llmc.py + corpus.jsonl (clinical-pl SmPC, 418 chunks) — BEZ ZMIAN.
# Pipeline IDENTYCZNY co Run-1/2 (70B) i Run-3 (8B/12B).
#
# Walltime estimate MI300X (TP=1, 192 GB HBM — 11B mieści się z dużym zapasem):
#   medadapt 11B ~15-25 min quant + ~kilka min download (22GB) ≈ <0.5 h.
#   @ $1.99/h → ~$1-1.50 z $71. Zniszcz droplet PO uploadzie (billing per-sekundę).
#
# ⚠️ LICENCJA: medadapt — korpus treningowy NIEUDOKUMENTOWANY (brak license w karcie) →
#   skwantyzuj + upload PRIVATE, NIE flip public aż autor (jmajkutewicz) potwierdzi licencję.
#   ALIA — zwykle Apache-2.0 (zweryfikuj kartę), flip public po Gate-1/2.
set -u
LOG=/scratch/run4.log
exec > >(tee -a "$LOG") 2>&1
echo "================ AWQ QUANT RUN-4 START $(date -u) ================"

# ALIA dropped+usunięta 2026-06-01 (iberyjski nie-PL, już vLLM-quant NVFP4, off-mission)
MODELS="jmajkutewicz/Bielik-11B-v3.0-medadapt"

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
  echo "[$NAME] >>> quant (llm-compressor AWQ W4A16, corpus clinical-pl)"
  if ! python3 /scratch/quant_llmc.py "$IN" "$OUT" /scratch/corpus.jsonl ; then
    echo "[$NAME] !!! QUANT FAIL"; FAIL=$((FAIL+1)); continue
  fi
  echo "[$NAME] === OK ==="; du -sh "$OUT" 2>/dev/null
  rm -rf "$IN"
  OK=$((OK+1))
done

echo; echo "================ RUN-4 DONE $(date -u) | OK=$OK FAIL=$FAIL ================"
ls -la /scratch/out/ 2>/dev/null
touch /scratch/RUN4_COMPLETE
