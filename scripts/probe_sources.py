"""Diagnostic probe — round 11: the real Proballers page for David Roddy.

Round 10 printed link 1's imgrefurl: /basketball/player/190935/roddy-david.
The cache URL from the search result is expired (404 bare and with a Referer),
but the page it came from should carry a live one. Pull the page, list every
image it holds, and try the plausible ones.

Also fixes the EuroCup squad listing — that feed answers a bare list, not the
{"data": [...]} envelope the earlier probe assumed.
"""
import io
import re
import urllib.parse

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,image/*;q=0.9,*/*;q=0.8"}

PAGE = "https://www.proballers.com/basketball/player/190935/roddy-david"


def log(*a):
    print("[probe]", *a, flush=True)


def try_image(url, label, referer=PAGE):
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    try:
        r = requests.get(url, headers=h, timeout=30, stream=True)
        ctype = r.headers.get("Content-Type", "?")
        data = r.raw.read(900000)
        ok = r.status_code == 200 and ctype.startswith("image/")
        log(f"  {label}: {r.status_code} {ctype} {len(data)} bytes")
        if ok:
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(data))
                log(f"    -> {im.size} {im.mode}  USABLE")
                return True
            except Exception as e:
                log("    could not decode:", e)
        return False
    except Exception as e:
        log(f"  {label}: FAIL {type(e).__name__} {str(e)[:120]}")
        return False


log("=" * 70)
log("A. the real Proballers page for Roddy")
log("=" * 70)
p = requests.get(PAGE, headers=UA, timeout=30)
log(f"  {PAGE} -> {p.status_code} {len(p.text)} chars")
html = p.text
log("  title:", (re.search(r"<title>(.*?)</title>", html, re.S) or [None, "?"])[1].strip()[:120])

seen = []
for m in re.findall(r'(?:src|content|data-src)="(https://[^"]+?\.(?:png|jpg|jpeg|webp)[^"]*)"', html):
    if m not in seen:
        seen.append(m)
log(f"  {len(seen)} distinct image urls on the page")
for u in seen[:20]:
    tag = "  <-- player?" if "/ul/player/" in u or "roddy" in u.lower() else ""
    log("   ", urllib.parse.unquote(u)[:200] + tag)

log("")
log("  trying the ones that look like a player image:")
for u in seen:
    if "/ul/player/" in u or "roddy" in u.lower():
        try_image(u, u.rsplit("/", 1)[-1][:60])

log("")
log("=" * 70)
log("B. the JER squad feed — who has a headshot and who does not")
log("=" * 70)
try:
    api = ("https://api-live.euroleague.net/v2/competitions/U/seasons/U2026"
           "/clubs/JER/people")
    j = requests.get(api, headers={"Accept": "application/json"}, timeout=30).json()
    people = j["data"] if isinstance(j, dict) and "data" in j else j
    log(f"  {len(people)} people in the feed")
    for row in people:
        person = row.get("person", row) if isinstance(row, dict) else {}
        name = person.get("name") or person.get("alias") or "?"
        code = person.get("code") or person.get("personCode")
        img = person.get("imageUrl") or (person.get("images") or {}).get("headshot")
        log(f"    {name[:34]:<34} code={str(code):<10} headshot={'yes' if img else 'no'}")
except Exception as e:
    log(f"  FAIL {type(e).__name__} {str(e)[:200]}")
