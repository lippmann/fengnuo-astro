#!/usr/bin/env python3
"""
Master sync script for fengnuo-astro.

Syncs Douban, X, Threads, Instagram → merges into src/data/feed.json
Astro reads feed.json at build time; no HTML rendering needed here.

Required env vars:
  DOUBAN_COOKIE    — full browser cookie string for douban.com
  THREADS_TOKEN    — (optional) Meta Threads API long-lived token
  INSTAGRAM_TOKEN  — (optional) Meta Instagram Graph API token
"""

import json
import os
import sys
from pathlib import Path

ROOT      = Path(__file__).parent.parent
FEED_FILE = ROOT / "src/data/feed.json"


def load_feed() -> list[dict]:
    if FEED_FILE.exists():
        return json.loads(FEED_FILE.read_text())
    return []


def save_feed(posts: list[dict]):
    FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEED_FILE.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def merge(existing: list[dict], new_posts: list[dict]) -> list[dict]:
    by_id = {p["id"]: p for p in existing}
    for p in new_posts:
        by_id[p["id"]] = p
    all_posts = list(by_id.values())
    all_posts.sort(key=lambda p: p.get("timestamp", 0), reverse=True)
    return all_posts


def main():
    feed = load_feed()
    new_posts: list[dict] = []

    # Douban
    douban_cookie = os.environ.get("DOUBAN_COOKIE", "")
    if douban_cookie:
        from sync_douban import fetch_posts as fetch_douban
        new_posts.extend(fetch_douban(douban_cookie))
    else:
        print("[douban] DOUBAN_COOKIE not set — skipping")

    # X / Twitter
    from sync_twitter import fetch_posts as fetch_twitter
    new_posts.extend(fetch_twitter())

    # Threads
    from sync_threads import fetch_posts as fetch_threads
    new_posts.extend(fetch_threads())

    # Instagram
    from sync_instagram import fetch_posts as fetch_instagram
    new_posts.extend(fetch_instagram())

    # WeChat Reading highlights
    weread_cookie = os.environ.get("WEREAD_COOKIE", "")
    if weread_cookie:
        from weread_sync import fetch_posts as fetch_weread
        new_posts.extend(fetch_weread(weread_cookie))
    else:
        print("[weread] WEREAD_COOKIE not set — skipping")

    if new_posts:
        feed = merge(feed, new_posts)
        save_feed(feed)
        print(f"[feed] total {len(feed)} posts saved to {FEED_FILE}")
    else:
        print("[feed] no new posts, feed unchanged")

    if not feed:
        print("ERROR: feed is empty", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
