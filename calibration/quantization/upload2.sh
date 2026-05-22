#!/bin/bash
# Upload 3 nowych modeli AWQ (run-2) na HF + flip public. Runs INSIDE navimed-quant.
exec > /scratch/upload2.log 2>&1
set -u
echo "================ UPLOAD-2 START $(date -u) ================"

MODELS="Llama-PLLuM-70B-instruct-2508-awq Llama-PLLuM-70B-chat-2512-awq Llama-PLLuM-70B-instruct-2512-awq"

for M in $MODELS; do
  echo
  echo "######## $M ########"
  if hf upload "mozarcik/$M" "/scratch/out/$M" --repo-type model ; then
    echo "[$M] UPLOAD OK"
  else
    echo "[$M] !!! UPLOAD FAIL"
  fi
done

echo
echo "==== flip 3 nowych na public ===="
python3 - <<'PYEOF'
from huggingface_hub import HfApi
api = HfApi()
for r in [
    "mozarcik/Llama-PLLuM-70B-instruct-2508-awq",
    "mozarcik/Llama-PLLuM-70B-chat-2512-awq",
    "mozarcik/Llama-PLLuM-70B-instruct-2512-awq",
]:
    try:
        api.update_repo_settings(repo_id=r, private=False)
        print("PUBLIC OK  ", r)
    except Exception as e:
        print("flip note  ", r, type(e).__name__, str(e)[:80])
PYEOF

echo
echo "================ UPLOAD-2 DONE $(date -u) ================"
touch /scratch/UPLOAD2_COMPLETE
