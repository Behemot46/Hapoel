#!/usr/bin/env python3
"""השידור: מה נלקח מאתר המועדון, ומה בכוונה לא.

אתר המועדון הוא **המקור היחיד** שמפרסם באיזה ערוץ משודר משחק. נמדד
ב־11.9.2026: אתר הליגה לא מחזיק עמודת שידור, ועמודי לוח השידורים של
ספורט 5 ושל ONE מחזירים 404. לכן אין כאן מקור שני להצליב מולו, וכל מה
שאפשר לעשות הוא לוודא שהחילוץ עצמו לא משקר.

הכרטיסים כאן הועתקו מהמבנה החי, ושלושה מהם הם מלכודות שכבר נפלו בהן:

1. **״פיס ארנה, ירושלים״ מכיל את המחרוזת ״יס״.** הגרסה הראשונה של
   הקוד חיפשה שמות ערוצים כתת־מחרוזת והכניסה את ״יס״ לרשימה, ולכן
   האולם הביתי שלנו סווג כערוץ טלוויזיה והמשחק הוצג בלי מקום.
2. **כרטיס שיש בו שידור ואין בו מקום.** חילוץ לפי מיקום קשיח היה מציג
   את שם הערוץ לאוהד ככתובת האולם.
3. **״שידור טרם נקבע״ אינו ״לא משודר״.** זו אמירה של המועדון, והיא
   נשמרת בנפרד מהיעדר מוחלט של השדה, שאומר רק שאיננו יודעים.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import club_games
import update_data

FAIL = []


def check(ok, msg):
    print(("  תקין:  " if ok else "  נשבר: ") + msg)
    if not ok:
        FAIL.append(msg)


def card(when, cycle, cells, teams):
    texts = "".join(f'<div class="text">{c}</div>' for c in cells)
    imgs = "".join(f'<img alt="{t}">' for t in teams)
    return f"""
    <div class="game">
      <div class="date-data"><div class="date-time">{when}</div>
        <div class="cycle">{cycle}</div></div>
      <div class="row league"><div class="game-type"><div class="container">
        {texts}</div></div></div>
      <div class="teams"><div class="teams-container">{imgs}</div></div>
      <div class="row game-data"><div class="score">0:0</div></div>
    </div>"""


HTML = "".join([
    # כפי שהוא באמת בעמוד, 18.9.2026
    card("18 בספטמבר, שישי 14:30", "גביע ווינר סל",
         ["פיס ארנה, ירושלים", "5STARS"], ["הפועל י-ם", "הפועל ב&quot;ש"]),
    card("11 באוקטובר, ראשון", "ליגת Winner סל",
         ["היכל טוטו, חולון", "שידור טרם נקבע"], ["הפועל חולון", "הפועל י-ם"]),
    card("12 בספטמבר, שבת 16:30", "משחקי הכנה",
         ["וילנה"], ["הפועל י-ם", "בורג"]),
    # מלכודת: שידור בלי מקום
    card("20 בספטמבר, ראשון 20:00", "גביע ווינר סל",
         ["ספורט 5"], ["הפועל י-ם", "מכבי ת&quot;א"]),
])


def main():
    games = {g["date"][:10]: g for g in club_games.parse_games(HTML, 2026)}
    print("חילוץ מאתר המועדון:")

    g = games["2026-09-18"]
    check(g.get("venue") == "פיס ארנה, ירושלים",
          f"״פיס ארנה״ נשאר מקום ולא הפך לערוץ (venue={g.get('venue')!r})")
    check(g.get("broadcast") == {"channel": "5STARS"},
          f"הערוץ נקרא ({g.get('broadcast')!r})")

    g = games["2026-10-11"]
    check(g.get("broadcast") == {"pending": True},
          f"״טרם נקבע״ נשמר כאמירה ולא כערוץ ({g.get('broadcast')!r})")
    check(g.get("venue") == "היכל טוטו, חולון", "והמקום לצידו")

    g = games["2026-09-12"]
    check("broadcast" not in g,
          "משחק שלא כתוב עליו כלום נשאר בלי שדה, ולא ״לא משודר״")
    check(g.get("venue") == "וילנה", "והמקום שלו נקרא")

    g = games["2026-09-20"]
    check(g.get("broadcast") == {"channel": "ספורט 5"} and not g.get("venue"),
          f"שידור בלי מקום לא הופך לכתובת אולם "
          f"(venue={g.get('venue')!r}, broadcast={g.get('broadcast')!r})")

    print("\nהעשרה של משחק שכבר הגיע ממקור רשמי:")
    # כך נראה הגביע ב־18.9 כשהוא מגיע מאתר הליגה: בלי מקום ובלי שידור
    board = [{"id": "20260918-הפועלבש", "date": "2026-09-18T14:30:00+03:00",
              "competition": "גביע ווינר סל", "home": "הפועל ירושלים",
              "away": 'הפועל ב"ש', "venue": None, "status": "scheduled"},
             {"id": "x", "date": "2026-09-12T16:30:00+03:00",
              "competition": "משחק הכנה", "home": "הפועל ירושלים",
              "away": "בורג", "venue": "מלחה", "status": "scheduled"}]
    update_data.enrich_from_club(board, list(games.values()))
    check(board[0].get("broadcast") == {"channel": "5STARS"},
          "השידור הושלם על משחק שהליגה נתנה בלי שידור")
    check(board[0].get("venue") == "פיס ארנה, ירושלים",
          "וגם המקום, שהיה חסר")
    check(board[1].get("venue") == "מלחה",
          "מקום שכבר היה על הלוח לא נדרס")

    print("\nהמקום מהמועדון מול רשימת אולם הבית של האפליקציה:")
    # **למה זה נבדק כאן.** ברגע שהמקום של הגביע ב־18.9 הושלם מאתר
    # המועדון כ־״פיס ארנה, ירושלים״, הוא הפסיק להתאים לרשימה
    # ב־venue-names.json, ו־homeAwayLabel הציג ״בית מחוץ לישראל״ על
    # משחק ביתי בירושלים. שני הקבצים חייבים להסכים, וזו ההסכמה.
    import json
    root = pathlib.Path(__file__).resolve().parent.parent
    home = json.loads((root / "app" / "data" / "venue-names.json")
                      .read_text(encoding="utf-8"))["homeArena"]

    def key(s):
        return str(s or "").split(",")[0].strip().lower()

    keys = {key(h) for h in home}
    for written in ("פיס ארנה, ירושלים", "פיס ארנה", "Pais Arena", "מלחה"):
        check(key(written) in keys,
              f"״{written}״ מזוהה כאולם הבית")
    check(key("היכל טוטו, חולון") not in keys,
          "היכל טוטו בחולון לא מזוהה בטעות כאולם הבית")

    if FAIL:
        print(f"\nנשברו {len(FAIL)} בדיקות.")
        sys.exit(1)
    print("\nהשידור נקרא נכון, והמלכודות שנפלנו בהן סגורות.")


if __name__ == "__main__":
    main()
