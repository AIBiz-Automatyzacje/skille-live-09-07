#!/usr/bin/env python3
"""Orkiestracja /meta-daily — ETAP 1: PULL → STORE.

Pobiera snapshot z Meta API i dokłada do meta-ads.db (idempotentnie).
Inkrementalny pull edycji: od najnowszego event_time w bazie.

Użycie: python3 run.py
"""
import json
import os
import sys
from datetime import date

import db
import pull
from meta_common import WORKSPACE

LIVE_CONFIG = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads", "live-config.json")


def store(conn, data, today):
    """Zapis snapshotu do bazy. Zwraca licznik zapisanych assetów."""
    for c in data["campaigns"]:
        db.upsert_campaign(conn, {**c, "last_seen": today})
    for row in data["campaign_daily"]:
        db.upsert_campaign_daily(conn, row)
    for row in data["assets"]:
        db.upsert_asset(conn, row)
    for row in data["campaign_windows"]:
        db.upsert_campaign_window(conn, row)
    for cr in data["creatives"]:
        db.upsert_creative(conn, cr)
    for obj in data["ad_objects"]:
        db.upsert_ad_object(conn, obj)
    for act in data["activities"]:
        db.insert_activity(conn, act)
    for row in data.get("adsets", []):
        db.upsert_adset(conn, {**row, "last_seen": today})
    db.update_campaign_statuses(conn, data.get("statuses", {}), today)
    conn.commit()
    return len(data["assets"])


def snapshot_live_signups(conn, today):
    """Dzienny snapshot łącznych zapisów na live z MailerLite (wg live-config.json).

    Nieudany snapshot NIE wywala pipeline'u — pacing po prostu nie zaktualizuje dzisiejszego
    punktu (raport pokaże ostatni znany stan).
    """
    if not os.path.exists(LIVE_CONFIG):
        return
    with open(LIVE_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    gid = cfg.get("mailer_group_id")
    if not gid:
        return
    n = pull.fetch_mailer_signups(gid)
    if n is not None:
        db.upsert_live_signups(conn, today, gid, n)
        conn.commit()
        print(f"Zapisy na live (MailerLite, organik+płatne): {n}", file=sys.stderr)


def summary(conn):
    """Podsumowanie stanu bazy na stderr."""
    q = conn.execute
    n_camp = q("SELECT COUNT(*) n FROM campaigns").fetchone()["n"]
    n_asset = q("SELECT COUNT(*) n FROM assets").fetchone()["n"]
    n_win = q("SELECT COUNT(*) n FROM campaign_windows").fetchone()["n"]
    n_creat = q("SELECT COUNT(*) n FROM creatives").fetchone()["n"]
    n_act = q("SELECT COUNT(*) n FROM activities").fetchone()["n"]
    rng = q("SELECT MIN(date) a, MAX(date) b FROM campaign_daily").fetchone()
    print("\n=== STAN BAZY meta-ads.db ===", file=sys.stderr)
    print(f"  kampanie:   {n_camp}", file=sys.stderr)
    print(f"  assets (lifetime): {n_asset} wierszy", file=sys.stderr)
    print(f"  campaign_windows: {n_win} wierszy", file=sys.stderr)
    print(f"  campaign_daily zakres: {rng['a']} … {rng['b']}", file=sys.stderr)
    print(f"  creatives:  {n_creat}", file=sys.stderr)
    print(f"  activities: {n_act}", file=sys.stderr)
    print("\n  Klasy kampanii:", file=sys.stderr)
    for r in q("SELECT klasa, COUNT(*) n FROM campaigns GROUP BY klasa").fetchall():
        print(f"    {r['klasa']}: {r['n']}", file=sys.stderr)


def main():
    conn = db.connect()
    since = db.latest_activity_time(conn)
    if since:
        print(f"Inkrementalny pull edycji od: {since}", file=sys.stderr)
    data = pull.pull_all(since=since)
    today = date.today().isoformat()
    n = store(conn, data, today)
    snapshot_live_signups(conn, today)
    print(f"\nZapisano snapshot {today}: {n} wierszy assetów.", file=sys.stderr)
    summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
