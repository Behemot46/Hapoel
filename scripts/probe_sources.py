"""Diagnostic probe, round three: all 19 fixtures on hapoel.co.il/games, one
line each, so the conventions can be read off the whole board at once.

Round two settled the shape of a single block:

    .game
      .date-data .date-time   "12 בספטמבר, שבת 16:30"   (no year)
      .date-data .cycle       "משחקי הכנה"
      .league .game-type .text  "וילנה"                  (venue)
      .teams .teams-container img[alt] x2                (the two sides, in order)
      .game-data .score       "0:0"

Three things still have to be read off real data before a parser can be
trusted, and each is the kind of thing that silently inverts:

  1. is the first team the home side, or is the club always printed first?
     If it is always first, home and away can only come from the venue.
  2. the dates carry no year, so the season rollover has to be inferred.
  3. which side of the score belongs to whom, and what an unplayed game
     looks like.

So: every block, every field, verbatim, plus the alt text order.
"""
import json
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
URL = "https://hapoel.co.il/games"


def log(*a):
    print("[probe]", *a, flush=True)


def txt(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


r = requests.get(URL, headers=UA, timeout=30)
r.raise_for_status()
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")
blocks = soup.select(".game")
log(f"{URL} -> {len(blocks)} blocks")
log("")

rows = []
for g in blocks:
    teams = [i.get("alt", "").strip()
             for i in g.select(".teams-container img") if i.get("alt")]
    row = {
        "when": txt(g.select_one(".date-time")),
        "cycle": txt(g.select_one(".cycle")),
        "venue": txt(g.select_one(".game-type .container .text")),
        "team1": teams[0] if len(teams) > 0 else "",
        "team2": teams[1] if len(teams) > 1 else "",
        "line": txt(g.select_one(".game-data .text")),
        "score": txt(g.select_one(".score")),
        "href": (g.select_one(".date-time a") or {}).get("href", "")
        if g.select_one(".date-time a") else "",
    }
    rows.append(row)

log("=" * 74)
log("every fixture, escaped so the log cannot mangle it")
log("=" * 74)
for i, row in enumerate(rows, 1):
    log(f"  [{i:>2}] {json.dumps(row, ensure_ascii=True)}")
log("")

log("=" * 74)
log("readable form")
log("=" * 74)
for i, row in enumerate(rows, 1):
    log(f"  [{i:>2}] {row['when']:<26} | {row['cycle']:<14} | "
        f"{row['venue']:<14} | {row['team1']} vs {row['team2']} | {row['score']}")
log("")

log("=" * 74)
log("conventions")
log("=" * 74)
first = [r["team1"] for r in rows]
us = [t for t in first if "הפועל י" in t or "ירושלים" in t]
log(f"  blocks where the club is printed FIRST: {len(us)} of {len(rows)}")
log(f"  distinct first-position teams: {json.dumps(sorted(set(first)), ensure_ascii=True)}")
second = sorted({r['team2'] for r in rows})
log(f"  distinct second-position teams: {json.dumps(second, ensure_ascii=True)}")
log(f"  distinct venues: {json.dumps(sorted({r['venue'] for r in rows}), ensure_ascii=True)}")
log(f"  distinct cycles: {json.dumps(sorted({r['cycle'] for r in rows}), ensure_ascii=True)}")
log(f"  distinct scores: {json.dumps(sorted({r['score'] for r in rows}), ensure_ascii=True)}")
log("")
log("  months seen, in page order (tells us where the year rolls over):")
months = [re.sub(r"^\d+\s+ב?", "", r["when"].split(",")[0]) for r in rows]
log(f"    {json.dumps(months, ensure_ascii=True)}")

log("done. nothing was written.")
