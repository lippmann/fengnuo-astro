#!/usr/bin/env python3
"""
Threads sync via Meta Threads API.

Setup (one-time):
  1. Go to developers.facebook.com → My Apps → Create App → "Access the Threads API"
  2. Add your Threads account under "Threads" product
  3. Generate a long-lived User Access Token (valid 60 days, renewable)
  4. Store as GitHub Secret: THREADS_TOKEN
  5. Your Threads user ID is stored below (or auto-fetched)

Docs: https://developers.facebook.com/docs/threads
"""

import json
import os
import ssl
import urllib.request
from datetime import datetime

TOKEN    = os.environ.get("THREADS_TOKEN", "")
USER_ID  = "fengnuo1892"   # your @handle; numeric ID is fetched automatically
MAX_POSTS = 10

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        return json.loads(r.read())


def fetch_posts() -> list[dict]:
    if not TOKEN:
        print("[threads] THREADS_TOKEN not set — skipping")
        return []

    print("[threads] fetching …")
    try:
        # Get numeric user ID
        me = _get(f"https://graph.threads.net/v1.0/me?fields=id&access_token={TOKEN}")
        uid = me["id"]

        # Fetch recent threads
        data = _get(
            f"https://graph.threads.net/v1.0/{uid}/threads"
            f"?fields=id,text,media_type,media_url,timestamp,permalink"
            f"&limit={MAX_POSTS}&access_token={TOKEN}"
        )
    except Exception as e:
        print(f"[threads] ERROR: {e}")
        return []

    posts = []
    for item in data.get("data", []):
        text  = item.get("text", "").strip()
        mtype = item.get("media_type", "TEXT")
        ts_raw = item.get("timestamp", "")
        link  = item.get("permalink", f"https://www.threads.com/@{USER_ID}")
        mid   = item.get("id", "")

        images = []
        if mtype in ("IMAGE", "CAROUSEL_ALBUM") and item.get("media_url"):
            images = [item["media_url"]]

        date_str, ts = "", 0
        if ts_raw:
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                ts = int(dt.timestamp())
            except Exception:
                pass

        if not text and not images:
            continue

        posts.append({
            "id": f"threads_{mid}",
            "platform": "threads",
            "text": text,
            "images": images[:4],
            "date": date_str,
            "timestamp": ts,
            "url": link,
        })

    print(f"[threads] got {len(posts)} posts")
    return posts
