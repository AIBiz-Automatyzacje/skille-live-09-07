---
name: youtube-transcript
description: Pobiera transkrypcję z YouTube i tworzy podsumowanie. Użyj gdy użytkownik chce zapisać wideo z YouTube, pobrać transkrypcję, zarchiwizować materiał, lub zrobić notatki z filmu.
allowed-tools: ["Bash", "Read", "Write"]
---

# YouTube Transcript

Pobiera transkrypcję z YouTube i generuje podsumowanie w Obsidianie.

## Lokalizacje

- **Skrypt:** `{baseDir}/scripts/youtube_transcript.py`
- **Notatki:** `Zasoby/Research/YouTube/[slug-tytulu]/`

## Workflow

> **Cross-platform Python:** Przed uruchomieniem skryptów ustaw interpreter (na Windows `python3` to stub ze Sklepu Microsoft):
> ```bash
> PYTHON=$(command -v python3 || command -v python)
> ```

1. Pobierz URL YouTube od użytkownika
2. Uruchom skrypt:
   ```bash
   $PYTHON {baseDir}/scripts/youtube_transcript.py <URL>
   ```
3. Skrypt tworzy folder z `transkrypcja.md` i `.meta.json`
4. Wczytaj `transkrypcja.md` z utworzonego folderu
5. Wygeneruj `podsumowanie.md` według formatu poniżej
6. Zapisz podsumowanie w tym samym folderze
7. Potwierdź użytkownikowi lokalizację plików

## Format podsumowania

```markdown
# [Tytuł wideo]

> **Kanał:** [nazwa] | **Data:** [data] | **Czas:** [długość]
> [Link do wideo]

## TL;DR
[2-3 zdania - główna teza filmu]

## Kluczowe punkty
- punkt 1
- punkt 2
- ... (5-10 punktów, krótkie)

## Cytaty warte zapamiętania
> "cytat 1"
> "cytat 2"
(2-3 cytaty)

## Notatki własne
[puste - do uzupełnienia ręcznie]
```

## Generowanie podsumowania

Po pobraniu transkrypcji:
1. Przeczytaj całą transkrypcję
2. Zidentyfikuj główną tezę (TL;DR)
3. Wyciągnij 5-10 kluczowych punktów - konkretne, actionable
4. Wybierz 2-3 najciekawsze cytaty dosłownie z transkrypcji
5. Zapisz do `podsumowanie.md`

## Wymagania

- Python 3.x
- Pakiety: `requests`, `python-dotenv`
- API key Apify w `.env` jako `APIFY_API_KEY`
