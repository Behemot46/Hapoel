"""Diagnostic probe — round 10: get a real, fetchable headshot for David Roddy.

Round 9 said the Proballers cache URL from link 1 answers 404, and that link 2
points at an Instagram crawler image we can neither verify nor re-host. So:

A. re-resolve link 1 and print its imgurl/imgrefurl untruncated, then try the
   image both bare and with a Referer (image CDNs often gate on it);
B. fetch the Proballers player page itself and read og:image — the cache path
   in a search result can expire, the page's own tag should not;
C. try the EuroLeague/EuroCup person record, which is where every other photo
   in this app comes from, in case Roddy has one under a code we missed.
"""
import io
import re
import urllib.parse

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,image/*;q=0.9,*/*;q=0.8"}

LINK1 = "https://share.google/gbAL2cjyQalVNvrBp"


def log(*a):
    print("[probe]", *a, flush=True)


def try_image(url, label, referer=None):
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    try:
        r = requests.get(url, headers=h, timeout=30, stream=True)
        ctype = r.headers.get("Content-Type", "?")
        data = r.raw.read(600000)
        log(f"  {label}: {r.status_code} {ctype} {len(data)} bytes")
        if ctype.startswith("image/"):
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(data))
                log(f"    -> image {im.size} {im.mode}  OK")
                return True
            except Exception as e:
                log("    could not decode:", e)
        return False
    except Exception as e:
        log(f"  {label}: FAIL {type(e).__name__} {str(e)[:120]}")
        return False


log("=" * 70)
log("A. re-resolve link 1, untruncated")
log("=" * 70)
r = requests.get(LINK1, headers=UA, timeout=30, allow_redirects=True)
r.encoding = r.apparent_encoding or "utf-8"
log("  final url:", r.url[:200])
qs = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
imgurl = None
for k in ("imgurl", "imgrefurl", "docid"):
    if k in qs:
        log(f"  {k} = {urllib.parse.unquote(qs[k][0])}")
        if k == "imgurl":
            imgurl = urllib.parse.unquote(qs[k][0])
if imgurl:
    try_image(imgurl, "imgurl bare")
    try_image(imgurl, "imgurl w/ referer", referer="https://www.proballers.com/")

log("")
log("=" * 70)
log("B. the Proballers player page itself")
log("=" * 70)
for page in ("https://www.proballers.com/basketball/player/61146/david-roddy",
             "https://www.proballers.com/search?q=david+roddy"):
    try:
        p = requests.get(page, headers=UA, timeout=30)
        log(f"  {page} -> {p.status_code} {len(p.text)} chars")
        if p.status_code != 200:
            continue
        for m in re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', p.text):
            log("    og:image:", m[:220])
            try_image(m, "og:image", referer=page)
        for m in re.findall(r'https://[^"\']*?/ul/player/[^"\']+\.(?:png|jpg|jpeg|webp)', p.text)[:6]:
            log("    ul/player:", m[:220])
        for m in re.findall(r'href="(/basketball/player/[^"]*roddy[^"]*)"', p.text, re.I)[:6]:
            log("    link:", m)
    except Exception as e:
        log(f"  {page}: FAIL {type(e).__name__} {str(e)[:120]}")

log("")
log("=" * 70)
log("C. EuroCup person records that mention Roddy or Milton")
log("=" * 70)
try:
    api = ("https://api-live.euroleague.net/v2/competitions/U/seasons/U2026"
           "/clubs/JER/people")
    j = requests.get(api, headers={"Accept": "application/json"}, timeout=30).json()
    people = j.get("data", j if isinstance(j, list) else [])
    log(f"  {len(people)} people in the JER squad feed")
    for p in people:
        person = p.get("person", p)
        name = person.get("name") or person.get("alias") or "?"
        code = person.get("code") or person.get("personCode")
        img = (person.get("images") or {}).get("headshot") or person.get("imageUrl")
        log(f"    {name:<32} code={code}  headshot={'yes' if img else 'no'}")
except Exception as e:
    log(f"  FAIL {type(e).__name__} {str(e)[:160]}")
