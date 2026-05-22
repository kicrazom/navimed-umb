"""
Parameterized concurrent-request benchmark — single GPU vs TP=2.

Consolidates six near-identical per-model scripts into one runner. The model
is selected by name on the CLI; everything that differed between the old
scripts (model path, quantization set, default max_model_len / gpu-util,
output format, prompt set) is data in the MODELS table below — not code.

Replaces (behaviour-preserving 1:1):
  - test_concurrent.py               → run_concurrent.py qwen7b
  - test_concurrent_qwen72b_awq.py   → run_concurrent.py qwen72b-awq
  - test_concurrent_qwen36_27b.py    → run_concurrent.py qwen36-27b
  - test_concurrent_bielik_11b.py    → run_concurrent.py bielik-11b
  - test_concurrent_bielik_11b_v30.py→ run_concurrent.py bielik-11b-v30
  - test_concurrent_longform.py      → run_concurrent.py longform

Pattern follows throughput_sweep_v0.3.py (model as a CLI argument).

Usage:
    python run_concurrent.py qwen7b 2 100
    python run_concurrent.py bielik-11b 1 50 --quant awq
    python run_concurrent.py qwen36-27b 2 25 --quant bf16 --max-len 1024 --util 0.95
    python run_concurrent.py longform 1 100 1024

`make_prompts` is byte-for-byte the workload of the old scripts per
METHODOLOGY §6 — cross-model comparability depends on it being identical.

Embargo: SCRIPT is PUBLIC (engineering). Polish-model runs (Bielik) produce
EMBARGO_paper_bound numbers per METHODOLOGY §11.3.

Author: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
"""

import argparse
import os
import sys
import time

