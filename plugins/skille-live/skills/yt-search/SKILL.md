---
name: yt-search
description: Wyszukuje materiały na YouTube przez oficjalne Data API v3 z filtrowaniem po wyświetleniach, języku, dacie, długości i sortowaniu. Zwraca listę top N filmów jako markdown + JSON gotowy do podania innym skillom (np. /youtube-transcript do oglądania). Używaj ZAWSZE gdy user prosi o szukanie materiałów na YouTube, research tematu na YT, listę filmów o X, inspiracje do rolek/lekcji, analizę konkurencji na YouTube, tweety/wpisy na temat który ktoś już opisał na YT. Trigger na frazy — "szukaj na youtube", "znajdź filmy o", "zbadaj na yt", "co jest na youtube o", "research yt", "najpopularniejsze filmy", "top wideo o".
allowed-tools: ["Bash", "Read", "Write"]
---

# yt-search

Wyszukiwarka YouTube z filtrowaniem i rankingiem. Klocek do composition z innymi skillami — sama tylko znajduje, nie ogląda.

## Kiedy używać

- Research tematu na YT (kombo z `/youtube-transcript` do obejrzenia top N)
- Inspiracje do tytułów/rolek — patrz jakie tytuły hookują
- Analiza konkurencji — co robią inni w niszy
- Budowanie listy "do obejrzenia później"

## Lokalizacje

- **Skrypt:** `{baseDir}/scripts/yt_search.py`
- **Output markdown:** `Zasoby/AI Output/yt-search/YYYY-MM-DD-[query-slug].md`
- **Output JSON (do pipeline'u):** obok markdowna, `.json` z tą samą nazwą

## Workflow

> **Cross-platform Python:** Przed uruchomieniem skryptów ustaw interpreter (na Windows `python3` to stub ze Sklepu Microsoft):
> ```bash
> PYTHON=$(command -v python3 || command -v python)
> ```

1. Ustal z userem zapytanie i filtry. Jeśli user daje tylko query — użyj sensownych defaultów (top 10 wyników, min 1000 views, ostatnie 2 lata, skip shorts).
2. Uruchom skrypt:
   ```bash
   $PYTHON {baseDir}/scripts/yt_search.py "query" \
     --top 10 \
     --min-views 1000 \
     --lang pl \
     --since 2024-01-01 \
     --skip-shorts \
     --sort relevance
   ```
3. Skrypt zapisuje 2 pliki: `.md` (do czytania) + `.json` (do parsowania).
4. Pokaż userowi ścieżki + krótkie podsumowanie (ile znalezionych, top 3 tytuły).
5. Zapytaj co robimy dalej: "obejrzeć top N?" → wtedy dla każdego `video_id` z JSONa wywołaj `/youtube-transcript` i syntezuj w raport.

## Flagi CLI

| Flaga | Default | Opis |
|-------|---------|------|
| `query` (positional) | — | Zapytanie, w cudzysłowie |
| `--top N` | 10 | Ile wyników pokazać w sekcji "Detale" markdowna (JSON ma wszystkie) |
| `--raw-fetch N` | 100 | Ile kandydatów pobrać z YouTube przed filtrami (paginacja po 50) |
| `--min-views N` | 1000 | Minimum wyświetleń |
| `--lang xx` | (brak) | Kod języka: `pl`, `en`. Brak = wszystkie |
| `--since YYYY-MM-DD` | (brak) | Materiały od tej daty |
| `--skip-shorts` | false | Pomiń Shorts (<60s) |
| `--min-duration SEC` | 0 | Minimalna długość w sekundach |
| `--sort X` | relevance | `relevance` / `date` / `viewCount` / `rating` |
| `--channel-blacklist "a,b,c"` | — | Ignoruj te kanały (po nazwie) |
| `--json-only` | false | Nie zapisuj markdowna, tylko JSON |

## Format markdowna

```markdown
---
query: "claude code tutorial"
date: 2026-04-20
filters:
  max: 10
  min_views: 1000
  lang: pl
  since: 2024-01-01
  skip_shorts: true
  sort: relevance
total_found: 8
---

# YT Search: claude code tutorial

**Filtry:** 10 max | min 1000 views | pl | od 2024-01-01 | skip shorts | sort: relevance
**Znalezionych:** 8

| # | Tytuł | Kanał | Views | ER% | Długość | Data | Link |
|---|-------|-------|-------|-----|---------|------|------|
| 1 | ... | ... | 45k | 3.2% | 18:45 | 2026-02-11 | [link](url) |

## Detale

### 1. [Tytuł] — Kanał
- **views:** 45 000 | **likes:** 1 440 | **engagement rate:** 3.2%
- **długość:** 18:45 | **opublikowano:** 2026-02-11
- **video_id:** `abc123`
- **URL:** https://youtube.com/watch?v=abc123
- **opis (skrót):** pierwsze 200 znaków...

### 2. ...
```

## Format JSON

```json
{
  "query": "claude code tutorial",
  "date": "2026-04-20",
  "filters": {...},
  "results": [
    {
      "rank": 1,
      "video_id": "abc123",
      "url": "https://youtube.com/watch?v=abc123",
      "title": "...",
      "channel": "...",
      "channel_id": "UC...",
      "views": 45000,
      "likes": 1440,
      "comments": 88,
      "engagement_rate": 3.2,
      "duration_seconds": 1125,
      "duration_human": "18:45",
      "published_at": "2026-02-11T14:30:00Z",
      "description_preview": "..."
    }
  ]
}
```

## Pipeline z innymi skillami

Gdy user chce nie tylko listę, tylko research:

1. Uruchom `yt-search` z sensownymi filtrami
2. Otwórz `.json` z wyniku
3. Dla top N (domyślnie 5) video_id: wywołaj `/youtube-transcript` z URL
4. Zsyntezuj wszystkie transkrypcje w raport (TL;DR, kluczowe tematy, rozbieżności, per-video summary)
5. Zapisz raport do `Zasoby/AI Output/yt-research/YYYY-MM-DD-[query-slug].md`

## Wymagania

- Python 3.x
- Pakiety: `requests`, `python-dotenv`
- `YOUTUBE_API_KEY` w `.env` (YouTube Data API v3)

## Quota (YouTube Data API v3)

- Dzienny limit: **10 000 units** (free tier)
- `search.list` = **100 units** (drogie)
- `videos.list` = **1 unit** per batch (do 50 video IDs na call)
- Pojedyncze wywołanie skilla = ~101 units (search + enrich) → ~99 searchy dziennie

## Graceful failures

- Brak klucza → czytelny błąd z instrukcją "dodaj YOUTUBE_API_KEY do .env"
- Quota exceeded (403 quotaExceeded) → komunikat + data resetu UTC
- Zero wyników po filtrach → zapisz pusty markdown z sugestią złagodzenia filtrów
