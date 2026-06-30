#!/usr/bin/env python3
"""YouTube Data API v3 search with filtering, ranking, and markdown/JSON output.

Wywołanie:
    python3 yt_search.py "query" [flags]

Produkuje parę plików w Zasoby/AI Output/yt-search/:
    YYYY-MM-DD-[slug].md    — tabela + detale
    YYYY-MM-DD-[slug].json  — pipeline-ready data
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Cross-platform: wymuś UTF-8 stdout (Windows cp1250 → UnicodeEncodeError przy emoji/PL)
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import find_workspace  # noqa: E402

API_BASE = "https://www.googleapis.com/youtube/v3"
WORKSPACE = find_workspace(__file__)
OUTPUT_DIR = WORKSPACE / "Zasoby" / "AI Output" / "yt-search"


def load_api_key() -> str:
    load_dotenv(WORKSPACE / ".env")
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        sys.exit("❌ Brak YOUTUBE_API_KEY w .env. Dodaj klucz z Google Cloud Console → YouTube Data API v3.")
    return key


def parse_duration_iso8601(iso: str) -> int:
    """PT1H2M3S → 3723 sekund. PT15M33S → 933. PT45S → 45."""
    if not iso or not iso.startswith("PT"):
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return 0
    h, m, s = (int(x) if x else 0 for x in match.groups())
    return h * 3600 + m * 60 + s


def fmt_duration(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len]


def search_videos(key: str, query: str, max_raw: int, lang: str | None, since: str | None, sort: str) -> list[dict]:
    """search.list z paginacją → lista kandydatów. API daje max 50/strona, paginujemy przez nextPageToken."""
    collected: list[dict] = []
    page_token: str | None = None
    while len(collected) < max_raw:
        remaining = max_raw - len(collected)
        params = {
            "key": key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(remaining, 50),
            "order": sort,
        }
        if lang:
            params["relevanceLanguage"] = lang
        if since:
            dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            params["publishedAfter"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(f"{API_BASE}/search", params=params, timeout=15)
        if resp.status_code == 403:
            err = resp.json().get("error", {}).get("errors", [{}])[0]
            sys.exit(f"❌ YouTube API 403: {err.get('reason')} — {err.get('message')}")
        resp.raise_for_status()
        payload = resp.json()
        for it in payload.get("items", []):
            collected.append(
                {
                    "video_id": it["id"]["videoId"],
                    "title": html.unescape(it["snippet"]["title"]),
                    "channel": html.unescape(it["snippet"]["channelTitle"]),
                    "channel_id": it["snippet"]["channelId"],
                    "published_at": it["snippet"]["publishedAt"],
                    "description_preview": html.unescape(it["snippet"].get("description", ""))[:200],
                }
            )
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return collected


def enrich_videos(key: str, video_ids: list[str]) -> dict[str, dict]:
    """videos.list — statystyki + czas trwania. Batch po 50."""
    results: dict[str, dict] = {}
    for chunk_start in range(0, len(video_ids), 50):
        chunk = video_ids[chunk_start : chunk_start + 50]
        params = {
            "key": key,
            "part": "statistics,contentDetails",
            "id": ",".join(chunk),
        }
        resp = requests.get(f"{API_BASE}/videos", params=params, timeout=15)
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            duration_seconds = parse_duration_iso8601(content.get("duration", ""))
            engagement = round((likes / views * 100), 2) if views > 0 else 0.0
            results[item["id"]] = {
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": engagement,
                "duration_seconds": duration_seconds,
                "duration_human": fmt_duration(duration_seconds),
            }
    return results


def filter_and_rank(
    candidates: list[dict],
    stats_map: dict[str, dict],
    min_views: int,
    skip_shorts: bool,
    min_duration: int,
    blacklist: set[str],
) -> list[dict]:
    """Przepuszcza wszystkich kandydatów przez filtry twarde. Ranking do top N robi caller."""
    enriched: list[dict] = []
    for c in candidates:
        stats = stats_map.get(c["video_id"])
        if not stats:
            continue
        if stats["views"] < min_views:
            continue
        if skip_shorts and stats["duration_seconds"] < 60:
            continue
        if stats["duration_seconds"] < min_duration:
            continue
        if c["channel"].lower() in blacklist:
            continue
        enriched.append({**c, **stats, "url": f"https://youtube.com/watch?v={c['video_id']}"})

    enriched.sort(key=lambda x: x["views"], reverse=True)
    for i, row in enumerate(enriched, start=1):
        row["rank"] = i
    return enriched


def write_outputs(
    query: str,
    filters: dict,
    all_results: list[dict],
    top_n: int,
    json_only: bool,
) -> tuple[Path, Path]:
    """JSON trzyma wszystkich przechodzących filtry — markdown pokazuje tylko top N."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(query) or "query"
    base = OUTPUT_DIR / f"{today}-{slug}"

    json_path = base.with_suffix(".json")
    payload = {
        "query": query,
        "date": today,
        "filters": filters,
        "total_found": len(all_results),
        "showing_top": min(top_n, len(all_results)),
        "results": all_results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = base.with_suffix(".md")
    if not json_only:
        md_path.write_text(render_markdown(query, today, filters, all_results, top_n), encoding="utf-8")
    return md_path, json_path


def render_markdown(query: str, date: str, filters: dict, all_results: list[dict], top_n: int) -> str:
    frontmatter_lines = [
        "---",
        f'query: "{query}"',
        f"date: {date}",
        "filters:",
    ]
    for k, v in filters.items():
        value = "null" if v is None else json.dumps(v, ensure_ascii=False)
        frontmatter_lines.append(f"  {k}: {value}")
    frontmatter_lines.append(f"total_found: {len(all_results)}")
    frontmatter_lines.append(f"showing_top: {min(top_n, len(all_results))}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    top = all_results[:top_n]
    tail = all_results[top_n:]

    body = [f"# YT Search: {query}", ""]
    filter_desc = (
        f"**Filtry:** min {filters['min_views']} views"
        f" | lang: {filters['lang'] or 'any'} | od: {filters['since'] or 'any'}"
        f" | skip shorts: {filters['skip_shorts']} | sort: {filters['sort']}"
    )
    body.append(filter_desc)
    body.append(f"**Znalezionych:** {len(all_results)} | **Pokazuję top:** {len(top)}")
    body.append("")

    if not all_results:
        body.append("## Brak wyników po zastosowaniu filtrów.")
        body.append("Spróbuj złagodzić filtry: obniżyć `--min-views`, rozszerzyć `--since`, wyłączyć `--skip-shorts`.")
        return "\n".join(frontmatter_lines + body)

    body.append(f"## Top {len(top)} — tabela")
    body.append("")
    body.append("| # | Tytuł | Kanał | Views | ER% | Długość | Data | Link |")
    body.append("|---|-------|-------|-------|-----|---------|------|------|")
    for r in top:
        title_safe = r["title"].replace("|", "\\|")
        channel_safe = r["channel"].replace("|", "\\|")
        body.append(
            f"| {r['rank']} | {title_safe} | {channel_safe} | "
            f"{fmt_number(r['views'])} | {r['engagement_rate']}% | "
            f"{r['duration_human']} | {r['published_at'][:10]} | [link]({r['url']}) |"
        )

    body.append("")
    body.append(f"## Detale top {len(top)}")
    body.append("")
    for r in top:
        body.extend(
            [
                f"### {r['rank']}. {r['title']} — {r['channel']}",
                "",
                f"- **views:** {fmt_number(r['views'])} | **likes:** {fmt_number(r['likes'])}"
                f" | **comments:** {fmt_number(r['comments'])} | **engagement rate:** {r['engagement_rate']}%",
                f"- **długość:** {r['duration_human']} | **opublikowano:** {r['published_at'][:10]}",
                f"- **video_id:** `{r['video_id']}`",
                f"- **URL:** {r['url']}",
                f"- **opis (skrót):** {r['description_preview'].strip() or '_brak_'}",
                "",
            ]
        )

    if tail:
        body.append(f"## Pozostałe {len(tail)} (kompaktowa tabela)")
        body.append("")
        body.append("| # | Tytuł | Kanał | Views | Długość | Data | Link |")
        body.append("|---|-------|-------|-------|---------|------|------|")
        for r in tail:
            title_safe = r["title"].replace("|", "\\|")
            channel_safe = r["channel"].replace("|", "\\|")
            body.append(
                f"| {r['rank']} | {title_safe} | {channel_safe} | "
                f"{fmt_number(r['views'])} | {r['duration_human']} | "
                f"{r['published_at'][:10]} | [link]({r['url']}) |"
            )
        body.append("")

    return "\n".join(frontmatter_lines + body)


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube search with filtering and ranking.")
    parser.add_argument("query", help="Zapytanie (w cudzysłowie)")
    parser.add_argument("--top", type=int, default=10, help="Ile wyników pokazać userowi w sekcji 'Detale' (default 10). JSON ma wszystkich.")
    parser.add_argument("--raw-fetch", type=int, default=100, help="Ile kandydatów pobrać z YouTube przed filtrami (default 100, paginacja po 50)")
    parser.add_argument("--min-views", type=int, default=1000)
    parser.add_argument("--lang", default=None, help="Kod języka np. pl, en")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD")
    parser.add_argument("--skip-shorts", action="store_true")
    parser.add_argument("--min-duration", type=int, default=0, help="Sekundy")
    parser.add_argument("--sort", default="relevance", choices=["relevance", "date", "viewCount", "rating"])
    parser.add_argument("--channel-blacklist", default="", help="Kanały do pominięcia, oddzielone przecinkiem")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    key = load_api_key()
    blacklist = {c.strip().lower() for c in args.channel_blacklist.split(",") if c.strip()}

    candidates = search_videos(key, args.query, args.raw_fetch, args.lang, args.since, args.sort)
    if not candidates:
        print(f"⚠️  search.list zwrócił 0 kandydatów dla zapytania: {args.query}")

    video_ids = [c["video_id"] for c in candidates]
    stats_map = enrich_videos(key, video_ids) if video_ids else {}

    all_results = filter_and_rank(
        candidates,
        stats_map,
        min_views=args.min_views,
        skip_shorts=args.skip_shorts,
        min_duration=args.min_duration,
        blacklist=blacklist,
    )

    filters = {
        "top": args.top,
        "raw_fetch": args.raw_fetch,
        "min_views": args.min_views,
        "lang": args.lang,
        "since": args.since,
        "skip_shorts": args.skip_shorts,
        "min_duration": args.min_duration,
        "sort": args.sort,
        "channel_blacklist": sorted(blacklist) or None,
    }

    md_path, json_path = write_outputs(args.query, filters, all_results, args.top, args.json_only)

    print(f"✅ Przechodzi filtry: {len(all_results)} (z {len(candidates)} kandydatów pobranych z YT)")
    print(f"📄 Markdown (top {min(args.top, len(all_results))} + reszta tabelą): {md_path}")
    print(f"🧾 JSON (wszystkich {len(all_results)}): {json_path}")
    if all_results:
        print(f"\nTop 3:")
        for r in all_results[:3]:
            print(f"  {r['rank']}. {r['title']} — {r['channel']} ({fmt_number(r['views'])} views, {r['duration_human']})")


if __name__ == "__main__":
    main()
