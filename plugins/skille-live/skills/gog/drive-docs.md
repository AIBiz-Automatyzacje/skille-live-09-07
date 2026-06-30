# Drive & Docs — gog drive / gog docs

## Drive — przeglądanie

```bash
# Lista plików (root)
gog drive ls

# Lista plików w folderze
gog drive ls --parent <folderId>

# Szukaj pełnotekstowo
gog drive search "raport kwartalny" --max 10

# Metadane pliku
gog drive get <fileId>

# URL do pliku
gog drive url <fileId>
```

## Drive — operacje na plikach

```bash
# Upload
gog drive upload ./raport.pdf
gog drive upload ./raport.pdf --parent <folderId> --name "Raport Q1.pdf"

# Download (automatycznie eksportuje Google Docs formats)
gog drive download <fileId>
gog drive download <fileId> --out ./raport.pdf
gog drive download <fileId> --format pdf

# Kopiuj
gog drive copy <fileId> "Kopia dokumentu"

# Stwórz folder
gog drive mkdir "Nowy folder"
gog drive mkdir "Podfolder" --parent <folderId>

# Przenieś plik do folderu
gog drive move <fileId> --parent <folderId>

# Zmień nazwę
gog drive rename <fileId> "Nowa nazwa"

# Usuń (do kosza)
gog drive delete <fileId>
```

## Drive — uprawnienia

```bash
# Lista uprawnień
gog drive permissions <fileId>

# Udostępnij
gog drive share <fileId> --email user@example.com --role writer
gog drive share <fileId> --email user@example.com --role reader

# Usuń uprawnienie
gog drive unshare <fileId> <permissionId>
```

## Drive — komentarze

```bash
# Lista komentarzy
gog drive comments list <fileId>

# Dodaj komentarz
gog drive comments create <fileId> --content "Komentarz do pliku"
```

## Docs — czytanie

```bash
# Wyświetl treść dokumentu jako tekst
gog docs cat <docId>

# Metadane dokumentu
gog docs info <docId>
```

## Docs — eksport

```bash
# Eksportuj jako PDF
gog docs export <docId> --format pdf --out ./dokument.pdf

# Eksportuj jako tekst
gog docs export <docId> --format txt --out ./dokument.txt

# Eksportuj jako docx
gog docs export <docId> --format docx --out ./dokument.docx
```

## Docs — tworzenie

```bash
# Stwórz nowy dokument
gog docs create "Tytuł dokumentu"
gog docs create "Tytuł" --parent <folderId>

# Kopiuj dokument
gog docs copy <docId> "Kopia dokumentu"
```

## Uwagi

- `gog docs` nie obsługuje edycji treści in-place (wymagałoby Docs API)
- Do pobrania Google Docs/Sheets/Slides użyj `gog drive download` z `--format`
- Formaty eksportu Drive: pdf, csv, xlsx, pptx, txt, png, docx
