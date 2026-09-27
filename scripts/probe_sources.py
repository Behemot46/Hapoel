#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שכבר ידוע, 27.9.2026, ואין טעם לבדוק שוב:**

  * **היורוקאפ פתור.** ‏``/v2/competitions/U/seasons/{s}/games/{c}/stats``
    מחזיר טופס מלא: בכל צד coach, players עם stats לכל שחקן, team
    לריבאונדים של הקבוצה ו־total לסכומים. שמות השדות: timePlayed
    בשניות, valuation, points, fieldGoalsMade2/3, freeThrowsMade,
    fieldGoalsMadeTotal, totalRebounds, defensiveRebounds,
    offensiveRebounds, assistances, steals, turnovers, blocksFavour,
    foulsCommited, plusMinus, dorsal, startFive. boxscore, players
    ו־report מחזירים 404 או 405, ו־v1 מחזיר XML.
  * **עמוד הקבוצה בליגה מקשר לכל משחק שנגמר** בכתובת
    ``game-zone.asp?GameId=NNNNN``, וטקסט הקישור הוא התוצאה. שלושת
    המשחקים הרשמיים שלנו העונה הם 26634, 26644 ו־26838.
  * ובעמוד המשחק יש טופס לשתי הקבוצות, תוצאות רבעים ונתונים נוספים.

**מה שנשאר, וזה כל מה שהכלי הזה עושה:** הדף של הליגה מוגש בקידוד עברי
ולא ב־UTF-8, והריצה הקודמת הדפיסה ג׳יבריש. כאן הוא מפוענח, ומודפס
במלואו, כדי שאפשר יהיה לכתוב פרסר מול טקסט אמיתי ולא מול ניחוש.

ובנוסף: איך מזהים באיזה משחק מדובר, כלומר מה יש בשורה בעמוד הקבוצה
שמקשרת לעמוד המשחק.
"""

import re
import sys
import pathlib

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

HEAD = "=" * 70
# המשחק של 25.9 מול בני הרצליה, 88-68, הרשמי האחרון שנגמר
GAME_ID = "26838"


def soup_of(url):
    r = requests.get(url, headers=ud.UA, timeout=30)
    r.raise_for_status()
    # **הדף הוא UTF-8 אבל לא מצהיר על זה**, ו־requests מנחשת latin-1.
    # נמדד פעמיים: בלי לקבוע קידוד יצא ג׳יבריש של UTF-8 כ־latin-1,
    # וכשקבעתי windows-1255 יצא ג׳יבריש אחר, של UTF-8 כעברית. שני סוגי
    # הג׳יבריש יחד הם מה שמוכיח שהדף עצמו UTF-8.
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def cells(row):
    return [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]


def probe_team_page():
    print(HEAD, "\n1. עמוד הקבוצה: איזו שורה מקשרת לאיזה משחק\n", HEAD)
    link = ud.find_team_link()
    print("עמוד הקבוצה:", link)
    soup = soup_of(link)
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not any(r.find("a", href=re.compile("game-zone")) for r in rows):
            continue
        print(f"\nטבלה עם {len(rows)} שורות. כותרת: {cells(rows[0])}")
        for r in rows:
            a = r.find("a", href=re.compile("game-zone"))
            if not a:
                continue
            gid = re.search(r"GameId=(\d+)", a["href"])
            print(f"  GameId={gid.group(1) if gid else '?'} · {cells(r)}")


def probe_game_page():
    print("\n" + HEAD, f"\n2. עמוד המשחק {GAME_ID}, מפוענח ובמלואו\n", HEAD)
    url = f"https://basket.co.il/game-zone.asp?GameId={GAME_ID}"
    print(url)
    soup = soup_of(url)
    print("title:", soup.title.get_text(strip=True) if soup.title else "")
    tables = soup.find_all("table")
    print(f"{len(tables)} טבלאות")
    # מודפסות לפי אינדקס ולא לפי זיהוי טקסט: הריצה הקודמת סיננה הכול,
    # כי ההשוואה לעברית נעשתה על טקסט מקולקל. הטווח 9 עד 15 הוא הרבעים,
    # שני הטפסים, הנתונים הנוספים ושתי הטבלאות שאחריהם.
    for i in range(9, min(16, len(tables))):
        rows = tables[i].find_all("tr")
        print(f"\n### טבלה {i}: {len(rows)} שורות")
        for r in rows:
            print("    ", cells(r))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "team"):
        probe_team_page()
    if which in ("all", "game"):
        probe_game_page()
