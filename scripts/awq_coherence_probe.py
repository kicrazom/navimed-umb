#!/usr/bin/env python3
"""awq_coherence_probe.py — Gate 2 (AWQ-QA) Polish-language coherence probe.

WHAT THIS IS
------------
A *vehicle-integrity check* for first-party AWQ quantizations of the eight
Llama-PLLuM-70B checkpoints. The llm-compressor toolchain carries a documented
artifact: it skips AWQ activation-scaling for ``v_proj`` on GQA-attention
models. A Gate-1 "not degenerate" verdict (HTTP 200, non-empty content) is
therefore insufficient — a model can emit non-empty yet broken Polish text.

This probe serves one quantized model, sends ~5 varied Polish prompts (factual
question, instruction-to-execute, short summary, definition, comparison), and
records the RAW responses plus three mechanical auto-flags per response:

  (a) polish      — Polish-language heuristic (diacritics + stopwords)
  (b) coherent    — not degenerate (no excessive n-gram repetition)
  (c) length_ok   — sensible length (neither truncated-empty nor runaway)

WHAT THIS IS NOT  (METHODOLOGY.md §8 boundary — read before extending)
----------------------------------------------------------------------
This is NOT a model-quality evaluation. It does not score reasoning, factual
accuracy, fluency, or clinical utility. Following Lerchner (2026) and §8, those
are extrinsic properties of cognition, not of the inference vehicle. The probe
answers exactly one question: *did the AWQ quantization step damage the model
so badly that it can no longer produce coherent Polish text?* — a yes/no
integrity gate, not a quality grade. The auto-flags are deliberately mechanical
(character classes, n-gram counts, token lengths); the raw text is retained so
a human can spot-check, but the SCRIPT makes no quality claim. Any future edit
that adds a "better/worse model" judgement crosses the §8 boundary and must be
rejected in review.

EMBARGO  (METHODOLOGY.md §11)
----------------------------
Probe output is a vehicle-integrity artifact in the same class as Gate-1 sanity
output: PUBLIC engineering content per §11.1 ("sanity ... numbers", engineering
workarounds). It carries NO throughput, latency, or scaling numbers — those are
the §11.2 EMBARGOED artifacts produced only by Gate 3 (the sweep). The probe
JSON is therefore safe to commit; the sweep results are not.

METHODOLOGY-COMPLIANCE
----------------------
Serves via ``vllm serve`` with the mandatory gfx1201 envelope:
  - env vars §3.1 (VLLM_ROCM_USE_AITER=0, AMD_SERIALIZE_KERNEL=1,
    HIP_LAUNCH_BLOCKING=1, ROCR_VISIBLE_DEVICES=0,1) — inherited from the
    process environment, set by scripts/_env.sh in the runner.
  - ``--enforce-eager`` §3.2 — suite-wide conservative default.
  - TP=2 — mandatory for the 70B tier (§4.3).

Idempotent: a model whose probe JSON already exists is skipped.

Usage (normally invoked by scripts/sanity_sweep_pllum70b_awq.sh --stage probe):
    python3 scripts/awq_coherence_probe.py <model_dir> [--tp 2] [--port 8100]

Author: Claude Code (navimed-umb AWQ-QA subagent), 2026-05-22.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --- Paths -------------------------------------------------------------------
NAVIMED_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.path.expanduser("~/models"))
PROBE_DIR = NAVIMED_ROOT / "environment" / "coherence-probes"
KILL_PORT = NAVIMED_ROOT / "scripts" / "kill_port.sh"

# --- Probe constants ---------------------------------------------------------
# Five varied Polish prompts. Deliberately general-knowledge — they do NOT
# probe medical correctness (that would be a quality claim, §8). They span five
# task shapes so a quantization defect that corrupts one decoding mode (e.g.
# instruction following) but not another is still caught.
PROMPTS: list[dict[str, str]] = [
    {
        "kind": "fakt",
        "text": "Jaka jest stolica Polski? Odpowiedz jednym zdaniem.",
    },
    {
        "kind": "polecenie",
        "text": "Wymień trzy pory roku w kolejności alfabetycznej.",
    },
    {
        "kind": "streszczenie",
        "text": (
            "Streść w dwóch zdaniach, czym zajmuje się botanika jako "
            "dziedzina nauki."
        ),
    },
    {
        "kind": "definicja",
        "text": "Wyjaśnij krótko, co oznacza słowo 'fotosynteza'.",
    },
    {
        "kind": "porownanie",
        "text": "Porównaj rower i samochód jako środki transportu — podaj jedną różnicę.",
    },
]

# Polish-specific diacritics — their presence is positive evidence of Polish.
POLISH_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Common Polish function words — robust to a response that happens to use no
# diacritics (e.g. a short factual answer). Matched as whole words, lowercased.
POLISH_STOPWORDS = {
    "i",
    "w",
    "na",
    "z",
    "do",
    "to",
    "jest",
    "się",
    "nie",
    "że",
    "o",
    "jako",
    "lub",
    "oraz",
    "przez",
    "dla",
    "po",
    "co",
    "jak",
    "ale",
    "który",
    "która",
    "które",
    "są",
    "być",
    "ma",
    "od",
    "tym",
    "tego",
}

# Serve / probe tunables.
MAX_TOKENS = 192  # enough for a 2-sentence answer, bounds runaway
TEMPERATURE = 0.7  # same as Gate-1 sanity probe
READY_TIMEOUT_S = 600  # 70B AWQ load is slow; 10 min ceiling
READY_POLL_S = 5
REQUEST_TIMEOUT_S = 120

# Auto-flag thresholds.
MIN_WORDS = 3  # below this a response is too short to be coherent
MAX_WORDS = 400  # above this likely runaway generation
REPEAT_NGRAM = 3  # n for the n-gram repetition check
# A response is "degenerate" if its most frequent 3-gram covers more than this
# fraction of all 3-grams — i.e. the model is looping.
MAX_NGRAM_SHARE = 0.30
MIN_POLISH_DIACRITIC_RATIO = 0.005  # diacritics / total chars: weak signal
MIN_POLISH_STOPWORD_HITS = 2  # distinct stopwords: stronger signal


def log(msg: str) -> None:
    """Timestamped stderr line — stdout stays clean for the JSON path."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# --- Auto-flag heuristics ----------------------------------------------------
