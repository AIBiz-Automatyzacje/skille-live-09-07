# Gmail — gog gmail

## Szukanie

```bash
# Szukaj wątków (grupuje po konwersacji)
gog gmail search 'newer_than:7d' --max 10

# Szukaj pojedynczych wiadomości (każdy email osobno)
gog gmail messages search "in:inbox from:ryanair.com" --max 20

# Popularne query Gmail:
# newer_than:7d, older_than:30d, from:x, to:x, subject:x
# in:inbox, in:sent, is:unread, has:attachment, label:nazwa
```

## Czytanie

```bash
# Pobierz wiadomość (full content)
gog gmail get <messageId>

# Pobierz tylko nagłówki
gog gmail get <messageId> --format metadata

# Pobierz cały wątek z załącznikami
gog gmail thread get <threadId>

# Lista załączników w wątku
gog gmail thread attachments <threadId>

# Pobierz załącznik
gog gmail attachment <messageId> <attachmentId>
```

## Wysyłanie

```bash
# Prosty email
gog gmail send --to a@b.com --subject "Temat" --body "Treść"

# Multi-line (heredoc przez stdin)
gog gmail send --to a@b.com --subject "Temat" --body-file - <<'EOF'
Cześć,

Treść wiadomości.

Pozdrawiam
EOF

# Z pliku
gog gmail send --to a@b.com --subject "Temat" --body-file ./message.txt

# HTML
gog gmail send --to a@b.com --subject "Temat" --body-html "<p>Hello</p><ul><li>punkt</li></ul>"

# Z załącznikiem
gog gmail send --to a@b.com --subject "Temat" --body "Treść" --attach ./plik.pdf

# CC/BCC
gog gmail send --to a@b.com --cc c@d.com --bcc e@f.com --subject "Temat" --body "Treść"
```

## Odpowiadanie

```bash
# Odpowiedź na konkretną wiadomość
gog gmail send --to a@b.com --subject "Re: Temat" --body "Odpowiedź" --reply-to-message-id <msgId>

# Odpowiedź w wątku (pobiera nagłówki z ostatniej wiadomości)
gog gmail send --subject "Re: Temat" --body "Odpowiedź" --thread-id <threadId> --reply-all
```

## Drafty

```bash
# Stwórz draft
gog gmail drafts create --to a@b.com --subject "Temat" --body-file ./message.txt

# Lista draftów
gog gmail drafts list

# Wyślij draft
gog gmail drafts send <draftId>

# Zaktualizuj draft
gog gmail drafts update <draftId> --subject "Nowy temat"

# Usuń draft
gog gmail drafts delete <draftId>
```

## Etykiety

```bash
# Lista etykiet
gog gmail labels list

# Szczegóły etykiety (z liczbą wiadomości)
gog gmail labels get <labelIdOrName>

# Stwórz etykietę
gog gmail labels create "Nazwa"

# Dodaj/usuń etykiety z wątków
gog gmail labels modify <threadId> --add "LABEL_ID" --remove "LABEL_ID"
```

## Formatowanie emaili

- `--body` nie interpretuje `\n`. Dla nowych linii użyj heredoc lub `$'Linia 1\n\nLinia 2'`
- `--body-file -` (stdin) to najwygodniejszy sposób na multi-line
- HTML tagi: `<p>`, `<br>`, `<strong>`, `<em>`, `<a href="">`, `<ul>/<li>`
- Ten sam wzorzec `--body-file` działa w send, drafts create i reply
