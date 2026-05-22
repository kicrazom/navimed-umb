# AWQ-QA coherence probes (Gate 2)

Output of the AWQ-QA Polish-language coherence probe — Gate 2 of the
four-gate evaluation for the eight `Llama-PLLuM-70B-*-awq` checkpoints
(see `docs/sessions/2026-05-22-test-plan-phase2-70b-awq.md`).

## What this is

A **vehicle-integrity check**. The eight checkpoints are first-party AWQ
quantizations carrying a documented artifact: `llm-compressor` skips AWQ
activation-scaling for `v_proj` on GQA-attention models. A Gate-1
"not degenerate" verdict is insufficient — the probe confirms the
quantized model still produces *coherent Polish text*.

It is **not** a model-quality evaluation. It does not score reasoning,
factual accuracy, fluency, or clinical utility. Per METHODOLOGY §8
(Lerchner 2026), those are extrinsic properties of cognition, not of the
inference vehicle. The probe answers one yes/no question: did the
quantization step damage the model.

## Producer

`scripts/awq_coherence_probe.py`, invoked by
`scripts/sanity_sweep_pllum70b_awq.sh --stage probe`. Serves each model
TP=2, `--enforce-eager`, env per METHODOLOGY §3.1; sends ~5 varied Polish
prompts; auto-flags each response (language / non-degeneracy / length);
retains the raw text for human spot-check.

## Files

- `<date>-<model>-coherence-probe.json` — structured record:
  per-prompt status, mechanical auto-flags, aggregate verdict
  (`PASS` / `REVIEW` / `FAIL`).
- `<date>-<model>-coherence-raw.txt` — raw model output, verbatim, for
  human spot-check.

## Verdict semantics

- `PASS` — every prompt returned `ok` and cleared all three auto-flags.
- `REVIEW` — at least one flagged response; raises a flag for human
  review. Does **not** by itself decide re-quantization — that decision
  belongs to the maintainer (the `v_proj` artifact is real).
- `FAIL` — the model never reached serving readiness.

## Embargo

PUBLIC engineering content per METHODOLOGY §11.1, same class as Gate-1
sanity output. The probe carries no throughput, latency, or scaling
numbers — those §11.2 EMBARGOED artifacts are produced only by Gate 3
(the sweep). Probe JSON and raw output are safe to commit.
