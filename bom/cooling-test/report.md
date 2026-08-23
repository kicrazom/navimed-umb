# Cooling A/B/C: Noctua NH-D15 G2 ↔ NL-LC1-42

CPU: AMD Ryzen 9 9950X3D (16C/32T, Tctl limit 95 °C — throttling objawia się spadkiem MHz, nie wzrostem temperatury).
Procedura: `cooling_ab_test.sh` — 10 min idle → 40 min stress-ng `matrixprod` (32 wątki) → 10 min cooldown, próbkowanie sensorów co 5 s (k10temp + asusec). Walltime ~61 min / przebieg.

> **🔴 Przebieg B jest NIEWAŻNY.** Jechał z zatrzymanymi wentylatorami chłodnicy. Zachowany
> w tabeli wyłącznie jako kontrola negatywna — pokazuje, ile kosztuje brak przepływu powietrza
> przez chłodnicę. Nie używaj go do oceny LC1-42. Szczegóły w sekcji „Unieważnienie" poniżej.

## Przebiegi

| tag | data | chłodzenie | stan wentylatorów chłodnicy | ważny |
|---|---|---|---|---|
| `noctua` | 2026-07-31 | NH-D15 G2 | pracują, 1436 RPM | ✅ |
| `lc142` | 2026-08-23 00:35 | NL-LC1-42 | **stoją, 0 RPM** | ❌ artefakt |
| `lc142-fanC` | 2026-08-23 08:33 | NL-LC1-42 | pracują, 2162 RPM | ✅ |

## Warunki

Kontrolowane we wszystkich przebiegach: GPU bezczynne (vLLM zatrzymany, PPT 6 W), maszyna nieużywana,
`systemd-inhibit` aktywny, ambient zmierzony i podany do skryptu (metryka porównawcza = ΔT nad otoczeniem),
BIOS 2202, PBO bez zmian.

**Zmienne, które NIE były kontrolowane** (i o które ten test się potknął):

- **krzywa wentylatorów** — A i B jechały na krzywej odziedziczonej po NH-D15 G2, C na krzywej
  zmienionej przez operatora 2026-08-23 rano. To ta zmiana ujawniła błąd (patrz niżej).
- **obciążenie tła w fazie idle** — A z aktywnymi przeglądarkami, B na maszynie wyciszonej,
  C z aktywnym Obsidianem. Faza idle jest przez to nieporównywalna między przebiegami.
- **kernel** — A `7.0.0-28`, B `7.0.0-29`, C `7.0.0-30`.
- **tryb wentylatorów obudowy ProArt PA602** — w A ustawiony na `max`, w B i C nieustalony.

Faza load pozostaje odporna: stress-ng nasyca wszystkie 32 wątki w każdym przebiegu.
**Wnioski wyciągaj wyłącznie z fazy load.**

## Wyniki

| Metryka | A: NH-D15 G2 | B: LC1-42 (went. 0 RPM) | C: LC1-42 (went. pracują) |
|---|---:|---:|---:|
| otoczenie [°C] | 24.5 | 23.5 | 24.0 |
| idle Tctl (śr. ost. 5 min) [°C] | 55.6 | 47.1 | 45.2 |
| ΔT idle [K] ⚠ | 31.1 | 23.6 | 21.2 |
| load Tctl (śr. ost. 10 min) [°C] | 80.6 | 83.4 | 80.8 |
| **ΔT load nad otoczeniem [K]** | **56.1** | 59.9 | **56.8** |
| **load Tctl max [°C]** | **81.2** | 86.4 | **81.2** |
| zegar śr. pod obciążeniem [MHz] | 5042 | 5019 | 5017 |
| bogo-ops/s (stress-ng, real time) | 25 942 | 25 974 | 25 929 |
| `CPU_Opt` śr. pod obciążeniem [RPM] | 1436 | **0** | 2162 |
| Tctl po 10 min cooldownu [°C] | 54.8 | 45.9 | 45.1 |
| **głośność @ 50 cm [dBA]** | **53–55** | niezmierzona | **51.2–53** |

⚠ ΔT idle **nie jest porównywalne między przebiegami** — różne obciążenie tła (patrz „Warunki”).
Kierunek (AIO chłodniej na idle) jest wiarygodny, magnituda zawyżona.

Głośność: aplikacja **SPL Meter (KTW Apps)**, telefon, **50 cm w obu pomiarach**, faza load.
Mikrofon nieskalibrowany → **wartości bezwzględne traktuj jako wskazania aplikacji, nie dBA**.
Różnica względna jest wiarygodna (ten sam przyrząd, ta sama odległość, ten sam typ obciążenia).
Tło pomieszczenia niezmierzone. Pomiar dla A wykonany 2026-08-23, poza logowanym przebiegiem A.

