---
name: himalaya
description: Zarządzanie emailem z terminala. Użyj gdy user prosi o sprawdzenie maili, przeczytanie wiadomości, wysłanie maila, odpowiedź na email, przeszukanie skrzynki.
allowed-tools: ["Bash"]
---

# Himalaya Email CLI

Himalaya to CLI do zarządzania emailami przez IMAP/SMTP.

## References

- `references/configuration.md` - konfiguracja konta, IMAP/SMTP
- `references/message-composition.md` - MML syntax do komponowania maili

## Podstawowe operacje

### Lista folderów

```bash
himalaya folder list
```

### Lista maili

INBOX (domyślny):
```bash
himalaya envelope list
```

Konkretny folder:
```bash
himalaya envelope list --folder "Sent"
```

Z paginacją:
```bash
himalaya envelope list --page 1 --page-size 20
```

### Szukanie maili

```bash
himalaya envelope list from john@example.com subject meeting
```

### Czytanie maila

```bash
himalaya message read 42
```

Raw MIME:
```bash
himalaya message export 42 --full
```

### Odpowiedź

```bash
himalaya message reply 42
```

Reply-all:
```bash
himalaya message reply 42 --all
```

### Forward

```bash
himalaya message forward 42
```

### Nowy mail

Interaktywnie (otwiera $EDITOR):
```bash
himalaya message write
```

Bezpośrednio:
```bash
himalaya message write -H "To:recipient@example.com" -H "Subject:Test" "Treść wiadomości"
```

Lub przez template:
```bash
cat << 'EOF' | himalaya template send
From: you@example.com
To: recipient@example.com
Subject: Test Message

Hello from Himalaya!
EOF
```

### Przenoszenie/kopiowanie

```bash
himalaya message move 42 "Archive"
himalaya message copy 42 "Important"
```

### Usuwanie

```bash
himalaya message delete 42
```

### Flagi

```bash
himalaya flag add 42 --flag seen
himalaya flag remove 42 --flag seen
```

## Wiele kont

Lista kont:
```bash
himalaya account list
```

Użyj konkretnego:
```bash
himalaya --account work envelope list
```

## Załączniki

Pobierz:
```bash
himalaya attachment download 42
```

Do konkretnego folderu:
```bash
himalaya attachment download 42 --dir ~/Downloads
```

## Output

```bash
himalaya envelope list --output json
himalaya envelope list --output plain
```

## Debug

```bash
RUST_LOG=debug himalaya envelope list
RUST_LOG=trace RUST_BACKTRACE=1 himalaya envelope list
```