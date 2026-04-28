#!/usr/bin/env python3
"""
Instagram sync via Meta Instagram Graph API.

Setup (one-time):
  1. You need a Professional / Creator account on Instagram
  2. Go to developers.facebook.com → Create App → "Instagram" product
  3. Connect your Instagram account and generate a long-lived token
  4. Store as GitHub Secret: INSTAGRAM_TOKEN
  5. Your Instagram user ID (numeric) goes in IG_USER_ID below

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api
"""

import json
import os
import ssl
import urllib.request
from datetime import datetime

TOKEN      = os.environ.get("INSTAGRAM_TOKEN", "")
IG_USER_ID = os.environ.get("INSTAGRAM_USER_ID", "")  # numeric ID from the API
MAX_POSTS  = 10

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        return json.loads(r.read())


def fetch_posts() -> list[dict]:
    if not TOKEN:
        print("[instagram] INSTAGRAM_TOKEN not set — skipping")
        return []

    print("[instagram] fetching …")
    try:
        # Get user ID if not cached
        uid = IG_USER_ID
        if not uid:
            me = _get(f"https://graph.instagram.com/me?fields=id&access_token={TOKEN}")
            uid = me["id"]

        data = _get(
            f"https://graph.instagram.com/v19.0/{uid}/media"
            f"?fields=id,caption,media_type,media_url,thumbnail_url,timestamp,permalink"
            f"&limit={MAX_POSTS}&access_token={TOKEN}"
        )
    except Exception as e:
        print(f"[instagram] ERROR: {e}")
        return []

    posts = []
    for item in data.get("data", []):
        caption = (item.get("caption") or "").strip()
        mtype   = item.get("media_type", "")
        ts_raw  = item.get("timestamp", "")
        link    = item.get("permalink", "https://www.instagram.com/fengnuo1892/")
        mid     = item.get("id", "")

        images = []
        if mtype == "IMAGE" and item.get("media_url"):
            images = [item["media_url"]]
        elif mtype == "VIDEO" and item.get("thumbnail_url"):
            images = [item["thumbnail_url"]]
        elif mtype == "CAROUSEL_ALBUM" and item.get("media_url"):
            images = [item["media_url"]]

        date_str, ts = "", 0
        if ts_raw:
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                ts = int(dt.timestamp())
            except Exception:
                pass

        if not caption and not images:
            continue

        posts.append({
            "id": f"instagram_{mid}",
            "platform": "instagram",
            "text": caption,
            "images": images[:4],
            "date": date_str,
            "timestamp": ts,
            "url": link,
        })

    print(f"[instagram] got {len(posts)} posts")
    return posts
