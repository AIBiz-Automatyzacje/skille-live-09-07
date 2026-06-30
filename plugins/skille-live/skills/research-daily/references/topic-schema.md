# Schemat `_topic.md`

```yaml
---
slug: mobile-design-best-practices
created: 2026-05-09
last_run: '2026-05-10'
total_runs: 3
core_queries:
  - "mobile app design best practices 2026"
  - "ios design guidelines HIG"
  - ...
emerging_queries:
  - "liquid glass accessibility"
  - ...
subreddits:
  - UXDesign
  - iosdev
  - ...
filters:
  yt:
    min_views: 2000
    skip_shorts: true
    since: 2025-01-01
    sort: relevance
  reddit:
    min_upvotes: 15
    min_comments: 3
    time: year
    sort: top
    max_items: 75
  x:
    enable: true                # default true — bird CLI skonfigurowane w naszym setupie
    min_likes: 30
    min_retweets: 5
    since_days: 7
    exclude_replies: true
    per_query_limit: 30
fetch_content:
  top_yt: 10
  top_reddit: 10
  top_x: 10
x:                              # osobny set krótkich queries dla X (full-text search X słabo radzi sobie z długimi)
  queries:
    - "krótka query 1"
    - "krótka query 2"
---

# Topic: {Tytuł}

## Focus
[Markdown z opisem co interesuje, czego szukam, czego ignorować]

## Notatki własne
[Komentarze usera]
```
