#!/usr/bin/env python3
"""
patch-notes-rss/merge.py
Jay Respawns — Patch Notes, Firmware & Driver RSS Aggregator
Regenerated every 4h via GitHub Actions.

Architecture:
  Tier 1  — Direct Steam app news feeds (major titles, keyword-filtered)
  Tier 2  — Official non-Steam game/platform feeds (keyword-filtered)
  Tier 3  — Gaming press patch-note tag feeds (pre-filtered by outlet)
  Tier 4  — Firmware: consoles, PC handhelds, retro handhelds, GPU drivers
  Tier 5  — Mobile & gacha game updates (targeted Google News queries)
  Dynamic — Broad catch-all queries for new/unlisted releases
"""

import feedparser
import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# ── Keywords: applied to Tier 1 + 2 only (broad news feeds need filtering) ────
PATCH_KEYWORDS = [
    "patch notes", "patch note", "hotfix", "hot fix",
    "balance update", "balance patch", "balance changes", "balance change",
    "bug fix", "bugfix", "bug fixes", "performance update", "performance fix",
    "update v", " v1.", " v2.", " v3.", " v4.", " v0.",
    "game update", "content update", "season update", "live patch",
    "weekly update", "maintenance update", "server update",
    "firmware", "system software", "driver update", "driver release",
    "game ready driver", "adrenalin edition", "steamos update",
]

def is_patch_relevant(entry):
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return any(kw in text for kw in PATCH_KEYWORDS)

def parse_date(entry):
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime.datetime(*t[:6])
            except Exception:
                pass
    return datetime.datetime.min

