#!/usr/bin/env python3
"""AWQ W4A16 via llm-compressor — Qwen3.5 variant.

Same as quant_llmc.py but passes the tokenizer explicitly as `processor` so
llm-compressor 0.12 does NOT try to auto-load a multimodal (image/video)
processor for this text-only model (which fails without torchvision).
Args: <model_dir> <out_dir> <corpus.jsonl>
"""

import os
import sys
import json

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from datasets import Dataset
from transformers import AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.awq import AWQModifier

model_path, output_dir, calib_path = sys.argv[1], sys.argv[2], sys.argv[3]
MAXLEN = 512

texts = [json.loads(line)["text"] for line in open(calib_path) if line.strip()]
print(f"[quant] {len(texts)} calibration samples | model={model_path}", flush=True)

tok = AutoTokenizer.from_pretrained(model_path)
ds = Dataset.from_dict({"text": texts})
ds = ds.map(
    lambda ex: tok(ex["text"], truncation=True, max_length=MAXLEN),
    remove_columns=["text"],
)

recipe = AWQModifier(scheme="W4A16", targets="Linear", ignore=["lm_head"])

oneshot(
    model=model_path,
    processor=tok,  # <-- skip multimodal AutoProcessor auto-load
    dataset=ds,
    recipe=recipe,
    output_dir=output_dir,
    max_seq_length=MAXLEN,
    num_calibration_samples=len(texts),
)
print(f"[quant] DONE -> {output_dir}", flush=True)
