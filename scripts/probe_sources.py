"""Diagnostic probe — is hapoel.site alive, and is it serving our app?

The domain was bought and pointed at Vercel. A previous run from a GitHub
runner answered NXDOMAIN with no NS published, which means the delegation at
the registrar had not completed — nothing Vercel could fix. This re-checks,
and if the name now resolves it goes on to verify the site is really ours:

  * the DNS chain: which nameservers the registry publishes, and what A /
    CNAME they answer with
  * the page: the app's title, and the three Open Graph lines that a crawler
    reads when the link is pasted into WhatsApp — those are hardcoded to
    hapoel.site and cannot come from club.json
  * club.json's own url field, which is what the in-app share message uses
  * every data file the app loads at boot, and the images it points at —
    a 404 here is silent in the browser and shows up as an empty screen

Resolution goes through DNS-over-HTTPS rather than the runner's resolver, so
the answer comes from the public DNS and not from a cache on the machine.
"""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITE = "https://hapoel.site"
FALLBACK = "https://behemot46.github.io/Hapoel"

# every file app/js/app.js asks for in boot(), in the same order
DATA_FILES = ["games.json", "standings.json", "meta.json", "club.json", "roster.json",
              "player-names.json", "player-profiles.json", "player-details.json",
              "team-names.json", "history.json", "eurocup.json", "hall-of-fame.json",
              "lastseason.json", "season-stats.json", "feedback.json",
              "venue-names.json", "news.json"]

RCODE = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 5: "REFUSED"}


def log(*a):
    print("[probe]", *a, flush=True)


def resolve(name, rtype):
    """Ask a public resolver over HTTPS. Returns (rcode, [answers])."""
    try:
        r = requests.get("https://dns.google/resolve",
                         params={"name": name, "type": rtype},
                         headers={"Accept": "application/dns-json"}, timeout=20)
        d = r.json()
        status = d.get("Status", -1)
        answers = [a.get("data", "") for a in (d.get("Answer") or [])]
        auth = [a.get("data", "") for a in (d.get("Authority") or [])]
        return RCODE.get(status, str(status)), answers, auth
    except Exception as e:
        return f"FAIL {type(e).__name__}", [], [str(e)[:80]]


log("=" * 78)
log("A. DNS — has the registrar delegated the name yet?")
log("=" * 78)
resolved = False
for rtype in ("NS", "A", "AAAA", "CNAME"):
    code, answers, auth = resolve("hapoel.site", rtype)
    log(f"  hapoel.site {rtype:<6} {code:<10} {answers if answers else '—'}")
    if auth and not answers:
        log(f"      authority: {str(auth)[:150]}")
    if rtype in ("A", "CNAME") and code == "NOERROR" and answers:
        resolved = True
code, answers, _ = resolve("www.hapoel.site", "A")
log(f"  www.hapoel.site A      {code:<10} {answers if answers else '—'}")

if not resolved:
    log("")
    log("  the name still does not resolve — the delegation is not live.")
    log("  nothing to check on the site itself; stopping here.")
    raise SystemExit(0)

log("")
log("=" * 78)
log("B. the page — is it our app?")
log("=" * 78)
try:
    r = requests.get(SITE + "/", headers=UA, timeout=30, allow_redirects=True)
    r.encoding = r.apparent_encoding or "utf-8"
    html = r.text
    log(f"  {r.status_code}  {r.headers.get('Content-Type', '?')[:40]}  {len(r.content)}b")
    log(f"  final url: {r.url}")
    log(f"  server: {r.headers.get('server', '?')}  "
        f"x-vercel-id: {r.headers.get('x-vercel-id', '—')[:40]}")
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    log(f"  <title>: {title.group(1).strip() if title else 'MISSING'}")
    for prop in ("og:url", "og:title", "og:image", "og:site_name"):
        m = re.search(r'<meta property="%s" content="([^"]*)"' % prop, html)
        val = m.group(1) if m else "MISSING"
        mark = "ok " if (prop != "og:url" or "hapoel.site" in val) else "!! "
        log(f"  {mark}{prop:<12} {val}")
    can = re.search(r'<link rel="canonical" href="([^"]*)"', html)
    log(f"  canonical: {can.group(1) if can else 'MISSING'}")
except Exception as e:
    log(f"  FAIL {type(e).__name__} {str(e)[:110]}")
    raise SystemExit(0)

log("")
log("=" * 78)
log("C. the data files the app loads at boot")
log("=" * 78)
club = None
bad = 0
for f in DATA_FILES:
    url = f"{SITE}/data/{f}"
    try:
        rr = requests.get(url, headers=UA, timeout=25)
        ok = rr.status_code == 200
        try:
            d = rr.json()
            shape = (f"{len(d)} keys" if isinstance(d, dict) else f"{len(d)} items")
        except Exception:
            d, shape = None, "NOT JSON"
            ok = False
        if f == "club.json":
            club = d
        log(f"  {'ok ' if ok else '!! '}{rr.status_code}  {shape:<12} {f}")
        if not ok:
            bad += 1
    except Exception as e:
        bad += 1
        log(f"  !! FAIL {f}: {type(e).__name__} {str(e)[:60]}")

log("")
if club:
    url = club.get("url", "")
    log(f"  club.json url: {url}   "
        f"{'← hapoel.site, as it should be' if 'hapoel.site' in url else '← NOT hapoel.site'}")

log("")
log("=" * 78)
log("D. the shell and the images")
log("=" * 78)
assets = ["css/style.css", "js/app.js", "sw.js", "manifest.webmanifest",
          "icons/crest.png", "icons/icon-192.png", "icons/icon-512.png",
          "icons/apple-touch-icon.png"]
try:
    roster = requests.get(f"{SITE}/data/roster.json", headers=UA, timeout=25).json()
    photos = [p["photo"] for p in roster.get("players", []) if p.get("photo")]
    log(f"  roster points at {len(photos)} player photos")
    assets += photos
except Exception as e:
    log(f"  could not read roster for photo paths: {e}")

for a in assets:
    try:
        rr = requests.get(f"{SITE}/{a}", headers=UA, timeout=25)
        ct = rr.headers.get("Content-Type", "?").split(";")[0]
        ok = rr.status_code == 200 and len(rr.content) > 100
        if not ok:
            bad += 1
        log(f"  {'ok ' if ok else '!! '}{rr.status_code}  {len(rr.content):>7}b  {ct:<26} {a}")
    except Exception as e:
        bad += 1
        log(f"  !! FAIL {a}: {type(e).__name__} {str(e)[:60]}")

log("")
log("=" * 78)
log(f"VERDICT: hapoel.site resolves and answers. broken resources: {bad}")
log("=" * 78)
