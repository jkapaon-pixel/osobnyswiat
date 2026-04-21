#!/usr/bin/env python3
"""
Osobny Świat - Blog Scraper & Static Site Generator
Scrapes strachowka.blogspot.com and generates a modern static website.

Usage:
  pip install requests beautifulsoup4 lxml
  python scraper_and_generator.py

Output:
  Creates a folder called 'osobny_swiat_site/' with the complete website.
  Upload the contents of that folder to any free hosting (e.g. Netlify, GitHub Pages).
"""

import requests
import json
import os
import re
import time
import shutil
from datetime import datetime
from xml.etree import ElementTree as ET
from html import unescape
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
BLOG_URL    = "https://strachowka.blogspot.com"
FEED_URL    = f"{BLOG_URL}/feeds/posts/default"
OUTPUT_DIR  = Path("osobny_swiat_site")
MAX_RESULTS = 150   # Blogger API max per request
DELAY       = 0.5   # seconds between requests (be polite)

NAMESPACES = {
    "atom":   "http://www.w3.org/2005/Atom",
    "gd":     "http://schemas.google.com/g/2005",
    "thr":    "http://purl.org/syndication/thread/1.0",
    "media":  "http://search.yahoo.com/mrss/",
}
# ────────────────────────────────────────────────────────────────────────────


