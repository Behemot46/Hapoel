#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שנמדד כאן ב־20.10.2026, וחבל שיישכח:** יונתן קלר, גארד ישראלי יליד
2007, נוסף לסגל דרך הרישום ליורוקאפ. אתר המועדון לא מציג אותו ולכן אין
לו שם עברי, והוא מופיע באפליקציה באותיות לטיניות.

הרעיון היה לקחת את השם מהעמוד של הליגה, שכתוב בעברית.
**זה לא עובד, ונמדד:** ``parse_roster`` על ``team.asp?TeamId=2114``
מחזיר **אפס שחקנים**. לעמוד הקבוצה אין טבלת סגל שהפרסר מזהה, וזו בדיוק
הסיבה שמסלול הגיבוי ב־``update_roster`` לא מסתפק בו אלא ממשיך
ל־``roster_candidates`` ואחר כך לעמוד סטטיסטיקה לפי TeamId.

**הניסיון הבא, כשתהיה דחיפה בלאו הכי:** לקרוא את כל שרשרת הגיבוי ולא
רק את הצעד הראשון שלה, ולהדפיס מה כל מועמד מחזיר. אם גם שם אין סגל
בעברית, המקור הסביר היחיד שנשאר הוא טופס משחק של הליגה, שבו שמות
השחקנים בעברית, וזה יקרה רק כשקלר ישחק משחק רשמי.
"""
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
    soup = BeautifulSoup(ud.fetch(link), "html.parser")
    print(f"  {len(ud.parse_roster(soup))} שחקנים מהעמוד עצמו")
    for u in ud.roster_candidates(link, soup)[:6]:
        try:
            sub = BeautifulSoup(ud.fetch(u), "html.parser")
        except Exception as e:
            print(f"  {u}: נפל, {e}")
            continue
        found = ud.parse_roster(sub)
        print(f"  {u}: {len(found)} שחקנים")
        for r in sorted(found, key=lambda x: x.get("number") or 99)[:20]:
            print(f"      {str(r.get('number') or '-'):>3} {r.get('name','')[:24]}")


if __name__ == "__main__":
    main()