## 🔴 Unieważnienie przebiegu B

**Wentylatory chłodnicy NL-LC1-42 są wpięte w header `CPU_OPT`** (zweryfikowane w BIOS-ie
2026-08-23 przez operatora). W przebiegu B kanał `CPU_Opt` raportował **0 RPM we wszystkich
próbkach, przez całe 61 minut — w tym przez 40 minut stress-ng**. Header, w który nic nie jest
wpięte, nie potrafi później zwrócić 2162 RPM; wentylator wpięty i pracujący raportowałby obroty
pod obciążeniem. Wniosek: **w przebiegu B wentylatory chłodnicy stały**.

Skutki:

1. Werdykt „LC1-42 gorszy o 3.8 K ΔT" **jest artefaktem braku przepływu powietrza**, nie
   właściwością chłodzenia. Porównywał wieżę z pracującym wentylatorem przeciw chłodnicy
   bez nadmuchu.
2. Wcześniejsza diagnoza „pompa siedzi na `AIO_PUMP`, kanał `CPU_Opt` niedostępny dla
   `asus-ec-sensors`" **była błędna**. Kanał był dostępny cały czas i raportował prawdę —
   zero. Wzorzec `CPU_Opt` w `snap()` był poprawny; awaria leżała w interpretacji, nie w kodzie.
3. Model „brak przepływu" tłumaczy **cały** zestaw obserwacji B naraz, co go uwiarygadnia:
   gorszy pod obciążeniem (chłodnica nie oddaje ciepła), a jednocześnie lepszy w stygnięciu
   i na idle (masa wody radzi sobie pasywnie z małym obciążeniem).

**Reguła wyciągnięta na przyszłość:** zero na kanale, który potrafi raportować, jest **pomiarem,
nie brakiem danych**. Zanim uznasz metrykę za niedostępną, sprawdź, czy ten sam kanał daje
niezerowy odczyt w innych warunkach — tu wystarczyło zauważyć, że przy Noctui `CPU_Opt`
pokazywał 1436 RPM. Zapis `NA` zamiast zera, wprowadzony żeby nie fałszować danych,
**zamaskował sygnał** — patrz „Dług" niżej.

## Interpretacja

**Pod obciążeniem C ≈ A. Remis.**

ΔT load 56.8 vs 56.1 K (+0.7 K, poniżej szumu pojedynczego przebiegu), `Tctl max` **identyczny
co do dziesiątej: 81.2 °C**, zegar −25 MHz (−0.5 %), przepustowość −13 bogo-ops/s (−0.05 %).
Trzy niezależne metryki zgodnie mówią, że tych chłodzeń nie da się rozróżnić pod sustained
all-core. Deficyt 3.8 K z przebiegu B zniknął wraz z uruchomieniem wentylatorów — unieważnienie
potwierdzone pomiarem, nie samym rozumowaniem.

Hipoteza „niższe temperatury odblokują wyższy boost PBO" pozostaje **obalona**, ale z innego
powodu niż zakładał poprzedni wniosek: NH-D15 G2 nie throttlował (5042 MHz przez 40 min,
zapas ~14 K do limitu), więc nie było czego odblokowywać. Żadne chłodzenie nie kupi tu
wydajności, bo wydajność nie jest ograniczona termicznie.

**Gdzie LC1-42 wygrywa:**

- **cooldown** — 45.1 vs 54.8 °C po 10 min. Przewaga potwierdzona w obu przebiegach AIO,
  także w B ze stojącymi wentylatorami, co potwierdza że źródłem jest masa termiczna wody.
- **głośność** — ~2 dBA ciszej przy tym samym wyniku termicznym. Różnica jest **przy progu
  rozróżnialności ucha** (~3 dB dla szumu szerokopasmowego) i zakresy się stykają na 53 dBA,
  więc kierunek jest wiarygodny, a skala praktycznie nieistotna.
- **idle** — kierunkowo, magnituda niepewna (patrz ⚠).

Wynik uboczny wart odnotowania: AIO osiąga ten sam efekt termiczny przy **2162 RPM tam, gdzie
wieża potrzebowała 1436** — o 50 % wyższe obroty, a mimo to ciszej. Wentylatory chłodnicy są
jednostkowo wyraźnie cichsze od wentylatorów NH-D15 G2.

