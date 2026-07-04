---
name: lead-fb-radar
description: Radar zleceń z publicznych grup Facebook. Scrapuje świeże posty z wybranych grup przez Apify (bez cookies), kwalifikuje każdy pod kątem zapytań o usługi automatyzacji/no-code i zapisuje trafienia jako notatki-leady w Obsidianie (baza Obsidian Bases). Używaj gdy user mówi "sprawdź leady z grup", "poszukaj zleceń na Facebooku", "radar leadów FB", "/lead-fb-radar", "co nowego w grupach", albo gdy skill odpala Puls (cron godzinowy). Przepięcie scenariusza n8n "Pozyskiwanie leadów z grup Facebook'owych" na skill.
allowed-tools: Bash(node *), Read, Write, Glob
---

# Lead FB Radar — zlecenia z grup Facebook

Monitoruje publiczne grupy FB, wyłapuje posty w stylu „szukam kogoś od automatyzacji /
integracji / bota" i podsuwa je jako gotowe leady. Kwalifikację robi asystent natywnie —
zero zewnętrznego API do LLM, zero kosztu tokenów poza tą sesją. To jest przewaga skilla nad
scenariuszem n8n, gdzie kwalifikował osobny model (Claude Haiku + fallback Gemini).

> Wymaga `APIFY_API_KEY` w root `.env`. Koszt: aktor `memo23/facebook-public-group-posts-scraper`
> ~$1,5/1000 postów (residential proxy). Tylko grupy publiczne (bez cookies).

## Pliki i lokalizacje

- **Lista grup:** `config/grupy.md` (linie z URL grup publicznych).
- **Baza leadów:** `Zasoby/Leady-FB/` w vaulcie — jedna notatka `.md` = jeden lead + widok `Leady-FB.base`.
- **Stan:** `Zasoby/Leady-FB/_seen.json` (URL-e już przetworzonych postów — dedup) i
  `_nowe-posty.json` (manifest świeżych postów do kwalifikacji, kasowany między runami).

Jednorazowy setup bazy: jeśli `Zasoby/Leady-FB/Leady-FB.base` nie istnieje, skopiuj tam
`assets/Leady-FB.base` ze skilla (daje widok tabeli w Obsidianie).

## Pipeline

### 1. Pobierz świeże posty — `node scripts/fetch.mjs --hours 26`
Scrapuje grupy z `config/grupy.md` (posty z ostatnich N godzin, **wraz z top komentarzami**),
odsiewa te już widziane (`_seen.json`) i zapisuje **nowe** do `Zasoby/Leady-FB/_nowe-posty.json`.
Skill chodzi raz na dobę, więc okno = `--hours 26` (24 h + 2 h zakładki na styku dób; dedup po URL
i tak usunie ewentualne duplikaty, więc zakładka jest darmowa, a nie gubi postów z granicy okna).

Jeśli manifest jest pusty — koniec, nie ma czego kwalifikować.

### 2. Zakwalifikuj każdy post (TY, natywnie)
Wczytaj `_nowe-posty.json` (Read). Każdy post ma `tekst` oraz `komentarze` (top komentarze pod
postem). Dla **każdego** postu oceń wg reguł niżej i przypisz `result` = `lead` / `odrzut`,
`snippet` (2 zdania: potrzeba + pożądany rezultat), a dla leadów dodatkowo z komentarzy:
- `konkurencja` — ile osób w komentarzach już oferuje wykonanie („zapraszam na priv", „robię
  takie rzeczy", „pisz do mnie"). 0 = gorący lead (zgłoś się pierwszy).
- `nastroje` — jedno zdanie: o czym piszą w komentarzach (podpowiedzi, sceptycyzm, gotowe
  rozwiązania). To amunicja do pierwszej wiadomości i sygnał, czy warto walczyć.

**Kwalifikuj jako `lead`, gdy post zawiera:**
- zapytanie o automatyzację procesów biznesowych,
- potrzebę integracji systemów / aplikacji,
- chęć zbudowania bota / agenta AI,
- prośbę o usprawnienie przepływu pracy,
- potrzebę połączenia różnych narzędzi / platform,
- automatyczne przetwarzanie danych,
- rozwiązanie no-code / low-code (Make, n8n, Zapier itp.).

