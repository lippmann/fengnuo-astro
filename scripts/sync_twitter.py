#!/usr/bin/env python3
"""X (Twitter) sync via nitter RSS fallback instances."""

import hashlib
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote

USERNAME  = "Surudo1892"
MAX_POSTS = 10
IMG_DIR   = Path(__file__).parent.parent / "public" / "images" / "twitter"

NITTER_INSTANCES = [
    "https://nitter.privacyredirect.com",
    "https://nitter.poast.org",
    "https://nitter.net",
]

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def _nitter_to_twimg(url: str) -> str:
    """Convert nitter image URL to pbs.twimg.com direct URL."""
    path = re.sub(r'^https://nitter\.[^/]+/pic/', '', url)
    decoded = unquote(path)
    if decoded.startswith('pbs.twimg.com/'):
        return 'https://' + decoded
    return 'https://pbs.twimg.com/' + decoded


def _download_image(twimg_url: str) -> str | None:
    """Download a Twitter image locally, return public path or None."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ext = twimg_url.split('?')[0].rsplit('.', 1)[-1]
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        ext = 'jpg'
    fname = hashlib.md5(twimg_url.encode()).hexdigest() + '.' + ext
    dest = IMG_DIR / fname
    if dest.exists():
        return f'/images/twitter/{fname}'
    try:
        req = urllib.request.Request(twimg_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': 'https://x.com/',
        })
        with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
            dest.write_bytes(r.read())
        print(f'[twitter]     downloaded image → {fname}')
        return f'/images/twitter/{fname}'
    except Exception as e:
        print(f'[twitter]     image download failed {twimg_url}: {e}')
        return None


def _fetch_rss(instance: str) -> bytes | None:
    url = f"{instance}/{USERNAME}/rss"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; RSS reader)",
        "Accept": "application/rss+xml, application/xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
            return r.read()
    except Exception as e:
        print(f"[twitter]   {instance} failed: {e}")
        return None


def _parse_rss(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return []

    posts = []
    for item in channel.findall("item")[:MAX_POSTS]:
        title_el  = item.find("title")
        link_el   = item.find("link")
        desc_el   = item.find("description")
        date_el   = item.find("pubDate")
        guid_el   = item.find("guid")

        # Skip retweets
        title = (title_el.text or "").strip() if title_el is not None else ""
        if title.startswith("RT by"):
            continue

        # Extract text (strip HTML) — this is the full description including RT author/text
        raw = (desc_el.text or "") if desc_el is not None else title
        full_text = re.sub(r'<[^>]+>', '', raw).strip()
        full_text = re.sub(r'\s+', ' ', full_text)
        if not full_text:
            continue

        # nitter <title> = my comment (the part before the RT attribution)
        # nitter <description> = full text: "comment author (@handle) rt_text — url"
        # We store comment and rt_text separately for clean rendering.
        # Strip trailing nitter URL from full_text first.
        clean_text = re.sub(r'\s+—\s+https?://\S+$', '', full_text).strip()

        # Detect if this is a repost: look for "author (@handle) rt_text" pattern
        rt_m = re.search(r'^(.*?)\s+\(@([A-Za-z0-9_]{1,50})\)\s+(.+)$', clean_text, re.DOTALL)
        if rt_m and len(rt_m.group(3).strip()) >= 3:
            # title is my comment; strip it from before the RT attribution
            comment = title.strip()
            rt_author_raw = rt_m.group(1).strip()
            rt_handle = rt_m.group(2).strip()
            rt_text = rt_m.group(3).strip()
            # rt_author_raw may start with comment text; remove it
            if comment and rt_author_raw.startswith(comment):
                rt_author = rt_author_raw[len(comment):].strip()
            else:
                rt_author = rt_author_raw
            # Store structured fields
            text = json.dumps({
                "comment": comment,
                "rtAuthor": rt_author,
                "rtHandle": rt_handle,
                "rtText": rt_text,
            }, ensure_ascii=False)
        else:
            # Plain tweet — just use clean_text
            text = clean_text

        # Extract images from description, convert nitter → pbs.twimg.com, download locally
        images = []
        if desc_el is not None and desc_el.text:
            raw_imgs = re.findall(
                r'<img[^>]+src="(https://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                desc_el.text
            )
            for img_url in raw_imgs[:4]:
                twimg_url = _nitter_to_twimg(img_url)
                local = _download_image(twimg_url)
                if local:
                    images.append(local)

        # Parse date
        date_str, ts = "", 0
        if date_el is not None and date_el.text:
            try:
                dt = parsedate_to_datetime(date_el.text)
                date_str = dt.strftime("%Y-%m-%d")
                ts = int(dt.timestamp())
            except Exception:
                date_str = ""

        # Canonical URL (convert nitter link to x.com)
        link = (link_el.text or "") if link_el is not None else ""
        for inst in NITTER_INSTANCES:
            link = link.replace(inst, "https://x.com")
        link = re.sub(r'https://nitter\.[^/]+/', 'https://x.com/', link)
        link = link.split('#')[0]  # strip nitter fragment (#m)

        # ID from guid or link
        id_m = re.search(r'/status/(\d+)', link)
        post_id = f"twitter_{id_m.group(1)}" if id_m else f"twitter_{abs(hash(link))}"

        posts.append({
            "id": post_id,
            "platform": "twitter",
            "text": text,
            "images": images,
            "date": date_str,
            "timestamp": ts,
            "url": link,
        })

    return posts


def fetch_posts() -> list[dict]:
    print("[twitter] trying nitter instances …")
    for instance in NITTER_INSTANCES:
        print(f"[twitter]   trying {instance} …")
        xml_bytes = _fetch_rss(instance)
        if xml_bytes:
            try:
                posts = _parse_rss(xml_bytes)
                if posts:
                    print(f"[twitter] got {len(posts)} posts")
                    return posts
            except Exception as e:
                print(f"[twitter]   parse error: {e}")

    print("[twitter] all instances failed — skipping")
    return []
