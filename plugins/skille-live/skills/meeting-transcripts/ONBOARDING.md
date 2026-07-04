# Onboarding — meeting-transcripts

Instrukcja dla Claude'a: przeprowadź użytkownika **INTERAKTYWNIE** przez pełny setup skilla + infrastruktury (PostgreSQL/Neon + Recall.ai + n8n).

**Wywołanie:** user mówi "skonfiguruj meeting-transcripts" / "onboarding meeting-transcripts" / "setup meeting-transcripts".

## Zasady pracy — WAŻNE

1. **Tryb interaktywny** — Ty prowadzisz, user podaje wartości. Ty:
   - Parsujesz wklejone connection stringi / klucze
   - Waliduje format
   - Zapisuje do `.env` sam (nie każesz userowi kopiować ręcznie)
   - Uruchamiasz komendy (psql, test połączenia) sam
2. **Idempotentność** — każdy krok sprawdza stan na żywo. Zrobione → ✅ skip.
3. **Jeden krok na raz** — nie zasypuj usera 10 pytaniami. Pytanie → odpowiedź → akcja → feedback → następne pytanie.
4. **Feedback po każdej akcji** — "zapisałem X do .env", "schema załadowana, 3 tabele utworzone", itd.
5. **Bez realnych calli do płatnych API** — test połączenia DB = OK (Neon free). Kluczy Recall.ai / OpenAI nie weryfikuj calli-em.
6. **Nie wypisuj sekretów na ekran** — jak user wkleił klucz, potwierdź "zapisałem RECALL_API_KEY (24 znaki)" ale nie echo'uj wartości.

## Mapa kroków

```
1. Python 3
2. psycopg2
3. Plik .env
4. Baza PostgreSQL
   4a. Dialog: "masz bazę?" [tak / nie]
   4b. Nie → setup Neon (interaktywny)
   4c. Tak → podaj connection string lub 5 osobnych zmiennych
5. Zmienne MEETINGS_DB_* w .env (sprawdzenie + ewentualnie wpisanie przez Ciebie)
6. Tabela meeting_transcripts
   6a. Check czy istnieje
   6b. Nie → załaduj schema.sql automatycznie
7. Pipeline (Recall.ai + n8n)
   7a. Dialog: "masz skonfigurowany?" [tak / nie / zrobię później]
   7b. Recall.ai — podaj API key (zapisz w .env)
   7c. n8n — pokaż template + lista credentials do ustawienia
8. Test końcowy (list z bazy)
9. Podsumowanie
```

---

## Krok 1 — Python 3

**Check:**
```bash
python3 --version
```

- ≥ 3.8 → ✅ "Python OK: {wersja}" → dalej
- brak / starsza → instrukcja instalacji:
  - Mac: `brew install python3`
  - Windows: python.org (zaznacz "Add to PATH")
  - Linux: `sudo apt install python3`
  - Po instalacji: "restartnij terminal i napisz 'gotowe'"

---

## Krok 2 — psycopg2

**Check:**
```bash
python3 -c "import psycopg2; print(psycopg2.__version__)"
```

- Działa → ✅ dalej
- `ModuleNotFoundError` → "Instaluję `psycopg2-binary`... [y/N]?"
  - y → `pip3 install psycopg2-binary` (pokaż output)
  - N → "Skrypt ma auto-install, zainstaluje się przy pierwszym użyciu"

---

## Krok 3 — Plik .env

**Check:**
```bash
test -f .env && echo "EXISTS" || echo "MISSING"
```

- Istnieje → ✅ dalej
- Brak → `touch .env` i poinformuj: "Utworzyłem pusty .env w {ścieżka}"

---

## Krok 4 — Baza PostgreSQL

### 4a. Dialog początkowy

Zapytaj:
```
Potrzebujesz PostgreSQL z tabelą meeting_transcripts. Jak wygląda sytuacja?

1. Mam już bazę (np. moja VPS, Supabase, lokalnie)
2. Nie mam - postaw mi na Neon (free, 3 min, zero karty)
3. Nie wiem / pokaż opcje

Napisz 1, 2 albo 3.
```

### 4b. User wybrał 2 (Neon) — setup interaktywny

