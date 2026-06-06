# RUNBOOK — clinical-EN corpus build / refresh

How to (re)build `corpus.jsonl` from scratch or refresh it against the latest EMA
Product Information. The build is two steps: **fetch** the English PI PDFs, then
**extract** the chunked corpus.

## 0. Prerequisites (one-time)

`extract_corpus.py` needs **pymupdf** (`fitz`). `fetch_pi.py` needs only the Python
standard library. Use an isolated venv:

```bash
cd 10_Projekty/0001-navimed-umb/calibration/clinical-en
python3 -m venv .venv
.venv/bin/pip install pymupdf
```

`fetch_pi.py` downloads via Python `urllib` (works where raw `curl` egress is blocked).
If your environment blocks even `urllib`, download the PDFs manually (URL list in §3)
into `epar_raw/` named `<medicine>.pdf`, then skip to §2.

## 1. Fetch the English Product Information PDFs

```bash
# all 61 medicines (skips any already present), polite delay between requests
python3 fetch_pi.py --skip-existing --sleep 0.6

# subset / one medicine:
python3 fetch_pi.py --only osimertinib,pembrolizumab
python3 fetch_pi.py --limit 5            # first 5 in the manifest (smoke test)
```

Writes PDFs to `epar_raw/` and an audit log to `fetch_log.json` (per medicine: URL,
byte count, sha256; or a skip reason). Skipped medicines are listed with the reason —
**nothing is fabricated or substituted** on failure.

The English PI URL pattern (documented EMA convention, verified for all 61 slugs):

```
https://www.ema.europa.eu/en/documents/product-information/<epar_slug>-epar-product-information_en.pdf
```

`<epar_slug>` comes from `manifest.json`, which is derived from the verified
`clinical-pl/corpus.jsonl` `source_url`s (the same EPAR pages the Polish corpus used).
If EMA renames a slug, fix it in `manifest.json` and re-run.

## 2. Extract the corpus

```bash
.venv/bin/python extract_corpus.py
```

Writes `corpus.jsonl` (412 chunks for the current 61-medicine set) and prints a JSON
report (`n_pdfs`, `n_chunks`, `drugs_covered`, `uncertain_brand`, `uncertain_url`,
`brand_mismatch`, per-drug `candidates`/`selected`). Deterministic — same PDFs in,
same corpus out.

## 2b. Verify (optional but recommended)

Confirm every chunk is verbatim source text (0 fabrication) and PHI-free:

```bash
.venv/bin/python - <<'PY'
import json, re, importlib.util, fitz
from pathlib import Path
ex = importlib.util.module_from_spec(s:=importlib.util.spec_from_file_location('ex','extract_corpus.py')); s.loader.exec_module(ex)
RAW=Path('epar_raw'); cache={}; rows=[json.loads(l) for l in open('corpus.jsonl')]
def clean_words(med):
    doc=fitz.open(RAW/f'{med}.pdf'); ls=[]
    for p in doc: ls.extend(p.get_text().splitlines())
    doc.close(); return re.findall(r'\S+', ex.clean_join(ls))
def subseq(n,h):
    L=len(n)
    return any(h[i:i+L]==n for i in range(len(h)-L+1)) if L else True
bad=[r['chunk_id'] for r in rows if subseq(re.findall(r'\S+',r['text']), cache.setdefault(r['medicine'], clean_words(r['medicine']))) is False]
print('chunks NOT verbatim in source:', len(bad), bad[:10])
phi=re.compile(r'\b(PESEL|SSN|date of birth|patient name)\b', re.I)
print('PHI hits:', sum(bool(phi.search(r['text'])) for r in rows))
PY
```

Expected: `chunks NOT verbatim in source: 0` and `PHI hits: 0`.

## 3. Full EMA URL list (61 medicines)

Source documents = English EMA Product Information (Annex I SmPC). All verified
reachable on 2026-06-06 (`fetch_log.json`).

