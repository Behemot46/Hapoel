"""Diagnostic probe — reads nothing, writes nothing, just describes sources.

The development sandbox cannot reach basket.co.il or the EuroCup API, so
this runs on Actions (workflow_dispatch) and prints enough structure to
write a parser against. Run it, read the log, then write the real code.

Round 5: player headshots. The roster endpoint returns images:{} for every
player, but a game's stats endpoint carries player.images.headshot. Before
scanning hundreds of box scores, check whether a per-person endpoint has
the same image — that would be one cheap request per player instead.
"""
import json
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; +https://github.com/Behemot46/Hapoel)",
      "Accept": "application/json"}
API = "https://api-live.euroleague.net"


def log(*a):
    print("[probe]", *a, flush=True)


def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        log("  FAIL", url, type(e).__name__, e)
        return None
    log(f"  {r.status_code} {len(r.content):>7}b  {url}")
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def images_in(obj, path="", found=None):
    """Every images.* URL anywhere in the blob, with its path."""
    if found is None:
        found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, str) and v.startswith("http") and "image" in path.lower() + k.lower():
                found.append((p, v[:90]))
            else:
                images_in(v, p, found)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            images_in(v, f"{path}[{i}]", found)
    return found


def section(t):
    log("")
    log("=" * 68)
    log(t)
    log("=" * 68)


HARPER = "011970"   # on the roster both seasons — a safe test subject


def probe_person():
    section("A. Does a per-person endpoint carry the headshot?")
    for u in (f"{API}/v2/people/{HARPER}",
              f"{API}/v2/competitions/U/seasons/U2026/people/{HARPER}",
              f"{API}/v2/competitions/U/seasons/U2025/people/{HARPER}",
              f"{API}/v2/competitions/U/seasons/U2026/clubs/JER/people/{HARPER}",
              f"{API}/v2/competitions/U/people/{HARPER}"):
        d = get(u)
        if d is None:
            continue
        imgs = images_in(d)
        log("    images found:", imgs if imgs else "NONE")
        if isinstance(d, dict):
            log("    top-level keys:", sorted(d.keys())[:18])


def probe_stats_images():
    section("B. Does the season stats endpoint carry images?")
    for season in ("U2026", "U2025"):
        d = get(f"{API}/v2/competitions/U/seasons/{season}/clubs/JER/people/stats")
        if not d:
            continue
        rows = d.get("playerStats") if isinstance(d, dict) else None
        log(f"    {season}: playerStats = {len(rows) if isinstance(rows, list) else 'n/a'}")
        if isinstance(rows, list) and rows:
            log("    row keys:", sorted(rows[0].keys())[:15])
            log("    images:", images_in(rows[0]) or "NONE")
            player = rows[0].get("player") or {}
            person = player.get("person") or {}
            log("    person keys:", sorted(person.keys())[:18])
            log("    person code/name:", person.get("code"), person.get("name"))


def probe_boxscore():
    section("C. Box score — the route we know works")
    d = get(f"{API}/v2/competitions/U/seasons/U2025/games")
    games = d.get("data") if isinstance(d, dict) else d
    ours = []
    for g in games or []:
        codes = ((g.get("local") or {}).get("club") or {}).get("code"), \
                ((g.get("road") or {}).get("club") or {}).get("code")
        if "JER" in codes and g.get("played"):
            ours.append(g.get("gameCode"))
    log(f"    {len(ours)} played JER games last season, codes {ours[:6]}")
    if not ours:
        return
    s = get(f"{API}/v2/competitions/U/seasons/U2025/games/{ours[0]}/stats")
    if not s:
        return
    for side in ("local", "road"):
        for pl in (s.get(side) or {}).get("players") or []:
            person = ((pl.get("player") or {}).get("person")) or {}
            imgs = (pl.get("player") or {}).get("images") or {}
            log(f"    {side} {person.get('code')} {str(person.get('name'))[:26]:<26} "
                f"{sorted(imgs.keys())} {str(imgs.get('headshot'))[:70]}")


def probe_coverage():
    """How many box scores must we scan to cover the whole current squad?"""
    section("D. Coverage — which of this season's squad appear last season?")
    d = get(f"{API}/v2/competitions/U/seasons/U2026/clubs/JER/people?personType=J")
    squad = {}
    for p in (d.get("data") if isinstance(d, dict) else d) or []:
        person = p.get("person") or {}
        squad[person.get("code")] = person.get("name")
    log(f"    squad: {len(squad)} players")

    d = get(f"{API}/v2/competitions/U/seasons/U2025/games")
    games = [g for g in ((d.get("data") if isinstance(d, dict) else d) or []) if g.get("played")]
    log(f"    {len(games)} played games in U2025 in total")

    seen, scanned = {}, 0
    for g in games:
        if len(seen) >= len(squad):
            break
        s = get(f"{API}/v2/competitions/U/seasons/U2025/games/{g.get('gameCode')}/stats")
        scanned += 1
        if not s:
            continue
        for side in ("local", "road"):
            for pl in (s.get(side) or {}).get("players") or []:
                person = ((pl.get("player") or {}).get("person")) or {}
                code = person.get("code")
                head = ((pl.get("player") or {}).get("images") or {}).get("headshot")
                if code in squad and code not in seen and head:
                    seen[code] = head
                    log(f"      +{squad[code]} after {scanned} box scores")
        if scanned >= 25:
            break
    log(f"    covered {len(seen)}/{len(squad)} after {scanned} box scores")
    for code, name in squad.items():
        if code not in seen:
            log(f"      MISSING: {name} ({code})")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("person", probe_person), ("stats", probe_stats_images),
                     ("box", probe_boxscore), ("coverage", probe_coverage)):
        if which in ("all", name):
            fn()
    log("")
    log("probe done")
