#!/usr/bin/env python3
"""WeChat Reading (微信读书) highlights/annotations sync.

Fetches highlights and personal annotations from the WeRead web API
and returns them as post dicts compatible with sync_all.py / feed.json.

Required env var:
  WEREAD_COOKIE  — full cookie string copied from browser devtools
                   e.g. "wr_skey=xxx; wr_vid=xxx; wr_uid=xxx; ..."

Usage (standalone):
  WEREAD_COOKIE="..." python weread_sync.py

Usage (from sync_all.py):
  from weread_sync import fetch_posts as fetch_weread
  new_posts.extend(fetch_weread(cookie))
"""

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL          = "https://i.weread.qq.com"
API_BASE_URL      = "https://weread.qq.com"
BOOK_URL_TEMPLATE = "https://weread.qq.com/web/bookDetail/{bookId}"

DEFAULT_DAYS      = 30   # look back this many days by default
REQUEST_DELAY     = 0.5  # seconds between API calls (be polite)

# ── TLS helper (same pattern as sync_douban.py) ──────────────────────────────

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode    = ssl.CERT_NONE


# ── HTTP helper ──────────────────────────────────────────────────────────────

# Mutable cookie jar — refreshed from set-cookie response headers
_cookie_jar: dict[str, str] = {}


def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """Parse 'k=v; k2=v2' cookie string into dict."""
    result = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


def _cookie_header() -> str:
    return "; ".join(f"{k}={v}" for k, v in _cookie_jar.items())


def _absorb_set_cookie(headers: dict):
    """Update _cookie_jar from a set-cookie response header."""
    sc = headers.get("set-cookie") or headers.get("Set-Cookie") or ""
    if not sc:
        return
    # set-cookie may be comma-joined multiple values
    for directive in sc.split(","):
        kv = directive.strip().split(";")[0].strip()
        if "=" in kv:
            k, _, v = kv.partition("=")
            _cookie_jar[k.strip()] = v.strip()