| medicine (INN) | brand | English Product Information PDF |
|---|---|---|
| aclidinium | Eklira Genuair | https://www.ema.europa.eu/en/documents/product-information/eklira-genuair-epar-product-information_en.pdf |
| aclidinium-formoterol | Duaklir Genuair | https://www.ema.europa.eu/en/documents/product-information/duaklir-genuair-epar-product-information_en.pdf |
| afatinib | GIOTRIF | https://www.ema.europa.eu/en/documents/product-information/giotrif-epar-product-information_en.pdf |
| alectinib | Alecensa | https://www.ema.europa.eu/en/documents/product-information/alecensa-epar-product-information_en.pdf |
| ambrisentan | Volibris | https://www.ema.europa.eu/en/documents/product-information/volibris-epar-product-information_en.pdf |
| amivantamab | Rybrevant | https://www.ema.europa.eu/en/documents/product-information/rybrevant-epar-product-information_en.pdf |
| atezolizumab | Tecentriq | https://www.ema.europa.eu/en/documents/product-information/tecentriq-epar-product-information_en.pdf |
| beclomethasone-formoterol-glycopyrronium | Trimbow | https://www.ema.europa.eu/en/documents/product-information/trimbow-epar-product-information_en.pdf |
| bedaquiline | SIRTURO | https://www.ema.europa.eu/en/documents/product-information/sirturo-epar-product-information_en.pdf |
| benralizumab | Fasenra | https://www.ema.europa.eu/en/documents/product-information/fasenra-epar-product-information_en.pdf |
| binimetinib | Mektovi | https://www.ema.europa.eu/en/documents/product-information/mektovi-epar-product-information_en.pdf |
| bosentan | Tracleer | https://www.ema.europa.eu/en/documents/product-information/tracleer-epar-product-information_en.pdf |
| brigatinib | Alunbrig | https://www.ema.europa.eu/en/documents/product-information/alunbrig-epar-product-information_en.pdf |
| cemiplimab | LIBTAYO | https://www.ema.europa.eu/en/documents/product-information/libtayo-epar-product-information_en.pdf |
| crizotinib | XALKORI | https://www.ema.europa.eu/en/documents/product-information/xalkori-epar-product-information_en.pdf |
| dacomitinib | Vizimpro | https://www.ema.europa.eu/en/documents/product-information/vizimpro-epar-product-information_en.pdf |
| docetaxel | Docetaxel Accord | https://www.ema.europa.eu/en/documents/product-information/docetaxel-accord-epar-product-information_en.pdf |
| dupilumab | Dupixent | https://www.ema.europa.eu/en/documents/product-information/dupixent-epar-product-information_en.pdf |
| durvalumab | IMFINZI | https://www.ema.europa.eu/en/documents/product-information/imfinzi-epar-product-information_en.pdf |
| elexacaftor-tezacaftor-ivacaftor | Kaftrio | https://www.ema.europa.eu/en/documents/product-information/kaftrio-epar-product-information_en.pdf |
| encorafenib | Braftovi | https://www.ema.europa.eu/en/documents/product-information/braftovi-epar-product-information_en.pdf |
| entrectinib | Rozlytrek | https://www.ema.europa.eu/en/documents/product-information/rozlytrek-epar-product-information_en.pdf |
| erlotinib | Tarceva | https://www.ema.europa.eu/en/documents/product-information/tarceva-epar-product-information_en.pdf |
| fluticasone-umeclidinium-vilanterol | Trelegy Ellipta | https://www.ema.europa.eu/en/documents/product-information/trelegy-ellipta-epar-product-information_en.pdf |
| gefitinib | IRESSA | https://www.ema.europa.eu/en/documents/product-information/iressa-epar-product-information_en.pdf |
| glycopyrronium | Seebri Breezhaler | https://www.ema.europa.eu/en/documents/product-information/seebri-breezhaler-epar-product-information_en.pdf |
| glycopyrronium-indacaterol | Ultibro Breezhaler | https://www.ema.europa.eu/en/documents/product-information/ultibro-breezhaler-epar-product-information_en.pdf |
| iloprost | Ventavis | https://www.ema.europa.eu/en/documents/product-information/ventavis-epar-product-information_en.pdf |
| indacaterol | Onbrez Breezhaler | https://www.ema.europa.eu/en/documents/product-information/onbrez-breezhaler-epar-product-information_en.pdf |
| ipilimumab | YERVOY | https://www.ema.europa.eu/en/documents/product-information/yervoy-epar-product-information_en.pdf |
| ivacaftor | Kalydeco | https://www.ema.europa.eu/en/documents/product-information/kalydeco-epar-product-information_en.pdf |
| lazertinib | Lazcluze | https://www.ema.europa.eu/en/documents/product-information/lazcluze-epar-product-information_en.pdf |
| levofloxacin | Quinsair | https://www.ema.europa.eu/en/documents/product-information/quinsair-epar-product-information_en.pdf |
| lorlatinib | Lorviqua | https://www.ema.europa.eu/en/documents/product-information/lorviqua-epar-product-information_en.pdf |
| lumacaftor-ivacaftor | Orkambi | https://www.ema.europa.eu/en/documents/product-information/orkambi-epar-product-information_en.pdf |
| macitentan | Opsumit | https://www.ema.europa.eu/en/documents/product-information/opsumit-epar-product-information_en.pdf |
| mepolizumab | Nucala | https://www.ema.europa.eu/en/documents/product-information/nucala-epar-product-information_en.pdf |
| nintedanib | Ofev | https://www.ema.europa.eu/en/documents/product-information/ofev-epar-product-information_en.pdf |
| nivolumab | OPDIVO | https://www.ema.europa.eu/en/documents/product-information/opdivo-epar-product-information_en.pdf |
| omalizumab | Xolair | https://www.ema.europa.eu/en/documents/product-information/xolair-epar-product-information_en.pdf |
| osimertinib | TAGRISSO | https://www.ema.europa.eu/en/documents/product-information/tagrisso-epar-product-information_en.pdf |
| pembrolizumab | KEYTRUDA | https://www.ema.europa.eu/en/documents/product-information/keytruda-epar-product-information_en.pdf |
| pemetrexed | Pemetrexed Accord | https://www.ema.europa.eu/en/documents/product-information/pemetrexed-accord-epar-product-information_en.pdf |
| pirfenidone | Esbriet | https://www.ema.europa.eu/en/documents/product-information/esbriet-epar-product-information_en.pdf |
| pretomanid | Dovprela | https://www.ema.europa.eu/en/documents/product-information/dovprela-epar-product-information_en.pdf |
| riociguat | Adempas | https://www.ema.europa.eu/en/documents/product-information/adempas-epar-product-information_en.pdf |
| rituximab | MabThera | https://www.ema.europa.eu/en/documents/product-information/mabthera-epar-product-information_en.pdf |
| roflumilast | Daxas | https://www.ema.europa.eu/en/documents/product-information/daxas-epar-product-information_en.pdf |
| selexipag | Uptravi | https://www.ema.europa.eu/en/documents/product-information/uptravi-epar-product-information_en.pdf |
| serplulimab | HETRONIFLY | https://www.ema.europa.eu/en/documents/product-information/hetronifly-epar-product-information_en.pdf |
| sildenafil | Revatio | https://www.ema.europa.eu/en/documents/product-information/revatio-epar-product-information_en.pdf |
| sotatercept | Winrevair | https://www.ema.europa.eu/en/documents/product-information/winrevair-epar-product-information_en.pdf |
| sotorasib | LUMYKRAS | https://www.ema.europa.eu/en/documents/product-information/lumykras-epar-product-information_en.pdf |
| tezacaftor-ivacaftor | Symkevi | https://www.ema.europa.eu/en/documents/product-information/symkevi-epar-product-information_en.pdf |
| tezepelumab | Tezspire | https://www.ema.europa.eu/en/documents/product-information/tezspire-epar-product-information_en.pdf |
| tislelizumab | Tevimbra | https://www.ema.europa.eu/en/documents/product-information/tevimbra-epar-product-information_en.pdf |
| tobramycin | TOBI Podhaler | https://www.ema.europa.eu/en/documents/product-information/tobi-podhaler-epar-product-information_en.pdf |
| tocilizumab | RoActemra | https://www.ema.europa.eu/en/documents/product-information/roactemra-epar-product-information_en.pdf |
| tremelimumab | IMJUDO | https://www.ema.europa.eu/en/documents/product-information/imjudo-epar-product-information_en.pdf |
| umeclidinium | Incruse Ellipta | https://www.ema.europa.eu/en/documents/product-information/incruse-ellipta-epar-product-information_en.pdf |
| umeclidinium-vilanterol | ANORO ELLIPTA | https://www.ema.europa.eu/en/documents/product-information/anoro-ellipta-epar-product-information_en.pdf |

## 4. Refresh policy

EMA updates Product Information periodically. To refresh: delete `epar_raw/`, re-run §1
then §2. `retrieved_at` in `extract_corpus.py` (currently `2026-06-06`) should be bumped
to the new fetch date, and `fetch_log.json` will record the new bytes/sha256 so changes
are diffable. Note that section content (and therefore chunk count) may shift slightly
when EMA revises an SmPC — this is expected and the corpus stays verbatim-faithful to
whatever was fetched.
