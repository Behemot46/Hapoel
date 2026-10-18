#!/usr/bin/env python3
"""האולם של משחק לא נעלם ברגע שהמשחק נגמר.

**התקלה, 18.10.2026.** האולם של משחק ישראלי מגיע רק מאתר המועדון,
והמועדון מחליף את כרטיס המשחק ברגע שהוא נגמר: במקום המקום והשידור
מופיעה התוצאה. אתר הליגה לא נותן אולם בכלל, ולכן הרשומה נבנתה מחדש בלי
אולם וכתבה ריק על מה שכבר ידענו.

נמדד על המשחק הביתי מול ב״ש: ב־15.10 ״פיס ארנה, ירושלים״, וב־17.10
בערב, אחרי השריקה, ריק. אותו דבר בכל משחקי הגביע והליגה שנגמרו, בעוד
שהמשחקים האירופיים שמרו על האולם שלהם כי שם הוא מגיע מהפיד.

הנתונים כאן אמיתיים, משתי הגרסאות של הקובץ.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

BEFORE = [
    {"id": "20261017-הפועלבש", "date": "2026-10-17T20:15:00+03:00",
     "home": "הפועל ירושלים", "away": "הפועל ב\"ש", "status": "scheduled",
     "venue": "פיס ארנה, ירושלים", "broadcast": {"channel": "ONE"}},
    {"id": "20261021-euro-RigaZelli", "date": "2026-10-21T18:00:00Z",
     "home": "הפועל ירושלים", "away": "Riga Zelli", "status": "scheduled",
     "venue": "Hala Sportova Ranko Zeravica"},
]


def main():
    fail = []

    # 1. אחרי השריקה הרשומה נבנית מחדש בלי אולם ובלי שידור
    after = [dict(BEFORE[0], status="finished", homeScore=88, awayScore=74,
                  venue=None, broadcast=None)]
    ud.carry_known_fields(after, BEFORE)
    print("אחרי שהמשחק נגמר:")
    print(f"   venue={after[0]['venue']!r}  broadcast={after[0]['broadcast']!r}")
    if after[0]["venue"] != "פיס ארנה, ירושלים":
        fail.append(f"האולם אבד: {after[0]['venue']!r}")
    if not after[0]["broadcast"]:
        fail.append("השידור אבד")

    # 2. **ומה שמקור כן אומר לא נדרס.** משחק שהועבר לאולם אחר חייב לקבל
    #    את החדש, אחרת הצעד הזה מקפיא טעות במקום לשמור נתון.
    moved = [dict(BEFORE[0], venue="היכל מנורה מבטחים, ת\"א")]
    ud.carry_known_fields(moved, BEFORE)
    print(f"\nמשחק שהועבר: {moved[0]['venue']}")
    if moved[0]["venue"] != "היכל מנורה מבטחים, ת\"א":
        fail.append("האולם החדש נדרס בישן")

    # 3. אותו משחק עם מזהה אחר, כי הוא עבר מלוח המועדון ללוח הליגה
    renamed = [dict(BEFORE[0], id="20261017-club-הפועלבש", venue=None)]
    ud.carry_known_fields(renamed, BEFORE)
    print(f"מזהה שהתחלף: {renamed[0]['venue']!r}")
    if renamed[0]["venue"] != "פיס ארנה, ירושלים":
        fail.append("זיווג לפי יריבה ותאריך לא עבד")

    # 4. ומשחק שלא היה בקובץ הקודם לא מקבל כלום
    brand_new = [{"id": "20270101-חדש", "date": "2027-01-01T18:00:00Z",
                  "home": "הפועל ירושלים", "away": "קבוצה חדשה"}]
    ud.carry_known_fields(brand_new, BEFORE)
    print(f"משחק חדש: venue={brand_new[0].get('venue')!r}")
    if brand_new[0].get("venue"):
        fail.append("הומצא אולם למשחק שלא הכרנו")

    # 5. ומשחק אחר באותו יום לא גונב את האולם של השכן שלו
    same_day = [{"id": "20261017-אחר", "date": "2026-10-17T12:00:00+03:00",
                 "home": "הפועל ירושלים", "away": "קבוצה אחרת"}]
    ud.carry_known_fields(same_day, BEFORE)
    print(f"משחק אחר באותו יום: venue={same_day[0].get('venue')!r}")
    if same_day[0].get("venue"):
        fail.append("אולם עבר למשחק אחר באותו יום")

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        return 1
    print("\nמה שהיה לנו נשמר, ומה שמקור אומר מנצח אותו.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
