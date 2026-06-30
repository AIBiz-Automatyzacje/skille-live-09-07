---
name: gog
description: >
  Google Workspace CLI for Gmail, Calendar, Drive, Sheets, and Docs.
  Używaj gdy użytkownik chce: wysłać email, sprawdzić kalendarz, przeszukać Gmail,
  zarządzać plikami na Google Drive, czytać lub edytować Google Sheets, eksportować
  Google Docs, tworzyć wydarzenia w kalendarzu, sprawdzić co ma w skrzynce,
  odpowiedzieć na maila, stworzyć draft, przeszukać dysk Google.
allowed-tools: Bash(gog:*)
---

# gog — Google Workspace CLI

Domyślne konto: ustawiane przez env var `GOG_ACCOUNT` (np. `GOG_ACCOUNT="ty@example.com"` w `.env`) lub flagą `--account ty@example.com`.

**Cross-platform detekcja środowiska:** Bash tool działa w non-interactive shell — `.bashrc` może się nie załadować. Przed KAŻDYM wywołaniem `gog` dodaj prefix detekcji:
```bash
GOG_PREFIX=""
case "$(uname -s)" in
  Linux*)
    # Linux native (VPS) lub WSL — gnome-keyring wymaga hasła w non-interactive shell.
    # MUSI być ustawione env var GOG_KEYRING_PASSWORD (np. w .env / userConfig pluginu).
    GOG_PREFIX='export PATH="$HOME/.npm-global/bin:$PATH"; '
    ;;
  Darwin*) ;;       # macOS — Keychain działa per session, prefix pusty
  MINGW*|MSYS*|CYGWIN*) ;;  # Windows (Git Bash/MSYS/Cygwin) — Credential Manager, prefix pusty
esac
eval "${GOG_PREFIX}gog ..."
```

`GOG_KEYRING_PASSWORD` jest natywnie respektowane przez `gog` CLI — wystarczy że istnieje w środowisku, nie trzeba reeksportować w prefixie.

## Globalne flagi

- `--json` — output JSON (do parsowania)
- `--plain` — output TSV (do skryptów)
- `--no-input` — nigdy nie pytaj interaktywnie
- `--force` — pomiń potwierdzenia

## Serwisy

| Serwis | Komenda bazowa | Referencja |
|--------|---------------|------------|
| Gmail | `gog gmail` | [gmail.md](gmail.md) |
| Calendar | `gog calendar` | [calendar.md](calendar.md) |
| Drive + Docs | `gog drive` / `gog docs` | [drive-docs.md](drive-docs.md) |
| Sheets | `gog sheets` | [sheets.md](sheets.md) |

## Zasady

- Potwierdź z użytkownikiem przed wysłaniem maila lub stworzeniem wydarzenia
- Preferuj plain text w mailach, HTML tylko gdy potrzebne formatowanie
- Dla multi-line body używaj `--body-file -` z heredoc
- `gog gmail search` zwraca wątki; `gog gmail messages search` zwraca pojedyncze wiadomości
