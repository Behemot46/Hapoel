#!/usr/bin/env python3
"""הקצב של המשמרת: יום רגוע, סביב משחק, ומיד אחרי השריקה.

**התקלה, 17.10.2026.** בחלון המשחק האיסוף רץ פעם בשלוש שעות, ולכן
התוצאה יכלה לאחר עד שלוש שעות. נמדד על המשחק מול ב״ש: השריקה ב־19:15
UTC, האיסוף שלפניה ב־18:23 ולא מצא כלום, והבא ב־21:39. **האוהד קיבל את
התוצאה שעתיים ו־24 דקות אחרי שהמשחק נגמר.**

הבדיקה מריצה את הקטע האמיתי מתוך ``update-data.yml``, ולא עותק שלו, כי
עותק נפרד הוא בדיוק מה שנשבר בשקט. היא בונה לוח משחקים יחסית לשעה
הנוכחית ושואלת את הקטע מה הוא אומר.
"""

import datetime
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
YAML = ROOT / ".github" / "workflows" / "update-data.yml"


def snippet():
    """גוף ה־heredoc של collect_every, כפי שהוא בקובץ."""
    text = YAML.read_text(encoding="utf-8")
    m = re.search(r"collect_every\(\) \{\n\s*python - <<'PY'\n(.*?)\n\s*PY\n",
                  text, re.S)
    if not m:
        sys.exit("לא נמצא הקטע של collect_every ב־update-data.yml. "
                 "הבדיקה חייבת להיכשל ברעש כשהיא מאבדת את מה שהיא מודדת.")
    body = m.group(1)
    # ההזחה של ה־YAML יורדת, אחרת פייתון לא יריץ את זה
    pad = min(len(l) - len(l.lstrip()) for l in body.split("\n") if l.strip())
    return "\n".join(l[pad:] for l in body.split("\n"))


def ask(games):
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        (tmp / "app" / "data").mkdir(parents=True)
        (tmp / "app" / "data" / "games.json").write_text(
            json.dumps({"games": games}, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, "-c", snippet()], cwd=tmp,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"הקטע נפל: {r.stderr.strip()}")
        return r.stdout.strip()


def game(hours_from_now, **extra):
    when = (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=hours_from_now))
    return dict({"date": when.isoformat(), "home": "הפועל ירושלים",
                 "away": "יריבה"}, **extra)


def main():
    fail = []
    cases = [
        ("אין משחק בכלל", [], "quiet"),
        ("משחק בעוד שבוע", [game(24 * 7)], "quiet"),
        ("משחק בעוד שעתיים", [game(2)], "game"),
        ("בדיוק אחרי הקפיצה", [game(-0.5)], "game"),
        # **החלון החדש:** משחק כדורסל נגמר אחרי כשעתיים
        ("שעתיים אחרי הקפיצה, המשחק נגמר", [game(-2)], "ended"),
        ("שלוש שעות אחרי הקפיצה", [game(-3)], "ended"),
        ("חמש שעות אחרי, חוזרים לקצב של חלון המשחק", [game(-5)], "game"),
        ("יממה אחרי", [game(-24)], "quiet"),
        # משחק בלי שעה שמורה על 12:00 אסור שיפעיל שום דבר
        ("משחק בלי שעה", [game(-2, timeTbd=True)], "quiet"),
        # ושני משחקים: מי שזה עתה נגמר קובע
        ("אחד נגמר ואחד מתקרב", [game(-2), game(5)], "ended"),
    ]
    for label, games, want in cases:
        got = ask(games)
        ok = got == want
        if not ok:
            fail.append(f"{label}: {got} במקום {want}")
        print(f"  {'תקין' if ok else 'נפל!'} {label:<42} {got}")

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        return 1
    print(f"\n{len(cases)} מצבים נכונים, והקטע נקרא מהקובץ עצמו.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
