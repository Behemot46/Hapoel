#!/usr/bin/env python3
"""הסגל נבנה משני מקורות, ושם עברי לא נעלם כשאחד מהם מפסיק להציג שחקן.

**התקלה, 11.10.2026.** השם העברי מגיע מאתר המועדון. באיסוף של 11.10
האתר הפסיק להציג שלושה שחקנים, ג׳ארד הארפר, שייק מילטון ודייוויד רודי,
ומאז הם הופיעו באפליקציה באותיות לטיניות בעוד שתשעת האחרים בעברית. הם
לא עזבו: מילטון שיחק תשעה משחקים העונה ורודי שמונה, כולל 6.10.

``player-names.json`` נערך ביד ומחזיק בדיוק את השמות האלה, ולכן הוא
המקור במקרה הזה. **הוא לא השלמה ולא ניחוש**, והאיסוף לעולם לא כותב
אליו. שחקן שאינו בו יוצג בשמו הלועזי, וזה מה שכתוב בו במילים.

הנתונים כאן אמיתיים: שתי הרשומות הן של מילטון, לפני ואחרי.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

NAMES = {"_comment": "ידני", "Shake Milton": "שייק מילטון",
         "Jaleen Smith": "ג׳יילן סמית׳"}

# מהפיד האירופי, כפי שהוא נראה היום
EURO = [
    {"name": "Shake Milton", "number": 9, "position": "גארד", "height": 196,
     "born": 1996, "country": "ארה״ב", "code": "014007"},
    {"name": "Jaleen Smith", "number": 3, "position": "גארד", "height": 193,
     "born": 1994, "country": "ארה״ב", "code": "011192"},
]


def run(club):
    saved = ud.load_json
    ud.load_json = lambda name: NAMES if name == "player-names.json" else saved(name)
    try:
        return {p["name"]: p for p in ud.merge_club_and_euro(club, [dict(e) for e in EURO])}
    finally:
        ud.load_json = saved


def main():
    fail = []

    # 1. כשהאתר מציג את שניהם, השם שלו הוא הקובע
    both = run([{"name": "ג׳יילן סמית׳", "number": 3, "clubId": "26045"},
                {"name": "שייק מילטון", "number": 9, "clubId": "26049"}])
    print("אתר המועדון מציג את שניהם:")
    for n, p in both.items():
        print(f"   {n:<16} nameHe={p.get('nameHe')}  source={p.get('source')}")
    if both["Shake Milton"].get("nameHe") != "שייק מילטון":
        fail.append("השם מהאתר לא נשמר")
    if both["Shake Milton"].get("source") != "club+eurocup":
        fail.append(f"מקור שגוי: {both['Shake Milton'].get('source')}")

    # 2. **וזה המקרה שנשבר:** האתר הפסיק להציג את מילטון
    dropped = run([{"name": "ג׳יילן סמית׳", "number": 3, "clubId": "26045"}])
    print("\nאתר המועדון הפסיק להציג את מילטון:")
    for n, p in dropped.items():
        print(f"   {n:<16} nameHe={p.get('nameHe')}  source={p.get('source')}")
    milton = dropped.get("Shake Milton") or {}
    if milton.get("nameHe") != "שייק מילטון":
        fail.append(f"השם העברי אבד: {milton.get('nameHe')}")
    if milton.get("source") != "eurocup":
        fail.append(f"מקור שגוי לשחקן שנשמט: {milton.get('source')}")
    if len(dropped) != 2:
        fail.append(f"{len(dropped)} שחקנים בסגל במקום 2")

    # 3. ומי שאינו בקובץ הידני נשאר בשמו הלועזי, כמו שכתוב בקובץ עצמו
    nameless = run([])
    print("\nבלי אתר המועדון בכלל, ושם אחד חסר מהקובץ הידני:")
    saved = ud.load_json
    ud.load_json = lambda name: ({"_comment": "ידני"}
                                 if name == "player-names.json" else saved(name))
    try:
        bare = {p["name"]: p for p in
                ud.merge_club_and_euro([], [dict(e) for e in EURO])}
    finally:
        ud.load_json = saved
    for n, p in bare.items():
        print(f"   {n:<16} nameHe={p.get('nameHe')}")
    if any(p.get("nameHe") for p in bare.values()):
        fail.append("הומצא שם עברי למי שאינו בקובץ הידני")
    if nameless["Shake Milton"].get("nameHe") != "שייק מילטון":
        fail.append("השם מהקובץ הידני לא נכנס בלי אתר המועדון")

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        return 1
    print("\nשם עברי שהיה לנו לא נעלם, ושם שאינו מאומת לא מומצא.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
