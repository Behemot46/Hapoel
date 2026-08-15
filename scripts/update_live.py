"""Game-night poller.

The main updater runs three times a day, which is fine for a schedule and a
table and useless on the one evening a fan actually opens the app. This
script runs every few minutes during the hours games are played, and does
nothing at all unless a game is actually on.

Output is a single small file, app/data/live.json:

    {"state": "live", "game": {...}, "home": 61, "away": 58,
     "partials": [...], "updated": "2026-09-08T18:12:03+00:00"}

or, when nothing is happening, {"state": "idle"}.

Deliberate limits, so the app can be honest about them:
- Actions cron is best-effort and often runs late, so the app shows how old
  the reading is rather than pretending to be second-by-second.
- Only EuroCup games have a live feed. Domestic games get a "playing now"
  state with no score, which is better than a frozen countdown.
"""
import datetime
import json
import pathlib
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; +https://github.com/Behemot46/Hapoel)",
      "Accept": "application/json"}
GAMES_URL = "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/games"

# a game is "on" from shortly before tip-off until well after it should have
# ended, the second bound is generous because overtime and late tip-offs happen
BEFORE = datetime.timedelta(minutes=20)
AFTER = datetime.timedelta(hours=3)


def log(*a):
    print("[live]", *a, flush=True)


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_live(doc):
    doc["updated"] = now().isoformat(timespec="seconds")
    p = DATA / "live.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("wrote live.json:", json.dumps(doc, ensure_ascii=False)[:200])


def parse_dt(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def current_game():
    """The game happening right now, according to our own schedule."""
    games = (load("games.json") or {}).get("games") or []
    t = now()
    for g in games:
        if g.get("status") == "finished":
            continue
        start = parse_dt(g.get("date"))
        if start and start - BEFORE <= t <= start + AFTER:
            return g, start
    return None, None


def eurocup_snapshot(game):
    """Score and quarters for a EuroCup game, or None if unavailable."""
    try:
        data = requests.get(GAMES_URL, headers=UA, timeout=25).json()
    except Exception as e:
        log("feed unreachable:", type(e).__name__, e)
        return None
    raw = data.get("data") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        log("unexpected envelope")
        return None

    target = parse_dt(game.get("date"))
    best = None
    for g in raw:
        local, road = g.get("local") or {}, g.get("road") or {}
        codes = ((local.get("club") or {}).get("code"), (road.get("club") or {}).get("code"))
        if "JER" not in codes:
            continue
        when = parse_dt(g.get("utcDate"))
        # match on kick-off time; a rescheduled game would otherwise mislead
        if when and target and abs((when - target).total_seconds()) < 4 * 3600:
            best = (g, local, road)
            break
    if not best:
        log("our game is not in the feed")
        return None

    g, local, road = best
    we_home = (local.get("club") or {}).get("code") == "JER"
    def parts(side):
        p = side.get("partials") or {}
        return [p.get(f"partials{i}") or 0 for i in range(1, 5)]
    hp, ap = parts(local), parts(road)
    played = bool(g.get("played"))
    hs = int(local.get("score") or 0)
    as_ = int(road.get("score") or 0)

    # nothing on the board yet means the feed has not caught up with tip-off
    if not played and hs == 0 and as_ == 0:
        return {"state": "starting"}

    # quarters that have any points in them; overtime shows as a 4-quarter game
    # still ticking, which is honest enough without inventing an OT field
    quarter = sum(1 for i in range(4) if (hp[i] or ap[i]))
    return {
        "state": "final" if played else "live",
        "home": hs if we_home else as_,
        "away": as_ if we_home else hs,
        "ourScore": hs if we_home else as_,
        "theirScore": as_ if we_home else hs,
        "quarter": quarter or 1,
        "partials": {"us": hp if we_home else ap, "them": ap if we_home else hp},
    }


def main():
    game, start = current_game()
    if not game:
        # only rewrite when the state actually changes, so quiet nights make
        # no commits at all
        prev = load("live.json") or {}
        if prev.get("state") == "idle":
            log("nothing on, already idle, no write")
            return 0
        save_live({"state": "idle"})
        return 0

    log("game in window:", game.get("id"), "tip-off", start.isoformat())
    base = {
        "gameId": game.get("id"),
        "competition": game.get("competition"),
        "home": game.get("home"),
        "away": game.get("away"),
        "date": game.get("date"),
        "venue": game.get("venue"),
    }

    snap = None
    if game.get("competition") == "יורוקאפ":
        snap = eurocup_snapshot(game)
    else:
        log("domestic game, no live feed available, reporting 'playing' only")

    if not snap:
        snap = {"state": "playing"}
    save_live({**snap, "game": base})
    return 0


if __name__ == "__main__":
    sys.exit(main())
