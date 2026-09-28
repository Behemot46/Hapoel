#!/usr/bin/env python3
"""הממוצעים חייבים לצאת מהטפסים, ולא להיות מספר שנראה סביר.

הבדיקה כאן היא לא על נתוני דמה: היא מחשבת מחדש מהטפסים האמיתיים
שבמאגר, ומשווה לקובץ שנכתב. אם מישהו יזיז שורה, ישנה עיגול או יספור
משחק הכנה בטעות, ההשוואה תיפול.

**ומשחקי הכנה הם הסכנה האמיתית כאן.** שלושת הטפסים הידניים הם משחקי
הכנה, והם יושבים באותה תיקייה ובאותה סכמה כמו הרשמיים. שורה אחת שתספור
אותם תנפח לכל שחקן את הממוצע בלי להשמיע שום רעש.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import player_stats as ps


def main():
    fail = []
    out = ps.load(ps.OUT)
    if not out:
        print("אין קובץ. הרץ קודם python scripts/player_stats.py")
        sys.exit(1)

    boxes = {}
    for name in ("game-stats.json", "boxscores.json"):
        boxes.update((ps.load(name) or {}).get("games") or {})
    fixtures = ps.official_games((ps.load("games.json") or {}).get("games") or [])

    print(f"{len(boxes)} טפסים במאגר, מהם {out['games']} רשמיים ונספרים.")

    # 1. משחקי הכנה לא נספרים, וזה נבדק בשם ולא באמונה
    friendlies = [gid for gid in boxes if gid not in fixtures]
    print("\nטפסים שלא נספרים, וצריך שכך יהיה:")
    for gid in friendlies:
        print("  ", gid)
    for gid in out["gameIds"]:
        if gid in friendlies:
            fail.append(f"{gid} נספר למרות שאינו משחק רשמי")
    if not friendlies:
        fail.append("לא נמצא אף משחק הכנה, כלומר הבדיקה הזאת לא בדקה כלום")

    # 2. הסכומים של כל שחקן, מחושבים מחדש מהטפסים
    print("\nכל שחקן, מחושב מחדש מהשורות:")
    for rec in out["players"]:
        rows = []
        for gid in out["gameIds"]:
            team = ps.our_side(boxes[gid]) or {}
            for row in team.get("players") or []:
                if row.get("slug") == rec["slug"]:
                    rows.append(row)
        if len(rows) != rec["games"]:
            fail.append(f"{rec['name']}: {rec['games']} משחקים בקובץ, "
                        f"{len(rows)} שורות בטפסים")
            continue
        bad = []
        for key in ps.SUMS:
            want = sum(int(r.get(key) or 0) for r in rows)
            if rec["totals"][key] != want:
                bad.append(f"{key} {rec['totals'][key]} מול {want}")
            avg = round(want / len(rows), 1)
            if rec["avg"][key] != avg:
                bad.append(f"ממוצע {key} {rec['avg'][key]} מול {avg}")
        for key in ps.PAIRS:
            for i in (0, 1):
                want = sum(int((r.get(key) or [0, 0])[i] or 0) for r in rows)
                if rec["totals"][key][i] != want:
                    bad.append(f"{key}[{i}] {rec['totals'][key][i]} מול {want}")
        secs = sum(ps.seconds(r.get("min")) for r in rows)
        if rec["avg"]["min"] != ps.mmss(secs / len(rows)):
            bad.append(f"דקות {rec['avg']['min']} מול {ps.mmss(secs / len(rows))}")
        mark = "תקין" if not bad else "נשבר"
        print(f"  {mark}  {rec['name'][:20]:<20} {rec['games']} מש׳ · "
              f"{rec['avg']['pts']} נק · {rec['avg']['reb']} ריב · {rec['avg']['ast']} אס")
        for b in bad:
            print("        " + b)
        fail += [f"{rec['name']}: {b}" for b in bad]

    # 3. אחוז שלא נזרק אינו אפס אחוז
    print("\nאחוזי קליעה בלי זריקות:")
    holes = [(r["name"], k) for r in out["players"] for k in ps.PAIRS
             if r["totals"][k][1] == 0 and r["avg"][k + "Pct"] is not None]
    for name, k in holes:
        fail.append(f"{name}: {k} בלי זריקות אבל עם אחוז")
    print(f"  {len(holes)} מקרים של אחוז על אפס זריקות" if holes
          else "  אין אחוז על אפס זריקות")

    # 4. יומן המשחקים מסודר מהחדש לישן, וכל רשומה מצביעה על משחק אמיתי
    print("\nיומן המשחקים:")
    for rec in out["players"][:1]:
        for e in rec["log"]:
            print(f"  {e['date'][:10]} מול {e['opponent'][:22]:<22} "
                  f"{e['us']}-{e['them']} · {e['pts']} נק · {e['min']} דק")
    for rec in out["players"]:
        dates = [e["date"] for e in rec["log"]]
        if dates != sorted(dates, reverse=True):
            fail.append(f"{rec['name']}: היומן אינו מהחדש לישן")
        for e in rec["log"]:
            if e["gameId"] not in fixtures:
                fail.append(f"{rec['name']}: ביומן משחק שאינו בלוח, {e['gameId']}")

    if fail:
        print(f"\nנשברו {len(fail)}:")
        for f in fail:
            print("   " + f)
        sys.exit(1)
    print("\nכל ממוצע יוצא מהשורות, ומשחקי ההכנה נשארו בחוץ.")


if __name__ == "__main__":
    main()
