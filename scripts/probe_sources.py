#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם, והיא פתוחה מ־20.10.2026:** יונתן קלר, גארד ישראלי יליד
2007, נוסף לסגל דרך הרישום ליורוקאפ. אתר המועדון לא מציג אותו ולכן אין
לו שם עברי, והוא מופיע באפליקציה באותיות לטיניות. **אין להמציא תעתיק.**

מה שנמדד ונפסל: ``parse_roster`` על ``team.asp?TeamId=2114`` מחזיר **אפס
שחקנים**, ולכן אותו עמוד לבדו הוא לא מקור לשם עברי.

**ומה שהתגלה ב־27.10:** חיפוש באינטרנט החזיר את
``basket.co.il/team.asp?TeamId=1112&lang=en``, ושם קלר כן מופיע ברשימת
הסגל. כלומר ל־2114 ול־1112 יש תפקידים שונים באתר הליגה, ו־
``find_team_link`` מוצא את הראשון.

ולכן שתי שאלות נפרדות, ושתיהן נבדקות כאן:

1. האם יש עמוד באתר הליגה שהפרסר מזהה בו סגל, לאורך **כל** שרשרת
   הגיבוי של ``update_roster`` ולא רק הצעד הראשון שלה.
2. **והחשובה יותר:** האם המילה ״קלר״ מופיעה בעברית באחד העמודים האלה
   בכלל, גם אם הפרסר לא מזהה שם טבלת סגל. שם שמפרסם כתב הוא נתון; שם
   שאני מרכיב מהאותיות הלטיניות הוא המצאה, וזה הגבול.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import requests
from bs4 import BeautifulSoup

import update_data as ud

# ״קלר״ ככתיב הצפוי, ו־Keller כדי לראות שבכלל הגענו לעמוד הנכון
HE = re.compile(r"קלר")
LAT = re.compile(r"Keller", re.I)


def look(label, url):
    """מוריד עמוד אחד, ומדווח גם סגל וגם אזכור של השם."""
    try:
        html = ud.fetch(url)
    except Exception as e:
        print(f"  {label}: נפל, {type(e).__name__} {e}")
        return None
    soup = BeautifulSoup(html, "html.parser")
    found = ud.parse_roster(soup)
    text = soup.get_text(" ", strip=True)
    marks = []
    if LAT.search(text):
        marks.append("Keller")
    if HE.search(text):
        marks.append("קלר")
    print(f"  {label}: {len(found)} שחקנים, {len(text)} תווים"
          + (f", מוזכר: {', '.join(marks)}" if marks else ""))
    for r in sorted(found, key=lambda x: x.get("number") or 99)[:20]:
        print(f"      {str(r.get('number') or '-'):>3} {r.get('name','')[:28]}")
    # **וההקשר, כי זה מה שקובע.** מדפיסים את הסביבה של כל אזכור, כדי
    # לקרוא בעיניים איך המפרסם כתב את השם ולא לנחש אותו.
    for pat in (HE, LAT):
        for m in list(pat.finditer(text))[:4]:
            a, b = max(0, m.start() - 70), min(len(text), m.end() + 70)
            print(f"      … {text[a:b]} …")
    return soup


def main():
    link = ud.find_team_link()
    print(f"עמוד הקבוצה כפי ש־find_team_link מוצא אותו: {link}")
    soup = look("אותו עמוד", link) if link else None

    if soup is not None:
        print("\nשרשרת roster_candidates:")
        for u in ud.roster_candidates(link, soup)[:6]:
            look(u, u)

    tid = None
    if link:
        m = re.search(r"TeamId=(\d+)", link)
        tid = m.group(1) if m else None
    print(f"\nעמודים לפי TeamId, גם זה שנמצא ({tid}) וגם 1112 מהחיפוש:")
    paths = ("team.asp?TeamId={}", "stats-individual.asp?TeamId={}",
             "stats-individual.asp?TeamId={}&cYear=2027",
             "team-players.asp?TeamId={}", "players.asp?TeamId={}",
             "stats-accumulate.asp?TeamId={}")
    for t in [x for x in (tid, "1112") if x]:
        for path in paths:
            u = requests.compat.urljoin(ud.LEAGUE_HOME, path.format(t))
            look(u, u)

    print("\nוהעמוד שהחיפוש החזיר, באנגלית, רק כדי לאמת שזו הקבוצה הנכונה:")
    look("1112&lang=en",
         requests.compat.urljoin(ud.LEAGUE_HOME, "team.asp?TeamId=1112&lang=en"))


if __name__ == "__main__":
    main()
