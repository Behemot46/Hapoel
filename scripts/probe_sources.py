"""בדיקת מקורות: לאן נעלם המשחק של 31.8, ומה התוצאה.

אחרי שהמשחק מול הפועל חולון שוחק, הוא נעלם מ־games.json לגמרי במקום
לקבל תוצאה. שתי אפשרויות שדורשות תיקון הפוך: או שאתר המועדון מוריד
משחק ששוחק מהעמוד, ואז אנחנו חייבים לשמור היסטוריה בעצמנו, או שהוא
עדיין שם עם תוצאה ואנחנו לא קוראים אותה.

מודפס מה שהעמוד מחזיר בפועל, כולל כל בלוק משחק גולמי, ומה הפרסר שלנו
מוציא ממנו.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import club_games
import update_data as u
from bs4 import BeautifulSoup


def log(*a):
    print("[probe]", *a, flush=True)


html = u.fetch(club_games.GAMES_URL)
log("עמוד המשחקים:", club_games.GAMES_URL, "|", len(html), "תווים")
soup = BeautifulSoup(html, "html.parser")
blocks = soup.select(".game")
log("בלוקים של משחק בעמוד:", len(blocks))
for i, g in enumerate(blocks[:8]):
    when = club_games._txt(g.select_one(".date-data .date-time"))
    score = club_games._txt(g.select_one(".game-data .score"))
    teams = [t.get("alt") for t in g.select(".teams-container img[alt]")]
    log(f"  [{i}] when={when!r} score={score!r} teams={teams}")

log("--- מה הפרסר מוציא ---")
games = club_games.fetch_games(u.fetch, log=log)
for g in games[:8]:
    log(f"  {g['date'][:16]} {g['home']} {g.get('homeScore')} : {g.get('awayScore')} "
        f"{g['away']}  status={g['status']}")
log("--- חיפוש 31.8 ---")
hit = [g for g in games if g["date"].startswith("2026-08-31")]
log("נמצא בפרסר:" , hit if hit else "לא נמצא")
if "31" in html and "אוגוסט" in html:
    log("המחרוזת ״אוגוסט״ מופיעה בעמוד")
