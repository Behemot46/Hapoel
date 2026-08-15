"""Diagnostic probe: cross-check what the app claims against the sources.

The automatic files are refetched constantly and mostly check themselves.
The dangerous ones are the files a human wrote once and nobody looked at
again: shirt numbers, heights, birth years, the count of titles, the year of
each one. This reads the live sources and prints, field by field, where the
committed data and the source disagree.

It only compares and prints. Nothing here writes to app/data, because the
right fix for a disagreement is a person deciding which side is wrong.

  A. the squad, against hapoel.co.il and the EuroCup feed
  B. the titles and the timeline, against Hebrew Wikipedia
"""
import json
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import club_roster

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; cross-check)"}
WIKI = "https://he.wikipedia.org/wiki/%D7%94%D7%A4%D7%95%D7%A2%D7%9C_%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D_(%D7%9B%D7%93%D7%95%D7%A8%D7%A1%D7%9C)"
EUROCUP_PEOPLE = ("https://api-live.euroleague.net/v2/competitions/U/seasons/"
                  "U2026/clubs/JER/people")


def log(*a):
    print("[check]", *a, flush=True)


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fetch(url, **kw):
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r


def norm(s):
    """Hebrew names differ by apostrophe style and spacing between sources."""
    return re.sub(r"[^\w]", "", (s or "").replace("׳", "'").replace("״", '"')).lower()


# ------------------------------------------------------------------ A. squad

log("=" * 78)
log("A. the squad, ours against the club's own page")
log("=" * 78)
ours = {p.get("nameHe") or p["name"]: p for p in (load("roster.json") or {}).get("players", [])}
log(f"  committed: {len(ours)} players")

try:
    theirs = {p["name"]: p for p in club_roster.parse_team_page(
        fetch("https://hapoel.co.il/team").text, log=lambda *a: None)}
    log(f"  club page: {len(theirs)} players")
except Exception as e:
    theirs = {}
    log(f"  club page FAILED: {type(e).__name__} {str(e)[:110]}")

if theirs:
    by_norm = {norm(k): v for k, v in theirs.items()}
    for name, p in ours.items():
        t = by_norm.get(norm(name))
        if not t:
            log(f"  !! {name}: in the app, not on the club page")
            continue
        for field, label in (("number", "מספר"), ("height", "גובה"),
                             ("birthDate", "תאריך לידה")):
            a, b = p.get(field), t.get(field)
            if a and b and str(a) != str(b):
                log(f"  !! {name}: {label} ours={a} theirs={b}")
    for name in theirs:
        if norm(name) not in {norm(k) for k in ours}:
            log(f"  !! {name}: on the club page, not in the app")
    log("  (no line above means every shared field agrees)")

log("")
log("-" * 78)
log("the same squad against the EuroCup feed")
log("-" * 78)
try:
    people = fetch(EUROCUP_PEOPLE, params={"limit": 100}).json()
    rows = people.get("data") if isinstance(people, dict) else people
    euro = {}
    for row in rows or []:
        person = row.get("person") or row
        nm = person.get("name") or ""
        if "," in nm:  # "SMITH, JALEEN"
            last, first = [x.strip() for x in nm.split(",", 1)]
            nm = f"{first} {last}"
        euro[norm(nm)] = {
            "name": nm.title(),
            "height": person.get("height"),
            "birthDate": (person.get("birthDate") or "")[:10],
            "number": row.get("dorsal") or row.get("jersey"),
        }
    log(f"  eurocup feed: {len(euro)} people")
    for name, p in ours.items():
        e = euro.get(norm(p.get("name")))
        if not e:
            continue
        for field, label in (("height", "גובה"), ("number", "מספר")):
            a, b = p.get(field), e.get(field)
            if a and b and str(a) != str(b):
                log(f"  !! {p['name']}: {label} ours={a} eurocup={b}")
        if p.get("birthDate") and e.get("birthDate") and p["birthDate"] != e["birthDate"]:
            log(f"  !! {p['name']}: תאריך לידה ours={p['birthDate']} eurocup={e['birthDate']}")
    log("  (no line above means every shared field agrees)")
except Exception as e:
    log(f"  eurocup FAILED: {type(e).__name__} {str(e)[:110]}")

# -------------------------------------------------------------- B. the club

log("")
log("=" * 78)
log("B. titles and timeline, against Hebrew Wikipedia")
log("=" * 78)
hist = load("history.json") or {}
log("  ours (trophies):")
for t in hist.get("trophies", []):
    log(f"    {t.get('count')}x {t.get('name')}  ({t.get('years')})")

try:
    page = fetch(WIKI).text
    text = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
    log("")
    log(f"  wikipedia page: {len(text)} characters of text")
    log("  every year we print, and whether the page carries it:")
    for t in hist.get("trophies", []):
        for y in re.findall(r"(?:19|20)\d{2}", str(t.get("years") or "")):
            hits = len(re.findall(re.escape(y), text))
            log(f"    {t.get('name')} {y}: {hits} mentions"
                + ("" if hits else "   !! NOT ON THE PAGE"))
    log("")
    log("  timeline years, and whether the page mentions them at all:")
    for ev in hist.get("timeline", [])[:40]:
        y = str(ev.get("year") or "")[:4]
        if not y:
            continue
        hit = y in text
        log(f"    {y} {'ok' if hit else '!! not on the page'}  {str(ev.get('title'))[:52]}")
except Exception as e:
    log(f"  wikipedia FAILED: {type(e).__name__} {str(e)[:110]}")

log("")
log("=" * 78)
log("done. nothing was written.")
