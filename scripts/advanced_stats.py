#!/usr/bin/env python3
"""מדדים מתקדמים מטפסי המשחק: החזקות, יעילות, ארבעת הגורמים, רבעים ושחקנים.

**למה זה קיים.** עמוד הסטטיסטיקה הבטיח עד 1.11.2026 ״יעילות התקפה והגנה
ל־100 מחזורים״ כמשהו שאי אפשר לחשב בכנות, כי ״ספירת מחזורים אין בטופס״.
זה נכון רק בחצי: ספירה מדויקת דורשת מהלך אחר מהלך, אבל **ההערכה המקובלת**
של מספר ההחזקות נבנית כולה משורת הסה״כ, וזו ההערכה שבה משתמשים
Basketball Reference, היורוליג וכל אתר ניתוח:

    החזקות = זריקות מהשדה + 0.44 × זריקות עונשין − ריבאונד התקפה + איבודים

ה־0.44 הוא אותו מקדם שכבר נמצא באפליקציה בנוסחת TS. כל השאר ספירה.

**מה עדיין אי אפשר, וזה לא משתנה כאן:** חמישיות, הפרש כשעל הפרקט מול
כשעל הספסל, וכל דבר שתלוי בשאלה מי היה על המגרש באיזה רגע. את זה רק מהלך
אחר מהלך יודע, ואין לנו אותו.

**משחקי הכנה לא נספרים**, בדיוק כמו בממוצעים (ראו player_stats.py).
"""

import datetime
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import player_stats as ps

OUT = "advanced.json"

# **המשקלות של דין אוליבר לארבעת הגורמים**, מתוך Basketball on Paper
# (2004): קליעה 40%, איבודים 25%, ריבאונד התקפה 20%, עונשין 15%. כאן הם
# משמשים לשאלה אחת בלבד, ״באיזה גורם המשחק הוכרע״, כדי שהפרש של שש
# נקודות אחוז בריבאונד לא ייחשב כמו שש נקודות אחוז בקליעה.
WEIGHTS = {"efg": 0.40, "tov": 0.25, "orb": 0.20, "ftr": 0.15}

# רבעים נספרים רק עד הרביעי. הארכה היא חמש דקות ולא עשר, וממוצע שמערבב
# אותה עם רבע רגיל משקר על שניהם.
QUARTERS = 4


def log(*a):
    print("[advanced]", *a, flush=True)


def comp_group(name):
    """ליגה, יורוקאפ או גביע, לפי שם התחרות בלוח."""
    name = name or ""
    if "יורוקאפ" in name:
        return "eurocup"
    if "גביע" in name:
        return "cup"
    return "league"


def pair(t, k):
    v = t.get(k) or [0, 0]
    return int(v[0] or 0), int(v[1] or 0)


def n(t, k):
    return int(t.get(k) or 0)


def totals_of(team):
    """שורת הסה״כ, ואם אין כזאת, סכום השחקנים והשורה הקבוצתית.

    נמדד ב־1.11.2026 על כל 12 המשחקים הרשמיים: הסכום שווה לשורת הסה״כ
    בנקודות, באיבודים ובריבאונדים, כולל הריבאונד והאיבוד הקבוצתיים. הגיבוי
    כאן הוא לטופס עתידי שיגיע בלי שורה כזאת.
    """
    tot = team.get("totals")
    if tot:
        return tot
    rows = list(team.get("players") or []) + [team.get("teamRow") or {}]
    out = {}
    for k in ("pts", "oreb", "dreb", "reb", "ast", "to", "stl", "blk", "pf"):
        out[k] = sum(n(r, k) for r in rows)
    for k in ("fg", "p2", "p3", "ft"):
        out[k] = [sum(pair(r, k)[0] for r in rows), sum(pair(r, k)[1] for r in rows)]
    return out


def possessions(t):
    """ההערכה המקובלת של מספר ההחזקות של קבוצה אחת."""
    fga = pair(t, "fg")[1]
    fta = pair(t, "ft")[1]
    return fga + 0.44 * fta - n(t, "oreb") + n(t, "to")


