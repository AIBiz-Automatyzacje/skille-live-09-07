#!/usr/bin/env python3
"""
YouTube Transcript Downloader
Pobiera transkrypcję z YouTube przez Apify YouTube Scraper (async API)
"""

import os
import sys
import re
import json
import time
import ssl
import urllib.request
import urllib.parse
from pathlib import Path

# Cross-platform: wymuś UTF-8 stdout (Windows cp1250 → UnicodeEncodeError przy emoji/PL)
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Ścieżki
sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import find_workspace, load_env
WORKSPACE = find_workspace(script_path=__file__)
YOUTUBE_DIR = WORKSPACE / "Zasoby" / "Research" / "YouTube"

# Apify
ACTOR_ID = "h7sDV53CddomktSi5"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"

# SSL context
SSL_CTX = ssl.create_default_context()


def load_api_key():
    """Wczytaj API key z .env"""
    load_env(WORKSPACE)
    key = os.getenv("APIFY_API_KEY")
    if not key:
        print("Błąd: Brak APIFY_API_KEY w .env")
        sys.exit(1)
    return key


def api_request(url, method="GET", data=None, params=None):
    """Wykonaj request HTTP przez urllib"""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    with urllib.request.urlopen(req, data=body, timeout=30, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_video_id(url):
    """Wyciągnij ID wideo z URL YouTube"""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def slugify(text):
    """Zamień tytuł na slug dla nazwy folderu"""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text[:80]


def clean_srt(srt_text):
    """Usuń timestampy i numery z SRT, zostaw czysty tekst"""
    lines = srt_text.split('\n')
    clean_lines = []

    for line in lines:
        line = line.strip()
        if re.match(r'^\d+$', line):
            continue
        if re.match(r'\d{2}:\d{2}:\d{1,2}', line):
            continue
        if not line:
            continue
        clean_lines.append(line)

    text = ' '.join(clean_lines)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def start_run(video_url, api_key):
    """Rozpocznij async run w Apify"""
    payload = {
        "startUrls": [{"url": video_url}],
        "downloadSubtitles": True,
        "maxResults": 1
    }

    print("Uruchamiam Apify actor...")
    data = api_request(APIFY_RUN_URL, method="POST", data=payload, params={"token": api_key})

    run_id = data["data"]["id"]
    dataset_id = data["data"]["defaultDatasetId"]

    print(f"Run ID: {run_id}")
    return run_id, dataset_id


def wait_for_run(run_id, api_key, max_wait=300):
    """Czekaj na zakończenie run"""
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"

    start_time = time.time()
    while time.time() - start_time < max_wait:
        data = api_request(url, params={"token": api_key})
        status = data["data"]["status"]

        if status == "SUCCEEDED":
            print("Run zakończony!")
            return True
        elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            print(f"Run nie powiódł się: {status}")
            return False

        print(f"Status: {status}... czekam")
        time.sleep(5)

    print("Timeout - run trwa zbyt długo")
    return False


def get_results(dataset_id, api_key):
    """Pobierz wyniki z datasetu"""
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    return api_request(url, params={"token": api_key})


def process_response(data):
    """Wyciągnij potrzebne dane z odpowiedzi API"""
    if not data or not isinstance(data, list) or len(data) == 0:
        print("Błąd: Brak danych w odpowiedzi")
        sys.exit(1)

    video = data[0]

    result = {
        "title": video.get("title", "Bez tytułu"),
        "channel": video.get("channelName", "Nieznany kanał"),
        "url": video.get("url", ""),
        "date": video.get("date", ""),
        "duration": video.get("duration", ""),
        "views": video.get("viewCount", 0),
        "description": video.get("text", ""),
        "transcript": None
    }

    subtitles = video.get("subtitles", [])
    if subtitles:
        for sub in subtitles:
            if sub.get("srt"):
                result["transcript"] = clean_srt(sub["srt"])
                break

    return result


def save_files(data):
    """Zapisz transkrypcję i metadane do plików"""
    folder_name = slugify(data["title"])
    folder_path = YOUTUBE_DIR / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    # Transkrypcja
    transcript_path = folder_path / "transkrypcja.md"
    transcript_content = f"""# Transkrypcja: {data['title']}

> **Kanał:** {data['channel']} | **Data:** {data['date'][:10] if data['date'] else 'brak'} | **Czas:** {data['duration']}
> {data['url']}

---

{data['transcript'] if data['transcript'] else '_Brak transkrypcji dla tego wideo_'}
"""
    transcript_path.write_text(transcript_content, encoding='utf-8')

    # Metadane JSON
    meta_path = folder_path / ".meta.json"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    return folder_path


def main():
    if len(sys.argv) < 2:
        print("Użycie: python3 youtube_transcript.py <URL_YOUTUBE>")
        print("Przykład: python3 youtube_transcript.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)

    url = sys.argv[1]
    video_id = extract_video_id(url)

    if not video_id:
        print(f"Błąd: Nie rozpoznano URL YouTube: {url}")
        sys.exit(1)

    full_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Video ID: {video_id}")

    api_key = load_api_key()

    # Async flow
    run_id, dataset_id = start_run(full_url, api_key)

    if not wait_for_run(run_id, api_key):
        sys.exit(1)

    raw_data = get_results(dataset_id, api_key)
    data = process_response(raw_data)

    if not data["transcript"]:
        print("Uwaga: Wideo nie ma dostępnej transkrypcji")

    folder_path = save_files(data)

    print(f"\nZapisano do: {folder_path.relative_to(WORKSPACE)}")
    print(f"- transkrypcja.md")
    print(f"- .meta.json")

    return str(folder_path)


if __name__ == "__main__":
    main()