# ── Tier 1: Steam app news feeds ───────────────────────────────────────────────
# RSS pattern: https://store.steampowered.com/feeds/news/app/{APPID}/
# Covers all game news — PATCH_KEYWORDS filters to patches/updates only.
STEAM_APPS = [
    # ── Shooters / FPS / TPS ──────────────────────────────────────────────────
    ("CS2",                             730),
    ("Apex Legends",                    1172470),
    ("PUBG: Battlegrounds",             578080),
    ("Halo Infinite",                   1240440),
    ("Rainbow Six Siege",               359550),
    ("Helldivers 2",                    553850),
    ("Hunt: Showdown 1896",             594650),
    ("The Finals",                      2073850),
    ("Gray Zone Warfare",               2479810),
    ("Ready or Not",                    1144200),
    ("Marvel Rivals",                   2767030),
    ("Deep Rock Galactic",              548430),
    ("DayZ",                            221100),
    ("Naraka: Bladepoint",              1172640),
    ("Payday 3",                        1272320),
    ("Enlisted",                        1138800),
    ("War Thunder",                     236390),
    ("World of Tanks",                  1407200),
    ("World of Warships",               552990),
    ("Planetside 2",                    218230),
    ("Squad",                           393380),

    # ── MOBAs ─────────────────────────────────────────────────────────────────
    ("Dota 2",                          570),
    ("Deadlock",                        1422450),
    ("Smite 2",                         2716310),
    ("Predecessor",                     1259420),

    # ── RPG / Open World ──────────────────────────────────────────────────────
    ("Elden Ring",                      1245620),
    ("Baldur's Gate 3",                 1086940),
    ("Cyberpunk 2077",                  1091500),
    ("Starfield",                       1716740),
    ("Monster Hunter Wilds",            2246340),
    ("Palworld",                        1623730),
    ("Dragon's Dogma 2",                2054970),
    ("V Rising",                        1604030),
    ("Remnant II",                      1282100),
    ("Wuthering Waves",                 2358720),
    ("Assassin's Creed Shadows",        2971790),

    # ── Live Service / MMO ────────────────────────────────────────────────────
    ("Destiny 2",                       1085660),
    ("Warframe",                        230410),
    ("The First Descendant",            2074920),
    ("Path of Exile 2",                 2694490),
    ("Elder Scrolls Online",            306130),
    ("Guild Wars 2",                    1284210),
    ("Lost Ark",                        1599340),
    ("Black Desert Online",             582660),
    ("New World: Aeternum",             1063730),
    ("RuneScape",                       1343400),
    ("Old School RuneScape",            1343370),
    ("Final Fantasy XIV",               39210),
    ("Albion Online",                   761634),
    ("Throne and Liberty",              2429290),

    # ── Survival / Sandbox ────────────────────────────────────────────────────
    ("Rust",                            252490),
    ("ARK: Survival Ascended",          2399830),
    ("Valheim",                         892970),
    ("Sons of the Forest",              1326470),
    ("Satisfactory",                    526870),
    ("Factorio",                        427520),
    ("Terraria",                        105600),
    ("Core Keeper",                     1621690),
    ("No Man's Sky",                    275850),
    ("7 Days to Die",                   251570),
    ("Subnautica 2",                    868060),
    ("Conan Exiles",                    440900),
    ("The Isle",                        376210),
    ("Enshrouded",                      1203220),

    # ── Strategy / RTS / 4X ───────────────────────────────────────────────────
    ("Age of Empires IV",               1466860),
    ("Civilization VII",                1295660),
    ("Company of Heroes 3",             1677280),
    ("Total War: Warhammer III",        1142710),
    ("Crusader Kings III",              1158310),
    ("Victoria 3",                      529340),
    ("StarCraft II",                    1466860),

    # ── Fighting Games ────────────────────────────────────────────────────────
    ("Street Fighter 6",                1353780),
    ("Tekken 8",                        1778820),
    ("Mortal Kombat 1",                 1971870),
    ("Guilty Gear: Strive",             1384160),
    ("MultiVersus",                     1818750),
    ("Granblue Fantasy Versus: Rising", 2125560),
    ("King of Fighters XV",             1498570),
    ("Under Night In-Birth II",         2313360),

    # ── Card / Deck Building ──────────────────────────────────────────────────
    ("Magic: The Gathering Arena",      2141910),
    ("Marvel Snap",                     1997040),

    # ── Sports / Racing ───────────────────────────────────────────────────────
    ("Rocket League",                   252950),
    ("eFootball",                       1360870),
    ("Forza Motorsport",                2229310),
    ("Forza Horizon 5",                 1551360),
    ("F1 25",                           3133470),

    # ── Horror / Co-op ────────────────────────────────────────────────────────
    ("Dead by Daylight",                381210),
    ("Phasmophobia",                    739630),
    ("Lethal Company",                  1966720),
    ("Content Warning",                 2881650),
    ("The Texas Chain Saw Massacre",    2298080),
    ("Back 4 Blood",                    924970),

    # ── Roguelikes / Indies (massive userbases) ───────────────────────────────
    ("Hades II",                        1145350),
    ("Dead Cells",                      588650),
    ("Risk of Rain 2",                  632360),
    ("Vampire Survivors",               1794680),
    ("Balatro",                         2379780),
    ("Slay the Spire",                  646570),

    # ── Other Major Titles ────────────────────────────────────────────────────
    ("GTA V / GTA Online",              271590),
    ("Red Dead Redemption 2",           1174180),
    ("Sea of Thieves",                  1172620),
    ("Among Us",                        945360),
    ("Fall Guys",                       1097150),
    ("Stumble Guys",                    1677740),
    ("Palia",                           2707930),
]

# ── Tier 2: Official non-Steam game & platform feeds (keyword filtered) ────────
OFFICIAL_FEEDS = [
    # Riot Games
    ("Valorant — Game Updates",         "https://playvalorant.com/en-us/news/game-updates/feed/"),
    ("League of Legends — News",        "https://www.leagueoflegends.com/en-us/news/feed/"),
    ("Teamfight Tactics — News",        "https://teamfighttactics.leagueoflegends.com/en-us/news/feed/"),
    ("Wild Rift — News",                "https://wildrift.leagueoflegends.com/en-us/news/feed/"),
    # Blizzard
    ("World of Warcraft — News",        "https://worldofwarcraft.blizzard.com/en-us/news/rss"),
    ("Overwatch 2 — News",              "https://overwatch.blizzard.com/en-us/news/rss"),
    ("Diablo IV — News",                "https://diablo.blizzard.com/en-us/news/rss"),
    ("Hearthstone — News",              "https://hearthstone.blizzard.com/en-us/news/rss"),
    # Bungie
    ("Destiny 2 — Bungie News",         "https://www.bungie.net/en/Rss/NewsByCategory?category=destiny"),
    # Console platforms (contain firmware + game updates)
    ("PlayStation Blog",                "https://blog.playstation.com/feed/"),
    ("Xbox Wire",                       "https://news.xbox.com/en-us/feed/"),
    ("Nintendo News",                   "https://www.nintendo.com/us/whatsnew/feed-en_US.xml"),
    # Steam Deck / SteamOS
    ("Steam Deck — Official Updates",   "https://store.steampowered.com/feeds/news/group/4145817/"),
    # Bethesda
    ("Bethesda News",                   "https://bethesda.net/en/rss"),
]

