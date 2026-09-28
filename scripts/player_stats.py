#!/usr/bin/env python3
"""ממוצעי העונה ויומן משחקים לכל שחקן, מהטפסים שאספנו.

**למה זה קיים.** ב־28.9.2026 עמוד השחקן של קני לופטון אמר ״העונה טרם
החלה. הנתונים יופיעו כאן אחרי המשחק הראשון״, שלושה ימים אחרי שקלע 17
נקודות עם 10 ריבאונדים ו־6 אסיסטים מול בני הרצליה. גם עמוד הסטטיסטיקה
אמר את זה. הסיבה: שני העמודים נשענו על season-stats.json, שהוא ממוצעי
היורוקאפ בלבד, והעונה האירופית באמת נפתחת רק ב־29.9. אבל האוהד לא חושב
בחתך של תחרות, הוא יודע שהקבוצה שיחקה ארבעה משחקים רשמיים.

**וזו הבקשה הראשונה במשוב, 14 מתוך 23**, גדולה יותר משירי היציע, מהחדשות
ומהתוצאה החיה. הנתונים כבר בבית מאז שנבנה game_stats.py, והם פשוט לא
היו מחוברים לשום מקום שהאוהד רואה.

**משחקי הכנה לא נספרים.** הם לא חלק מהעונה, ואתר המועדון אפילו לא מפרסם
להם תוצאה. הטפסים שלהם נשארים בעמוד המשחק, ופשוט לא נכנסים לממוצע.
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
OUT = "player-season.json"
FRIENDLY = "משחק הכנה"

# מה שמצטבר כמספר, ומה שמצטבר כזוג של קלע מתוך זרק
SUMS = ("pts", "reb", "oreb", "dreb", "ast", "to", "stl", "blk", "pf", "pir")
PAIRS = ("fg", "p2", "p3", "ft")


def log(*a):
    print("[season]", *a, flush=True)


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def seconds(value):
    """״19:55״, ״24״ או ריק, אל שניות.

    שלושת המקורות כותבים דקות אחרת: הטופס הידני דקות ושניות, אתר הליגה
    יחידות שלמות, והפיד האירופי שניות שאנחנו כבר ממירים. חישוב שמניח
    צורה אחת נשבר בשקט על האחרות, וזה בדיוק מה שקרה בשורת הסה״כ.
    """
    parts = str(value or "").strip().split(":")
    try:
        m = int(parts[0])
    except (ValueError, IndexError):
        return 0
    if len(parts) < 2:
        return m * 60
    try:
        return m * 60 + int(parts[1])
    except ValueError:
        return m * 60


def mmss(total):
    total = int(round(total))
    return f"{total // 60}:{total % 60:02d}"


def official_games(games):
    """המשחקים הרשמיים שנגמרו, לפי מזהה."""
    out = {}
    for g in games:
        if g.get("competition") == FRIENDLY or g.get("homeScore") is None:
            continue
        out[g["id"]] = g
    return out


def our_side(box):
    for team in box.get("teams") or []:
        if team.get("us"):
            return team
    return None


def opponent_of(box):
    for team in box.get("teams") or []:
        if not team.get("us"):
            return team
    return None


def collect(boxes, fixtures):
    """{slug: רשומת שחקן} עם סכומים, ממוצעים ויומן משחקים."""
    people = {}
    counted = []
    for gid in sorted(boxes):
        if gid not in fixtures:
            continue
        box = boxes[gid]
        mine, theirs = our_side(box), opponent_of(box)
        if not mine:
            continue
        fixture = fixtures[gid]
        counted.append(gid)
        us_score = mine.get("score")
        them_score = theirs.get("score") if theirs else None
        for row in mine.get("players") or []:
            slug = row.get("slug")
            if not slug:
                continue
            rec = people.setdefault(slug, {
                "slug": slug, "name": row.get("he") or row.get("name"),
                "games": 0, "seconds": 0,
                "totals": {k: 0 for k in SUMS}, "log": [],
            })
            for k in PAIRS:
                rec["totals"].setdefault(k, [0, 0])
            rec["games"] += 1
            rec["seconds"] += seconds(row.get("min"))
            for k in SUMS:
                rec["totals"][k] += int(row.get(k) or 0)
            for k in PAIRS:
                pair = row.get(k) or [0, 0]
                rec["totals"][k][0] += int(pair[0] or 0)
                rec["totals"][k][1] += int(pair[1] or 0)
            rec["log"].append({
                "gameId": gid,
                "date": fixture.get("date"),
                "competition": fixture.get("competition"),
                "opponent": (theirs or {}).get("name"),
                "us": us_score, "them": them_score,
                "win": (us_score is not None and them_score is not None
                        and us_score > them_score),
                "min": row.get("min"), "pts": row.get("pts"),
                "reb": row.get("reb"), "ast": row.get("ast"),
                "pir": row.get("pir"),
            })
    return people, counted


def finish(rec):
    """ממוצעים למשחק, מעוגלים למקום אחד, ואחוזי קליעה."""
    n = max(rec["games"], 1)
    avg = {k: round(rec["totals"][k] / n, 1) for k in SUMS}
    avg["min"] = mmss(rec["seconds"] / n)
    for k in PAIRS:
        made, att = rec["totals"][k]
        # אחוז נכתב רק כשבאמת זרקו. אפס מתוך אפס הוא לא אפס אחוז, הוא
        # פשוט לא קרה, ו־0% על שחקן שלא זרק שלוש הוא שקר קטן שנראה רע.
        avg[k + "Pct"] = round(100 * made / att) if att else None
        avg[k] = [made, att]
    # **שני מדדים מתקדמים שאפשר לחשב בכנות מטופס משחק.** עמוד
    # הסטטיסטיקה הבטיח ״בדרך״ מדדים שדורשים נתוני מחזורים שאין לנו, אבל
    # שניים מהם לא דורשים כלום מעבר למה שכבר יש:
    #
    #   * **eFG%** נותן לשלשה את המשקל שלה. 4 מתוך 10 משלוש שוות יותר
    #     מ־4 מתוך 10 משתיים, ואחוז קליעה רגיל מטשטש את זה.
    #   * **TS%** מכניס לתמונה גם את קו העונשין, וזה המדד שהכי קרוב
    #     לשאלה ״כמה נקודות הוא מפיק מכל זריקה שהוא לוקח״.
    #
    # ה־0.44 בנוסחת TS הוא מקדם מקובל להערכת כמה ניסיונות קליעה שווה
    # זריקת עונשין, כי לא כל עונשין מסיים התקפה. זו הערכה, וכתוב באפליקציה
    # שזו הערכה.
    fga = rec["totals"]["fg"][1]
    fta = rec["totals"]["ft"][1]
    made3 = rec["totals"]["p3"][0]
    fgm = rec["totals"]["fg"][0]
    pts = rec["totals"]["pts"]
    avg["efg"] = round(100 * (fgm + 0.5 * made3) / fga, 1) if fga else None
    shots = fga + 0.44 * fta
    avg["ts"] = round(100 * pts / (2 * shots), 1) if shots else None

    rec["avg"] = avg
    rec["log"].sort(key=lambda x: x["date"] or "", reverse=True)
    return rec


COMMENT = (
    "ממוצעי העונה ויומן המשחקים לכל שחקן, מחושבים מטפסי המשחק שנאספו. "
    "**הקובץ נכתב על ידי scripts/player_stats.py ואין לערוך אותו ביד.** "
    "רק משחקים רשמיים נספרים: משחקי הכנה נשארים בעמוד המשחק שלהם ולא "
    "נכנסים לממוצע, כי הם לא חלק מהעונה. אחוז קליעה נכתב רק כשבאמת זרקו."
)


def update_player_season():
    boxes = {}
    # הסדר הוא ההלכה: הידני נטען אחרון ולכן הוא מנצח, בדיוק כמו באפליקציה
    for name in ("game-stats.json", "boxscores.json"):
        boxes.update((load(name) or {}).get("games") or {})
    fixtures = official_games((load("games.json") or {}).get("games") or [])
    people, counted = collect(boxes, fixtures)
    if not people:
        raise RuntimeError("אין אף שורת שחקן בטפסים הרשמיים")

    players = [finish(rec) for rec in people.values()]
    players.sort(key=lambda r: -r["avg"]["pts"])
    payload = {
        "_comment": COMMENT,
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "games": len(counted),
        "gameIds": counted,
        "players": players,
    }
    (DATA / OUT).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"נכתב {OUT}: {len(players)} שחקנים מתוך {len(counted)} משחקים רשמיים")
    return f"{len(players)} שחקנים מתוך {len(counted)} משחקים"


if __name__ == "__main__":
    update_player_season()
