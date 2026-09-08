"""בדיקה של מצב התוצאה החיה: מה נכתב, ומתי בכלל נכתב.

שני באגים אמיתיים נבדקים כאן, שניהם מ־8.9.2026, המשחק הרשמי הראשון של
העונה:

1. הפולר הכריז ״המשחק מתנהל״ ברגע שנכנס לחלון, כלומר לפני הקפיצה.
   האוהד ראה ״עכשיו · המשחק מתנהל״ על משחק שלא התחיל.
2. כל דגימה חידשה את חותמת הזמן ולכן ייצרה קומיט ודיפלוי, גם כשלא
   השתנה כלום. עם חלון של 75 דקות זה 25 דחיפות לפני כל משחק.

    python scripts/live_state_test.py
"""
import datetime
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_live as ul

GAME = {"id": "g", "date": "2026-09-08T19:00:00+03:00", "status": "scheduled",
        "competition": "גביע ווינר סל", "home": "מכבי אשדוד",
        "away": "הפועל ירושלים", "venue": None}
TIP = datetime.datetime.fromisoformat(GAME["date"])


def run_at(t, tmp):
    """הרצה אחת של הפולר בזמן נתון, מול תיקיית נתונים זמנית."""
    ul.now = lambda: t
    ul.load = lambda name: {"games": [GAME]} if name == "games.json" else {}
    ul.DATA = tmp
    ul.main()
    p = tmp / "live.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main():
    fail = []
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)

        cases = [
            ("שעה ורבע לפני הקפיצה", TIP - datetime.timedelta(minutes=74), "starting"),
            ("דקה לפני הקפיצה", TIP - datetime.timedelta(minutes=1), "starting"),
            ("רגע אחרי הקפיצה", TIP + datetime.timedelta(minutes=1), "playing"),
            ("באמצע המשחק", TIP + datetime.timedelta(minutes=60), "playing"),
            ("ארבע שעות אחרי", TIP + datetime.timedelta(hours=4), "idle"),
        ]
        for label, t, want in cases:
            got = run_at(t, tmp).get("state")
            if got != want:
                fail.append(f"{label}: {got}, אמור להיות {want}")

        # וחותמת הזמן: שתי דגימות סמוכות לפני הקפיצה לא מייצרות שינוי
        t0 = TIP - datetime.timedelta(minutes=70)
        first = run_at(t0, tmp)
        again = run_at(t0 + datetime.timedelta(minutes=3), tmp)
        if again.get("updated") != first.get("updated"):
            fail.append("דגימה שלוש דקות אחרי חידשה את החותמת בלי סיבה")
        later = run_at(t0 + datetime.timedelta(minutes=16), tmp)
        if later.get("updated") == first.get("updated"):
            fail.append("אחרי רבע שעה החותמת הייתה צריכה להתרענן")
        # וכשהמצב באמת משתנה, כותבים מיד
        after_tip = run_at(TIP + datetime.timedelta(minutes=1), tmp)
        if after_tip.get("state") != "playing":
            fail.append("שינוי מצב אמיתי לא נכתב מיד")

    if fail:
        print(f"{len(fail)} כשלים:")
        for f in fail:
            print("  ✗", f)
        return 1
    print("המצב נכון סביב הקפיצה, והכתיבה קורית רק כשיש מה לומר.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
