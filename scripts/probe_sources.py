#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם, פתוחה מ־4.11.2026:** מי מפרסם ראשון את התוצאה של משחק
יורוקאפ, אתר המועדון או הפיד של היורוליג?

מה שנמדד מול אריס ב־4.11: הפיד ``v2/.../games`` לא הראה תוצאה כל המשחק
וגם לא אחרי השריקה, והתוצאה נכנסה ללוח רק ב־00:06 UTC, יותר משלוש שעות
אחרי הסיום. אם אתר המועדון (או ה־API החי הישן של היורוליג) מחזיק תוצאה
מוקדם יותר, אפשר להשתמש בו כגיבוי לתוצאה כשהפיד הרשמי שותק. **מודדים
לפני שבונים**: מריצים את הכלי כמה פעמים אחרי השריקה ומשווים.

מה מודפס בכל ריצה, לפי התאריך שהתקבל (ברירת מחדל: היום ב־UTC):

1. אתר המועדון: הכרטיס של המשחק, הטקסט הגולמי של ``.score``, והאם
   הכרטיס בכלל עוד מופיע (ההערה ב־update_data.py אומרת שהאתר מוריד
   משחק מהעמוד כשהוא נגמר, וזה בדיוק מה שצריך לראות).
2. הפיד ``v2/.../games``: played, score ורבעים של המשחק שלנו.
3. הטופס ``v2/.../games/{code}/stats``: סכום הנקודות של כל צד.
4. ה־API החי הישן, ``live.euroleague.net/api/Header``, שאינו בשימוש אצלנו
   ונבדק רק כדי לדעת אם יש בו משהו.

הכלי לא כותב כלום. שעת הריצה מודפסת בראש, כי היא הנתון.

    python scripts/probe_sources.py [YYYY-MM-DD]
"""
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import requests
from bs4 import BeautifulSoup

import club_games
import update_data as ud

V2_GAMES = "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/games"
V2_STATS = V2_GAMES + "/{code}/stats"
OLD_HEADER = "https://live.euroleague.net/api/Header?gamecode={code}&seasoncode=U2026"


def get(url):
    r = requests.get(url, headers=ud.UA, timeout=30)
    print(f"  GET {url} → {r.status_code}, {len(r.content)} בתים")
    r.raise_for_status()
    return r


def club(day):
    print("\n1. אתר המועדון")
    # דרך ud.fetch ולא requests ישירות, כי הוא מפענח את הקידוד של האתר;
    # requests לבד מנחש latin-1, ואז אף כרטיס לא מזוהה כשלנו
    try:
        html = ud.fetch(club_games.GAMES_URL)
        print(f"  GET {club_games.GAMES_URL}, {len(html)} תווים")
    except Exception as e:
        print(f"  נפל: {type(e).__name__} {e}")
        return
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".game")
    print(f"  {len(cards)} כרטיסים בעמוד")
    games = club_games.parse_games(html, club_games.season_start_year())
    near = [g for g in games if abs((datetime.date.fromisoformat(g["date"][:10]) - day).days) <= 1]
    if not near:
        first = games[0]["date"][:10] if games else "-"
        print(f"  אין כרטיס ל־{day}. הכרטיס הראשון בעמוד: {first}")
    for g in near:
        print(f"  {g['date']} {g['home']} - {g['away']}: {g['status']}, "
              f"{g['homeScore']}-{g['awayScore']}")
    # **והטקסט הגולמי, כי _score מתרגם 0:0 ל״אין תוצאה״** ואולי האתר כותב
    # תוצאה חיה בפורמט אחר
    for c in cards:
        when = club_games._txt(c.select_one(".date-time"))
        d, _ = club_games.parse_when(when, club_games.season_start_year())
        if d and abs((d - day).days) <= 1:
            print(f"  גולמי: date-time={when!r} score={club_games._txt(c.select_one('.score'))!r}")


def euroleague(day):
    print("\n2. הפיד v2/games")
    try:
        body = get(V2_GAMES).json()
    except Exception as e:
        print(f"  נפל: {type(e).__name__} {e}")
        return None
    rows = body.get("data") if isinstance(body, dict) else body
    ours = []
    for g in rows or []:
        local, road = g.get("local") or {}, g.get("road") or {}
        codes = [(s.get("club") or {}).get("code") for s in (local, road)]
        if "JER" in codes and (g.get("utcDate") or "")[:10] in (
                str(day), str(day - datetime.timedelta(days=1))):
            ours.append(g)
    if not ours:
        print(f"  אין משחק שלנו ב־{day}")
        return None
    g = ours[-1]
    local, road = g.get("local") or {}, g.get("road") or {}
    print(f"  {g.get('utcDate')} code={g.get('gameCode') or g.get('code')} "
          f"played={g.get('played')}")
    for side in (local, road):
        print(f"    {(side.get('club') or {}).get('code')}: score={side.get('score')} "
              f"partials={side.get('partials')}")
    # שדות מצב שאולי קיימים ולא נקראים אצלנו
    flags = {k: v for k, v in g.items() if re.search(r"status|live|state|minute|quarter", k, re.I)}
    if flags:
        print(f"  שדות מצב: {json.dumps(flags, ensure_ascii=False)[:300]}")
    return g


def stats(g):
    code = g.get("gameCode") or g.get("code")
    print("\n3. הטופס v2/games/{code}/stats")
    try:
        body = get(V2_STATS.format(code=code)).json()
    except Exception as e:
        print(f"  נפל: {type(e).__name__} {e}")
        return
    for key in ("local", "road"):
        tot = ((body.get(key) or {}).get("total") or {})
        print(f"    {key}: points={tot.get('points')} timePlayed={tot.get('timePlayed')}")


def old_live(g):
    code = g.get("gameCode") or g.get("code")
    print("\n4. ה־API החי הישן")
    try:
        r = get(OLD_HEADER.format(code=code))
        print(f"  {r.text[:400]}")
    except Exception as e:
        print(f"  נפל: {type(e).__name__} {e}")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    now = datetime.datetime.now(datetime.timezone.utc)
    day = datetime.date.fromisoformat(arg) if re.match(r"\d{4}-\d{2}-\d{2}$", arg) else now.date()
    print(f"ריצה ב־{now:%Y-%m-%d %H:%M:%S} UTC, משחק של {day}")
    club(day)
    g = euroleague(day)
    if g:
        stats(g)
        old_live(g)


if __name__ == "__main__":
    main()
