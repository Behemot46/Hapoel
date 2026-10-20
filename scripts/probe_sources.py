#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם, 20.10.2026:** יונתן קלר, גארד ישראלי יליד 2007, נוסף לסגל
דרך הרישום ליורוקאפ ואתר המועדון לא מציג אותו, ולכן הוא מופיע באפליקציה
באותיות לטיניות. תעתיק שאני ממציא אסור, ולכן השם צריך לבוא ממקור שפרסם
אותו: העמוד של הליגה, שכתוב בעברית.

הכלי בודק אם העמוד הזה באמת מחזיק טבלת סגל עם מספרי חולצה, מה
``parse_roster`` מוציא ממנו, והאם ``fill_he_from_league`` משלים את השם
החסר. בלי זה התיקון הוא ניחוש שעובד רק במבחן.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from bs4 import BeautifulSoup

import update_data as ud


def main():
    link = ud.find_team_link()
    print(f"עמוד הקבוצה בליגה: {link}")
    if not link:
        return
    league = ud.parse_roster(BeautifulSoup(ud.fetch(link), "html.parser"))
    print(f"\n{len(league)} שחקנים נקראו מהעמוד:")
    for r in sorted(league, key=lambda x: x.get("number") or 99):
        print(f"  {str(r.get('number') or '-'):>3} {r.get('name','')[:24]:<24} "
              f"{r.get('position','')[:10]:<10} {r.get('born','')}")

    roster = json.loads(
        (ud.DATA / "roster.json").read_text(encoding="utf-8"))["players"]
    before = [p["name"] for p in roster if not p.get("nameHe")]
    print(f"\nבסגל שלנו בלי שם עברי: {before or 'אף אחד'}")
    filled = ud.fill_he_from_league(roster, league, log=ud.log)
    print(f"הושלמו {filled}:")
    for p in roster:
        if p["name"] in before:
            print(f"  {p['name']} -> {p.get('nameHe')!r}")


if __name__ == "__main__":
    main()
