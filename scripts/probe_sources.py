"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

The development sandbox cannot reach basket.co.il or the EuroCup API, so
this runs on Actions (workflow_dispatch) and prints enough structure to
write a parser against. Run it, read the log, then write the real code.

Round 1 established: /clubs/JER/games is a 404, the group table lives at
/rounds/N/standings, and the club has 10 registered players plus a coach.
Round 2 goes after the game object itself, player images, and the league's
fixture board.
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
        log("    (not json)", r.text[:300].replace("\n", " "))
        return None


def shape(obj, prefix="", depth=0, out=None):
    """Print the key structure of a JSON blob, one line per leaf path."""
    if out is None:
        out = []
    if depth > 5 or len(out) > 150:
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


def dump(obj, limit=90):
    for line in shape(obj)[:limit]:
        log("   ", line)


def section(title):
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


def listify(d):
    """Unwrap the {data: [...], total: n} envelope the v2 API mostly uses."""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if isinstance(d.get("data"), list):
            return d["data"]
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


# ---------------------------------------------------------------- 1. games

def probe_games():
    section("1. Which games endpoint works, and what live state does it carry?")
    candidates = [
        f"{API}/v2/competitions/U/seasons/{SEASON}/games",
        f"{API}/v2/competitions/U/seasons/{SEASON}/games?clubCode=JER",
        f"{API}/v2/competitions/U/seasons/{SEASON}/games?teamCode=JER",
        f"{API}/v1/schedules?seasonCode={SEASON}",
        f"{API}/v1/results?seasonCode={SEASON}",
    ]
    games = None
    for u in candidates:
        d = get(u, want_json=not u.startswith(f"{API}/v1"))
        if d is None:
            continue
        if isinstance(d, str):
            log("    xml head:", d[:400].replace("\n", " "))
            continue
        lst = listify(d)
        log(f"    -> {len(lst)} entries")
        if lst and games is None:
            games = lst
            log("  --- full shape of games[0] ---")
            dump(lst[0])

    if not games:
        log("  no game list found at all")
        return

    ours = [g for g in games if "JER" in json.dumps(g)]
    log(f"  {len(ours)} games mentioning JER")
    if ours:
        log("  --- full shape of one of ours ---")
        dump(ours[0])

    keys = set()
    for g in games:
        keys |= {k for k in g if re.search(
            r"live|status|played|period|quarter|minute|clock|phase|score|result", k, re.I)}
    log("  live-ish top-level keys across all games:", sorted(keys))

    # a game already played is the best proxy for what a live game looks like
    played = [g for g in games if g.get("played") or g.get("status") in ("played", "result")]
    log(f"  {len(played)} already played")
    if played:
        log("  --- a played game ---")
        dump(played[0])
        gid = played[0].get("gameCode") or played[0].get("code") or played[0].get("id")
        if gid:
            for u in (f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}",
                      f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}/boxscore",
                      f"{API}/v2/competitions/U/seasons/{SEASON}/games/{gid}/stats"):
                d = get(u)
                if d:
                    log(f"  --- {u.rsplit('/', 1)[-1]} ---")
                    dump(d, 50)


# ---------------------------------------------------------------- 2. standings

def probe_standings():
    section("2. Group table — which round, and what is in a row?")
    # find the highest round that still answers, so we always show the latest
    highest = None
    for rnd in (1, 2, 5, 10, 18, 20):
        d = get(f"{API}/v2/competitions/U/seasons/{SEASON}/rounds/{rnd}/standings")
        if d:
            highest = (rnd, d)
    if not highest:
        return
    rnd, d = highest
    groups = d if isinstance(d, list) else listify(d)
    log(f"  round {rnd}: {len(groups)} groups")
    for g in groups:
        info = g.get("group", {})
        rows = g.get("standings", [])
        names = [r.get("club", {}).get("code") for r in rows]
        log(f"    {info.get('name')} ({info.get('phaseTypeCode')}): {len(rows)} teams {names}")
    log("  --- full shape of one standings row ---")
    for g in groups:
        for r in g.get("standings", []):
            if r.get("club", {}).get("code") == "JER":
                dump(r, 60)
                return
    dump(groups[0]["standings"][0], 60)


# ---------------------------------------------------------------- 3. league

def probe_league():
    section("3. Winner League fixture board — is our schedule published?")
    for u in ("https://basket.co.il/results.asp?Board=5&RoundNumber=0&TeamId=0",
              "https://basket.co.il/more-games.asp?cYear=2027&my-list=1"):
        h = get(u, want_json=False)
        if not h:
            continue
        s = BeautifulSoup(h, "html.parser")
        tables = s.find_all("table")
        log(f"    {u}")
        log(f"      {len(tables)} tables")
        for i, t in enumerate(tables[:10]):
            rows = t.find_all("tr")
            head = rows[0].get_text(" | ", strip=True)[:110] if rows else ""
            nxt = rows[1].get_text(" | ", strip=True)[:110] if len(rows) > 1 else ""
            log(f"      table[{i}] rows={len(rows)} head={head!r}")
            log(f"                 next={nxt!r}")
        hits = [x.get_text(" ", strip=True)[:80]
                for x in s.find_all(string=re.compile("הפועל"))][:10]
        log(f"      {len(hits)} mentions of הפועל, e.g. {hits[:5]}")


# ---------------------------------------------------------------- 4. people

def probe_people():
    section("4. Player objects — is there an official headshot?")
    d = get(f"{API}/v2/competitions/U/seasons/{SEASON}/clubs/JER/people?personType=J")
    people = listify(d)
    if not people:
        return
    log(f"  {len(people)} players")
    log("  --- full shape of people[0] ---")
    dump(people[0])
    for p in people:
        per = p.get("person") or {}
        imgs = per.get("images") or p.get("images") or {}
        log("   ", p.get("dorsal"), (per.get("name") or "?")[:28],
            "images:", json.dumps(imgs, ensure_ascii=False)[:160])


# ---------------------------------------------------------------- 5. crests

def probe_crests():
    section("5. Club crests — usable badges for opponents?")
    d = get(f"{API}/v2/competitions/U/seasons/{SEASON}/clubs")
    for c in listify(d)[:6]:
        log("   ", c.get("code"), (c.get("name") or "")[:30],
            json.dumps(c.get("images") or {}, ensure_ascii=False)[:160])


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("games", probe_games), ("standings", probe_standings),
                     ("league", probe_league), ("people", probe_people),
                     ("crests", probe_crests)):
        if which in ("all", name):
            fn()
    log("")
    log("probe done")
