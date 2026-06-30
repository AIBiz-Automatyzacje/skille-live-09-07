#!/usr/bin/env python3
"""Reddit search przez oficjalne Reddit API (PRAW).

Read-only mode (client_credentials OAuth). Multi-query + subreddit whitelist
+ post-fetch filtry (upvotes, komentarze, data).
Output: Zasoby/AI Output/reddit-search/YYYY-MM-DD-[slug].{md,json}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Cross-platform: wymuś UTF-8 stdout (Windows cp1250 → UnicodeEncodeError przy emoji/PL)
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

try:
    import praw
    from prawcore.exceptions import NotFound, Forbidden, PrawcoreException
except ImportError:
    print("Brak praw. Instaluję (--user)...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "praw", "-q"])
    import praw
    from prawcore.exceptions import NotFound, Forbidden, PrawcoreException

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import find_workspace, load_env  # noqa: E402

WORKSPACE = find_workspace(script_path=__file__)
load_env(WORKSPACE)
OUTPUT_DIR = Path(
    os.getenv("REDDIT_OUTPUT_DIR")
    or WORKSPACE / "Zasoby" / "AI Output" / "reddit-search"
)


def build_reddit() -> praw.Reddit:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    if not all([client_id, client_secret, user_agent]):
        sys.exit("❌ Brak REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT w .env")
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        check_for_async=False,
    )


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len]


def submission_to_dict(s) -> dict:
    return {
        "post_id": s.id,
        "url": f"https://www.reddit.com{s.permalink}",
        "title": s.title,
        "subreddit": s.subreddit.display_name,
        "author": str(s.author) if s.author else "deleted",
        "body": s.selftext or "",
        "body_preview": (s.selftext or "")[:300],
        "upvotes": int(s.score or 0),
        "comments": int(s.num_comments or 0),
        "created_utc": s.created_utc,
        "created_at": datetime.fromtimestamp(s.created_utc, tz=timezone.utc).isoformat(),
        "is_video": bool(s.is_video),
        "over18": bool(s.over_18),
    }


def search_subreddit(reddit, subreddit_name: str, query: str, sort: str, time_filter: str, limit: int) -> list[dict]:
    try:
        results = reddit.subreddit(subreddit_name).search(
            query, sort=sort, time_filter=time_filter, limit=limit
        )
        return [submission_to_dict(s) for s in results]
    except NotFound:
        print(f"  ⚠️ r/{subreddit_name} nie istnieje — pomijam")
        return []
    except Forbidden:
        print(f"  ⚠️ r/{subreddit_name} prywatny/quarantined — pomijam")
        return []
    except PrawcoreException as e:
        print(f"  ⚠️ r/{subreddit_name} błąd API: {e}")
        return []


def deduplicate(posts: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in posts:
        if p["post_id"] in seen:
            continue
        seen.add(p["post_id"])
        unique.append(p)
    return unique


def apply_filters(
    posts: list[dict],
    min_upvotes: int,
    min_comments: int,
    since: str | None,
    include_nsfw: bool,
) -> list[dict]:
    since_dt = None
    if since:
        since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)

    filtered = []
    for p in posts:
        if p["upvotes"] < min_upvotes:
            continue
        if p["comments"] < min_comments:
            continue
        if not include_nsfw and p["over18"]:
            continue
        if since_dt:
            post_dt = datetime.fromtimestamp(p["created_utc"], tz=timezone.utc)
            if post_dt < since_dt:
                continue
        filtered.append(p)

    filtered.sort(key=lambda x: x["upvotes"], reverse=True)
    for i, p in enumerate(filtered, start=1):
        p["rank"] = i
    return filtered


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def render_markdown(queries: list[str], filters: dict, all_results: list[dict], top_n: int) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    front = ["---", f"queries: {json.dumps(queries, ensure_ascii=False)}", f"date: {date}", "filters:"]
    for k, v in filters.items():
        front.append(f"  {k}: {json.dumps(v, ensure_ascii=False) if v is not None else 'null'}")
    front.append(f"total_found: {len(all_results)}")
    front.append(f"showing_top: {min(top_n, len(all_results))}")
    front.append("---")
    front.append("")

    top = all_results[:top_n]
    tail = all_results[top_n:]

    body = [f"# Reddit Search: {' | '.join(queries)}", ""]
    body.append(
        f"**Filtry:** {filters['sort']}/{filters['time']}"
        f" | min {filters['min_upvotes']} upvotes | min {filters['min_comments']} komentarzy"
        f" | r/{filters['subreddits'] or 'all'}"
    )
    body.append(f"**Znalezionych:** {len(all_results)} | **Pokazuję top:** {len(top)}")
    body.append("")

    if not all_results:
        body.append("## Brak wyników po zastosowaniu filtrów.")
        body.append("Spróbuj złagodzić: obniżyć `--min-upvotes`, `--min-comments`, rozszerzyć subreddity lub `--time`.")
        return "\n".join(front + body)

    body.append(f"## Top {len(top)} — tabela")
    body.append("")
    body.append("| # | Tytuł | r/ | Autor | ⬆️ | 💬 | Data | Link |")
    body.append("|---|-------|-----|-------|-----|-----|------|------|")
    for r in top:
        title_safe = r["title"].replace("|", "\\|")
        body.append(
            f"| {r['rank']} | {title_safe} | {r['subreddit']} | u/{r['author']} |"
            f" {fmt_number(r['upvotes'])} | {fmt_number(r['comments'])} |"
            f" {r['created_at'][:10]} | [link]({r['url']}) |"
        )
    body.append("")

    body.append(f"## Detale top {len(top)}")
    body.append("")
    for r in top:
        body.extend([
            f"### {r['rank']}. {r['title']} — r/{r['subreddit']}",
            "",
            f"- **upvotes:** {fmt_number(r['upvotes'])} | **komentarze:** {fmt_number(r['comments'])}"
            f" | **autor:** u/{r['author']}",
            f"- **post_id:** `{r['post_id']}` | **opublikowano:** {r['created_at'][:10]}",
            f"- **URL:** {r['url']}",
            f"- **body (skrót):** {r['body_preview'].strip() or '_brak treści_'}",
            "",
        ])

    if tail:
        body.append(f"## Pozostałe {len(tail)} (tabela kompaktowa)")
        body.append("")
        body.append("| # | Tytuł | r/ | ⬆️ | 💬 | Link |")
        body.append("|---|-------|-----|-----|-----|------|")
        for r in tail:
            title_safe = r["title"].replace("|", "\\|")
            body.append(
                f"| {r['rank']} | {title_safe} | {r['subreddit']} |"
                f" {fmt_number(r['upvotes'])} | {fmt_number(r['comments'])} | [link]({r['url']}) |"
            )
        body.append("")

    return "\n".join(front + body)


def write_outputs(queries: list[str], filters: dict, all_results: list[dict], top_n: int) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(queries[0]) or "query"
    base = OUTPUT_DIR / f"{date}-{slug}"

    json_path = base.with_suffix(".json")
    payload = {
        "queries": queries,
        "date": date,
        "filters": filters,
        "total_found": len(all_results),
        "showing_top": min(top_n, len(all_results)),
        "results": all_results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = base.with_suffix(".md")
    md_path.write_text(render_markdown(queries, filters, all_results, top_n), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Reddit search przez oficjalne Reddit API (PRAW).")
    parser.add_argument("--query", action="append", required=True, help="Query (można powtórzyć wielokrotnie)")
    parser.add_argument("--subreddits", default=None, help="Whitelist subredditów, comma-separated (bez prefiksu r/)")
    parser.add_argument("--sort", default="top", choices=["top", "hot", "new", "relevance", "comments"])
    parser.add_argument("--time", default="year", choices=["hour", "day", "week", "month", "year", "all"])
    parser.add_argument("--min-upvotes", type=int, default=10)
    parser.add_argument("--min-comments", type=int, default=3)
    parser.add_argument("--max-items", type=int, default=100, help="Limit per (query × subreddit). Max 100 z Reddit API.")
    parser.add_argument("--top", type=int, default=10, help="Ile w szczegółach markdowna (JSON ma wszystkie)")
    parser.add_argument("--since", default=None, help="Dodatkowy filtr YYYY-MM-DD")
    parser.add_argument("--nsfw", action="store_true")
    args = parser.parse_args()

    reddit = build_reddit()
    subreddit_list = (
        [s.strip().lstrip("r/").strip("/") for s in args.subreddits.split(",") if s.strip()]
        if args.subreddits else []
    )

    # Reddit API cap: limit max = 100 per call
    per_call_limit = min(args.max_items, 100)

    targets = subreddit_list or ["all"]
    total_calls = len(targets) * len(args.query)
    print(f"🔍 Reddit search — {len(targets)} sub × {len(args.query)} q = {total_calls} calls"
          f" | sort={args.sort}/{args.time} | limit/call={per_call_limit}")

    raw_posts: list[dict] = []
    for sub in targets:
        for q in args.query:
            print(f"  → r/{sub} :: '{q}'")
            posts = search_subreddit(reddit, sub, q, args.sort, args.time, per_call_limit)
            print(f"    pobrano: {len(posts)}")
            raw_posts.extend(posts)

    unique = deduplicate(raw_posts)
    print(f"  Raw: {len(raw_posts)} → unique: {len(unique)}")

    filtered = apply_filters(
        unique,
        min_upvotes=args.min_upvotes,
        min_comments=args.min_comments,
        since=args.since,
        include_nsfw=args.nsfw,
    )
    print(f"  Po filtrach: {len(filtered)}")

    filters = {
        "subreddits": args.subreddits,
        "sort": args.sort,
        "time": args.time,
        "min_upvotes": args.min_upvotes,
        "min_comments": args.min_comments,
        "max_items": args.max_items,
        "since": args.since,
        "nsfw": args.nsfw,
    }
    md_path, json_path = write_outputs(args.query, filters, filtered, args.top)

    print(f"\n✅ Znalezionych: {len(filtered)} (z {len(unique)} unique, {len(raw_posts)} raw)")
    print(f"📄 Markdown: {md_path}")
    print(f"🧾 JSON:     {json_path}")
    if filtered:
        print("\nTop 3:")
        for r in filtered[:3]:
            print(f"  {r['rank']}. [{r['upvotes']} ⬆️ {r['comments']} 💬] {r['title']} — r/{r['subreddit']}")


if __name__ == "__main__":
    main()
