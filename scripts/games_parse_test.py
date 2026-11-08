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

    # **והשעה של משחקי היורוקאפ כשהפיד הראשי נופל.** נמדד ב־4.11.2026
    # מול אריס: בקשה אחת נכשלה, הגיבוי קרא את date, ״20:00״ בשעון מרכז
    # אירופה, וחתם אותו +03:00, כלומר שעתיים מוקדם. כל משחקי היורוקאפ
    # על הלוח זזו לשלוש שעות, והכרטיס החי נסגר מוקדם. המספרים כאן הם
    # בדיוק מה שהגיבוי קרא באותו ערב, מול מה שהפיד הראשי נותן לאותם משחקים.
    import datetime as dt
    def instant(s):
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    utc = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
    full = {"date": "2026-11-04T20:00:00", "localdate": "2026-11-04T20:00:00",
            "utcdate": "2026-11-04T19:00:00Z"}
    check("יורוקאפ, utcDate קודם לכל השאר", u._date_of(full), "2026-11-04T19:00:00Z")
    check("יורוקאפ, date לבד בחורף הוא שעון מרכז אירופה",
          instant(u._date_of({"date": "2026-11-04T20:00:00"})), utc("2026-11-04T19:00:00"))
    check("יורוקאפ, המשחק השני מול אריס",
          instant(u._date_of({"date": "2027-01-05T19:00:00"})), utc("2027-01-05T18:00:00"))
    check("יורוקאפ, date לבד בקיץ",
          instant(u._date_of({"date": "2026-09-29T19:00:00"})), utc("2026-09-29T17:00:00"))

    if fail:
        print(f"{len(fail)} כשלים:")
        for f in fail:
            print("  ✗", f)
        return 1
    print("הפרסר מחזיר כל מספר לקבוצה שלו, בבית ובחוץ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
