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
        # **שחקן על slug זמני לא נבדק כאן, כי הוא דווקא אמור לזוז.** לורנזו
        # בראון פורסם בעברית בלבד ולכן יש לו p-27222, ושם לטיני חדש שלו
        # הוא בדיוק המקרה שבו הכתובת שלו משתדרגת. הבדיקה הזאת היא על
        # כתובות אמיתיות, ובראון נבדק בסעיף שאחריה.
        if ud.is_placeholder_slug(p["slug"], str(p.get("clubId") or "")):
            print(f"  מדולג {p['slug']:<24} כתובת זמנית, נבדקת בהמשך")
            continue
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
    # מזווגים לפי מזהה ולא לפי מקום ברשימה, כי הדילוג למעלה כבר הוציא
    # שחקן אחד מהאמצע וזיווג לפי סדר הוא בדיוק סוג הדיוק שנשבר בשקט.
    by_id = {str(p.get("clubId")): p for p in before}
    for cid, was, newname in switched:
        now = by_id[str(cid)]
        state = "נשאר " if now["slug"] == was else "זז!  "
        if now["slug"] != was:
            fail.append(f"{newname}: ה־slug זז מ־{was} ל־{now['slug']}")
        print(f"  {state} {was:<24} כששמו הפך ל־{newname[:26]}")

    # **ו־slug זמני כן משתדרג, פעם אחת, עם כל מה שמצביע עליו.**
    # ב־25.9 נחתם לורנזו בראון ואתר המועדון פרסם אותו בעברית בלבד, אז הוא
    # קיבל p-27222. הקפאה של זה הייתה משאירה לו את הכתובת הזאת לנצח, וזה
    # מחיר מטופש. אבל זה בדיוק המעבר שנשבר אצל לוברבוים, ולכן הוא נבדק
    # כאן משני הצדדים: שהשדרוג קורה, ושהשורה בטופס עוברת איתו.
    print("\nslug זמני משתדרג כשהשם הלטיני מגיע:")
    fake = [{"clubId": "999001", "name": "שם בעברית", "nameHe": "שם בעברית"}]
    saving, mig = ud.save_json, ud.migrate_slug_references
    ud.save_json = lambda *a, **k: None
    seen = []
    ud.migrate_slug_references = lambda ups: seen.extend(ups)
    try:
        ud.assign_slugs(fake)
        first = fake[0]["slug"]
        fake[0]["name"] = "Latin Name"
        # הזיכרון נקרא מהקובץ, אז הסימולציה מזריקה אותו דרך load_json
        loading = ud.load_json
        ud.load_json = (lambda name: {"999001": first}
                        if name == ud.SLUG_MAP else loading(name))
        try:
            ud.assign_slugs(fake)
        finally:
            ud.load_json = loading
    finally:
        ud.save_json, ud.migrate_slug_references = saving, mig
    second = fake[0]["slug"]
    print(f"  {first} -> {second}")
    if first != "p-999001":
        fail.append(f"שם עברי לא נתן slug זמני אלא {first}")
    if second != "latin-name":
        fail.append(f"ה־slug הזמני לא השתדרג, נשאר {second}")
    if seen != [("p-999001", "latin-name")]:
        fail.append(f"ההעברה לא דווחה כמו שצריך: {seen}")
    else:
        print("  וההעברה של האזכורים דווחה")

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
