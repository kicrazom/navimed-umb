# Plan — dedicated sanity + envelope sweep (2026-06-08)

**Goal:** fill the PUBLIC dashboard cells (`gate`, `conc`, `weight`, `kv`) for the gap models —
deployable family + the 10 `pending` rows — WITHOUT producing embargoed throughput. This is a
light **load + sanity probe**, not a thermal/throughput sweep, so every figure it yields is
public by construction (engineering envelope + Gate-1).

> Why a separate run: the v3.0 thermal sweep produced only embargoed perf (tok/s, latency,
> power). Gate-1 (2/31 filled) and weight/KV-GiB (3/31, 2/31) are broadly missing because no
> sweep targets them. This run does.

## Per-model recipe (reuse existing tooling)

1. **Envelope probe** — `benchmarks/scripts/runners/probe_max_context.py` at **ctx 24576**
   (the dashboard's normalization basis), `enforce_eager=True` (mandatory on gfx1201). Capture
   from the vLLM load log: **model footprint (GiB)**, **KV-cache tokens**, **max-concurrency**.
   - 70B / 72B at TP=2 may not fit ctx 24576 → fall back to the largest ctx that loads and
     **record the ctx in the row note** (do not pretend it is comparable to the 24576 rows).
2. **Gate-1 sanity 5/5** — existing `sanity_bielik_11b.py` / `sanity_qwen36_27b.py` /
   `sanity_qwen72b_awq.py` pattern (generalize to a `sanity_grid.py` taking a model arg).
   5 Polish-clinical prompts (1 factual + 4 clinical: definitional, syndrome, instructional,
   procedural) via **`/v1/completions`, chat-template bypassed** (the documented pattern).
   Records pass/fail → `gate = "5/5"` on success.
3. Tear down. ~2–4 min/model (load + 5 prompts). No `run_concurrent.py` throughput.

## Targets (tiered; ~25 models)

- **Tier 1 — single-card, TP=1** (fast): Llama-PLLuM-8B-instruct (BF16) + 8B-chat-2512 (AWQ),
  PLLuM-12B-chat (BF16) + 12B-chat-2512 (AWQ), Bielik-11B v3.0/v2.3 (AWQ+BF16), Bielik-4.5B-v3.0,
  Qwen2.5-7B, Qwen3.5-9B. → fills `gate` + refreshes `conc`/`weight`/`kv` where missing.
- **Tier 2 — 70B family, TP=2** (both cards): 7× PLLuM-70B-AWQ `pending`
  (base/instruct/chat × 2412/2508 + instruct-2512). → flips `pending` → envelope + gate.
- **Tier 3 — large Qwen, TP=2**: Qwen2.5-72B-AWQ, Qwen3.6-27B(-FP8). → envelope + gate.
- **Skip:** BF16 70B parents (not deployable, >64 GB) — leave `n/a` with existing note.

## Constraints (METHODOLOGY + gfx1201 findings)

- `enforce_eager=True` always (CUDA-graph crashes on gfx1201).
- TP=1 for ≤~12B; TP=2 for 70B/72B.
- AWQ checkpoints with no maxctx probe (Run-3 addendum) → note the ctx basis used.
- KV in GiB only if the probe reports it; otherwise `kv = null` (n/a) + KV-tokens in the note,
  consistent with the 70B row.

## Orchestration

`benchmarks/scripts/orchestrators/run_sanity_envelope_sweep.sh` — iterate the tiered model list,
per model: probe_max_context (ctx 24576 / fallback) → sanity_grid → append a public-envelope
row to `benchmarks/results/_envelope_probe/<key>.json` (footprint, kv_tokens, max_conc, gate).
No embargoed fields written. Wrap in `systemd-inhibit` like the other orchestrators.

**Wall-time estimate:** Tier 1 ~10 models × ~3 min ≈ 30 min; Tier 2/3 ~10 models × ~4-6 min
(70B loads slower) ≈ 60 min. **Total ≈ 1.5–2 h.** Run when GPU frees (after canonical recovery,
~09:20–09:30) — or chain via a `launch_sanity_envelope_after_recovery.sh` sentinel-gated launcher.

## After the run → dashboard

Update `site/results.html` ROWS public cells (`gate`, `conc`, `weight`, `kv` + notes) from
`_envelope_probe/*.json`. **Do not touch the 🔒 perf columns.** Commit → subtree deploy → verify
live. All deployed figures are public envelope / Gate-1 (no embargo).

## Open decision for Łukasz

- **conc basis for the new 70B/72B rows:** ctx 24576 won't fit at TP=2; use model-card basis or
  largest-fitting ctx, and note it (already the convention for the 70B-chat-2512 row).
- Whether to chain it auto after recovery, or launch manually in the morning.
