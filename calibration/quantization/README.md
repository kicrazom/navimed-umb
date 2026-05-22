# AWQ quantization scripts

Scripts used to quantize the Llama-PLLuM-70B family to AWQ W4A16 on AMD
Instinct MI300X (AMD Developer Cloud). Full account:
[`../../docs/sessions/2026-05-21-pllum-70b-awq-amd-mi300x.md`](../../docs/sessions/2026-05-21-pllum-70b-awq-amd-mi300x.md).

| Script | Role |
|---|---|
| `quant_llmc.py` | AWQ W4A16 quantization via llm-compressor (compressed-tensors, pack-quantized) |
| `run_quant.sh` | Batch orchestrator — run 1 (5 checkpoints): download BF16 → quant → AWQ |
| `run_quant2.sh` | Batch orchestrator — run 2 (3 checkpoints) |
| `upload_hf.sh` | Publish AWQ checkpoints to Hugging Face |
| `upload2.sh` | Publish run-2 checkpoints + set public |

The calibration corpus consumed by `quant_llmc.py` is
[`../clinical-pl/corpus.jsonl`](../clinical-pl/corpus.jsonl) (418 chunks,
clinical-PL SmPC). Retained for reproducibility — METHODOLOGY §3.3 (causal
closure). Paths inside the scripts (`/scratch/...`) are the MI300X instance
layout; adapt for re-runs.
