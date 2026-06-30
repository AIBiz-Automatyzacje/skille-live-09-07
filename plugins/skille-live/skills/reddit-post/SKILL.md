---
name: reddit-post
description: Pobiera post z Reddita wraz z komentarzami i zapisuje jako Markdown. Użyj gdy użytkownik chce zapisać post z Reddita, pobrać dyskusję, zarchiwizować wątek, lub zrobić notatki z Reddita.
allowed-tools: ["Bash", "Read", "Write"]
---

# Reddit Post

Pobiera post z Reddita wraz z komentarzami i zapisuje w Obsidianie.

Backend: oficjalne Reddit API przez PRAW (read-only OAuth). 1 request = post + top 50 komentarzy (sortowane po upvotes).

## Lokalizacje

- **Skrypt:** `{baseDir}/scripts/reddit_post.py`
- **Notatki:** `Zasoby/Research/Reddit/[slug-tytulu]/`

## Workflow

> **Cross-platform Python:** Przed uruchomieniem skryptów ustaw interpreter (na Windows `python3` to stub ze Sklepu Microsoft):
> ```bash
> PYTHON=$(command -v python3 || command -v python)
> ```

1. Pobierz URL posta Reddit od użytkownika
2. Uruchom skrypt:
   ```bash
   $PYTHON {baseDir}/scripts/reddit_post.py <URL>
   ```
3. Skrypt tworzy folder z `post.md` i `.meta.json`
4. Wczytaj `post.md` z utworzonego folderu
5. Potwierdź użytkownikowi lokalizację plików i podsumuj treść

## Format outputu

```markdown
# [Tytuł posta]

> **Subreddit:** r/[nazwa] | **Autor:** u/[username] | **Data:** [data]
> **Upvotes:** [liczba] | **Komentarze:** [liczba]
> [Link do posta]

---

## Treść posta
[treść]

---

## Komentarze (50)

### 1. u/[username] ([punkty] pts)
*[data]*

[treść komentarza]
```

## Wymagania

- Python 3.x, pakiety: `praw`, `python-dotenv`
- `.env` w workspace root:
  - `REDDIT_CLIENT_ID`
  - `REDDIT_CLIENT_SECRET`
  - `REDDIT_USER_AGENT` (format: `nazwa/wersja by /u/username`)

## Koszt

**Darmowe.** Reddit API w read-only mode — 100 req/min, brak limitów miesięcznych.