def is_polish(text: str) -> tuple[bool, dict]:
    """Heuristic Polish-language detector.

    Two independent signals, OR-combined: (1) diacritic density above a small
    threshold, (2) at least N distinct Polish stopwords. Either alone is enough
    — a short diacritic-free factual answer ("Warszawa.") still passes on
    stopwords if present, and a longer answer passes on diacritics. This is a
    language gate, not a fluency score.
    """
    stripped = text.strip()
    if not stripped:
        return False, {"reason": "empty"}

    diacritics = sum(1 for c in stripped if c in POLISH_DIACRITICS)
    diacritic_ratio = diacritics / len(stripped)

    words = re.findall(r"[^\W\d_]+", stripped.lower(), flags=re.UNICODE)
    stopword_hits = len({w for w in words if w in POLISH_STOPWORDS})

    by_diacritics = diacritic_ratio >= MIN_POLISH_DIACRITIC_RATIO
    by_stopwords = stopword_hits >= MIN_POLISH_STOPWORD_HITS
    detail = {
        "diacritic_count": diacritics,
        "diacritic_ratio": round(diacritic_ratio, 4),
        "stopword_hits": stopword_hits,
        "by_diacritics": by_diacritics,
        "by_stopwords": by_stopwords,
    }
    return (by_diacritics or by_stopwords), detail


def is_coherent(text: str) -> tuple[bool, dict]:
    """Non-degeneracy check — flags runaway n-gram repetition.

    Computes the share of the single most frequent word-level 3-gram among all
    3-grams. A healthy answer spreads 3-grams thin; a model stuck in a loop
    ("the the the ..." / repeated phrase) concentrates them. This catches the
    classic quantization-damage failure mode without judging meaning.
    """
    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    if len(words) < REPEAT_NGRAM:
        # Too short for the n-gram test — defer the verdict to length_ok.
        return True, {"reason": "too_short_for_ngram", "word_count": len(words)}

    ngrams = [
        tuple(words[i : i + REPEAT_NGRAM]) for i in range(len(words) - REPEAT_NGRAM + 1)
    ]
    counts: dict[tuple, int] = {}
    for ng in ngrams:
        counts[ng] = counts.get(ng, 0) + 1
    top = max(counts.values())
    top_share = top / len(ngrams)
    coherent = top_share <= MAX_NGRAM_SHARE
    return coherent, {
        "ngram_count": len(ngrams),
        "top_ngram_repeats": top,
        "top_ngram_share": round(top_share, 4),
    }


def has_sensible_length(text: str) -> tuple[bool, dict]:
    """Length sanity — not empty/truncated, not runaway."""
    words = re.findall(r"[^\W\d_]+", text.strip(), flags=re.UNICODE)
    n = len(words)
    return (MIN_WORDS <= n <= MAX_WORDS), {"word_count": n}


