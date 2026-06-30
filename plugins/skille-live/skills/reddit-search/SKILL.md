---
name: reddit-search
description: Wyszukuje posty na Reddicie przez oficjalne Reddit API (PRAW) z filtrowaniem po upvotes, komentarzach, subredditach i czasie. Zwraca listę top N postów jako markdown + JSON gotowy do podania `/reddit-post` (pobiera pełne dyskusje z komentarzami). Używaj ZAWSZE gdy user prosi o szukanie czegoś na Reddicie, research tematu na Reddit, listę postów o X, analizę dyskusji w subredditach, opinie społeczności, case studies z Reddita. Trigger na frazy — "szukaj na reddicie", "znajdź posty o", "co na reddicie o", "research reddit", "opinie ludzi o", "najpopularniejsze dyskusje", "top posty o".
allowed-tools: ["Bash", "Read", "Write"]
---

# reddit-search

Wyszukiwarka Reddita z filtrowaniem. Klocek do composition z `/reddit-post` (pełne dyskusje) analogicznie do pary `/yt-search` + `/youtube-transcript`.

Backend: oficjalne Reddit API przez PRAW (read-only OAuth client_credentials). Limit 100 req/min — w praktyce nieograniczone dla typowych researchy.

## Kiedy używać

- Research tematu na Reddicie (kombo z `/reddit-post` dla top N dyskusji)
- Inspiracje do rolek/wpisów — co zadaje ludziom w danej niszy
- Analiza konkurencji — co robią inni
- Case studies z liczbami (r/sideproject, r/indiehackers to złoto)
- Opinie użytkowników o narzędziach/metodach

## Lokalizacje

- **Skrypt:** `{baseDir}/scripts/reddit_search.py`
- **Output:** `$REDDIT_OUTPUT_DIR/YYYY-MM-DD-[query-slug].{md,json}` (fallback: `Zasoby/AI Output/reddit-search/` w workspace)

## Workflow (default research mode)

> **Cross-platform Python:** Przed uruchomieniem skryptów ustaw interpreter (na Windows `python3` to stub ze Sklepu Microsoft):
> ```bash
> PYTHON=$(command -v python3 || command -v python)
> ```

1. Ustal z userem: query (lub lista query), opcjonalnie subreddity do skonkretyzowania
2. Uruchom skrypt:
   ```bash
   $PYTHON {baseDir}/scripts/reddit_search.py \
     --query "claude code mobile app" \
     --query "claude code react native" \
     --subreddits "ClaudeAI,reactnative,iosdev,expo" \
     --sort top --time year \
     --min-upvotes 20 --min-comments 5 \
     --max-items 100 --top 10
   ```
3. Skrypt loopuje (subreddit × query), deduplikuje, filtruje, zapisuje 2 pliki
4. Pokaż userowi ścieżki + top 3 tytuły
5. Zapytaj co dalej: "obejrzeć top N dyskusji?" → dla każdego URL z JSON wywołaj `/reddit-post`

## Flagi CLI

| Flaga | Default | Opis |
|-------|---------|------|
| `--query TEXT` (wielokrotna) | — | Query, można powtórzyć dla multi-search |
| `--subreddits "a,b,c"` | (brak) | Whitelist subredditów (bez prefiksu `r/`). Bez = `r/all` |
| `--sort X` | `top` | `top` / `hot` / `new` / `relevance` / `comments` |
| `--time X` | `year` | `hour` / `day` / `week` / `month` / `year` / `all` |
| `--min-upvotes N` | 10 | Odrzuć posty z mniej upvotami |
| `--min-comments N` | 3 | Odrzuć bez dyskusji |
| `--max-items N` | 100 | Limit per (subreddit × query). Max 100 (cap Reddit API) |
| `--top N` | 10 | Ile pokazać w detalu markdowna (JSON ma wszystkie) |
| `--since YYYY-MM-DD` | — | Dodatkowy filtr daty (dokładniejszy niż `--time`) |
| `--nsfw` | false | Włącz NSFW |

**Uwaga limit/call:** Reddit API zwraca max 100 wyników per call. Skrypt robi `N_subreddits × N_queries` calli, więc dla 4 subów × 2 query × 100 limit = potencjalnie 800 raw wyników. Po deduplikacji i filtrach często zostaje 50-200.

## Format markdowna