def _fetch_json(url: str) -> dict:
    """GET url with current cookie jar, absorb any cookie refresh, return JSON."""
    req = urllib.request.Request(url, headers={
        "Cookie":          _cookie_header(),
        "User-Agent":      (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer":         "https://weread.qq.com/",
        "Origin":          "https://weread.qq.com",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        raw = r.read().decode("utf-8", errors="replace")
        _absorb_set_cookie(dict(r.headers))
    data = json.loads(raw)
    # WeRead returns errcode -2012 for session expiry
    if isinstance(data, dict) and data.get("errcode") in (-2012, -2010):
        raise urllib.error.HTTPError(url, 401, f"WeRead session expired (errcode={data['errcode']})", {}, None)
    return data


# ── WeRead API calls ─────────────────────────────────────────────────────────

def _get_shelf(cookie: str) -> list[dict]:
    """Return list of book dicts using the /api/user/notebook endpoint (same as obsidian plugin)."""
    global _cookie_jar
    _cookie_jar = _parse_cookie_string(cookie)
    data = _fetch_json(f"{API_BASE_URL}/api/user/notebook")
    books = []
    for item in data.get("books", []):
        info = item.get("bookInfo") or item.get("book") or item
        if not info or not info.get("bookId"):
            continue
        books.append(info)
    return books


def _get_bookmarks(book_id: str, cookie: str) -> list[dict]:
    """Return raw bookmark (highlight) list for one book."""
    try:
        data = _fetch_json(f"{BASE_URL}/book/bookmarklist?bookId={book_id}")
        return data.get("updated", []) or data.get("bookmarks", [])
    except Exception as e:
        print(f"[weread]     bookmark fetch failed for {book_id}: {e}")
        return []


def _get_reviews(book_id: str, cookie: str) -> list[dict]:
    """Return personal note/review list for one book."""
    try:
        data = _fetch_json(
            f"{BASE_URL}/review/list?bookId={book_id}&listType=11&mine=1&synckey=0"
        )
        return data.get("reviews", [])
    except Exception as e:
        print(f"[weread]     review fetch failed for {book_id}: {e}")
        return []


# ── Data parsing ─────────────────────────────────────────────────────────────

_WEREAD_LOGO_SVG = (
    '<svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">'
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'M8.5 16.5v-9l7 4.5-7 4.5z"/>'
    '</svg>'
)

def _ts_to_date(ts: int) -> str:
    """Unix timestamp → 'YYYY-MM-DD' in local time."""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d")


def _clean_text(s: str) -> str:
    """Strip leading/trailing whitespace, collapse interior blank lines."""
    s = s.strip()
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s


def _entry_id(book_id: str, mark_id: str) -> str:
    return f"weread_{book_id}_{mark_id}"


def _parse_bookmark(bm: dict, book_title: str, book_author: str,
                    book_id: str, cutoff_ts: int) -> dict | None:
    """Turn a single bookmark dict into a feed post dict, or None if skipped."""
    create_time = bm.get("createTime", 0)
    if create_time < cutoff_ts:
        return None

    mark_text = _clean_text(bm.get("markText", ""))
    if not mark_text:
        return None

    mark_id   = str(bm.get("bookmarkId", bm.get("markId", abs(hash(mark_text)))))
    date_str  = _ts_to_date(create_time)
    book_url  = BOOK_URL_TEMPLATE.format(bookId=book_id)

    # Compose display text: "highlight" + optional chapter context
    chapter = bm.get("chapterTitle") or bm.get("chapterUid", "")
    prefix  = f"《{book_title}》"
    if book_author:
        prefix += f" — {book_author}"
    if chapter:
        prefix += f"\n[{chapter}]"

    text = f"{prefix}\n\n{mark_text}"

    return {
        "id":        _entry_id(book_id, mark_id),
        "platform":  "weread",
        "text":      text,
        "images":    [],
        "date":      date_str,
        "timestamp": create_time,
        "url":       book_url,
    }


def _parse_review(rv: dict, book_title: str, book_author: str,
                  book_id: str, cutoff_ts: int) -> dict | None:
    """Turn a single review/note dict into a feed post dict, or None if skipped."""
    # Reviews are nested: {"review": {...}}
    review = rv.get("review", rv)
    create_time = review.get("createTime", 0)
    if create_time < cutoff_ts:
        return None

    abstract = _clean_text(review.get("abstract", ""))   # the highlighted passage
    content  = _clean_text(review.get("content",  ""))   # the user's own note

    # Need at least one piece of text
    if not abstract and not content:
        return None

    review_id = str(review.get("reviewId", abs(hash(abstract + content))))
    date_str  = _ts_to_date(create_time)
    book_url  = BOOK_URL_TEMPLATE.format(bookId=book_id)

    prefix = f"《{book_title}》"
    if book_author:
        prefix += f" — {book_author}"

    parts = [prefix]
    if abstract:
        parts.append(f"\n{abstract}")
    if content:
        parts.append(f"\n💬 {content}")

    text = "\n".join(parts)

    return {
        "id":        _entry_id(book_id, f"review_{review_id}"),
        "platform":  "weread",
        "text":      text,
        "images":    [],
        "date":      date_str,
        "timestamp": create_time,
        "url":       book_url,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def fetch_posts(cookie: str, days: int = DEFAULT_DAYS) -> list[dict]:
    """Fetch WeRead highlights + notes from the last `days` days.

    Returns list of post dicts ready for merge() / feed.json.
    """
    if not cookie or not cookie.strip():
        print("[weread] ERROR: WEREAD_COOKIE is not set.")
        print("[weread]   Open weread.qq.com in Chrome, sign in, then copy the")
        print("[weread]   full Cookie header from any /i.weread.qq.com/ XHR request")
        print("[weread]   in DevTools → Network tab, and export it as WEREAD_COOKIE.")
        return []

    cutoff_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    posts: list[dict] = []

    # 1. Get recently read books
    print("[weread] fetching shelf / recent books …")
    try:
        books = _get_shelf(cookie)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"[weread] ERROR {e.code}: cookie is missing or expired.")
            print("[weread]   Go to weread.qq.com → DevTools → Application → Cookies")
            print("[weread]   Copy all wr_* cookie values and update WEREAD_COOKIE secret.")
        else:
            print(f"[weread] ERROR fetching shelf: {e}")
        return []
    except Exception as e:
        print(f"[weread] ERROR fetching shelf: {e}")
        return []

    print(f"[weread] found {len(books)} books on shelf")

    # 2. For each book, fetch highlights and notes
    for book in books:
        book_id    = book.get("bookId", "")
        book_title = book.get("title",  book_id)
        book_author = book.get("author", "")

        if not book_id:
            continue

        print(f"[weread]   processing 《{book_title}》 …")

        # Highlights / bookmarks
        time.sleep(REQUEST_DELAY)
        bms = _get_bookmarks(book_id, cookie)
        for bm in bms:
            post = _parse_bookmark(bm, book_title, book_author, book_id, cutoff_ts)
            if post:
                posts.append(post)

        # Personal notes / reviews
        time.sleep(REQUEST_DELAY)
        rvs = _get_reviews(book_id, cookie)
        for rv in rvs:
            post = _parse_review(rv, book_title, book_author, book_id, cutoff_ts)
            if post:
                posts.append(post)

    # Sort newest first
    posts.sort(key=lambda p: p.get("timestamp", 0), reverse=True)
    return posts


# ── Logo registration (called by sync_all.py after import) ───────────────────

WEREAD_LOGO = (
    "#1A7E4A",   # dark green, close to WeRead brand
    '<svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">'
    '<path d="M17.5 6.5C17.5 4.57 15.93 3 14 3s-3.5 1.57-3.5 3.5c0 .88.32 1.68.85 2.3'
    'C9.91 9.38 9 10.84 9 12.5c0 2.49 2.01 4.5 4.5 4.5s4.5-2.01 4.5-4.5'
    'c0-1.66-.91-3.12-2.35-3.7.53-.62.85-1.42.85-2.3z'
    'M14 5c.83 0 1.5.67 1.5 1.5S14.83 8 14 8s-1.5-.67-1.5-1.5S13.17 5 14 5z'
    'M13.5 15c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>'
    '<path d="M6.5 8C5.12 8 4 9.12 4 10.5S5.12 13 6.5 13 9 11.88 9 10.5 7.88 8 6.5 8z'
    'M6.5 11C6.22 11 6 10.78 6 10.5S6.22 10 6.5 10s.5.22.5.5-.22.5-.5.5z"/>'
    '</svg>'
)


# ── Standalone entry point ────────────────────────────────────────────────────

def main():
    import sys
    from pathlib import Path

    # Allow overriding look-back window via first positional arg
    days = DEFAULT_DAYS
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [days]")
            sys.exit(1)

    cookie = os.environ.get("WEREAD_COOKIE", "")
    posts  = fetch_posts(cookie, days=days)

    if not posts:
        print("[weread] no highlights found (or auth failed).")
        sys.exit(0)

    print(f"\n[weread] fetched {len(posts)} highlights/notes in the last {days} days:\n")
    for p in posts:
        preview = p["text"].replace("\n", " ")[:80]
        print(f"  {p['date']}  {preview}…")

    # Optionally integrate into feed.json when run standalone
    root      = Path(__file__).parent.parent
    feed_file = root / "content/says/feed.json"

    if not feed_file.exists():
        print("\n[weread] feed.json not found — run sync_all.py to initialise the feed.")
        sys.exit(0)

    existing  = json.loads(feed_file.read_text(encoding="utf-8"))
    by_id     = {p["id"]: p for p in existing}
    new_count = 0
    for p in posts:
        if p["id"] not in by_id:
            by_id[p["id"]] = p
            new_count += 1
        else:
            by_id[p["id"]] = p   # refresh existing entry

    if new_count == 0:
        print("\n[weread] all entries already in feed — nothing to add.")
        sys.exit(0)

    merged = sorted(by_id.values(), key=lambda p: p.get("timestamp", 0), reverse=True)
    feed_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[weread] +{new_count} new entries written to feed.json")
    print("[weread] run sync_all.py (or its render step) to rebuild says/index.md")


if __name__ == "__main__":
    main()
