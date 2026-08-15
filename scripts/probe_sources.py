"""Diagnostic probe — a high-resolution club crest.

The crest supplied is 160x160. That is plenty for the 38px header mark, but a
PWA icon is 512x512 and upscaling 3.2x turns crisp lettering into mush. The
club's own site and its social cards usually carry a larger original — find
the biggest one that is actually the crest.
"""
import io
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def log(*a):
    print("[probe]", *a, flush=True)


def measure(url, label):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        ct = r.headers.get("Content-Type", "?")
        if r.status_code != 200 or not ct.startswith("image/"):
            log(f"  {label}: {r.status_code} {ct[:24]}")
            return None
        from PIL import Image
        im = Image.open(io.BytesIO(r.content))
        log(f"  {label}: {im.size} {im.mode} {len(r.content)}b  {url[:88]}")
        return (im.size[0] * im.size[1], url, im.size)
    except Exception as e:
        log(f"  {label}: FAIL {type(e).__name__} {str(e)[:80]}")
        return None


found = []
log("=" * 74)
log("A. images on the club's own pages")
log("=" * 74)
for page in ("https://hapoel.co.il/", "https://hapoel.co.il/team"):
    try:
        r = requests.get(page, headers=UA, timeout=30)
        r.encoding = r.apparent_encoding or "utf-8"
        urls = []
        for m in re.findall(r'(?:src|href|content)="([^"]+\.(?:png|svg|jpg|webp))"', r.text, re.I):
            u = m if m.startswith("http") else requests.compat.urljoin(page, m)
            if u not in urls:
                urls.append(u)
        picks = [u for u in urls
                 if re.search(r"logo|crest|emblem|semel|icon|apple|favicon|share|og", u, re.I)]
        log(f"  {page}: {len(urls)} images, {len(picks)} look like a mark")
        for u in picks[:12]:
            if u.lower().endswith(".svg"):
                log(f"    SVG (vector, scales to any size): {u[:110]}")
                found.append((10 ** 9, u, "svg"))
                continue
            got = measure(u, "      ")
            if got:
                found.append(got)
    except Exception as e:
        log(f"  {page}: FAIL {type(e).__name__} {str(e)[:90]}")

log("")
log("=" * 74)
log("B. the usual fixed locations")
log("=" * 74)
for u in ("https://hapoel.co.il/favicon.ico",
          "https://hapoel.co.il/apple-touch-icon.png",
          "https://hapoel.co.il/images/logo.png",
          "https://upload.wikimedia.org/wikipedia/he/thumb/9/9d/Hapoel_Jerusalem_B.C._logo.png/512px-Hapoel_Jerusalem_B.C._logo.png",
          "https://upload.wikimedia.org/wikipedia/he/9/9d/Hapoel_Jerusalem_B.C._logo.png"):
    got = measure(u, u.split("/")[-1][:34])
    if got:
        found.append(got)

log("")
log("=" * 74)
log("BEST CANDIDATES (largest first)")
log("=" * 74)
for area, u, size in sorted(found, reverse=True)[:6]:
    log(f"  {size}  {u}")
if not found:
    log("  nothing usable — the 160px original stays the source")