# Standard workload — 8 templates × 20 topics (METHODOLOGY §6). Shared by the
# five concurrent benchmarks; longform uses its own set below.
TEMPLATES = [
    "Explain {} in simple terms, with an example:",
    "Write a short story (about 100 words) involving {}:",
    "What are the three key benefits of {}? Give specific reasons:",
    "Summarize the history of {} in 3-4 sentences:",
    "Compare {} with a related concept, highlighting differences:",
    "Describe how {} works from first principles:",
    "What are common misconceptions about {}? Address them:",
    "Give a practical example of using {} in everyday life:",
]
TOPICS = [
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

# Long-form workload — 4 templates × 20 topics, longer expected output.
LONGFORM_TEMPLATES = [
    "Write a detailed technical guide on {} covering history, key concepts, "
    "practical applications, and future directions:",
    "Explain {} from basic principles to advanced implications. "
    "Structure your answer with clear sections:",
    "Compose a comprehensive analysis of {} addressing theory, practice, "
    "limitations, and current research frontiers:",
    "Walk through {} step-by-step, from foundational ideas to contemporary "
    "developments, with examples:",
]
LONGFORM_TOPICS = [
    "transformer attention mechanisms",
    "RNA splicing regulation",
    "distributed consensus protocols",
    "neural coding in the visual cortex",
    "quantum error correction",
    "supply chain resilience",
    "CRISPR off-target effects",
    "reinforcement learning policy gradients",
    "plate tectonics feedback loops",
    "cryptographic zero-knowledge proofs",
    "mRNA vaccine thermostability",
    "tensor network methods in physics",
    "circadian rhythm molecular biology",
    "carbon capture technologies",
    "graph neural networks for chemistry",
    "climate sensitivity estimation",
    "prokaryotic vs eukaryotic gene regulation",
    "bandwidth-delay product in networking",
    "large language model alignment",
    "gene therapy delivery vectors",
]


def make_prompts(n: int) -> list[str]:
    """Build n varied prompts from templates × topics (METHODOLOGY §6).

    Byte-for-byte identical to the old test_concurrent_*.py scripts — the
    7B/11B/27B/72B benchmarks share this workload so cross-model comparison
    stays apples-to-apples.
    """
    return [
        TEMPLATES[i % len(TEMPLATES)].format(TOPICS[i % len(TOPICS)]) for i in range(n)
    ]


def make_longform_prompts(n: int) -> list[str]:
    """Long-form workload prompts (test_concurrent_longform.py, unchanged)."""
    return [
        LONGFORM_TEMPLATES[i % len(LONGFORM_TEMPLATES)].format(
            LONGFORM_TOPICS[i % len(LONGFORM_TOPICS)]
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Per-model configuration. Every field below is what differed between the six
# old scripts; the executable logic in main() is shared.
#
#   label        : human-readable model name for the run banner
#   banner_quant : True → banner reads "<label> <QUANT> TP=...";
#                  False → banner reads "<label> TP=..." (label already names
#                  the quant, e.g. qwen72b-awq, so it is not appended twice)
#   quants       : {quant_key: {model_path, max_model_len, gpu_memory_utilization}}
#   default_quant: quant used when --quant is omitted
#   dtype        : vLLM dtype kwarg
#   awq_marlin   : True → pass quantization="awq_marlin" for the 'awq' quant
#   report       : output format — "results_block" | "flat" | "longform"
#   prompt_set   : "standard" | "longform"
#   warmup       : warmup prompt count ("min5" → min(5,N); "min3" → min(3,N);
#                  3 → fixed 3; 5 → fixed 5)
#   tp_warn      : optional (predicate, message) printed when TP is unexpected
#   verbose_cfg  : True → print model/max_len/util/kv/eager config lines
# ---------------------------------------------------------------------------
MODELS = {
    # test_concurrent.py — Qwen 2.5 7B, positional CLI, results block.
    "qwen7b": {
        "label": "",
        "quants": {
            "fp16": {
                "model_path": "Qwen/Qwen2.5-7B-Instruct",
                "max_model_len": 4096,
                "gpu_memory_utilization": 0.70,
            },
        },
        "default_quant": "fp16",
        "dtype": "float16",
        "awq_marlin": False,
        "report": "results_block",
        "prompt_set": "standard",
        "warmup": 5,
        "tp_warn": None,
        "verbose_cfg": False,
        "results_header": "RESULTS — TP={tp}",
    },
    # test_concurrent_longform.py — Qwen 2.5 7B, long-form workload.
    "longform": {
        "label": "",
        "quants": {
            "fp16": {
                "model_path": "Qwen/Qwen2.5-7B-Instruct",
                "max_model_len": 4096,
                "gpu_memory_utilization": 0.70,
            },
        },
        "default_quant": "fp16",
        "dtype": "float16",
        "awq_marlin": False,
        "report": "longform",
        "prompt_set": "longform",
        "warmup": 3,
        "tp_warn": None,
        "verbose_cfg": False,
        "results_header": "RESULTS — TP={tp}",
    },
    # test_concurrent_qwen72b_awq.py — Qwen 2.5 72B AWQ, TP=2 only.
    "qwen72b-awq": {
        "label": "Qwen 72B AWQ",
        "banner_quant": False,  # label already says "AWQ"
        "quants": {
            "awq": {
                "model_path": os.path.expanduser("~/models/qwen25-72b-awq"),
                "max_model_len": 4096,
                "gpu_memory_utilization": 0.92,
            },
        },
        "default_quant": "awq",
        "dtype": "auto",
        "awq_marlin": False,  # 72B path relies on vLLM auto-selecting awq_marlin
        "report": "results_block",
        "prompt_set": "standard",
        "warmup": 5,
        "tp_warn": (
            lambda tp: tp != 2,
            "WARNING: Qwen 72B AWQ requires TP=2 (39 GB > 32 GB single-GPU)",
        ),
        "verbose_cfg": False,
        "results_header": "RESULTS - Qwen 72B AWQ TP={tp}",
    },
    # test_concurrent_qwen36_27b.py — Qwen 3.6 27B, FP8/BF16, TP=2.
    "qwen36-27b": {
        "label": "Qwen 3.6 27B",
        "quants": {
            "fp8": {
                "model_path": os.path.expanduser("~/models/qwen36-27b-fp8"),
                "max_model_len": 2048,
                "gpu_memory_utilization": 0.85,
            },
            "bf16": {
                "model_path": os.path.expanduser("~/models/qwen36-27b"),
                "max_model_len": 1024,
                "gpu_memory_utilization": 0.95,
            },
        },
        "default_quant": "bf16",
        "dtype": "auto",
        "awq_marlin": False,
        "report": "results_block",
        "prompt_set": "standard",
        "warmup": "min5",
        "tp_warn": (
            lambda tp: tp != 2,
            "WARNING: Qwen 3.6 27B requires TP=2 on 32 GB GPUs (single-GPU "
            "configurations OOM at weight padding stage)",
        ),
        "verbose_cfg": True,
        "verbose_eager": "True (mandatory for Qwen 3.5/3.6)",
        "results_header": "RESULTS - Qwen 3.6 27B {quant} TP={tp}",
    },
    # test_concurrent_bielik_11b.py — Bielik 11B v2.3, FP16/AWQ.
    "bielik-11b": {
        "label": "Bielik 11B v2.3",
        "quants": {
            "fp16": {
                "model_path": os.path.expanduser("~/models/bielik-11b-v23"),
                "max_model_len": 8192,
                "gpu_memory_utilization": 0.90,
            },
            "awq": {
                "model_path": os.path.expanduser("~/models/bielik-11b-v23-awq"),
                "max_model_len": 2048,
                "gpu_memory_utilization": 0.90,
            },
        },
        "default_quant": "fp16",
        "dtype": "auto",
        "awq_marlin": True,  # v2.3 AWQ passes quantization="awq_marlin" explicitly
        "report": "flat",
        "prompt_set": "standard",
        "warmup": "min5",
        "tp_warn": (
            lambda tp, quant=None: quant == "awq" and tp != 1,
            None,  # message built dynamically (depends on TP)
        ),
        "verbose_cfg": True,
        "verbose_eager": "True (graphs path segfaults on gfx1201)",
        "results_header": "",
    },
    # test_concurrent_bielik_11b_v30.py — Bielik 11B v3.0, BF16 only.
    "bielik-11b-v30": {
        "label": "Bielik 11B v3.0",
        "quants": {
            "bf16": {
                "model_path": "/home/mozarcik/models/bielik-11b-v30",
                "max_model_len": 8192,
                "gpu_memory_utilization": 0.90,
            },
        },
        "default_quant": "bf16",
        "dtype": "bfloat16",
        "awq_marlin": False,
        "report": "flat",
        "prompt_set": "standard",
        "warmup": "min5",
        "tp_warn": None,
        "verbose_cfg": True,
        "verbose_eager": "True (graphs path segfaults on gfx1201)",
        "verbose_dtype": "bfloat16",
        "results_header": "",
    },
}


def _resolve_warmup(spec, n: int) -> int:
    """Map a warmup spec (int | 'min5' | 'min3') to a concrete count."""
    if spec == "min5":
        return min(5, n)
    if spec == "min3":
        return min(3, n)
    return int(spec)


def _print_results_block(header: str, n, total_in, total_out, out_lens, t_gen) -> None:
    """Output format of test_concurrent.py / qwen36_27b / qwen72b_awq."""
    print(f"\n{'='*50}")
    print(header)
    print(f"{'='*50}")
    print(f"Prompts:             {n}")
    print(f"Input tokens total:  {total_in}")
    print(f"Input tokens mean:   {total_in/n:.1f}")
    print(f"Output tokens total: {total_out}")
    print(f"Output tokens mean:  {total_out/n:.1f}")
    print(f"Output tokens min:   {min(out_lens)}")
    print(f"Output tokens max:   {max(out_lens)}")
    print(f"Total time:          {t_gen:.2f}s")
    print(f"Output throughput:   {total_out/t_gen:.1f} tok/s")
    print(f"Total throughput:    {(total_in+total_out)/t_gen:.1f} tok/s")
    print(f"Requests/second:     {n/t_gen:.2f}")
    print(f"{'='*50}")


def _print_longform_block(header: str, n, total_in, total_out, out_lens, t_gen) -> None:
    """Output format of test_concurrent_longform.py."""
    print(f"\n{'='*50}")
    print(header)
    print(f"{'='*50}")
    print(f"Prompts:             {n}")
    print(f"Input mean:          {total_in/n:.1f} tokens")
    print(f"Output mean:         {total_out/n:.1f} tokens")
    print(f"Output min/max:      {min(out_lens)} / {max(out_lens)}")
    print(f"Total time:          {t_gen:.2f}s")
    print(f"Output throughput:   {total_out/t_gen:.1f} tok/s")
    print(f"Total throughput:    {(total_in+total_out)/t_gen:.1f} tok/s")
    print(f"Requests/second:     {n/t_gen:.2f}")
    print(f"{'='*50}")


def _print_flat_block(n, total_in, total_out, t_gen) -> None:
    """Output format of test_concurrent_bielik_11b{,_v30}.py."""
    print()
    print(f"Total time:           {t_gen:.2f}s")
    print(f"Total output tokens:  {total_out}")
    print(f"Total input tokens:   {total_in}")
    print(f"Output throughput:    {total_out / t_gen:.2f} tok/s")
    print(f"Total throughput:     {(total_out + total_in) / t_gen:.2f} tok/s")
    print(f"Requests/second:      {n / t_gen:.3f}")
    print(f"Mean output len:      {total_out / n:.1f}")


def main() -> int:
    """Argument parsing and benchmark execution.

    vLLM is imported inside main() to avoid CUDA init at module load — vLLM
    with TP>=2 uses 'spawn' multiprocessing which re-imports this module per
    worker; module-level CUDA init causes recursion errors.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", choices=sorted(MODELS), help="Model key (see MODELS)")
    ap.add_argument("tp", type=int, help="Tensor parallel size (1 or 2)")
    ap.add_argument("n", type=int, help="Number of concurrent prompts")
    ap.add_argument(
        "max_tokens",
        type=int,
        nargs="?",
        default=None,
        help="Max output tokens (longform only; default 1024 for longform, "
        "128 otherwise)",
    )
    ap.add_argument(
        "--quant",
        default=None,
        help="Quantization variant (default: model's default_quant)",
    )
    ap.add_argument(
        "--max-len",
        type=int,
        default=None,
        help="Override max_model_len (default: from MODELS table)",
    )
    ap.add_argument(
        "--util",
        type=float,
        default=None,
        help="Override gpu_memory_utilization (default: from MODELS table)",
    )
    ap.add_argument(
        "--kv-dtype",
        default=None,
        help="Override kv_cache_dtype (e.g. fp8_e4m3, default: vLLM default)",
    )
    args = ap.parse_args()

    spec = MODELS[args.model]
    quant = args.quant or spec["default_quant"]
    if quant not in spec["quants"]:
        ap.error(
            f"model '{args.model}' supports --quant "
            f"{sorted(spec['quants'])}, got '{quant}'"
        )

    from vllm import LLM, SamplingParams

    # Resolve config from the table + CLI overrides.
    config = dict(spec["quants"][quant])
    if args.max_len is not None:
        config["max_model_len"] = args.max_len
    if args.util is not None:
        config["gpu_memory_utilization"] = args.util

    # max_tokens: longform supports a positional override (default 1024);
    # all other models use 128 and ignore the positional argument.
    if spec["report"] == "longform":
        max_tokens = args.max_tokens if args.max_tokens is not None else 1024
    else:
        max_tokens = 128

    # TP warning (model-specific). Bielik-11b's AWQ warning text depends on TP.
    tp_warn = spec["tp_warn"]
    if tp_warn is not None:
        predicate, message = tp_warn
        # bielik-11b's predicate also inspects quant
        try:
            triggered = predicate(args.tp, quant)
        except TypeError:
            triggered = predicate(args.tp)
        if triggered:
            if message is None:
                message = (
                    "WARNING: Bielik AWQ per METHODOLOGY §4 model 6 supports "
                    f"TP=1 only. Got TP={args.tp}; behavior undefined."
                )
            print(message)

    # Run banner.
    label = spec["label"]
    if spec["report"] == "longform":
        print(f"=== Long-form: TP={args.tp}, N={args.n}, max_tokens={max_tokens} ===")
    elif label:
        banner_label = (
            f"{label} {quant.upper()}" if spec.get("banner_quant", True) else label
        )
        print(
            f"=== Concurrent benchmark: {banner_label} "
            f"TP={args.tp}, N={args.n} prompts ==="
        )
    else:
        print(f"=== Concurrent benchmark: TP={args.tp}, N={args.n} prompts ===")

    if spec["verbose_cfg"]:
        print(f"    model:                {config['model_path']}")
        print(f"    max_model_len:        {config['max_model_len']}")
        print(f"    gpu_memory_util:      {config['gpu_memory_utilization']}")
        print(f"    kv_cache_dtype:       {args.kv_dtype or 'default'}")
        print(f"    enforce_eager:        {spec['verbose_eager']}")
        if "verbose_dtype" in spec:
            print(f"    dtype:                {spec['verbose_dtype']}")

    # Build the workload.
    if spec["prompt_set"] == "longform":
        prompts = make_longform_prompts(args.n)
    else:
        prompts = make_prompts(args.n)

    # Build LLM kwargs — quantization arg only when the model wants explicit
    # awq_marlin; kv_cache_dtype only when set on the CLI.
    llm_kwargs = dict(
        model=config["model_path"],
        dtype=spec["dtype"],
        max_model_len=config["max_model_len"],
        gpu_memory_utilization=config["gpu_memory_utilization"],
        enforce_eager=True,
        tensor_parallel_size=args.tp,
    )
    if spec["awq_marlin"] and quant == "awq":
        llm_kwargs["quantization"] = "awq_marlin"
    if args.kv_dtype:
        llm_kwargs["kv_cache_dtype"] = args.kv_dtype

    t0 = time.time()
    llm = LLM(**llm_kwargs)
    print(f"Load time: {time.time()-t0:.1f}s")

    sampling = SamplingParams(temperature=0.7, max_tokens=max_tokens)

    # Warmup so scheduler and attention backend are hot.
    warmup_n = _resolve_warmup(spec["warmup"], args.n)
    print(f"\n=== Warmup ({warmup_n} prompts) ===")
    llm.generate(prompts[:warmup_n], sampling)

    if spec["report"] == "longform":
        print(f"\n=== Benchmark ({args.n} prompts) ===")
    else:
        print(f"\n=== Benchmark ({args.n} prompts concurrent) ===")
    t0 = time.time()
    outputs = llm.generate(prompts, sampling)
    t_gen = time.time() - t0

    out_lens = [len(o.outputs[0].token_ids) for o in outputs]
    in_lens = [len(o.prompt_token_ids) for o in outputs]
    total_out = sum(out_lens)
    total_in = sum(in_lens)

    if spec["report"] == "flat":
        _print_flat_block(args.n, total_in, total_out, t_gen)
    elif spec["report"] == "longform":
        header = spec["results_header"].format(tp=args.tp)
        _print_longform_block(header, args.n, total_in, total_out, out_lens, t_gen)
    else:  # results_block
        header = spec["results_header"].format(tp=args.tp, quant=quant.upper())
        _print_results_block(header, args.n, total_in, total_out, out_lens, t_gen)

    return 0


if __name__ == "__main__":
    sys.exit(main())
