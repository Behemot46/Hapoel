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
# **למה 75 דקות ולא 20:** הפולר לא מתחיל לבד, האיסוף מזמן אותו כשהוא
# רואה משחק מתקרב, והאיסוף דוגם כל שעה (מאז שהקצב הואט בגלל מכסת
# הדיפלויים של ורסל). חלון של 20 דקות מול דגימה שעתית פירושו שרוב
# הדקירות נופלות מחוצה לו: ב־8.9.2026 האיסוף דקר ב־13:43 וב־14:43,
# שתיהן לפני שהחלון נפתח, ושתיהן יצאו מיד. הפולר עלה רק כי הופעל ביד.
# חלון של 75 דקות מבטיח שכל דקירה שעתית תיפול בפנים.
BEFORE = datetime.timedelta(minutes=75)
AFTER = datetime.timedelta(hours=3)


def log(*a):
    print("[live]", *a, flush=True)


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# כל כתיבה ל־live.json הופכת לקומיט ולדיפלוי בוורסל, ושם יש תקרה של 100
# ביום. לפני הקפיצה שום דבר לא משתנה מלבד חותמת הזמן, ובחלון של 75 דקות
# זה 25 דחיפות שכל מה שהן אומרות הוא ״עדיין רגע לפני״. לכן כותבים רק
# כשהתוכן באמת השתנה, ומרעננים את החותמת פעם ברבע שעה כדי שהתווית
# ״עודכן לפני״ באפליקציה לא תזדקן בלי סיבה.
STAMP_EVERY = datetime.timedelta(minutes=15)


def save_live(doc):
    p = DATA / "live.json"
    try:
        prev = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        prev = None

    if prev is not None:
        same = {k: v for k, v in prev.items() if k != "updated"} == doc
        if same:
            last = parse_dt(prev.get("updated"))
            if last and now() - last < STAMP_EVERY:
                log("live.json לא השתנה, ועוד לא הגיע הזמן לרענן חותמת")
                return

    doc = dict(doc)
    doc["updated"] = now().isoformat(timespec="seconds")
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
        # משחק שהליגה עוד לא פרסמה לו שעה נשמר על 12:00 כמציין מקום
        # (ראו parse_team_games ב־update_data.py). בלי הדילוג הזה הפולר
        # היה מכריז ״משחק עכשיו״ בצהריים של יום המשחק, על סמך שעה שאיש
        # לא פרסם, ומראה לאוהד משחק חי שלא מתקיים.
        if g.get("timeTbd"):
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

    # **פיד ששותק לא אומר שהמשחק לא התחיל, והשעון שלנו כן אומר.** עד
    # 14.10.2026 הענף הזה החזיר ״starting״, כלומר ״רגע לפני הקפיצה״,
    # בכל פעם שלא הייתה תוצאה על הלוח. באותו יום זה נמדד על המשחק
    # בבורגוס, **המשחק האירופי הראשון שהפולר בכלל כיסה**: הקפיצה הייתה
    # ב־18:30, הפיד פרסם את התוצאה רק ב־20:46 כשהמשחק נגמר, ועד אז האוהד
    # ראה ״רגע לפני הקפיצה״ שעתיים אחרי שהמשחק התחיל.
    #
    # ההחזרה של None מעבירה את ההחלטה לשעון, כלומר בדיוק למה שכבר נכתב
    # ב־``main`` בשביל משחקי הליגה: ״playing״ אחרי הקפיצה ו״starting״
    # לפניה. זה גם מה שנכון לומר: אנחנו יודעים מהלוח שהמשחק התחיל, ולא
    # יודעים מה התוצאה.
    if not played and hs == 0 and as_ == 0:
        log("אין עדיין תוצאה בפיד, השעון יכריע אם המשחק התחיל")
        return None

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


# **מתי החלון נסגר, לשימוש הלולאה שב־live.yml.** הלולאה חייבת לשרוד עד
# שהחלון נסגר, אחרת היא מתה כשהמצב עוד ״playing״ ואף אחד לא כותב idle.
# זה מה שקרה ב־11.10.2026, המשחק הראשון בליגה: הדדליין היה 210 דקות
# מתחילת הריצה, כלומר 20:37, והחלון נסגר ב־20:55. הלולאה מתה 18 דקות
# לפני, והאוהד ראה ״המשחק מתנהל״ עוד שלוש שעות ועשרים, עד שדקירה מאוחרת
# ב־23:06 כתבה idle. דווקא בשעה שאחרי המשחק, כשנכנסים לראות את התוצאה.
#
# הקבוע נשאר כאן ולא מועתק ל־YAML, כדי שלא ייפרדו.
def window_end():
    game, start = current_game()
    return (start + AFTER) if game else None


def main():
    if "--window-end" in sys.argv:
        # הלולאה קוראת את זה, ולכן שורה אחת בלבד לפלט: חותמת זמן או כלום
        end = window_end()
        print(int(end.timestamp()) if end else "")
        return 0
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
        # לפני הקפיצה זה עדיין לא ״המשחק מתנהל״. עד היום הפולר כתב
        # playing מהרגע שנכנס לחלון, והאפליקציה הכריזה ״עכשיו · המשחק
        # מתנהל״ על משחק שלא התחיל: ב־8.9.2026 זה קרה ב־15:41 למשחק של
        # 16:00. המצב starting כבר קיים והאפליקציה מציגה אותו כ״רגע לפני
        # הקפיצה״, הוא פשוט לא היה בשימוש למשחקי בית. עם חלון של 75
        # דקות זה קריטי: בלי זה היינו משקרים שעה ורבע.
        snap = {"state": "playing" if now() >= start else "starting"}
    save_live({**snap, "game": base})
    return 0


if __name__ == "__main__":
    sys.exit(main())
