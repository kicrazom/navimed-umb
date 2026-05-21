---
type: note
status: final
domain: [pulmonology, oncology, navimed, LLM-calibration]
project: "[[NaviMed_UMB_index|navimed-umb]]"
source: "NFZ Drug Programs — Announcement of the Minister of Health, version 2026-04 (Programy_lekowe_2026-04) + base reimbursement list"
created: 2026-05-20
lang: en
tags: [navimed/calibration, clinical-pl, drug-catalog]
---

# Drug Catalog — clinical-PL Calibration Corpus (EN version)

## Description

**Rationale.** This catalog is the basis of a calibration corpus for AWQ
(AutoAWQ) quantization of PLLuM-70B models in the navimed-umb project. AWQ
quantization requires representative, dense text from the target domain; for
navimed this is dense Polish clinical language (pulmonology + thoracic
oncology).

**Construction method.** Łukasz Minarowski selected drugs from pulmonology
and thoracic oncology — from the NFZ drug programs (version 2026-04) and the
base reimbursement list — **as a source of dense Polish clinical language for
model calibration**. For each drug the Summary of Product Characteristics
(SmPC / Polish ChPL) is downloaded, the text is chunked (~512 tokens/chunk)
and saved as `corpus.jsonl` — the `calib_data` input file for AutoAWQ.

**Provenance.**
- Drug programs: `Programy_lekowe_2026-04` (Announcement of the Minister of
  Health, annexes `B.xx`, version effective 2026-04-01).
- SmPC: EMA (Polish SmPC, Annex I "Product information") for centrally
  authorized drugs; URPL Register of Medicinal Products for nationally
  authorized drugs.
- SmPC scrape date: 2026-05-20.

> [!info] Łukasz's decisions (2026-05-20)
> This version of the catalog reflects the following decisions relative to the
> initial draft (`drug-catalog.md`):
> - **INCLUDED** ambrisentan (B.31, PAH).
> - **INCLUDED** chemotherapy from B.6 (pemetrexed, cisplatin, carboplatin,
>   paclitaxel, gemcitabine, docetaxel).
> - **EXCLUDED** new-generation SCLC drugs (tarlatamab, lurbinectedin,
>   adagrasib) — not available in Poland.
> - **REMOVED** program B.156 (CRSwNP / nasal polyps) — redundant with B.44
>   (same biologics: dupilumab, mepolizumab).
> - **B.40** (RSV prophylaxis) — remains outside the catalog.
> - Inhaled COPD combinations — kept unchanged.

---

## PART A — Drugs from pulmonology drug programs

**9 programs** identified as pulmonology/respiratory (B.156 removed).

### B.6. — Lung cancer (ICD-10: C34) and pleural mesothelioma (ICD-10: C45)

Oncology program covering NSCLC (non-small-cell), SCLC (small-cell) and
pleural mesothelioma. The largest program — molecularly targeted agents,
immunotherapy, chemotherapy.

**Kinase inhibitors / molecularly targeted agents:**
- osimertinib — EGFR
- afatinib — EGFR
- dacomitinib — EGFR
- erlotinib — EGFR
- gefitinib — EGFR
- alectinib — ALK
- brigatinib — ALK
- lorlatinib — ALK
- crizotinib — ALK / ROS1
- entrectinib — ROS1
- encorafenib — BRAF V600E
- binimetinib — MEK (combined with encorafenib)
- sotorasib — KRAS G12C
- nintedanib — antiangiogenic (combined with docetaxel)

**Antibodies / immunotherapy (checkpoint inhibitors) and bispecifics:**
- amivantamab — bispecific EGFR/MET
- lazertinib — EGFR (combined with amivantamab) [TKI]
- atezolizumab — anti-PD-L1
- durvalumab — anti-PD-L1
- nivolumab — anti-PD-1
- pembrolizumab — anti-PD-1
- cemiplimab — anti-PD-1
- tislelizumab — anti-PD-1
- serplulimab — anti-PD-1
- ipilimumab — anti-CTLA-4
- tremelimumab — anti-CTLA-4

