#!/usr/bin/env python3
"""Warstwa SQLite dla /meta-daily — schemat + idempotentne upserty.

Baza: Zadania/projekty/meta-ads/meta-ads.db (trwały store, rośnie w czasie).
Używa wbudowanego modułu sqlite3 (działa na VPS bez instalacji).
"""
import hashlib
import json
import os
import sqlite3

from meta_common import WORKSPACE

DB_PATH = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads", "meta-ads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    objective     TEXT,
    klasa         TEXT,              -- 'sales' | 'lead'
    daily_budget  INTEGER,           -- grosze
    status        TEXT,
    created_time  TEXT,
    last_seen     TEXT NOT NULL,     -- data ostatniego snapshotu (YYYY-MM-DD)
    live_group    TEXT               -- tag grupy live (np. 'live 9 lipca'); ręcznie nadpisywalny
);

CREATE TABLE IF NOT EXISTS campaign_daily (
    campaign_id   TEXT NOT NULL,
    date          TEXT NOT NULL,     -- YYYY-MM-DD
    impressions   INTEGER DEFAULT 0,
    clicks        INTEGER DEFAULT 0,
    spend         REAL DEFAULT 0,
    ctr           REAL DEFAULT 0,
    leads         REAL DEFAULT 0,
    purchases     REAL DEFAULT 0,
    revenue       REAL DEFAULT 0,
    PRIMARY KEY (campaign_id, date)
);

CREATE TABLE IF NOT EXISTS assets (
    campaign_id   TEXT NOT NULL,
    ad_id         TEXT NOT NULL,
    ad_name       TEXT,
    asset_type    TEXT NOT NULL,     -- 'image' | 'video' | 'body' | 'title'
    asset_key     TEXT NOT NULL,     -- hash | video_id | text_id (stabilny)
    impressions   INTEGER DEFAULT 0,
    clicks        INTEGER DEFAULT 0,
    spend         REAL DEFAULT 0,
    ctr           REAL DEFAULT 0,
    leads         REAL DEFAULT 0,
    purchases     REAL DEFAULT 0,
    revenue       REAL DEFAULT 0,
    first_day     TEXT,              -- pierwszy dzień z wyświetleniami (okres emisji kreacji)
    last_day      TEXT,              -- ostatni dzień z wyświetleniami
    active_days   INTEGER DEFAULT 0, -- liczba dni z wyświetleniami (emisja bywa z przerwami)
    PRIMARY KEY (ad_id, asset_type, asset_key)  -- lifetime: 1 wiersz/asset (bez time_increment = dokładna atrybucja)
);

CREATE TABLE IF NOT EXISTS campaign_windows (
    campaign_id   TEXT NOT NULL,
    window        TEXT NOT NULL,     -- 'today'|'yesterday'|'short'|'week'|'month'|'this_week'|'prev_week'
    date_from     TEXT NOT NULL,     -- granice okna (źródło prawdy z pull, compute ich nie przelicza)
    date_to       TEXT NOT NULL,
    impressions   INTEGER DEFAULT 0,
    clicks        INTEGER DEFAULT 0,
    spend         REAL DEFAULT 0,
    leads         REAL DEFAULT 0,
    purchases     REAL DEFAULT 0,
    revenue       REAL DEFAULT 0,
    reach         INTEGER DEFAULT 0, -- zasięg okna (do frequency = zmęczenie kreacji)
    frequency     REAL DEFAULT 0,
    link_clicks   INTEGER DEFAULT 0, -- lejek: klik w link → landing → lead
    lpv           INTEGER DEFAULT 0, -- landing_page_view
    PRIMARY KEY (campaign_id, window)  -- okna liczone time_range BEZ increment = dokładnie jak Ads Manager
);

CREATE TABLE IF NOT EXISTS adsets (
    adset_id      TEXT PRIMARY KEY,
    campaign_id   TEXT NOT NULL,
    name          TEXT,
    status        TEXT,
    daily_budget  INTEGER,           -- grosze
    targeting     TEXT,              -- JSON: wiek, płeć, grupy odbiorców + wykluczenia (nazwy)
    last_seen     TEXT
);

CREATE TABLE IF NOT EXISTS live_signups (
    date          TEXT NOT NULL,     -- dzień snapshotu (YYYY-MM-DD)
    group_id      TEXT NOT NULL,     -- ID grupy MailerLite (zapisy na live: organik + płatne)
    signups       INTEGER NOT NULL,
    PRIMARY KEY (date, group_id)
);

CREATE TABLE IF NOT EXISTS ad_objects (
    object_id     TEXT PRIMARY KEY,  -- adset_id lub ad_id
    object_type   TEXT,              -- 'adset' | 'ad'
    campaign_id   TEXT NOT NULL      -- do mapowania edycji zestawu/reklamy na kampanię
);

