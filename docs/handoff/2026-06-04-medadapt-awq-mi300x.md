# Handoff: Bielik-11B-v3.0-medadapt AWQ on MI300X (Run-4)

**Created:** 2026-06-04
**Author:** Claude Opus 4.8 (sesja "Vault" — `~/Vaults-main`, R9700)
**For:** Claude (sesja "MI300X" — quantization runner) / Łukasz (operator)
**Operator:** Łukasz Minarowski (root orchestrator)
**Protocol:** append-only, timestamped sections, oba endy piszą do tego pliku.
**Lock convention:** brak file locking — sekwencyjnie, nowa `## YYYY-MM-DD HH:MM UTC — <author>`.

---

## Context — czytaj najpierw

- Run-1/2 (2026-05-21/22) → 8× Llama-PLLuM-70B AWQ na MI300X (AMD Dev Cloud).
- Run-3 (2026-05-24/26) → PLLuM-12B + 8B AWQ.
- **Run-4 = 1 model** (ALIA-40b dropped+usunięta 2026-06-01: iberyjski nie-PL, off-mission):
  - `jmajkutewicz/Bielik-11B-v3.0-medadapt` (llama, polski **kliniczny** CPT+SFT na Bielik-11B-v3.0)
- Pipeline IDENTYCZNY co Run-1/2/3 — `llm-compressor` AWQ W4A16, calibration `corpus.jsonl` (418 chunks SmPC clinical-PL). **NIE modyfikuj `quant_llmc.py`.**

**Dlaczego cloud, nie lokal:** oba R9700 zajęte (PLLuM-70B-base sweep, TP2, start 2026-06-04 07:36) — quant lokalnie skolidowałby z żywymi pomiarami throughput+thermal. MI300X (192 GB HBM3, TP1) liczy 11B w ~15–25 min, ~$1–1.5.

## ⚠️ LICENCJA (krytyczne)

Korpus treningowy medadapt **NIEUDOKUMENTOWANY** (brak `license` w karcie modelu).
→ skwantyzuj + upload **PRIVATE**. **NIE flip public** dopóki autor (jmajkutewicz)
nie potwierdzi licencji korpusu. `upload4.sh` tworzy repo `--private` — zostaw tak.

## Twoja rola (MI300X-side)

Sesja zalogowana na MI300X (AMD Developer Cloud — provision świeży LUB reattach do
grantu z 2026-05-21, ważny ~do 2026-06-20). Uprawnienia: `/scratch/`, hf CLI z PAT
(write scope `mozarcik/*`), ssh in/out.

**NIE rób:** public push przed Gate-1/2 PASS na R9700 + licencja; nie modyfikuj
`quant_llmc.py`; nie skracaj logów (`/scratch/run4.log` = release artefakt, METHODOLOGY §8).

## Pliki do scp (Vault-side R9700 → MI300X `/scratch/`)

| Źródło (`navimed-umb/`) | Cel | SHA256 |
|---|---|---|
| `calibration/quantization/quant_llmc.py` | `/scratch/quant_llmc.py` | `be4c67c8012dacea3370353647956192efa1457e2d03413b3732c05ad3210fa6` |
| `calibration/clinical-pl/corpus.jsonl` | `/scratch/corpus.jsonl` | `f8af734d8326e7bedb274fed14abeabb0a13439db22c9d12b0b6425e4321e1a0` |
| `calibration/quantization/run_quant4.sh` | `/scratch/run_quant4.sh` | `8fa99214a08e21ba324fcc3e3c78bd35310f94bc4ee1c90f4eedf733493f6f25` |
| `calibration/quantization/upload4.sh` | `/scratch/upload4.sh` | `b9b88afe645eefd983f53149552995436639781c546abf039f7f39a6f5533132` |

scp jedną komendą (z `~/Vaults-main/10_Projekty/0001-navimed-umb`):
```bash
scp calibration/quantization/quant_llmc.py \
    calibration/clinical-pl/corpus.jsonl \
    calibration/quantization/run_quant4.sh \
    calibration/quantization/upload4.sh \
    <MI300X_HOST>:/scratch/
```

## Tasks (kolejność)

### T1. Verify instance
```bash
hostname; date -u
df -h /scratch
rocm-smi || nvidia-smi          # 1× MI300X 192 GB HBM3
hf auth whoami                  # PAT write scope mozarcik/*
sha256sum /scratch/quant_llmc.py /scratch/corpus.jsonl /scratch/run_quant4.sh /scratch/upload4.sh
chmod +x /scratch/run_quant4.sh /scratch/upload4.sh
```
SHA256 muszą się zgadzać z tabelą wyżej. `wc -l /scratch/corpus.jsonl` = **418**.

### T2. Quant
```bash
bash /scratch/run_quant4.sh
```
Download repo (22 GB) ~kilka min + quant ~15–25 min. Sentinel: `/scratch/RUN4_COMPLETE`.
Output: `/scratch/out/Bielik-11B-v3.0-medadapt-awq/` (oczekiwane ~6–7 GB W4A16).

### T3. Upload PRIVATE
```bash
bash /scratch/upload4.sh        # → mozarcik/Bielik-11B-v3.0-medadapt-awq (PRIVATE)
```
Sentinel: `/scratch/UPLOAD4_COMPLETE`. Log: `/scratch/upload4.log`.

### T4. Teardown
Po potwierdzeniu uploadu — zniszcz droplet (billing per-sekundę). Append wynik
(walltime, OUT size, HF repo URL) do tej noty pod `## <ts> — MI300X — Run-4 result`.

## Po stronie Vault (R9700, po uploadzie) — NIE teraz

1. `hf download mozarcik/Bielik-11B-v3.0-medadapt-awq` (po zwolnieniu GPU przez sweep).
2. **Gate-1 sanity** (chat-template! — patrz memory `navimed-sanity-chat-template`: użyj `/v1/completions` lub `--chat-template`).
3. Gate-2, potem dopiero README/LICENSE/NOTICE/USE_POLICY — **public flip czeka na licencję od jmajkutewicz**.
