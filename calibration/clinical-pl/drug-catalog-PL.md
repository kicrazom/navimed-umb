---
type: note
status: final
domain: [pulmonologia, onkologia, navimed, kalibracja-LLM]
project: "[[NaviMed_UMB_index|navimed-umb]]"
source: "NFZ Programy lekowe — Obwieszczenie Ministra Zdrowia, wersja 2026-04 (Programy_lekowe_2026-04) + bazowa lista refundacyjna"
created: 2026-05-20
lang: pl
tags: [navimed/calibration, clinical-pl, drug-catalog]
---

# Katalog leków — korpus kalibracyjny clinical-PL (wersja PL)

## Opis

**Potrzeba.** Katalog stanowi podstawę korpusu kalibracyjnego do kwantyzacji
AWQ (AutoAWQ) modeli PLLuM-70B w projekcie navimed-umb. Kwantyzacja AWQ
wymaga reprezentatywnego, gęstego tekstu z domeny docelowej; dla navimed jest
to gęsta polszczyzna kliniczna (pulmonologia + onkologia płuc).

**Sposób tworzenia.** Łukasz Minarowski wyselekcjonował leki z zakresu
pulmonologii i onkologii klatki piersiowej — z programów lekowych NFZ
(wersja 2026-04) oraz bazowej listy refundacyjnej — **jako źródło gęstej
polszczyzny klinicznej do kalibracji modelu**. Dla każdego leku pobierana jest
Charakterystyka Produktu Leczniczego (ChPL / polski SmPC), tekst jest
chunkowany (~512 tokenów/chunk) i zapisywany jako `corpus.jsonl` — plik
wejściowy `calib_data` dla AutoAWQ.

**Proweniencja.**
- Programy lekowe: `Programy_lekowe_2026-04` (Obwieszczenie Ministra Zdrowia,
  załączniki `B.xx`, wersja na 1.04.2026).
