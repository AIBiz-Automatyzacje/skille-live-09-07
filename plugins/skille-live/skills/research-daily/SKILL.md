---
name: research-daily
description: Multi-source research orchestrator. Spawnuje 4 wyspecjalizowane subagenty równolegle (yt-research-agent, reddit-research-agent, perplexity-research-agent, x-research-agent), które fetchują i destylują content z YT/Reddit/Perplexity/X, zapisują pełne dane do raw/ i zwracają lekkie handoffy. Master Claude robi cross-source klasyfikację 🔥/💡/🔁/❌, aktualizuje wiki i tworzy daily digest. Działa zarówno interaktywnie (user mówi "uruchom research X") jak i headless przez claude-cron. Każdy temat to folder w Zasoby/Research/{slug}/ który rośnie w czasie. Trigger phrases — "daily research", "uruchom research", "monitoruj X", "śledź co się dzieje w", "baza wiedzy o", "agent do researchu", "zrób research daily", "odpal research", "weekly rollup researchu".
---

# research-daily — orchestrator

Multi-source research agent w architekturze **master + 4 specialist subagents**.

## Konfiguracja (env vars)

Wszystkie ścieżki i URL'e w skillu mogą być nadpisane przez env vars. Defaults pasują do workspace Obsidian z folderem `Zasoby/Research/`.

| Env var | Default | Co to |
|---------|---------|-------|
| `RESEARCH_BASE_DIR` | `$WORKSPACE/Zasoby/Research` | Główny folder na tematy researchowe (`{base}/{slug}/`) |
| `CLAUDE_CRON_URL` | `http://localhost:7777` | URL panelu claude-cron do scheduling daily runów |

W dokumentacji niżej pojawiają się ścieżki `Zasoby/Research/{slug}/` — czytaj je jako `${RESEARCH_BASE_DIR}/{slug}/`. Tak samo `localhost:7777` = `${CLAUDE_CRON_URL}`.

## Filozofia

**Master (ten skill) NIE fetchuje danych** — deleguje do subagentów. Każdy subagent ma własny izolowany kontekst (do 200k tokenów raw content), zwraca masterowi destylację (~2-3k tokens summary). Master ma w głównym kontekście tylko 4 lekkie handoffy = ~12k tokens, dzięki czemu nie eksploduje przy 38 queries × 4 platformy.

**Subagenci zapisują do `raw/`, master edytuje `wiki/`.** Single writer principle — master jest jedynym autorem wiki, digestów, _seen, _timeline, _metrics. Subagenci piszą tylko do swoich `raw/{źródło}-{date}.md`.

**Cross-source klasyfikacja jest super-mocą mastera.** Subagent yt nie wie co zobaczył reddit-agent. Master ma 4 handoffy obok siebie i może powiedzieć: "iOS 26 Liquid Glass pojawił się w YT (3 wideo), Reddit (4 wątki, 2300 upvotes), X (12 tweetów +50k engagement) i Perplexity (claim accessibility issue) — to jest 🔥".

## Architektura runów

```
User mówi "uruchom research mobile-design-best-practices"
         ↓
Master Claude (ten skill)
         ↓
   1. Read _topic.md, _seen.json, last digest
   2. Spawn 4 agents PARALLEL (single message, multiple Agent calls):
      ┌──────────────┬──────────────┬───────────────┬──────────────┐
      │ yt-research  │ reddit-      │ perplexity-   │ x-research   │
      │ -agent       │ research     │ research      │ -agent       │
      │              │ -agent       │ -agent        │ (if enabled) │
      └──────┬───────┴──────┬───────┴──────┬────────┴──────┬───────┘
             ↓               ↓               ↓                 ↓
     raw/yt-content.md  raw/reddit-      raw/web.md     raw/x-content.md
                        content.md
             ↓               ↓               ↓                 ↓
     summary+findings  summary+findings summary+claims  summary+threads
                              ↓
   3. Master odbiera 4 handoffy (~12k tokens łącznie)
   4. Cross-source klasyfikacja: które tematy pojawiają się w 2+ źródłach?
   5. Update wiki/ (lazy read raw/ przy pisaniu długiego działu)
   6. Zapisz: digests/{date}.md, _seen.json (dopisz IDs ze wszystkich agentów),
              _timeline.md (1 linia), _metrics.md (Poziom 1-3)
   7. Update _topic.md: last_run, total_runs, ewentualnie emerging_queries
```

