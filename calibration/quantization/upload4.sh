#!/bin/bash
# Upload Run-4 (medadapt-awq + ALIA-40b-awq) na HF — OBA PRIVATE. Runs INSIDE navimed-quant.
# Weights only. README + LICENSE + NOTICE + USE_POLICY → osobny push (po Gate-1/2 na R9700).
#
# ⚠️ FLIP PUBLIC:
#   - medadapt-awq: NIE flip public aż jmajkutewicz potwierdzi licencję korpusu treningowego.
#   - ALIA-40b-awq: flip public po (a) weryfikacji licencji ALIA (zwykle Apache-2.0) + (b) Gate-1/2 PASS.
exec > /scratch/upload4.log 2>&1
set -u
echo "================ UPLOAD-4 START $(date -u) ================"
hf auth whoami 2>/dev/null || { echo "!!! brak hf auth login — zaloguj się najpierw"; exit 1; }

MODELS="Bielik-11B-v3.0-medadapt-awq"   # ALIA dropped 2026-06-01

for M in $MODELS; do
  echo
  echo "######## $M ########"
  hf repo create "mozarcik/$M" --repo-type model --private -y 2>/dev/null
  if hf upload "mozarcik/$M" "/scratch/out/$M" --repo-type model ; then
    echo "[$M] UPLOAD OK (PRIVATE)"
  else
    echo "[$M] !!! UPLOAD FAIL"
  fi
done

echo
echo "==== OBA PRIVATE. Pobierz na R9700 (hf download) dla Gate-1/sweep. ===="
echo "==== medadapt: public DOPIERO po licencji. ALIA: public po licencji+Gate. ===="
echo "================ UPLOAD-4 DONE $(date -u) ================"
touch /scratch/UPLOAD4_COMPLETE
