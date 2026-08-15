"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

Round 7: photos for the four players the EuroCup feed has no headshot for.
They all played in the NBA, so Wikimedia Commons is the obvious place to
look — freely licensed and attributable, unlike scraping an image search.

This prints candidates only. Nothing is downloaded into the repo until a
human has looked at the list and confirmed the person and the licence.
"""
import json
import sys
import urllib.parse

import requests

UA = {"User-Agent": "HapoelFanApp/1.0 (https://github.com/Behemot46/Hapoel; fan project)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"

WANTED = [
    ("Devontae Cacok", "דבונטה קאקוק"),
    ("Kenny Lofton Jr.", "קני לופטון"),
    ("Shake Milton", "שייק מילטון"),
    ("David Roddy", "דייוויד רודי"),
]


def log(*a):
    print("[probe]", *a, flush=True)


def search(term):
    params = {
        "action": "query", "format": "json",
        "generator": "search",
        "gsrsearch": f'filetype:bitmap {term}',
        "gsrnamespace": "6", "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": "600",
    }
    try:
        r = requests.get(COMMONS, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log("  FAIL", term, type(e).__name__, str(e)[:120])
        return None


def probe():
    for latin, he in WANTED:
        log("")
        log("=" * 68)
        log(f"{latin}  ({he})")
        log("=" * 68)
        data = search(latin)
        pages = ((data or {}).get("query") or {}).get("pages") or {}
        if not pages:
            log("  no results on Commons")
            continue
        for pg in list(pages.values())[:8]:
            ii = (pg.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata") or {}
            def m(k):
                v = (meta.get(k) or {}).get("value")
                if not isinstance(v, str):
                    return ""
                # extmetadata values arrive as little bits of html
                import re as _re
                return _re.sub(r"<[^>]+>", "", v).strip()[:70]
            log(f"  {pg.get('title')}")
            log(f"     {ii.get('width')}x{ii.get('height')}  {ii.get('url','')[:100]}")
            log(f"     licence: {m('LicenseShortName') or '?'} | by: {m('Artist') or '?'}")
            log(f"     desc: {m('ImageDescription')[:70]}")


if __name__ == "__main__":
    probe()
    log("")
    log("probe done — nothing downloaded")
