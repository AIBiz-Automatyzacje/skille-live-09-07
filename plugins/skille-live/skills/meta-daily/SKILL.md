---
name: meta-daily
description: Dzienny raport Meta Ads z analizą per kreacja. Pobiera aktywne kampanie (podział sprzedaż/lead), schodzi do poziomu pojedynczego assetu (grafika/wideo/copy), liczy metryki w oknach czasowych (dziś/wczoraj/3 dni/tydzień/miesiąc) z porównaniem, sprawdza historię edycji (czystość porównań), analizuje wizualnie kreacje (grafiki przez vision, wideo przez Gemini, z cache) i generuje raport HTML z oceną i sugestiami. Trigger — "raport meta", "dzienny meta", "/meta-daily", "jak idą kampanie meta", "analiza kreacji meta", lub uruchomienie przez claude-cron.
allowed-tools: Bash(python3 *), Read, Write, Skill
---

# Meta Daily — dzienny raport Meta Ads per kreacja

Pełna maszyna analizy aktywnych kampanii: metryki kampanii + per asset, trend w oknach, historia edycji, analiza wizualna kreacji, ocena i sugestie. Raport HTML w stylu AIBIZ Dark Impact.

> Spec i ustalenia: `Zadania/projekty/meta-ads/dzienny-raport-specyfikacja.md` + `flow-skilla.md`.
> Kontekst konta i metodologia klasyfikacji: `_KONTEKST.md` + `proces-klasyfikacji-kampanii.md`.

## Wymagania (env w root `.env`)
- `ACCESS_TOKEN` + `AD_ACCOUNT_ID` — Meta Marketing API (token wygasa ~11.07.2026, odnawiać).
- `GOOGLE_API_KEY` — Gemini (analiza wideo).
- `MAILER_API` — MailerLite (snapshot łącznych zapisów na live do pacingu; brak = pacing pomijany, pipeline działa dalej).
- Interpreter: systemowy `python3` (lokalnie i na VPS ma requests, dotenv, markdown-it, google-genai). Ścieżki wykrywane względem położenia skryptu — działa na Macu i na VPS (`/home/claude/vault`).

## Pliki kontekstowe (katalog projektu `Zadania/projekty/meta-ads/`)
- **`_plan-marcina.md`** — świadome decyzje i zamiary Marcina (budżety, struktura, cele). REASON MUSI go respektować: nie wolno rekomendować cofnięcia decyzji z planu ani „odkrywać" ich jako problemów. **Aktualizować po każdym zarządzie** — nieaktualny plan = raport doradza bzdury.
- **`playbook-meta.md`** — metodyka ocen: destylat bazy Loomera 2026 (`Zasoby/Research/jonloomer-meta-ads-2026/`, pełna ekstrakcja w `loomer-wnioski-2026-07-03.md`). REASON opiera rekomendacje na TYCH regułach, nie na ogólnej wiedzy modelu. Odświeżać po dosypaniu nowych materiałów do bazy (ponowna ekstrakcja → aktualizacja playbooka).
- **`live-config.json`** — bieżący live: grupa, data, ID grupy MailerLite, cel zapisów. Po ogłoszeniu nowego live'a zaktualizować.
- **`benchmarki-livow.json`** — ekonomia poprzednich live'ów (zapisy → zakupy po kodzie → przychód/zapis). Odświeżać po każdym live (baza EasyCart na VPS Coolify + MailerLite).

## Pipeline (uruchamiaj po kolei)

Katalog skryptów: `.claude/skills/meta-daily/scripts/`. Komendy odpalaj z tego katalogu.

### 1. PULL + STORE — `python3 run.py`
Pobiera aktywne kampanie, klasyfikuje sprzedaż/lead (po faktycznych zdarzeniach, nie `objective`), reklamy **wszystkich statusów** (stare/spauzowane trzymają historię ROAS), mapę zestawów/reklam i historię edycji. Zapis idempotentny do `meta-ads.db`. Inkrementalny pull edycji.

