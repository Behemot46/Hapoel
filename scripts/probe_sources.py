"""Diagnostic probe — does hapoel.site actually serve the app?

The sandbox proxy refuses the domain (403 on CONNECT), so this is the only
way to see it. Checks the things that would break on a move to a new host:
the page itself, the data files the app fetches on boot, the service worker
and its cache header, the icons, and the Open Graph tags a WhatsApp preview
reads. Also checks live.json, which until now was published only to the
branch GitHub Pages serves.
"""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITE = "https://hapoel.site"


def log(*a):
    print("[probe]", *a, flush=True)


def get(path, note=""):
    url = SITE + path
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        cc = r.headers.get("Cache-Control", "—")
        log(f"  {path:<34} {r.status_code}  {r.headers.get('Content-Type','?')[:28]:<28}"
            f" {len(r.content):>7}b  cache={cc[:38]} {note}")
        return r
    except Exception as e:
        log(f"  {path:<34} FAIL {type(e).__name__} {str(e)[:90]}")
        return None


log("=" * 78)
log("A. the pages and assets the app needs")
log("=" * 78)
root = get("/")
for p in ("/index.html", "/js/app.js", "/css/style.css", "/sw.js",
          "/manifest.webmanifest", "/icons/icon-512.png",
          "/data/club.json", "/data/games.json", "/data/standings.json",
          "/data/meta.json", "/data/hall-of-fame.json", "/data/history.json",
          "/data/roster.json", "/data/feedback.json",
          "/img/players/david-roddy.jpg", "/hapoel-standalone.html"):
    get(p)
log("")
log("  live.json — 404 here means the live score would never show:")
get("/data/live.json", "(404 is expected when no game is on)")

log("")
log("=" * 78)
log("B. is it serving OUR app, and the new domain?")
log("=" * 78)
if root is not None and root.status_code == 200:
    html = root.text
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    log("  title:", (t.group(1).strip() if t else "?"))
    for prop in ("og:url", "og:title", "og:image", "og:description"):
        m = re.search(rf'property="{prop}"[^>]*content="([^"]*)"', html)
        log(f"  {prop:<16}", m.group(1)[:80] if m else "MISSING")
    m = re.search(r'rel="canonical"[^>]*href="([^"]*)"', html)
    log("  canonical       ", m.group(1) if m else "MISSING")
    log("  registers sw    ", 'navigator.serviceWorker.register("sw.js"' in html)

log("")
log("  club.json url — what a shared WhatsApp link will point at:")
c = get("/data/club.json")
if c is not None and c.status_code == 200:
    try:
        log("    url =", c.json().get("url"))
    except Exception as e:
        log("    could not parse:", e)

log("")
log("=" * 78)
log("C. the old address still up?")
log("=" * 78)
try:
    r = requests.get("https://behemot46.github.io/Hapoel/data/club.json",
                     headers=UA, timeout=30)
    log(f"  github.io club.json: {r.status_code}")
    if r.status_code == 200:
        log("    url =", r.json().get("url"))
except Exception as e:
    log(f"  github.io: FAIL {type(e).__name__} {str(e)[:90]}")
