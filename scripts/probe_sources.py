"""Diagnostic probe — round 9: confirm the two candidate photo URLs.

Link 1 resolved to a Proballers headshot of David Roddy. Link 2 resolved to
an Instagram post, which is neither verifiable nor ours to re-host — but the
same results page carried a basket.co.il file whose path names Shake Milton.
Print both untruncated and check that they are really images.
"""
import re
import sys
import urllib.parse

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,image/*;q=0.9,*/*;q=0.8"}

RODDY = ("https://www.proballers.com/media/cache/resize_600_png/"
         "https---www.proballers.com/ul/player/"
         "david-roddy-1f0fe381-d437-6f74-ad19-414dbecff047.png")
LINK2 = "https://share.google/BLobTWj4FcMsUfGzo"


def log(*a):
    print("[probe]", *a, flush=True)


def head(url, label):
    try:
        r = requests.get(url, headers=UA, timeout=30, stream=True)
        ctype = r.headers.get("Content-Type", "?")
        data = r.raw.read(400000)
        log(f"  {label}: {r.status_code} {ctype} {len(data)} bytes")
        if ctype.startswith("image/"):
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(data))
                log(f"    image {im.size} {im.mode}")
            except Exception as e:
                log("    could not decode:", e)
        return r.status_code == 200 and ctype.startswith("image/")
    except Exception as e:
        log(f"  {label}: FAIL {type(e).__name__} {str(e)[:120]}")
        return False


log("=" * 70)
log("A. the Roddy headshot from link 1")
log("=" * 70)
log("  " + RODDY)
head(RODDY, "roddy")

log("")
log("=" * 70)
log("B. untruncated image urls behind link 2")
log("=" * 70)
r = requests.get(LINK2, headers=UA, timeout=30, allow_redirects=True)
r.encoding = r.apparent_encoding or "utf-8"
html = r.text
# the imgrefurl / imgurl parameters carry the real target
q = urllib.parse.urlparse(r.url).query
for k, v in urllib.parse.parse_qs(q).items():
    if k in ("imgurl", "imgrefurl", "docid"):
        log(f"  {k} = {v[0][:300]}")
urls = []
for u in re.findall(r'https?://[^\s"\'<>\\]+', html):
    if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", u, re.I) and u not in urls:
        urls.append(u)
log(f"  {len(urls)} image urls, full text:")
for u in urls[:14]:
    log("   ", urllib.parse.unquote(u)[:260])