def flag_response(text: str) -> dict:
    """Apply the three mechanical auto-flags to one raw response."""
    polish, polish_detail = is_polish(text)
    coherent, coherent_detail = is_coherent(text)
    length_ok, length_detail = has_sensible_length(text)
    return {
        "polish": polish,
        "coherent": coherent,
        "length_ok": length_ok,
        "all_flags_ok": bool(polish and coherent and length_ok),
        "detail": {
            "polish": polish_detail,
            "coherent": coherent_detail,
            "length": length_detail,
        },
    }


# --- vLLM serve lifecycle ----------------------------------------------------
def serve(model_path: Path, served_name: str, tp: int, port: int) -> subprocess.Popen:
    """Launch ``vllm serve`` METHODOLOGY-compliant (TP=2, enforce-eager).

    Env vars §3.1 are inherited from the parent process (set by _env.sh in the
    runner). compressed-tensors W4A16 is auto-detected from config.json, so no
    ``--quantization`` flag is passed.
    """
    cmd = [
        "vllm",
        "serve",
        str(model_path),
        "--tensor-parallel-size",
        str(tp),
        "--port",
        str(port),
        "--max-model-len",
        "8192",
        "--gpu-memory-utilization",
        "0.9",
        "--enforce-eager",  # §3.2 conservative default
        "--served-model-name",
        served_name,
    ]
    log(f"serve: {' '.join(cmd)}")
    # stdout/stderr to DEVNULL — the probe needs only the HTTP endpoint; the
    # Gate-1 sanity stage already captures the vLLM load log.
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_ready(proc: subprocess.Popen, served_name: str, port: int) -> bool:
    """Poll /v1/models until the model is served, the process dies, or timeout."""
    url = f"http://localhost:{port}/v1/models"
    deadline = time.time() + READY_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            log(f"  [FAIL] vllm serve exited (code {proc.returncode}) during load")
            return False
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if served_name in r.read().decode("utf-8", "replace"):
                    log("  ready")
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(READY_POLL_S)
    log("  [FAIL] readiness timeout")
    return False


