#!/bin/bash
# Push gotowych modeli AWQ na HF (mozarcik/*).
# Uruchamiać INSIDE kontenera navimed-quant, PO `hf auth login`.
set -u
HF_USER=mozarcik
echo "================ HF UPLOAD START $(date -u) ================"
hf auth whoami 2>/dev/null || { echo "!!! brak hf auth login — przerwij, zaloguj się najpierw"; exit 1; }

OK=0; FAIL=0
for D in /scratch/out/*-awq; do
  [ -d "$D" ] || continue
  NAME=$(basename "$D")
  REPO="$HF_USER/$NAME"
  echo; echo "######## $NAME -> $REPO ########"
  hf repo create "$REPO" --repo-type model --private -y 2>/dev/null
  if hf upload "$REPO" "$D" --repo-type model ; then
    echo "[$NAME] === UPLOAD OK ==="; OK=$((OK+1))
  else
    echo "[$NAME] !!! UPLOAD FAIL"; FAIL=$((FAIL+1))
  fi
done
echo; echo "================ DONE $(date -u) | OK=$OK FAIL=$FAIL ================"
