# Digest — style guide (OBOWIĄZKOWY)

Digest czyta CZŁOWIEK rano przy kawie, nie security researcher.

## Zasady

- **Polski język domyślnie.** Każdy angielski termin → tłumacz w nawiasie.
  - `arbitrary code execution` → "uruchomienie dowolnego kodu (czyli ktoś może wykonać cokolwiek na Twojej maszynie)"
  - `prompt injection` → "wstrzyknięcie polecenia do AI"
  - `RCE` / `CVSS 9.9` / `RLS` — ZAWSZE z tłumaczeniem przy pierwszym wystąpieniu
- **Każdy bullet zaczyna się od ludzkiego zdania**, nie od listy terminów.
- **Każdy hot finding KOŃCZY się jednym zdaniem "co to znaczy dla mnie"** — czemu Cię to dotyczy.
- **Liczby zostają.** Tłumaczymy CO znaczą.
- **Pełne zdania, nie telegram.**
- **Bez korpo-żargonu.**
- **Test 5 sekund.** Po przeczytaniu bullet point user wie czemu go to dotyczy.

**WAŻNE — linkowanie działów.** Każde wystąpienie nazwy działu w digest ZAWSZE jako wikilink `[[wiki/{nazwa-dzialu}]]`. User otwiera digest w Obsidianie, klika i przeskakuje do działu.

## Template digest

```markdown
# Daily Digest {date} — {slug}

**Run #{N}** | **Sources:** {yt} yt + {reddit} reddit + {web} web + {x} x | **New:** {} | **Noise filtered:** {}

## 🔥 Hot ({N})

### {Topic title po polsku}
- Źródła: [YT {views}](url), [Reddit {upvotes}↑ {comments}c](url), [X @{user} {engagement}](url)
- **Dlaczego hot:** [pełne zdania, czemu to ważne, co konkretnego, jakie liczby]
- **Co to znaczy dla mnie:** [jedno zdanie — w czym to się zmienia w MOJEJ pracy/decyzjach]
- **Action:** wplecione w [[wiki/dzial-X]] (rozszerzone o przykład Y), dorzucone do [[wiki/dzial-Z]] (counter +1)

## 💡 New angle ({N})
- {Topic} — {1-2 zdania kontekstu}, dorzucone do [[wiki/dzial]]. Dopisane do `emerging_queries` w `_topic.md`.

## 🔁 Repeat of known ({N}, counter updates)
- "{Pattern X}" w [[wiki/dzial]] — +N (teraz {total} wzmianek)

## ❌ Noise filtered ({total})
- {category 1}: {N}
- {category 2}: {N}

## ⚠️ Attention needed
- [warningi z agent quality_flags + master observations]

## Metryki
| Metryka | Wartość |
|---------|---------|
| findings_total | {} |
| findings_kept_ratio | {%} {🟢/🟡/🔴 jeśli próg trafia} |
| cache_hits_dedup | {%} |
| sections_updated | {} |

---
*Run #{N} zakończony {time}. Następny: {cron schedule albo manual}.*
```
