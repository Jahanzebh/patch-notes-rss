#!/usr/bin/env python3
"""
check_patches.py — Jay Respawns Official Patch Notes RSS Generator
Replaces merge.py. Sources only from official developer/publisher sites.
Runs daily via GitHub Actions → writes feed.xml → n8n publishes one article/day.

Design:
  - games.json is the authoritative whitelist of tracked games + sources
  - Steam RSS (store.steampowered.com) and official RSS feeds only — no press feeds
  - Items filtered by PATCH_KW to avoid announcements/sale posts
  - Output RSS sorted by game priority (1=most_searched → 4=indie), then by date
  - n8n's EXTRACT_PN_CODE deduplicates against published WP posts, picks top item
  - Retry on n8n trigger failure (3 attempts, 60s apart)
"""

import json
import os
import re
import sys
import time
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ── Configuration ─────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
GAMES_FILE   = os.path.join(SCRIPT_DIR, "games.json")
LAST_SEEN    = os.path.join(SCRIPT_DIR, "last_seen.json")
FEED_OUT     = os.path.join(SCRIPT_DIR, "feed.xml")

MAX_AGE_HOURS  = 72        # items older than this are ignored
MAX_ITEMS_OUT  = 50        # max items in output feed
FETCH_TIMEOUT  = 15        # seconds per HTTP request
N8N_RETRIES    = 3
N8N_RETRY_WAIT = 60        # seconds between n8n trigger attempts

N8N_BASE_URL    = "https://n8n.jayrespawns.com"
N8N_WORKFLOW_ID = "uQi8fNQdKzNB9NER"
N8N_API_KEY     = os.environ.get("N8N_API_KEY", "")

# Keywords that confirm a post is actually patch notes (not a store update / trailer)
PATCH_KW = re.compile(
    r'patch|update|fix|hotfix|balance|maintenance|season|content update|'
    r'changelog|release notes|bug fix|version \d|v\d+\.\d|new season|'
    r'weekly update|daily update|tuning|rebalance|nerf|buff|rework',
    re.IGNORECASE
)

# Keywords that disqualify a post (DLC announcements, trailers, sales)
SKIP_KW = re.compile(
    r'\btrailer\b|\bteaser\b|\bannouncement\b|\bpre.?order\b|\bDLC\b|'
    r'\bexpansion\b|\bsale\b|\bdiscount\b|\bsteam deal\b|\bcoming soon\b|'
    r'\bearly access launch\b|\bfull release\b|\bnow available\b',
    re.IGNORECASE
)

UA = "Mozilla/5.0 (compatible; JayRespawns-PatchBot/1.1; +https://jayrespawns.com)"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_games():
    with open(GAMES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [g for g in data["games"] if g.get("active", True)]

def load_state():
    if os.path.exists(LAST_SEEN):
        with open(LAST_SEEN, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}}

