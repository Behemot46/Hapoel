#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה, 27.9.2026:** גבי ביקש סטטיסטיקה כמה שיותר מלאה על המשחקים. מה
שיש לנו היום הוא שלושה טפסים של משחקי הכנה שהעתקתי ביד מאתר המועדון,
ו־season-stats.json שהוא ממוצעי יורוקאפ בלבד ועדיין ריק כי העונה
האירופית נפתחת ב־29.9. **כלומר לשלושת משחקי הגביע הרשמיים, 8.9, 18.9
ו־25.9, אין שום סטטיסטיקה.** זה הפער.

לפני שכותבים פרסר צריך לדעת מה המקורות באמת מפרסמים, ולכן שלוש שאלות:

  1. **הליגה, basket.co.il.** האם מעמוד הקבוצה אפשר להגיע לעמוד משחק עם
     מזהה, והאם בעמוד המשחק יש טופס מלא? אם כן, יש לנו טפסים לכל משחק
     ישראלי רשמי, אוטומטית, במקום העתקה ביד.
  2. **היורוקאפ, api-live.euroleague.net.** איזה שדה מזהה משחק בפיד
     שאנחנו כבר קוראים, ואיזו כתובת מחזירה טופס? נבדק על משחק שנגמר
     מהעונה הקודמת, כי לנו עוד לא היה משחק אירופי העונה.
  3. ואיזה שדות בכלל יש בטופס, כדי לדעת מה אפשר להציג בלי להמציא.
"""

import json
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

HEAD = "=" * 70


def jshow(o, limit=1400):
    return json.dumps(o, ensure_ascii=False, indent=1)[:limit]


def probe_league():
    print(HEAD, "\n1. basket.co.il: עמוד הקבוצה, ומשם לעמוד משחק\n", HEAD)
    link = ud.find_team_link()
    print("עמוד הקבוצה:", link)
    if not link:
        return
    html = ud.fetch(link)
    soup = BeautifulSoup(html, "html.parser")

    print("\nכל הקישורים שנראים כמו עמוד משחק:")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"(game|match)", href, re.I) and href not in seen:
            seen.add(href)
            print(f"  {(a.get_text(' ', strip=True) or '')[:40]:<40} {href[:110]}")
    if not seen:
        print("  אף אחד. מדפיס כל href ייחודי כדי לראות מה יש:")
        for href in list(dict.fromkeys(a["href"] for a in soup.find_all("a", href=True)))[:40]:
            print("   ", href[:120])

    # המשחק של 25.9 מול בני הרצליה, שהוא הרשמי האחרון שנגמר
    for gid in ("25331",):
        for pat in ("https://basket.co.il/game-zone.asp?GameId={}",
                    "https://basket.co.il/game.asp?GameId={}"):
            url = pat.format(gid)
            print(f"\n--- {url}")
            try:
                r = requests.get(url, headers=ud.UA, timeout=30)
            except Exception as e:
                print("  נפל:", type(e).__name__, e)
                continue
            print(f"  {r.status_code} · {len(r.content)} bytes")
            if r.status_code != 200:
                continue
            r.encoding = r.encoding or "utf-8"
            s = BeautifulSoup(r.text, "html.parser")
            title = (s.title.get_text(strip=True) if s.title else "")
            print("  title:", title[:90])
            tables = s.find_all("table")
            print(f"  {len(tables)} טבלאות")
            for i, tb in enumerate(tables[:14]):
                rows = tb.find_all("tr")
                if not rows:
                    continue
                head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
                print(f"   טבלה {i}: {len(rows)} שורות · כותרות {head[:14]}")
                for row in rows[1:3]:
                    cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
                    if any(cells):
                        print(f"      {cells[:14]}")


EURO = "https://api-live.euroleague.net"
STATS = EURO + "/v2/competitions/U/seasons/{s}/games/{c}/stats"


def probe_eurocup():
    """**כבר ידוע מהריצה הקודמת:** ‏/games/{code}/stats מחזיר 200 עם local
    ו־road, ובכל צד coach ורשימת players. boxscore, players ו־report
    מחזירים 404 או 405, ו־v1 מחזיר XML. מה שחסר הוא שמות שדות המספרים,
    וזה כל מה שמודפס כאן."""
    print("\n" + HEAD, "\n2. היורוקאפ: שמות השדות בטופס\n", HEAD)
    url = STATS.format(s="U2025", c=185)
    print(url)
    try:
        body = requests.get(url, headers=ud.UA, timeout=30).json()
    except Exception as e:
        print("נפל:", e)
        return
    side = body.get("local") or {}
    print("מפתחות בצד:", list(side.keys()))
    players = side.get("players") or []
    print(f"{len(players)} שורות שחקנים")
    if players:
        row = players[0]
        print("\nמפתחות בשורת שחקן:", list(row.keys()))
        # כל מה שאינו האובייקט הגדול של השחקן, כלומר המספרים עצמם
        flat = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
        print("\nהמספרים בשורה, כמו שהם:")
        print(jshow(flat, 2000))
        nested = [k for k, v in row.items() if isinstance(v, (dict, list)) and k != "player"]
        for k in nested:
            print(f"\n{k}:", jshow(row[k], 700))
        pl = (row.get("player") or {})
        per = (pl.get("person") or {})
        print("\nזיהוי השחקן:", {x: per.get(x) for x in
              ("code", "name", "passportName", "passportSurname", "jerseyName")},
              "| מספר חולצה:", pl.get("dorsal"))
    for k, v in side.items():
        if k not in ("players", "coach"):
            print(f"\nסכומי הקבוצה ({k}):", jshow(v, 900))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "league"):
        probe_league()
    if which in ("all", "euro"):
        probe_eurocup()
