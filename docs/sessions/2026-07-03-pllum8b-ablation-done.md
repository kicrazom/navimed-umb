# Precision-ablation — PLLuM-8B pair done, 12B queued — 2026-07-03

Operational checkpoint (per-model commit discipline). No embargoed performance numbers
(METHODOLOGY §11.2/§11.3); raw thermal-runs stay gitignored/local.

## Done

- **Split #1 — PLLuM-8B same-checkpoint pair** (`Llama-PLLuM-8B-chat-2512`, BF16 + AWQ):
  full-ladder Tier-A sweep complete via `run_ablation_pllum8b_pair_sweep.sh` —
  **280/280 runs OK, 0 FAIL** (~7.5 h wall). Reps under (embargoed)
  `benchmarks/results/pllum-8b{,-awq}/thermal-runs/`.
- BF16-side keys `pllum-8b` / `pllum-12b` registered in `run_concurrent.py` and
  `bench_with_thermals.py` (same-checkpoint partners for the existing `-awq` keys).

## Queued

- **Split #2 — PLLuM-12B same-checkpoint pair** (`PLLuM-12B-chat-2512`, BF16 + AWQ):
  `run_ablation_pllum12b_pair_sweep.sh`, launching now under a no-sleep holder. 12B BF16
  fit at gpu_memory_utilization 0.90 verified by a single-stream smoke.

## Notes

- Each same-checkpoint pair is the "model" unit; commit + push at each pair boundary
  (embargo-clean delta only).
- Aggregation for the BF16-vs-AWQ precision comparison (`aggregate_precision_ablation.py`)
  still to write; it feeds the Paper #1 fixed-identity control (referee finding M4).