def factors(off, opp):
    """ארבעת הגורמים של ההתקפה של off, באחוזים, מול ההגנה של opp.

    * קליעה אפקטיבית: (קליעות + חצי שלשה) / זריקות
    * איבודים: איבודים / (זריקות + 0.44 × עונשין + איבודים)
    * ריבאונד התקפה: מתוך כל ההזדמנויות, כלומר שלנו ועוד ההגנה שלהם
    * עונשין: קליעות עונשין לכל זריקה מהשדה, כמו אצל אוליבר
    """
    fgm, fga = pair(off, "fg")
    p3m = pair(off, "p3")[0]
    ftm, fta = pair(off, "ft")
    tov = n(off, "to")
    orb, opp_drb = n(off, "oreb"), n(opp, "dreb")
    used = fga + 0.44 * fta + tov
    return {
        "efg": round(100 * (fgm + 0.5 * p3m) / fga, 1) if fga else None,
        "tov": round(100 * tov / used, 1) if used else None,
        "orb": round(100 * orb / (orb + opp_drb), 1) if (orb + opp_drb) else None,
        "ftr": round(100 * ftm / fga, 1) if fga else None,
    }


def shares(t):
    """מאיפה הנקודות: שתיים, שלוש ועונשין, באחוזים מהסך."""
    pts = n(t, "pts")
    if not pts:
        return None
    p2 = 2 * pair(t, "p2")[0]
    p3 = 3 * pair(t, "p3")[0]
    ft = pair(t, "ft")[0]
    return {"p2": round(100 * p2 / pts, 1), "p3": round(100 * p3 / pts, 1),
            "ft": round(100 * ft / pts, 1)}


def key_factor(four, won):
    """הגורם שבו ההפרש הממושקל הכי גדול לטובת התוצאה.

    בניצחון, הגורם שבו ניצחנו הכי הרבה; בהפסד, הגורם שבו הפסדנו הכי הרבה.
    באיבודים פחות זה טוב, ולכן ההפרש שם הפוך.
    """
    best, best_score = None, 0.0
    for f, w in WEIGHTS.items():
        a, b = four["us"].get(f), four["them"].get(f)
        if a is None or b is None:
            continue
        edge = (b - a) if f == "tov" else (a - b)
        score = w * edge * (1 if won else -1)
        if score > best_score:
            best, best_score = f, score
    return best


def team_minutes(team):
    """דקות המשחק עצמו, מסכום דקות השחקנים חלקי חמש."""
    secs = sum(ps.seconds(r.get("min")) for r in team.get("players") or [])
    return secs / 60 / 5


def game_record(gid, box, fixture):
    mine, theirs = ps.our_side(box), ps.opponent_of(box)
    if not mine or not theirs:
        return None
    us, them = totals_of(mine), totals_of(theirs)
    p_us, p_them = possessions(us), possessions(them)
    poss = (p_us + p_them) / 2
    if poss <= 0:
        return None
    minutes = team_minutes(mine) or 40.0
    pts_us, pts_them = n(us, "pts"), n(them, "pts")
    four = {"us": factors(us, them), "them": factors(them, us)}
    quarters = [[int(q[0] or 0), int(q[1] or 0)] for q in (box.get("quarters") or [])]
    return {
        "gameId": gid,
        "date": fixture.get("date"),
        "competition": fixture.get("competition"),
        "group": comp_group(fixture.get("competition")),
        "us": pts_us, "them": pts_them,
        "win": pts_us > pts_them,
        "poss": round(poss, 1),
        "minutes": round(minutes, 1),
        "pace": round(poss * 40 / minutes, 1),
        "ortg": round(100 * pts_us / poss, 1),
        "drtg": round(100 * pts_them / poss, 1),
        "net": round(100 * (pts_us - pts_them) / poss, 1),
        "four": four,
        "share": {"us": shares(us), "them": shares(them)},
        "quarters": quarters,
        "key": key_factor(four, pts_us > pts_them),
    }


def add_into(acc, t):
    for k in ("pts", "oreb", "dreb", "to"):
        acc[k] = acc.get(k, 0) + n(t, k)
    for k in ("fg", "p2", "p3", "ft"):
        cur = acc.get(k, [0, 0])
        a, b = pair(t, k)
        acc[k] = [cur[0] + a, cur[1] + b]
    return acc


