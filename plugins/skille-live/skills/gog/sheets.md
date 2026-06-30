# Sheets — gog sheets

## Czytanie danych

```bash
# Pobierz zakres
gog sheets get <spreadsheetId> "Sheet1!A1:D10"

# JSON output (do parsowania)
gog sheets get <spreadsheetId> "Sheet1!A1:D10" --json

# Surowe wartości (bez formatowania)
gog sheets get <spreadsheetId> "Sheet1!A1:D10" --render UNFORMATTED_VALUE

# Formuły zamiast wartości
gog sheets get <spreadsheetId> "Sheet1!A1:D10" --render FORMULA

# Metadane arkusza (nazwy zakładek, wymiary)
gog sheets metadata <spreadsheetId> --json
```

## Zapisywanie danych

```bash
# Zaktualizuj zakres (JSON — rekomendowane)
gog sheets update <spreadsheetId> "Sheet1!A1:B2" --values-json '[["Imię","Email"],["Jan","jan@x.com"]]' --input USER_ENTERED

# Dopisz wiersz na końcu
gog sheets append <spreadsheetId> "Sheet1!A:C" --values-json '[["nowy","wiersz","danych"]]' --insert INSERT_ROWS

# Dopisz wiele wierszy
gog sheets append <spreadsheetId> "Sheet1!A:C" --values-json '[["a","b","c"],["d","e","f"]]' --insert INSERT_ROWS

# Wyczyść zakres
gog sheets clear <spreadsheetId> "Sheet1!A2:Z"
```

## Tworzenie i kopiowanie

```bash
# Nowy arkusz
gog sheets create "Raport Q1"

# Nowy arkusz z nazwanymi zakładkami
gog sheets create "Raport Q1" --sheets "Dane,Podsumowanie,Wykresy"

# Kopiuj istniejący
gog sheets copy <spreadsheetId> "Kopia raportu"
```

## Formatowanie

```bash
# Pogrubienie nagłówków
gog sheets format <spreadsheetId> "Sheet1!A1:D1" \
  --format-json '{"textFormat":{"bold":true}}' \
  --format-fields "textFormat.bold"

# Kolor tła
gog sheets format <spreadsheetId> "Sheet1!A1:D1" \
  --format-json '{"backgroundColor":{"red":0.9,"green":0.9,"blue":1.0}}' \
  --format-fields "backgroundColor"
```

## Eksport

```bash
# Eksport do xlsx
gog sheets export <spreadsheetId> --format xlsx --out ./raport.xlsx

# Eksport do CSV
gog sheets export <spreadsheetId> --format csv --out ./dane.csv

# Eksport do PDF
gog sheets export <spreadsheetId> --format pdf --out ./raport.pdf
```

## Wzorce użycia

- `--values-json` to rekomendowany sposób podawania danych (zamiast inline pipe-separated)
- `--input USER_ENTERED` — Google interpretuje wartości (daty, liczby, formuły)
- `--input RAW` — wartości traktowane jako tekst
- Range format: `NazwaZakładki!A1:D10` (zakładka z spacjami: `'Moja Zakładka'!A1:D10`)
- `--copy-validation-from` kopiuje walidację z istniejących komórek do nowych