## Komendy (jak user może wywołać)

| User mówi | Co robisz |
|-----------|-----------|
| "uruchom research mobile-design" / "odpal research X" | `run` mode — pełen pipeline, 4 agentów spawn |
| "zrób research na temat X" (nowy temat) | `init` mode — utwórz folder, wygeneruj config, spawn agentów |
| "co monitoruję?" / "lista tematów" | `list` mode — wylistuj `Zasoby/Research/*/` z statusem |
| "weekly rollup X" / "podsumuj tydzień" | `weekly` mode — konsoliduje 7 ostatnich digestów |
| "zaktualizuj research X bez fetcha" | `inspect` mode — pokaż status bez nowego fetcha |

## Workflow `init` (nowy temat)

User mówi "zrób research na temat X" — tworzysz folder, generujesz config, NIE odpalasz fetcha (cron zrobi to nocą lub user manualnie).

1. **Pytanie o focus** (max 1-2 zdania odpowiedzi):
   > "Co Cię najbardziej interesuje w [X]? Np. case studies z liczbami, porównania techniczne, trendy/nowe narzędzia, opinie builderów."

2. **Wygeneruj config z własnej wiedzy o niszy** — NIE pytaj usera o queries i subreddity, zgaduj z kontekstu:
   - **core_queries (4-6):** warianty tego samego tematu — exact match + synonyms + powiązane narzędzia
   - **subreddits (5-10):** właściwe dla niszy
   - **filtry:** sensowne defaults (yt: min_views=1000, skip_shorts=true, since=2024-06-01; reddit: min_upvotes=10, time=year, sort=top, max_items=75; **x: enable=true default** — bird CLI aktywny w naszym setupie)
   - **fetch_content:** top_yt=10, top_reddit=10, top_x=10
   - **x.queries (5-7):** krótkie, precyzyjne (full-text search X słabo radzi sobie z długimi frazami) — destyluj z core_queries 1-2 słowowe warianty
   - **focus:** zacytuj odpowiedź usera + dorzuć kontekst

3. **Pokaż config userowi** w 3-4 linijkach do zatwierdzenia:
   > "Config: queries [A, B, C], subreddity [x, y, z], focus: ...
   > Jedziemy? (tak/edytuj)"