**🎯 Grupy live (aktywne + wstrzymane jednego live'a):** pull bierze wszystkie ACTIVE **oraz** wstrzymane kampanie należące do grupy live, która ma aktywną kampanię. Grupa wykrywana z nazwy (`meta_common.live_group`, wzorzec „live <dzień> <miesiąc>", np. „live 9 lipca") i zapisana w kolumnie `campaigns.live_group`. Po co: jeden live ma często kilka kampanii (główna + forma + test), część bywa wstrzymana, a ich leady to realne zapisy — bez tego raport gubił 100+ leadów. **Archiwum** (wstrzymane grupy bez aktywnej kampanii — stare live'y z tysiącami leadów) jest pomijane, żeby nie zaśmiecać sum. Nazwy nietypowe (np. „Własne grupy (pod live w 21 maja)") → `live_group=NULL`; w razie potrzeby dotaguj ręcznie w bazie — pull tego nie nadpisze (`COALESCE`).

**⚠️ Atrybucja konwersji (kluczowe — patrz `handoff-2026-06-26.md`):** `time_increment=1` rozbija okno atrybucji Meta na dni i NIEDOSZACOWUJE leady/zakupy/przychód (KursCC: 47 vs realne ~90). Dlatego store rozdziela trzy źródła:
- **`assets`** — lifetime per kreacja (image/video/body/title), `time_range` BEZ `time_increment` = dokładne totale jak Ads Manager. Plus okres emisji (`first_day`/`last_day`/`active_days`) z osobnego lekkiego zapytania o same impresje.
- **`campaign_windows`** — 7 okien (dziś/wczoraj/3d/tydzień/miesiąc + this/prev_week) liczonych osobnym `time_range` BEZ `time_increment` względem ostatniego aktywnego dnia kampanii. Granice dat zapisane w wierszu = źródło prawdy (compute ich nie przelicza).
- **`campaign_daily`** — dzienny trend z sumy reklam (`time_increment=1`), WYŁĄCZNIE do `days_inactive` + trend spend/CTR + wykres leadów (leady mają atrybucję natychmiastową, więc dzienny rozkład jest tu wiarygodny). CTR zawsze ważony `SUM(clicks)/SUM(impr)`, nigdy `AVG`.

### 2. ENRICH grafiki (krok LLM — vision) — `python3 enrich.py prepare`
Zwraca manifest JSON grafik z sensowną emisją (>3000 wyśw.) bez analizy (z `image_path` lokalnego obrazu i kontekstem copy — **celowo bez metryk**). **Dla każdej pozycji:**
- Otwórz `image_path` narzędziem Read (vision) i obejrzyj grafikę.
- Napisz zwięzły opis (2-3 zdania): CO WIDAĆ — hook, układ, twarz/ikony, plakietki, styl, czytelność przekazu.
- **⛔ TWARDA REGUŁA: ZERO liczb i metryk w analizie.** Żadnych CTR/CPL/wyświetleń/zakupów, żadnych „najwyższy CTR w zestawie". Analiza trafia do cache raz na życie assetu — liczby w niej ZAMARZAJĄ i po tygodniu kłamią obok świeżych kafelków (bug z 02.07: cache „CTR 3,88%" obok kafelka 1,81%). Interpretację metryk robi codziennie krok REASON na świeżych danych.
- Zbierz wszystkie do pliku `{asset_key: "analiza"}` i zapisz: Write do `scratchpad/visual.json`, potem `python3 enrich.py save <ścieżka>/visual.json`.

Cache: assety z gotową analizą są pomijane (analiza raz na życie assetu). Drugi przebieg = `prepare` zwróci tylko nowe kreacje. Kreacje z próbą <3000 wyśw. nie są analizowane — w raporcie lądują jako zwinięta linijka faktów.

### 3. ENRICH wideo (Gemini, automatyczny) — `python3 enrich.py videos`
Pobiera plik wideo z Meta i analizuje przez Gemini (reuse `video-analyze`). Zapis do cache. Wideo bez `source` w API pomijane.

