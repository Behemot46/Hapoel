"""בדיקה של המדדים המתקדמים: החזקות, יעילות, ארבעת הגורמים, רבעים ושחקנים.

המספרים כאן חושבו ביד מהטופס של המשחק בלה מאן ב־28.10.2026 (90-83 לנו),
ולא נקראים מהקובץ החי, כדי שהבדיקה לא תזוז כשהעונה מתקדמת.

    python scripts/advanced_stats_test.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import advanced_stats as adv


def team(us, pts, fg, p3, ft, oreb, dreb, to, players=None, totals=True):
    t = {"us": us, "score": pts, "players": players or [], "teamRow": {}}
    if totals:
        t["totals"] = {"pts": pts, "fg": fg, "p3": p3, "p2": [fg[0] - p3[0], fg[1] - p3[1]],
                       "ft": ft, "oreb": oreb, "dreb": dreb, "reb": oreb + dreb, "to": to}
    return t


# הטופס של לה מאן, שורות הסה״כ בלבד
LEMANS = {
    "quarters": [[21, 19], [27, 21], [17, 27], [25, 16]],
    "teams": [
        team(False, 83, [29, 70], [10, 30], [15, 21], 16, 22, 17),
        team(True, 90, [34, 65], [7, 20], [15, 20], 11, 24, 13),
    ],
}
FIX = {"date": "2026-10-28T19:00:00Z", "competition": "יורוקאפ"}


def close(a, b, tol=0.05):
    return a is not None and abs(a - b) <= tol


def main():
    fail = []
    rec = adv.game_record("L", LEMANS, FIX)

    # **החזקות.** 65 + 0.44×20 − 11 + 13 = 75.8 לנו, 70 + 0.44×21 − 16 + 17
    # = 80.24 להם, והמשחק הוא הממוצע: 78.02
    print("לה מאן ב־28.10, ביד מול הקוד:")
    checks = [
        ("החזקות", rec["poss"], 78.0),
        ("התקפה ל־100", rec["ortg"], 115.4),
        ("הגנה ל־100", rec["drtg"], 106.4),
        ("הפרש ל־100", rec["net"], 9.0),
        ("קליעה אפקטיבית שלנו", rec["four"]["us"]["efg"], 57.7),
        ("קליעה אפקטיבית שלהם", rec["four"]["them"]["efg"], 48.6),
        ("איבודים שלנו", rec["four"]["us"]["tov"], 15.0),
        ("איבודים שלהם", rec["four"]["them"]["tov"], 17.7),
        ("ריבאונד התקפה שלנו", rec["four"]["us"]["orb"], 33.3),
        ("ריבאונד התקפה שלהם", rec["four"]["them"]["orb"], 40.0),
        ("עונשין לזריקה שלנו", rec["four"]["us"]["ftr"], 23.1),
        ("עונשין לזריקה שלהם", rec["four"]["them"]["ftr"], 21.4),
    ]
    for label, got, want in checks:
        print(f"   {label}: {got}")
        if not close(got, want):
            fail.append(f"{label}: {got}, אמור להיות {want}")

    # הקליעה הכריעה: 9.1 נקודות אחוז × 0.4 גובר על כל השאר
    if rec["key"] != "efg":
        fail.append(f"הגורם המכריע בלה מאן: {rec['key']}, אמור להיות efg")

    # **ובהפסד, הגורם שבו הפסדנו הכי הרבה.** אותו טופס, רק שהם איבדו
    # מעט ואנחנו הרבה, והתוצאה הפוכה
    loss = {
        "quarters": [],
        "teams": [
            team(False, 80, [30, 64], [6, 20], [14, 18], 9, 25, 6),
            team(True, 72, [30, 64], [6, 20], [6, 9], 9, 25, 20),
        ],
    }
    lrec = adv.game_record("X", loss, FIX)
    print(f"   הפסד שבו איבדנו 20 כדורים מול 6: הגורם הוא {lrec['key']}")
    if lrec["key"] != "tov":
        fail.append(f"בהפסד על איבודים הגורם יצא {lrec['key']}, אמור להיות tov")

    # **מדדי עונה מסכומים, לא ממוצע של אחוזים.** משחק של 60 החזקות עם 60
    # נקודות (100) ומשחק של 90 החזקות עם 135 נקודות (150): הממוצע הנאיבי
    # הוא 125, והאמת היא 195 נקודות מתוך 150 החזקות, כלומר 130
    def flat(us_pts, poss):
        # זריקות בלבד, בלי ריבאונד, איבוד או עונשין, ולכן החזקות = זריקות
        return {"quarters": [], "teams": [
            team(True, us_pts, [poss // 2, poss], [0, 0], [0, 0], 0, 0, 0),
            team(False, 0, [0, poss], [0, 0], [0, 0], 0, 0, 0),
        ]}
    boxes = {"a": flat(60, 60), "b": flat(135, 90)}
    fixtures = {"a": FIX, "b": FIX}
    body = adv.build(boxes, fixtures)
    print(f"\nהתקפה לעונה משני משחקים לא שווים: {body['team']['ortg']}")
    if not close(body["team"]["ortg"], 130.0):
        fail.append(f"התקפה לעונה {body['team']['ortg']}, אמורה להיות 130 ולא 125")

    # **משחק הכנה לא נספר**, בדיוק כמו בממוצעים
    games = [{"id": "f", "competition": "משחק הכנה", "homeScore": 80},
             {"id": "a", "competition": "יורוקאפ", "homeScore": 60,
              "date": "2026-10-01T19:00:00Z"}]
    official = adv.ps.official_games(games)
    body2 = adv.build({"f": flat(80, 70), "a": flat(60, 60)}, official)
    ids = [g["gameId"] for g in body2["games"]]
    print(f"משחקים שנספרו כשאחד מהם משחק הכנה: {ids}")
    if ids != ["a"]:
        fail.append(f"משחק הכנה נספר: {ids}")

    # **רבעים: רק עד הרביעי, ומשחק בלי ארבעה רבעים לא נכנס לממוצע.**
    q = adv.quarter_summary([
        {"quarters": [[20, 10], [15, 20], [25, 25], [20, 18], [10, 2]]},
        {"quarters": [[10, 20], [15, 10], [20, 30], [22, 20]]},
        {"quarters": [[30, 0]]},
    ])
    print(f"\nרבעים, עם הארכה ועם טופס חסר: {q}")
    if q["games"] != 2:
        fail.append(f"נספרו {q['games']} משחקים לרבעים, אמורים להיות 2")
    if q["avg"] != [0.0, 0.0, -5.0, 2.0]:
        fail.append(f"ממוצע הרבעים {q['avg']}, אמור להיות [0, 0, -5, 2]")
    if q["won"] != [1, 1, 0, 2] or q["lost"] != [1, 1, 1, 0]:
        fail.append(f"ניצחונות והפסדים ברבעים: {q['won']} / {q['lost']}")

    # **שורת סה״כ חסרה: סכום השחקנים והשורה הקבוצתית.**
    t = {"players": [{"pts": 10, "fg": [4, 8], "to": 1, "oreb": 2},
                     {"pts": 5, "fg": [2, 5], "to": 2, "oreb": 0}],
         "teamRow": {"to": 1, "oreb": 1}}
    s = adv.totals_of(t)
    print(f"סכום כשאין שורת סה״כ: {s['pts']} נק׳, {s['fg']}, {s['to']} איבודים, "
          f"{s['oreb']} ריבאונד התקפה")
    if (s["pts"], s["fg"], s["to"], s["oreb"]) != (15, [6, 13], 4, 3):
        fail.append(f"הסכום בלי שורת סה״כ שגוי: {s}")

    # **שימוש.** חמישה שחקנים, כל אחד 40 דקות, ולכן כל אחד ״רואה״ את כל
    # ההחזקות. לאחד 20 שימושים מתוך 80 של הקבוצה, כלומר 25%
    def p(slug, fga, to):
        return {"slug": slug, "name": slug, "min": "40:00", "fg": [fga // 2, fga],
                "ft": [0, 0], "to": to, "ast": 0, "reb": 0, "oreb": 0, "dreb": 0,
                "plusMinus": 4}
    five = [p("a", 18, 2), p("b", 15, 0), p("c", 15, 0), p("d", 15, 0), p("e", 15, 0)]
    box = {"quarters": [], "teams": [
        team(True, 80, [39, 78], [0, 0], [0, 0], 0, 0, 2, players=five),
        team(False, 70, [35, 80], [0, 0], [0, 0], 0, 0, 0),
    ]}
    rates = {r["slug"]: r for r in adv.player_rates({"g": box}, {"g": FIX})}
    print(f"\nשימוש של שחקן עם 20 מתוך 80: {rates['a']['usg']}%, "
          f"פלוס/מינוס ל־40: {rates['a']['pmPer40']}")
    if not close(rates["a"]["usg"], 25.0):
        fail.append(f"שימוש {rates['a']['usg']}, אמור להיות 25")
    if not close(rates["a"]["pmPer40"], 4.0):
        fail.append(f"פלוס/מינוס ל־40 {rates['a']['pmPer40']}, אמור להיות 4")
    # ושחקן שלא שיחק לא נכנס בכלל, ולא מקבל אפס
    box["teams"][0]["players"].append({"slug": "z", "name": "z", "min": "0"})
    rates = {r["slug"]: r for r in adv.player_rates({"g": box}, {"g": FIX})}
    if "z" in rates:
        fail.append("שחקן בלי דקות קיבל שורה")

    # **והחיווט, כי חישוב נכון שאף עמוד לא טוען הוא כלום.** המודול רץ
    # באיסוף אחרי הממוצעים, הקובץ נטען בגל השני, ו־analytics.js נטען לפני
    # app.js, כי בסדר ההפוך הציור הראשון היה יכול לרוץ לפני שהפונקציות
    # שלו קיימות. ו־sw.js חייב להכיר אותו, אחרת אוהד בלי רשת מקבל עמוד
    # שבור.
    root = pathlib.Path(__file__).resolve().parent.parent
    upd = (root / "scripts" / "update_data.py").read_text(encoding="utf-8")
    if upd.find('("advanced", advanced_stats.update_advanced)') < upd.find('("playerSeason"'):
        fail.append("advanced לא רץ באיסוף, או רץ לפני הממוצעים")
    app = (root / "app" / "js" / "app.js").read_text(encoding="utf-8")
    if '["advanced", "advanced.json", null]' not in app:
        fail.append("app.js לא טוען את advanced.json")
    html = (root / "app" / "index.html").read_text(encoding="utf-8")
    a, b = html.find('src="js/analytics.js"'), html.find('src="js/app.js"')
    if a < 0 or a > b:
        fail.append("analytics.js לא נטען, או נטען אחרי app.js")
    if '"js/analytics.js"' not in (root / "app" / "sw.js").read_text(encoding="utf-8"):
        fail.append("sw.js לא שומר את analytics.js במטמון")
    if 'js/analytics.js' not in (root / "scripts" / "build_standalone.py").read_text(encoding="utf-8"):
        fail.append("העותק להורדה לא כולל את analytics.js")

    if fail:
        print(f"\n{len(fail)} כשלים:")
        for f in fail:
            print("  ✗", f)
        return 1
    print("\nהמדדים המתקדמים תואמים את החישוב ביד.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
