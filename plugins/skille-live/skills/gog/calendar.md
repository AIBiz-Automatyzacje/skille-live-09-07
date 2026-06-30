# Calendar — gog calendar

## Przeglądanie wydarzeń

```bash
# Lista wydarzeń (domyślnie primary calendar)
gog calendar events --today
gog calendar events --tomorrow
gog calendar events --week
gog calendar events --days 7
gog calendar events --from 2026-01-27 --to 2026-01-31

# Z konkretnego kalendarza
gog calendar events <calendarId> --today

# Ze wszystkich kalendarzy
gog calendar events --all --today

# Szukaj wydarzeń
gog calendar search "spotkanie" --today
gog calendar search "review" --from today --to friday

# Lista kalendarzy (żeby poznać calendarId)
gog calendar calendars

# Sprawdź konflikty
gog calendar conflicts --today
gog calendar conflicts --week
```

## Tworzenie wydarzeń

```bash
# Podstawowe wydarzenie
gog calendar create primary --summary "Spotkanie" --from "2026-01-28T10:00:00" --to "2026-01-28T11:00:00"

# Z opisem i lokalizacją
gog calendar create primary --summary "Review" --from "2026-01-28T14:00:00" --to "2026-01-28T15:00:00" \
  --description "Omówienie sprintu" --location "Sala B"

# Z uczestnikami
gog calendar create primary --summary "Sync" --from "2026-01-28T10:00:00" --to "2026-01-28T10:30:00" \
  --attendees "jan@firma.com,anna@firma.com"

# Z Google Meet
gog calendar create primary --summary "Call" --from "2026-01-28T10:00:00" --to "2026-01-28T10:30:00" --with-meet

# Całodniowe
gog calendar create primary --summary "Urlop" --from "2026-01-28" --to "2026-01-29" --all-day

# Z kolorem
gog calendar create primary --summary "Ważne" --from "2026-01-28T10:00:00" --to "2026-01-28T11:00:00" --event-color 11

# Z przypomnieniem
gog calendar create primary --summary "Deadline" --from "2026-01-28T10:00:00" --to "2026-01-28T11:00:00" \
  --reminder popup:30m --reminder email:1d

# Cykliczne
gog calendar create primary --summary "Standup" --from "2026-01-28T09:00:00" --to "2026-01-28T09:15:00" \
  --rrule "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

# Focus Time
gog calendar focus-time --from "2026-01-28T08:00:00" --to "2026-01-28T12:00:00" --summary "Deep work"

# Out of Office
gog calendar out-of-office --from "2026-02-01" --to "2026-02-03"
```

## Edycja i usuwanie

```bash
# Zaktualizuj wydarzenie
gog calendar update primary <eventId> --summary "Nowy tytuł" --event-color 4

# Zmień czas
gog calendar update primary <eventId> --from "2026-01-28T11:00:00" --to "2026-01-28T12:00:00"

# Dodaj uczestnika (bez nadpisywania istniejących)
gog calendar update primary <eventId> --add-attendee "nowy@firma.com"

# Usuń wydarzenie
gog calendar delete primary <eventId>

# Odpowiedz na zaproszenie
gog calendar respond primary <eventId> --status accepted
gog calendar respond primary <eventId> --status declined
```

## Kolory wydarzeń

ID kolorów (użyj z `--event-color`):

| ID | Kolor | Hex |
|----|-------|-----|
| 1 | Lawenda | #a4bdfc |
| 2 | Szałwia | #7ae7bf |
| 3 | Winogrono | #dbadff |
| 4 | Flamingo | #ff887c |
| 5 | Banan | #fbd75b |
| 6 | Mandarynka | #ffb878 |
| 7 | Paw | #46d6db |
| 8 | Grafit | #e1e1e1 |
| 9 | Borówka | #5484ed |
| 10 | Bazylia | #51b749 |
| 11 | Pomidor | #dc2127 |

Sprawdź aktualne: `gog calendar colors`

## Czas

- Format czasu: RFC3339 (`2026-01-28T10:00:00`) lub relatywny (`today`, `tomorrow`, `monday`)
- Daty bez czasu (`2026-01-28`) dla wydarzeń całodniowych
- `--today`, `--tomorrow`, `--week`, `--days N` jako skróty