CREATE TABLE IF NOT EXISTS creatives (
    asset_key        TEXT PRIMARY KEY,
    asset_type       TEXT NOT NULL,
    name             TEXT,
    thumbnail_url    TEXT,           -- podgląd grafiki / klatka wideo
    copy_text        TEXT,           -- dla body/title: treść wariantu
    visual_analysis  TEXT,           -- cache analizy wizualnej (NULL = nieanalizowane)
    analysis_engine  TEXT,           -- 'vision' (grafiki) | 'gemini' (wideo)
    analyzed_at      TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    dedup_key     TEXT PRIMARY KEY,  -- sha1(event_time|event_type|object_id|extra_data)
    event_time    TEXT NOT NULL,
    event_type    TEXT,
    actor_name    TEXT,
    object_id     TEXT,
    object_type   TEXT,
    object_name   TEXT,
    campaign_id   TEXT,
    extra_data    TEXT               -- JSON old_value/new_value
);

CREATE TABLE IF NOT EXISTS reports (
    date          TEXT PRIMARY KEY,
    html_path     TEXT,
    created_at    TEXT
);
"""


def _migrate(conn):
    """Lekkie migracje dla baz utworzonych starszym schematem (CREATE IF NOT EXISTS nie dodaje kolumn)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()}
    if "live_group" not in cols:
        conn.execute("ALTER TABLE campaigns ADD COLUMN live_group TEXT")
    wcols = {r["name"] for r in conn.execute("PRAGMA table_info(campaign_windows)").fetchall()}
    for col, typ in (("reach", "INTEGER DEFAULT 0"), ("frequency", "REAL DEFAULT 0"),
                     ("link_clicks", "INTEGER DEFAULT 0"), ("lpv", "INTEGER DEFAULT 0")):
        if col not in wcols:
            conn.execute(f"ALTER TABLE campaign_windows ADD COLUMN {col} {typ}")


