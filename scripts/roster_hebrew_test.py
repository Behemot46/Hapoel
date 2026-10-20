#!/usr/bin/env python3
"""שם עברי לשחקן שאתר המועדון לא מציג, בלי להמציא תעתיק.

**המקרה, 20.10.2026.** לסגל נוסף יונתן קלר, גארד ישראלי יליד 2007
שנרשם ליורוקאפ. אתר המועדון לא מציג אותו, ולכן הוא הגיע בלי שם עברי
והופיע באפליקציה עברית באותיות לטיניות. בשם של ישראלי זה צורם במיוחד.

**ותעתיק שאני ממציא הוא בדיוק מה שאסור.** שם של אדם אמיתי נכתב רק כפי
שמקור פרסם, ולכן המקור כאן הוא העמוד של הליגה, שכתוב בעברית ושאנחנו
כבר יודעים לקרוא אותו.

הזיווג דורש יותר ממספר חולצה, והמבחן הזה בודק בדיוק מה הוא דורש.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

# הסגל כפי שהוא מגיע מהמיזוג, עם שחקן אחד בלי שם עברי
def squad():
    return [
        {"name": "Yovel Zoosman", "nameHe": "יובל זוסמן", "number": 50,
         "born": 1998},
        {"name": "Yonatan Keller", "number": 30, "born": 2007,
         "position": "גארד"},
    ]


LEAGUE = [
    {"name": "יובל זוסמן", "number": 50, "born": 1998},
    {"name": "יונתן קלר", "number": 30, "born": 2007},
]


def main():
    fail = []

    players = squad()
    n = ud.fill_he_from_league(players, LEAGUE)
    got = players[1].get("nameHe")
    print(f"מהעמוד של הליגה: {got!r} ({n} הושלמו)")
    if got != "יונתן קלר":
        fail.append(f"השם לא הושלם: {got!r}")

    # **מספר חולצה לבדו אינו מספיק.** שנת לידה שלא מסכימה פוסלת.
    players = squad()
    ud.fill_he_from_league(players, [{"name": "מישהו אחר", "number": 30,
                                      "born": 1995}])
    print(f"שנת לידה שלא מסכימה: {players[1].get('nameHe')!r}")
    if players[1].get("nameHe"):
        fail.append("שם נכנס למרות ששנת הלידה לא הסכימה")

    # שני שחקנים על אותו מספר בעמוד של הליגה: לא יודעים מי, ולא בוחרים
    players = squad()
    ud.fill_he_from_league(players, [{"name": "ראשון", "number": 30},
                                     {"name": "שני", "number": 30}])
    print(f"שני מועמדים לאותו מספר: {players[1].get('nameHe')!r}")
    if players[1].get("nameHe"):
        fail.append("נבחר שם כששני שחקנים חולקים מספר")

    # שם שכבר שייך לשחקן אחר בסגל לא מועתק לשני
    players = squad()
    ud.fill_he_from_league(players, [{"name": "יובל זוסמן", "number": 30}])
    print(f"שם שכבר תפוס: {players[1].get('nameHe')!r}")
    if players[1].get("nameHe"):
        fail.append("שם של שחקן אחר הועתק")

    # ושם לטיני בעמוד של הליגה אינו שם עברי
    players = squad()
    ud.fill_he_from_league(players, [{"name": "Yonatan Keller", "number": 30}])
    print(f"שם לטיני בעמוד הליגה: {players[1].get('nameHe')!r}")
    if players[1].get("nameHe"):
        fail.append("שם לטיני נכנס כשם עברי")

    # ומי שכבר יש לו שם לא נוגעים בו
    players = squad()
    ud.fill_he_from_league(players, [{"name": "שם אחר לגמרי", "number": 50,
                                      "born": 1998}])
    print(f"מי שכבר יש לו שם: {players[0]['nameHe']!r}")
    if players[0]["nameHe"] != "יובל זוסמן":
        fail.append("שם קיים נדרס")

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        return 1
    print("\nשם עברי מגיע ממקור שפרסם אותו, ובכל ספק נשארים בשם הלועזי.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
