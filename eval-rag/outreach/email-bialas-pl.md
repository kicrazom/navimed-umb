# Draft emaila — Adam Białas (UM Łódź)

**Status:** DRAFT do Twojego review przed wysyłką. Sprawdź ton, długość, claimy. Wszystko możesz przerobić.

**Sugerowany temat:** `Propozycja współpracy: ewaluacja polskich LLM (PLLuM, Bielik) na korpusie ChPL — kontekst PTChP`

**Sugerowane CC:** brak (pierwszy kontakt = direct only)

**Sugerowane załączniki:** brak na tym etapie (możesz dołączyć PDF/screenshot strony `huggingface.co/mozarcik/Llama-PLLuM-70B-instruct-2512-awq` jeśli odbiorca lepiej reaguje na konkret)

---

## Treść

Szanowny Panie Profesorze,

Piszę z prośbą o rozważenie współpracy naukowej. Krótko o kontekście, zanim przedstawię propozycję.

**Kontekst.** W zespole na UMB (Zakład Fizjopatologii Oddychania) prowadzę projekt `navimed-umb` — reprodukowalny benchmark lokalnego inference dużych modeli językowych na sprzęcie konsumenckim AMD (2× Radeon AI PRO R9700, gfx1201). W ramach tego projektu w sobotę 23 maja udostępniłem publicznie na Hugging Face komplet ośmiu wariantów rodziny `Llama-PLLuM-70B` skwantyzowanych do AWQ W4A16 — według mojej wiedzy pierwszy publicznie dostępny pełny zestaw AWQ tej rodziny (https://huggingface.co/mozarcik). Korpus kalibracyjny do tej kwantyzacji — 418 fragmentów polskich Charakterystyk Produktów Leczniczych z EMA (pulmonologia + onkologia klatki piersiowej, bez PHI) — również jest publiczny jako osobny artefakt.

**Pytanie naukowe, które się stąd otwiera.** Skoro PLLuM-70B w wersji AWQ rzeczywiście mieści się teraz na sprzęcie klasy klinika/zakład UM (~37 GB na pojedynczej parze kart konsumenckich) — czy odpowiada on na polskie pytania kliniczno-regulacyjne (ChPL/SmPC) merytorycznie *lepiej* niż mniejszy polski Bielik (11B, 45B), i czy ma istotną przewagę nad multilingwalnym Mistralem-Nemo (12B) lub Qwenem (27B)? Innymi słowy: czy istnieje istotna różnica jakościowa pomiędzy pięcioma modelami, które konkretnie da się dziś lokalnie i bez kosztu wdrożyć w warunkach polskiej placówki?

Tej części projekt `navimed-umb` świadomie nie mierzy — jego metodologia (§8) jest ograniczona do mierzenia *envelope'u* sprzętowego (footprint, KV cache, throughput), nie *jakości* odpowiedzi. Ewaluacja jakości wymaga oddzielnej metodologii, oddzielnego protokołu, i przede wszystkim — *klinicystów-recenzentów*.

**Propozycja.** Chciałbym zaprosić Pana Profesora do współautorstwa tej ewaluacji, w roli kluczowej:

1. **Współ-projekt zestawu 50 pytań** klinicznych, zorientowanych na obszary, w których pomyłka jest groźna (dawkowanie, interakcje, przeciwwskazania, działania niepożądane). Mam roboczy podział na 7 kategorii i proporcji — zostawiam to do dyskusji. Naturalna mapa pokrycia mojego korpusu — wziewne ICS/LABA/LAMA, antyfibrotyki w IPAF, biologiki w astmie ciężkiej — bezpośrednio przecina się z Pana dorobkiem wytycznych PTChP (np. Adv Respir Med 2026 Acute Exacerbation COPD consensus, 2024 SITT update). Pana pespektywa wytycznych byłaby tu nie do zastąpienia.

2. **Ocena 5-punktowa** wygenerowanych odpowiedzi w czterech wymiarach (faithfulness do dostarczonego fragmentu ChPL, kompletność, bezpieczeństwo kliniczne, naturalność polskiego stylu medycznego), 50 pytań × 5 modeli = 250 odpowiedzi — zakładam ~2 h pracy recenzenta, asynchronicznie w terminie 2–4 tygodni od dostarczenia odpowiedzi.

Trzeci recenzent (dr Jakub Radliński, IGiChP Rabka-Zdrój) byłby zaproszony jako *expert reviewer* dla węższego podzbioru pytań dotyczących badań czynnościowych i monitorowania.

**Autorstwo.** Proponuję kolejność zgodną z ICMJE w oparciu o wkład: ja (lead, design metodyki, generacja, integracja) — Pan Profesor (co-design pytań, ocena, interpretacja, drafting) — Radliński (expert review subset). Pierwszy autor lub corresponding ustalimy po komitecie redakcyjnym docelowego czasopisma. Naturalnym kierunkiem dla manuskryptu wydaje mi się ścieżka PTChP (Adv Respir Med), albo Adv Med Sci / PeerJ — chętnie posłucham Pana sugestii.

**Czego nie proszę.** Nie proszę o zaangażowanie infrastrukturalne, kodowe ani danych pacjentów — pipeline retrievalu i generacji jest po mojej stronie i działa na otwartym korpusie regulacyjnym (EMA, No PHI). Nie proszę też o czas teraz — pełna propozycja designu jest publicznie dostępna w repozytorium projektu (https://github.com/kicrazom/navimed-umb, podkatalog `eval-rag/`), a generacja odpowiedzi zaczyna się dopiero po Pana ewentualnej akceptacji projektu pytań.

Wdzięczny będę za każdą reakcję — także krytyczną, jeżeli widzi Pan słabość metodologiczną, którą warto poprawić przed startem.

Z wyrazami szacunku,
dr n. med. Łukasz Minarowski
Zakład Fizjopatologii Oddychania
Uniwersytet Medyczny w Białymstoku
ORCID: 0000-0002-2536-3508
e-mail: lukasz.minarowski@umb.edu.pl

---

## Notatki do review (Łukasz, do usunięcia przed wysłaniem)

- **Ton**: "specjalista do specjalisty", bez owijania, ale formalny "Pan Profesor" (Białas jest dr hab. + prof. uczelni). Jeśli wolisz partnerstwo "Drogi Adamie" — przerób.
- **Link do AWQ release**: jeden link do profilu HF; jeśli chcesz mocniej zachęcić, dorzuć link do LinkedIn posta (activity-7464059097575907328).
- **Authorship**: zaproponowałem ICMJE-style; jeśli wolisz określić wprost ("Ty pierwszy autor", "ja senior author") — to Twoja decyzja, jest miejsce w "Pierwszy autor lub corresponding ustalimy po komitecie redakcyjnym".
- **Punkt o Radlińskim**: zostawiłem wstępną wzmiankę. Można usunąć jeśli wolisz nie wymieniać tu trzecich osób przed decyzją.
- **Załącznik PDF/screenshot**: opcjonalny. Profesor Białas pisze szybkie odpowiedzi po PubMed — może preferować tekst.
- **Wytyczne PTChP**: wymieniłem 2 konkretne (Acute Exacerbation COPD consensus 2026, SITT 2024 update) — sprawdziłem PMID-y, są poprawne. Jeśli chcesz dorzucić KL-6/SP-D ILD lub IPAF papers — patrz Agent H raport.
- **Długość**: ~500 słów, jeden ekran na monitorze. Standard dla pierwszego kontaktu w PL akademii.
