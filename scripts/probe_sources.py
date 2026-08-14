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
  round 3  (this one) no 2026-27 game has been played yet, so the shape of a
           game in progress is learned from last season instead.
"""
import json
import re
import sys

import requests

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


def probe_played():
    """Last season has finished games — their shape is the shape a live game
    will take as it fills in."""
    section("A. A finished game from last season: what does a result look like?")
    d = get(f"{API}/v2/competitions/U/seasons/U2025/games")
    games = listify(d)
    log(f"  {len(games)} games in U2025")
    played = [g for g in games if g.get("played")]
    log(f"  {len(played)} played")
    if not played:
        log("  nothing played — cannot learn the shape here")
        return
    g = played[len(played) // 2]
    log("  --- full shape of a finished game ---")
    dump(g)

    code = g.get("gameCode") or g.get("code") or g.get("id")
    log("  game identifier:", repr(code))
    if not code:
        return
    for u in (f"{API}/v2/competitions/U/seasons/U2025/games/{code}",
              f"{API}/v2/competitions/U/seasons/U2025/games/{code}/boxscore",
              f"{API}/v2/competitions/U/seasons/U2025/games/{code}/stats",
              f"{API}/v2/competitions/U/seasons/U2025/games/{code}/report",
              f"{API}/v1/games?seasonCode=U2025&gameCode={code}"):
        r = get(u, want_json=not u.startswith(f"{API}/v1"))
        if r is None:
            continue
        if isinstance(r, str):
            log("    xml head:", r[:500].replace("\n", " "))
            continue
        log(f"  --- {u.rsplit('/', 1)[-1][:40]} ---")
        dump(r, 70)


def probe_upcoming_shape():
    section("B. Our own 2026-27 games — the exact fields we will be polling")
    d = get(f"{API}/v2/competitions/U/seasons/U2026/games")
    games = listify(d)
    ours = [g for g in games if "JER" in json.dumps(g)]
    log(f"  {len(games)} games, {len(ours)} ours")
    if ours:
        log("  --- full shape of our first game ---")
        dump(ours[0])
        log("  date-ish values across our games:")
        for g in ours[:4]:
            vals = {k: v for k, v in g.items()
                    if isinstance(v, str) and re.search(r"date|time|utc", k, re.I)}
            log("   ", json.dumps(vals, ensure_ascii=False)[:220])


def probe_live_endpoints():
    section("C. Anything explicitly named 'live'?")
    for u in (f"{API}/v2/competitions/U/seasons/U2026/games/live",
              f"{API}/v2/competitions/U/games/live",
              f"{API}/v1/games?seasonCode=U2026",
              f"{API}/v2/competitions/U/seasons/U2026/rounds"):
        r = get(u, want_json=not u.startswith(f"{API}/v1"))
        if r is None:
            continue
        if isinstance(r, str):
            log("    xml head:", r[:400].replace("\n", " "))
        else:
            dump(r, 30)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("played", probe_played), ("upcoming", probe_upcoming_shape),
                     ("live", probe_live_endpoints)):
        if which in ("all", name):
            fn()
    log("")
    log("probe done")