**Odrzuć (`odrzut`), gdy post to:**
- ogólne pytanie techniczne bez kontekstu biznesowego,
- pytanie o programowanie / kodowanie samo w sobie,
- post promocyjny / sprzedażowy (ktoś oferuje, nie szuka),
- pytanie o narzędzie bez kontekstu automatyzacji,
- dyskusja teoretyczna,
- rekrutacja programistów,
- problem techniczny z urządzeniem.

Sedno rozróżnienia: **lead = ktoś opisuje POTRZEBĘ, którą można zaspokoić usługą automatyzacji.**
Ktoś, kto sam oferuje usługi albo tylko dyskutuje — to nie lead. Bądź selektywny: lepiej
oddać czysty strumień 3 realnych leadów niż 20 „może". Zawartość grup bywa myląca — np. w grupie
Akademii Automatyzacji większość to praktycy dzielący się wiedzą, nie zleceniodawcy; nie łap ich.

### 3. Zapisz leady jako notatki
Dla **każdego postu z `result: lead`** utwórz notatkę w `Zasoby/Leady-FB/` o nazwie
`YYYY-MM-DD-<krótki-slug>.md` (slug z 3-4 słów tematu, małe litery, myślniki). Szablon frontmatteru
— patrz `assets/lead-template.md`. Posty `odrzut` NIE tworzą notatek (baza zostaje czysta), ale
ich URL-e i tak trafią do `_seen` w kroku 4, żeby nie wracały do kwalifikacji.

Frontmatter każdej notatki:
```yaml
---
grupa: "<groupTitle z postu>"
url: <url postu>
autor: "<autor>"
data: <data postu, YYYY-MM-DD jeśli znana>
status: nowy          # nowy → kontakt → odrzucony (zmieniasz Ty, ręcznie w Obsidianie)
result: lead
konkurencja: <liczba osób oferujących w komentarzach; 0 jeśli brak>
nastroje: "<jedno zdanie o komentarzach>"
snippet: "<2 zdania: potrzeba + pożądany rezultat>"
---
```
W treści notatki wklej pełny `tekst` postu, a pod nim najważniejsze komentarze (do wglądu przy
pisaniu wiadomości). Szablon: `assets/lead-template.md`.

### 4. Zamknij run — `node scripts/fetch.mjs --commit`
Dopisuje URL-e WSZYSTKICH postów z manifestu (leady i odrzuty) do `_seen.json`, żeby przy kolejnym
runie nie kwalifikować ich ponownie. Rób to DOPIERO po kroku 3 — inaczej przy przerwaniu stracisz
posty bez zapisanych leadów.

### 5. Wygeneruj raport — `node scripts/report.mjs`
Składa przeglądarkowy raport HTML z dzisiejszych leadów (styl AIBIZ Dark) do
`Zasoby/Leady-FB/raporty/YYYY-MM-DD.html`: karty leadów ze snippetem, statusem, licznikiem
konkurencji (🥊) i linkiem do postu. Zwróć użytkownikowi ścieżkę. To jest „raporcik do przejrzenia"
nowych leadów; trwała baza ze wszystkimi leadami i statusami żyje w `Leady-FB.base` (Obsidian).

### 6. Podsumuj
Zwróć zwięźle: ile nowych postów, ile leadów, ile bez konkurencji, ścieżkę raportu. Jeśli user
chce alert na Discord — ma webhook; napisz „🎯 N nowych leadów z grup FB" z listą. (Opcjonalne.)

## Uruchomienie w Pulsie (cron)
Job **dobowy** (raz na dobę) typu claude-job z promptem: „Uruchom skill lead-fb-radar". Skill sam
zrobi fetch (`--hours 26`) → kwalifikacja → zapis leadów → commit → raport HTML. Raz na dobę bo
grupy nie zapełniają się tak szybko, żeby skanować częściej, a dobowe okno łapie komplet.

## Pułapki
- **Tylko grupy publiczne.** Aktor bez cookies nie wejdzie do prywatnych — dla nich trzeba by innego
  aktora z cookies (i fejkowego konta FB), czego tu świadomie unikamy.
- **Apify residential proxy bywa wolne** — timeout w skrypcie to 30 min, z zapasem dla 2 grup.
- **Nie commituj przed zapisaniem leadów** (patrz krok 4) — kolejność ma znaczenie.
- **Kwalifikacja to Twój osąd, nie regex** — reguły są ramą, nie sztywną listą słów kluczowych.
