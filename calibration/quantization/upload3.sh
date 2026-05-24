#!/bin/bash
# Upload 2 nowych modeli AWQ (run-3) na HF + flip public. Runs INSIDE navimed-quant.
# UWAGA: README.md + LICENSE + NOTICE + USE_POLICY.md per repo wymaga osobnego pushu
# (po upload weights → wyrenderuj README z generate-readmes-3.sh → upload-to-hf-3.sh).
# Ten skrypt zajmuje się tylko weights.
exec > /scratch/upload3.log 2>&1
set -u
echo "================ UPLOAD-3 START $(date -u) ================"
hf auth whoami 2>/dev/null || { echo "!!! brak hf auth login — przerwij, zaloguj się najpierw"; exit 1; }

MODELS="Llama-PLLuM-8B-chat-2512-awq PLLuM-12B-chat-2512-awq"

for M in $MODELS; do
  echo
  echo "######## $M ########"
  hf repo create "mozarcik/$M" --repo-type model --private -y 2>/dev/null
  if hf upload "mozarcik/$M" "/scratch/out/$M" --repo-type model ; then
    echo "[$M] UPLOAD OK"
  else
    echo "[$M] !!! UPLOAD FAIL"
  fi
done

echo
echo "==== keep private until README + LICENSE + NOTICE + USE_POLICY pushed ===="
echo "==== run upload-to-hf-3.sh (separate) to push docs + flip public ===="
echo "================ UPLOAD-3 DONE $(date -u) ================"
touch /scratch/UPLOAD3_COMPLETE