def slug(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower()
    text = re.sub(r"[ąàáâãäå]", "a", text)
    text = re.sub(r"[ćç]", "c", text)
    text = re.sub(r"[ęèéêë]", "e", text)
    text = re.sub(r"[łl]", "l", text)
    text = re.sub(r"[ńñ]", "n", text)
    text = re.sub(r"[óòôõöø]", "o", text)
    text = re.sub(r"[śšß]", "s", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[źżž]", "z", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:80]


def fetch_all_posts():
    """Fetch every post from the Blogger Atom feed using pagination."""
    posts = []
    start_index = 1

    print("📥 Fetching posts from Blogger feed...")
    while True:
        url = f"{FEED_URL}?max-results={MAX_RESULTS}&start-index={start_index}&alt=atom"
        print(f"   → Fetching posts {start_index} – {start_index + MAX_RESULTS - 1}...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/atom+xml,application/xml,text/xml,*/*",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"   ✗ Error: {e}")
            break

        root = ET.fromstring(resp.content)

        entries = root.findall("atom:entry", NAMESPACES)
        if not entries:
            break  # no more posts

        for entry in entries:
            title_el = entry.find("atom:title", NAMESPACES)
            content_el = entry.find("atom:content", NAMESPACES)
            published_el = entry.find("atom:published", NAMESPACES)
            updated_el = entry.find("atom:updated", NAMESPACES)
            id_el = entry.find("atom:id", NAMESPACES)

            # Get the link to the post
            link = ""
            for link_el in entry.findall("atom:link", NAMESPACES):
                if link_el.get("rel") == "alternate":
                    link = link_el.get("href", "")
                    break

            # Get labels/tags
            labels = []
            for cat_el in entry.findall("atom:category", NAMESPACES):
                term = cat_el.get("term", "")
                if term and "http" not in term:
                    labels.append(term)

            title = title_el.text if title_el is not None else "Bez tytułu"
            content = content_el.text if content_el is not None else ""
            published = published_el.text if published_el is not None else ""
            post_id = id_el.text if id_el is not None else ""

            posts.append({
                "id": post_id,
                "title": title or "Bez tytułu",
                "content": content or "",
                "published": published,
                "link": link,
                "labels": labels,
                "slug": slug(title or "post") + "-" + published[:10].replace("-", "") if title else "post",
            })

        # Check if there are more pages
        next_link = None
        for link_el in root.findall("atom:link", NAMESPACES):
            if link_el.get("rel") == "next":
                next_link = link_el.get("href")
                break

        if next_link is None:
            break

        start_index += MAX_RESULTS
        time.sleep(DELAY)

    print(f"✅ Fetched {len(posts)} posts total.")
    return posts


def format_date(iso_date: str) -> str:
    """Format ISO date for display."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        months_pl = [
            "", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
            "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
        ]
        return f"{dt.day} {months_pl[dt.month]} {dt.year}"
    except Exception:
        return iso_date[:10] if iso_date else ""


def format_date_short(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_date[:10] if iso_date else ""


# ── HTML TEMPLATES ───────────────────────────────────────────────────────────


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400;1,600&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,300;1,400&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body { background: #f7f3ed; color: #1c1916; font-family: 'Crimson Pro', Georgia, serif; font-size: 19px; line-height: 1.72; -webkit-font-smoothing: antialiased; }
a { color: inherit; text-decoration: none; }

.site-header { background: #2d4a3e; padding: 0 2rem; }
.header-top { max-width: 1080px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0.55rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
.header-top span { font-family: 'DM Sans', sans-serif; font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; color: rgba(255,255,255,0.35); }
.header-tags { display: flex; gap: 1.5rem; }

.masthead-inner { max-width: 1080px; margin: 0 auto; position: relative; z-index: 1; padding: 0 0; }
.masthead-top { display: flex; align-items: flex-start; justify-content: space-between; padding-top: 2.5rem; margin-bottom: 1.5rem; }
.masthead-label { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase; color: rgba(255,255,255,0.3); border: 1px solid rgba(255,255,255,0.15); padding: 0.3rem 0.7rem; display: inline-block; }
.masthead-issue { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(255,255,255,0.25); text-align: right; line-height: 1.8; }
.masthead-name { font-family: 'Playfair Display', serif; font-weight: 400; font-style: italic; font-size: clamp(3rem, 8vw, 6.5rem); color: #f7f3ed; line-height: 0.92; letter-spacing: -0.03em; display: block; margin-bottom: 1.25rem; }
.masthead-name:hover { opacity: 0.85; }
.masthead-tagline { font-family: 'Crimson Pro', serif; font-style: italic; font-size: 1.1rem; color: rgba(247,243,237,0.4); letter-spacing: 0.02em; padding-bottom: 1.75rem; border-bottom: 1px solid rgba(255,255,255,0.12); }

.sitenav { display: flex; justify-content: center; }
.sitenav a { font-family: 'DM Sans', sans-serif; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(255,255,255,0.45); padding: 0.8rem 1.2rem; display: inline-block; border-bottom: 2px solid transparent; transition: color 0.15s, border-color 0.15s; }
.sitenav a:hover { color: rgba(255,255,255,0.8); }
.sitenav a.active { color: #f7f3ed; border-bottom-color: #c8a84b; }

.page-wrap { max-width: 1080px; margin: 0 auto; padding: 0 2rem; }

/* FEATURED */
.featured { padding: 3rem 0; border-bottom: 1px solid #d4cec4; display: grid; grid-template-columns: 1fr 1fr; gap: 3.5rem; align-items: start; }
.feat-num { font-family: 'Playfair Display', serif; font-size: 5rem; font-weight: 700; color: #e8e2d8; line-height: 1; margin-bottom: 0.5rem; display: block; }
.feat-label { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; font-weight: 500; letter-spacing: 0.2em; text-transform: uppercase; color: #8a6a30; margin-bottom: 0.85rem; display: flex; align-items: center; gap: 0.6rem; }
.feat-label::after { content: ''; flex: 0 0 20px; height: 1px; background: #8a6a30; }
.feat-title { font-family: 'Playfair Display', serif; font-weight: 500; font-size: clamp(1.7rem, 3vw, 2.5rem); line-height: 1.2; letter-spacing: -0.02em; color: #1c1916; margin-bottom: 1rem; }
.feat-title a:hover { color: #2d4a3e; }
.feat-excerpt { font-family: 'Crimson Pro', serif; font-size: 1.05rem; line-height: 1.78; color: #4a4540; margin-bottom: 1.25rem; }
.feat-byline { font-family: 'DM Sans', sans-serif; font-size: 0.75rem; color: #9a9590; display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.feat-byline .sep { color: #d4cec4; }
.feat-read { font-family: 'DM Sans', sans-serif; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: #2d4a3e; border-bottom: 1px solid rgba(45,74,62,0.35); }
.feat-read:hover { opacity: 0.65; }
.feat-poem-block { background: #2d4a3e; padding: 2.5rem; position: relative; margin-top: 0.5rem; }
.feat-poem-block::before { content: ''; position: absolute; top: 0.75rem; left: 0.75rem; right: -0.75rem; bottom: -0.75rem; border: 1px solid #c8a84b; z-index: -1; }
.feat-poem-text { font-family: 'Crimson Pro', serif; font-style: italic; font-size: 1.05rem; line-height: 2; color: rgba(247,243,237,0.8); white-space: pre-line; }
.feat-poem-cite { display: block; font-family: 'DM Sans', sans-serif; font-size: 0.62rem; letter-spacing: 0.1em; text-transform: uppercase; color: #c8a84b; margin-top: 1.25rem; opacity: 0.8; }

/* SECTION LABEL */
.sec-label { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; font-weight: 500; letter-spacing: 0.22em; text-transform: uppercase; color: #9a9590; padding: 2.5rem 0 1.5rem; display: flex; align-items: center; gap: 1rem; justify-content: space-between; }
.sec-label::before { content: ''; flex: 0 0 2rem; height: 1px; background: #c8a84b; }
.sec-label a { color: #2d4a3e; border-bottom: 1px solid rgba(45,74,62,0.3); font-size: 0.65rem; }
.sec-label a:hover { opacity: 0.7; }

/* POST TILES */
.post-tiles { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2rem 2.5rem; padding-bottom: 3rem; border-bottom: 1px solid #d4cec4; }
.tile { padding-bottom: 2rem; border-bottom: 1px solid #e8e2d8; }
.tile-num { font-family: 'Playfair Display', serif; font-size: 2.5rem; font-weight: 700; color: #e8e2d8; line-height: 1; margin-bottom: 0.3rem; display: block; }
.tile-tag { font-family: 'DM Sans', sans-serif; font-size: 0.62rem; font-weight: 500; letter-spacing: 0.18em; text-transform: uppercase; color: #8a6a30; margin-bottom: 0.4rem; display: block; }
.tile-date { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; color: #9a9590; margin-bottom: 0.5rem; display: block; }
.tile-title { font-family: 'Playfair Display', serif; font-weight: 400; font-size: 1.1rem; line-height: 1.3; letter-spacing: -0.01em; color: #1c1916; margin-bottom: 0.6rem; }
.tile-title a:hover { color: #2d4a3e; }
.tile-excerpt { font-family: 'Crimson Pro', serif; font-size: 0.92rem; line-height: 1.65; color: #6a6560; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.tile-wide { grid-column: span 2; display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; padding-bottom: 2rem; border-bottom: 1px solid #e8e2d8; }
.tile-wide .tile-title { font-size: 1.4rem; }
.tile-wide .tile-excerpt { -webkit-line-clamp: 4; }

/* ARCHIVE BAND */
.archive-band { background: #1c1916; padding: 2.5rem 2rem; margin: 0 -2rem; }
.archive-band-inner { max-width: 1080px; margin: 0 auto; }
.archive-band-top { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.08); }
.archive-band-top h2 { font-family: 'Playfair Display', serif; font-style: italic; font-weight: 400; font-size: 1.4rem; color: rgba(247,243,237,0.7); letter-spacing: -0.01em; }
.archive-band-top a { font-family: 'DM Sans', sans-serif; font-size: 0.68rem; letter-spacing: 0.08em; color: #c8a84b; border-bottom: 1px solid rgba(200,168,75,0.35); }
.archive-band-top a:hover { opacity: 0.7; }
.archive-band-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: rgba(255,255,255,0.05); }
.ab-item { background: #231f1b; padding: 1rem 1.25rem; transition: background 0.15s; }
.ab-item:hover { background: #2d2925; }
.ab-dt { font-family: 'DM Sans', sans-serif; font-size: 0.62rem; color: rgba(255,255,255,0.25); letter-spacing: 0.06em; margin-bottom: 0.3rem; }
.ab-tt { font-family: 'Crimson Pro', serif; font-size: 0.92rem; color: rgba(247,243,237,0.65); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; transition: color 0.15s; }
.ab-item:hover .ab-tt { color: #c8a84b; }

/* PAGINATION */
.pagination { padding: 2.5rem 0; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #d4cec4; }
.pg-nums { display: flex; align-items: center; gap: 0.2rem; }
.pg-nums a, .pg-nums span { font-family: 'DM Sans', sans-serif; font-size: 0.82rem; color: #6a6560; padding: 0.4rem 0.65rem; transition: color 0.15s; border: 1px solid transparent; text-decoration: none; }
.pg-nums a:hover { color: #1c1916; border-color: #d4cec4; }
.pg-nums .cur { color: #1c1916; border-color: #1c1916; font-weight: 500; }
.pg-nums .ell { border: none; color: #9a9590; }
.pg-arrow { font-family: 'DM Sans', sans-serif; font-size: 0.75rem; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: #6a6560; transition: color 0.15s; }
.pg-arrow:hover { color: #1c1916; }

/* SINGLE POST */
.single-wrap { max-width: 1080px; margin: 0 auto; padding: 0 2rem; display: grid; grid-template-columns: 1fr 260px; gap: 5rem; align-items: start; }
.single-main { padding: 3.5rem 0 4rem; }
.post-kicker { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; font-weight: 500; letter-spacing: 0.2em; text-transform: uppercase; color: #8a6a30; margin-bottom: 0.85rem; display: flex; align-items: center; gap: 0.6rem; }
.post-kicker::after { content: ''; flex: 0 0 20px; height: 1px; background: #8a6a30; }
.post-h1 { font-family: 'Playfair Display', serif; font-weight: 500; font-size: clamp(2rem, 4vw, 3.2rem); line-height: 1.15; letter-spacing: -0.025em; color: #1c1916; margin-bottom: 1.25rem; }
.post-meta-bar { display: flex; align-items: center; gap: 0.75rem; font-family: 'DM Sans', sans-serif; font-size: 0.75rem; color: #9a9590; padding-bottom: 2rem; border-bottom: 2px solid #1c1916; margin-bottom: 2.5rem; flex-wrap: wrap; }
.post-meta-bar .sep { color: #d4cec4; }
.post-body { font-size: 1.07rem; line-height: 1.88; color: #2e2b27; }
.post-body p { margin-bottom: 1.4em; }
.post-body strong { font-weight: 600; color: #1c1916; }
.post-body em { font-style: italic; color: #5a5550; }
.post-body a { color: #2d4a3e; border-bottom: 1px solid rgba(45,74,62,0.3); }
.post-body a:hover { border-color: #2d4a3e; }
.post-body hr { border: none; border-top: 1px solid #e0dbd0; margin: 2.5em 0; }
.post-body img { max-width: 100%; display: block; margin: 2.5em auto; border: 1px solid #d4cec4; }
.post-body h2, .post-body h3 { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; font-weight: 500; letter-spacing: 0.2em; text-transform: uppercase; color: #9a9590; margin: 3em 0 1.2em; display: flex; align-items: center; gap: 0.75rem; }
.post-body h2::after, .post-body h3::after { content: ''; flex: 1; height: 1px; background: #e0dbd0; }
.post-body blockquote, .post-body pre { font-family: 'Crimson Pro', serif; font-style: italic; font-size: 1rem; line-height: 2.1; color: #5a5550; border-left: 2px solid #c8a84b; padding: 0.5em 0 0.5em 1.6em; margin: 2.25em 0; background: none; white-space: pre-wrap; }
.poem-block { font-family: 'Crimson Pro', serif; font-style: italic; font-size: 1.08rem; line-height: 2.1; color: #3a3530; border-left: 3px solid #c8a84b; padding: 1.25em 0 1.25em 2em; margin: 2.5em 0; background: linear-gradient(to right, rgba(200,168,75,0.04), transparent); white-space: pre-line; position: relative; }
.poem-block::before { content: '\201C'; font-family: 'Playfair Display', serif; font-size: 4rem; color: rgba(200,168,75,0.2); position: absolute; top: -0.5rem; left: 0.3rem; line-height: 1; font-style: normal; }
.poem-divider { text-align: center; color: #c8a84b; margin: 2rem 0; letter-spacing: 0.5em; font-size: 0.8rem; }

.post-nav-bar { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #d4cec4; border-top: 2px solid #1c1916; margin-top: 3.5rem; }
.post-nav-bar a { background: #f7f3ed; padding: 1.5rem; display: block; transition: background 0.15s; }
.post-nav-bar a:hover { background: #fff; }
.post-nav-bar a:last-child { text-align: right; }
.nav-dir { display: block; font-family: 'DM Sans', sans-serif; font-size: 0.62rem; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; color: #9a9590; margin-bottom: 0.4rem; }
.nav-title { display: block; font-family: 'Playfair Display', serif; font-size: 1rem; color: #1c1916; line-height: 1.35; }

/* SIDEBAR */
.single-sidebar { padding: 3.5rem 0; position: sticky; top: 1.5rem; }
.sidebar-sec { margin-bottom: 2.5rem; }
.sidebar-label { font-family: 'DM Sans', sans-serif; font-size: 0.62rem; font-weight: 500; letter-spacing: 0.2em; text-transform: uppercase; color: #9a9590; margin-bottom: 0.8rem; padding-bottom: 0.6rem; border-bottom: 1px solid #d4cec4; }
.search-row { display: flex; border: 1.5px solid #d4cec4; transition: border-color 0.2s; }
.search-row:focus-within { border-color: #1c1916; }
.search-row input { flex: 1; padding: 0.6rem 0.75rem; font-family: 'Crimson Pro', serif; font-size: 0.9rem; color: #1c1916; border: none; outline: none; background: transparent; }
.search-row button { padding: 0 0.75rem; border: none; background: none; color: #9a9590; cursor: pointer; font-size: 0.9rem; transition: color 0.15s; }
.search-row button:hover { color: #1c1916; }
.yr-block { margin-bottom: 0.15rem; }
.yr-row { display: flex; align-items: center; justify-content: space-between; padding: 0.4rem 0; cursor: pointer; font-family: 'DM Sans', sans-serif; font-size: 0.84rem; color: #1c1916; user-select: none; transition: color 0.15s; }
.yr-row:hover { color: #8a6a30; }
.yr-n { font-size: 0.72rem; color: #9a9590; }
.yr-ch { font-size: 0.6rem; color: #9a9590; transition: transform 0.2s; display: inline-block; }
.yr-ch.open { transform: rotate(90deg); }
.yr-items { display: none; padding: 0.15rem 0 0.4rem 0.9rem; border-left: 1.5px solid #e8e2d8; margin-left: 0.1rem; }
.yr-items.open { display: block; }
.yr-items a { display: block; font-family: 'DM Sans', sans-serif; font-size: 0.8rem; color: #6a6560; padding: 0.22rem 0; line-height: 1.4; transition: color 0.15s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.yr-items a:hover { color: #8a6a30; }

/* ARCHIVE PAGE */
.archive-page-title { font-family: 'Playfair Display', serif; font-style: italic; font-weight: 400; font-size: 2.5rem; letter-spacing: -0.02em; color: #1c1916; padding: 3rem 0 0.5rem; display: block; }
.archive-yr-head { font-family: 'Playfair Display', serif; font-weight: 400; font-style: italic; font-size: 1.8rem; letter-spacing: -0.02em; padding: 2.5rem 0 1rem; border-bottom: 1px solid #d4cec4; display: flex; align-items: baseline; gap: 0.75rem; color: #1c1916; }
.archive-yr-head small { font-family: 'DM Sans', sans-serif; font-size: 0.72rem; font-weight: 400; color: #9a9590; font-style: normal; }
.archive-row { display: grid; grid-template-columns: 100px 1fr; gap: 1.25rem; padding: 0.9rem 0; border-bottom: 1px solid #e8e2d8; align-items: baseline; transition: background 0.1s; }
.archive-row:hover { background: #fff; margin: 0 -0.5rem; padding: 0.9rem 0.5rem; }
.archive-dt { font-family: 'DM Sans', sans-serif; font-size: 0.7rem; color: #9a9590; letter-spacing: 0.05em; }
.archive-tt { font-family: 'Crimson Pro', serif; font-size: 1rem; color: #1c1916; line-height: 1.4; transition: color 0.15s; }
.archive-tt:hover { color: #8a6a30; }

/* SEARCH */
#search-big { width: 100%; padding: 1rem 0; font-family: 'Playfair Display', serif; font-style: italic; font-size: 1.5rem; color: #1c1916; border: none; border-bottom: 2px solid #1c1916; outline: none; background: transparent; margin-bottom: 2.5rem; letter-spacing: -0.01em; }
.sr { padding: 1.5rem 0; border-bottom: 1px solid #e8e2d8; }
.sr-date { font-family: 'DM Sans', sans-serif; font-size: 0.7rem; color: #9a9590; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.35rem; }
.sr h3 { font-family: 'Playfair Display', serif; font-weight: 400; font-size: 1.2rem; letter-spacing: -0.01em; }
.sr h3 a { color: #1c1916; transition: color 0.15s; }
.sr h3 a:hover { color: #8a6a30; }
.sr p { font-family: 'Crimson Pro', serif; font-size: 0.95rem; color: #6a6560; margin-top: 0.35rem; }
mark { background: none; color: #8a6a30; font-weight: 600; }

/* FOOTER */
footer { background: #2d4a3e; padding: 3rem 2rem; margin-top: 0; }
.footer-inner { max-width: 1080px; margin: 0 auto; display: grid; grid-template-columns: 1fr auto 1fr; align-items: start; gap: 3rem; }
.footer-brand { font-family: 'Playfair Display', serif; font-style: italic; font-weight: 400; font-size: 1.8rem; color: rgba(247,243,237,0.85); letter-spacing: -0.02em; display: block; margin-bottom: 0.4rem; }
.footer-tagline { font-family: 'DM Sans', sans-serif; font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(255,255,255,0.25); }
.footer-links { display: flex; flex-direction: column; gap: 0.5rem; align-items: center; }
.footer-links a { font-family: 'DM Sans', sans-serif; font-size: 0.72rem; letter-spacing: 0.06em; color: rgba(255,255,255,0.35); transition: color 0.15s; text-transform: uppercase; }
.footer-links a:hover { color: rgba(255,255,255,0.75); }
.footer-copy { font-family: 'DM Sans', sans-serif; font-size: 0.68rem; color: rgba(255,255,255,0.2); text-align: right; line-height: 1.8; }

@media (max-width: 860px) { .featured { grid-template-columns: 1fr; } .feat-poem-block { display: none; } .post-tiles { grid-template-columns: 1fr 1fr; } .tile-wide { grid-column: span 1; display: block; } .archive-band-grid { grid-template-columns: 1fr 1fr; } .single-wrap { grid-template-columns: 1fr; } .single-sidebar { display: none; } .footer-inner { grid-template-columns: 1fr; text-align: center; } .footer-copy { text-align: center; } .footer-links { align-items: center; } }
@media (max-width: 580px) { .post-tiles { grid-template-columns: 1fr; } .archive-band-grid { grid-template-columns: 1fr; } .masthead-name { font-size: 3rem; } .page-wrap { padding: 0 1.25rem; } .post-nav-bar { grid-template-columns: 1fr; } }
"""

SEARCH_JS = """
(function() {
  var input = document.getElementById('search-big');
  var results = document.getElementById('search-results');
  var noRes = document.getElementById('no-results');
  var posts = [];
  var timer;

  function loadIndex() {
    fetch('../search-index.json')
      .then(function(r){ return r.json(); })
      .then(function(d){ posts = d; })
      .catch(function(){
        fetch('search-index.json')
          .then(function(r){ return r.json(); })
          .then(function(d){ posts = d; });
      });
  }
  loadIndex();

  function hl(text, q) {
    var escaped = q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
    return text.replace(new RegExp('(' + escaped + ')', 'gi'), '<mark>$1</mark>');
  }

  function doSearch(q) {
    q = q.trim();
    results.innerHTML = '';
    if (!q || q.length < 2) { noRes.style.display = 'none'; return; }
    var ql = q.toLowerCase();
    var matched = posts.filter(function(p){
      return p.title.toLowerCase().indexOf(ql) >= 0 || p.excerpt.toLowerCase().indexOf(ql) >= 0;
    }).slice(0, 30);
    if (!matched.length) { noRes.style.display = 'block'; return; }
    noRes.style.display = 'none';
    matched.forEach(function(p) {
      var d = document.createElement('div');
      d.className = 'sr';
      d.innerHTML = '<div class="sr-date">' + p.date + '</div>' +
        '<h3><a href="../posts/' + p.slug + '.html">' + hl(p.title, q) + '</a></h3>' +
        '<p>' + hl(p.excerpt, q) + '</p>';
      results.appendChild(d);
    });
  }

  if (input) {
    input.addEventListener('input', function() {
      clearTimeout(timer);
      var v = this.value;
      timer = setTimeout(function(){ doSearch(v); }, 250);
    });
  }
})();
"""

ARCHIVE_JS = """
document.querySelectorAll('.yr-row').forEach(function(row) {
  row.addEventListener('click', function() {
    var items = this.nextElementSibling;
    var ch = this.querySelector('.yr-ch');
    items.classList.toggle('open');
    if (ch) ch.classList.toggle('open');
  });
});
var yr = new Date().getFullYear().toString();
document.querySelectorAll('.yr-row').forEach(function(row) {
  if (row.dataset.year === yr) row.click();
});
"""


def html_page(title, content, *, css_path="", nav_active="",
              sidebar_html="", featured_html="", archive_band_html=""):
    today = datetime.now()
    days_pl = ["Poniedzialek","Wtorek","Sroda","Czwartek","Piatek","Sobota","Niedziela"]
    months_pl = ["","stycznia","lutego","marca","kwietnia","maja","czerwca",
                 "lipca","sierpnia","wrzesnia","pazdziernika","listopada","grudnia"]
    today_str = f"{days_pl[today.weekday()]}, {today.day} {months_pl[today.month]} {today.year}"

    main_wrap_open  = '<div class="single-wrap">' if sidebar_html else '<div class="page-wrap">'
    main_wrap_close = '</div>'
    inner_open  = '<div class="single-main">' if sidebar_html else ''
    inner_close = '</div>' if sidebar_html else ''
    sidebar_block = f'<aside class="single-sidebar">{sidebar_html}</aside>' if sidebar_html else ''

    feat_block    = f'<div class="page-wrap">{featured_html}</div>' if featured_html else ''
    archive_block = f'<div class="page-wrap">{archive_band_html}</div>' if archive_band_html else ''

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Osobny Swiat</title>
  <link rel="stylesheet" href="{css_path}style.css">
</head>
<body>

<header class="site-header">
  <div class="header-top">
    <span>{today_str}</span>
    <div class="header-tags">
      <span>Filozofia</span><span>Literatura</span><span>Refleksja</span>
    </div>
  </div>
  <div class="masthead-inner">
    <div class="masthead-top">
      <span class="masthead-label">Rok Norwidowski Zawsze</span>
      <div class="masthead-issue">Widziane ze Strachowki<br>od 2016 roku</div>
    </div>
    <a href="{css_path}index.html" class="masthead-name">Osobny Swiat</a>
    <p class="masthead-tagline">Filozofia, wiara, wiersze i mysli — pisane codziennie od lat</p>
    <nav class="sitenav">
      <a href="{css_path}index.html" {"class='active'" if nav_active=='home' else ''}>Teksty</a>
      <a href="{css_path}archiwum/index.html" {"class='active'" if nav_active=='archiwum' else ''}>Archiwum</a>
      <a href="{css_path}search/index.html" {"class='active'" if nav_active=='search' else ''}>Szukaj</a>
      <a href="{css_path}universe/index.html" {"class='active'" if nav_active=='universe' else ''}>&#346;wiat S&#322;&#243;w</a>
      <a href="{css_path}universe/timeline.html" {"class='active'" if nav_active=='timeline' else ''}>O&#347; Czasu</a>
      <a href="{css_path}galeria/index.html" {"class='active'" if nav_active=='galeria' else ''}>Galeria</a>
    </nav>
  </div>
</header>

{feat_block}

{main_wrap_open}
  {inner_open}
    {content}
  {inner_close}
  {sidebar_block}
{main_wrap_close}

{archive_block}

<footer>
  <div class="footer-inner">
    <div>
      <span class="footer-brand">Osobny Swiat</span>
      <span class="footer-tagline">Widziane ze Strachowki</span>
    </div>
    <div class="footer-links">
      <a href="{css_path}index.html">Strona glowna</a>
      <a href="{css_path}archiwum/index.html">Archiwum</a>
      <a href="{css_path}search/index.html">Szukaj</a>
      <a href="https://strachowka.blogspot.com" target="_blank">Oryginalny blog</a>
    </div>
    <span class="footer-copy">&copy; {today.year} Jozef Kapaon<br>osobnyswiat.pl</span>
  </div>
</footer>

<script>{ARCHIVE_JS}</script>
</body>
</html>"""


def build_sidebar(posts, css_path=""):
    from collections import defaultdict
    by_year = defaultdict(list)
    for p in posts:
        year = p["published"][:4] if p["published"] else "?"
        by_year[year].append(p)

    archive_html = ""
    for year in sorted(by_year.keys(), reverse=True):
        yp = by_year[year]
        items = "".join(
            f'<a href="{css_path}posts/{p["slug"]}.html">{p["title"][:60]}{"..." if len(p["title"])>60 else ""}</a>'
            for p in yp
        )
        archive_html += f"""
        <div class="yr-block">
          <div class="yr-row" data-year="{year}">
            <span>{year} <span class="yr-n">{len(yp)} tekstow</span></span>
            <span class="yr-ch">&#9656;</span>
          </div>
          <div class="yr-items">{items}</div>
        </div>"""

    return f"""
    <div class="sidebar-sec">
      <div class="sidebar-label">Szukaj</div>
      <div class="search-row">
        <input type="text" placeholder="Szukaj w tekstach..."
               onkeydown="if(event.key==='Enter'){{location.href='{css_path}search/index.html?q='+this.value;}}">
        <button onclick="location.href='{css_path}search/index.html'">&#8594;</button>
      </div>
    </div>
    <div class="sidebar-sec">
      <div class="sidebar-label">Archiwum</div>
      {archive_html}
    </div>"""
def strip_html(html_content):
    """Strip HTML tags for excerpts."""
    clean = re.sub(r'<[^>]+>', ' ', html_content or '')
    clean = unescape(clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


# Caption phrases to remove from excerpts and featured text
CAPTION_PHRASES = [
    "grafika wygenerowana przez ai",
    "grafika wygenerowana przez",
    "zdjęcie wygenerowane przez ai",
    "obraz wygenerowany przez ai",
    "ilustracja wygenerowana przez ai",
    "wygenerowane przez ai",
    "generated by ai",
    "ai generated",
    "image generated",
]


def clean_excerpt(html_content, max_len=300):
    """Strip HTML, remove captions, return clean excerpt."""
    text = strip_html(html_content)
    # Remove caption lines
    lines = text.split('.')
    clean_lines = []
    for line in lines:
        low = line.lower().strip()
        if any(cap in low for cap in CAPTION_PHRASES):
            continue
        if len(low) < 8:  # skip very short fragments
            continue
        clean_lines.append(line.strip())
    result = '. '.join(clean_lines).strip()
    if result and not result.endswith('.'):
        result += ''
    return result[:max_len]


def format_post_content(html_content):
    """Process post HTML to style poems and remove captions."""
    if not html_content:
        return html_content

    # Remove AI image caption paragraphs
    def remove_captions(m):
        text = strip_html(m.group(0)).lower().strip()
        if any(cap in text for cap in CAPTION_PHRASES):
            return ''
        return m.group(0)

    content = re.sub(r'<p[^>]*>.*?</p>', remove_captions, html_content,
                     flags=re.DOTALL | re.IGNORECASE)

    # Convert *** dividers to styled dividers
    content = re.sub(
        r'<[^>]*>\s*\*\*\*\s*</[^>]*>',
        '<div class="poem-divider">&#10022; &nbsp; &#10022; &nbsp; &#10022;</div>',
        content, flags=re.IGNORECASE
    )

    # Detect and style poem blocks
    # Poems in his blog are typically italic text or short-line paragraphs
    # wrapped in <i> or <em> tags, sometimes in sequence
    def style_poem_block(m):
        inner = m.group(1)
        # Check if this looks like poetry (short lines, no long sentences)
        text = strip_html(inner)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            lines = [l.strip() for l in text.split('<br') if l.strip()]
        avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
        # If average line is short it's likely poetry
        if avg_len < 60 and len(lines) >= 3:
            # Clean up inner HTML for poem display
            poem_text = re.sub(r'<br\s*/?>', '\n', inner)
            poem_text = strip_html(poem_text).strip()
            return f'<div class="poem-block">{poem_text}</div>'
        return m.group(0)

    # Style consecutive italic blocks as poems
    content = re.sub(
        r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>',
        style_poem_block,
        content,
        flags=re.DOTALL | re.IGNORECASE
    )

    return content


# Expanded Polish stopwords for word cloud
STOPWORDS = {
    # Basic conjunctions/prepositions
    "i","w","z","na","do","nie","to","sie","jest","ze","ale","jak","co","po",
    "by","tak","go","jej","jego","ich","im","nas","nam","czy","ten","ta","te",
    "tego","tej","tych","tym","temu","przez","przy","dla","od","o","a","bo",
    "no","juz","tu","tam","sobie","tylko","jestem","bylo","byly","mnie","mam",
    "mi","my","ja","ty","on","ona","ono","oni","one","pan","pani","choc",
    "kiedy","gdy","jesli","jezeli","aby","zeby","iz","moze","mozna",
    "wszystko","wszystkich","wszystkim","wszystkie","bardzo","bardziej",
    "najbardziej","jaki","jaka","jakie","jacy","tego","taka","takie",
    "takiej","takim","taki","tyle","tez","juz","sobie","czego","czemu",
    "czym","moj","moja","moje","moich","swoj","swoja","swoje","swoich",
    "swoim","swoja","swoja","chcę","chce","chcial","moze","mozemy",
    "mozecie","moga","jeszcze","tez","rowniez","jednak","lecz","wiec",
    "dlatego","ktory","ktora","ktore","ktorzy","ktorych","ktorym",
    # Verb forms
    "jest","bylo","bedzie","byla","byli","bylo","beda","byc","miec","mam",
    "masz","maja","mamy","macie","mial","miala","mieli","mialy","moze",
    "mozna","mozemy","chce","chcemy","chcial","chciala","chcieli","widziec",
    "widze","widzisz","widzi","widzimy","wiecie","wiedza","wiedziec","wiem",
    "wiesz","wiemy","wiecie","wiedza","znac","znam","znasz","zna","znamy",
    "znacie","znaja","mowic","mowie","mowisz","mowi","mowimy","mowicie",
    "mowia","powiedziec","powiem","powie","powiemy","powiedzial","myslec",
    "mysle","myslisz","mysli","myslimy","myslicie","mysla","myslal","myslala",
    "czuc","czuje","czujesz","czuje","czujemy","czujecie","czuja","czul",
    "isc","idzie","idzie","idemy","idziecie","ida","szedl","szla","znalezc",
    "znajde","znajdziesz","znajdzie","znalazl","znalazla","pisac","pisze",
    "piszesz","pisze","piszemy","piszecie","pisza","pisal","pisala","napisal",
    "byc","jestem","jestes","jest","jestesmy","jestescie","sa",
    # Common adjectives/adverbs
    "dobry","dobra","dobre","dobrego","dobrze","zly","zla","zle","zlego",
    "wielki","wielka","wielkie","wielkiego","duzy","duza","duze","duzego",
    "maly","mala","male","malego","nowy","nowa","nowe","nowego","stary",
    "stara","stare","starego","pierwszy","pierwsza","pierwsze","ostatni",
    "wlasnie","juz","jeszcze","tez","rowniez","bardzo","bardziej","zawsze",
    "nigdy","czasem","czasami","zawsze","wszedzie","nigdzie","gdzies",
    "kiedys","nigdy","teraz","wtedy","potem","potem","najpierw","potem",
    "jeden","jedna","jedno","dwa","dwie","trzy","cztery","piec","szesc",
    "wiele","wiele","kilka","kilku","kilkoma","troche","malo","duzo",
    # Pronouns / determiners
    "ten","ta","te","tego","tej","temu","tym","tych","tymi","tamten",
    "tamta","tamte","tamtego","tamtej","ow","owa","owe","swoj","swoja",
    "swoje","nasz","nasza","nasze","wasz","wasza","wasze","kazdy","kazda",
    "kazde","kazde","zaden","zadna","zadne","sam","sama","samo","sami",
    "inne","inny","inna","innych","innym","innymi","pewien","pewna","pewne",
    # Question words
    "kto","kogo","komu","kim","co","czego","czemu","czym","gdzie","kiedy",
    "jak","dlaczego","skad","dokad","ile","ktory","ktora","ktore",
    # Misc common words that aren't meaningful
    "raz","razy","razem","nawet","jednak","chociaz","mimo","wprawdzie",
    "przeciez","zreszta","owszem","otoz","mianowicie","czyli","albo","lub",
    "ani","nie","tak","tak","nie","no","och","ach","hm","coz","otoz",
    "wlasnie","akurat","juz","jeszcze","juz","sobie","sobie","tego",
    "tego","wiec","wiec","przy","przy","jako","jako","przez","przez",
    "przed","przed","nad","pod","bez","bez","okolo","kolo","wokol",
    "sposrod","sposob","sposob","typ","forma","rzecz","sprawa","kwestia",
    "punkt","miejsce","czas","dzien","rok","lat","lata","lat","roku",
    "dnia","godz","godz","min","chwila","moment","okres","etap","faza",
}


def build_site(posts):
    """Generate all HTML files for the static site."""

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()
    (OUTPUT_DIR / "posts").mkdir()
    (OUTPUT_DIR / "archiwum").mkdir()
    (OUTPUT_DIR / "search").mkdir()
    (OUTPUT_DIR / "universe").mkdir()
    (OUTPUT_DIR / "galeria").mkdir()

    (OUTPUT_DIR / "style.css").write_text(CSS, encoding="utf-8")

    posts_sorted = sorted(posts, key=lambda p: p["published"], reverse=True)

    # Unique slugs
    seen_slugs = {}
    for p in posts_sorted:
        base = p["slug"]
        if base in seen_slugs:
            seen_slugs[base] += 1
            p["slug"] = f"{base}-{seen_slugs[base]}"
        else:
            seen_slugs[base] = 1

    # ── Search index ──────────────────────────────────────
    print("Building search index...")
    index = []
    for p in posts_sorted:
        excerpt = clean_excerpt(p["content"], max_len=250)
        index.append({
            "slug":    p["slug"],
            "title":   p["title"],
            "date":    format_date(p["published"]),
            "excerpt": excerpt,
        })
    (OUTPUT_DIR / "search-index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )

    # ── Individual post pages ─────────────────────────────
    print(f"Building {len(posts_sorted)} post pages...")
    for i, p in enumerate(posts_sorted):
        prev_post = posts_sorted[i + 1] if i + 1 < len(posts_sorted) else None
        next_post = posts_sorted[i - 1] if i > 0 else None

        nav_html = '<div class="post-nav-bar">'
        nav_html += f'<a href="{prev_post["slug"]}.html"><span class="nav-dir">&larr; Poprzedni</span><span class="nav-title">{prev_post["title"][:65]}</span></a>' if prev_post else '<span></span>'
        nav_html += f'<a href="{next_post["slug"]}.html"><span class="nav-dir">Nastepny &rarr;</span><span class="nav-title">{next_post["title"][:65]}</span></a>' if next_post else '<span></span>'
        nav_html += '</div>'

        labels_str = " &middot; ".join(p["labels"]) if p["labels"] else ""
        labels_sep = f'<span class="sep">&middot;</span><span>{labels_str}</span>' if labels_str else ""

        content = f"""
        <div class="post-kicker">{format_date(p['published'])}</div>
        <h1 class="post-h1">{p['title']}</h1>
        <div class="post-meta-bar">
          <span>{format_date(p['published'])}</span>
          {labels_sep}
        </div>
        <div class="post-body">{format_post_content(p['content'])}</div>
        {nav_html}"""

        page = html_page(
            p["title"],
            content,
            css_path="../",
            sidebar_html=build_sidebar(posts_sorted, css_path="../"),
        )
        (OUTPUT_DIR / "posts" / f"{p['slug']}.html").write_text(page, encoding="utf-8")

    # ── Index pages ───────────────────────────────────────
    print("Building index pages...")
    PER_PAGE = 11  # 1 featured + 10 tiles per page
    pages = [posts_sorted[i:i+PER_PAGE] for i in range(0, len(posts_sorted), PER_PAGE)]

    def pagination_html(current, total):
        if total <= 1:
            return ""
        h = '<div class="pagination">'
        prev_href = "index.html" if current - 1 == 1 else f"page{current-1}.html"
        next_href = f"page{current+1}.html"
        h += f'<a href="{prev_href}" class="pg-arrow">&larr; Wczesniejsze</a>' if current > 1 else '<span></span>'
        h += '<div class="pg-nums">'
        for pg in range(1, total + 1):
            href = "index.html" if pg == 1 else f"page{pg}.html"
            if pg == current:
                h += f'<span class="cur">{pg}</span>'
            elif pg <= 2 or pg >= total - 1 or abs(pg - current) <= 2:
                h += f'<a href="{href}">{pg}</a>'
            elif abs(pg - current) == 3:
                h += '<span class="ell">...</span>'
        h += '</div>'
        h += f'<a href="{next_href}" class="pg-arrow">Nastepne &rarr;</a>' if current < total else '<span></span>'
        h += '</div>'
        return h

    for pg_num, pg_posts in enumerate(pages, 1):
        featured_html = ""
        tile_posts = pg_posts

        # Featured post — first post on each page
        if pg_posts:
            fp = pg_posts[0]
            tile_posts = pg_posts[1:]
            excerpt = clean_excerpt(fp["content"], max_len=320)
            raw = clean_excerpt(fp["content"], max_len=180)
            poem_lines = raw if len(raw) <= 180 else raw[:177] + "..."
            labels_feat = fp["labels"][0] if fp["labels"] else "tekst"

            featured_html = f"""
            <div class="featured">
              <div>
                <span class="feat-num">01</span>
                <div class="feat-label">Esej dnia</div>
                <h2 class="feat-title"><a href="posts/{fp['slug']}.html">{fp['title']}</a></h2>
                <p class="feat-excerpt">{excerpt}</p>
                <div class="feat-byline">
                  <span>{format_date(fp['published'])}</span>
                  <span class="sep">&middot;</span>
                  <span>{labels_feat}</span>
                  <span class="sep">&middot;</span>
                  <a href="posts/{fp['slug']}.html" class="feat-read">Czytaj &rarr;</a>
                </div>
              </div>
              <div>
                <div class="feat-poem-block">
                  <p class="feat-poem-text">{poem_lines}</p>
                  <cite class="feat-poem-cite">{format_date(fp['published'])}</cite>
                </div>
              </div>
            </div>"""

        # Tile grid
        tiles = ""
        for idx, p in enumerate(tile_posts):
            excerpt = clean_excerpt(p["content"], max_len=200)
            tag_html = f'<span class="tile-tag">{p["labels"][0]}</span>' if p["labels"] else ""
            num = str(idx + 2).zfill(2)

            # Every 5 tiles, make a wide one
            if idx == 2:
                tiles += f"""
                <div class="tile-wide">
                  <div>
                    {tag_html}
                    <span class="tile-date">{format_date(p['published'])}</span>
                    <h2 class="tile-title"><a href="posts/{p['slug']}.html">{p['title']}</a></h2>
                  </div>
                  <div><p class="tile-excerpt">{excerpt}</p></div>
                </div>"""
            else:
                tiles += f"""
                <div class="tile">
                  <span class="tile-num">{num}</span>
                  {tag_html}
                  <span class="tile-date">{format_date(p['published'])}</span>
                  <h2 class="tile-title"><a href="posts/{p['slug']}.html">{p['title']}</a></h2>
                  <p class="tile-excerpt">{excerpt}</p>
                </div>"""

        # Archive band — older posts shown on page 1
        archive_band_html = ""
        if pg_num == 1 and len(posts_sorted) > 50:
            band_posts = [p for p in posts_sorted
                          if p["published"][:4] < str(datetime.now().year)][:8]
            if band_posts:
                year_label = band_posts[0]["published"][:4]
                items = "".join(
                    f'<div class="ab-item"><div class="ab-dt">{format_date_short(bp["published"])}</div>'
                    f'<a href="posts/{bp["slug"]}.html" class="ab-tt">{bp["title"]}</a></div>'
                    for bp in band_posts[:8]
                )
                archive_band_html = f"""
                <div class="archive-band">
                  <div class="archive-band-inner">
                    <div class="archive-band-top">
                      <h2>Ze Strachowki &mdash; {year_label}</h2>
                      <a href="archiwum/index.html">Pelne archiwum &rarr;</a>
                    </div>
                    <div class="archive-band-grid">{items}</div>
                  </div>
                </div>"""

        sec_label = '<div class="sec-label"><span>Ostatnie teksty</span><a href="archiwum/index.html">Archiwum &rarr;</a></div>' if pg_num == 1 else f'<div class="sec-label"><span>Strona {pg_num}</span><a href="index.html">Strona glowna &rarr;</a></div>'

        content = f'{sec_label}<div class="post-tiles">{tiles}</div>{pagination_html(pg_num, len(pages))}'
        fname = "index.html" if pg_num == 1 else f"page{pg_num}.html"

        page = html_page(
            "Strona glowna" if pg_num == 1 else f"Strona {pg_num}",
            content,
            css_path="",
            nav_active="home",
            featured_html=featured_html,
            archive_band_html=archive_band_html,
        )
        (OUTPUT_DIR / fname).write_text(page, encoding="utf-8")

    # ── Archive page ──────────────────────────────────────
    print("Building archive page...")
    from collections import defaultdict
    by_year = defaultdict(list)
    for p in posts_sorted:
        year = p["published"][:4] if p["published"] else "?"
        by_year[year].append(p)

    archive_content = f'<span class="archive-page-title">Archiwum</span>'
    archive_content += f'<p style="font-family:\'DM Sans\',sans-serif;font-size:0.8rem;color:#9a9590;margin-bottom:1rem">{len(posts_sorted)} tekstow</p>'
    for year in sorted(by_year.keys(), reverse=True):
        year_posts = by_year[year]
        archive_content += f'<div class="archive-yr-head">{year} <small>{len(year_posts)} tekstow</small></div>'
        for p in year_posts:
            archive_content += f'<div class="archive-row"><span class="archive-dt">{format_date_short(p["published"])}</span><a href="../posts/{p["slug"]}.html" class="archive-tt">{p["title"]}</a></div>'

    page = html_page("Archiwum", archive_content, css_path="../", nav_active="archiwum")
    (OUTPUT_DIR / "archiwum" / "index.html").write_text(page, encoding="utf-8")

    # ── Search page ───────────────────────────────────────
    print("Building search page...")
    search_content = """
    <div style="padding: 3rem 0 4rem">
      <input type="text" id="search-big" placeholder="Szukaj w tekstach..." autocomplete="off">
      <div id="search-results"></div>
      <div id="no-results" style="display:none;color:#9a9590;font-family:'DM Sans',sans-serif;font-size:0.9rem;font-style:italic">
        Nie znaleziono wynikow.
      </div>
    </div>"""
    page = html_page("Szukaj", search_content, css_path="../", nav_active="search")
    page = page.replace("</body>", f"<script>{SEARCH_JS}</script></body>")
    (OUTPUT_DIR / "search" / "index.html").write_text(page, encoding="utf-8")

    # ── Word cloud data ───────────────────────────────────────
    print("Analysing word frequencies...")
    (OUTPUT_DIR / "universe").mkdir(exist_ok=True)

    from collections import Counter
    word_freq = Counter()
    post_dates = {}

    for p in posts_sorted:
        text = strip_html(p["content"] + " " + p["title"])
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        words_in_post = text.split()
        for w in words_in_post:
            w = w.strip()
            if len(w) >= 4 and w not in STOPWORDS and not w.isdigit():
                word_freq[w] += 1
        year = p["published"][:4] if p["published"] else "?"
        post_dates[year] = post_dates.get(year, 0) + 1

    # Extra words to exclude that slip through
    extra_stop = {
        "jest","bylo","bedzie","mozna","mozemy","ktory","ktora","moze",
        "chce","tego","tych","sobie","przez","przy","mnie","moje","moja",
        "swoje","swojej","swoim","swojego","jestem","bylem","bylas",
        "bedzie","bylo","tego","taki","takie","takiej","takim","innym",
        "innej","inne","kazdy","kazda","kazde","kazdej","kazdym","kazdego",
        "bardziej","jednak","wlasnie","wiec","ktore","ktore","ktos","czegos",
        "czemu","skoro","chociaz","przeciez","bowiem","aczkolwiek","poniewaz",
        "dlatego","tutaj","teraz","wtedy","potem","jeszcze","rowniez",
        "sposob","rzecz","sprawa","kwestia","miejsce","czas","chwila",
        "mozemy","mozecie","moga","chcemy","chcecie","chcial","chciala",
        "wiedziec","wiedzial","widzimy","widziec","znalazl","pisac","pisal",
        "mozna","trzeba","warto","wiele","kilka","troche","malo","duzo",
        "niego","niemu","nimi","nich","nami","wami","nimi","sobie","siebie",
        "soba","sobą","tego","temu","tych","tymi","tamte","tamtej","tamtego",
    }

    top_words = [
        {"text": w, "count": c}
        for w, c in word_freq.most_common(300)
        if w not in extra_stop and w not in STOPWORDS and len(w) >= 4
    ][:60]

    # Posts per year for timeline bar chart
    years_data = sorted(post_dates.items())

    # Save as JSON for the pages to use
    universe_data = {
        "words": top_words,
        "years": [{"year": y, "count": c} for y, c in years_data],
        "total_posts": len(posts_sorted),
        "total_words": sum(word_freq.values()),
    }
    (OUTPUT_DIR / "universe" / "data.json").write_text(
        json.dumps(universe_data, ensure_ascii=False), encoding="utf-8"
    )

    # ── Word cloud page ───────────────────────────────────────
    print("Building word cloud page...")

    word_cloud_js = """
const CAT_COLORS = {
  default: '#2d4a3e',
  alt1: '#8a4f20',
  alt2: '#4a3580',
  alt3: '#1a4a6b',
  alt4: '#6b2020',
};

fetch('data.json').then(r => r.json()).then(data => {
  const words = data.words;
  const totalPosts = data.total_posts;
  const totalWords = data.total_words;

  document.getElementById('stat-posts').textContent = totalPosts.toLocaleString('pl-PL');
  document.getElementById('stat-words').textContent = Math.round(totalWords / 1000) + 'k';
  document.getElementById('stat-unique').textContent = words.length + '+';

  const container = document.getElementById('wc-container');
  const W = container.offsetWidth;
  const H = 460;
  container.style.height = H + 'px';
  container.style.position = 'relative';
  container.style.overflow = 'hidden';

  const maxCount = words[0].count;
  const placed = [];
  const colors = Object.values(CAT_COLORS);

  function overlaps(a, b) {
    return !(a.r < b.l || a.l > b.r || a.b < b.t || a.t > b.b);
  }

  words.forEach(function(w, i) {
    var fontSize = Math.round(12 + (w.count / maxCount) * 40);
    var cx = W / 2, cy = H / 2;
    var placed_pos = null;

    for (var attempt = 0; attempt < 800; attempt++) {
      var angle = attempt * 2.399;
      var r = Math.sqrt(attempt) * 16;
      var x = cx + r * Math.cos(angle);
      var y = cy + r * Math.sin(angle);
      var pw = fontSize * w.text.length * 0.58;
      var ph = fontSize * 1.3;
      var box = { l: x - pw/2, r: x + pw/2, t: y - ph/2, b: y + ph/2 };
      if (box.l < 4 || box.r > W-4 || box.t < 4 || box.b > H-4) continue;
      if (!placed.some(function(p) { return overlaps(p, box); })) {
        placed.push(box);
        placed_pos = { x: x, y: y };
        break;
      }
    }

    if (!placed_pos) return;

    var el = document.createElement('span');
    el.textContent = w.text;
    el.style.cssText = [
      'position:absolute',
      'font-family:Playfair Display,serif',
      'font-size:' + fontSize + 'px',
      'color:' + colors[i % colors.length],
      'opacity:' + (0.45 + (w.count / maxCount) * 0.55),
      'left:' + placed_pos.x + 'px',
      'top:' + placed_pos.y + 'px',
      'transform:translate(-50%,-50%)',
      'cursor:pointer',
      'transition:opacity 0.2s',
      'white-space:nowrap',
      'user-select:none',
    ].join(';');

    el.title = w.text + ' — ' + w.count.toLocaleString('pl-PL') + ' wystąpień';
    el.onmouseenter = function() { this.style.opacity = '1'; };
    el.onmouseleave = function() { this.style.opacity = (0.45 + (w.count / maxCount) * 0.55).toString(); };
    el.onclick = function() {
      window.location.href = '../search/index.html?q=' + encodeURIComponent(w.text);
    };
    container.appendChild(el);
  });
});
"""

    word_cloud_content = """
<div style="padding: 3rem 0 4rem">
  <h1 style="font-family:'Playfair Display',serif;font-weight:400;font-style:italic;font-size:2.5rem;letter-spacing:-0.02em;margin-bottom:0.5rem">Swiat slow</h1>
  <p style="font-family:'DM Sans',sans-serif;font-size:0.85rem;color:#9a9590;margin-bottom:2.5rem">Najczestsze slowa i tematy ze wszystkich tekstow. Kliknij slowo by przeszukac blog.</p>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:2.5rem">
    <div style="background:#f0ece2;border:0.5px solid #d4cec4;border-radius:8px;padding:1.25rem 1.5rem">
      <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;letter-spacing:0.12em;text-transform:uppercase;color:#9a9590;margin-bottom:0.4rem">Wszystkich tekstow</div>
      <div style="font-family:'Playfair Display',serif;font-size:2rem;font-weight:400;color:#1c1916" id="stat-posts">—</div>
    </div>
    <div style="background:#f0ece2;border:0.5px solid #d4cec4;border-radius:8px;padding:1.25rem 1.5rem">
      <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;letter-spacing:0.12em;text-transform:uppercase;color:#9a9590;margin-bottom:0.4rem">Slow lacznie</div>
      <div style="font-family:'Playfair Display',serif;font-size:2rem;font-weight:400;color:#1c1916" id="stat-words">—</div>
    </div>
    <div style="background:#f0ece2;border:0.5px solid #d4cec4;border-radius:8px;padding:1.25rem 1.5rem">
      <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;letter-spacing:0.12em;text-transform:uppercase;color:#9a9590;margin-bottom:0.4rem">Unikalnych slow</div>
      <div style="font-family:'Playfair Display',serif;font-size:2rem;font-weight:400;color:#1c1916" id="stat-unique">—</div>
    </div>
  </div>

  <div id="wc-container" style="background:#faf8f3;border:0.5px solid #d4cec4;border-radius:12px;"></div>
  <p style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#9a9590;margin-top:1rem;text-align:center">Rozmiar slowa odpowiada czestotliwosci wystepowania w tekstach</p>
</div>
"""
    page = html_page("Swiat slow", word_cloud_content, css_path="../")
    page = page.replace("</body>", f"<script>{word_cloud_js}</script></body>")
    (OUTPUT_DIR / "universe" / "index.html").write_text(page, encoding="utf-8")

    # ── Timeline page ─────────────────────────────────────────
    print("Building timeline page...")

    timeline_js = """
fetch('data.json').then(r => r.json()).then(data => {
  var years = data.years;
  var maxCount = Math.max.apply(null, years.map(function(y){ return y.count; }));
  var container = document.getElementById('year-bars');

  years.forEach(function(y) {
    var pct = Math.round((y.count / maxCount) * 100);
    var bar = document.createElement('div');
    bar.style.cssText = 'display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem';
    bar.innerHTML = '<span style="font-family:DM Sans,sans-serif;font-size:0.72rem;color:#9a9590;width:2.5rem;text-align:right;flex-shrink:0">' + y.year + '</span>' +
      '<div style="flex:1;background:#f0ece2;border-radius:2px;height:18px;position:relative">' +
        '<div style="background:#2d4a3e;height:100%;width:' + pct + '%;border-radius:2px;transition:width 0.6s ease"></div>' +
        '<span style="position:absolute;right:6px;top:50%;transform:translateY(-50%);font-family:DM Sans,sans-serif;font-size:0.68rem;color:#9a9590">' + y.count + '</span>' +
      '</div>';
    container.appendChild(bar);
  });
});
"""

    # Historical events to overlay on the timeline
    events = [
        ("1978", "Wybór Jana Pawła II", "world"),
        ("1980", "Narodziny Solidarności", "world"),
        ("1981", "Stan wojenny", "world"),
        ("1989", "Upadek komunizmu", "world"),
        ("2005", "Śmierć Jana Pawła II", "world"),
        ("2016", "Początek bloga", "personal"),
        ("2022", "Inwazja Rosji na Ukrainę", "world"),
        ("2023", "Era AI — ChatGPT", "world"),
    ]

    events_html = ""
    for year, event, etype in events:
        color = "#8a4f20" if etype == "personal" else "#1a4a6b"
        events_html += f"""
        <div style="display:flex;align-items:baseline;gap:1rem;padding:0.75rem 0;border-bottom:0.5px solid #e8e2d8">
          <span style="font-family:'Playfair Display',serif;font-size:1.3rem;font-weight:400;color:{color};width:3rem;flex-shrink:0">{year}</span>
          <span style="font-family:'Crimson Pro',serif;font-size:1rem;color:#2e2b27">{event}</span>
        </div>"""

    timeline_content = f"""
<div style="padding: 3rem 0 4rem">
  <h1 style="font-family:'Playfair Display',serif;font-weight:400;font-style:italic;font-size:2.5rem;letter-spacing:-0.02em;margin-bottom:0.5rem">Os czasu</h1>
  <p style="font-family:'DM Sans',sans-serif;font-size:0.85rem;color:#9a9590;margin-bottom:3rem">Pisanie na tle historii — kazdy slupek to rok, kazdy rok to setki tekstow.</p>

  <div style="display:grid;grid-template-columns:1fr 280px;gap:4rem;align-items:start">
    <div>
      <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;letter-spacing:0.14em;text-transform:uppercase;color:#9a9590;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #d4cec4">Teksty na rok</div>
      <div id="year-bars"></div>
    </div>
    <div>
      <div style="font-family:'DM Sans',sans-serif;font-size:0.68rem;letter-spacing:0.14em;text-transform:uppercase;color:#9a9590;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #d4cec4">Wielkie wydarzenia</div>
      {events_html}
    </div>
  </div>
</div>
"""
    page = html_page("Os czasu", timeline_content, css_path="../")
    page = page.replace("</body>", f"<script>{timeline_js}</script></body>")
    (OUTPUT_DIR / "universe" / "timeline.html").write_text(page, encoding="utf-8")

    # ── Gallery page ──────────────────────────────────────────
    print("Building photo gallery...")
    (OUTPUT_DIR / "galeria").mkdir(exist_ok=True)
    (OUTPUT_DIR / "galeria" / "photos").mkdir(exist_ok=True)

    # Patterns that identify AI-generated or non-photo images
    AI_PATTERNS = [
        "chatgpt", "chatgpt image", "use ai image", "ai image",
        "dalle", "midjourney", "stable diffusion", "generated",
        "wygenerowana", "wygenerowane", "generowany",
        "przemiany", "duchowosci", "technologii",  # his recurring AI image names
    ]

    def is_ai_image(url, surrounding_text=""):
        """Return True if this looks like an AI generated image."""
        url_lower = url.lower()
        text_lower = surrounding_text.lower()
        # Only flag if very clearly AI - filename patterns
        ai_filename_patterns = [
            "chatgpt image", "chatgpt%20image",
            "use ai image", "use%20ai%20image",
            "dall-e", "dalle", "midjourney",
            "ai image", "ai%20image",
            "wygenerowana przez ai", "generated by ai",
        ]
        if any(p in url_lower for p in ai_filename_patterns):
            return True
        # Flag if caption text very clearly says AI
        if "grafika wygenerowana przez ai" in text_lower:
            return True
        if "wygenerowane przez ai" in text_lower:
            return True
        return False

    def get_full_res_url(url):
        """Convert Blogger thumbnail URL to full resolution."""
        # Remove size constraints like /w400-h266/ or /s320/
        url = re.sub(r'/w\d+-h\d+(-[^/]+)?/', '/', url)
        url = re.sub(r'/s\d+(-[^/]+)?/', '/', url)
        return url

    # Collect candidate images from all posts
    print("  Scanning posts for images...")
    candidates = []
    seen_urls = set()

    for p in posts_sorted:
        content = p["content"] or ""
        # Find all img tags
        imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', content, re.IGNORECASE)

        # Get surrounding text for AI detection
        text_around = strip_html(content)[:500].lower()

        for img_url in imgs:
            # Skip tiny images (icons etc) - check if URL has size hints
            if any(x in img_url for x in ['/s16/', '/s32/', '/s64/', '/s72/', '/favicon']):
                continue

            # Skip non-Blogger images
            if 'blogger.googleusercontent.com' not in img_url and \
               'blogspot.com' not in img_url and \
               'bp.blogspot.com' not in img_url:
                continue

            # Skip AI images
            if is_ai_image(img_url, text_around):
                continue

            # Get full res URL
            full_url = get_full_res_url(img_url)

            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            candidates.append({
                "url": full_url,
                "thumb_url": img_url,
                "post_slug": p["slug"],
                "post_title": p["title"],
                "post_date": format_date(p["published"]),
                "post_year": p["published"][:4] if p["published"] else "?",
            })

    print(f"  Found {len(candidates)} candidate photos (after filtering AI images)")

    # Download images — limit to best 180, prefer one per post
    # Sort so we get spread across posts
    # Pick first candidate per post (usually the most prominent image)
    per_post = {}
    for c in candidates:
        if c["post_slug"] not in per_post:
            per_post[c["post_slug"]] = c

    # Take up to 180 unique-post images, sorted by date newest first
    gallery_items = list(per_post.values())[:180]

    print(f"  Downloading {len(gallery_items)} photos...")
    downloaded = []

    for idx, item in enumerate(gallery_items):
        try:
            safe_slug = item["post_slug"][:40].replace("/", "-")
            fname = f"photo_{idx:04d}_{safe_slug}.jpg"
            fpath = OUTPUT_DIR / "galeria" / "photos" / fname

            dl_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
                "Referer": "https://strachowka.blogspot.com/",
                "sec-fetch-dest": "image",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-site": "cross-site",
            }

            # Try full res first, fall back to thumb URL
            for try_url in [item["url"], item["thumb_url"]]:
                try:
                    resp = requests.get(try_url, headers=dl_headers, timeout=20)
                    if resp.status_code == 200 and len(resp.content) > 3000:
                        fpath.write_bytes(resp.content)
                        item["local_path"] = f"photos/{fname}"
                        downloaded.append(item)
                        break
                except Exception:
                    continue

            if idx % 10 == 0:
                print(f"    Processed {idx+1}/{len(gallery_items)}, downloaded {len(downloaded)} so far...")
            time.sleep(0.4)
        except Exception as e:
            continue

    print(f"  Successfully downloaded {len(downloaded)} photos")

    # Build the gallery page
    gallery_js = """
(function() {
  var items = document.querySelectorAll('.gallery-item');
  var lightbox = document.getElementById('lightbox');
  var lbImg = document.getElementById('lb-img');
  var lbTitle = document.getElementById('lb-title');
  var lbDate = document.getElementById('lb-date');
  var lbLink = document.getElementById('lb-link');
  var lbClose = document.getElementById('lb-close');
  var current = 0;

  function open(idx) {
    current = idx;
    var item = items[idx];
    lbImg.src = item.dataset.src;
    lbTitle.textContent = item.dataset.title;
    lbDate.textContent = item.dataset.date;
    lbLink.href = '../posts/' + item.dataset.slug + '.html';
    lightbox.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function close() {
    lightbox.style.display = 'none';
    document.body.style.overflow = '';
  }

  items.forEach(function(item, idx) {
    item.addEventListener('click', function() { open(idx); });
  });

  lbClose.addEventListener('click', close);
  lightbox.addEventListener('click', function(e) {
    if (e.target === lightbox) close();
  });

  document.addEventListener('keydown', function(e) {
    if (lightbox.style.display === 'none') return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight' && current < items.length - 1) open(current + 1);
    if (e.key === 'ArrowLeft' && current > 0) open(current - 1);
  });
})();
"""

    gallery_css = """
<style>
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
  padding: 2rem 0 4rem;
}
.gallery-item {
  aspect-ratio: 4/3;
  overflow: hidden;
  cursor: pointer;
  background: #e8e2d8;
  position: relative;
}
.gallery-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease, opacity 0.2s;
  display: block;
}
.gallery-item:hover img { transform: scale(1.04); }
.gallery-item-overlay {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: linear-gradient(to top, rgba(28,25,22,0.85) 0%, transparent 100%);
  padding: 1.5rem 0.75rem 0.75rem;
  opacity: 0;
  transition: opacity 0.2s;
}
.gallery-item:hover .gallery-item-overlay { opacity: 1; }
.gallery-item-title {
  font-family: 'Crimson Pro', serif;
  font-size: 0.85rem;
  color: rgba(247,243,237,0.9);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.gallery-item-date {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.65rem;
  color: rgba(247,243,237,0.5);
  margin-top: 0.2rem;
  letter-spacing: 0.05em;
}

/* Lightbox */
#lightbox {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(20,18,16,0.95);
  z-index: 1000;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 2rem;
}
#lb-img {
  max-width: 90vw;
  max-height: 75vh;
  object-fit: contain;
  display: block;
}
#lb-info {
  margin-top: 1.25rem;
  text-align: center;
}
#lb-title {
  font-family: 'Playfair Display', serif;
  font-weight: 400;
  font-size: 1.1rem;
  color: rgba(247,243,237,0.9);
  margin-bottom: 0.35rem;
  display: block;
}
#lb-date {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.72rem;
  color: rgba(247,243,237,0.35);
  letter-spacing: 0.07em;
  display: block;
  margin-bottom: 0.75rem;
}
#lb-link {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #c8a84b;
  border-bottom: 1px solid rgba(200,168,75,0.4);
  text-decoration: none;
}
#lb-close {
  position: fixed;
  top: 1.5rem;
  right: 1.5rem;
  background: none;
  border: none;
  color: rgba(247,243,237,0.5);
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  transition: color 0.15s;
}
#lb-close:hover { color: rgba(247,243,237,0.9); }
</style>"""

    # Build gallery grid HTML
    grid_html = ""
    for item in downloaded:
        grid_html += f"""
        <div class="gallery-item"
             data-src="{item['local_path']}"
             data-title="{item['post_title'][:80]}"
             data-date="{item['post_date']}"
             data-slug="{item['post_slug']}">
          <img src="{item['local_path']}" alt="{item['post_title'][:60]}" loading="lazy">
          <div class="gallery-item-overlay">
            <div class="gallery-item-title">{item['post_title'][:80]}</div>
            <div class="gallery-item-date">{item['post_date']}</div>
          </div>
        </div>"""

    gallery_content = f"""
{gallery_css}
<div style="padding: 3rem 0 0">
  <h1 style="font-family:'Playfair Display',serif;font-weight:400;font-style:italic;font-size:2.5rem;letter-spacing:-0.02em;margin-bottom:0.5rem">Galeria</h1>
  <p style="font-family:'DM Sans',sans-serif;font-size:0.85rem;color:#9a9590;margin-bottom:0">
    {len(downloaded)} zdjec z tekstow — kliknij aby zobaczyc wieksze i przejsc do tekstu.
  </p>
</div>
<div class="gallery-grid">{grid_html}</div>

<div id="lightbox">
  <button id="lb-close">&times;</button>
  <img id="lb-img" src="" alt="">
  <div id="lb-info">
    <span id="lb-title"></span>
    <span id="lb-date"></span>
    <a id="lb-link" href="#">Czytaj tekst &rarr;</a>
  </div>
</div>
"""

    page = html_page("Galeria", gallery_content, css_path="../", nav_active="galeria")
    page = page.replace("</body>", f"<script>{gallery_js}</script></body>")
    (OUTPUT_DIR / "galeria" / "index.html").write_text(page, encoding="utf-8")

    print(f"\n Site built successfully in ./{OUTPUT_DIR}/")
    print(f"   Posts:    {len(posts_sorted)}")
    print(f"   Pages:    {len(pages)} index pages")
    print(f"   Gallery:  {len(downloaded)} photos")
    print(f"   Universe: word cloud + timeline generated")
    print(f"\nNext step: commit to GitHub and the site will deploy automatically tonight")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Osobny Swiat -- Blog Migrator")
    print("=" * 60)

    posts = fetch_all_posts()
    if not posts:
        print("No posts found. Check the blog URL and try again.")
        exit(1)

    build_site(posts)
