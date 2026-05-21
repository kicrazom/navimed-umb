#!/usr/bin/env python3
"""Re-derive the navimed clinical-PL calibration corpus with per-chunk provenance.

The original corpus.jsonl (415 chunks, ~61k words, text-only) was a *curated
sample* of dense Polish clinical prose drawn from the Annex I SmPC of 61 EMA
Product Information PDFs (each PDF also contains Annex II + Annex III
labelling/leaflet, which are NOT clinical prose).

This script reproduces a materially equivalent corpus:
  - restricts extraction to Annex I (SmPC) only,
  - drops the section 6 pharmaceutical-particulars tail (excipients, shelf-life,
    marketing-authorisation boilerplate) which is not clinical prose,
  - chunks at ~150 words/chunk, sentence-boundary preferred, hard word cap
    (matches original: median 143 words, max 254),
  - samples ~415 chunks total, allocated per drug proportionally to that drug's
    Annex I clinical-prose volume, biased toward clinical-efficacy /
    pharmacology sections (original profile: 56% efficacy, 13% pharmacology),
  - attaches full provenance metadata to every chunk.

Run inside a venv with pymupdf installed.
"""

import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

RAW_DIR = Path(__file__).resolve().parent / "chpl_raw"
OUT = RAW_DIR.parent / "corpus.jsonl"

RETRIEVED_AT = "2026-05-20"
LICENSE_NOTE = "EMA reproduction policy; source attribution required"
DOC_TYPE = "SmPC / Product Information"

TARGET_TOTAL = 415  # target corpus size (material equivalence)
TARGET_WORDS = 150  # soft chunk window
MAX_WORDS = 255  # hard cap (matches observed max 254)
MIN_WORDS = 80  # minimum viable chunk

# clinical-prose section weighting for the sampling bias. Tuned so the
# resulting content profile approximates the original curated corpus
# (~56% clinical-efficacy prose, ~13% pharmacology, ~7% dosing, rest mixed).
# Section 5.1 is the largest section in most SmPCs, so a moderate weight
# already dominates; over-weighting it crowds out everything else.
SECTION_WEIGHT = {
    "5.1": 1.6,  # clinical efficacy & safety  (original ~56%)
    "5.2": 1.3,  # pharmacokinetics
    "5.3": 0.9,  # preclinical safety
    "4.2": 1.2,  # posology / dosing
    "4.4": 1.3,  # special warnings & precautions
    "4.5": 1.0,  # interactions
    "4.6": 0.9,  # fertility / pregnancy / lactation
    "4.8": 1.0,  # adverse reactions (prose parts)
    "4.1": 0.8,  # indications
    "4.3": 0.6,  # contraindications
    "4.9": 0.6,  # overdose
    "5.0": 0.8,  # section 5 intro / other 5.x
}
DEFAULT_WEIGHT = 0.7


# --- brand name + URL --------------------------------------------------------
def extract_brand_name(full_text: str) -> str:
    m = re.search(
        r"1\.\s*(?:NAZWA PRODUKTU LECZNICZEGO|NAME OF THE MEDICINAL PRODUCT)",
        full_text,
        re.I,
    )
    if not m:
        return ""
    tail = re.split(r"\n\s*2\.\s", full_text[m.end() : m.end() + 400])[0]
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    if not lines:
        return ""
    first = lines[0]
    mm = re.match(r"^([A-Za-zÀ-ÿ][\w®™\-]*(?:\s[A-Za-zÀ-ÿ][\w®™\-]*)?)", first)
    if not mm:
        return first
    cand = mm.group(1).strip()
    cand = re.sub(
        r"\s+(tabletki|kapsu\w*|roztw\w*|proszek|koncentrat|film|"
        r"injection|solution).*$",
        "",
        cand,
        flags=re.I,
    ).strip()
    return cand


def epar_url(brand_name: str) -> str:
    """Best-effort EMA EPAR URL from the brand name.

    Verified empirically: EMA EPAR slugs use the FULL brand name with spaces
    -> hyphens, lowercased (e.g. 'Eklira Genuair' -> 'eklira-genuair',
    'Docetaxel Accord' -> 'docetaxel-accord', 'Keytruda' -> 'keytruda').
    """
    if not brand_name:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-")
    return f"https://www.ema.europa.eu/en/medicines/human/EPAR/{slug}" if slug else ""