### 4. REASON — ocena i sugestie (krok LLM) — `python3 reason_input.py`
Zwraca JSON: `plan_marcina` (świadome decyzje), **`playbook`** (metodyka z bazy Loomera 2026), `live_context` (pacing + ekonomia leada), a per kampania: metryki w oknach (z **frequency, reach i lejkiem** link_click→LPV→lead), tydzień-do-tygodnia, edycje, **ad sety z targetingiem i wykluczeniami**, analizy wizualne assetów, copy wg CTR. **Przeczytaj i dla każdej kampanii napisz ocenę (analiza → ocena → sugestia):**
- **⛔ Respektuj `plan_marcina`** — to świadome decyzje. Nie wolno rekomendować ich cofnięcia ani zgłaszać jako problem (np. „przywróć budżet", który Marcin celowo zmniejszył). Wolno się do nich odnieść z liczbami („redukcja LP działa — CPL stabilny") albo zakwestionować wprost z dowodem, oznaczając że to polemika z planem.
- **📖 Rekomendacje opieraj na `playbook`** — to destylat metodyki praktyka (Loomer 2026), zastępuje Twoje ogólne defaulty. Kluczowe reguły, których MUSISZ przestrzegać: (1) diagnostyka spadków w KOLEJNOŚCI z playbooka (losowość → edycje → wyczerpanie engaged → placementy → aukcja/CPM → strona → dopiero zmęczenie kreacji); (2) „wygaś kreację" tylko przy trendzie wielodniowym + agregacie ad setu ponad celem LUB twardym błędzie przekazu — nie po jednym drogim dniu; (3) targeting płeć/górny wiek/LAL przy Advantage+ to SUGESTIE — wnioski o dotarciu buduj na breakdownach, nie na ustawieniach; naprawy przez Value Rules, nie restrykcje; (4) raportowane leady przy 7-day click to górna granica (repeat conversions, any-click) — dopóki atrybucja nie zejdzie na 1-day click, mów o tym przy porównaniach; (5) pojedynczy skok spendu do +75% dnia = normalne wyrównywanie tygodniowe. Gdy reguła playbooka kłóci się z planem Marcina (np. skoki budżetu vs „kroki +20-30%") — obowiązuje plan, ale odnotuj konflikt w ocenie.
- **Stosuj reguły skalowania z planu:** 5+ konwersji i stabilny koszt 3–5 dni zanim „skaluj"; kroki +20–30%; bez wystarczającej próby → „obserwuj". Każda rekomendacja z uzasadnieniem liczbowym.
- **Bez progów** — czytaj wszystkie metryki razem (CTR, koszt konwersji, ROAS, trend, edycje), nie alarmuj od sztywnego % zmiany.
- **Frequency = sygnał zmęczenia** (uwaga od ~2,5, historycznie problem od 3,0) — ale wg playbooka NAJPIERW wyklucz wyczerpanie puli engaged i drożejącą aukcję (CPM), zanim zdiagnozujesz zmęczenie kreacji.
- **Lejek:** link_clicks → LPV → lead. Duży ubytek klik→LPV = wolny landing/zły ruch; niska konwersja LPV→lead = landing lub oferta (dotyczy kampanii z ruchem na LP, nie formy błyskawicznej — rozróżnij po adsetach/optymalizacji).
- Uwzględnij historię edycji (czy spadek wyniku to skutek zmiany, nie skuteczności) i flagę bezczynności.
- **JĘZYK — pełne, proste zdania, jak do wspólnika (feedback Marcina 02.07).** Zakaz skrótów analityka: nie „tempo realizacji 108/dzień wobec 62", tylko „żeby dobić do 2000 zapisów, potrzebujemy 108 zapisów dziennie; wczoraj było 62". Każde stwierdzenie = liczba + co z niej wynika + co zrobić. Bez metafor („koń pociągowy", „w plecy"), bez żargonu. Treść może być w markdown (pogrubienia, listy) — raport je renderuje.
- **Werdykty per kreacja — klucz `_assets`** = `{asset_key: "werdykt"}` dla KAŻDEJ kreacji z sensowną próbą (te z listy `assets` we wsadzie; asset_key jest w danych). Werdykt renderuje się w małym boksie siatki — **MAKSYMALNIE 2 zdania: ocena + akcja.** ⛔ NIE opisuj co widać na grafice/wideo — Marcin ma oczy; opis wizualny ze wsadu to Twój kontekst, nie treść. Werdykt = dzisiejsze liczby + wzorce konta (twarz > brak twarzy, konkretny ból > abstrakcyjny benefit, kontrast STARY/NOWY) + JASNA AKCJA: skaluj / zostaw / wygaś / wymień hook / do nowej struktury. Przy wideo: co zmienić w następnym (hook, pierwsze kadry, format), nie streszczenie fabuły.
- **Lejek per kampania:** wsad ma pole `funnel` (`form` = formularz błyskawiczny, `lp` = landing page). ⛔ Nie porównuj CPL między lejkami 1:1 — to inne wyjście z reklamy i inna jakość leada (formularz = tańszy zapis, historycznie słabsza obecność na live). Oceniaj kampanię w ramach jej lejka; różnice między lejkami komentuj jako różnicę MODELU, nie skuteczności.
- **Tablica akcji — klucz `_actions`** = PŁASKA lista obiektów `{"typ": "zmien|usun|popraw|obserwuj", "kampania_id": "<id>"|null, "tekst": "..."}`. To odpowiedź na pytanie „co mam DZIŚ zrobić": `zmien` = ruchy budżetowe/strukturalne, `usun` = wygaszenia, `popraw` = rzeczy do naprawy, `obserwuj` = co śledzić z progiem decyzyjnym. `kampania_id` = kampania, której akcja dotyczy (null = konto/ogólne) — raport pokazuje wszystkie w Przeglądzie i filtruje per kampania w widoku Kampanie. Każda pozycja: 1 zdanie z liczbą, samodzielna i wykonalna w Ads Managerze.
- Zapisz jako `{campaign_id: "ocena", ..., "_assets": {...}, "_actions": [...], "_summary": "..."}` do `Zadania/projekty/meta-ads/reason.json`. `_summary` krótkie (2 akapity): pacing/prognoza + najważniejszy wniosek dnia — szczegółowe ruchy żyją w `_actions`, nie duplikuj ich w podsumowaniu.
- **Dodatkowo klucz `_summary`** = podsumowanie dnia (panel „🧠 Ocena eksperta" na górze raportu). To pierwsza rzecz, którą czyta Marcin — ma odpowiadać na pytania, których panel Meta nie zada:
  1. **Czy dowozimy cel?** (pacing z `live_context`: zapisy łączne vs cel, tempo vs wymagane)
  2. **Czy koszt się opłaca?** (CPL vs **wartość NOWEGO zapisu** z benchmarków — ⛔ NIGDY przychód z kodu ÷ wszyscy zapisani: kupuje głównie baza, to zawyża wartość leada z reklam; korekta Kacpra 02.07)
  3. **Trzy ruchy na dziś** — konkretne akcje (budżet/kreacje) wg reguł skalowania, każda z liczbą.
  Bez lania wody: 2-3 akapity + lista. Nie powtarzaj metryk, które widać w kafelkach — interpretuj je.

> ⚠️ Polskie cudzysłowy w `reason.json`: jeśli zapisujesz przez skrypt Pythona, NIE używaj ASCII `"` jako zamykającego w `„…”` — zamknie literal. Najbezpieczniej zapisać plik skryptem `.py` (UTF-8), nie heredokiem przez stdin.

### 4.5. REVIEW — redakcja copy (subagent, Sonnet)
Po zapisaniu `reason.json` odpal **osobny przebieg redaktorski** — świeże oczy czyszczą tekst, którego autor REASON mógł nie wyłapać (tu wcześniej przeszło koślawe „koń z twarzą"). Spawnuj subagenta narzędziem **Agent** z `model: sonnet` (taniej niż Opus, do redakcji wystarcza) i zadaniem:
- Wczytaj `Zadania/projekty/meta-ads/reason.json` (wszystkie klucze: `_summary` + oceny per kampania + werdykty w `_assets`).
- **Popraw i uprość polski:** krótsze zdania, zero żargonu i anglicyzmów (zostaw tylko nazwy własne i akronimy: CTR, ROAS, CPL, CPA, Ads Manager), wytnij niezręczne metafory i potworki słowne (np. nie skracaj „koń pociągowy / filar konta z twarzą Kacpra" do form brzmiących jak opis zwierzęcia). Stosuj zasady z `rules/content/ai-writing-patterns.md` (długie myślniki, filler, hedging).
- **TWARDA reguła: nie ruszaj żadnych liczb, nazw kreacji, kampanii ani rekomendacji** — wyłącznie warstwa językowa. Zachowaj markdown (pogrubienia, listy) i strukturę `_summary` (synteza + „Trzy ruchy na dziś").
- Nadpisz `reason.json` poprawioną wersją (ten sam format `{campaign_id: "...", "_summary": "..."}`, UTF-8, uwaga na polskie cudzysłowy `„…”` — patrz ostrzeżenie przy REASON).

### 5. RENDER — `python3 report.py`
Składa **interaktywny HTML v2.0** (układ zatwierdzony przez Kacpra w Figmie 03.07) do `Zadania/projekty/meta-ads/raporty/YYYY-MM-DD.html`. Zwróć użytkownikowi ścieżkę. Dwa widoki (czysty JS w pliku, zero zależności), zasada wizualna: jedna neutralna powierzchnia, kolor tylko dla statusu:
- **Widok Przegląd (domyślny):** rząd KPI (zapisy z paskiem postępu do celu · tempo śr. 3 dni vs wymagane · prognoza na dzień live · koszt zapisu 7 dni vs granica 25 zł) → karta „Ocena dnia" (`_summary` + stopka źródeł: rekonsyliacja Meta↔lista, MailerLite) → karta „Akcje na dziś" (wszystkie `_actions` z chipem typu i nazwą kampanii).
- **Widok Kampanie:** selektor `<select>` (aktywne najpierw, wg wydatku 7d) → per kampania: chipy statusu (AKTYWNA/WSTRZYMANA, LEJEK, freq 7d z ostrzeżeniem ≥2,5, stoi N dni) → KPI kampanii (koszt zapisu wczoraj/7d/30d lub ROAS dla sprzedażowych, CPM 7d + CPC, budżet dziś z ostatnią zmianą) → „Akcje dla tej kampanii" (filtrowane po `kampania_id`) → „Ocena" → **sekcje zwijane `<details>`**: Kreacje (siatka 3 kolumny: miniatura + metryki + werdykt z `_assets`; boks tylko dla aktywnych ≥3000 wyśw. z emisją w ostatnich 5 dniach, reszta jedną linijką; zwinięty nagłówek pokazuje liczbę + najlepszą/najsłabszą) · Historia zmian · Teksty reklam (wg kosztu zapisu) · Zapisy dziennie (wykres).
- **⛔ NIE renderujemy:** panelu „wartość nowego zapisu" (insight jednorazowy — decyzja Kacpra 03.07; benchmarki zostają w wsadzie REASON jako wiedza), kolorowych paneli tła, opisów wizualnych z cache.

### Benchmark historyczny — `python3 benchmark_livow.py` (raz po każdym live, NIE codziennie)
Zaciąga z Meta krzywe kumulacji zapisów z reklam poprzednich live'ów (dzień po dniu do daty live) i dopisuje je do `benchmarki-livow.json` — pacing porównuje „gdzie jesteśmy vs gdzie były poprzednie live'y na X dni przed". Po każdym live: dopisz nowy live do `livy` (zapisani/nowi/zakupy z analizy atrybucji + EasyCart) i odpal skrypt.

### 6. ZADANIE — utwórz przez `/utworz-zadanie`
Po wygenerowaniu raportu utwórz zadanie przypominające o wysyłce. Wywołaj skill `/utworz-zadanie` (NIGDY ręcznie — to twarda reguła systemu zadań) z:
- **Tytuł:** `Wyślij raport do Marcina` (Meta Ads, data raportu)
- **Termin:** dziś
- **Priorytet:** normalne (🟢)
- W treści zadania wklej ścieżkę do dzisiejszego raportu HTML (z kroku 5).

## Tryb headless (claude-cron)
Cały pipeline w jednej sesji: kroki 1, 3, 5 to czyste komendy; kroki 2 i 4 wymagają Claude (vision + ocena) — w `claude -p` model wykona je w tej samej sesji. Krok 4.5 (REVIEW) spawnuje subagenta Sonnet narzędziem Agent — działa też w `claude -p`. Kolejność bez zmian.

## Do zrobienia (kolejne iteracje)
- **Wysyłka na Discord** (po akceptacji raportu — na razie raport zostaje jako HTML w `raporty/`).
- Feedback Marcina nanosić na układ/treść raportu na bieżąco.
