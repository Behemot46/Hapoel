"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

The development sandbox cannot reach basket.co.il or the EuroCup API, so
this runs on Actions (workflow_dispatch) and prints enough structure to
write a parser against. Run it, read the log, then write the real code.

Established so far:
  round 1  /clubs/JER/games is a 404; the group table is /rounds/N/standings;
           the club has 10 registered players plus a coach.
  round 2  Group A holds JER; standings rows carry position/W/L/points;
           player objects carry no images at all; every club has a crest;
           the league fixture list is genuinely still unpublished.
  round 3  the feed gives three different times per game and utcDate is the
           only true one; scores live in local/road .score and .partials.
  round 4  (this one) last season — what did 2025-26 actually look like, and
           is there a season-level player stats endpoint to aggregate?
"""
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; +https://github.com/Behemot46/Hapoel)",
      "Accept": "application/json, text/html;q=0.9"}
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
        log("    (not json)", r.text[:300].replace("\n", " "))
        return None


def shape(obj, prefix="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 5 or len(out) > 160:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                shape(v, p, depth + 1, out)
            else:
                out.append(f"{p} = {json.dumps(v, ensure_ascii=False)[:70]}")
    elif isinstance(obj, list):
        out.append(f"{prefix}: list[{len(obj)}]")
        if obj:
            shape(obj[0], prefix + "[0]", depth + 1, out)
    return out


def dump(obj, limit=110):
    for line in shape(obj)[:limit]:
        log("   ", line)


def section(title):
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


def listify(d):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if isinstance(d.get("data"), list):
            return d["data"]
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


# ------------------------------------------------------- last European season

def probe_last_euro():
    section("A. Last season in Europe — our record and how it ended")
    d = get(f"{API}/v2/competitions/U/seasons/U2025/games")
    games = listify(d)
    ours = []
    for g in games:
        local, road = g.get("local") or {}, g.get("road") or {}
        codes = ((local.get("club") or {}).get("code"), (road.get("club") or {}).get("code"))
        if "JER" in codes:
            ours.append((g, local, road))
    log(f"  {len(games)} games in U2025, {len(ours)} ours")
    w = l = 0
    for g, local, road in sorted(ours, key=lambda x: x[0].get("utcDate") or ""):
        home = (local.get("club") or {}).get("code") == "JER"
        us = int(local.get("score") or 0) if home else int(road.get("score") or 0)
        them = int(road.get("score") or 0) if home else int(local.get("score") or 0)
        opp = ((road if home else local).get("club") or {}).get("name")
        if g.get("played"):
            w += us > them
            l += us < them
        log(f"    {(g.get('utcDate') or '')[:10]} {'H' if home else 'A'} "
            f"{us:>3}-{them:<3} {'W' if us > them else 'L'}  {opp}  "
            f"[{g.get('phaseType', {}).get('name')} {g.get('roundName')}]")
    log(f"  RECORD: {w}-{l}")

    section("A2. Last season's final group table")
    for rnd in range(22, 0, -1):
        d = get(f"{API}/v2/competitions/U/seasons/U2025/rounds/{rnd}/standings")
        groups = d if isinstance(d, list) else listify(d)
        if groups:
            log(f"  last populated round: {rnd}")
            for grp in groups:
                rows = grp.get("standings") or []
                if any((r.get("club") or {}).get("code") == "JER" for r in rows):
                    log("  our group:", (grp.get("group") or {}).get("name"))
                    for r in rows:
                        c, dd = r.get("club") or {}, r.get("data") or {}
                        log(f"    {dd.get('position')}. {c.get('name')[:34]:<34} "
                            f"{dd.get('gamesWon')}-{dd.get('gamesLost')} "
                            f"{dd.get('pointsFavour')}:{dd.get('pointsAgainst')}")
            break


def probe_player_stats():
    section("B. Is there a season-level player stats endpoint?")
    for u in (f"{API}/v2/competitions/U/seasons/U2025/clubs/JER/people/stats",
              f"{API}/v2/competitions/U/seasons/U2025/statistics/players",
              f"{API}/v2/competitions/U/seasons/U2025/people/statistics",
              f"{API}/v2/competitions/U/seasons/U2025/statistics/players/traditional?limit=400",
              f"{API}/v2/competitions/U/seasons/U2025/statistics/teams/traditional"):
        d = get(u)
        if d:
            dump(d, 45)

    section("B2. Failing that, a single game's boxscore")
    d = get(f"{API}/v2/competitions/U/seasons/U2025/games")
    for g in listify(d):
        local, road = g.get("local") or {}, g.get("road") or {}
        codes = ((local.get("club") or {}).get("code"), (road.get("club") or {}).get("code"))
        if "JER" in codes and g.get("played"):
            code = g.get("gameCode")
            log("  using gameCode", code)
            for u in (f"{API}/v2/competitions/U/seasons/U2025/games/{code}/stats",
                      f"{API}/v2/competitions/U/seasons/U2025/games/{code}/boxscore"):
                r = get(u)
                if r:
                    dump(r, 60)
            break


def probe_league_last():
    section("C. Last season in the Israeli league")
    for u in ("https://basket.co.il/table.asp?cYear=2026",
              "https://basket.co.il/team.asp?TeamId=1035&cYear=2026"):
        h = get(u, want_json=False)
        if not h:
            continue
        s = BeautifulSoup(h, "html.parser")
        for i, t in enumerate(s.find_all("table")[:10]):
            rows = t.find_all("tr")
            if len(rows) < 3:
                continue
            head = rows[0].get_text(" | ", strip=True)[:100]
            log(f"    table[{i}] rows={len(rows)} head={head!r}")
            for r in rows[1:14]:
                log("      ", r.get_text(" | ", strip=True)[:110])


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("euro", probe_last_euro), ("stats", probe_player_stats),
                     ("league", probe_league_last)):
        if which in ("all", name):
            fn()
    log("")
    log("probe done")
