#!/usr/bin/env python3
"""Import writing articles from Obsidian → src/content/writing/"""

import os, re, shutil, textwrap
from pathlib import Path
from datetime import datetime

SRC_BASE = Path("/Users/liurui28/Library/CloudStorage/Dropbox/Obsidian/lr's notes/Writing/Nonfiction writing/for media")
VAULT_ROOT = Path("/Users/liurui28/Library/CloudStorage/Dropbox/Obsidian/lr's notes")
DEST = Path(__file__).parent.parent / "src/content/writing"
PUBLIC_IMG = Path(__file__).parent.parent / "public/images/writing"

MEDIA_MAP = {
    "浪潮作品":     ("浪潮",     "lc"),
    "答案如下作品":  ("答案如下",  "daxr"),
    "真故研究室作品": ("真故研究室", "zgyjss"),
    "回声作品":     ("回声",     "hs"),
}


# ── Date parsing ──────────────────────────────────────────────

def parse_yymmdd(s):
    """Parse 6-digit YYMMDD → datetime. YY >= 50 treated as 19xx."""
    yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
    year = 1900 + yy if yy >= 50 else 2000 + yy
    try:
        return datetime(year, mm, dd)
    except ValueError:
        return None


def extract_date_from_filename(fname, media_abbrev):
    """Return (datetime, clean_title) from filename."""
    stem = Path(fname).stem

    # [浪潮][YYMMDD...] title  or  [浪潮][YYMMDD label] title
    m = re.match(r'^\[.*?\]\[(\d{6})', stem)
    if m:
        dt = parse_yymmdd(m.group(1))
        title = re.sub(r'^\[.*?\]\[.*?\]\s*', '', stem).strip()
        return dt, clean_title(title)

    # [回声]YYMMDD title
    m = re.match(r'^\[.*?\](\d{6})(.*)', stem)
    if m:
        dt = parse_yymmdd(m.group(1))
        title = m.group(2).strip()
        return dt, clean_title(title)

    # YYMMDD title (答案如下, some 浪潮)
    m = re.match(r'^(\d{6})(.*)', stem)
    if m:
        dt = parse_yymmdd(m.group(1))
        title = m.group(2).strip()
        return dt, clean_title(title)

    return None, clean_title(stem)


def clean_title(title):
    """Remove ｜文字稿 / ｜文字版 / ｜答案如下 / 空格+文字稿 suffixes."""
    title = re.sub(r'[｜|].*$', '', title)
    title = re.sub(r'\s+(文字稿|文字版|答案如下)\s*$', '', title)
    return title.strip()


def resolve_local_image(img_ref, article_dir):
    """Find the actual image file by searching parent Attachments folders."""
    # Try direct resolution first
    direct = (article_dir / img_ref).resolve()
    if direct.exists():
        return direct
    # Extract just the filename and search upward
    fname = Path(img_ref).name
    d = article_dir
    for _ in range(6):
        candidate = d / 'Attachments' / fname
        if candidate.exists():
            return candidate
        d = d.parent
    # Try vault root Attachments
    candidate = VAULT_ROOT / 'Attachments' / fname
    if candidate.exists():
        return candidate
    return None


def sanitize_body(body, article_dir):
    """Strip local image references and Obsidian-specific syntax from body.
    Copies resolvable local images to public/images/writing/ and rewrites paths."""
    PUBLIC_IMG.mkdir(parents=True, exist_ok=True)
    lines = body.splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        # Handle image-only lines
        if re.match(r'^!\[.*?\]\(', stripped):
            # Extract all images from this line
            def replace_img(m):
                alt = m.group(1)
                src = m.group(2)
                if src.startswith('http'):
                    return m.group(0)  # keep http images unchanged
                local_path = resolve_local_image(src, article_dir)
                if local_path:
                    dest_fname = local_path.name
                    dest_path = PUBLIC_IMG / dest_fname
                    if not dest_path.exists():
                        try:
                            shutil.copy2(local_path, dest_path)
                        except Exception:
                            return ''
                    return f'![{alt}](/images/writing/{dest_fname})'
                return ''  # can't resolve — drop it
            new_line = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img, line)
            if new_line.strip():
                out.append(new_line)
            continue
        # Remove Obsidian embed syntax ![[...]]
        line = re.sub(r'!\[\[[^\]]*\]\]', '', line)
        # Remove Obsidian attribute syntax {width=...}
        line = re.sub(r'\{[^}]*width[^}]*\}', '', line)
        out.append(line)
    return '\n'.join(out)



def extract_date_from_body(body):
    """Parse *YYYY 年 M 月 D 日* pattern from WeChat article body."""
    m = re.search(r'\*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', body)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


# ── Description extraction ────────────────────────────────────

