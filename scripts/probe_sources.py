"""Diagnostic probe — round 2 on last season's player stats.

Round 1: the EuroCup U2025 endpoint answers 200 with 23 KB, so the data is
there and only the envelope guess was wrong — print the real shape. And the
league's own team page for cYear=2026 (the 2025/26 season) contains נקודות,
ריבאונד, אסיסט and ממוצע next to PlayerId links, so a per-player table exists
there too — print its columns.

Two competitions, two different sets of numbers. Whatever ends up in the app
has to name which one it is.
"""
import json
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 70)
log("A. EuroCup U2025 — the real envelope")
log("=" * 70)
url = ("https://api-live.euroleague.net/v2/competitions/U/seasons/U2025"
       "/clubs/JER/people/stats")
r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
j = r.json()
log("  top-level type:", type(j).__name__)
if isinstance(j, dict):
    log("  top-level keys:", sorted(j.keys()))
    for k, v in j.items():
        log(f"    {k}: {type(v).__name__}" +
            (f" len={len(v)}" if isinstance(v, (list, dict)) else f" = {str(v)[:60]}"))
    # find the list of players wherever it lives
    for k, v in j.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            log(f"  --- list at {k!r}, {len(v)} entries ---")
            log("  entry keys:", sorted(v[0].keys()))
            log("  entry 0:", json.dumps(v[0], ensure_ascii=False)[:1400])
            break
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                    log(f"  --- list at {k!r}.{k2!r}, {len(v2)} entries ---")
                    log("  entry keys:", sorted(v2[0].keys()))
                    log("  entry 0:", json.dumps(v2[0], ensure_ascii=False)[:1400])
                    break

log("")
log("=" * 70)
log("B. the league's team page — the per-player table")
log("=" * 70)
u = "https://basket.co.il/team.asp?TeamId=1095&cYear=2026"
r = requests.get(u, headers=UA, timeout=30)
r.encoding = r.apparent_encoding or "windows-1255"
soup = BeautifulSoup(r.text, "html.parser")
log(f"  {u} -> {r.status_code}")
for ti, table in enumerate(soup.find_all("table")):
    rows = table.find_all("tr")
    if len(rows) < 3:
        continue
    head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    if not any(w in " ".join(head) for w in ("נק", "ריב", "אס", "ממוצע", "שחקן")):
        continue
    log(f"  --- table {ti}: {len(rows)} rows ---")
    log("  header:", head)
    for tr in rows[1:5]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        pid = re.search(r"PlayerId=(\d+)", str(tr))
        log(f"    {'id=' + pid.group(1) if pid else 'id=?':<10}", cells)
    break
else:
    log("  no table matched — dumping any row that names a player")
    for m in re.findall(r"<tr[^>]*>.*?PlayerId=\d+.*?</tr>", r.text, re.S)[:2]:
        log("   ", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", m))[:400])
