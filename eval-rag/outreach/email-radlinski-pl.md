# Draft emaila — Jakub Radliński (IGiChP Rabka-Zdrój)

**Status:** DRAFT do Twojego review przed wysyłką. Mniej formalny niż do Białasa (dr n. tech., równy poziom afiliacji UMB/IGiChP), mniejszy ask (expert reviewer subset, nie co-author całości).

**Sugerowany temat:** `Prośba o ekspercką recenzję subsetu pytań do ewaluacji LLM — moduł badań czynnościowych`

**Sugerowane CC:** brak

**Sugerowane załączniki:** brak

---

## Treść

Szanowny Panie Doktorze,

Piszę z konkretną prośbą o pomoc ekspercką w wąskim zakresie. Krótko o kontekście.

**Kontekst.** W zespole UMB prowadzę projekt benchmarków lokalnego inference dużych modeli językowych (`navimed-umb`). Przy okazji ostatniego release (kwantyzacja AWQ całej rodziny Llama-PLLuM-70B udostępniona publicznie 23 maja na Hugging Face) otwiera mi się oddzielne pytanie — czy te modele rzeczywiście odpowiadają merytorycznie poprawnie na polskie pytania kliniczne, jeżeli dostają fragment ChPL jako kontekst. Pełen design ewaluacji opisany jest w repozytorium projektu (https://github.com/kicrazom/navimed-umb, podkatalog `eval-rag/`).

Główną oś klinicznej oceny prowadzić będzie zespół farmakoterapeutyczny (prof. Adam Białas z UM Łódź zaproszony jako co-autor, jeszcze przed decyzją). Ale moja siatka 50 pytań planowo obejmuje 5–7 pozycji ściśle związanych z **monitorowaniem czynności płuc** i **standardami badań** — kwalifikacją do programów lekowych po spirometrii i dyfuzji DLCO, kryteriami odpowiedzi w astmie ciężkiej, parametrami safety wymagającymi PSG, itd. To są pytania, których jakości oceny *nie powinien* prowadzić nikt poza ekspertem od metodologii badań czynnościowych — a Pana dorobek w tej dziedzinie (wytyczne PTChP spirometrii w pandemii COVID-19, zalecenia dot. OBS u kierowców, oceny jakości spirometrii) jest naturalnym punktem odniesienia.

**Propozycja.** Chciałbym zaprosić Pana do roli **expert reviewer** dla podzbioru 10–15 pytań i odpowiednio 50–75 odpowiedzi modeli (te pytania × 5 modeli pod ewaluacją). Ocena standardową siatką 5-punktową w 4 wymiarach (faithfulness, kompletność, bezpieczeństwo kliniczne, naturalność polskiego stylu medycznego). Zakładam ~30–45 min pracy, asynchronicznie w terminie 2 tygodni od dostarczenia materiału. Autorstwo zgodne z ICMJE — w pozycji odpowiadającej wkładowi (najpewniej z formułą "expert reviewer for pulmonary function questions" w sekcji Author Contributions).

Pytanie jest otwarte — jeżeli zechce Pan zaangażować się szerzej w projekt zestawu pytań od strony metodologii badań czynnościowych, też mi to bardzo odpowiada; rola expert reviewer to minimum, nie pułap.

**Czego nie proszę.** Nie proszę o dane pacjentów, dostęp do żadnej infrastruktury, ani o czas teraz. Generacja odpowiedzi modeli zacznie się dopiero po sfinalizowaniu zestawu pytań — najwcześniej za 2–3 tygodnie. Materiał do oceny dostanie Pan w formie prostej (tabela / CSV / wybrana wygodna), z jasnymi instrukcjami.

Będę wdzięczny za odpowiedź — także "nie mam teraz czasu", jeżeli tak wypada; ułatwi to planowanie zespołu.

Z wyrazami szacunku,
dr n. med. Łukasz Minarowski
Zakład Fizjopatologii Oddychania
Uniwersytet Medyczny w Białymstoku
ORCID: 0000-0002-2536-3508
e-mail: lukasz.minarowski@umb.edu.pl

---

## Notatki do review (Łukasz, do usunięcia przed wysłaniem)

- **Ton**: Bardziej direct niż do Białasa, bo mniejszy ask + Radliński nie jest "Profesorem" (dr n. tech., kierownik pracowni). "Panie Doktorze" jest właściwe.
- **Wzmianka o Białasie**: zostawiłem "jeszcze przed decyzją" — to uczciwe wobec Radlińskiego (nie chcę sugerować, że Białas już zgodził się), a jednocześnie pokazuje że zespół docelowy ma poziom. Możesz usunąć jeśli wolisz nie ujawniać partnerów do akceptacji.
- **Konkrety pytań**: wymieniłem trzy obszary, gdzie jego ekspertyza jest niezastąpiona (spirometria→programy lekowe, kryteria astmy ciężkiej, PSG-relevant safety). Każdy z nich jest realnie w korpusie SmPC (np. omalizumab/mepolizumab/dupilumab wymagają spirometrycznych kryteriów eligibility).
- **Authorship**: ICMJE z "expert reviewer for pulmonary function questions" — w PL akademii to standardowa formuła dla limited-contribution authorship, akceptowalna w Acta Pneumonol et Allergol czy Adv Respir Med.
- **Długość**: ~370 słów, świadomie krótsze niż do Białasa (mniejszy ask = krótsze emaile).
- **Możliwy follow-up**: jeśli odpowie "tak ale dopiero we wrześniu", przesuwamy ewaluację, nie jest to deal-breaker — Białas jest critical path, Radliński nice-to-have z mocnym uzasadnieniem.