def extract_description(body):
    """First substantial paragraph from article body, max 120 chars."""
    lines = body.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            continue
        if re.match(r'^!\[', line):
            continue
        if re.match(r'^原创\s', line):
            continue
        if re.match(r'^\*\*撰文', line):
            continue
        if re.match(r'^\*\*编辑', line):
            continue
        if re.match(r'^\*\*出品', line):
            continue
        if re.match(r'^\{width=', line):
            continue
        # skip lines that are only bold wrapper e.g. "**出品 | 浪潮**"
        stripped = re.sub(r'\*+', '', line).strip()
        if not stripped or re.match(r'^出品\s*[|｜]', stripped) or re.match(r'^撰文\s*[|｜]', stripped):
            continue
        # strip markdown formatting
        text = re.sub(r'\*+', '', line)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)  # images
        text = re.sub(r'\{[^}]+\}', '', text)  # obsidian attrs
        text = text.strip()
        if len(text) > 10:
            return text[:120] + ('…' if len(text) > 120 else '')
    return ''


# ── Frontmatter parsing ──────────────────────────────────────

def split_frontmatter(content):
    """Return (frontmatter_str, body) or ('', content).
    Also strips Date:/Link:/Tags: pseudo-frontmatter used in older 浪潮 files."""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return parts[1], parts[2]

    # Handle Date:/Link:/Tags: pseudo-frontmatter (no dashes)
    lines = content.splitlines()
    header_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        if re.match(r'^(Date|Link|Tags|Author):', line):
            header_lines.append(line)
            body_start = i + 1
        elif header_lines and line.strip() == '':
            body_start = i + 1
            break
        elif not header_lines:
            break

    if header_lines:
        fm = '\n'.join(header_lines)
        body = '\n'.join(lines[body_start:])
        return fm, body

    return '', content


# ── Main ──────────────────────────────────────────────────────

def process_folder(folder_name, media_label, media_abbrev, counters):
    src_dir = SRC_BASE / folder_name
    results = []

    for fname in sorted(os.listdir(src_dir)):
        if not fname.endswith('.md'):
            continue

        src_path = src_dir / fname
        raw = src_path.read_text(encoding='utf-8')

        fm_raw, body = split_frontmatter(raw)

        # Determine title & date
        if isinstance(fm_raw, str) and 'title:' in fm_raw:
            # Existing YAML frontmatter (答案如下, 真故研究室)
            title_m = re.search(r'^title:\s*"?(.+?)"?\s*$', fm_raw, re.MULTILINE)
            raw_title = title_m.group(1).strip('"') if title_m else Path(fname).stem
            title = clean_title(raw_title)
            # try date from frontmatter first
            date_m = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', fm_raw, re.MULTILINE)
            if date_m:
                dt = datetime.strptime(date_m.group(1), '%Y-%m-%d')
            else:
                dt = extract_date_from_body(body)
                if not dt:
                    dt = datetime(2020, 1, 1)
            desc_m = re.search(r'^description:\s*"?(.+?)"?\s*$', fm_raw, re.MULTILINE)
            description = desc_m.group(1).strip('"') if desc_m else extract_description(body)
        elif isinstance(fm_raw, str) and 'Date:' in fm_raw:
            # Pseudo-frontmatter (older 浪潮 format)
            date_m = re.search(r'^Date:\s*(\d{4}-\d{2}-\d{2})', fm_raw, re.MULTILINE)
            if date_m:
                dt = datetime.strptime(date_m.group(1), '%Y-%m-%d')
            else:
                dt, _ = extract_date_from_filename(fname, media_abbrev)
                if not dt:
                    dt = datetime(2020, 1, 1)
            _, title = extract_date_from_filename(fname, media_abbrev)
            description = extract_description(body)
        else:
            # No frontmatter — parse from filename
            dt, title = extract_date_from_filename(fname, media_abbrev)
            if not dt:
                dt = datetime(2020, 1, 1)
            description = extract_description(body)

        # Strip all quote variants using unicode escapes
        _QUOT = str.maketrans('', '', chr(0x22) + chr(0x201c) + chr(0x201d) + chr(0x2018) + chr(0x2019))
        def strip_quotes(s: str) -> str:
            return s.translate(_QUOT).strip()
        title = strip_quotes(title)
        description = strip_quotes(description) if description else ''

        date_str = dt.strftime('%Y-%m-%d')

        # Generate slug
        counters[media_abbrev] = counters.get(media_abbrev, 0) + 1
        idx = counters[media_abbrev]
        slug = f"{media_abbrev}-{idx:03d}"

        # Build output content — sanitize body and resolve local images
        clean_body = sanitize_body(body, src_path.parent)
        fm_lines = [
            '---',
            f'title: "{title}"',
            f'date: {date_str}',
            f'media: "{media_label}"',
            f'description: "{description}"',
            '---',
            '',
        ]
        output = '\n'.join(fm_lines) + clean_body

        results.append((dt, slug, output))

    # Sort by date ascending
    results.sort(key=lambda x: x[0])
    return results


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    # Clear existing writing content
    for f in DEST.glob('*.md'):
        f.unlink()

    counters = {}
    all_items = []

    for folder_name, (media_label, media_abbrev) in MEDIA_MAP.items():
        items = process_folder(folder_name, media_label, media_abbrev, counters)
        all_items.extend(items)
        print(f"{media_label}: {len(items)} articles")

    # Write files
    for dt, slug, content in all_items:
        out_path = DEST / f"{slug}.md"
        out_path.write_text(content, encoding='utf-8')

    print(f"\nTotal: {len(all_items)} articles written to {DEST}")


if __name__ == '__main__':
    main()