# ── Tier 3: Gaming press patch-note tag feeds (pre-filtered — no keyword check) ─
PRESS_PATCH_FEEDS = [
    ("PC Gamer — Patch Notes",          "https://www.pcgamer.com/tag/patch-notes/feed/"),
    ("Dot Esports — Patch Notes",       "https://dotesports.com/tag/patch-notes/feed/"),
    ("Rock Paper Shotgun — Patches",    "https://www.rockpapershotgun.com/tag/patches/feed/"),
    ("Eurogamer — Patch Notes",         "https://www.eurogamer.net/tag/patch-notes/feed/"),
    ("Kotaku — Patch Notes",            "https://kotaku.com/tag/patch-notes/feed/"),
    ("VG247 — Patch Notes",             "https://www.vg247.com/tag/patch-notes/feed/"),
    ("GamesRadar — Patch Notes",        "https://www.gamesradar.com/tag/patch-notes/feed/"),
    ("Destructoid — Patch Notes",       "https://www.destructoid.com/tag/patch-notes/feed/"),
    ("Dexerto — Updates",               "https://www.dexerto.com/gaming/feed/"),
    ("Push Square — Updates",           "https://www.pushsquare.com/news/patches/feed/"),
    ("Nintendo Life — Updates",         "https://www.nintendolife.com/news/patches/feed/"),
    ("Pure Xbox — Updates",             "https://www.purexbox.com/news/patches/feed/"),
]

# ── Tier 4a: GPU driver feeds (tech press + Google News) ──────────────────────
GPU_DRIVER_FEEDS = [
    ("TechPowerUp — GPU News",          "https://www.techpowerup.com/rss/news.xml"),
    ("Tom's Hardware — All",            "https://www.tomshardware.com/feeds/all"),
    ("Google News — NVIDIA Driver",     "https://news.google.com/rss/search?q=NVIDIA+GeForce+%22Game+Ready+Driver%22+release&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — AMD Driver",        "https://news.google.com/rss/search?q=AMD+Radeon+%22Adrenalin%22+driver+release&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Intel Arc Driver",  "https://news.google.com/rss/search?q=Intel+Arc+graphics+driver+release&hl=en-US&gl=US&ceid=US:en"),
]

# ── Tier 4b: Console & PC handheld firmware (Google News) ─────────────────────
CONSOLE_FIRMWARE_FEEDS = [
    ("Google News — PS5 Firmware",      "https://news.google.com/rss/search?q=PS5+%22system+software%22+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — PS4 Firmware",      "https://news.google.com/rss/search?q=PS4+%22system+software%22+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Xbox Firmware",     "https://news.google.com/rss/search?q=Xbox+%22system+update%22+firmware&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Switch Firmware",   "https://news.google.com/rss/search?q=Nintendo+Switch+%22system+update%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Switch 2 Firmware", "https://news.google.com/rss/search?q=%22Nintendo+Switch+2%22+system+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Steam Deck OS",     "https://news.google.com/rss/search?q=Steam+Deck+SteamOS+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Meta Quest",        "https://news.google.com/rss/search?q=Meta+Quest+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — ROG Ally",          "https://news.google.com/rss/search?q=%22ROG+Ally%22+firmware+BIOS+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Legion Go",         "https://news.google.com/rss/search?q=%22Legion+Go%22+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — GPD Win",           "https://news.google.com/rss/search?q=%22GPD+Win%22+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — OneXPlayer",        "https://news.google.com/rss/search?q=OneXPlayer+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — AOKZOE",            "https://news.google.com/rss/search?q=AOKZOE+firmware+update&hl=en-US&gl=US&ceid=US:en"),
]

# ── Tier 4c: Retro handheld firmware (Google News) ────────────────────────────
RETRO_HANDHELD_FEEDS = [
    ("Google News — Anbernic",          "https://news.google.com/rss/search?q=Anbernic+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Retroid Pocket",    "https://news.google.com/rss/search?q=%22Retroid+Pocket%22+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Miyoo",             "https://news.google.com/rss/search?q=Miyoo+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Powkiddy",          "https://news.google.com/rss/search?q=Powkiddy+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — AYN Odin",          "https://news.google.com/rss/search?q=%22AYN+Odin%22+firmware+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Trimui",            "https://news.google.com/rss/search?q=Trimui+firmware+update&hl=en-US&gl=US&ceid=US:en"),
]

