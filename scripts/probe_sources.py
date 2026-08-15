"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

Round 8: resolve two share.google links the founder sent, so we can see what
they actually point at before anything is downloaded into the repo. Prints
the redirect chain, the page title and any image URLs; downloads nothing.
"""
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.8",
      "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"}

LINKS = [
    "https://share.google/gbAL2cjyQalVNvrBp",
    "https://share.google/BLobTWj4FcMsUfGzo",
]


def log(*a):
    print("[probe]", *a, flush=True)


def probe(url):
    log("")
    log("=" * 70)
    log(url)
    log("=" * 70)
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
    except Exception as e:
        log("  FAIL", type(e).__name__, str(e)[:160])
        return
    log(f"  status {r.status_code}  content-type {r.headers.get('Content-Type','?')}  "
        f"{len(r.content)} bytes")
    for h in r.history:
        log(f"  redirect {h.status_code} -> {h.headers.get('Location','')[:150]}")
    log(f"  FINAL: {r.url[:200]}")

    ctype = r.headers.get("Content-Type", "")
    if ctype.startswith("image/"):
        log("  this URL is the image itself")
        return

    r.encoding = r.apparent_encoding or "utf-8"
    html = r.text
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if t:
        log("  title:", re.sub(r"\s+", " ", t.group(1))[:160])

    for prop in ("og:image", "og:title", "og:description", "twitter:image"):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)',
                      html, re.I)
        if not m:
            m = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{prop}["\']',
                          html, re.I)
        if m:
            log(f"  {prop}: {m.group(1)[:170]}")

    imgs = re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?', html, re.I)
    seen, keep = set(), []
    for u in imgs:
        if u in seen:
            continue
        seen.add(u)
        keep.append(u)
    log(f"  {len(keep)} distinct image urls on the page; first 12:")
    for u in keep[:12]:
        log("   ", u[:170])


if __name__ == "__main__":
    for u in LINKS:
        probe(u)
    log("")
    log("probe done — nothing downloaded")
