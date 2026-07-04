---
name: meeting-transcripts
description: Wyciąga transkrypcje spotkań z bazy PostgreSQL. Użyj gdy użytkownik pyta o spotkania, rozmowy, co było omawiane, notatki ze spotkań.
allowed-tools: ["Bash", "Read", "Write"]
---

# Meeting Transcripts

Pobiera transkrypcje spotkań (Recall.ai) zapisane w bazie PostgreSQL.

## Wymagania

W `.env` workspace'u:

| Zmienna | Default | Opis |
|---------|---------|------|
| `MEETINGS_DB_HOST` | `localhost` | Host bazy |
| `MEETINGS_DB_PORT` | `5432` | Port |
| `MEETINGS_DB_NAME` | `meetings_db` | Nazwa bazy |
| `MEETINGS_DB_USER` | `meetings` | Użytkownik |
| `MEETINGS_DB_PASSWORD` | — | Hasło (obowiązkowe) |

Biblioteka Python: `psycopg2-binary` (skrypt sam zainstaluje jeśli brak).

**Pierwsza konfiguracja:** jeśli user prosi o "setup", "konfigurację", "onboarding meeting-transcripts" — przeprowadź go przez checklistę z [ONBOARDING.md](ONBOARDING.md).

## Skąd się biorą dane

Skill TYLKO CZYTA z bazy. Wypełnianie tabeli to osobna infrastruktura:

```
Recall.ai (panel)  → bot dołącza do spotkań (Google Meet / Zoom / Teams)
      ↓
n8n workflow       → odbiera event "meeting ended", pobiera transkrypcję z Recall.ai
                     i INSERT do tabeli meeting_transcripts
      ↓
PostgreSQL         ← skill czyta stąd
      ↓
claude-cron        → (opcjonalnie) webhook po zapisie, triggeruje asystenta
```

**Template n8n workflow** — patrz `scripts/n8n-template.json` (import do n8n, dostosuj credentials).

**Baza PostgreSQL** — schema w `scripts/schema.sql`. Najszybszy setup: [Neon](https://neon.tech) (free, serverless, 3 min).

## Lokalizacje plików

- **Skrypt CLI:** `{baseDir}/scripts/meeting_transcripts.py`
- **Schema SQL:** `{baseDir}/scripts/schema.sql`
- **Template n8n:** `{baseDir}/scripts/n8n-template.json`
- **Tabela:** `meeting_transcripts`

## Szybkie użycie

> **Cross-platform Python:** Przed uruchomieniem skryptów ustaw interpreter (na Windows `python3` to stub ze Sklepu Microsoft):
> ```bash
> PYTHON=$(command -v python3 || command -v python)
> ```

```bash
# Lista ostatnich spotkań
$PYTHON {baseDir}/scripts/meeting_transcripts.py list

# Spotkanie z konkretnej daty
$PYTHON {baseDir}/scripts/meeting_transcripts.py get --date 2026-01-12

# Spotkanie sprzed X dni
$PYTHON {baseDir}/scripts/meeting_transcripts.py get --days-ago 3

# Spotkanie po ID
$PYTHON {baseDir}/scripts/meeting_transcripts.py get --id 1

# Szukaj w transkrypcjach
$PYTHON {baseDir}/scripts/meeting_transcripts.py search "live"
```

## Parametry

| Komenda | Opis |
|---------|------|
| `list` | Lista ostatnich spotkań (bez transkrypcji) |
| `get` | Pobierz pełną transkrypcję spotkania |
| `search` | Szukaj frazy w transkrypcjach |

| Parametr | Opis |
|----------|------|
| `--date`, `-d` | Data spotkania (YYYY-MM-DD) |
| `--days-ago` | Ile dni temu (np. 3 = 3 dni temu) |
| `--id` | ID rekordu w bazie |
| `--limit`, `-l` | Limit wyników (domyślnie 10) |
| `--json`, `-j` | Wynik w formacie JSON |

## Struktura tabeli

```
meeting_transcripts:
- id (SERIAL)
- recall_bot_id (UUID)
- meeting_id (VARCHAR)
- platform (VARCHAR) - google_meet, zoom, teams
- title (VARCHAR)
- started_at (TIMESTAMPTZ)
- ended_at (TIMESTAMPTZ)
- transcript (TEXT)
- created_at (TIMESTAMPTZ)
```

## Workflow

1. Użytkownik pyta o spotkanie (np. "co było na spotkaniu 3 dni temu?", "pokaż transkrypcję z wczoraj")
2. Użyj odpowiedniej komendy do pobrania transkrypcji
3. Przetwórz transkrypcję według instrukcji użytkownika (podsumowanie, wyciągnięcie zadań, itp.)

## Interpretacja dat

Gdy użytkownik mówi:
- "wczoraj" → `--days-ago 1`
- "3 dni temu" → `--days-ago 3`
- "w poniedziałek" → oblicz datę i użyj `--date YYYY-MM-DD`
- "ostatnie spotkanie" → `list --limit 1` a potem `get --id X`

## Obsługa błędów

| Błąd | Znaczenie |
|------|-----------|
| `connection refused` / `could not connect` | Baza niedostępna — sprawdź `MEETINGS_DB_HOST`, `MEETINGS_DB_PORT`, firewall, czy baza działa |
| `password authentication failed` | Zły `MEETINGS_DB_USER` lub `MEETINGS_DB_PASSWORD` |
| `database "X" does not exist` | Zła nazwa bazy w `MEETINGS_DB_NAME` |
| `relation "meeting_transcripts" does not exist` | Brak tabeli — uruchom `psql -f scripts/schema.sql` |
| `Nie znaleziono spotkania` | Tabela istnieje, ale brak danych — sprawdź pipeline (Recall.ai + n8n) |