def aggregate(records, boxes):
    """מדדי עונה מסכומים, לא ממוצע של אחוזים למשחק.

    ממוצע של אחוזים נותן למשחק של 60 החזקות את אותו משקל כמו למשחק של 80,
    וזה מעוות. כאן כל הזריקות וכל ההחזקות של העונה נכנסות לאותו סל.
    """
    if not records:
        return None
    us_acc, them_acc = {}, {}
    poss = minutes = 0.0
    for r in records:
        box = boxes[r["gameId"]]
        add_into(us_acc, totals_of(ps.our_side(box)))
        add_into(them_acc, totals_of(ps.opponent_of(box)))
        poss += r["poss"]
        minutes += r["minutes"]
    games = len(records)
    out = {
        "games": games,
        "wins": sum(1 for r in records if r["win"]),
        "poss": round(poss / games, 1),
        "pace": round(poss * 40 / minutes, 1) if minutes else None,
        "ortg": round(100 * us_acc["pts"] / poss, 1),
        "drtg": round(100 * them_acc["pts"] / poss, 1),
        "net": round(100 * (us_acc["pts"] - them_acc["pts"]) / poss, 1),
        "ppg": round(us_acc["pts"] / games, 1),
        "oppg": round(them_acc["pts"] / games, 1),
        "four": {"us": factors(us_acc, them_acc), "them": factors(them_acc, us_acc)},
        "share": {"us": shares(us_acc), "them": shares(them_acc)},
    }
    return out


def quarter_summary(records):
    """ההפרש הממוצע בכל רבע, וכמה רבעים כאלה ניצחנו."""
    sums = [0] * QUARTERS
    won = [0] * QUARTERS
    lost = [0] * QUARTERS
    counted = 0
    for r in records:
        q = r["quarters"]
        if len(q) < QUARTERS:
            continue
        counted += 1
        for i in range(QUARTERS):
            d = q[i][0] - q[i][1]
            sums[i] += d
            if d > 0:
                won[i] += 1
            elif d < 0:
                lost[i] += 1
    if not counted:
        return None
    return {"games": counted,
            "avg": [round(s / counted, 1) for s in sums],
            "won": won, "lost": lost}


def player_rates(boxes, fixtures):
    """שיעורי שחקן מהטפסים: שימוש, אסיסטים, ריבאונדים, איבודים ופלוס/מינוס.

    כל שיעור נבנה כמו ב־Basketball Reference: החלק של השחקן מתוך מה שקרה
    בזמן שהוא היה על המגרש, כשהזמן הזה מוערך מהדקות שלו. כדי שמשחק שבו
    שיחק חמש דקות לא ישקול כמו משחק של שלושים, המונה והמכנה נצברים לאורך
    כל המשחקים ורק אז מחולקים.

    * שימוש: כמה מההחזקות של הקבוצה הסתיימו אצלו (זריקה, עונשין או איבוד)
    * אסיסטים: כמה מהסלים של חבריו בזמן שהיה על המגרש הוא בישל
    * ריבאונדים: כמה מהריבאונדים הפנויים בזמן שהיה על המגרש הוא לקח
    * איבודים: כמה מהשימושים שלו נגמרו באיבוד
    """
    acc = {}
    for gid in sorted(boxes):
        if gid not in fixtures:
            continue
        box = boxes[gid]
        mine, theirs = ps.our_side(box), ps.opponent_of(box)
        if not mine or not theirs:
            continue
        tm, op = totals_of(mine), totals_of(theirs)
        tm_secs = sum(ps.seconds(r.get("min")) for r in mine.get("players") or [])
        if not tm_secs:
            continue
        tm_fgm, tm_fga = pair(tm, "fg")
        tm_fta = pair(tm, "ft")[1]
        tm_used = tm_fga + 0.44 * tm_fta + n(tm, "to")
        tm_reb = n(tm, "oreb") + n(tm, "dreb")
        op_reb = n(op, "oreb") + n(op, "dreb")
        for row in mine.get("players") or []:
            slug = row.get("slug")
            secs = ps.seconds(row.get("min"))
            if not slug or not secs:
                continue
            # החלק של השחקן מהזמן של חמישה שחקנים על המגרש
            share = secs / (tm_secs / 5)
            fgm, fga = pair(row, "fg")
            fta = pair(row, "ft")[1]
            used = fga + 0.44 * fta + n(row, "to")
            a = acc.setdefault(slug, {
                "slug": slug, "name": row.get("he") or row.get("name"),
                "games": 0, "secs": 0, "pm": 0,
                "used": 0.0, "usedDen": 0.0, "ast": 0, "astDen": 0.0,
                "reb": 0, "rebDen": 0.0, "orb": 0, "orbDen": 0.0,
                "drb": 0, "drbDen": 0.0, "tov": 0, "tovDen": 0.0,
            })
            a["games"] += 1
            a["secs"] += secs
            a["pm"] += n(row, "plusMinus")
            a["used"] += used
            a["usedDen"] += share * tm_used
            a["ast"] += n(row, "ast")
            a["astDen"] += share * tm_fgm - fgm
            a["reb"] += n(row, "reb")
            a["rebDen"] += share * (tm_reb + op_reb)
            a["orb"] += n(row, "oreb")
            a["orbDen"] += share * (n(tm, "oreb") + n(op, "dreb"))
            a["drb"] += n(row, "dreb")
            a["drbDen"] += share * (n(tm, "dreb") + n(op, "oreb"))
            a["tov"] += n(row, "to")
            a["tovDen"] += used

    def rate(x, d):
        return round(100 * x / d, 1) if d > 0 else None

    out = []
    for a in acc.values():
        mins = a["secs"] / 60
        out.append({
            "slug": a["slug"], "name": a["name"],
            "games": a["games"], "min": round(mins, 1),
            "mpg": round(mins / a["games"], 1) if a["games"] else 0,
            "usg": rate(a["used"], a["usedDen"]),
            "ast": rate(a["ast"], a["astDen"]),
            "reb": rate(a["reb"], a["rebDen"]),
            "orb": rate(a["orb"], a["orbDen"]),
            "drb": rate(a["drb"], a["drbDen"]),
            "tov": rate(a["tov"], a["tovDen"]),
            "pm": a["pm"],
            "pmPer40": round(a["pm"] * 40 / mins, 1) if mins else None,
        })
    out.sort(key=lambda r: -r["min"])
    return out


