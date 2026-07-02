# Precision-ablation launch + overnight handoff — 2026-07-02

Operational session note. No embargoed performance numbers (METHODOLOGY §11.2/§11.3);
envelope facts are §11.1 PUBLIC.

## What ran / was set up

- **N=1 single-stream anchor confirmed complete.** All eight 70B-AWQ configs plus the
  small/mid set are in `paper/figures/n1_anchor_dataset.csv` (n=10 reps each); ladder
  figures regenerated under `paper/figures/R/`.

- **Precision-ablation sub-study operationalized** (`benchmarks/PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md`):
  same-checkpoint BF16-vs-AWQ matrix on RDNA4/gfx1201.
  - Faza 1 quantization complete: three fresh AWQ (W4A16, `calibration/quantization/quant_llmc.py`,
    clinical-pl calibration): `bielik-4.5b-v30-awq`, `qwen25-7b-instruct-awq`, `mistral-nemo-instruct-2407-awq`.
  - Faza 2 hardware envelope (§11.1) recorded for the three via
    `benchmarks/scripts/orchestrators/run_envelope_gate1_ablation.sh`
    → `benchmarks/results/hardware_envelope/*_maxctx.json`; Gate-1 coherence outputs recorded
    for human review (not auto-stamped).
  - New keys `bielik-4.5b-v30-awq` registered in `run_concurrent.py` and `bench_with_thermals.py`.

- **First same-checkpoint sweep launched:** `run_ablation_bielik45_awq_sweep.sh`
  (Bielik-4.5B-v3.0 AWQ side; BF16 side already swept full ladder), Tier-A n=10,
  N∈{10,25,50,100,200,500,1000}, TP∈{1,2}, under a systemd-inhibit no-sleep holder.
  Output (embargoed) under `benchmarks/results/bielik-4.5b-v30-awq/thermal-runs/`.

## Overnight (unattended)

1. `bielik-4.5b-v30-awq` sweep completes → sentinel `_ablation_bielik45_awq_logs/SWEEP_COMPLETE`.
2. A follow-on task runs on the freed GPUs, then the workstation suspends.

## TODO (Łukasz)

- Review the Gate-1 coherence outputs for the three new AWQ before promoting any dashboard cell.
- Paper #1 self-review pass complete; author-decision items are flagged inline in the (local,
  gitignored) drafts — venue, multiplicity reporting, firmware provenance reconciliation with
  METHODOLOGY §2.1, final title.
- Aggregation for the BF16-vs-AWQ precision comparison (`aggregate_precision_ablation.py`) still to write.
- Remaining ablation cells (PLLuM-8B / 12B, same-checkpoint pairs) are queued and splittable per cell.

## Navigation

- Plan: `benchmarks/PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md`
- Orchestrators: `benchmarks/scripts/orchestrators/{run_envelope_gate1_ablation,run_ablation_bielik45_awq_sweep}.sh`
- N=1 anchor: `benchmarks/scripts/orchestrators/run_n1_anchor_{smallmid,70b}.sh`, `paper/figures/n1_anchor_dataset.csv`
