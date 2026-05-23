---
type: note
status: draft
domain: [pulmonologia, navimed, kalibracja-LLM]
project: "[[NaviMed_UMB_index|navimed-umb]]"
source: "NFZ Programy lekowe — Obwieszczenie Ministra Zdrowia, wersja 2026-04 (lista załączników na dzień 1.04.2026)"
created: 2026-05-20
tags: [navimed/calibration, clinical-pl, draft/proposal]
---

# Katalog leków pulmonologicznych — korpus kalibracyjny clinical-PL

> [!warning] PROPOZYCJA — do potwierdzenia przez Łukasza
> Ten katalog jest **wstępną ekstrakcją** nazw substancji czynnych z programów
> lekowych NFZ. Przed użyciem jako gold standard korpusu kalibracyjnego wymaga
> weryfikacji merytorycznej. Scrap ChPL **nie został wykonany** — to kolejny krok
> po akceptacji tej listy.

## Cel

Katalog INN (international nonproprietary name, nazwy polskie) leków
pulmonologicznych/oddechowych jako **korpus kalibracyjny** dla kwantyzacji AWQ
modelu clinical-PL w projekcie navimed-umb. Lista służy jako zbiór terminów
domenowych (drug entity recognition, normalizacja nazw, kalibracja perplexity na
tekstach klinicznych PL).

## Źródło

- **Programy lekowe:** NFZ / Ministerstwo Zdrowia — załączniki `B.xx` programów
  lekowych, wersja obowiązująca **2026-04** (indeks: *Lista załączników programów
  lekowych na dzień 1.04.2026 r.*).
- **Pliki źródłowe:** `~/Pobrane/programy_lekowe_extract/B.*.docx` (142 załączniki).
- **Sekcja bazowa (refundacja zwykła):** dostarczona ręcznie przez Łukasza —
  **nie** pochodzi z programów lekowych (patrz oznaczenie sekcji).
- **Data ekstrakcji:** 2026-05-20.

## Metoda ekstrakcji

Konwersja `.docx → XML/plaintext` (pandoc 3.1.3 + parsowanie `word/document.xml`).
Z każdego programu wyciągnięto **wyłącznie substancje czynne jawnie wymienione**
w sekcji „W ramach programu lekowego udostępnia się leczenie następującymi
substancjami" / „udostępnia się terapie" oraz w nagłówkach sekcji leczenia.
Leki wymienione **wyłącznie** jako kryterium wykluczenia, terapia poprzedzająca
lub schemat tła (nie finansowane w programie) — **wykluczone** i odnotowane w
sekcji „Wątpliwości i luki".

---

## CZĘŚĆ A — Leki z programów lekowych pulmonologicznych

Zidentyfikowano **10 programów** pulmonologicznych/oddechowych.

### B.6. — Rak płuca (ICD-10: C34) oraz międzybłoniak opłucnej (ICD-10: C45)

Program onkologiczny obejmujący NSCLC (niedrobnokomórkowy), SCLC (drobnokomórkowy)
i międzybłoniaka opłucnej. Najobszerniejszy program — leki ukierunkowane
molekularnie, immunoterapia, chemioterapia.

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

**Chemioterapia (wymieniona w schematach skojarzonych):**
- pemetreksed (pemetrexed)
- cisplatyna / karboplatyna (pochodne platyny)
- paklitaksel (paclitaxel)
- gemcytabina (gemcitabine)
- docetaksel (docetaxel)