Wyświetl KROK PO KROKU (nie wszystko na raz):

**Krok 4b.1:**
```
Zakładamy konto na Neon.

1. Otwórz https://neon.tech
2. Kliknij "Sign up" → preferuj GitHub (najszybciej)
3. Po zalogowaniu: klik "Create a project"
4. Ustaw:
   - Project name: meetings (albo co chcesz)
   - Postgres version: zostaw domyślną (17)
   - Region: Europe (Frankfurt)  ← dla Polski
5. Klik "Create project"

Jesteś na ekranie z "Connection Details"? Napisz "tak" jak tam dojdziesz.
```

**Krok 4b.2:**
```
Zobaczysz box "Connection string" z czymś jak:

postgresql://neondb_owner:AbCdEf123@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require

Skopiuj CAŁY string i wklej tu w chacie.
(nie martw się o hasło — za chwilę zapiszę do .env i nie wrócę do niego)
```

**Krok 4b.3 — user wkleił connection string:**
Parsuj go (regex: `postgresql://(.+?):(.+?)@(.+?):?(\d+)?/(.+?)(\?.*)?$`):
- user → `MEETINGS_DB_USER`
- password → `MEETINGS_DB_PASSWORD`
- host → `MEETINGS_DB_HOST`
- port → `MEETINGS_DB_PORT` (default 5432 jeśli brak)
- database → `MEETINGS_DB_NAME` (bez `?sslmode=require`)

Zapisz do `.env` używając `sed` lub Write (jeśli zmiennych brak → append). Po każdym:
```
✅ Zapisałem 5 zmiennych MEETINGS_DB_* do .env
   Host: ep-xxx.eu-central-1.aws.neon.tech
   Database: neondb
   User: neondb_owner
   Password: *** (ukryte)
   Port: 5432
```

Poinformuj o pułapce Neon:
```
ℹ️ Uwaga: Neon free tier pauzuje bazę po ~5 min nieaktywności.
   Pierwsze query po pauzie = 1-2s opóźnienia. Niekrytyczne.
```

Przejdź do kroku 5 (pominięty, bo już zapisałeś) → bezpośrednio krok 6.

### 4c. User wybrał 1 (mam bazę) — zbierz dane

Zapytaj:
```
OK. Masz connection string (np. z Supabase, Railway) czy wolisz podać 5 wartości osobno?

A - wklej connection string
B - podam osobno host/user/password/etc
```

- A → jak w kroku 4b.3 (parsuj string → zapisz do `.env`)
- B → pytaj po kolei (jedno na raz):
  ```
  Host bazy (np. 123.45.67.89 albo db.example.com):
  ```
  → zapisz do `.env` → pytaj o port, potem database, user, password

Po zebraniu wszystkich → confirmation:
```
✅ Zapisałem 5 zmiennych MEETINGS_DB_* do .env
```

### 4d. User wybrał 3 (pokaż opcje)

Wyświetl:
```
Masz 4 opcje:

1. Neon (neon.tech) — SERVERLESS, free tier, bez karty, pauzuje po 5min
2. Supabase (supabase.com) — free tier, bardziej rozbudowany
3. Railway (railway.app) — $5/mies, bez pauzy
4. Lokalny Postgres w Docker — darmowy, ale musisz mieć Docker

Dla onboardingu proponuję Neon (2 min setupu). OK? [Neon / inne]
```

Jak Neon → kontynuuj 4b.
Jak inne → "OK, załóż konto i wróć z connection stringiem" → po powrocie 4c.

---

## Krok 5 — Weryfikacja zmiennych .env

**Check:**
```bash
for v in MEETINGS_DB_HOST MEETINGS_DB_PORT MEETINGS_DB_NAME MEETINGS_DB_USER MEETINGS_DB_PASSWORD; do
    grep -q "^$v=" .env && echo "$v: SET" || echo "$v: MISSING"
done
```

- Wszystkie SET → ✅ dalej
- Coś MISSING → poinformuj "brakuje X, Y" → wróć do kroku 4

---

## Krok 6 — Tabela `meeting_transcripts`

### 6a. Check czy istnieje

