# Skille Live 09.07 — Akademia Automatyzacji

Zestaw gotowych skilli Claude Code, których używam na co dzień w swoim asystencie. Jeden marketplace, jedna instalacja — i masz wszystkie 9.

To te same skille, które pokazuję na live 09.07.2026. Bierzesz, konfigurujesz klucze i działasz.

## Co dostajesz (9 skilli)

| Skill | Co robi | Czego potrzebuje |
|-------|---------|------------------|
| **gog** | Całe Google Workspace z poziomu asystenta: Gmail, Kalendarz, Dysk, Arkusze, Dokumenty. Wyślij maila, dodaj wydarzenie, czytaj/edytuj arkusz — jednym poleceniem. | CLI `gog` + autoryzacja Google (OAuth) |
| **himalaya** | E-mail z terminala (IMAP/SMTP): czytanie, wysyłka, odpowiedzi, przeszukiwanie skrzynki bez otwierania klienta pocztowego. | CLI `himalaya` + konto IMAP/SMTP |
| **bird** | X/Twitter z poziomu asystenta: czytanie, wyszukiwanie, publikowanie, interakcje, pobieranie wideo. | CLI `bird` + cookies konta X |
| **youtube-transcript** | Pobiera transkrypcję dowolnego filmu z YouTube i robi z niej podsumowanie / notatki. | — |
| **yt-search** | Wyszukiwarka YouTube (oficjalne Data API v3) z filtrami: wyświetlenia, język, data, długość. Zwraca top N filmów gotowych do podania do `youtube-transcript`. | `YOUTUBE_API_KEY` |
| **reddit-search** | Wyszukiwarka Reddita (oficjalne API / PRAW) z filtrami upvotes / komentarze / subreddity / czas. Zwraca top posty gotowe do pobrania przez `reddit-post`. | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT` |
| **reddit-post** | Pobiera pojedynczy post z Reddita z komentarzami i zapisuje jako czysty Markdown. | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT` |
| **reddit-news** | Codzienny skan wybranych subredditów (AI, narzędzia, automatyzacja), filtr po kontekście i upvotes → raport HTML + zadanie. Pod cron. | `APIFY_API_KEY` |
| **research-daily** | Agent researchu multi-source: równolegle YouTube + Reddit + Perplexity + X, klasyfikacja i destylacja do rosnącej bazy wiedzy. Pod cron lub na żądanie. | `YOUTUBE_API_KEY` + `REDDIT_*` + `PERPLEXITY_API_KEY` (X opcjonalnie). Wymaga też 4 subagentów researchowych — patrz uwaga niżej. |

## Instalacja

1. W terminalu (najlepiej w Twoim vaultcie Obsidian) uruchom asystenta: `claude`
2. Dodaj marketplace:

   ```
   /plugin marketplace add AIBiz-Automatyzacje/skille-live-09-07
   ```

3. Zainstaluj plugin:

   ```
   /plugin install skille-live
   ```

To wszystko — masz wszystkie 9 skilli. Część z nich wymaga jeszcze kluczy API lub zewnętrznych CLI (kolumna „Czego potrzebuje").

## Klucze API

Skille czytają klucze ze zmiennych środowiskowych (plik `.env` w katalogu, z którego odpalasz `claude`). Przykład:

```
YOUTUBE_API_KEY=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=...
APIFY_API_KEY=...
PERPLEXITY_API_KEY=...
```

Gdzie je zdobyć:
- **YouTube** — Google Cloud Console → YouTube Data API v3 → klucz API (darmowy limit dzienny).
- **Reddit** — https://www.reddit.com/prefs/apps → utwórz aplikację typu „script" (darmowe, read-only).
- **Apify** — https://apify.com → Settings → Integrations → API token (reddit-news działa przez Apify Reddit Scraper).
- **Perplexity** — https://www.perplexity.ai/settings/api → klucz API (płatne).

Zewnętrzne CLI:
- **gog** — narzędzie do Google Workspace (wymaga autoryzacji OAuth do Twojego konta Google).
- **himalaya** — https://github.com/pimalaya/himalaya (konfiguracja IMAP/SMTP w `~/.config/himalaya/`).
- **bird** — `brew install steipete/tap/bird` lub `npm i -g @steipete/bird` (logujesz się cookies konta X).

## Uwaga do `research-daily`

To najbardziej rozbudowany skill. Działa w architekturze **master + 4 subagenty** (`yt-research-agent`, `reddit-research-agent`, `perplexity-research-agent`, `x-research-agent`), które trzeba mieć zdefiniowane jako agenty w `~/.claude/agents/`. Sam skill (orkiestrator) jest w pluginie; definicje subagentów dograj osobno, jeśli chcesz pełnego pipeline'u. Zapisuje wyniki do `Zasoby/Research/{temat}/` — pod strukturę Obsidian.

## Wsparcie

Akademia Automatyzacji — https://akademiaautomatyzacji.com

---

*Skille udostępnione „as is" na potrzeby live'a. Wymagają własnych kluczy API i konfiguracji.*
