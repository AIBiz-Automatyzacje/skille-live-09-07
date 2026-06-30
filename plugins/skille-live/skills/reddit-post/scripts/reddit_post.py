#!/usr/bin/env python3
"""Reddit Post Downloader — pobiera post + komentarze przez oficjalne Reddit API (PRAW).

Read-only mode (client_credentials OAuth) — bez user login.
Limit: 100 req/min (PRAW handles throttling automatically).
"""

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
from env_loader import find_workspace, load_env

WORKSPACE = find_workspace(script_path=__file__)
load_env(WORKSPACE)
REDDIT_DIR = WORKSPACE / "Zasoby" / "Research" / "Reddit"

MAX_COMMENTS = 50


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


def extract_post_id(url: str) -> str | None:
    match = re.search(r"/comments/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None


def slugify(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_len]


def fmt_date(ts: float | None) -> str:
    if not ts:
        return "brak daty"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def collect_post(submission) -> dict:
    submission.comments.replace_more(limit=0)
    flat = submission.comments.list()
    flat.sort(key=lambda c: c.score, reverse=True)

    comments = []
    for c in flat[:MAX_COMMENTS]:
        comments.append({
            "username": str(c.author) if c.author else "deleted",
            "body": c.body or "",
            "upvotes": c.score,
            "created_utc": c.created_utc,
            "created_at": datetime.fromtimestamp(c.created_utc, tz=timezone.utc).isoformat(),
        })

    return {
        "id": submission.id,
        "url": f"https://www.reddit.com{submission.permalink}",
        "title": submission.title,
        "username": str(submission.author) if submission.author else "deleted",
        "subreddit": submission.subreddit.display_name,
        "body": submission.selftext or "",
        "upvotes": submission.score,
        "num_comments": submission.num_comments,
        "created_utc": submission.created_utc,
        "created_at": datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "is_video": bool(submission.is_video),
        "over18": bool(submission.over_18),
        "comments": comments,
    }


def build_markdown(data: dict) -> str:
    lines = [
        f"# {data['title']}",
        "",
        f"> **Subreddit:** r/{data['subreddit']} | **Autor:** u/{data['username']} | **Data:** {fmt_date(data['created_utc'])}",
        f"> **Upvotes:** {data['upvotes']} | **Komentarze:** {data['num_comments']}",
        f"> {data['url']}",
        "",
        "---",
        "",
        "## Treść posta",
        "",
        data["body"] if data["body"] else "_Brak treści (post może zawierać tylko link lub obraz)_",
        "",
    ]

    if data["comments"]:
        lines.extend(["---", "", f"## Komentarze ({len(data['comments'])})", ""])
        for i, c in enumerate(data["comments"], 1):
            lines.extend([
                f"### {i}. u/{c['username']} ({c['upvotes']} pts)",
                f"*{fmt_date(c['created_utc'])}*",
                "",
                c["body"],
                "",
            ])

    return "\n".join(lines)


def save_files(data: dict) -> Path:
    folder_name = slugify(data["title"]) or f"post-{data['id']}"
    folder_path = REDDIT_DIR / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    (folder_path / "post.md").write_text(build_markdown(data), encoding="utf-8")

    meta = {k: v for k, v in data.items() if k != "comments"}
    meta["comments_count"] = len(data["comments"])
    (folder_path / ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return folder_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Użycie: python3 reddit_post.py <URL_REDDIT_POST>")
        print("Przykład: python3 reddit_post.py https://www.reddit.com/r/ClaudeAI/comments/abc123/title/")
        sys.exit(1)

    url = sys.argv[1]
    post_id = extract_post_id(url)
    if not post_id:
        sys.exit(f"❌ Nie rozpoznano URL posta Reddit: {url}")

    print(f"Post ID: {post_id}")
    reddit = build_reddit()

    try:
        submission = reddit.submission(id=post_id)
        # trigger fetch
        _ = submission.title
    except NotFound:
        sys.exit(f"❌ Post nie istnieje lub został usunięty: {post_id}")
    except Forbidden:
        sys.exit(f"❌ Brak dostępu do posta (prywatny/quarantined): {post_id}")
    except PrawcoreException as e:
        sys.exit(f"❌ Reddit API error: {e}")

    print("Pobieram post + komentarze...")
    data = collect_post(submission)
    print(f"Tytuł: {data['title']}")
    print(f"Komentarze pobrane: {len(data['comments'])} (z {data['num_comments']} total)")

    folder_path = save_files(data)
    print(f"\nZapisano do: {folder_path.relative_to(WORKSPACE)}")
    print("- post.md")
    print("- .meta.json")


if __name__ == "__main__":
    main()
