"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

The development sandbox cannot reach basket.co.il, hapoel.co.il or the
EuroCup API, so this runs on Actions (workflow_dispatch) and prints enough
structure to write a parser against. Run it, read the log, then write the
real code.

Round 6: the club's own squad page. It should carry the full squad — not
only the ten registered for Europe — with Hebrew names and birth dates.
First question is whether it is server-rendered at all, or a JS shell with
an API behind it.
"""
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/json;q=0.9",
      "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"}

TEAM_URL = "https://hapoel.co.il/team"
# names we know are in the squad — if these appear in the HTML it is rendered
KNOWN = ["הארפר", "הובר", "זוסמן", "לוי", "Harper", "Huber", "Zoosman", "קאקוק"]


def log(*a):
    print("[probe]", *a, flush=True)


def get(url, as_json=False):
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
    except Exception as e:
        log("  FAIL", url, type(e).__name__, str(e)[:120])
        return None
    log(f"  {r.status_code} {len(r.content):>8}b  {r.url}")
    if r.status_code != 200:
        return None
    if as_json:
        try:
            return r.json()
        except Exception:
            log("    (not json)", r.text[:160].replace("\n", " "))
            return None
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def section(t):
    log("")
    log("=" * 68)
    log(t)
    log("=" * 68)


def probe_page():
    section("A. Is the squad page server-rendered?")
    html = get(TEAM_URL)
    if not html:
        return None
    log(f"  {len(html)} chars of html")
    hits = [k for k in KNOWN if k in html]
    log("  known squad names present in raw html:", hits or "NONE — likely a JS shell")

    soup = BeautifulSoup(html, "html.parser")
    log("  title:", (soup.title.string or "").strip()[:80] if soup.title else "-")

    # embedded state blobs used by common frameworks
    for pat, label in ((r"__NEXT_DATA__", "Next.js"), (r"window\.__NUXT__", "Nuxt"),
                       (r"wp-json", "WordPress REST"), (r"__INITIAL_STATE__", "initial state"),
                       (r"application/ld\+json", "JSON-LD")):
        if re.search(pat, html):
            log(f"  contains {label}")

    for sc in soup.find_all("script", type="application/ld+json")[:3]:
        log("  ld+json:", (sc.string or "")[:300].replace("\n", " "))

    # any API-looking URLs referenced by the page
    urls = set(re.findall(r'["\'](/(?:api|wp-json)/[^"\']{3,90})["\']', html))
    urls |= set(re.findall(r'["\'](https?://[^"\']*(?:api|wp-json)[^"\']{0,70})["\']', html))
    log(f"  {len(urls)} api-ish urls referenced:")
    for u in sorted(urls)[:20]:
        log("   ", u)
    return html, soup


def probe_structure(soup):
    section("B. Page structure — where would players live?")
    # repeated blocks are usually the player cards
    from collections import Counter
    classes = Counter()
    for tag in soup.find_all(True):
        for c in (tag.get("class") or []):
            classes[c] += 1
    log("  most repeated class names:")
    for c, n in classes.most_common(30):
        if n >= 3:
            log(f"    {n:>4}  {c}")

    links = [(a.get_text(" ", strip=True)[:32], a["href"])
             for a in soup.find_all("a", href=True)]
    playerish = [(t, h) for t, h in links
                 if re.search(r"player|sagal|squad|/team/", h, re.I) and t]
    log(f"  {len(playerish)} player-ish links:")
    for t, h in playerish[:25]:
        log(f"    {t!r} -> {h[:90]}")

    # any date that looks like a birth date anywhere on the page
    dates = re.findall(r"\b\d{1,2}[./]\d{1,2}[./](?:19|20)\d{2}\b", soup.get_text(" "))
    log(f"  {len(dates)} date-like strings on the page, e.g. {dates[:10]}")


def probe_api():
    section("C. Common API shapes behind an Israeli club site")
    for u in ("https://hapoel.co.il/wp-json/wp/v2/players?per_page=40",
              "https://hapoel.co.il/wp-json/wp/v2/types",
              "https://hapoel.co.il/wp-json",
              "https://hapoel.co.il/api/team",
              "https://hapoel.co.il/api/players"):
        d = get(u, as_json=True)
        if d is None:
            continue
        if isinstance(d, list):
            log(f"    list[{len(d)}]")
            if d:
                log("    keys:", sorted(d[0].keys())[:25] if isinstance(d[0], dict) else type(d[0]))
                log("    sample:", json.dumps(d[0], ensure_ascii=False)[:400])
        elif isinstance(d, dict):
            log("    keys:", sorted(d.keys())[:30])
            if "routes" in d:
                routes = [r for r in d["routes"] if re.search(r"player|team|sagal", r, re.I)]
                log("    player-ish routes:", routes[:20])


def probe_one_player(soup):
    section("D. A single player page")
    if soup is None:
        return
    hrefs = [a["href"] for a in soup.find_all("a", href=True)
             if re.search(r"player", a["href"], re.I)]
    if not hrefs:
        log("  no player links found on the squad page")
        return
    url = hrefs[0]
    if url.startswith("/"):
        url = "https://hapoel.co.il" + url
    html = get(url)
    if not html:
        return
    s = BeautifulSoup(html, "html.parser")
    txt = re.sub(r"\s+", " ", s.get_text(" ", strip=True))
    log("  page text (first 900 chars):")
    log("   ", txt[:900])
    for label in ("תאריך לידה", "גובה", "משקל", "עמדה", "לידה", "גיל", "מספר"):
        m = re.search(label + r"[:\s]*([^|]{0,40})", txt)
        if m:
            log(f"    {label} -> {m.group(1)[:60]!r}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    page = None
    if which in ("all", "page", "structure", "player"):
        page = probe_page()
    if page and which in ("all", "structure"):
        probe_structure(page[1])
    if which in ("all", "api"):
        probe_api()
    if page and which in ("all", "player"):
        probe_one_player(page[1])
    log("")
    log("probe done")
