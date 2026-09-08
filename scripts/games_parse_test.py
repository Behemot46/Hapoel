"""בדיקה של פרסר לוח המשחקים, על השורה האמיתית שהפילה אותנו.

הבאג: עד 8.9.2026 הפרסר קרא את תא התוצאה כמארחת ואז אורחת, וכך המשחק
הרשמי הראשון של העונה הוצג לאוהד כהפסד 110-77 במקום ניצחון. תא התוצאה
באתר הליגה כתוב **אורחת ואז מארחת**.

הבדיקה הזאת מזינה לפרסר את השורה כפי שהיא באתר, ומוודאת שכל מספר הגיע
לקבוצה שלו. יש כאן גם המקרה ההפוך, שבו אנחנו המארחת, כי כלל שמתקן צד
אחד ושובר את השני הוא לא תיקון.

    python scripts/games_parse_test.py
"""
import pathlib
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u

HEAD = "<tr><th>תאריך</th><th>שעה</th><th>שלב</th><th>מארחת</th><th>אורחת</th><th>תוצאה</th></tr>"


def row(date, time, stage, host, guest, score):
    return (f"<tr><td>{date}</td><td>{time}</td><td>{stage}</td>"
            f"<td>{host}</td><td>{guest}</td><td>{score}</td></tr>")


def parse(*rows):
    html = "<table>" + HEAD + "".join(rows) + "</table>"
    return u.parse_team_games(BeautifulSoup(html, "html.parser"))


def main():
    fail = []

    def check(what, got, want):
        if got != want:
            fail.append(f"{what}: אצלנו {got}, אמור להיות {want}")

    # השורה האמיתית מ־8.9.2026, כפי שהודפסה מהאתר בבדיקת מקורות:
    # מארחת מכבי אשדוד, אורחת הפועל י-ם, תא התוצאה 110-77.
    # העיתונות: הפועל ירושלים ניצחה 110-77.
    g = parse(row("08/09/2026", "19:00", "גביע ווינר סל",
                  "מכבי אשדוד", "הפועל י-ם", "110-77"))[0]
    check("המשחק שלנו בחוץ, מארחת", g["home"], "מכבי אשדוד")
    check("המשחק שלנו בחוץ, אורחת", g["away"], "הפועל ירושלים")
    check("הנקודות של המארחת", g["homeScore"], 77)
    check("הנקודות של האורחת (שלנו)", g["awayScore"], 110)
    check("סטטוס", g["status"], "finished")

    # ואותו כלל כשאנחנו המארחת: 88 לאורחת, 95 לנו
    g = parse(row("18/09/2026", "20:00", "גביע ווינר סל",
                  "הפועל י-ם", "הפועל ב\"ש", "88-95"))[0]
    check("משחק בית, מארחת", g["home"], "הפועל ירושלים")
    check("משחק בית, הנקודות שלנו", g["homeScore"], 95)
    check("משחק בית, הנקודות של האורחת", g["awayScore"], 88)

    # משחק שטרם שוחק נשאר בלי מספרים ובלי סטטוס גמור
    g = parse(row("11/10/2026", "", "ליגת ווינר סל",
                  "הפועל חולון", "הפועל י-ם", ""))[0]
    check("משחק עתידי, סטטוס", g["status"], "scheduled")
    check("משחק עתידי, אין תוצאה", (g["homeScore"], g["awayScore"]), (None, None))
    check("משחק בלי שעה מסומן", g.get("timeTbd"), True)

    if fail:
        print(f"{len(fail)} כשלים:")
        for f in fail:
            print("  ✗", f)
        return 1
    print("הפרסר מחזיר כל מספר לקבוצה שלו, בבית ובחוץ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