# ── Tier 4d: Custom firmware / OS — GitHub releases.atom (no filter needed) ────
GITHUB_CFW_FEEDS = [
    ("muOS — Anbernic CFW",             "https://github.com/MustardOS/mustard/releases.atom"),
    ("ROCKNIX",                         "https://github.com/ROCKNIX/distribution/releases.atom"),
    ("Knulli CFW",                      "https://github.com/knulli-cfw/distribution/releases.atom"),
    ("Batocera Linux",                  "https://github.com/batocera-linux/batocera.linux/releases.atom"),
    ("ArkOS",                           "https://github.com/christianhaitian/arkos/releases.atom"),
    ("MinUI",                           "https://github.com/shauninman/MinUI/releases.atom"),
    ("RetroArch",                       "https://github.com/libretro/RetroArch/releases.atom"),
    ("EmuDeck",                         "https://github.com/EmuDeck/emudeck-electron/releases.atom"),
]

# ── Tier 5: Mobile & gacha updates (targeted Google News — no filter) ──────────
MOBILE_GACHA_FEEDS = [
    ("Google News — Genshin Impact",    "https://news.google.com/rss/search?q=Genshin+Impact+%22patch+notes%22+OR+%22version+update%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Honkai Star Rail",  "https://news.google.com/rss/search?q=%22Honkai+Star+Rail%22+%22patch+notes%22+OR+%22version+update%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Zenless Zone Zero", "https://news.google.com/rss/search?q=%22Zenless+Zone+Zero%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Wuthering Waves",   "https://news.google.com/rss/search?q=%22Wuthering+Waves%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Blue Archive",      "https://news.google.com/rss/search?q=%22Blue+Archive%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Arknights",         "https://news.google.com/rss/search?q=Arknights+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Nikke",             "https://news.google.com/rss/search?q=Nikke+%22Goddess+of+Victory%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — AFK Journey",       "https://news.google.com/rss/search?q=%22AFK+Journey%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Epic Seven",        "https://news.google.com/rss/search?q=%22Epic+Seven%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — PUBG Mobile",       "https://news.google.com/rss/search?q=%22PUBG+Mobile%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Free Fire",         "https://news.google.com/rss/search?q=%22Free+Fire%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — MLBB Updates",      "https://news.google.com/rss/search?q=%22Mobile+Legends%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — CoD Mobile",        "https://news.google.com/rss/search?q=%22Call+of+Duty+Mobile%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Diablo Immortal",   "https://news.google.com/rss/search?q=%22Diablo+Immortal%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Pokemon GO",        "https://news.google.com/rss/search?q=%22Pokemon+GO%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Wild Rift",         "https://news.google.com/rss/search?q=%22Wild+Rift%22+%22patch+notes%22+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Honor of Kings",    "https://news.google.com/rss/search?q=%22Honor+of+Kings%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Clash of Clans",    "https://news.google.com/rss/search?q=%22Clash+of+Clans%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Brawl Stars",       "https://news.google.com/rss/search?q=%22Brawl+Stars%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Clash Royale",      "https://news.google.com/rss/search?q=%22Clash+Royale%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Summoners War",     "https://news.google.com/rss/search?q=%22Summoners+War%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Limbus Company",    "https://news.google.com/rss/search?q=%22Limbus+Company%22+update+patch&hl=en-US&gl=US&ceid=US:en"),
]

