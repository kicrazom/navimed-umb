#!/usr/bin/env python3
"""Generic Gate-1 sanity grid — the standard five Polish clinical completion prompts
(factual / definitional / syndrome / instructional / procedural), verbatim from the
2026-05-26 Run-3 reference (METHODOLOGY §4.3). Loads a model offline via vLLM, records each
{prompt, output}. PUBLIC envelope data §11.1.

It RECORDS outputs + an auto-coherence hint; it does NOT stamp the public "5/5" gate — that is
a coherence judgement in the clinical domain, confirmed by the human (Łukasz) before the
dashboard cell is set. enforce_eager mandatory on gfx1201.

Usage: gate1_grid.py <model_dir-under-~/models> <tp> [--max-len 4096] [--quant auto]
Emits: GATE_RESULT_JSON={...}
"""

import argparse
import json
import sys
from pathlib import Path

PROMPTS = [
    ("factual", "Stolicą Polski jest"),
    ("definitional", "Tiotropium to lek wziewny stosowany w"),
    ("syndrome", "Astma oskrzelowa charakteryzuje się"),
    ("instructional", "Pacjent z ostrą dusznością powinien być"),
    ("procedural", "Spirometria z testem rozkurczowym pokazuje"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("tp", type=int)
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--quant", default=None)
    a = ap.parse_args()

    path = Path.home() / "models" / a.model_dir
    if not (path / "config.json").exists():
        print(f"ERROR: {path}/config.json missing", file=sys.stderr)
        return 2

    from vllm import LLM, SamplingParams  # noqa: E402

    kw = dict(
        model=str(path),
        tensor_parallel_size=a.tp,
        max_model_len=a.max_len,
        enforce_eager=True,
        gpu_memory_utilization=0.9,
    )
    if a.quant:
        kw["quantization"] = a.quant
    llm = LLM(**kw)
    outs = llm.generate(
        [p for _, p in PROMPTS], SamplingParams(max_tokens=60, temperature=0.3)
    )

    grid = []
    for (cat, prompt), o in zip(PROMPTS, outs):
        txt = o.outputs[0].text.strip()
        grid.append(
            {
                "category": cat,
                "prompt": prompt,
                "output": txt,
                "auto_coherent": len(txt) >= 20,
            }
        )  # hint only; human confirms
    res = {
        "model_dir": a.model_dir,
        "tp": a.tp,
        "n": len(grid),
        "auto_coherent_count": sum(g["auto_coherent"] for g in grid),
        "gate_stamp": None,  # set to "5/5" ONLY after human coherence review
        "grid": grid,
    }
    print("GATE_RESULT_JSON=" + json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
