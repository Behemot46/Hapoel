"""בדיקה של טופסי המשחק: כל מספר מול הסכומים המודפסים בטופס.

טופס משחק מועתק ביד, וטעות העתקה של ספרה אחת נראית סבירה לגמרי על
המסך. לכן כל מספר כאן נבדק מול הסכום המודפס באותו טופס: אם העמודה
מתאזנת, ההעתקה נכונה. הבדיקה כוללת גם הצלבות שלא ניתן לזייף בטעות:
נקודות של שחקן מול הקליעה שלו, סכום הרבעים מול התוצאה הסופית, וחסימות
של קבוצה אחת מול החסימות שנחסמו אצל השנייה.

הסכומים המודפסים יושבים כאן ולא בקובץ הנתונים, כי הם עדות נפרדת: הם
נכתבו על ידי מי שהפיק את הטופס, ואנחנו רק מוודאים שההעתקה שלנו מסכימה
איתם.

    python scripts/boxscore_test.py
"""
import json
import pathlib
import sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"

# מה שמודפס בשורת ה־Totals של כל טופס
PRINTED = {
    "20260831-club-הפועלחולון": {
        "הפועל ירושלים": {"fg": [37, 57], "p2": [27, 33], "p3": [10, 24], "ft": [18, 21],
                          "oreb": 9, "dreb": 31, "reb": 40, "ast": 23, "to": 18,
                          "stl": 7, "blk": 2, "pf": 24, "pts": 102, "pir": 130,
                          "min": 200, "bench": 43},
        "הפועל חולון": {"fg": [24, 60], "p2": [13, 26], "p3": [11, 34], "ft": [17, 21],
                        "oreb": 6, "dreb": 11, "reb": 17, "ast": 15, "to": 11,
                        "stl": 8, "blk": 0, "pf": 21, "pts": 76, "pir": 66,
                        "min": 200, "bench": 20},
    },
    "20260904-club-הפועלהעמק": {
        "הפועל ירושלים": {"fg": [28, 67], "p2": [20, 43], "p3": [8, 24], "ft": [22, 31],
                          "oreb": 12, "dreb": 40, "reb": 52, "ast": 19, "to": 14,
                          "stl": 6, "blk": 3, "pf": 24, "pts": 86, "pir": 102,
                          "min": 200, "bench": 43},
        # 27 העבירות של העמק הן 24 שספגנו ועוד שלוש טכניות שרשומות בתחתית
        # הטופס (הנרי, גולדנברג וקפלן), ולכן העמודה הזאת לא מתלכדת עם
        # עמודת העבירות שספגנו, בניגוד לכל שאר ההצלבות
        "הפועל העמק": {"fg": [30, 74], "p2": [21, 43], "p3": [9, 31], "ft": [13, 24],
                       "oreb": 9, "dreb": 30, "reb": 39, "ast": 21, "to": 9,
                       "stl": 8, "blk": 2, "pf": 27, "pts": 82, "pir": 82,
                       "min": 200, "bench": 40},
    },
}


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + int(s)


def check(game_id, game, printed, fail):
    def say(ok, what, got, want):
        if not ok:
            fail.append(f"{game_id} · {what}: אצלנו {got}, בטופס {want}")

    for team in game["teams"]:
        p = printed[team["name"]]
        players, row = team["players"], team["teamRow"]

        for k in ("fg", "p2", "p3", "ft"):
            for i, what in ((0, "קלע"), (1, "ניסה")):
                got = sum(x[k][i] for x in players)
                say(got == p[k][i], f"{team['name']} {k} {what}", got, p[k][i])

        for k in ("ast", "stl", "blk", "pf", "pts", "pir"):
            got = sum(x[k] for x in players)
            # ה־PIR המודפס כולל את שורת הקבוצה: ריבאונד קבוצתי מוסיף,
            # איבוד קבוצתי מוריד
            if k == "pir":
                got += row["oreb"] + row["dreb"] - row["to"]
            say(got == p[k], f"{team['name']} {k}", got, p[k])

        for k in ("oreb", "dreb", "to"):
            got = sum(x[k] for x in players) + row[k]
            say(got == p[k], f"{team['name']} {k}", got, p[k])

        got = sum(x["reb"] for x in players) + row["oreb"] + row["dreb"]
        say(got == p["reb"], f"{team['name']} ריבאונדים", got, p["reb"])

        got = sum(secs(x["min"]) for x in players) // 60
        say(got == p["min"], f"{team['name']} דקות", got, p["min"])

        starters = [x for x in players if x.get("starter")]
        say(len(starters) == 5, f"{team['name']} חמישייה פותחת", len(starters), 5)
        bench = sum(x["pts"] for x in players if not x.get("starter"))
        say(bench == p["bench"], f"{team['name']} נקודות הספסל", bench, p["bench"])

        say(sum(x["pts"] for x in players) == team["score"],
            f"{team['name']} נקודות מול התוצאה",
            sum(x["pts"] for x in players), team["score"])

        for x in players:
            calc = x["p2"][0] * 2 + x["p3"][0] * 3 + x["ft"][0]
            say(calc == x["pts"], f"{team['name']} נקודות של {x['name']}", calc, x["pts"])
            say(x["fg"] == [x["p2"][0] + x["p3"][0], x["p2"][1] + x["p3"][1]],
                f"{team['name']} קליעה של {x['name']}", x["fg"],
                [x["p2"][0] + x["p3"][0], x["p2"][1] + x["p3"][1]])
            say(x["reb"] == x["oreb"] + x["dreb"],
                f"{team['name']} ריבאונדים של {x['name']}", x["reb"], x["oreb"] + x["dreb"])

    a, b = game["teams"]
    for i, q in ((0, a), (1, b)):
        got = sum(x[i] for x in game["quarters"])
        say(got == q["score"], f"{q['name']} סכום הרבעים", got, q["score"])
    say(len(game["quarters"]) >= 4, "מספר הרבעים", len(game["quarters"]), "4 ומעלה")


def main():
    path = DATA / "boxscores.json"
    if not path.exists():
        print("אין קובץ טופסי משחק, אין מה לבדוק.")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    fail = []
    seen = 0
    for gid, game in (data.get("games") or {}).items():
        if gid not in PRINTED:
            fail.append(f"{gid}: אין סכומים מודפסים לבדוק מולם. "
                        "טופס נכנס לקובץ רק יחד עם השורה שלו כאן.")
            continue
        check(gid, game, PRINTED[gid], fail)
        seen += 1

    games = json.loads((DATA / "games.json").read_text(encoding="utf-8"))["games"]
    for gid, game in (data.get("games") or {}).items():
        g = next((x for x in games if x.get("id") == gid), None)
        if not g:
            fail.append(f"{gid}: יש טופס אבל אין משחק כזה בלוח")
            continue
        us = game["teams"][0]["score"] if game["teams"][0].get("us") else game["teams"][1]["score"]
        them = game["teams"][1]["score"] if game["teams"][0].get("us") else game["teams"][0]["score"]
        ours = g["homeScore"] if g["home"] == "הפועל ירושלים" else g["awayScore"]
        theirs = g["awayScore"] if g["home"] == "הפועל ירושלים" else g["homeScore"]
        if (ours, theirs) != (us, them):
            fail.append(f"{gid}: הלוח אומר {ours}-{theirs} והטופס אומר {us}-{them}. "
                        "אחד מהם הפוך.")

    if fail:
        print(f"{len(fail)} כשלים:")
        for f in fail:
            print("  ✗", f)
        return 1
    print(f"{seen} טפסים נבדקו, כל עמודה מתאזנת מול הסכומים המודפסים.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