**Chemotherapy (INCLUDED — Łukasz's decision):**
- pemetrexed
- cisplatin
- carboplatin
- paclitaxel
- gemcitabine
- docetaxel

> [!note] Excluded from B.6
> New-generation SCLC drugs — **tarlatamab, lurbinectedin, adagrasib** —
> excluded from the catalog as not available in Poland.

### B.27. — Treatment of chronic lung infections in patients with cystic fibrosis (ICD-10: E84)

- tobramycin — inhaled
- levofloxacin — inhaled

### B.31. — Treatment of pulmonary arterial hypertension — PAH (ICD-10: I27, I27.0)

- bosentan
- macitentan
- ambrisentan
- sildenafil
- riociguat
- iloprost
- treprostinil
- epoprostenol
- selexipag
- sotatercept

### B.44. — Treatment of patients with severe asthma (ICD-10: J45, J82)

- omalizumab — anti-IgE
- mepolizumab — anti-IL-5
- benralizumab — anti-IL-5R
- dupilumab — anti-IL-4R / IL-13
- tezepelumab — anti-TSLP

### B.74. — Treatment of chronic thromboembolic pulmonary hypertension — CTEPH (ICD-10: I27, I27.0 and/or I26)

- riociguat

### B.87. — Treatment of idiopathic pulmonary fibrosis — IPF (ICD-10: J84.1)

- pirfenidone
- nintedanib

### B.112. — Treatment of patients with cystic fibrosis (ICD-10: E84)

CFTR modulators:
- ivacaftor — monotherapy
- lumacaftor — in combination lumacaftor/ivacaftor
- tezacaftor — in combination tezacaftor/ivacaftor
- elexacaftor — in combination elexacaftor/tezacaftor/ivacaftor

### B.135. — Treatment of patients with interstitial lung disease (ICD-10: D86, J67.0-J67.9, J84.1, J84.8, J84.9, J99.0, J99.1, M34)

- nintedanib
- rituximab
- tocilizumab

### B.136.FM. — Treatment of patients with drug-resistant tuberculosis MDR/XDR (ICD-10: A15)

- bedaquiline
- pretomanid
- linezolid

---

## PART B — Drugs outside drug programs (standard reimbursement)

> [!info] Source of Part B
> Base reimbursement list — drugs reimbursed on general terms, outside the
> NFZ drug programs.

### COPD — inhaled drugs

**LAMA (long-acting antimuscarinics):**
- tiotropium
- umeclidinium
- glycopyrronium
- aclidinium

**LABA (long-acting β2-agonists):**
- formoterol
- salmeterol
- indacaterol
- olodaterol
- vilanterol

**ICS (inhaled corticosteroids):**
- budesonide
- fluticasone
- beclomethasone

**Combinations (kept unchanged):**
- LAMA/LABA (e.g. tiotropium/olodaterol, umeclidinium/vilanterol, glycopyrronium/indacaterol, aclidinium/formoterol)
- ICS/LABA (e.g. budesonide/formoterol, fluticasone/salmeterol, fluticasone/vilanterol, beclomethasone/formoterol)
- triple ICS/LAMA/LABA (e.g. fluticasone/umeclidinium/vilanterol, beclomethasone/glycopyrronium/formoterol, budesonide/glycopyrronium/formoterol)

**PDE4 inhibitor (oral):**
- roflumilast

### Asthma — non-biologic treatment

- montelukast (leukotriene receptor antagonist, LTRA)

### Respiratory antibiotics

- amoxicillin
- amoxicillin + clavulanic acid
- azithromycin
- clarithromycin
- levofloxacin
- moxifloxacin
- doxycycline
- cefuroxime

---

## Numerical summary

| Section | Programs / categories | Active substances (unique) |
|---|---|---|
| Part A — drug programs | 9 programs (B.6, B.27, B.31, B.44, B.74, B.87, B.112, B.135, B.136.FM) | 60 |
| Part B — standard reimbursement | COPD inhaled, non-biologic asthma, antibiotics | 22 (mono-substances) |
| **Total (cross deduplication A∩B)** | — | **81 unique INN** |

Deduplication note: the only cross-overlap A∩B is **levofloxacin** — in B.27
(inhaled form) and in Part B (oral antibiotic). Hence 60 + 22 − 1 = **81
unique INN names**. **Nintedanib** appears in 3 programs (B.6, B.87, B.135) —
counted once. Relative to the initial draft (79 INN): +1 ambrisentan,
+1 carboplatin (split out from cisplatin), B.156 removed without changing the
INN count (dupilumab and mepolizumab already in B.44).

### List of pulmonology/respiratory programs

| B.xx | Program name | Drug count |
|---|---|---|
| B.6. | Lung cancer + pleural mesothelioma | 31 |
| B.27. | Chronic lung infections in cystic fibrosis | 2 |
| B.31. | Pulmonary arterial hypertension (PAH) | 10 |
| B.44. | Severe asthma | 5 |
| B.74. | CTEPH | 1 |
| B.87. | Idiopathic pulmonary fibrosis (IPF) | 2 |
| B.112. | Cystic fibrosis (CFTR modulators) | 4 |
| B.135. | Interstitial lung disease | 3 |
| B.136.FM. | Drug-resistant tuberculosis MDR/XDR | 3 |

---

## Next step

SmPC scrape (EMA / URPL) → extraction of clinical prose → chunking ~512
tokens → `corpus.jsonl` (`calib_data` for AutoAWQ). Progress and coverage
recorded in the session report and in `corpus.jsonl` / `chpl_raw/`.
