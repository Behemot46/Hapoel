"""Diagnostic probe: where the club publishes its own fixture list.

The club site is already the source for the squad (/team), and it is the only
place that carries pre-season games at all. So the question is narrow: which
URL holds the schedule, and what does its markup look like, so a parser can
be written against real structure instead of a guess.

Three things, in order:
  1. crawl the home page for any internal link that reads like a schedule
  2. try the paths a site like this usually uses, and report status + size
  3. for anything that answers, dump the repeating structure: tables, and
     the most common repeated class names, with a sample of their text

Nothing is written. This is a scratch tool, rewritten per question.
"""
import collections
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
BASE = "https://hapoel.co.il"

HINT = re.compile(r"משחק|לוח|מחזור|תוצא|game|match|schedul|fixtur|calendar", re.I)

CANDIDATES = [
    "/games", "/game", "/schedule", "/fixtures", "/matches", "/calendar",
    "/לוח-משחקים", "/משחקים", "/תוצאות", "/לוח", "/season", "/results",
    "/wp-json/wp/v2/pages?per_page=100", "/sitemap.xml", "/sitemap_index.xml",
]


def log(*a):
    print("[probe]", *a, flush=True)


def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        return r
    except Exception as e:
        log(f"   !! {e}")
        return None


log("=" * 76)
log("A. internal links on the home page that read like a schedule")
log("=" * 76)
home = get(BASE + "/")
seen = set()
if home is not None and home.ok:
    log(f"  home: HTTP {home.status_code}, {len(home.content)} bytes")
    soup = BeautifulSoup(home.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        label = a.get_text(" ", strip=True)
        if not HINT.search(href) and not HINT.search(label):
            continue
        full = urllib.parse.urljoin(BASE, href)
        if not full.startswith(BASE) or full in seen:
            continue
        seen.add(full)
        log(f"    {label[:38]:<38} -> {full[:96]}")
    if not seen:
        log("    (no link matched the hint)")
else:
    log(f"  home failed: {home.status_code if home is not None else 'no response'}")

log("")
log("=" * 76)
log("B. likely paths")
log("=" * 76)
alive = []
for path in CANDIDATES:
    r = get(BASE + path)
    if r is None:
        log(f"  {path:<40} ERROR")
        continue
    ctype = (r.headers.get("content-type") or "")[:40]
    log(f"  {path:<40} {r.status_code}  {len(r.content):>8} bytes  {ctype}")
    if r.ok and len(r.content) > 2000:
        alive.append((path, r))

# anything found by crawling counts too
for full in list(seen)[:6]:
    r = get(full)
    if r is not None and r.ok and len(r.content) > 2000:
        alive.append((full.replace(BASE, ""), r))

log("")
log("=" * 76)
log("C. structure of the pages that answered")
log("=" * 76)
for path, r in alive[:6]:
    log("-" * 70)
    log(f"  {path}")
    log("-" * 70)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.find("title")
    log(f"    <title>: {(title.get_text(strip=True) if title else '')[:90]}")

    tables = soup.find_all("table")
    log(f"    tables: {len(tables)}")
    for t in tables[:2]:
        rows = t.find_all("tr")
        log(f"      table with {len(rows)} rows, first three:")
        for tr in rows[:3]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            log(f"        {' | '.join(c for c in cells if c)[:140]}")

    # the repeating block is usually the fixture card
    classes = collections.Counter()
    for el in soup.find_all(class_=True):
        for c in el.get("class"):
            classes[c] += 1
    common = [(c, n) for c, n in classes.most_common(40)
              if n >= 3 and HINT.search(c)]
    log(f"    repeated classes that read like fixtures: {common[:10] or '(none)'}")
    if not common:
        log(f"    most repeated classes overall: {classes.most_common(8)}")

    # dates in the visible text are the strongest hint the page holds a schedule
    text = soup.get_text(" ", strip=True)
    dates = re.findall(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b", text)
    times = re.findall(r"\b\d{1,2}:\d{2}\b", text)
    log(f"    date-like tokens: {len(dates)} {dates[:10]}")
    log(f"    time-like tokens: {len(times)} {times[:10]}")
    for word in ("הפועל ירושלים", "מכבי", "הכנה", "גביע", "יורוקאפ", "ליגת"):
        if word in text:
            log(f"    mentions ״{word}״")
    log("")

log("done. nothing was written.")
