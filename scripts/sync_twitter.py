#!/usr/bin/env python3
"""X (Twitter) sync via nitter RSS fallback instances."""

import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

USERNAME  = "Surudo1892"
MAX_POSTS = 10

NITTER_INSTANCES = [
    "https://nitter.privacyredirect.com",
    "https://nitter.poast.org",
    "https://nitter.net",
]

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


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
        title = (title_el.text or "") if title_el is not None else ""
        if title.startswith("RT by"):
            continue

        # Extract text (strip HTML)
        raw = (desc_el.text or "") if desc_el is not None else title
        text = re.sub(r'<[^>]+>', '', raw).strip()
        text = re.sub(r'\s+', ' ', text)
        if not text:
            continue

        # Extract images from description
        images = []
        if desc_el is not None and desc_el.text:
            images = re.findall(
                r'<img[^>]+src="(https://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                desc_el.text
            )

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
            "images": images[:4],
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
