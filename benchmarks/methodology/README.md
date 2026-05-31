# Methodology — benchmark-specific notes

The **canonical protocol** (two-phase design, workload, reporting schema,
mandatory env-var floor, embargo policy) lives once in the repository-root
**[`METHODOLOGY.md`](../../METHODOLOGY.md)** — the single source of truth. This
file holds only what is specific to the studies under
[`results/`](../results/) and is *not* restated in the canonical document; see
also [`hardware_context.md`](hardware_context.md) for the dGPU/iGPU device mask
and CCD topology.

> Earlier revisions of this file restated an abridged copy of the protocol
> (sweep design, env-var floor). That was removed to avoid divergence from
> `METHODOLOGY.md`. In particular the env-var rationale had drifted:
> `enforce_eager=True` is mandatory for **all** models on gfx1201
> (METHODOLOGY §3.2), not only the hybrid-attention Qwen 3.5/3.6 — the
> CUDA-graph capture path hits `HSA_STATUS_ERROR_INVALID_PACKET_FORMAT`
> regardless of architecture.

## Run identifiers (Plan A / Plan B)

`run_plan_*.sh` orchestrators follow METHODOLOGY §5.2 with per-model N spacing:
Plan A (Qwen 7B) used a wide ladder up to N≈3000 (large KV absorbs all);
Plan B (Qwen 72B AWQ) used the standard ladder to N=1000 at
`max_model_len=4096`.

## Negative results (rule out optimization paths)

- **H7** — `VLLM_V1_USE_PREFILL_DECODE_ATTENTION=1` (from
  [`kyuz0/amd-r9700-vllm-toolboxes`](https://github.com/kyuz0/amd-r9700-vllm-toolboxes))
  is silently a no-op on stable vLLM 0.19.0+rocm721; it is implemented only in
  the TheRock-patched git build kyuz0 ships.
- **CCD1 pinning** — `taskset -c 8-15,24-31` (the 96 MB 3D V-Cache CCD)
  produced identical throughput across repeated runs at N=100, with the GPU
  saturated at 100% utilisation and the CPU at ~14%. V-Cache cannot accelerate
  a non-bottleneck. (Concrete tok/s embargoed per METHODOLOGY §11.2.)

## Prompt set and prefix caching

Plan A/B use 8 prefixes × 20 topics = 160 unique prompts, recycled when
N > 160. vLLM prefix caching (on by default) amplifies absolute throughput vs
unique prompts, but the TP=1 : TP=2 ratio is invariant. A unique-prompt sweep
is queued for the Polish-language phase.