# --- Annex I extraction ------------------------------------------------------
def annex1_pages(doc) -> tuple[int, int]:
    """Return [start, end) page range of Annex I (SmPC)."""
    start = 0
    end = len(doc)
    for i, pg in enumerate(doc):
        if re.search(r"\bANEKS\s+II\b", pg.get_text()):
            end = i
            break
    return start, end


SENT_END = re.compile(r"(?<=[.!?])\s+")
DROP_LINE = re.compile(
    r"^\s*(?:\d+\s*)?$" r"|^ANEKS\b" r"|^CHARAKTERYSTYKA PRODUKTU LECZNICZEGO\s*$",
    re.I,
)
# section 6 onward = pharmaceutical particulars / MA holder boilerplate
SEC6 = re.compile(r"^\s*6\.\s+DANE FARMACEUTYCZNE", re.I)
# SmPC numbered section headers. In these EMA PDFs the header line is usually
# just the bare number ("4.1 ") with the section title on the following line;
# occasionally number and title share a line ("4.1 Wskazania...").
# A header line is the number followed by EOL or whitespace + a title that
# starts with a letter (never punctuation -> excludes prose like "5.1).").
SEC_HEADER = re.compile(r"^\s*([45])\.(\d)\s*(?:[A-Za-zÀ-ÿ].*)?$")


def clean_join(raw_lines) -> str:
    out = []
    for ln in raw_lines:
        s = ln.strip()
        if not s or DROP_LINE.match(s):
            continue
        out.append(s)
    text = " ".join(out)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def annex1_sections(doc):
    """Extract Annex I as a list of (section_key, prose_text) segments.

    section_key is like '5.1', '4.8', or '5.0' for the section-5 intro / other.
    Section 6 onward is dropped.
    """
    s, e = annex1_pages(doc)
    lines = []
    for i in range(s, e):
        lines.extend(doc[i].get_text().splitlines())

    # split into sections at numbered headers; capture only sections 4.x/5.x
    # (clinical particulars + pharmacological properties). Sections 1-3
    # (name, composition, pharmaceutical form) and 6+ are not clinical prose.
    segments = []
    cur_key = None
    cur_lines = []
    for ln in lines:
        if SEC6.match(ln):
            break
        m = SEC_HEADER.match(ln)
        if m:
            if cur_key is not None and cur_lines:
                segments.append((cur_key, cur_lines))
            cur_key = f"{m.group(1)}.{m.group(2)}"
            cur_lines = [ln]
        elif cur_key is not None:
            cur_lines.append(ln)
        # lines before the first 4.x/5.x header are dropped
    if cur_key is not None and cur_lines:
        segments.append((cur_key, cur_lines))

    out = []
    for key, raw in segments:
        prose = clean_join(raw)
        if len(prose.split()) >= MIN_WORDS:
            # normalise section-5 intro / unkeyed -> '5.0'
            k = (
                key
                if key in SECTION_WEIGHT
                else ("5.0" if key.startswith("5") else key)
            )
            out.append((k, prose))
    return out


def chunk_text(text: str):
    sentences = [x.strip() for x in SENT_END.split(text) if x.strip()]
    chunks, buf, buf_words = [], [], 0

    def flush():
        nonlocal buf, buf_words
        if buf:
            chunks.append(" ".join(buf).strip())
            buf, buf_words = [], 0

    for sent in sentences:
        wc = len(sent.split())
        if wc > MAX_WORDS:
            flush()
            w = sent.split()
            for i in range(0, wc, MAX_WORDS):
                chunks.append(" ".join(w[i : i + MAX_WORDS]).strip())
            continue
        if buf_words + wc > MAX_WORDS:
            flush()
        buf.append(sent)
        buf_words += wc
        if buf_words >= TARGET_WORDS:
            flush()
    flush()
    if len(chunks) >= 2 and len(chunks[-1].split()) < MIN_WORDS:
        tail = chunks.pop()
        if len((chunks[-1] + " " + tail).split()) <= MAX_WORDS:
            chunks[-1] += " " + tail
        else:
            chunks.append(tail)
    return chunks


