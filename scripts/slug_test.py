#!/usr/bin/env python3
"""ה־slug של שחקן חייב להישאר שלו, גם כשהשם שלו מתחלף.

**מה שקרה ב־23.9.2026 וממה שהמבחן הזה שומר.** אתר המועדון החליף את שחר
לוברבוים משם עברי לשם לטיני, וה־slug שלו התהפך מ־p-26156 ל־
shachar-loberboum. ה־slug הוא גם הכתובת שלו באפליקציה וגם שם קובץ
התמונה שלו, ולכן שני דברים נשברו בלי להשמיע רעש: הקישור אליו מהבוקס של
31.8 הפך למקום שאין בו שחקן, והתמונה שלו הייתה מתייתמת אם הייתה לו אחת.

**ושתי השבירות האלה שקטות לגמרי.** קישור מת נראה כמו עמוד ריק, ותמונה
חסרה נראית כמו שחקן בלי תמונה, וזה מצב רגיל אצלנו. אין שום סימן שמשהו
התקלקל, ולכן זה בדיוק מה שצריך מבחן.

מזהה המועדון לא מתחלף כשהשם מתחלף, ולכן המיפוי בין מזהה ל־slug נשמר
בקובץ, והמבחן הזה מוודא שהוא באמת מנצח את השם.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"


def main():
    fail = []

    # 1. הקובץ קיים ומכסה את כל הסגל, אחרת אין ממה להיזכר
    saved = ud.load_json(ud.SLUG_MAP) or {}
    saved = {k: v for k, v in saved.items() if not k.startswith("_")}
    roster = json.loads((DATA / "roster.json").read_text(encoding="utf-8"))
    players = roster["players"] if isinstance(roster, dict) else roster
    print(f"{len(saved)} מיפויים שמורים, {len(players)} שחקנים בסגל.")
    for p in players:
        cid = str(p.get("clubId") or "")
        if not cid:
            fail.append(f"{p.get('name')} בלי מזהה מועדון, אין לו על מה לשמור")
        elif saved.get(cid) != p["slug"]:
            fail.append(f"{p.get('name')}: בסגל {p['slug']}, בקובץ {saved.get(cid)}")

    # 2. **הבדיקה האמיתית:** שם מתחלף, וה־slug לא זז
    print("\nשם מתחלף, וה־slug נשאר:")
    before = [dict(p) for p in players]
    switched = []
    for p in before:
        he = p.get("nameHe") or "שחקן"
        p["name"] = he if p.get("name") != he else "Latin Name"
        switched.append((p["clubId"], p["slug"], p["name"]))
    # **המבחן לא כותב לשום קובץ, וזה תוקן אחרי שהוא כן כתב.** assign_slugs
    # שומרת מיפוי חדש לדיסק, ולכן הרצת מוטציה ראשונה דרסה את
    # player-slugs.json האמיתי במיפויים שגויים ושברה את הסגל. מבחן
    # שמשנה נתוני אמת הוא באג חמור יותר ממה שהוא בא לתפוס.
    saving = ud.save_json
    ud.save_json = lambda *a, **k: None
    try:
        ud.assign_slugs(before)
    finally:
        ud.save_json = saving
    for (cid, was, newname), now in zip(switched, before):
        state = "נשאר " if now["slug"] == was else "זז!  "
        if now["slug"] != was:
            fail.append(f"{newname}: ה־slug זז מ־{was} ל־{now['slug']}")
        print(f"  {state} {was:<24} כששמו הפך ל־{newname[:26]}")

    # **ומי שבודק שהקישורים מהטפסים חיים הוא boxscore_test, לא הקובץ הזה.**
    # כתבתי כאן בדיקה כזאת וגיליתי שהיא ריקה: teams הוא רשימה ולא מילון,
    # אז הלולאה שלי לא נכנסה לאף שורה והמבחן עבר על כלום. בדיקה ריקה
    # גרועה מאין בדיקה, כי היא נראית כמו כיסוי.

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        sys.exit(1)
    print("\nה־slug של כל שחקן קבוע, וגם שם לטיני חדש לא מזיז אותו.")


if __name__ == "__main__":
    main()
