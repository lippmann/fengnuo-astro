#!/usr/bin/env python3
"""Push new feed entries to flomo via its API webhook."""

import json
import re
import ssl
import urllib.request
from pathlib import Path

# File that records IDs already pushed to flomo (lives next to this script)
PUSHED_IDS_FILE = Path(__file__).parent / ".flomo_pushed_ids.json"

_SSL = ssl.create_default_context()


def _load_pushed_ids() -> set[str]:
    if PUSHED_IDS_FILE.exists():
        return set(json.loads(PUSHED_IDS_FILE.read_text()))
    return set()


def _save_pushed_ids(ids: set[str]):
    PUSHED_IDS_FILE.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2))


def _format(item: dict) -> str:
    platform = item.get("platform", "")
    text = item.get("text", "")
    date = item.get("date", "")
    url = item.get("url", "")

    if platform == "weread":
        lines = text.split("\n")
        book_line = lines[0] if lines else ""
        rest = "\n".join(lines[1:]).strip()
        if "💬" in rest:
            idx = rest.index("💬")
            highlight = rest[:idx].strip()
            annotation = rest[idx + len("💬"):].strip()
            parts = []
            if annotation:
                parts.append(annotation)
            if highlight:
                parts.append(f"> {highlight}")
            parts.append(f"——{book_line}")
            return "\n".join(parts) + "\n#读书笔记"
        else:
            highlight = re.sub(r"^\[.*?\]\n+", "", rest).strip()
            return f"> {highlight}\n\n——{book_line}\n#读书笔记"

    if platform == "twitter":
        # New JSON-structured format
        if text.strip().startswith("{"):
            try:
                tw = json.loads(text)
                comment = tw.get("comment", "")
                rt_author = tw.get("rtAuthor", "")
                rt_handle = tw.get("rtHandle", "")
                rt_text = tw.get("rtText", "")
                parts = []
                if comment:
                    parts.append(comment)
                if rt_author or rt_handle:
                    parts.append(f"**{rt_author}** @{rt_handle}")
                if rt_text:
                    parts.append(f"> {rt_text}")
                if url:
                    parts.append(url)
                return "\n\n".join(parts) + "\n#推特博文"
            except json.JSONDecodeError:
                pass
        # Plain tweet
        content = re.sub(r"\s+—\s+https?://\S+$", "", text).strip()
        return f"{content}\n\n{url}\n#推特博文" if url else f"{content}\n#推特博文"

    if platform == "douban":
        return f"{text}\n\n{url}\n#豆瓣广播" if url else f"{text}\n#豆瓣广播"

    return text


def push_new_posts(feed: list[dict], api_url: str, dry_run: bool = False) -> int:
    """Push entries not yet sent to flomo. Returns count of pushed items."""
    pushed_ids = _load_pushed_ids()
    count = 0

    for item in feed:
        item_id = item.get("id", "")
        if not item_id or item_id in pushed_ids:
            continue

        content = _format(item).strip()
        if not content:
            continue

        if dry_run:
            print(f"[flomo] DRY RUN — would push {item_id}:\n{content[:120]}…\n")
            pushed_ids.add(item_id)
            count += 1
            continue

        try:
            body = json.dumps({"content": content}, ensure_ascii=False).encode()
            req = urllib.request.Request(
                api_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10, context=_SSL) as r:
                resp = json.loads(r.read())
            if resp.get("code") == 0:
                pushed_ids.add(item_id)
                count += 1
                print(f"[flomo] pushed {item_id} ({item.get('platform')} {item.get('date')})")
            else:
                print(f"[flomo] API error for {item_id}: {resp}")
        except Exception as e:
            print(f"[flomo] failed {item_id}: {e}")

    _save_pushed_ids(pushed_ids)
    return count