# ── Dynamic: Broad catch-all — catches notable new releases automatically ───────
# Gaming press acts as notability filter: they only cover games worth covering.
BROAD_FEEDS = [
    # Non-Steam games not in Tier 1/2 above
    ("Google News — Fortnite Patch",    "https://news.google.com/rss/search?q=Fortnite+%22patch+notes%22+OR+%22update+v%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Valorant Patch",    "https://news.google.com/rss/search?q=Valorant+%22patch+notes%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — OW2 Patch",         "https://news.google.com/rss/search?q=%22Overwatch+2%22+%22patch+notes%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — CoD Patch",         "https://news.google.com/rss/search?q=%22Call+of+Duty%22+%22patch+notes%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — LoL Patch",         "https://news.google.com/rss/search?q=%22League+of+Legends%22+%22patch+notes%22&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — WoW Patch",         "https://news.google.com/rss/search?q=%22World+of+Warcraft%22+%22patch+notes%22+OR+hotfix&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Diablo IV Patch",   "https://news.google.com/rss/search?q=%22Diablo+IV%22+%22patch+notes%22+OR+hotfix&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — EA FC Patch",       "https://news.google.com/rss/search?q=%22EA+FC%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — NBA 2K Patch",      "https://news.google.com/rss/search?q=%22NBA+2K%22+%22patch+notes%22+OR+update&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Hearthstone Patch", "https://news.google.com/rss/search?q=Hearthstone+%22patch+notes%22+OR+%22balance+update%22&hl=en-US&gl=US&ceid=US:en"),
    # Generic sweep — catches any notable new release getting patch coverage
    ("Google News — Patch Notes 2026",  "https://news.google.com/rss/search?q=%22patch+notes%22+game+2026&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Hotfix 2026",       "https://news.google.com/rss/search?q=%22hotfix%22+game+2026&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Balance Update",    "https://news.google.com/rss/search?q=%22balance+update%22+game&hl=en-US&gl=US&ceid=US:en"),
    ("Google News — Season Update",     "https://news.google.com/rss/search?q=%22season+update%22+game+2026&hl=en-US&gl=US&ceid=US:en"),
]

# ── Aggregation ────────────────────────────────────────────────────────────────

items = []
seen_urls = set()

def add_items(feed_name, url, keyword_filter=False):
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0 (compatible; RSS aggregator)")
        count = 0
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in seen_urls:
                continue
            if keyword_filter and not is_patch_relevant(entry):
                continue
            seen_urls.add(link)
            items.append({
                "title":   entry.get("title", "No title"),
                "link":    link,
                "summary": entry.get("summary", ""),
                "date":    parse_date(entry),
                "source":  feed_name,
            })
            count += 1
        if count > 0:
            print(f"  OK  {feed_name}: {count} items")
    except Exception as e:
        print(f"  ERR {feed_name}: {e}")

print("=== Tier 1: Steam App Feeds ===")
for name, app_id in STEAM_APPS:
    if app_id is None:
        continue
    add_items(name, f"https://store.steampowered.com/feeds/news/app/{app_id}/", keyword_filter=True)

print("\n=== Tier 2: Official Non-Steam Feeds ===")
for name, url in OFFICIAL_FEEDS:
    add_items(name, url, keyword_filter=True)

print("\n=== Tier 3: Press Patch-Note Tags ===")
for name, url in PRESS_PATCH_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Tier 4a: GPU Driver Feeds ===")
for name, url in GPU_DRIVER_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Tier 4b: Console & PC Handheld Firmware ===")
for name, url in CONSOLE_FIRMWARE_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Tier 4c: Retro Handheld Firmware ===")
for name, url in RETRO_HANDHELD_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Tier 4d: Custom Firmware / OS (GitHub) ===")
for name, url in GITHUB_CFW_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Tier 5: Mobile & Gacha ===")
for name, url in MOBILE_GACHA_FEEDS:
    add_items(name, url, keyword_filter=False)

print("\n=== Dynamic: Broad Catch-All ===")
for name, url in BROAD_FEEDS:
    add_items(name, url, keyword_filter=False)

# ── Build RSS XML output ───────────────────────────────────────────────────────
items.sort(key=lambda x: x["date"], reverse=True)
items = items[:300]

rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")
SubElement(channel, "title").text = "Jay Respawns — Patch Notes, Firmware & Drivers"
SubElement(channel, "link").text = "https://jayrespawns.com"
SubElement(channel, "description").text = (
    "Aggregated patch notes, hotfixes, firmware and driver updates "
    "for games, consoles, handhelds and GPUs"
)
SubElement(channel, "lastBuildDate").text = (
    datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
)

for item in items:
    entry_el = SubElement(channel, "item")
    SubElement(entry_el, "title").text = item["title"]
    SubElement(entry_el, "link").text = item["link"]
    SubElement(entry_el, "description").text = item["summary"]
    SubElement(entry_el, "pubDate").text = item["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
    SubElement(entry_el, "source").text = item["source"]

xml_str = minidom.parseString(tostring(rss)).toprettyxml(indent="  ")
with open("feed.xml", "w", encoding="utf-8") as f:
    f.write(xml_str)

print(f"\nDone. {len(items)} items written to feed.xml.")
