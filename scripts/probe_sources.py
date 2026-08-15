"""Diagnostic probe — player stats for the season that just ended.

The stats page has a full team table for 2025/26 but not a single player line.
Two possible sources:

  A. the EuroCup feed for the previous season code. This season is U2026, so
     last season should be U2025 — confirm that, and print what a player row
     actually carries (games, minutes, points, rebounds, assists, rating).
  B. the league's own site, which is the only place Winner League averages
     live. Print enough of the page to see whether a per-player table exists
     and how it is shaped.

Anything written into the app has to say which competition it is from: a
EuroCup average and a Winner League average are different numbers, and one
labelled as the other is a lie even when both are accurate.
"""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
API = "https://api-live.euroleague.net/v2/competitions/U/seasons"


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 70)
log("A. EuroCup player stats, by season code")
log("=" * 70)
for season in ("U2025", "U2026"):
    url = f"{API}/{season}/clubs/JER/people/stats"
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        log(f"  {season}: {r.status_code} {len(r.text)} chars")
        if r.status_code != 200:
            continue
        j = r.json()
        rows = j.get("data", j if isinstance(j, list) else [])
        log(f"    {len(rows)} rows")
        if rows:
            log("    keys on a row:", sorted(rows[0].keys()))
            first = rows[0]
            for k in ("player", "person", "stats", "averages", "accumulated"):
                if isinstance(first.get(k), dict):
                    log(f"    {k} keys:", sorted(first[k].keys())[:26])
            log("    row 0 verbatim:", json.dumps(first, ensure_ascii=False)[:1100])
    except Exception as e:
        log(f"  {season}: FAIL {type(e).__name__} {str(e)[:140]}")

log("")
log("=" * 70)
log("B. the league site — are there per-player averages?")
log("=" * 70)
for url in ("https://basket.co.il/team-stats.asp?TeamId=1095&cYear=2026",
            "https://basket.co.il/team.asp?TeamId=1095&cYear=2026",
            "https://basket.co.il/stats.asp?cYear=2026"):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.encoding = r.apparent_encoding or "windows-1255"
        log(f"  {url} -> {r.status_code} {len(r.text)} chars")
        if r.status_code != 200:
            continue
        # a stats table would name the usual columns
        for word in ("נקודות", "ריבאונד", "אסיסט", "דקות", "PlayerId", "ממוצע"):
            log(f"    contains {word!r}:", word in r.text)
        m = re.findall(r"PlayerId=(\d+)[^>]*>([^<]{2,40})", r.text)[:8]
        if m:
            log("    player links:", m)
    except Exception as e:
        log(f"  {url}: FAIL {type(e).__name__} {str(e)[:140]}")