```bash
python3 -c "
import sys, os
sys.path.insert(0, '.claude/skills/meeting-transcripts/scripts')
from env_loader import find_workspace, load_env
load_env(find_workspace())
import psycopg2
conn = psycopg2.connect(
    host=os.getenv('MEETINGS_DB_HOST'),
    port=int(os.getenv('MEETINGS_DB_PORT', '5432')),
    database=os.getenv('MEETINGS_DB_NAME'),
    user=os.getenv('MEETINGS_DB_USER'),
    password=os.getenv('MEETINGS_DB_PASSWORD'),
    sslmode='require'  # Neon wymaga
)
cur = conn.cursor()
cur.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'meeting_transcripts')\")
print('EXISTS' if cur.fetchone()[0] else 'MISSING')
conn.close()
" 2>&1
```

**Wyniki:**

- `EXISTS` → ✅ "Tabela istnieje" → krok 7
- `MISSING` → przejdź do 6b
- `connection refused` / `SSL required` / inny błąd → diagnostyka:
  - SSL → sprawdź czy host to Neon/cloud (wymaga SSL)
  - refused → sprawdź host/port/firewall
  - password failed → `MEETINGS_DB_USER` lub `MEETINGS_DB_PASSWORD` źle

### 6b. Tabela nie istnieje — załaduj schema AUTOMATYCZNIE

Nie pytaj — po prostu zrób (za zgodą usera raz):
```
Tabela nie istnieje. Ładuję schema (scripts/schema.sql)... [y/N]
```

Po y:
```bash
PGPASSWORD="$MEETINGS_DB_PASSWORD" psql \
  "sslmode=require host=$MEETINGS_DB_HOST port=$MEETINGS_DB_PORT dbname=$MEETINGS_DB_NAME user=$MEETINGS_DB_USER" \
  -f .claude/skills/meeting-transcripts/scripts/schema.sql
```

(jak `psql` brak → `brew install postgresql` albo `sudo apt install postgresql-client`)

Output:
```
✅ CREATE TABLE meeting_transcripts
✅ CREATE INDEX idx_meeting_started_at
✅ CREATE INDEX idx_meeting_meeting_id
```

---

## Krok 7 — Pipeline (Recall.ai + n8n)

### 7a. Dialog początkowy

```
Skill już CZYTA z bazy. Teraz potrzebujesz PIPELINE'u który wrzuca dane.

Dwa komponenty:
- Recall.ai → bot dołącza do spotkań + dostarcza transkrypcję
- n8n → odbiera event "meeting ended", zapisuje do bazy

Masz już to skonfigurowane?

1. Tak, pipeline działa → lecimy do testu
2. Nie, pomóż mi teraz
3. Zrobię później (skill będzie działał, ale baza pusta)

[1/2/3]
```

- 1 → krok 8 (test)
- 2 → krok 7b (Recall) + 7c (n8n)
- 3 → krok 9 (podsumowanie z ostrzeżeniem "baza pusta")

### 7b. Recall.ai

```
Recall.ai setup:

1. Wejdź na https://recall.ai → Sign up
   ⚠️ WAŻNE: przy rejestracji wybierz region EU
   (przechowywanie danych w UE, GDPR)

2. Po zalogowaniu dostajesz $5 credits na start (new accounts).
   Potwierdź że je widzisz w Billing → Credits.

3. Dashboard → API Keys → Create new key → skopiuj.

4. Wklej klucz tutaj w chacie (zapiszę do .env).
```

Po wklejeniu klucza:
- Waliduj format (Recall.ai używa format typu `rcl_xxx...`)
- Zapisz do `.env` jako `RECALL_API_KEY=<wartość>`
- Confirm:
  ```
  ✅ Zapisałem RECALL_API_KEY do .env ({N} znaków)
  ```

**Uwaga:** szczegółowy tutorial Recall.ai — patrz `Zasoby/Tech/recall-ai-onboarding.md` (notatki z setupu).

### 7c. n8n workflow

```
n8n workflow — import template:

1. Otwórz swoją instancję n8n
2. Workflows → Import from File
3. Wybierz: .claude/skills/meeting-transcripts/scripts/n8n-template.json
4. Ustaw credentials:
   - "Recall.ai webhook" → twój Recall API key (z kroku 7b)
   - "PostgreSQL" → dane bazy (host/user/pass/db z .env)

5. Activate workflow (toggle top-right)

6. Skopiuj URL webhooka (Webhook node → URL) i wklej w panelu Recall.ai
   (Recall → Webhooks → Add → wklej URL n8n)

Gotowe? Napisz "gotowe" albo "pomóż".
```

