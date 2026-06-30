---
name: reddit-news
description: Codzienny skan wybranych subredditów (AI, agenci, narzędzia, automatyzacja) — pobiera top posty z doby przez Apify (Reddit Scraper), filtruje po upvotes i kontekście (filtr.md), klasyfikuje, streszcza i generuje raport HTML w stylu AIBIZ Dark Impact + zadanie do przejrzenia. Trigger — "/reddit-news", "skan reddita", "newsy z reddita", "co nowego na reddicie", lub uruchomienie przez claude-cron rano.
argument-hint: "[run]"
---

# /reddit-news — codzienne newsy z Reddita

Pipeline: **fetch listingu → klasyfikacja po filtrze → streszczenie + sentyment → raport HTML → zadanie → commit dedup**.
Wszystkie ścieżki względem `Zasoby/Research/reddit-news/`. Skrypty w `scripts/` tego skilla.

## Konfiguracja (edytowalna przez usera, NIE w kodzie)
- `subreddity.txt` — lista subredditów (1 na linię)
- `filtr.md` — definicja ✅/❌ i punktacji — **przeczytaj go w całości przed klasyfikacją**

## Progi (domyślne, zmieniasz flagami)
upvotes ≥ 50 · okno 24h · bez limitu liczby (wszystko co przejdzie próg + filtr)

---

## Architektura — 2 joby (WAŻNE)

Fetch jest ODKLEJONY od części LLM, bo scrape Apify trwa ~26-29 min (RESIDENTIAL dławiony)
i headless `claude -p` przy błędzie scrape'u wpadał w debug → twardy timeout joba.
- **script-job `Reddit Fetch — scrape`** (cron `0 5`) — czysty node `fetch_subreddits.mjs`, zapisuje `raw/`. Długi timeout, zero LLM.
- **claude-job `Reddit Newsy`** (cron `45 5`, ten skill) — czyta GOTOWY `raw/`, klasyfikuje → raport → zadanie. Szybkie.

## Workflow `/reddit-news run`

### Krok 1 — WCZYTAJ raw (NIE scrapuj sam)
`raw/YYYY-MM-DD.json` robi wcześniej script-job `Reddit Fetch`. Sprawdź czy istnieje:
- **istnieje** → wczytaj `candidates` i przejdź do Kroku 2.
- **nie istnieje** (ręczne uruchomienie poza cronem) → odpal RAZ
  `node .claude/skills/reddit-news/scripts/fetch_subreddits.mjs` i poczekaj (do ~30 min).
- **`count: 0`** lub fetch zakończył się błędem → przejdź do Kroku 5 z pustym raportem.

⛔ **NIE debuguj Apify, NIE zmieniaj proxy, NIE odpalaj actora ręcznie przez curl.**
Brak danych = pusty raport, nie śledztwo. Scrape to sprawa script-joba, nie twoja.

### Krok 2 — KLASYFIKACJA (Ty, model)
1. Przeczytaj `Zasoby/Research/reddit-news/filtr.md` (cała definicja ✅/🟡/❌).
2. Przeczytaj `raw/YYYY-MM-DD.json` (pole `candidates`).
3. Dla KAŻDEGO kandydata oceń na podstawie `title` + `body_preview`:
   - `keep` (bool) — `false` dla wszystkiego z sekcji ❌ (ceny/limity tokenów,
     narzekanie na jakość modeli, doom o końcu programowania, memy, "jak zacząć")
   - `tag` — krótka kategoria po polsku/angielsku (np. `AI-tooling`, `agenci`,
     `premiera-modelu`, `automatyzacja`, `case-study`, `MCP`)
   - `score` 1-10 wg skali z `filtr.md`

### Krok 3 — STRESZCZENIE (Ty, model)
Dla newsów z `keep = true`:
- `summary` — 3-4 zdania po polsku, konkret: co to, dla kogo, czemu warte uwagi,
  ewentualnie jak wykorzystać w pracy/contencie.

### Krok 4 — ZAPIS data.json (Ty, model)
Zapisz `Zasoby/Research/reddit-news/data/YYYY-MM-DD.json`:
```json
{
  "date": "YYYY-MM-DD",
  "stats": { "fetched": <count z raw>, "kept": <ile keep=true> },
  "news": [
    { "post_id","title","url","subreddit","author","upvotes","comments",
      "created_at","link_url","tag","score","summary" }
  ]
}
```
Do `news[]` trafiają **tylko `keep = true`**. `link_url` przepisz z raw (puste dla text-postów).

### Krok 5 — RAPORT HTML (mechaniczny)
```bash
node .claude/skills/reddit-news/scripts/generate-raport.mjs
```
Pisze `Raporty/raport-aktualny.html` + `Raporty/YYYY-MM-DD.html` (sort po score, AIBIZ Dark Impact).

### Krok 6 — ZADANIE
Utwórz zadanie „Przejrzyj newsy Reddit DD.MM" przez `/utworz-zadanie`:
- priorytet 🟢 normalne, termin = dziś, projekt pusty
- w Notatkach (H4) wklej ścieżkę do raportu: `Zasoby/Research/reddit-news/Raporty/raport-aktualny.html` + liczbę newsów
Jeśli zadanie z dziś już istnieje — zaktualizuj liczbę zamiast tworzyć duplikat.

### Krok 7 — COMMIT DEDUP (mechaniczny, na końcu)
```bash
node .claude/skills/reddit-news/scripts/fetch_subreddits.mjs --commit Zasoby/Research/reddit-news/raw/YYYY-MM-DD.json
```
Dopisuje WSZYSTKICH kandydatów (po raw, czyli tych co przeszli próg 50⬆️) do `_seen.json`
z dzisiejszą datą i przycina wpisy starsze niż 30 dni. **Rób to dopiero po raporcie** —
crash wcześniej oznacza że te posty wrócą jutro (idempotentne, lepsze niż zgubienie).
Posty < 50⬆️ świadomie NIE trafiają do seen — mogą urosnąć i wejść jutro.

---

## Uwagi
- Cron: script-job `Reddit Fetch` `0 5 * * *` (node fetch, timeout 40 min) → claude-job `Reddit Newsy` `45 5 * * *` `claude -p "/reddit-news run"`.
- Dane z **Apify** (`trudax/reddit-scraper-lite`) — oficjalne API Reddit padło (zmiana
  polityki 06.2026). Wymaga `APIFY_API_KEY` w `.env`. Koszt pay-per-event: grosze/dzień.
- Dedup po `post_id`. Próg upvotes / okno / liczbę postów per sub zmienisz flagami
  `--min-upvotes` / `--hours` / `--max-per-sub`.
- Pułapka aktora: pole `communityName` ma prefiks `r/` (kod normalizuje na `parsedCommunityName`).
