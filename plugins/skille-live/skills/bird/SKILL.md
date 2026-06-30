---
name: bird
description: X/Twitter CLI for reading, searching, posting, engagement, and video download via cookies.
homepage: https://bird.fast
allowed-tools: Bash(bird:*), Bash(yt-dlp *)
metadata: {"clawdbot":{"emoji":"🐦","requires":{"bins":["bird"]},"install":[{"id":"brew","kind":"brew","formula":"steipete/tap/bird","bins":["bird"],"label":"Install bird (brew)","os":["darwin"]},{"id":"npm","kind":"node","package":"@steipete/bird","bins":["bird"],"label":"Install bird (npm)"}]}}
---

# bird 🐦

Fast X/Twitter CLI using GraphQL + cookie auth.

## Install

```bash
# npm/pnpm/bun
npm install -g @steipete/bird

# Homebrew (macOS, prebuilt binary)
brew install steipete/tap/bird

# One-shot (no install)
bunx @steipete/bird whoami
```

## Authentication

`bird` uses cookie-based auth.

Use `--auth-token` / `--ct0` to pass cookies directly, or `--cookie-source` for browser cookies.

Run `bird check` to see which source is active. For Arc/Brave, use `--chrome-profile-dir <path>`.

## Commands

### Account & Auth

```bash
bird whoami                    # Show logged-in account
bird check                     # Show credential sources
bird query-ids --fresh         # Refresh GraphQL query ID cache
```

### Reading Tweets

```bash
bird read <url-or-id>          # Read a single tweet
bird <url-or-id>               # Shorthand for read
bird thread <url-or-id>        # Full conversation thread
bird replies <url-or-id>       # List replies to a tweet
```

### Timelines

```bash
bird home                      # Home timeline (For You)
bird home --following          # Following timeline
bird user-tweets @handle -n 20 # User's profile timeline
bird mentions                  # Tweets mentioning you
bird mentions --user @handle   # Mentions of another user
```

### Search

```bash
bird search "query" -n 10
bird search "from:steipete" --all --max-pages 3
```

### News & Trending

```bash
bird news -n 10                # AI-curated from Explore tabs
bird news --ai-only            # Filter to AI-curated only
bird news --sports             # Sports tab
bird news --with-tweets        # Include related tweets
bird trending                  # Alias for news
```

### Lists

```bash
bird lists                     # Your lists
bird lists --member-of         # Lists you're a member of
bird list-timeline <id> -n 20  # Tweets from a list
```

### Bookmarks & Likes

```bash
bird bookmarks -n 10
bird bookmarks --folder-id <id>           # Specific folder
bird bookmarks --include-parent           # Include parent tweet
bird bookmarks --author-chain             # Author's self-reply chain
bird bookmarks --full-chain-only          # Full reply chain
bird unbookmark <url-or-id>
bird likes -n 10
```

### Social Graph

```bash
bird following -n 20           # Users you follow
bird followers -n 20           # Users following you
bird following --user <id>     # Another user's following
bird about @handle             # Account origin/location info
```

### Engagement Actions

```bash
bird follow @handle            # Follow a user
bird unfollow @handle          # Unfollow a user
```

### Posting

```bash
bird tweet "hello world"
bird reply <url-or-id> "nice thread!"
bird tweet "check this out" --media image.png --alt "description"
```

**⚠️ Posting risks**: Posting is more likely to be rate limited; if blocked, use the browser tool instead.

## Media Uploads

```bash
bird tweet "hi" --media img.png --alt "description"
bird tweet "pics" --media a.jpg --media b.jpg  # Up to 4 images
bird tweet "video" --media clip.mp4            # Or 1 video
```

## Video Download 🎬

Pobieranie wideo z tweetów za pomocą `yt-dlp`. Działa z publicznymi tweetami zawierającymi wideo.

```bash
# Pobierz wideo z tweeta (domyślna jakość)
yt-dlp "<tweet-url>" -o "Marketing/media/%(title)s.%(ext)s"

# Pobierz z własną nazwą
yt-dlp "<tweet-url>" -o "Marketing/media/nazwa-pliku.mp4"

# Wymuś najlepszą jakość MP4
yt-dlp "<tweet-url>" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" -o "Marketing/media/%(title)s.%(ext)s"

# Tylko pokaż dostępne formaty (bez pobierania)
yt-dlp "<tweet-url>" --list-formats
```

### Workflow: Tweet → Video → Analiza

Pełny pipeline od tweeta do analizy wideo:

1. **Odczytaj tweet** — `bird read <url>` (sprawdź czy jest wideo)
2. **Pobierz wideo** — `yt-dlp "<url>" -o "Marketing/media/%(title)s.%(ext)s"`
3. **Analizuj** — użyj `/video-analyze` na pobranym pliku MP4 (Gemini API → opis, tytuły, deskrypcja)

**⚠️ Uwagi:**
- Wymaga `yt-dlp` (`brew install yt-dlp`)
- Niektóre prywatne tweety mogą wymagać cookies — użyj `yt-dlp --cookies-from-browser chrome`
- Duże pliki (>100MB) mogą wymagać dłuższego timeout w video-analyze

## Pagination

Commands supporting pagination: `replies`, `thread`, `search`, `bookmarks`, `likes`, `list-timeline`, `following`, `followers`, `user-tweets`

```bash
bird bookmarks --all                    # Fetch all pages
bird bookmarks --max-pages 3            # Limit pages
bird bookmarks --cursor <cursor>        # Resume from cursor
bird replies <id> --all --delay 1000    # Delay between pages (ms)
```

## Output Options

```bash
--json          # JSON output
--json-full     # JSON with raw API response
--plain         # No emoji, no color (script-friendly)
--no-emoji      # Disable emoji
--no-color      # Disable ANSI colors (or set NO_COLOR=1)
--quote-depth n # Max quoted tweet depth in JSON (default: 1)
```

## Global Options

```bash
--auth-token <token>       # Set auth_token cookie
--ct0 <token>              # Set ct0 cookie
--cookie-source <source>   # Cookie source for browser cookies (repeatable)
--chrome-profile <name>    # Chrome profile name
--chrome-profile-dir <path> # Chrome/Chromium profile dir or cookie DB path
--firefox-profile <name>   # Firefox profile
--timeout <ms>             # Request timeout
--cookie-timeout <ms>      # Cookie extraction timeout
```

## Config File

`~/.config/bird/config.json5` (global) or `./.birdrc.json5` (project):

```json
{
  cookieSource: ["chrome"],
  chromeProfileDir: "/path/to/Arc/Profile",
  timeoutMs: 20000,
  quoteDepth: 1
}
```

Environment variables: `BIRD_TIMEOUT_MS`, `BIRD_COOKIE_TIMEOUT_MS`, `BIRD_QUOTE_DEPTH`

## Troubleshooting

### Query IDs stale (404 errors)
```bash
bird query-ids --fresh
```

### Cookie extraction fails
- Check browser is logged into X
- Try different `--cookie-source`
- For Arc/Brave: use `--chrome-profile-dir`

---

**TL;DR**: Read/search/engage with CLI. Post carefully or use browser. 🐦