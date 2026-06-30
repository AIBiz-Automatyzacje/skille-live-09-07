# Metryki sukcesu (`_metrics.md`)

3 poziomy:

**Poziom 1 — per run** (zlicz z handoffów agentów):
- `findings_total` (suma raw items ze wszystkich źródeł)
- `findings_kept_ratio` (klasyfikowane jako 🔥/💡/🔁 vs ❌)
- `cache_hits_dedup` (% odrzuconych przez `_seen`)
- `new_observations` (poszło do "Tymczasowych obserwacji" w `_index.md`)
- `sections_updated` (ile działów wiki dostało update)

**Poziom 2 — per dział** (recompute przy update):
- `word_count` (`wc -w wiki/{dzial}.md`)
- `source_count` (z linii `*Źródła: ...*`)
- `last_update_days_ago` (z `*Ostatni update: YYYY-MM-DD.*`)
- `unverified_claims` (count `⚠️` markerów)
- `consolidation_overdue` (`runs_since_last_consolidation > 5`)

**Poziom 3 — per topic** (agregat):
- `coverage` (działy istniejące / wiki_sections z _topic.md × 100%)
- `freshness` (mediana last_update_days_ago)
- `quality_score` (średnia (word × sources)/max(unverified, 1) znormalizowana 0-10)
- `exhaustion_signal` (średni cache_hits_dedup z 3 ostatnich runów)
- `attention_score` (count flag wymagających reakcji)

## Reguły reakcji

- `findings_kept_ratio < 30%` przez 3 runy → digest sekcja "⚠️ Ratio findings spada" + propozycja zawężenia queries
- `cache_hits_dedup > 90%` → eskalacja Exhaustion handling
- `last_update_days_ago > 14` dla działu → flag "Działy bez świeżego contentu"
- `unverified_claims > 5` w pojedynczym dziale → wymóg consolidation pass z fact-checkiem
- `coverage < 80%` → digest "Brakujące działy" todo
- `attention_score > 5` → digest otwierany "🔴 Health needs attention" zamiast standard TL;DR

## Format `_metrics.md`

3 sekcje od góry do dołu:

**Top — human summary** (czyta user raz w tygodniu):
```markdown
# Health: {slug}
**Status:** 🟢 Healthy / 🟡 Monitor / 🔴 Needs attention
**Last run:** Run #N, YYYY-MM-DD

🟢 Coverage: 9/9 działów (100%)
🟢 Freshness: średnio 2 dni
🟡 Quality: 7.2/10 — `case-studies` ma 5+ unverified claims
🔴 Exhaustion: 87% cache hits w ostatnich 3 runach

## ⚠️ Attention needed
- ...
```

**Mid — tabele per dział** (snapshot najnowszego stanu)

**Bottom — historia run-by-run** (audyt, append-only)

## Progi statusów

| Metryka | 🟢 | 🟡 | 🔴 |
|---------|-----|------|------|
| `coverage` | ≥ 90% | 70-89% | < 70% |
| `freshness` (mediana dni) | ≤ 7 | 8-14 | > 14 |
| `quality_score` | ≥ 7.0 | 4.0-6.9 | < 4.0 |
| `exhaustion_signal` | < 70% | 70-89% | ≥ 90% |
| `attention_score` | 0-2 | 3-5 | > 5 |
