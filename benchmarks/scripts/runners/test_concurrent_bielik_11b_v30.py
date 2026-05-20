"""
Concurrent request benchmark for Bielik 11B v3.0 (BF16) on 2x R9700 (gfx1201).

This is the v3.0 sibling of test_concurrent_bielik_11b.py. Identical workload
(make_prompts is unchanged, byte-for-byte) but pointing at the v3.0 model and
defaulting to BF16 (the Phase 1 envelope on 2026-05-17 was BF16).

Phase 1 envelope (see environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp{1,2}-bf16.json):
  - TP=1 BF16 max_len=8192 util=0.90  → KV pool 37,584 tokens, max_concurrency 4.59×
  - TP=2 BF16 max_len=8192 util=0.90  → KV pool 183,968 tokens, max_concurrency 22.46×

Per METHODOLOGY §4 v3.0 entry (and matching v2.3 segfault history on gfx1201):
  - enforce_eager=True empirically required (graphs path segfaults in libhsa-runtime64).

Usage:
    python test_concurrent_bielik_11b_v30.py 1 50  --quant bf16
    python test_concurrent_bielik_11b_v30.py 2 100 --quant bf16

All vLLM imports inside main() to avoid CUDA init at module load
(TP=2 uses 'spawn' multiprocessing which re-imports this module per worker).

Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.3).

Author: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
Sibling file (do not modify): test_concurrent_bielik_11b.py (v2.3, FP16/AWQ).
"""

import argparse
import sys
import time

# Default configuration — locked from Phase 1 envelope (2026-05-17).
DEFAULT_CONFIG = {
    "model_path": "/home/mozarcik/models/bielik-11b-v30",
    "max_model_len": 8192,
    "gpu_memory_utilization": 0.90,
}


def make_prompts(n: int) -> list[str]:
    """Build n varied prompts from templates × topics.

    IDENTICAL to test_concurrent_bielik_11b.py (v2.3) and to the 7B/27B/72B
    benchmarks per METHODOLOGY §6 — same workload, different model. Cross-model
    comparability depends on this being byte-for-byte identical.
    """
    templates = [
        "Explain {} in simple terms, with an example:",
        "Write a short story (about 100 words) involving {}:",
        "What are the three key benefits of {}? Give specific reasons:",
        "Summarize the history of {} in 3-4 sentences:",
        "Compare {} with a related concept, highlighting differences:",
        "Describe how {} works from first principles:",
        "What are common misconceptions about {}? Address them:",
        "Give a practical example of using {} in everyday life:",
    ]
    topics = [
        "quantum entanglement",
        "photosynthesis",
        "machine learning",
        "the TCP/IP protocol",
        "black holes",
        "mRNA vaccines",
        "distributed systems",
        "neural plasticity",
        "supply chain logistics",
        "tensor parallelism",
        "climate feedback loops",
        "the Krebs cycle",
        "cryptographic hashing",
        "CRISPR gene editing",
        "monetary policy",
        "reinforcement learning",
        "ocean currents",
        "magnetic resonance imaging",
        "fermentation",
        "GPS triangulation",
    ]
    return [
        templates[i % len(templates)].format(topics[i % len(topics)]) for i in range(n)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tp", type=int, help="Tensor parallel size (1 or 2)")
    ap.add_argument("n", type=int, help="Number of concurrent prompts")
    ap.add_argument(
        "--quant",
        choices=["bf16"],
        default="bf16",
        help="Quantization variant (BF16 only for v3.0 in this orchestration)",
    )
    ap.add_argument("--max-len", type=int, default=None, help="Override max_model_len")
    ap.add_argument(
        "--util", type=float, default=None, help="Override gpu_memory_utilization"
    )
    ap.add_argument("--kv-dtype", default=None, help="Override kv_cache_dtype")
    args = ap.parse_args()

    from vllm import LLM, SamplingParams

    config = DEFAULT_CONFIG.copy()
    if args.max_len is not None:
        config["max_model_len"] = args.max_len
    if args.util is not None:
        config["gpu_memory_utilization"] = args.util

    print(
        f"=== Concurrent benchmark: Bielik 11B v3.0 {args.quant.upper()} "
        f"TP={args.tp}, N={args.n} prompts ==="
    )
    print(f"    model:                {config['model_path']}")
    print(f"    max_model_len:        {config['max_model_len']}")
    print(f"    gpu_memory_util:      {config['gpu_memory_utilization']}")
    print(f"    kv_cache_dtype:       {args.kv_dtype or 'default'}")
    print("    enforce_eager:        True (graphs path segfaults on gfx1201)")
    print("    dtype:                bfloat16")

    prompts = make_prompts(args.n)

    llm_kwargs = dict(
        model=config["model_path"],
        dtype="bfloat16",
        max_model_len=config["max_model_len"],
        gpu_memory_utilization=config["gpu_memory_utilization"],
        enforce_eager=True,
        tensor_parallel_size=args.tp,
    )
    if args.kv_dtype:
        llm_kwargs["kv_cache_dtype"] = args.kv_dtype

    t0 = time.time()
    llm = LLM(**llm_kwargs)
    print(f"Load time: {time.time()-t0:.1f}s")

    sampling = SamplingParams(temperature=0.7, max_tokens=128)

    warmup_n = min(5, args.n)
    print(f"\n=== Warmup ({warmup_n} prompts) ===")
    llm.generate(prompts[:warmup_n], sampling)

    print(f"\n=== Benchmark ({args.n} prompts concurrent) ===")
    t0 = time.time()
    outputs = llm.generate(prompts, sampling)
    t_gen = time.time() - t0

    out_lens = [len(o.outputs[0].token_ids) for o in outputs]
    in_lens = [len(o.prompt_token_ids) for o in outputs]
    total_out = sum(out_lens)
    total_in = sum(in_lens)

    print()
    print(f"Total time:           {t_gen:.2f}s")
    print(f"Total output tokens:  {total_out}")
    print(f"Total input tokens:   {total_in}")
    print(f"Output throughput:    {total_out / t_gen:.2f} tok/s")
    print(f"Total throughput:     {(total_out + total_in) / t_gen:.2f} tok/s")
    print(f"Requests/second:      {args.n / t_gen:.3f}")
    print(f"Mean output len:      {total_out / args.n:.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