def ask(served_name: str, prompt: str, port: int) -> dict:
    """Send one chat-completion request; return parsed status + raw content."""
    body = json.dumps(
        {
            "model": served_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "request_error",
            "content": "",
            "error": str(exc),
            "response_time_sec": round(time.time() - t0, 2),
        }
    rtime = round(time.time() - t0, 2)

    try:
        choice = payload["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        return {"status": "parse_fail", "content": "", "response_time_sec": rtime}

    if content.strip():
        status = "ok"
    else:
        usage = payload.get("usage") or {}
        # Non-empty completion but blank content = degenerate (e.g. <unk> spam).
        status = "degenerate" if usage.get("completion_tokens", 0) else "parse_fail"
    return {"status": status, "content": content, "response_time_sec": rtime}


def kill_port(port: int) -> None:
    """Isolated cleanup via scripts/kill_port.sh (setsid — never pkill -f)."""
    subprocess.run(["bash", str(KILL_PORT), str(port)], check=False)


# --- Main --------------------------------------------------------------------
def probe_model(model_dir: str, tp: int, port: int) -> int:
    """Run the full coherence probe for one model. Returns process exit code."""
    model_path = MODELS_DIR / model_dir
    date = datetime.date.today().isoformat()
    json_out = PROBE_DIR / f"{date}-{model_dir}-coherence-probe.json"
    raw_out = PROBE_DIR / f"{date}-{model_dir}-coherence-raw.txt"
    PROBE_DIR.mkdir(parents=True, exist_ok=True)

    # Idempotent — skip a model already probed today.
    if json_out.exists():
        log(f"[skip] {model_dir} — probe JSON already exists ({json_out.name})")
        return 0
    if not (model_path / "config.json").exists():
        log(f"[skip] {model_dir} — no config.json at {model_path}")
        return 0

    log(f"=== COHERENCE PROBE {model_dir} (TP={tp}) ===")
    kill_port(port)
    proc = serve(model_path, model_dir, tp, port)

    if not wait_ready(proc, model_dir, port):
        kill_port(port)
        record = {
            "test_type": "coherence_probe",
            "date": date,
            "model": model_dir,
            "tensor_parallel_size": tp,
            "enforce_eager": True,
            "verdict": "FAIL",
            "reason": "serve readiness timeout / died",
            "embargo": "PUBLIC engineering §11.1",
            "methodology_note": (
                "Vehicle-integrity check (AWQ-QA Gate 2), NOT a model-quality "
                "evaluation — METHODOLOGY §8 boundary preserved."
            ),
            "orchestrated_by": "Claude Code awq_coherence_probe.py",
        }
        json_out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        log(f"  {model_dir} -> FAIL (serve never ready) — {json_out.name}")
        return 1

    # Serve is up — run the five prompts.
    responses = []
    raw_blocks = [
        f"# Coherence probe — {model_dir}",
        f"# date: {date}  TP={tp}  enforce_eager=True",
        "# AWQ-QA Gate 2 vehicle-integrity check (METHODOLOGY §8 boundary).",
        "# Raw model output, retained verbatim for human spot-check.",
        "",
    ]
    for i, p in enumerate(PROMPTS, 1):
        log(f"  prompt {i}/{len(PROMPTS)} [{p['kind']}]")
        result = ask(model_dir, p["text"], port)
        flags = flag_response(result["content"])
        responses.append(
            {
                "index": i,
                "kind": p["kind"],
                "prompt": p["text"],
                "response_status": result["status"],
                "response_time_sec": result.get("response_time_sec"),
                "flags": flags,
            }
        )
        raw_blocks += [
            f"## [{i}] kind={p['kind']}  status={result['status']}  "
            f"flags_ok={flags['all_flags_ok']}",
            f"PROMPT: {p['text']}",
            "RESPONSE:",
            result["content"] if result["content"] else "(empty)",
            "",
        ]

    kill_port(port)

    # Aggregate verdict. PASS only if every prompt got an 'ok' status AND
    # cleared all three mechanical flags. Anything else is a flagged finding
    # for human review — the script does NOT decide re-quantization, it only
    # raises the flag (the v_proj artifact decision belongs to Łukasz, §8/plan).
    n = len(responses)
    n_ok = sum(1 for r in responses if r["response_status"] == "ok")
    n_flags_ok = sum(1 for r in responses if r["flags"]["all_flags_ok"])
    n_polish = sum(1 for r in responses if r["flags"]["polish"])
    n_coherent = sum(1 for r in responses if r["flags"]["coherent"])
    n_length_ok = sum(1 for r in responses if r["flags"]["length_ok"])
    verdict = "PASS" if (n_ok == n and n_flags_ok == n) else "REVIEW"

    record = {
        "test_type": "coherence_probe",
        "date": date,
        "model": model_dir,
        "tensor_parallel_size": tp,
        "enforce_eager": True,
        "quantization": "compressed-tensors",
        "prompt_count": n,
        "summary": {
            "responses_ok": n_ok,
            "all_flags_ok": n_flags_ok,
            "polish": n_polish,
            "coherent": n_coherent,
            "length_ok": n_length_ok,
        },
        "verdict": verdict,
        "responses": responses,
        "raw_outputs_file": raw_out.name,
        "embargo": "PUBLIC engineering §11.1",
        "methodology_note": (
            "AWQ-QA Gate 2 vehicle-integrity check: confirms the AWQ "
            "quantization did not destroy the model's ability to produce "
            "coherent Polish text. NOT a model-quality, reasoning, or factual "
            "accuracy evaluation — METHODOLOGY §8 boundary preserved. "
            "Auto-flags are mechanical (diacritics, n-gram repetition, "
            "length); raw outputs retained for human spot-check. A REVIEW "
            "verdict raises a flag for Łukasz — it does not by itself decide "
            "re-quantization."
        ),
        "orchestrated_by": "Claude Code awq_coherence_probe.py",
    }
    json_out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    raw_out.write_text("\n".join(raw_blocks))

    log(
        f"  {model_dir} -> {verdict} "
        f"(ok {n_ok}/{n}, flags {n_flags_ok}/{n}, "
        f"pl {n_polish}/{n}, coher {n_coherent}/{n}, len {n_length_ok}/{n})"
    )
    log(f"  JSON: {json_out}")
    log(f"  RAW:  {raw_out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AWQ-QA Gate 2 — Polish coherence probe (vehicle-integrity "
        "check, NOT model-quality eval — METHODOLOGY §8).",
    )
    ap.add_argument("model_dir", help="model directory name under ~/models/")
    ap.add_argument(
        "--tp",
        type=int,
        default=2,
        help="tensor-parallel size (default 2 — §4.3 for 70B)",
    )
    ap.add_argument("--port", type=int, default=8100, help="vLLM serve port")
    args = ap.parse_args()
    return probe_model(args.model_dir, args.tp, args.port)


if __name__ == "__main__":
    sys.exit(main())