```markdown
---
queries: ["claude code mobile app", "claude code react native"]
date: 2026-05-13
filters:
  subreddits: "ClaudeAI,reactnative,iosdev,expo"
  sort: top
  time: year
  min_upvotes: 20
  min_comments: 5
total_found: 87
showing_top: 10
---

# Reddit Search: claude code mobile app | claude code react native

**Filtry:** top/year | min 20 upvotes | min 5 komentarzy | r/ClaudeAI,reactnative,iosdev,expo
**Znalezionych:** 87 | **Pokazuję top:** 10

## Top 10 — tabela
| # | Tytuł | r/ | Autor | ⬆️ | 💬 | Data | Link |
|---|-------|-----|-------|-----|-----|------|------|
| 1 | ... | ClaudeAI | u/x | 432 | 67 | 2026-02-11 | [link] |

## Detale top 10
### 1. [Tytuł] — r/ClaudeAI
- **upvotes:** 432 | **komentarze:** 67 | **autor:** u/x
- **post_id:** `abc123` | **opublikowano:** 2026-02-11
- **URL:** https://www.reddit.com/r/ClaudeAI/comments/abc123/...
- **body (skrót):** pierwsze 300 znaków...
```

## Format JSON

```json
{
  "queries": ["..."],
  "date": "2026-05-13",
  "filters": {...},
  "total_found": 87,
  "showing_top": 10,
  "results": [
    {
      "rank": 1,
      "post_id": "abc123",
      "url": "https://www.reddit.com/r/ClaudeAI/comments/abc123/...",
      "title": "...",
      "subreddit": "ClaudeAI",
      "author": "x",
      "body": "...",
      "body_preview": "...",
      "upvotes": 432,
      "comments": 67,
      "created_utc": 1707654000.0,
      "created_at": "2026-02-11T14:30:00+00:00",
      "is_video": false,
      "over18": false
    }
  ]
}
```

## Pipeline z innymi skillami

Gdy user chce research end-to-end:

1. `/reddit-search` z sensownymi filtrami → lista top N
2. User wybiera (lub AI wybiera pod kątem tematu)
3. Dla wybranych URL → `/reddit-post` (pełne drzewo komentarzy)
4. Synteza wszystkich dyskusji → raport `Zasoby/AI Output/reddit-research/YYYY-MM-DD-[slug].md`

## Wymagania

- Python 3.x, pakiety: `praw`, `python-dotenv`
- `.env` w workspace root:
  - `REDDIT_CLIENT_ID`
  - `REDDIT_CLIENT_SECRET`
  - `REDDIT_USER_AGENT` (format: `nazwa/wersja by /u/username`)

## Koszt

**Darmowe.** Reddit API w read-only mode (client_credentials) — 100 req/min, brak limitów miesięcznych. PRAW handles throttling automatycznie.

## Advanced — capabilities PRAW poza defaultowym workflow

Skrypt obsługuje search w obrębie subreddita. PRAW pozwala na więcej:

**Listing trendujących postów w subreddicie (bez query):**
```python
import praw, os
from dotenv import load_dotenv; load_dotenv()
r = praw.Reddit(client_id=os.getenv("REDDIT_CLIENT_ID"),
                client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
                user_agent=os.getenv("REDDIT_USER_AGENT"))
for p in r.subreddit("ClaudeAI").top("month", limit=50): print(p.title, p.score)
```

**Historia usera:**
```python
for s in r.redditor("username").submissions.new(limit=50): print(s.title)
for c in r.redditor("username").comments.new(limit=100): print(c.body[:100])
```

**Discovery — szukaj subredditów po nazwie/temacie:**
```python
for sub in r.subreddits.search("ai coding", limit=20):
    print(sub.display_name, sub.subscribers)
```

**Streaming nowych postów (real-time monitoring):**
```python
for p in r.subreddit("ClaudeAI").stream.submissions(): print(p.title)
```

Wszystkie powyższe są nielimitowane w czasie i działają w tym samym OAuth context (read-only).

## Co tracimy względem starego Apify-based skilla

- **Search w komentarzach** — Reddit API nie wspiera (Apify scrape'ował przez UI search). Workaround: pobierz top posty, dla każdego `/reddit-post`, grep w komentarzach lokalnie.
- **Search w userach** — częściowo, przez `r.subreddits.search()` da się znaleźć usery (jako redditor object), ale full-text search po profilach to limit Reddit API.