4. **Po OK:**
   - Utwórz folder `Zasoby/Research/{slug}/`
   - Zapisz `_topic.md` z configiem
   - Inicjalizuj `_seen.json` jako `{"youtube": {}, "reddit": {}, "x": {}, "urls": {}}`
   - Pusty `_index.md`, `_timeline.md`, `_metrics.md`
   - Pusty `wiki/README.md` (placeholder spisu treści — działy powstaną po Run #1)
   - Pusty folder `raw/` i `digests/`

5. **Zaproponuj cron job:**
   > "Config zapisany. Dodać do claude-cron na 03:00 codziennie? Komenda do panelu localhost:7777:
   > `/research-daily run {slug}`
   > Pierwszy digest pojawi się jutro rano w `Zasoby/Research/{slug}/digests/`."

## Workflow `run` (istniejący temat)

### Krok 1 — Read state

Przed spawnem agentów wczytaj:
- `_topic.md` — queries, subreddits, filtry, focus, fetch_content
- `_seen.json` — co już zobaczyliśmy (dla deduplication przez agentów)
- `_index.md` — counters, tymczasowe obserwacje, status promocji do działów
- Ostatnie 1-2 `digests/*.md` — dla kontekstu o tym co już było 🔥

### Krok 2 — Spawn 4 agentów PARALLEL

**WAŻNE: w jednym message wywołaj wszystkie 4 Agent tool calls jednocześnie.** Anthropic best practice — paralelne spawny wykonują się równolegle, sekwencyjne nie.

Dla każdego agenta przygotuj payload (z _topic.md i _seen.json):

```yaml
yt-research-agent:
  slug: {slug}
  topic_folder: Zasoby/Research/{slug}/
  queries: [core + emerging]
  filters: {filters.yt}
  seen_yt: {_seen.json.youtube}
  focus: {wyciąg z _topic.md}
  top_n: {fetch_content.top_yt | 10}
  date: {today}

reddit-research-agent:
  slug: {slug}
  topic_folder: Zasoby/Research/{slug}/
  queries: [core + emerging]
  subreddits: [...]
  filters: {filters.reddit}
  seen_reddit: {_seen.json.reddit}
  focus: ...
  top_n: 10
  date: {today}

perplexity-research-agent:
  slug: {slug}
  queries: [...]
  focus: ...
  seen_urls: {_seen.json.urls}
  date: {today}
  run_mode: full              # albo "weekly" przy weekly rollup
  last_perplexity_run: {z _index.md}

x-research-agent:                # TYLKO jeśli filters.x.enable: true
  slug: {slug}
  queries: [_topic.md.x.queries albo subset core]
  filters: {filters.x}
  seen_tweets: {_seen.json.x}
  focus: ...
  top_n: 10
  date: {today}
```

Jeśli `filters.x.enable: false` — pomiń x-research-agent, w summary masterzapisz "X disabled in topic config".

### Krok 3 — Odbierz handoffy

Każdy agent zwraca markdown z 3 sekcjami: `## Summary`, `## Key Findings`, `## Raw Data`. Łączny rozmiar wszystkich handoffów ≈ 8-15k tokens — mieści się komfortowo w głównym kontekście.

Jeśli któryś agent zwrócił `Quality flag: error` (np. YT quota exceeded, Reddit API rate limit, Perplexity API down) — kontynuuj z pozostałymi, odnotuj w digest sekcja "⚠️ Attention needed".

### Krok 4 — Cross-source klasyfikacja

Tu jest wartość mastera. Patrząc na 4 listy `Key Findings`, identyfikujesz tematy które pojawiają się w **wielu źródłach** — to są kandydaci na 🔥.

**Algorytm:**

1. **Zbuduj cross-source map** — dla każdego unikalnego tematu policz w ilu źródłach (YT/Reddit/X/Perplexity) się pojawił + sumuj engagement (views/upvotes/likes/retweets).

2. **Klasyfikuj:**
   - **🔥 Hot:** pojawia się w 2+ źródłach **lub** w 1 źródle z bardzo wysokim engagement (YT >100k views, Reddit >500↑, X >1k❤️, Perplexity konsensus); musi być świeże (≤30 dni preferowane); musi mieć konkret (case study, liczby, twarde claims)
   - **💡 New angle:** pierwszy raz pojawia się fraza/koncept/narzędzie — bez względu na liczbę źródeł, byle z merytoryką; **dopisuj do `emerging_queries` w `_topic.md`**
   - **🔁 Repeat of known:** temat już w `wiki/{dział}.md` — zwiększ counter w `_index.md`, dorzuć ewentualnie nowy cytat/przykład, ale NIE pisz o tym wielkiej sekcji w digestcie
   - **❌ Noise:** nie trafia w focus, generic, clickbait — odfiltrowuję, ale zostaje w `raw/` dla audytu

3. **Sprawdź konflikty cytatów** — jeśli YT mówi "X" a Reddit "nie X", flag jako split topic (interesujące, można rozwinąć w wiki).

### Krok 5 — Update wiki (lazy read raw/)

Dla każdego 🔥 i 💡 finding:

1. **Identyfikuj dział** w `wiki/`:
   - Pasuje do istniejącego → otwórz plik, **wpleć w tekst** (rozszerz akapit, dodaj przykład, popraw fakt)
   - Nowy obszar (3+ findingów) → utwórz nowy dział + zaktualizuj `wiki/README.md`
   - Jeden finding bez działu → zapisz w `_index.md` sekcja "Tymczasowe obserwacje", po 3+ podobnych promuj do działu

2. **Lazy read raw/** — gdy piszesz dział wymagający kontekstu (np. cytat dosłowny, porównanie z Things 3, specyficzne liczby), otwórz `raw/{źródło}-{date}.md` przez Read i wyciągnij co potrzeba. NIE wczytuj raw/ "na zapas" — czytaj na potrzebę.

3. **Update counter** na końcu działu i datę ostatniej aktualizacji (zgodnie z wiki style guide poniżej).

4. **Co 5 runów** dla działów >500 słów: consolidation pass — przepisz dział na czysto. Zapisz w `_index.md` historię consolidation passes.

### Krok 6 — Zapisz wszystko

1. **`digests/{date}.md`** — TL;DR z sekcjami:
   - Header (run ID, sources fetched, classification stats)
   - 🔥 Hot (pełne sekcje z cytatami i "Co to znaczy dla mnie")
   - 💡 New angle (krótkie wpisy + Action gdzie wpleciono)
   - 🔁 Repeat (counter updates)
   - ❌ Noise filtered (krótka statystyka per kategoria)
   - ⚠️ Attention needed (warningi: quota, errors, problemy konfiguracji)
   - Metryki (Poziom 1 + reguły reakcji jeśli trafiają)

2. **`_seen.json`** — dopisz wszystkie IDs ze wszystkich agentów (yt video_ids, reddit post_ids, x tweet_ids, perplexity URLs)

3. **`_timeline.md`** — append linia: "{date}: Run #{N} — X hot + Y new angle, sources Z, hot topics: ..."

4. **`_index.md`** — update counters, tymczasowe obserwacje, status promocji emerging→dział

5. **`_metrics.md`** — recompute Poziom 1 (per run), Poziom 2 (działy które dostały update), Poziom 3 (agregaty per topic). Append wiersz do "Historia runów". Jeśli reguły reakcji trafiają → flagi w digest (NIE tylko w _metrics).

6. **`_topic.md`** — update `last_run`, `total_runs += 1`, ewentualnie `emerging_queries` jeśli wykryłeś nowe powtarzające się frazy.

## Wiki tematyczna i digest — pisanie

Wiki w `wiki/` to wikipedia użytkownika dla tematu (jeden plik = jeden dział = mini-artykuł). Digest czyta człowiek rano przy kawie. Oba formaty mają sztywny styl — pełne zdania po polsku, liczby i nazwiska, zero mikro-nagłówków typu `Signal:` / `Action:`.

Przy pisaniu wiki — **zawsze otwórz** `references/wiki-style.md` (zasady, anatomia działu, style guide).

Przy generowaniu digest — **zawsze otwórz** `references/digest-template.md` (zasady tłumaczenia, template z sekcjami 🔥/💡/🔁/❌/⚠️/Metryki, linkowanie wikilinków `[[wiki/{dzial}]]`).

## Klasyfikacja — decision tree

- **🔥 Hot:**
  - 2+ źródła pokazują ten sam temat, LUB
  - 1 źródło z bardzo wysokim engagement (YT >100k, Reddit >500↑, X >1k❤️), LUB
  - Konsensus Perplexity z konkretnymi liczbami
  - + świeże (≤30 dni)
  - + zawiera konkret (case study, revenue, metryki, cytaty z dowodów)

- **💡 New angle:**
  - Pierwszy raz pojawia się fraza/koncept/narzędzie
  - Pasuje do focus
  - Ma przynajmniej 1 mocne źródło (nie clickbait)
  - **Dopisuj do `emerging_queries`**

- **🔁 Repeat:**
  - Temat już w odpowiednim dziale `wiki/`
  - Zwiększ counter w `_index.md`, update `last seen`
  - Nie dokładaj ciężaru w digest

- **❌ Noise:**
  - Nie pasuje do focus
  - Generic / clickbait
  - Odfiltruj, ale zostaw w `raw/` dla audytu

## Exhaustion handling — co gdy 0 hot findings

Eskaluj w kolejności:

1. **Expand temporal scope** — `time: year → all`, `since: 2024-06-01 → usuń`
2. **Lower quality bar** — `min_upvotes: 10 → 5`, `min_views: 1000 → 500`
3. **Switch discovery mode** — `sort: top → new`, dopisz emerging queries
4. **Expand sources** — włącz X jeśli było wyłączone, dorzuć subreddity adjacent niszy
5. **Sugeruj userowi pauzę** — po 3 runach z rzędu bez hot:
   > "Temat wyczerpany na YT/Reddit. Opcje: (a) zmiana focus, (b) rozszerz do pokrewnych, (c) pauza na tydzień"

## Metryki i schemat _topic.md

Health monitoring dla tematu działa na 3 poziomach (per run, per dział, per topic) z regułami reakcji (np. `cache_hits_dedup > 90%` → exhaustion, `unverified_claims > 5` → consolidation pass). Pełne definicje, progi 🟢/🟡/🔴 i format `_metrics.md` — `references/metrics.md`.

Schemat `_topic.md` (frontmatter z queries, subreddits, filters yt/reddit/x, fetch_content, sekcja x.queries) — `references/topic-schema.md`.

## Cron / claude-cron integration

Skill jest bezstanowy — orkiestruje agenty per request. Cykliczne runy odpalamy przez **claude-cron**:

1. Otwórz panel `http://localhost:7777`
2. Dodaj job z komendą:
   ```
   /research-daily run {slug}
   ```
3. Schedule np. `0 3 * * *` (codziennie 3:00)

claude-cron odpala Claude headless, który czyta SKILL.md, spawnuje agentów, syntezuje, zapisuje. Wyniki w `Zasoby/Research/{slug}/digests/` rano.

**NIE używaj** `/schedule` (remote agents) — to inna infrastruktura. Default scheduler = claude-cron.

## Wymagania

- Działające skille `/yt-search`, `/reddit-search`, `/deep-research`, `/bird` (z auth cookies dla X)
- Subagenty w `~/.claude/agents/`: `yt-research-agent.md`, `reddit-research-agent.md`, `perplexity-research-agent.md`, `x-research-agent.md`
- API keys: `YOUTUBE_API_KEY`, `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT`, `PERPLEXITY_API_KEY`
- `bird` CLI tylko jeśli używasz X — `brew install steipete/tap/bird`

## Graceful degradation

- Brak `YOUTUBE_API_KEY` → yt-research-agent zwraca summary "skipped, missing key"
- Brak `REDDIT_CLIENT_ID/SECRET/USER_AGENT` → reddit-research-agent skip
- Brak `PERPLEXITY_API_KEY` → perplexity-research-agent skip
- `filters.x.enable: false` lub brak `bird` CLI → x-research-agent nie spawn
- Minimum: 1 agent musi zwrócić findings, inaczej digest zawiera "🔴 No sources available — sprawdź API keys"

## Koszty szacunkowe (per run)

- yt-research-agent: ~$0.30-0.80 (Claude tokens) + YT API quota (~3-4k jednostek z 10k dziennego limitu)
- reddit-research-agent: ~$0.40-1.00 (Claude tokens) — Reddit API darmowe (PRAW, 100 req/min)
- perplexity-research-agent: ~$0.20-0.50 + Perplexity API ~$0.10 (gdy odpala)
- x-research-agent: ~$0.20-0.50 (gdy enabled)
- Master synteza: ~$0.30-0.60
- **~$1.50-3 / dzień / temat** (z X enabled), ~$1-2.50 bez X — taniej po migracji z Apify na oficjalne Reddit API

Per Day 0 init może być wyższe (~$5-8) bo Perplexity zawsze się odpala.

## Lokalizacje

- **Skill:** `.claude/skills/research-daily/SKILL.md`
- **Subagenty:** `~/.claude/agents/{yt,reddit,perplexity,x}-research-agent.md`
- **Tematy:** `Zasoby/Research/{slug}/`
- **Struktura folderu tematu:**
  ```
  Zasoby/Research/{slug}/
  ├── _topic.md       # config: queries, subreddits, focus, filtry
  ├── _index.md       # meta: counters, status promocji, tymczasowe obserwacje
  ├── _seen.json      # dedup IDs (yt, reddit, x, urls)
  ├── _timeline.md    # historia runów (append-only)
  ├── _metrics.md     # health: Top summary + Mid stan działów + Bottom historia
  ├── digests/        # daily TL;DR
  │   └── YYYY-MM-DD.md
  ├── raw/            # surowe dane per agent per dzień (zapisuje subagent)
  │   ├── YYYY-MM-DD-yt-content.md
  │   ├── YYYY-MM-DD-reddit-content.md
  │   ├── YYYY-MM-DD-web.md
  │   └── YYYY-MM-DD-x-content.md
  └── wiki/           # wikipedia DLA UŻYTKOWNIKA (master pisze)
      ├── README.md   # spis treści
      └── {dzial}.md
  ```
