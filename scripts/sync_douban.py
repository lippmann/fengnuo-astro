#!/usr/bin/env python3
"""Douban broadcast sync — returns list of post dicts."""

import hashlib
import os
import re
import ssl
import time
import urllib.request
from datetime import datetime
from pathlib import Path

STATUSES_URL  = "https://www.douban.com/people/L.Revolution/statuses"
TOPIC_URL     = "https://www.douban.com/topic/{}/"
MAX_POSTS     = 10
IMG_DIR       = Path(__file__).parent.parent / "public" / "images" / "douban"

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def _fetch(url: str, cookie: str) -> str:
    req = urllib.request.Request(url, headers={
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douban.com",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        return r.read().decode("utf-8", errors="replace")


def _download_image(url: str) -> str | None:
    """Download a douban image locally, return the public path or None on failure."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ext = url.split("?")[0].rsplit(".", 1)[-1]
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = "jpg"
    fname = hashlib.md5(url.encode()).hexdigest() + "." + ext
    dest = IMG_DIR / fname
    if dest.exists():
        return f"/images/douban/{fname}"
    try:
        req = urllib.request.Request(url, headers={
            "Referer": "https://www.douban.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        })
        with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
            dest.write_bytes(r.read())
        print(f"[douban]     downloaded image → {fname}")
        return f"/images/douban/{fname}"
    except Exception as e:
        print(f"[douban]     image download failed {url}: {e}")
        return None


def _topic_ids(html: str) -> list[str]:
    seen, ids = set(), []
    for m in re.finditer(r'douban\.com/topic/(\d+)', html):
        tid = m.group(1)
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    return ids[:MAX_POSTS]


def _parse_topic(tid: str, html: str) -> dict | None:
    date_m = re.search(r'<span class="create-time">([^<]+)</span>', html)
    paragraphs = re.findall(r'<p data-align[^>]*>(.*?)</p>', html, re.DOTALL)
    remote_images = re.findall(r'<img[^>]+src="(https://[^"]+doubanio[^"]+)"', html)
    remote_images = [
        i for i in remote_images
        if not i.endswith(".svg")
        and "/icon/" not in i
        and "new_menu" not in i
        and "/f/shire/" not in i
    ][:4]

    text = "\n".join(
        re.sub(r'<[^>]+>', '', p).strip()
        for p in paragraphs
        if re.sub(r'<[^>]+>', '', p).strip()
    )
    if not text:
        return None

    date_str, ts = "", 0
    if date_m:
        raw = date_m.group(1).strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            date_str = dt.strftime("%Y-%m-%d")
            ts = int(dt.timestamp())
        except ValueError:
            date_str = raw[:10]

    # Download images locally to avoid hotlink blocking
    local_images = []
    for img_url in remote_images:
        local = _download_image(img_url)
        if local:
            local_images.append(local)

    return {
        "id": f"douban_{tid}",
        "platform": "douban",
        "text": text,
        "images": local_images,
        "date": date_str,
        "timestamp": ts,
        "url": f"https://www.douban.com/topic/{tid}/",
    }


def fetch_posts(cookie: str) -> list[dict]:
    print("[douban] fetching statuses page …")
    try:
        html = _fetch(STATUSES_URL, cookie)
    except Exception as e:
        print(f"[douban] ERROR: {e}")
        return []

    ids = _topic_ids(html)
    print(f"[douban] found {len(ids)} topic IDs")

    posts = []
    for tid in ids:
        try:
            th = _fetch(TOPIC_URL.format(tid), cookie)
            post = _parse_topic(tid, th)
            if post:
                posts.append(post)
                print(f"[douban]   {post['date']} — {post['text'][:50]}…")
        except Exception as e:
            print(f"[douban]   skip {tid}: {e}")
        time.sleep(0.6)

    return posts
