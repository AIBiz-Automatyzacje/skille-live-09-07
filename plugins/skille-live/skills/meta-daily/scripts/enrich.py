#!/usr/bin/env python3
"""ENRICH — analiza wizualna assetów z cache.

Grafiki: ogląda Claude (vision) — ten skrypt przygotowuje manifest + pobiera obrazy.
Wideo: Gemini (analyze_videos) — pobiera source z Meta i woła Gemini API.
Cache: pomijamy assety, które mają już visual_analysis (raz na życie assetu).

Użycie:
  python3 enrich.py prepare   → manifest grafik do obejrzenia przez Claude (JSON na stdout)
  python3 enrich.py videos    → analiza wideo przez Gemini (zapis do bazy)
"""
import json
import os
import subprocess
import sys
from datetime import date

import requests

import db
from meta_common import WORKSPACE, api_get

# Reużycie gotowego skryptu Gemini (systemowy python3 ma google-genai — zero nowych zależności)
VIDEO_ANALYZE = os.path.join(WORKSPACE, ".claude/skills/video-analyze/scripts/analyze_video.py")
VIDEO_PROMPT = (
    "To kreacja wideo reklamy Meta Ads (pozyskiwanie zapisów na bezpłatny live / sprzedaż kursu). "
    "Opisz zwięźle co się dzieje w wideo: hook w pierwszych 3 sekundach, tempo, czytelność przekazu, "
    "obecność i siłę CTA. Oceń, co w tej kreacji może podbijać lub obniżać CTR i koszt konwersji. "
    "Bez ogólników — konkretne obserwacje wizualne."
)

CACHE_DIR = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads", ".cache")

# Minimalna próba do analizy wizualnej — poniżej kreacja i tak ląduje w raporcie jako
# zwinięta linijka „mała próba", więc analiza byłaby szumem (i kosztem) bez odbiorcy.
MIN_IMPR = 3000


def log(msg):
    print(msg, file=sys.stderr)


def assets_to_analyze(conn, asset_type):
    """image/video z sensowną emisją (impressions > MIN_IMPR) bez gotowej analizy wizualnej."""
    return conn.execute(
        """SELECT c.asset_key, c.name, c.thumbnail_url,
                  SUM(a.impressions) impr
           FROM creatives c JOIN assets a ON a.asset_key=c.asset_key
           WHERE c.asset_type=? AND c.visual_analysis IS NULL
           GROUP BY c.asset_key HAVING impr > ?
           ORDER BY SUM(a.spend) DESC""",
        (asset_type, MIN_IMPR),
    ).fetchall()


def campaign_copy(conn, asset_key):
    """Copy (body/title) reklam, w których asset się pojawia — kontekst dla analizy grafiki."""
    rows = conn.execute(
        """SELECT DISTINCT cr.copy_text FROM assets a
           JOIN assets b ON b.ad_id=a.ad_id AND b.asset_type IN ('body','title')
           JOIN creatives cr ON cr.asset_key=b.asset_key
           WHERE a.asset_key=? AND cr.copy_text IS NOT NULL LIMIT 5""",
        (asset_key,),
    ).fetchall()
    return [r["copy_text"] for r in rows]


def download_image(url, dest):
    """Pobiera obraz do dest. Zwraca True/False."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except (requests.RequestException, OSError) as e:
        log(f"  download fail: {e}")
        return False


def prepare(conn):
    """Manifest grafik do obejrzenia przez Claude vision. Pobiera obrazy do CACHE_DIR.

    Manifest CELOWO nie zawiera metryk: analiza wizualna opisuje wyłącznie CO WIDAĆ
    (hook, układ, twarz, plakietki). Liczby w tekście analizy dezaktualizują się w cache
    i kłamią w raporcie (bug z 02.07: analiza „CTR 3,88%" obok kafelka 1,81%).
    Interpretację metryk robi codziennie krok REASON na świeżych danych.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    items = []
    for r in assets_to_analyze(conn, "image"):
        dest = os.path.join(CACHE_DIR, f"{r['asset_key']}.png")
        if not os.path.exists(dest) and not download_image(r["thumbnail_url"], dest):
            continue
        items.append({
            "asset_key": r["asset_key"], "name": r["name"], "image_path": dest,
            "copy_context": campaign_copy(conn, r["asset_key"]),
        })
    return items


def fetch_video_source(video_id):
    """URL pliku wideo (mp4) do pobrania/analizy."""
    _, j = api_get(f"{video_id}", {"fields": "source"})
    return j.get("source")


def analyze_one_video(video_id, dest_mp4):
    """Pobiera mp4 i woła Gemini przez analyze_video.py (systemowy python3). Zwraca tekst lub None."""
    source = fetch_video_source(video_id)
    if not source:
        log(f"  brak source dla wideo {video_id}")
        return None
    if not os.path.exists(dest_mp4) and not download_image(source, dest_mp4):
        return None
    try:
        out = subprocess.run(
            ["python3", VIDEO_ANALYZE, dest_mp4, "--prompt", VIDEO_PROMPT, "--raw"],
            capture_output=True, text=True, timeout=300, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log(f"  Gemini fail dla {video_id}: {e}")
        return None


def analyze_videos(conn):
    """Dla każdego wideo z emisją bez analizy: pobierz source → Gemini → zapis. Liczba przeanalizowanych."""
    vids = assets_to_analyze(conn, "video")
    if not vids:
        log("Brak wideo do analizy.")
        return 0
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = date.today().isoformat()
    done = 0
    for v in vids:
        log(f"  analizuję wideo {v['name']} ({v['asset_key']})...")
        dest = os.path.join(CACHE_DIR, f"{v['asset_key']}.mp4")
        analysis = analyze_one_video(v["asset_key"], dest)
        if analysis:
            db.save_visual_analysis(conn, v["asset_key"], analysis, "gemini", today)
            conn.commit()
            done += 1
    return done


def save_analyses(conn, path):
    """Ładuje {asset_key: analiza} z pliku JSON i zapisuje jako analizy vision (grafiki)."""
    from datetime import date
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    today = date.today().isoformat()
    for asset_key, text in data.items():
        db.save_visual_analysis(conn, asset_key, text, "vision", today)
    conn.commit()
    return len(data)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    conn = db.connect()
    if cmd == "prepare":
        manifest = prepare(conn)
        log(f"Grafik do analizy wizualnej: {len(manifest)}")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif cmd == "save":
        if len(sys.argv) < 3:
            log("Użycie: enrich.py save <plik.json>")
        else:
            n = save_analyses(conn, sys.argv[2])
            log(f"Zapisano analiz grafik: {n}")
    elif cmd == "videos":
        n = analyze_videos(conn)
        log(f"Przeanalizowano wideo: {n}")
    else:
        log(f"Nieznana komenda: {cmd}")
    conn.close()


if __name__ == "__main__":
    main()