Po "gotowe" → krok 8.

⚠️ Jeśli brak pliku `scripts/n8n-template.json` — poinformuj:
```
Template n8n jeszcze nie jest dorzucony do skilla. Musisz zbudować workflow ręcznie:
- Trigger: Webhook (POST)
- Node 1: HTTP Request → Recall.ai API /bot/{id}/transcript
- Node 2: PostgreSQL → INSERT do meeting_transcripts

Docelowo template będzie w scripts/n8n-template.json.
```

---

## Krok 8 — Test końcowy

Uruchom:
```bash
python3 .claude/skills/meeting-transcripts/scripts/meeting_transcripts.py list
```

**Interpretacja wyników:**

- Wyświetliła się tabela ze spotkaniami → ✅ "Pełny setup działa, {N} rekordów w bazie"
- "Brak spotkań w bazie" → ✅ "Skill działa technicznie, ale tabela pusta — czekasz na pierwsze spotkanie z bota Recall.ai"
- Błąd połączenia → wróć do diagnostyki z kroku 6a

---

## Krok 9 — Podsumowanie

```
✅ meeting-transcripts — setup ukończony

Status:
- Python {wersja} + psycopg2 ✅
- Baza: {host} / {database} ✅
- Tabela meeting_transcripts ✅
- Rekordy w bazie: {N}
- Recall.ai API key: {skonfigurowany / TODO}
- n8n workflow: {aktywny / TODO}

Użycie:
  "pokaż ostatnie spotkanie"
  "co było na spotkaniu 3 dni temu"
  "szukaj 'automatyzacja' w transkrypcjach"

{JEŚLI Recall/n8n TODO:}
⚠️ Pipeline jeszcze nie leci — dokończ krok 7 gdy będziesz mógł.
   Skill działa, ale będzie zwracał puste wyniki.

{JEŚLI wszystko gotowe:}
🚀 Gotowe. Dodaj bota Recall do swojego następnego spotkania i sprawdź czy zapisał.
```

---

## Helper: parsowanie connection stringa PostgreSQL

Dla `postgresql://USER:PASSWORD@HOST:PORT/DATABASE?params`:

```python
import re
m = re.match(r'postgresql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)', connection_string)
user, password, host, port, database = m.group(1), m.group(2), m.group(3), m.group(4) or '5432', m.group(5)
```

URL-decode password jeśli zawiera znaki specjalne.

## Helper: update/append zmiennej w .env

```bash
# Jeśli zmienna istnieje — replace, jak nie — append
if grep -q "^MEETINGS_DB_HOST=" .env; then
    sed -i '' "s|^MEETINGS_DB_HOST=.*|MEETINGS_DB_HOST=$VALUE|" .env
else
    echo "MEETINGS_DB_HOST=$VALUE" >> .env
fi
```

(na Linux `sed -i` bez `''`, na macOS `sed -i ''`)

## Obsługa błędów

- **`psql: command not found`** → `brew install postgresql` / `apt install postgresql-client`
- **Connection timeout** → firewall hostingu (dla Neon sprawdź IP whitelist — domyślnie all)
- **SSL handshake failed** → dodać `sslmode=require` w connection
- **User wkleja niepełny connection string** → poproś o pełny (od `postgresql://` do końca)
- **User wkleja klucz z cudzysłowami/spacjami** → trim i strip przed zapisem

## Czego NIE robić

- ❌ Nie każ userowi ręcznie edytować `.env` — sam parsuj i zapisuj
- ❌ Nie zasypuj user'a 10 pytaniami na raz — krok po kroku
- ❌ Nie wypisuj kluczy/haseł na ekran po zapisaniu
- ❌ Nie weryfikuj kluczy Recall.ai realnym callem do API (to płatne)
- ❌ Nie modyfikuj `meeting_transcripts.py` ani `env_loader.py`
- ❌ Nie próbuj ręcznie wrzucać testowych danych do bazy
