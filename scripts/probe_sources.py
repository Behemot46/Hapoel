"""בדיקת מקורות: איך אתר המועדון מציג את התוצאה של 8.9.

באתר המועדון כל קבוצה היא תמונה עם alt, והתוצאה היא מחרוזת ״A:B״ אחת.
מה שצריך לדעת: איזה מספר שייך לאיזו קבוצה. את האמת אנחנו כבר יודעים
משלוש כותרות עצמאיות (הפועל ירושלים ניצחה 110-77 את מכבי אשדוד), ולכן
מה שנראה כאן מכריע את הסדר גם באתר המועדון וגם, בהצלבה, באתר הליגה.
"""
import re
import sys
import pathlib

from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u
import club_games


def log(*a):
    print("[probe]", *a, flush=True)


html = u.fetch("https://hapoel.co.il/games")
soup = BeautifulSoup(html, "html.parser")
found = 0
for g in soup.select(".game"):
    teams = [i.get("alt", "").strip() for i in g.select(".teams-container img") if i.get("alt")]
    when = club_games._txt(g.select_one(".date-time"))
    score = club_games._txt(g.select_one(".score"))
    if not teams:
        continue
    if "8/9" not in when and "08/09" not in when and "8.9" not in when:
        continue
    log(f"תאריך גולמי: {when!r}")
    log(f"סדר הקבוצות (לפי alt של הלוגו): {teams}")
    log(f"תא התוצאה: {score!r}")
    log(f"מקום: {club_games._txt(g.select_one('.game-type .container .text'))!r}")
    found += 1

if not found:
    log("לא נמצאה שורה של 8.9. כל המשחקים שיש בעמוד, עם התוצאה שלהם:")
    for g in soup.select(".game")[:14]:
        teams = [i.get("alt", "").strip() for i in g.select(".teams-container img") if i.get("alt")]
        log(f"  {club_games._txt(g.select_one('.date-time'))!r} | {teams} | "
            f"{club_games._txt(g.select_one('.score'))!r}")
