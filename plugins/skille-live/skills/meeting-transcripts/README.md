# meeting-transcripts

Skill do Claude Code, który wyciąga transkrypcje Twoich spotkań (Google Meet / Zoom / Teams) z bazy PostgreSQL. Pytasz asystenta zwykłym zdaniem — „co ustaliliśmy na wczorajszym callu", „wypisz zadania ze spotkania zarządu" — a on czyta transkrypcję i wyciąga konkrety.

## ⚠️ Zanim zaczniesz — to nie jest skill „zainstaluj i działa"

W odróżnieniu od reszty paczki, ten skill to **końcówka większego systemu**. Sam skill tylko *czyta* z bazy — dane musi tam ktoś włożyć. Potrzebujesz trzech rzeczy:

| Element | Do czego | Koszt |
|---------|----------|-------|
| **PostgreSQL** | trzyma transkrypcje | za darmo — [Neon](https://neon.tech) (serverless, 3 min, bez karty) |
| **Recall.ai** | bot dołącza do spotkań i transkrybuje | **płatne** — $5 credits na start, potem wg zużycia |
| **n8n** | spina Recall → baza (gotowy template w repo) | za darmo (self-host) lub plan n8n Cloud |

Jeśli szukasz czegoś darmowego i self-contained — to nie ten skill. Jeśli masz dużo spotkań i chcesz je mieć w zasięgu asystenta — jest wart tej konfiguracji.

## Jak to działa

```
Recall.ai        → bot dołącza do spotkania, po zakończeniu ma transkrypcję
     ↓ (webhook "meeting ended")
n8n workflow     → pobiera transkrypt z Recall.ai i robi INSERT do bazy
     ↓
PostgreSQL       ← skill czyta stąd
     ↓
Claude Code      → "pokaż ostatnie spotkanie", "wyciągnij zadania z wtorku"
```

## Szybki start

Najprościej — powiedz asystentowi: **„skonfiguruj meeting-transcripts"**. Przeprowadzi Cię przez cały setup interaktywnie (zakłada bazę, parsuje connection string, ładuje schemat, ustawia klucze) — patrz [`ONBOARDING.md`](ONBOARDING.md).

Ręcznie, w skrócie:

1. **Baza** — załóż projekt na [Neon](https://neon.tech), skopiuj connection string.
2. **Zmienne** — wpisz do `.env` w workspace:
   ```
   MEETINGS_DB_HOST=ep-xxx.eu-central-1.aws.neon.tech
   MEETINGS_DB_PORT=5432
   MEETINGS_DB_NAME=neondb
   MEETINGS_DB_USER=neondb_owner
   MEETINGS_DB_PASSWORD=twoje_haslo
   ```
3. **Tabela** — załaduj schemat:
   ```bash
   psql "$CONNECTION_STRING" -f scripts/schema.sql
   ```
4. **Pipeline** — zaimportuj [`scripts/n8n-template.json`](scripts/n8n-template.json) do n8n, podłącz swoje credentials (Recall.ai + PostgreSQL), aktywuj i wklej URL webhooka w panelu Recall.ai.
5. **Gotowe** — sprawdź: `python3 scripts/meeting_transcripts.py list`

## Template n8n — co podłączyć po imporcie

Workflow ma 8 nodów (Recall webhook → pobranie bota → transkrypcja → zapis do Postgresa). Po imporcie ustaw:

- **Recall.ai** (nody HTTP) — credential typu *Header Auth* z Twoim kluczem API.
- **PostgreSQL** (node „Zapisz do PostgreSQL") — dane Twojej bazy z `.env`.
- **„Uruchom asystenta AI"** (opcjonalny, ostatni node) — URL ustawiony na placeholder `REPLACE_ME`. To krok, który po zapisie triggeruje asystenta (np. przez webhook Twojego schedulera). Jeśli go nie używasz — usuń node albo zostaw nieaktywny.

## Użycie

```bash
python3 scripts/meeting_transcripts.py list                  # ostatnie spotkania
python3 scripts/meeting_transcripts.py get --days-ago 3      # sprzed 3 dni
python3 scripts/meeting_transcripts.py get --date 2026-07-04 # z konkretnej daty
python3 scripts/meeting_transcripts.py search "automatyzacja"
```

W praktyce nie wpisujesz tego ręcznie — pytasz asystenta („co było na spotkaniu w poniedziałek"), a on dobiera komendę sam.

## Prywatność

Bot Recall.ai nagrywa i transkrybuje spotkania — poinformuj uczestników. Przy rejestracji Recall.ai wybierz **region EU** (dane w UE, RODO). Transkrypcje trzymasz u siebie (Twoja baza), skill niczego nie wysyła na zewnątrz.
