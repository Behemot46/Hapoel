"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

The development sandbox cannot reach basket.co.il or the EuroCup API, so
this runs on Actions (workflow_dispatch) and prints enough structure to
write a parser against. Run it, read the log, then write the real code.

Answers four questions in one run:
  1. does a EuroCup game object carry a live score, period and clock?
  2. is there a EuroCup standings/group table endpoint?
  3. has the Winner League published its fixture list yet?
  4. how many players does the club actually have registered?
"""
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; +https://github.com/Behemot46/Hapoel)",
      "Accept": "application/json, text/html;q=0.9"}
SEASON = "U2026"
API = "https://api-live.euroleague.net"


def log(*a):
    print("[probe]", *a, flush=True)


def get(url, want_json=True):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        log("  FAIL", url, type(e).__name__, e)
        return None
    log(f"  {r.status_code} {len(r.content):>8}b  {url}")
    if r.status_code != 200:
        return None
    if not want_json:
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    try:
        return r.json()
    except Exception:
        log("    (not json)", r.text[:200].replace("\n", " "))
        return None


def shape(obj, prefix="", depth=0, out=None, seen=0):
    """Print the key structure of a JSON blob, one line per leaf path."""
    if out is None:
        out = []
    if depth > 4 or len(out) > 120:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                shape(v, p, depth + 1, out)
            else:
                out.append(f"{p} = {json.dumps(v, ensure_ascii=False)[:60]}")
    elif isinstance(obj, list):
        log(f"    {prefix}: list[{len(obj)}]")
        if obj:
            shape(obj[0], prefix + "[0]", depth + 1, out)
    return out


def section(title):
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


# ---------------------------------------------------------------- 1. live game

def probe_games():
    section("1. EuroCup games — does a game object carry live state?")
    data = get(f"{API}/v2/competitions/U/seasons/{SEASON}/clubs/JER/games")
    if not data:
        log("  no games payload")
        return
    games = data.get("data") if isinstance(data, dict) else data
    if not isinstance(games, list):
        log("  unexpected envelope, keys:", list(data)[:15])
        games = None
        for v in (data or {}).values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                games = v
                break
    if not games:
        log("  could not locate the game list")
        return
    log(f"  {len(games)} games")
    log("  --- full shape of games[0] ---")
    for line in shape(games[0]):
        log("   ", line)
    # anything that smells like live state, across every game
    keys = set()
    for g in games:
        keys |= {k for k in g if re.search(
            r"live|status|played|period|quarter|minute|clock|time|phase", k, re.I)}
    log("  live-ish keys present:", sorted(keys))
    for g in games[:3]:
        log("   sample:", json.dumps({k: g.get(k) for k in sorted(keys)}, ensure_ascii=False)[:300])

    # the per-game detail endpoint is where a live boxscore usually lives
    gid = games[0].get("gameCode") or games[0].get("code") or games[0].get("id")
    if gid:
        for u in (f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}",
                  f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}/stats",
                  f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}/boxscore"):
            d = get(u)
            if d:
                log(f"  --- shape of {u.rsplit('/', 1)[-1]} ---")
                for line in shape(d)[:45]:
                    log("   ", line)


# ---------------------------------------------------------------- 2. standings

def probe_standings():
    section("2. EuroCup standings — is there a group table?")
    for u in (f"{API}/v2/competitions/U/seasons/{SEASON}/standings",
              f"{API}/v2/competitions/U/seasons/{SEASON}/standings/traditional",
              f"{API}/v2/competitions/U/seasons/{SEASON}/rounds/1/standings",
              f"{API}/v2/competitions/U/seasons/{SEASON}/clubs",
              f"{API}/v1/standings?seasonCode={SEASON}"):
        d = get(u)
        if d:
            for line in shape(d)[:40]:
                log("   ", line)


# ---------------------------------------------------------------- 3. league

def probe_league():
    section("3. Winner League — is the fixture list published?")
    html = get("https://basket.co.il/", want_json=False)
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if re.search(r"משחק|מחזור|לוח|תוצא", t) and len(t) < 40:
            links.append((t, a["href"]))
    log(f"  {len(links)} schedule-ish links on the home page")
    for t, h in links[:20]:
        log(f"    {t!r} -> {h}")
    for u in ("https://basket.co.il/games.asp",
              "https://basket.co.il/team.asp?TeamId=1035",
              "https://basket.co.il/league.asp?LeagueId=1"):
        h = get(u, want_json=False)
        if not h:
            continue
        s = BeautifulSoup(h, "html.parser")
        tables = s.find_all("table")
        log(f"    {u}: {len(tables)} tables")
        for i, t in enumerate(tables[:8]):
            rows = t.find_all("tr")
            head = rows[0].get_text(" | ", strip=True)[:100] if rows else ""
            log(f"      table[{i}] rows={len(rows)} head={head!r}")


# ---------------------------------------------------------------- 4. roster

def probe_roster():
    section("4. Roster — how many players are actually registered?")
    for u in (f"{API}/v2/competitions/U/seasons/{SEASON}/clubs/JER/people",
              f"{API}/v2/competitions/U/seasons/{SEASON}/clubs/JER/people?personType=J",
              f"{API}/v2/competitions/U/seasons/{SEASON}/clubs/JER"):
        d = get(u)
        if not d:
            continue
        people = d.get("data") if isinstance(d, dict) else d
        if isinstance(people, list):
            log(f"    {len(people)} entries")
            for p in people:
                per = p.get("person") or p
                log("      ",
                    p.get("dorsal") or p.get("jerseyNumber") or "-",
                    (per.get("name") or per.get("fullName") or "?")[:32],
                    p.get("positionName") or p.get("position") or "",
                    p.get("type") or p.get("personType") or "")
        else:
            for line in shape(d)[:30]:
                log("   ", line)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "games"):
        probe_games()
    if which in ("all", "standings"):
        probe_standings()
    if which in ("all", "league"):
        probe_league()
    if which in ("all", "roster"):
        probe_roster()
    log("")
    log("probe done")