- ChPL: EMA (polski SmPC, Aneks I „Product information") dla leków
  rejestrowanych centralnie; Rejestr Produktów Leczniczych URPL dla leków
  rejestrowanych krajowo.
- Data scrapu ChPL: 2026-05-20.

> [!info] Decyzje Łukasza (2026-05-20)
> Niniejsza wersja katalogu zawiera następujące rozstrzygnięcia względem
> wstępnej propozycji (`drug-catalog.md`):
> - **WŁĄCZONO** ambrisentan (B.31, TNP).
> - **WŁĄCZONO** chemioterapię z B.6 (pemetreksed, cisplatyna, karboplatyna,
>   paklitaksel, gemcytabina, docetaksel).
> - **WYKLUCZONO** leki SCLC nowej generacji (tarlatamab, lurbinektedyna,
>   adagrasib) — niedostępne w Polsce.
> - **USUNIĘTO** program B.156 (CRSwNP / polipy nosa) — redundantny względem
>   B.44 (te same biologiki: dupilumab, mepolizumab).
> - **B.40** (profilaktyka RSV) — pozostaje poza katalogiem.
> - Kombinacje wziewne POChP — pozostawione bez zmian.

---

## CZĘŚĆ A — Leki z programów lekowych pulmonologicznych

Zidentyfikowano **9 programów** pulmonologicznych/oddechowych (B.156 usunięty).

### B.6. — Rak płuca (ICD-10: C34) oraz międzybłoniak opłucnej (ICD-10: C45)

Program onkologiczny obejmujący NSCLC (niedrobnokomórkowy), SCLC
(drobnokomórkowy) i międzybłoniaka opłucnej. Najobszerniejszy program — leki
ukierunkowane molekularnie, immunoterapia, chemioterapia.

**Inhibitory kinaz / leki ukierunkowane molekularnie:**
- ozymertynib (osimertinib) — EGFR
- afatynib (afatinib) — EGFR
- dakomitynib (dacomitinib) — EGFR
- erlotynib (erlotinib) — EGFR
- gefitynib (gefitinib) — EGFR
- alektynib (alectinib) — ALK
- brygatynib (brigatinib) — ALK
- lorlatynib (lorlatinib) — ALK
- kryzotynib (crizotinib) — ALK / ROS1
- entrektynib (entrectinib) — ROS1
- enkorafenib (encorafenib) — BRAF V600E
- binimetynib (binimetinib) — MEK (skojarzenie z enkorafenibem)
- sotorasib (sotorasib) — KRAS G12C
- nintedanib (nintedanib) — antyangiogenny (skojarzenie z docetakselem)

**Przeciwciała / immunoterapia (inhibitory punktów kontrolnych) i bispecyficzne:**
- amiwantamab (amivantamab) — bispecyficzne EGFR/MET
- lazertynib (lazertinib) — EGFR (skojarzenie z amiwantamabem) [TKI]
- atezolizumab — anty-PD-L1
- durwalumab (durvalumab) — anty-PD-L1
- niwolumab (nivolumab) — anty-PD-1
- pembrolizumab — anty-PD-1
- cemiplimab — anty-PD-1
- tislelizumab — anty-PD-1
- serplulimab — anty-PD-1
- ipilimumab — anty-CTLA-4
- tremelimumab — anty-CTLA-4

**Chemioterapia (WŁĄCZONA — decyzja Łukasza):**
- pemetreksed (pemetrexed)
- cisplatyna (cisplatin)
- karboplatyna (carboplatin)
- paklitaksel (paclitaxel)
- gemcytabina (gemcitabine)
- docetaksel (docetaxel)

> [!note] Wykluczone z B.6
> Leki SCLC nowej generacji — **tarlatamab, lurbinektedyna, adagrasib** —
> wykluczone z katalogu jako niedostępne w Polsce.

### B.27. — Leczenie przewlekłych zakażeń płuc u świadczeniobiorców z mukowiscydozą (ICD-10: E84)

- tobramycyna (tobramycin) — wziewna
- lewofloksacyna (levofloxacin) — wziewna

### B.31. — Leczenie tętniczego nadciśnienia płucnego — TNP (ICD-10: I27, I27.0)

- bosentan
- macytentan (macitentan)
- ambrisentan
- sildenafil
- riocyguat (riociguat)
- iloprost
- treprostinil
- epoprostenol
- seleksypag (selexipag)
- sotatercept

### B.44. — Leczenie chorych z ciężką postacią astmy (ICD-10: J45, J82)

- omalizumab — anty-IgE
- mepolizumab — anty-IL-5
- benralizumab — anty-IL-5R
- dupilumab — anty-IL-4R / IL-13
- tezepelumab — anty-TSLP

### B.74. — Leczenie przewlekłego zakrzepowo-zatorowego nadciśnienia płucnego — CTEPH (ICD-10: I27, I27.0 i/lub I26)

- riocyguat (riociguat)

### B.87. — Leczenie idiopatycznego włóknienia płuc — IPF (ICD-10: J84.1)

- pirfenidon (pirfenidone)
- nintedanib (nintedanib)

### B.112. — Leczenie chorych na mukowiscydozę (ICD-10: E84)

Modulatory CFTR:
- iwakaftor (ivacaftor) — monoterapia
- lumakaftor (lumacaftor) — w skojarzeniu lumakaftor/iwakaftor
- tezakaftor (tezacaftor) — w skojarzeniu tezakaftor/iwakaftor
- eleksakaftor (elexacaftor) — w skojarzeniu eleksakaftor/tezakaftor/iwakaftor

### B.135. — Leczenie pacjentów z chorobą śródmiąższową płuc (ICD-10: D86, J67.0-J67.9, J84.1, J84.8, J84.9, J99.0, J99.1, M34)

- nintedanib (nintedanib)
- rytuksymab (rituximab)
- tocilizumab

### B.136.FM. — Leczenie chorych na gruźlicę lekooporną MDR/XDR (ICD-10: A15)

- bedakilina (bedaquiline)
- pretomanid (pretomanid)
- linezolid (linezolid)

---

## CZĘŚĆ B — Leki spoza programów lekowych (refundacja zwykła)

> [!info] Źródło sekcji B
> Bazowa lista refundacyjna — leki refundowane na zasadach ogólnych, poza
> programami lekowymi NFZ.

### POChP — leki wziewne

**LAMA (długo działające antycholinergiki):**
- tiotropium
- umeklidynium (umeclidinium)
- glikopironium (glycopyrronium)
- aklidynium (aclidinium)

**LABA (długo działające β2-mimetyki):**
- formoterol
- salmeterol
- indakaterol (indacaterol)
- olodaterol
- wilanterol (vilanterol)

**ICS (wziewne glikokortykosteroidy):**
- budezonid (budesonide)
- flutykazon (fluticasone)
- beklometazon (beclomethasone)

**Kombinacje (pozostawione bez zmian):**
- LAMA/LABA (np. tiotropium/olodaterol, umeklidynium/wilanterol, glikopironium/indakaterol, aklidynium/formoterol)
- ICS/LABA (np. budezonid/formoterol, flutykazon/salmeterol, flutykazon/wilanterol, beklometazon/formoterol)
- triple ICS/LAMA/LABA (np. flutykazon/umeklidynium/wilanterol, beklometazon/glikopironium/formoterol, budezonid/glikopironium/formoterol)

**Inhibitor PDE4 (doustny):**
- roflumilast

### Astma — leczenie niebiologiczne

- montelukast (antagonista receptora leukotrienowego, LTRA)

### Antybiotyki oddechowe

- amoksycylina (amoxicillin)
- amoksycylina + kwas klawulanowy (amoxicillin/clavulanic acid)
- azytromycyna (azithromycin)
- klarytromycyna (clarithromycin)
- lewofloksacyna (levofloxacin)
- moksyfloksacyna (moxifloxacin)
- doksycyklina (doxycycline)
- cefuroksym (cefuroxime)

---

## Podsumowanie liczbowe

| Sekcja | Programy / kategorie | Substancje czynne (unikalne) |
|---|---|---|
| Część A — programy lekowe | 9 programów (B.6, B.27, B.31, B.44, B.74, B.87, B.112, B.135, B.136.FM) | 60 |
| Część B — refundacja zwykła | POChP wziewne, astma niebiologiczna, antybiotyki | 22 (monosubstancje) |
| **Razem (deduplikacja krzyżowa A∩B)** | — | **81 unikalnych INN** |

Uwaga deduplikacja: jedyne nakładanie krzyżowe A∩B to **lewofloksacyna** —
w B.27 (postać wziewna) oraz w Części B (antybiotyk doustny). Stąd
60 + 22 − 1 = **81 unikalnych nazw INN**. **Nintedanib** występuje w 3
programach (B.6, B.87, B.135) — liczony raz. Względem wstępnej propozycji
(79 INN): +1 ambrisentan, +1 karboplatyna (rozdzielona z cisplatyną), B.156
usunięty bez zmiany licznika INN (dupilumab i mepolizumab już w B.44).

### Lista programów pulmonologicznych/oddechowych

| B.xx | Nazwa programu | Liczba leków |
|---|---|---|
| B.6. | Rak płuca + międzybłoniak opłucnej | 31 |
| B.27. | Przewlekłe zakażenia płuc w mukowiscydozie | 2 |
| B.31. | Tętnicze nadciśnienie płucne (TNP) | 10 |
| B.44. | Ciężka astma | 5 |
| B.74. | CTEPH | 1 |
| B.87. | Idiopatyczne włóknienie płuc (IPF) | 2 |
| B.112. | Mukowiscydoza (modulatory CFTR) | 4 |
| B.135. | Choroba śródmiąższowa płuc | 3 |
| B.136.FM. | Gruźlica lekooporna MDR/XDR | 3 |

---

## Następny krok

Scrap ChPL (EMA / URPL) → ekstrakcja prozy klinicznej → chunking ~512 tokenów
→ `corpus.jsonl` (`calib_data` dla AutoAWQ). Postęp i pokrycie odnotowane
w raporcie sesji oraz w `corpus.jsonl` / `chpl_raw/`.
