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

## Precision-ablation quants (RDNA 4, local)

`quant_llmc.py` (same compressed-tensors W4A16 recipe, same
`clinical-pl/corpus.jsonl` calibration) was also used — **locally on the
2× R9700 workstation, not MI300X** — to produce fresh same-checkpoint AWQ
quants for the BF16-vs-AWQ precision-ablation study
([`../../benchmarks/PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md`](../../benchmarks/PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md)):

| Model | Base arch | AWQ artifact |
|---|---|---|
| Bielik-4.5B-v3.0-Instruct | Mistral-PL | `bielik-4.5b-v30-awq` |
| Qwen2.5-7B-Instruct | Qwen | `qwen25-7b-instruct-awq` |
| Mistral-Nemo-Instruct-2407 | Mistral | `mistral-nemo-instruct-2407-awq` |

Each is the AWQ half of a same-checkpoint pair whose BF16 half is already
benchmarked, enabling a like-for-like precision comparison rather than a
capacity-driven one. The domain calibration corpus (Polish clinical SmPC)
is reused deliberately across architectures for a consistent, domain-relevant
quantization target.