def connect():
    """Otwiera połączenie i gwarantuje schemat. Tworzy katalog jeśli brak."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def upsert_campaign(conn, camp):
    """camp: dict z id,name,objective,klasa,daily_budget,status,created_time,last_seen,live_group.

    live_group: auto-wykryte z nazwy wygrywa; gdy pull nie wykrył (NULL), zachowujemy
    istniejącą wartość — chroni ręczny override dla kampanii o nietypowych nazwach.
    """
    camp = {"live_group": None, **camp}
    conn.execute(
        """INSERT INTO campaigns (id,name,objective,klasa,daily_budget,status,created_time,last_seen,live_group)
           VALUES (:id,:name,:objective,:klasa,:daily_budget,:status,:created_time,:last_seen,:live_group)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, objective=excluded.objective, klasa=excluded.klasa,
             daily_budget=excluded.daily_budget, status=excluded.status, last_seen=excluded.last_seen,
             live_group=COALESCE(excluded.live_group, campaigns.live_group)""",
        camp,
    )


def upsert_campaign_daily(conn, row):
    """row: dict z kluczami kolumn campaign_daily. Idempotentne per (kampania,dzień)."""
    conn.execute(
        """INSERT INTO campaign_daily
             (campaign_id,date,impressions,clicks,spend,ctr,leads,purchases,revenue)
           VALUES (:campaign_id,:date,:impressions,:clicks,:spend,:ctr,:leads,:purchases,:revenue)
           ON CONFLICT(campaign_id,date) DO UPDATE SET
             impressions=excluded.impressions, clicks=excluded.clicks, spend=excluded.spend,
             ctr=excluded.ctr, leads=excluded.leads, purchases=excluded.purchases,
             revenue=excluded.revenue""",
        row,
    )


def upsert_asset(conn, row):
    """row: dict z kluczami kolumn assets (lifetime). Idempotentne per (ad,asset_type,asset_key)."""
    conn.execute(
        """INSERT INTO assets
             (campaign_id,ad_id,ad_name,asset_type,asset_key,
              impressions,clicks,spend,ctr,leads,purchases,revenue,
              first_day,last_day,active_days)
           VALUES
             (:campaign_id,:ad_id,:ad_name,:asset_type,:asset_key,
              :impressions,:clicks,:spend,:ctr,:leads,:purchases,:revenue,
              :first_day,:last_day,:active_days)
           ON CONFLICT(ad_id,asset_type,asset_key) DO UPDATE SET
             impressions=excluded.impressions, clicks=excluded.clicks, spend=excluded.spend,
             ctr=excluded.ctr, leads=excluded.leads, purchases=excluded.purchases,
             revenue=excluded.revenue, ad_name=excluded.ad_name, campaign_id=excluded.campaign_id,
             first_day=excluded.first_day, last_day=excluded.last_day, active_days=excluded.active_days""",
        row,
    )


def upsert_campaign_window(conn, row):
    """row: dict z kluczami kolumn campaign_windows. Idempotentne per (kampania,okno)."""
    conn.execute(
        """INSERT INTO campaign_windows
             (campaign_id,window,date_from,date_to,impressions,clicks,spend,leads,purchases,revenue,
              reach,frequency,link_clicks,lpv)
           VALUES
             (:campaign_id,:window,:date_from,:date_to,:impressions,:clicks,:spend,:leads,:purchases,:revenue,
              :reach,:frequency,:link_clicks,:lpv)
           ON CONFLICT(campaign_id,window) DO UPDATE SET
             date_from=excluded.date_from, date_to=excluded.date_to,
             impressions=excluded.impressions, clicks=excluded.clicks, spend=excluded.spend,
             leads=excluded.leads, purchases=excluded.purchases, revenue=excluded.revenue,
             reach=excluded.reach, frequency=excluded.frequency,
             link_clicks=excluded.link_clicks, lpv=excluded.lpv""",
        row,
    )


def upsert_adset(conn, row):
    """row: dict adset_id,campaign_id,name,status,daily_budget,targeting(JSON str),last_seen."""
    conn.execute(
        """INSERT INTO adsets (adset_id,campaign_id,name,status,daily_budget,targeting,last_seen)
           VALUES (:adset_id,:campaign_id,:name,:status,:daily_budget,:targeting,:last_seen)
           ON CONFLICT(adset_id) DO UPDATE SET
             campaign_id=excluded.campaign_id, name=excluded.name, status=excluded.status,
             daily_budget=excluded.daily_budget, targeting=excluded.targeting,
             last_seen=excluded.last_seen""",
        row,
    )


def upsert_live_signups(conn, day, group_id, signups):
    """Dzienny snapshot łącznych zapisów na live z MailerLite (organik + płatne).

    Delta między dniami = dzienne tempo zapisów WSZYSTKICH źródeł — tego Meta nie widzi.
    """
    conn.execute(
        """INSERT INTO live_signups (date,group_id,signups) VALUES (?,?,?)
           ON CONFLICT(date,group_id) DO UPDATE SET signups=excluded.signups""",
        (day, group_id, signups),
    )


def update_campaign_statuses(conn, statuses, today):
    """Odświeża status znanych kampanii wg pełnej listy z API (reaper wstrzymanych).

    Kampania wstrzymana na Meta nie wraca w pull selekcji — bez tego wisiałaby w bazie
    jako ACTIVE ze starymi danymi (bug „KursCC wisi jako ACTIVE" z 30.06).
    """
    for cid, status in statuses.items():
        conn.execute("UPDATE campaigns SET status=?, last_seen=? WHERE id=?",
                     (status, today, cid))


def upsert_ad_object(conn, obj):
    """obj: dict object_id,object_type,campaign_id. Mapa zestaw/reklama → kampania."""
    conn.execute(
        """INSERT INTO ad_objects (object_id,object_type,campaign_id)
           VALUES (:object_id,:object_type,:campaign_id)
           ON CONFLICT(object_id) DO UPDATE SET
             object_type=excluded.object_type, campaign_id=excluded.campaign_id""",
        obj,
    )


def upsert_creative(conn, cr):
    """cr: dict asset_key,asset_type,name,thumbnail_url,copy_text.

    NIE nadpisuje gemini_analysis/analyzed_at (cache analizy wizualnej zostaje).
    """
    conn.execute(
        """INSERT INTO creatives (asset_key,asset_type,name,thumbnail_url,copy_text)
           VALUES (:asset_key,:asset_type,:name,:thumbnail_url,:copy_text)
           ON CONFLICT(asset_key) DO UPDATE SET
             name=excluded.name, thumbnail_url=excluded.thumbnail_url,
             copy_text=excluded.copy_text""",
        cr,
    )


def insert_activity(conn, act):
    """act: dict event_time,event_type,actor_name,object_id,object_type,object_name,
    campaign_id,extra_data(str/dict). Dedup po hashu — duplikaty ignorowane."""
    extra = act.get("extra_data")
    extra_str = extra if isinstance(extra, str) else json.dumps(extra, ensure_ascii=False)
    raw = f"{act.get('event_time')}|{act.get('event_type')}|{act.get('object_id')}|{extra_str}"
    dedup_key = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO activities
             (dedup_key,event_time,event_type,actor_name,object_id,object_type,object_name,campaign_id,extra_data)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (dedup_key, act.get("event_time"), act.get("event_type"), act.get("actor_name"),
         act.get("object_id"), act.get("object_type"), act.get("object_name"),
         act.get("campaign_id"), extra_str),
    )


def save_visual_analysis(conn, asset_key, text, engine, analyzed_at):
    """Zapisuje analizę wizualną do cache. Nie nadpisuje metadanych assetu."""
    conn.execute(
        """UPDATE creatives SET visual_analysis=?, analysis_engine=?, analyzed_at=?
           WHERE asset_key=?""",
        (text, engine, analyzed_at, asset_key),
    )


def latest_activity_time(conn):
    """Najnowszy event_time w activities (do inkrementalnego pull). None jeśli pusto."""
    row = conn.execute("SELECT MAX(event_time) AS t FROM activities").fetchone()
    return row["t"] if row else None
