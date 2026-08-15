"""Diagnostic probe — round 3: the actual numbers, ready to paste.

Round 2 found the EuroCup shape: playerStats[] with player/accumulated/
averagePerGame, 14 players for U2025. timePlayed looks like seconds
(18246 over 16 games = 1140/game = 19:00), so convert and sanity-check it.

Round 2 also matched the wrong table on the league page — it grabbed the
standings, and those read all zeros for cYear=2026, which means that code is
now the *coming* season. Find the per-player table properly, and work out
which cYear actually holds 2025/26.
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
log("A. EuroCup 2025/26 per-player averages")
log("=" * 70)
url = ("https://api-live.euroleague.net/v2/competitions/U/seasons/U2025"
       "/clubs/JER/people/stats")
j = requests.get(url, headers={"Accept": "application/json"}, timeout=30).json()
rows = j.get("playerStats", [])
log(f"  {len(rows)} players")
out = []
for r in rows:
    p, a = r.get("player", {}), r.get("averagePerGame", {})
    acc = r.get("accumulated", {})
    gp = acc.get("gamesPlayed") or 0
    secs = a.get("timePlayed") or 0
    out.append({
        "name": p.get("name"), "code": p.get("code"),
        "gp": gp,
        "min": round(secs / 60.0, 1),
        "pts": a.get("points"), "reb": a.get("totalRebounds"),
        "ast": a.get("assistances"), "stl": a.get("steals"),
        "blk": a.get("blocksFavour"), "tov": a.get("turnovers"),
        "pir": a.get("valuation"),
        "fg2": acc.get("twoPointShootingPercentage"),
        "fg3": acc.get("threePointShootingPercentage"),
        "ft": acc.get("freeThrowShootingPercentage"),
    })
out.sort(key=lambda x: (x["pts"] or 0), reverse=True)
log("  sanity: minutes must land between 5 and 40")
bad = [o for o in out if o["min"] and not (5 <= o["min"] <= 40)]
log("    out of range:", bad or "none — the seconds reading is right")
log("")
log("  PASTE-READY:")
log(json.dumps(out, ensure_ascii=False, indent=1))

log("")
log("=" * 70)
log("B. which cYear is 2025/26, and where is the player table?")
log("=" * 70)
for year in (2026, 2025):
    u = f"https://basket.co.il/team.asp?TeamId=1095&cYear={year}"
    try:
        r = requests.get(u, headers=UA, timeout=30)
        r.encoding = r.apparent_encoding or "windows-1255"
        soup = BeautifulSoup(r.text, "html.parser")
        log(f"  cYear={year} -> {r.status_code}")
        # a player row is one that links to a PlayerId
        hits = 0
        for tr in soup.find_all("tr"):
            if not re.search(r"PlayerId=\d+", str(tr)):
                continue
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if len(cells) < 3:
                continue
            hits += 1
            if hits <= 4:
                log(f"    {cells}")
        log(f"    rows linking a player: {hits}")
    except Exception as e:
        log(f"  cYear={year}: FAIL {type(e).__name__} {str(e)[:120]}")