> [!note] Uwaga — B.6
> Lista chemioterapeutyków w B.6 jest wymieniona w kontekście schematów
> skojarzonych (np. „pembrolizumab + pemetreksed + pochodna platyny"). Sam program
> lekowy finansuje przede wszystkim leki celowane/immunoterapię; chemioterapia
> może być rozliczana w ramach katalogu chemioterapii, nie programu lekowego —
> **do weryfikacji przy potwierdzaniu zakresu.**

### B.27. — Leczenie przewlekłych zakażeń płuc u świadczeniobiorców z mukowiscydozą (ICD-10: E84)

- tobramycyna (tobramycin) — wziewna
- lewofloksacyna (levofloxacin) — wziewna

### B.31. — Leczenie tętniczego nadciśnienia płucnego — TNP (ICD-10: I27, I27.0)

- bosentan
- macytentan (macitentan)
- ambrisentan *(do weryfikacji — patrz uwaga)*
- sildenafil
- riocyguat (riociguat)
- iloprost
- treprostinil
- epoprostenol
- seleksypag (selexipag)
- sotatercept

> [!note] Uwaga — B.31
> Ambrisentan nie został potwierdzony w przeszukiwaniu XML wersji 2026-01 —
> wymaga weryfikacji (mógł zostać usunięty z programu lub występować pod inną
> formą zapisu). Potwierdzone w pliku: bosentan, macytentan, sildenafil,
> riocyguat, iloprost, treprostinil, epoprostenol, seleksypag, sotatercept.

### B.74. — Leczenie przewlekłego zakrzepowo-zatorowego nadciśnienia płucnego — CTEPH (ICD-10: I27, I27.0 i/lub I26)

- riocyguat (riociguat)

> [!note] Uwaga — B.74
> Program CTEPH finansuje **wyłącznie riocyguat**. PDE5i (sildenafil, tadalafil,
> wardenafil) występują w pliku jedynie jako **kryterium wykluczenia**
> (jednoczesne podawanie z riocyguatem przeciwwskazane) — NIE są lekami programu.

### B.44. — Leczenie chorych z ciężką postacią astmy (ICD-10: J45, J82)

- omalizumab — anty-IgE
- mepolizumab — anty-IL-5
- benralizumab — anty-IL-5R
- dupilumab — anty-IL-4R / IL-13
- tezepelumab — anty-TSLP

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

> [!note] Uwaga — B.136.FM
> Program finansuje 2 terapie: (1) bedakilina + leki przeciwprątkowe,
> (2) pretomanid + bedakilina + linezolid. Leki przeciwprątkowe schematu tła
> (izoniazyd, ryfampicyna, etionamid, PAS, etambutol, pyrazynamid, amikacyna,
> kapreomycyna, kanamycyna, fluorochinolony) są wymienione jako schemat tła /
> kryteria oporności, **nie jako substancje finansowane w programie** — dlatego
> NIE włączono ich do katalogu programowego.

### B.156. — Leczenie chorych z zapaleniem nosa i zatok przynosowych z polipami nosa (ICD-10: J32, J33)

- dupilumab — anty-IL-4R / IL-13
- mepolizumab — anty-IL-5

> [!note] Status B.156
> Program laryngologiczny (CRSwNP), ale ściśle powiązany z astmą typu 2
> (wspólne biologiki). Włączony jako oddechowy — do decyzji Łukasza czy
> pozostawić w korpusie pulmonologicznym.

---

## CZĘŚĆ B — Leki spoza programów lekowych (refundacja zwykła)

> [!info] Źródło sekcji B
> Lista bazowa dostarczona ręcznie przez Łukasza — **nie** pochodzi z programów
> lekowych NFZ. To leki refundowane na zasadach ogólnych (lista refundacyjna).

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

**Kombinacje:**
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
| Część A — programy lekowe | 10 programów (B.6, B.27, B.31, B.44, B.74, B.87, B.112, B.135, B.136.FM, B.156) | 58 |
| Część B — refundacja zwykła | POChP wziewne, astma niebiologiczna, antybiotyki | 22 (monosubstancje; kombinacje liczone z komponentów) |
| **Razem (deduplikacja krzyżowa A∩B)** | — | **79 unikalnych INN** |

Uwaga deduplikacja: jedyne nakładanie krzyżowe A∩B to **lewofloksacyna** —
w B.27 (postać wziewna, mukowiscydoza) oraz w Części B (antybiotyk doustny). Stąd
58 + 22 − 1 = **79 unikalnych nazw INN**. Wewnątrz Części A **nintedanib**
występuje w 3 programach (B.6, B.87, B.135) — liczony raz. Kombinacje wziewne
POChP w Części B liczone przez monosubstancje (22 mono-INN), nazwy kombinacji
osobno nie zwiększają licznika.

### Lista programów zidentyfikowanych jako pulmonologiczne/oddechowe

| B.xx | Nazwa programu | Liczba leków |
|---|---|---|
| B.6. | Rak płuca + międzybłoniak opłucnej | 25 |
| B.27. | Przewlekłe zakażenia płuc w mukowiscydozie | 2 |
| B.31. | Tętnicze nadciśnienie płucne (TNP) | 9-10 |
| B.44. | Ciężka astma | 5 |
| B.74. | CTEPH | 1 |
| B.87. | Idiopatyczne włóknienie płuc (IPF) | 2 |
| B.112. | Mukowiscydoza (modulatory CFTR) | 4 |
| B.135. | Choroba śródmiąższowa płuc | 3 |
| B.136.FM. | Gruźlica lekooporna MDR/XDR | 3 |
| B.156. | Polipy nosa / CRSwNP | 2 |

---

## Wątpliwości i luki

1. **B.31 — ambrisentan:** nie potwierdzony w wersji 2026-01 pliku B.31. Wymaga
   weryfikacji czy nadal w programie TNP (możliwe usunięcie lub inny zapis).
2. **B.6 — chemioterapia:** pemetreksed, platyny, paklitaksel, gemcytabina,
   docetaksel wymienione w schematach skojarzonych. Niejasne czy finansowane przez
   program lekowy B.6 czy rozliczane w katalogu chemioterapii. Do decyzji czy
   włączyć do korpusu programowego.
3. **B.6 — sotorasib / adagrasib:** sotorasib potwierdzony. Adagrasib (KRAS G12C)
   NIE znaleziony — do weryfikacji czy w programie.
4. **B.6 — tarlatamab, lurbinektedyna:** leki SCLC nowej generacji NIE znalezione
   w wersji 2026-04 — do weryfikacji.
5. **B.156:** program laryngologiczny (polipy nosa); włączony ze względu na
   powiązanie z astmą typu 2. Do decyzji czy zostaje w korpusie pulmonologicznym.
6. **B.40 (Profilaktyka zakażeń wirusem RS):** NIE włączony — to profilaktyka
   pediatryczna (paliwizumab/nirsewimab), nie leczenie choroby płuc sensu stricto.
   Do decyzji Łukasza czy dołączyć (kod ICD obejmuje m.in. E84.0 — mukowiscydoza).
7. **Sekcja B — kombinacje wziewne POChP:** nazwy handlowe kombinacji nie zostały
   rozpisane wyczerpująco (przykładowe). Pełna lista refundowanych kombinacji
   wymaga osobnego źródła (obwieszczenie refundacyjne, nie programy lekowe).
8. **Nazwy polskie vs INN łacińskie:** katalog podaje formę polską (z plików NFZ)
   i w nawiasie INN angielski. Dla korpusu kalibracyjnego należy ustalić, która
   forma jest gold standard (lub obie jako warianty normalizacji).

## Następny krok (po akceptacji Łukasza)

Scrap ChPL (Charakterystyka Produktu Leczniczego) dla potwierdzonych substancji —
ekstrakcja dawkowania, wskazań, interakcji do rozszerzenia korpusu domenowego.
NIE wykonano w tym kroku.
