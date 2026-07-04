#!/usr/bin/env python3
"""
Meeting Transcripts - pobiera transkrypcje spotkań z bazy PostgreSQL.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Cross-platform: wymuś UTF-8 stdout (Windows cp1250 → UnicodeEncodeError przy emoji/PL)
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import find_workspace, load_env
WORKSPACE = find_workspace(script_path=__file__)
load_env(WORKSPACE)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Brak psycopg2. Instaluję...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2
    from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": os.getenv("MEETINGS_DB_HOST", "localhost"),
    "port": int(os.getenv("MEETINGS_DB_PORT", "5432")),
    "database": os.getenv("MEETINGS_DB_NAME", "meetings_db"),
    "user": os.getenv("MEETINGS_DB_USER", "meetings"),
    "password": os.getenv("MEETINGS_DB_PASSWORD", ""),
    "sslmode": os.getenv("MEETINGS_DB_SSLMODE", "prefer"),
}


def connect():
    """Nawiązuje połączenie z bazą."""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def execute_query(sql: str, params: tuple = None) -> list:
    """Wykonuje zapytanie SQL i zwraca wyniki."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            return []
    finally:
        conn.close()


def format_datetime(dt):
    """Formatuje datetime do czytelnej postaci."""
    if dt is None:
        return "-"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)


def list_meetings(limit: int = 10, as_json: bool = False):
    """Lista ostatnich spotkań."""
    sql = """
        SELECT id, meeting_id, platform, title, started_at, ended_at,
               LENGTH(transcript) as transcript_length
        FROM meeting_transcripts
        ORDER BY started_at DESC
        LIMIT %s
    """
    rows = execute_query(sql, (limit,))

    if as_json:
        return json.dumps([dict(r) for r in rows], indent=2, default=str, ensure_ascii=False)

    if not rows:
        return "Brak spotkań w bazie."

    lines = ["ID | Data       | Czas  | Platform    | Długość transkr.",
             "---+------------+-------+-------------+-----------------"]
    for r in rows:
        date_str = format_datetime(r['started_at'])
        lines.append(f"{r['id']:<2} | {date_str} | {r['platform']:<11} | {r['transcript_length'] or 0} znaków")

    return "\n".join(lines)


def get_meeting(meeting_id: int = None, date: str = None, days_ago: int = None, as_json: bool = False):
    """Pobiera pełną transkrypcję spotkania."""

    if meeting_id:
        sql = "SELECT * FROM meeting_transcripts WHERE id = %s"
        params = (meeting_id,)
    elif date:
        sql = """
            SELECT * FROM meeting_transcripts
            WHERE DATE(started_at) = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        params = (date,)
    elif days_ago is not None:
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        sql = """
            SELECT * FROM meeting_transcripts
            WHERE DATE(started_at) = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        params = (target_date,)
    else:
        # Ostatnie spotkanie
        sql = "SELECT * FROM meeting_transcripts ORDER BY started_at DESC LIMIT 1"
        params = None

    rows = execute_query(sql, params)

    if not rows:
        return "Nie znaleziono spotkania."

    r = rows[0]

    if as_json:
        return json.dumps(dict(r), indent=2, default=str, ensure_ascii=False)

    output = []
    output.append(f"=== Spotkanie #{r['id']} ===")
    output.append(f"Data: {format_datetime(r['started_at'])} - {format_datetime(r['ended_at'])}")
    output.append(f"Platform: {r['platform']}")
    output.append(f"Meeting ID: {r['meeting_id']}")
    if r['title']:
        output.append(f"Tytuł: {r['title']}")
    output.append("")
    output.append("=== Transkrypcja ===")
    output.append(r['transcript'] or "(brak transkrypcji)")

    return "\n".join(output)


def search_meetings(query: str, limit: int = 10, as_json: bool = False):
    """Szuka frazy w transkrypcjach."""
    sql = """
        SELECT id, meeting_id, platform, started_at,
               LENGTH(transcript) as transcript_length,
               SUBSTRING(transcript FROM POSITION(LOWER(%s) IN LOWER(transcript)) FOR 200) as context
        FROM meeting_transcripts
        WHERE LOWER(transcript) LIKE LOWER(%s)
        ORDER BY started_at DESC
        LIMIT %s
    """
    search_pattern = f"%{query}%"
    rows = execute_query(sql, (query, search_pattern, limit))

    if as_json:
        return json.dumps([dict(r) for r in rows], indent=2, default=str, ensure_ascii=False)

    if not rows:
        return f"Nie znaleziono '{query}' w transkrypcjach."

    lines = [f"Znaleziono {len(rows)} spotkań z frazą '{query}':", ""]
    for r in rows:
        lines.append(f"#{r['id']} | {format_datetime(r['started_at'])} | {r['platform']}")
        if r['context']:
            lines.append(f"   ...{r['context'][:150]}...")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Meeting Transcripts - pobieranie transkrypcji spotkań",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python3 meeting_transcripts.py list
  python3 meeting_transcripts.py get --date 2026-01-12
  python3 meeting_transcripts.py get --days-ago 3
  python3 meeting_transcripts.py get --id 1
  python3 meeting_transcripts.py search "live"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Dostępne komendy")

    # list
    list_parser = subparsers.add_parser("list", help="Lista ostatnich spotkań")
    list_parser.add_argument("--limit", "-l", type=int, default=10, help="Limit wyników")
    list_parser.add_argument("--json", "-j", action="store_true", help="Wynik jako JSON")

    # get
    get_parser = subparsers.add_parser("get", help="Pobierz transkrypcję spotkania")
    get_parser.add_argument("--id", type=int, help="ID spotkania w bazie")
    get_parser.add_argument("--date", "-d", help="Data spotkania (YYYY-MM-DD)")
    get_parser.add_argument("--days-ago", type=int, help="Ile dni temu")
    get_parser.add_argument("--json", "-j", action="store_true", help="Wynik jako JSON")

    # search
    search_parser = subparsers.add_parser("search", help="Szukaj w transkrypcjach")
    search_parser.add_argument("query", help="Fraza do wyszukania")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Limit wyników")
    search_parser.add_argument("--json", "-j", action="store_true", help="Wynik jako JSON")

    args = parser.parse_args()

    if args.command == "list":
        print(list_meetings(args.limit, args.json))
    elif args.command == "get":
        print(get_meeting(args.id, args.date, args.days_ago, args.json))
    elif args.command == "search":
        print(search_meetings(args.query, args.limit, args.json))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