COMMENT = (
    "מדדים מתקדמים מטפסי המשחק: החזקות, יעילות התקפה והגנה, ארבעת הגורמים, "
    "רבעים ושיעורי שחקן. **הקובץ נכתב על ידי scripts/advanced_stats.py ואין "
    "לערוך אותו ביד.** מספר ההחזקות הוא ההערכה המקובלת משורת הסה״כ "
    "(זריקות + 0.44 × עונשין − ריבאונד התקפה + איבודים), ממוצע של שתי "
    "הקבוצות. רק משחקים רשמיים נספרים."
)


def build(boxes, fixtures):
    records = []
    for gid in sorted(boxes):
        if gid not in fixtures:
            continue
        rec = game_record(gid, boxes[gid], fixtures[gid])
        if rec:
            records.append(rec)
    records.sort(key=lambda r: r["date"] or "")
    split = {}
    for g in ("league", "eurocup", "cup"):
        sub = [r for r in records if r["group"] == g]
        if sub:
            split[g] = aggregate(sub, boxes)
    return {
        "team": aggregate(records, boxes),
        "split": split,
        "quarters": quarter_summary(records),
        "games": records,
        "players": player_rates(boxes, fixtures),
    }


def update_advanced():
    boxes = {}
    # הסדר כמו ב־player_stats: הידני נטען אחרון ולכן הוא מנצח
    for name in ("game-stats.json", "boxscores.json"):
        boxes.update((ps.load(name) or {}).get("games") or {})
    fixtures = ps.official_games((ps.load("games.json") or {}).get("games") or [])
    body = build(boxes, fixtures)
    if not body["games"]:
        raise RuntimeError("אין אף טופס רשמי לחשב ממנו")
    payload = {
        "_comment": COMMENT,
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        **body,
    }
    (ps.DATA / OUT).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    t = body["team"]
    log(f"נכתב {OUT}: {t['games']} משחקים, התקפה {t['ortg']}, הגנה {t['drtg']}, "
        f"קצב {t['pace']}, {len(body['players'])} שחקנים")
    return f"{t['games']} משחקים, הפרש {t['net']:+} ל־100 החזקות"


if __name__ == "__main__":
    update_advanced()