def main():
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"no PDFs in {RAW_DIR}")

    # ---- pass 1: extract all candidate chunks per drug, weighted ----
    per_drug = {}  # medicine -> dict
    report = {
        "n_pdfs": len(pdfs),
        "target_total": TARGET_TOTAL,
        "uncertain_brand": [],
        "uncertain_url": [],
        "per_drug": [],
    }

    for pdf in pdfs:
        medicine = pdf.stem
        doc = fitz.open(pdf)
        head = "\n".join(doc[i].get_text() for i in range(min(6, len(doc))))
        brand = extract_brand_name(head)
        url = epar_url(brand)
        if not brand:
            report["uncertain_brand"].append(medicine)
        if not url:
            report["uncertain_url"].append(medicine)

        candidates = []  # (weight, section_key, chunk_text)
        for sec_key, prose in annex1_sections(doc):
            w = SECTION_WEIGHT.get(sec_key, DEFAULT_WEIGHT)
            for ch in chunk_text(prose):
                if len(ch.split()) >= MIN_WORDS:
                    candidates.append((w, sec_key, ch))
        doc.close()
        per_drug[medicine] = {
            "brand": brand,
            "url": url,
            "candidates": candidates,
        }

    # ---- allocate ~TARGET_TOTAL chunks proportionally per drug ----
    total_cand = sum(len(d["candidates"]) for d in per_drug.values())
    records = []
    for medicine in sorted(per_drug):
        d = per_drug[medicine]
        cands = d["candidates"]
        if not cands:
            report["per_drug"].append(
                {
                    "medicine": medicine,
                    "brand": d["brand"],
                    "candidates": 0,
                    "selected": 0,
                    "url": d["url"],
                }
            )
            continue
        # proportional allocation, >=1 per drug, capped at available
        quota = max(1, round(TARGET_TOTAL * len(cands) / total_cand))
        quota = min(quota, len(cands))
        # stratified-by-section selection: distribute the quota across the
        # drug's SmPC sections in proportion to (section_count * weight),
        # then within each section pick evenly spaced candidates. This keeps
        # the section mix close to the original corpus instead of collapsing
        # onto whichever section is largest.
        by_sec = {}
        for i, (w, sec, _) in enumerate(cands):
            by_sec.setdefault(sec, {"w": w, "idx": []})["idx"].append(i)
        sec_score = {s: v["w"] * len(v["idx"]) for s, v in by_sec.items()}
        score_sum = sum(sec_score.values()) or 1.0
        chosen = []
        for sec, v in by_sec.items():
            avail = v["idx"]
            share = max(1, round(quota * sec_score[sec] / score_sum))
            take = min(share, len(avail))
            if take >= len(avail):
                chosen.extend(avail)
            else:
                step = len(avail) / take
                chosen.extend(
                    avail[min(len(avail) - 1, int(j * step))] for j in range(take)
                )
        chosen = sorted(set(chosen))
        # trim/pad to the exact quota
        if len(chosen) > quota:
            step = len(chosen) / quota
            chosen = sorted(
                chosen[min(len(chosen) - 1, int(j * step))] for j in range(quota)
            )
            chosen = sorted(set(chosen))
        elif len(chosen) < quota:
            extra = [i for i in range(len(cands)) if i not in set(chosen)]
            chosen = sorted(set(chosen) | set(extra[: quota - len(chosen)]))
        for n, idx in enumerate(chosen, start=1):
            _, sec_key, text = cands[idx]
            records.append(
                {
                    "text": text,
                    "source_authority": "EMA",
                    "source_document_type": DOC_TYPE,
                    "source_url": d["url"],
                    "medicine": medicine,
                    "brand_name": d["brand"],
                    "language": "pl",
                    "retrieved_at": RETRIEVED_AT,
                    "chunk_id": f"EMA_{medicine}_pl_{n:04d}",
                    "license_note": LICENSE_NOTE,
                }
            )
        report["per_drug"].append(
            {
                "medicine": medicine,
                "brand": d["brand"],
                "candidates": len(cands),
                "selected": quota,
                "url": d["url"],
            }
        )

    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    report["n_chunks"] = len(records)
    report["drugs_covered"] = sum(1 for p in report["per_drug"] if p["selected"] > 0)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