def save_state(state):
    with open(LAST_SEEN, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def url_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def now_utc():
    return datetime.now(timezone.utc)

def parse_date(s):
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    fmts = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s[:len(fmt)+4].strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None

def is_recent(dt, hours=MAX_AGE_HOURS):
    if dt is None:
        return True  # assume recent if we can't parse date
    cutoff = now_utc() - timedelta(hours=hours)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= cutoff

def is_patch_content(title, summary=""):
    text = f"{title} {summary}"
    if SKIP_KW.search(title):
        return False
    return bool(PATCH_KW.search(text))

def http_get(url, timeout=FETCH_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        print(f"    WARN fetch failed ({url}): {e}", file=sys.stderr)
        return None

def rfc822_now():
    return now_utc().strftime("%a, %d %b %Y %H:%M:%S +0000")

def rfc822(dt):
    if dt is None:
        return rfc822_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

# ── Steam RSS ─────────────────────────────────────────────────────────────────

def fetch_steam(app_id, game_name):
    url = f"https://store.steampowered.com/feeds/news/app/{app_id}/?cc=US&l=english&count=10"
    raw = http_get(url)
    if not raw:
        return []
    items = []
    if HAS_FEEDPARSER:
        feed = feedparser.parse(raw)
        for e in feed.entries:
            title   = e.get("title", "")
            link    = e.get("link", "")
            summary = e.get("summary", "")
            pub     = parse_date(e.get("published", ""))
            if not is_recent(pub):
                continue
            if not is_patch_content(title, summary):
                continue
            items.append({"title": title, "link": link, "date": pub, "summary": summary[:500]})
    else:
        # minimal XML parse fallback
        try:
            root = ET.fromstring(raw)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for item in root.iter("item"):
                title   = (item.findtext("title") or "").strip()
                link    = (item.findtext("link") or "").strip()
                summary = (item.findtext("description") or "").strip()
                pub     = parse_date(item.findtext("pubDate") or "")
                if not is_recent(pub):
                    continue
                if not is_patch_content(title, summary):
                    continue
                items.append({"title": title, "link": link, "date": pub, "summary": summary[:500]})
        except Exception as e:
            print(f"    WARN XML parse failed for {game_name}: {e}", file=sys.stderr)
    return items

# ── Official RSS ──────────────────────────────────────────────────────────────

def fetch_official_rss(game):
    url = game["rss_url"]
    raw = http_get(url)
    if not raw:
        return []
    items = []
    kw_filter = game.get("rss_keyword_filter", False)
    keywords  = [k.lower() for k in game.get("rss_keywords", [])]

    if HAS_FEEDPARSER:
        feed = feedparser.parse(raw)
        for e in feed.entries:
            title   = e.get("title", "")
            link    = e.get("link", "")
            summary = e.get("summary", "")
            pub     = parse_date(e.get("published", ""))
            if not is_recent(pub):
                continue
            if kw_filter:
                text_lower = f"{title} {summary}".lower()
                if not any(k in text_lower for k in keywords):
                    continue
            else:
                if not is_patch_content(title, summary):
                    continue
            items.append({"title": title, "link": link, "date": pub, "summary": summary[:500]})
    else:
        try:
            root = ET.fromstring(raw)
            for item in root.iter("item"):
                title   = (item.findtext("title") or "").strip()
                link    = (item.findtext("link") or "").strip()
                summary = (item.findtext("description") or "").strip()
                pub     = parse_date(item.findtext("pubDate") or "")
                if not is_recent(pub):
                    continue
                if kw_filter:
                    text_lower = f"{title} {summary}".lower()
                    if not any(k in text_lower for k in keywords):
                        continue
                else:
                    if not is_patch_content(title, summary):
                        continue
                items.append({"title": title, "link": link, "date": pub, "summary": summary[:500]})
        except Exception as e:
            print(f"    WARN XML parse failed for {game['name']}: {e}", file=sys.stderr)
    return items

# ── HTML Scrapers ─────────────────────────────────────────────────────────────

def scrape_cod_patchnotes(game):
    if not HAS_BS4:
        print("    WARN BeautifulSoup not installed — skipping HTML scrape for COD", file=sys.stderr)
        return []
    raw = http_get(game["official_patch_url"])
    if not raw:
        return []
    soup = BeautifulSoup(raw, "html.parser")
    items = []
    # COD patch notes page lists cards with links to individual notes
    for card in soup.select("a[href*='/patchnotes/']")[:5]:
        href = card.get("href", "")
        if not href.startswith("http"):
            href = "https://www.callofduty.com" + href
        title_el = card.select_one("h2, h3, h4, .title, .card-title")
        title = title_el.get_text(strip=True) if title_el else card.get_text(strip=True)[:80]
        if not title or not is_patch_content(title):
            continue
        items.append({"title": title, "link": href, "date": None, "summary": ""})
    return items[:2]

def scrape_fortnite_patchnotes(game):
    if not HAS_BS4:
        print("    WARN BeautifulSoup not installed — skipping HTML scrape for Fortnite", file=sys.stderr)
        return []
    raw = http_get(game["official_patch_url"])
    if not raw:
        return []
    soup = BeautifulSoup(raw, "html.parser")
    items = []
    # Fortnite patch notes page has article cards
    for card in soup.select("a[href*='/patch-notes/']")[:5]:
        href = card.get("href", "")
        if not href.startswith("http"):
            href = "https://www.fortnite.com" + href
        title_el = card.select_one("h1, h2, h3, .patch-note-title, [class*='title']")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            title = card.get_text(strip=True)[:80]
        if not title or not is_patch_content(title):
            continue
        items.append({"title": title, "link": href, "date": None, "summary": ""})
    return items[:2]

def scrape_forza_support(game):
    if not HAS_BS4:
        print("    WARN BeautifulSoup not installed — skipping HTML scrape for Forza", file=sys.stderr)
        return []
    raw = http_get(game["official_patch_url"])
    if not raw:
        return []
    soup = BeautifulSoup(raw, "html.parser")
    items = []
    for link in soup.select(".article-list-item a, .article-list a")[:5]:
        href = link.get("href", "")
        if not href.startswith("http"):
            href = "https://support.forza.net" + href
        title = link.get_text(strip=True)
        if not title or not is_patch_content(title):
            continue
        items.append({"title": title, "link": href, "date": None, "summary": ""})
    return items[:2]

def scrape_ea_news(game):
    if not HAS_BS4:
        print("    WARN BeautifulSoup not installed — skipping HTML scrape for EA", file=sys.stderr)
        return []
    raw = http_get(game["official_patch_url"])
    if not raw:
        return []
    soup = BeautifulSoup(raw, "html.parser")
    items = []
    for card in soup.select("a[href]")[:20]:
        href = card.get("href", "")
        title = card.get_text(strip=True)
        if not title or len(title) < 10 or not is_patch_content(title):
            continue
        if not href.startswith("http"):
            href = "https://www.ea.com" + href
        items.append({"title": title, "link": href, "date": None, "summary": ""})
        if len(items) >= 2:
            break
    return items

def scrape_generic_news_page(game):
    if not HAS_BS4:
        print(f"    WARN BeautifulSoup not installed — skipping HTML scrape for {game['name']}", file=sys.stderr)
        return []
    raw = http_get(game["official_patch_url"])
    if not raw:
        return []
    soup = BeautifulSoup(raw, "html.parser")
    items = []
    # Look for article cards with patch-related titles
    base = "/".join(game["official_patch_url"].split("/")[:3])
    for tag in soup.select("a[href]"):
        title = tag.get_text(strip=True)
        href  = tag.get("href", "")
        if len(title) < 10 or len(title) > 200:
            continue
        if not is_patch_content(title):
            continue
        if not href.startswith("http"):
            href = base + href if href.startswith("/") else base + "/" + href
        items.append({"title": title, "link": href, "date": None, "summary": ""})
        if len(items) >= 3:
            break
    return items

HTML_SCRAPERS = {
    "cod_patchnotes":    scrape_cod_patchnotes,
    "fortnite_patchnotes": scrape_fortnite_patchnotes,
    "forza_support":     scrape_forza_support,
    "ea_news":           scrape_ea_news,
    "generic_news_page": scrape_generic_news_page,
}

# ── Fetch dispatcher ──────────────────────────────────────────────────────────

def fetch_game_items(game):
    stype = game["source_type"]
    name  = game["name"]
    try:
        if stype == "steam_rss":
            return fetch_steam(game["steam_app_id"], name)
        elif stype == "official_rss":
            return fetch_official_rss(game)
        elif stype == "html":
            scraper = HTML_SCRAPERS.get(game.get("html_extractor", "generic_news_page"))
            if scraper:
                return scraper(game)
            print(f"    WARN no scraper for {name} extractor '{game.get('html_extractor')}'", file=sys.stderr)
            return []
        else:
            print(f"    WARN unknown source_type '{stype}' for {name}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"    ERROR fetching {name}: {e}", file=sys.stderr)
        return []

# ── Deduplication ─────────────────────────────────────────────────────────────

def already_seen(url, state):
    return url_id(url) in state.get("seen", {})

def mark_seen(url, state, game_slug):
    state.setdefault("seen", {})[url_id(url)] = {
        "url": url,
        "slug": game_slug,
        "ts": now_utc().isoformat()
    }

def prune_seen(state, days=30):
    cutoff = now_utc() - timedelta(days=days)
    state["seen"] = {
        k: v for k, v in state.get("seen", {}).items()
        if parse_date(v.get("ts", "")) and parse_date(v["ts"]) >= cutoff
    }

# ── RSS builder ───────────────────────────────────────────────────────────────

def escape_xml(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_feed(output_items):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>Jay Respawns — Patch Notes (Official Sources Only)</title>',
        '    <link>https://jayrespawns.com</link>',
        '    <description>Official patch notes from developer and publisher sources. '
        'No press outlets. Updated daily.</description>',
        f'    <lastBuildDate>{rfc822_now()}</lastBuildDate>',
        '    <atom:link href="https://jahanzebh.github.io/patch-notes-rss/feed.xml" '
        'rel="self" type="application/rss+xml"/>',
    ]
    for item in output_items:
        title   = escape_xml(item["title"])
        link    = escape_xml(item["link"])
        summary = escape_xml(item.get("summary", ""))
        pub     = rfc822(item.get("date"))
        guid    = escape_xml(item["link"])
        cat     = escape_xml(item.get("game_name", ""))
        lines += [
            "    <item>",
            f"      <title>{title}</title>",
            f"      <link>{link}</link>",
            f"      <guid isPermaLink=\"true\">{guid}</guid>",
            f"      <pubDate>{pub}</pubDate>",
            f"      <category>{cat}</category>",
            f"      <description>{summary}</description>",
            "    </item>",
        ]
    lines += ["  </channel>", "</rss>"]
    return "\n".join(lines)

# ── n8n trigger ───────────────────────────────────────────────────────────────

def trigger_n8n():
    if not N8N_API_KEY:
        print("  INFO N8N_API_KEY not set — skipping n8n trigger", file=sys.stderr)
        return False
    url  = f"{N8N_BASE_URL}/api/v1/workflows/{N8N_WORKFLOW_ID}/run"
    data = json.dumps({}).encode()
    for attempt in range(1, N8N_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url, data=data, method="POST",
                headers={
                    "X-N8N-API-KEY": N8N_API_KEY,
                    "Content-Type":  "application/json",
                    "User-Agent":    UA,
                }
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.getcode()
                if status in (200, 201):
                    print(f"  OK n8n triggered (attempt {attempt}, HTTP {status})")
                    return True
                print(f"  WARN n8n trigger attempt {attempt}: HTTP {status}", file=sys.stderr)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            print(f"  WARN n8n trigger attempt {attempt}: HTTP {e.code} — {body}", file=sys.stderr)
        except Exception as e:
            print(f"  WARN n8n trigger attempt {attempt}: {e}", file=sys.stderr)
        if attempt < N8N_RETRIES:
            print(f"  INFO retrying n8n in {N8N_RETRY_WAIT}s…", file=sys.stderr)
            time.sleep(N8N_RETRY_WAIT)
    print("  ERROR n8n trigger failed after all retries", file=sys.stderr)
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[check_patches] {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  feedparser: {'yes' if HAS_FEEDPARSER else 'NO (fallback mode)'}")
    print(f"  beautifulsoup: {'yes' if HAS_BS4 else 'NO (HTML scrapers disabled)'}")

    games  = load_games()
    state  = load_state()
    prune_seen(state, days=30)

    print(f"  Checking {len(games)} active games…")

    all_new   = []   # items not yet seen, passes patch filter
    all_fresh = []   # items already in state (for backfill if nothing new)

    for game in games:
        print(f"  [{game['slug']}]", end=" ", flush=True)
        items = fetch_game_items(game)
        if not items:
            print("(no items)")
            continue

        new_count = 0
        for item in items:
            if not item.get("link"):
                continue
            seen = already_seen(item["link"], state)
            enriched = dict(item, game_slug=game["slug"], game_name=game["name"],
                            priority=game["priority"], wp_category=game["wp_category"])
            if not seen:
                all_new.append(enriched)
                new_count += 1
        print(f"{new_count} new / {len(items)} total")

    # Sort new items: priority ASC (1 first), then date DESC (newest first)
    def sort_key(x):
        d = x.get("date") or datetime.min.replace(tzinfo=timezone.utc)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (x["priority"], -d.timestamp())

    all_new.sort(key=sort_key)

    output_items = all_new[:MAX_ITEMS_OUT]

    # Mark all output items as seen so they're not repeated tomorrow
    for item in output_items:
        mark_seen(item["link"], state, item["game_slug"])

    save_state(state)

    feed_xml = build_feed(output_items)
    with open(FEED_OUT, "w", encoding="utf-8") as f:
        f.write(feed_xml)

    print(f"\n  Written {len(output_items)} items to feed.xml")
    if output_items:
        top = output_items[0]
        print(f"  Top item: [{top['game_name']} p{top['priority']}] {top['title']}")

    # Only trigger n8n if there's at least one new patch note
    if output_items:
        print("  Triggering n8n workflow…")
        trigger_n8n()
    else:
        print("  No new items — skipping n8n trigger")

    return 0 if output_items else 0  # always exit 0; empty feed is not a failure

if __name__ == "__main__":
    sys.exit(main())
