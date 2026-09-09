#!/usr/bin/env python3
"""הקצבים של האיסוף, של הפולר ושל השומר חייבים להסכים זה עם זה.

שלושת הקבצים האלה נכתבים בנפרד, וכבר פעמיים קרה שמספר בקובץ אחד ביטל
בשקט את הכוונה של מספר בקובץ אחר:

1. חלון ההתעוררות של הפולר היה 20 דקות, בזמן שהאיסוף דקר אותו פעם בשעה.
   ב־8.9.2026 שתי הדקירות, ב־13:43 וב־14:43, נפלו מחוץ לחלון, והמשחק
   הראשון של העונה עבר בלי אף דגימה חיה. שום ריצה לא נכשלה.
2. הלולאה דחפה כל 20 דקות, וורסל עצרה את הפרסום ל־24 שעות אחרי 148
   דחיפות ביממה. האתר קפא על גרסה ישנה בדיוק בגלל ניסיון לרענן אותו יותר.

שני הכשלים האלה הם חשבון, ולכן אפשר לבדוק אותם. הבדיקה קוראת את המספרים
מהקבצים עצמם, לא מעותק שלהם, כדי שמי שישנה מספר אחד יראה מיד את מי הוא
שבר.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILURES = []


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def grab(text, pattern, name, where):
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        sys.exit(f"לא נמצא {name} ב־{where}. הבדיקה הזאת חייבת להיכשל "
                 f"ברעש כשהיא מאבדת את מה שהיא מודדת.")
    return [int(g) for g in m.groups() if g is not None]


def check(ok, message):
    print(("  תקין:  " if ok else "  נשבר: ") + message)
    if not ok:
        FAILURES.append(message)


live_yml = read(".github/workflows/live.yml")
data_yml = read(".github/workflows/update-data.yml")
dog_yml = read(".github/workflows/watchdog.yml")
live_py = read("scripts/update_live.py")

# הפולר: כל כמה זמן הוא דוגם, וכמה זמן הוא מחזיק
poll_every = grab(live_yml, r"^          EVERY=(\d+)$",
                  "EVERY", "live.yml")[0] // 60
poll_minutes = grab(live_yml, r"DEADLINE=\$\(\( \$\(date \+%s\) \+ (\d+) \* 60 \)\)",
                    "DEADLINE", "live.yml")[0]

# הפולר: מתי הוא מחשיב משחק כ״עכשיו״
before = grab(live_py, r"^BEFORE = datetime\.timedelta\(minutes=(\d+)\)",
              "BEFORE", "update_live.py")[0]
after_h = grab(live_py, r"^AFTER = datetime\.timedelta\(hours=(\d+)\)",
               "AFTER", "update_live.py")[0]
stamp = grab(live_py, r"^STAMP_EVERY = datetime\.timedelta\(minutes=(\d+)\)",
             "STAMP_EVERY", "update_live.py")[0]

# האיסוף: כל כמה זמן הוא אוסף, כל כמה זמן הוא דוקר, וכל כמה זמן דופק
collect = grab(data_yml, r"^          EVERY=\$\(\( (\d+) \* 3600 \)\)",
               "EVERY", "update-data.yml")[0] * 60
poke = grab(data_yml, r"^          POKE_EVERY=\$\(\( (\d+) \* 60 \)\)",
            "POKE_EVERY", "update-data.yml")[0]
heartbeat = grab(data_yml, r"^          HEARTBEAT=\$\(\( (\d+) \* 3600 \)\)",
                 "HEARTBEAT", "update-data.yml")[0] * 60
soon_h, soon_m = grab(
    data_yml, r"SOON = datetime\.timedelta\(hours=(\d+), minutes=(\d+)\)",
    "SOON", "update-data.yml")
soon = soon_h * 60 + soon_m

# השומר: מאיזה גיל הוא מחליט שהאיסוף מת
limit = grab(dog_yml, r"^          LIMIT_HOURS = (\d+)\.\d+$",
             "LIMIT_HOURS", "watchdog.yml")[0] * 60

print("מה שנקרא מהקבצים:")
print(f"  פולר: דגימה כל {poll_every} דק׳, מחזיק {poll_minutes} דק׳, "
      f"חלון {before} דק׳ לפני ועד {after_h} שע׳ אחרי, חותמת כל {stamp} דק׳")
print(f"  איסוף: אוסף כל {collect // 60} שע׳, דוקר כל {poke} דק׳, "
      f"דופק כל {heartbeat // 60} שע׳, מחפש משחק עד {soon} דק׳ קדימה")
print(f"  שומר: ישן מדי מעל {limit // 60} שע׳")

print("\nכיסוי פתיחת המשחק:")
# כדי שהפולר יעבוד ברגע הקפיצה, חייבת ליפול דקירה בתוך [קפיצה מינוס
# BEFORE, קפיצה]. דקירות מרוחקות POKE_EVERY זו מזו, אז זה מתקיים רק אם
# POKE_EVERY לא גדול מ־BEFORE. זה הכשל של 8.9 בדיוק.
check(poke <= before,
      f"דקירה כל {poke} דק׳ נופלת בתוך חלון של {before} דק׳ לפני הקפיצה")
# ודקירה יכולה לקרות רק אם האיסוף בכלל מחשיב את המשחק כמתקרב
check(soon >= before,
      f"האיסוף מחפש משחק {soon} דק׳ קדימה, לפחות כמו חלון הפולר ({before})")
check(poll_minutes >= after_h * 60,
      f"הפולר מחזיק {poll_minutes} דק׳, מכסה את החלון של {after_h * 60} דק׳")

print("\nהשומר מול הדופק:")
# לולאה בריאה שקטה כשאין חדשות. אם השומר קורא לשקט הזה ״מת״, הוא יזמן
# איסוף מיותר בכל סיבוב.
check(limit > heartbeat,
      f"השומר מחכה {limit // 60} שע׳, יותר מהדופק של {heartbeat // 60} שע׳")
check(heartbeat >= collect,
      f"הדופק ({heartbeat // 60} שע׳) לא צפוף מהאיסוף ({collect // 60} שע׳)")

print("\nתקציב הדיפלויים של ורסל, 100 ביום:")
# כל דחיפה ל־main היא דיפלוי. gh-pages לא נספר, ורסל מגישה את main.
from_collect = (24 * 60) // collect
from_poller = poll_minutes // poll_every
worst = from_collect + from_poller
print(f"  איסוף: לכל היותר {from_collect} ביום")
print(f"  פולר במשחק: לכל היותר {from_poller}")
print(f"  יום משחק במקרה הגרוע: {worst}")
check(worst <= 80,
      f"{worst} ביום משחק, עם מרווח מתחת ל־100")
# שני משחקים ביום קורים, למשל בטורניר הכנה
check(from_collect + 2 * from_poller <= 100,
      f"{from_collect + 2 * from_poller} גם ביום עם שני משחקים")

if FAILURES:
    print(f"\nנשברו {len(FAILURES)} הסכמות בין הקבצים.")
    sys.exit(1)
print("\nהקצבים מסכימים, ותקציב הדיפלויים סוגר.")