**Wniosek operacyjny: LC1-42 zostaje.** Nie dlatego, że wygrał termicznie — pod obciążeniem to
remis. Dlatego, że nie przegrywa nic mierzalnego, jest nieznacznie ciszej, lepiej stygnie i już
jest zamontowany. Gdyby wybór stał otworem przy pustej płycie, wieża byłaby rozsądniejsza
(brak pompy = mniej trybów awarii, ten sam wynik); to nie jest wystarczający powód, żeby ją
teraz wkręcać z powrotem.

### ⛔ Punkt bezpieczeństwa: czy krzywa spełnia wymóg producenta

Instrukcja NL-LC1 (`NOCTUA NL-LC1 Manual EN`, sekcja 5 „Connecting the fans and the pump"):

> „the fans must only be shut off (0% PWM) if the CPU is running at temperatures lower than
> 60 °C and that the fans must be set to **80% PWM or more at the CPU's maximum operating
> temperature**. Letting the fans shut off at higher CPU temperatures or limiting the fan speed
> below 80% PWM at the maximum operating temperature **can lead to elevated liquid temperatures
> and cause damage to the cooler**."

**Przebieg B naruszył ten wymóg wprost:** wentylatory na 0 % PWM przy Tctl 83.4 °C średnio
i 86.4 °C maksymalnie, przez 40 minut. To jest dokładnie scenariusz, przed którym ostrzega
producent („elevated liquid temperatures and cause damage to the cooler”).

**Do sprawdzenia — czy chłodnica nie ucierpiała:** przebieg B to jednorazowa ~40-minutowa
ekspozycja, więc uszkodzenie jest mało prawdopodobne, ale przebieg C daje punkt odniesienia
na przyszłość — jeśli przy tej samej krzywej i tym samym obciążeniu ΔT load zacznie rosnąć
w kolejnych miesiącach, będzie to sygnał degradacji cieczy. **Zanotuj C jako baseline: 56.8 K.**

**Otwarte dla przebiegu C:** czy nowa krzywa daje ≥80 % PWM przy maksymalnej temperaturze
roboczej. `CPU_Opt` pod obciążeniem = 2162 RPM, ale procent PWM nie jest czytelny z `sensors` —
**odczytaj w BIOS-ie**, jaki procent odpowiada tym obrotom przy ~85 °C. Bez tego nie wiadomo,
czy C jest zgodny z instrukcją, mimo że termicznie wypadł dobrze.

### ❓ Niespójność do rozstrzygnięcia: co właściwie czyta `CPU_Opt`

2162 RPM pod obciążeniem i ~1520 RPM na idle to **obroty wysokie jak na 140 mm wentylator
chłodnicy**, a mieszczące się w podanym przez producenta zakresie **pompy** (quiet 750–2100,
balanced 750–2600). Nie mam jak tego rozstrzygnąć z poziomu systemu — `asus-ec-sensors`
eksponuje jeden kanał bez etykiety źródła.

Argument za tym, że to jednak **wentylatory**: gdyby `CPU_Opt` = pompa, przebieg B jechałby
40 minut all-core z **zatrzymaną pompą**, a wtedy Tctl uderzyłby w limit 95 °C i throttling
w ciągu minut. Zmierzone 86.4 °C max jest na to o wiele za dobre. Stojące wentylatory przy
pracującej pompie tłumaczą +3.8 K; stojąca pompa nie tłumaczy tak łagodnego wyniku.

**Do weryfikacji w BIOS-ie:** porównaj odczyt RPM na `CPU_OPT` i `AIO_PUMP` przy obciążeniu
i sprawdź, który zgadza się z 2162. Zapisz wynik tutaj — od tego zależy, czy w kolejnych
przebiegach kolumna RPM opisuje wentylatory, czy pompę.

### Tryb pompy

NL-LC1-42 wychodzi z fabryki z profilem **„quiet"** (przełącznik na bloku pompy, pod
magnetycznym faceplate'em / NL-ACF1; prawa pozycja = quiet, środkowa = balanced).
Zakresy: quiet 750–2100 rpm*, balanced 750–2600 rpm*, manual 750–3400 rpm.
**Stan potwierdzony oględzinami 2026-08-23: `quiet`, pozycja fabryczna** — niezmieniony
w przebiegach B i C.

`*up to 3400rpm at higher liquid temperatures` — pompa auto-boostuje niezależnie od trybu,
gdy rośnie temperatura cieczy (zintegrowany czujnik, próg ok. 45 °C). Skoro C osiąga parytet
z wieżą **na trybie quiet**, hipoteza „quiet dławi przepływ" jest **wykluczona** — nie ma luki
do wytłumaczenia. Przebieg z trybem balanced stracił uzasadnienie.

### Wykluczone

**Osłona pasty (Noctua NA-TPG1) — wykluczona.** Producent podaje brak mierzalnego wpływu na
temperatury; osłona obejmuje krawędzie IHS, nie wchodzi pod coldplate, przewidziana do
pozostawienia na stałe. Przebieg C potwierdza to niezależnie: ta sama osłona, ten sam montaż,
a wynik termiczny na poziomie wieży.

**Podłączenie pompy zgodne z instrukcją.** Manual: „connect the pump to your motherboard's pump
**or CPU fan** header" — oba dozwolone.

### Ograniczenia

- **n = 1 na wariant.** Różne dni, różny ambient, różny kernel, świeży montaż i nowa pasta
  w przebiegach AIO. Powtarzalności między montażami ten test nie mierzy.
- **Faza idle nieporównywalna** między przebiegami (różne tło).
- **Głośność mierzona nieskalibrowanym mikrofonem telefonu**, bez pomiaru tła pomieszczenia.
  Nadaje się do porównania względnego, nie do podawania wartości bezwzględnych.
- **Różnica 0.7 K między A i C jest poniżej rozdzielczości tego testu** — nie twierdź na jej
  podstawie, że którekolwiek chłodzenie jest lepsze pod obciążeniem.

## Dług

`snap()` zapisuje `NA`, gdy `CPU_Opt` = 0. Intencja była słuszna (nie fałszować braku czujnika
zerem), ale **skutek był odwrotny od zamierzonego: zamaskował prawdziwe zero** i kosztował
jeden unieważniony przebieg. Poprawka: rozróżnić „kanał nieobecny w wyjściu `sensors`” (→ `NA`)
od „kanał obecny i raportuje 0” (→ `0`), i ostrzec w podsumowaniu, gdy pod obciążeniem
padnie zero.

## Kolejność dalszych testów

Pierwotny plan (`lc142-casemax`, `lc142-fan80`, `lc142-bal`) jest **zdezaktualizowany**:
przebieg C osiągnął parytet z wieżą, więc nie ma luki do zamykania. Zostaje tylko weryfikacja,
nie optymalizacja:

1. **Odczyt w BIOS-ie** — % PWM przy ~85 °C (zgodność z wymogiem ≥80 %) oraz rozstrzygnięcie,
   czy `CPU_Opt` to wentylatory, czy pompa.
2. **Tło pomieszczenia w dBA** — jeden odczyt tą samą apką z tego samego miejsca przy
   wyłączonej maszynie. Bez tego nie wiadomo, ile z 51–53 dBA to komputer, a ile pokój.
3. **Powtórka C za ~6 miesięcy** przy tej samej krzywej i obciążeniu — kontrola degradacji
   cieczy po incydencie z przebiegu B. Baseline: ΔT load 56.8 K.

## Provenance

- Przebieg A (`noctua`, 2026-07-31, ambient 24.5 °C, kernel 7.0.0-28): `noctua_20260731-2232.csv` + `stressng_noctua_20260731-2232.log` — bogo ops 62 261 310 / 2400 s
- Przebieg B (`lc142`, 2026-08-23 00:35, ambient 23.5 °C, kernel 7.0.0-29): `lc142_20260823-0035.csv` + `stressng_lc142_20260823-0035.log` — bogo ops 62 338 264 / 2400 s — **NIEWAŻNY**
- Przebieg C (`lc142-fanC`, 2026-08-23 08:33, ambient 24.0 °C, kernel 7.0.0-30): `lc142-fanC_20260823-0833.csv` + `stressng_lc142-fanC_20260823-0833.log` — bogo ops 62 230 800 / 2400 s
- Ambient i głośność przebiegu C: `.ambient_lc142-fanC`, `.noise_lc142-fanC`
- Poprzednia wersja raportu (z obalonym wnioskiem) — w historii gita, commit poprzedzający przebieg C
- Wykres porównawczy (PL/EN): `plot_cooling_polars.py` → `~/Pulpit/chlodzenie-cpu-AB/`
  — obróbka w Polars, trzy przebiegi, asercje na remis A↔C i na odstawanie B.
  Poprzednik `plot_cooling_ab.py` rysuje tylko 2 warianty i jest zachowany dla historii przebiegu A.
- Instrukcja NL-LC1 (cytaty o PWM wentylatorów i trybach pompy): `NOCTUA NL-LC1 Manual EN`, 2 s.
