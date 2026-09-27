#!/usr/bin/env python3
"""טופסי משחק מאתר הליגה, נאספים אוטומטית.

**למה זה קיים.** עד 27.9.2026 הסטטיסטיקה על משחק הייתה שלושה טפסים של
משחקי הכנה שהעתקתי ביד ל־boxscores.json, ולשלושת משחקי הגביע הרשמיים לא
היה כלום. אתר הליגה מפרסם טופס מלא לכל משחק רשמי, ומעמוד הקבוצה יש
קישור לכל אחד, אז אין שום סיבה שזה יהיה ידני.

**הקובץ הידני לא נגמר כאן ולא נדרס.** boxscores.json מוצהר כ״נערך ידנית
בלבד״, וכל מספר בו אומת מול הסכומים המודפסים בטופס הנייר. איסוף אוטומטי
שכותב לשם היה יכול למחוק נתון מאומת בלי שאף אחד ישים לב, ולכן מה שנאסף
נכתב לקובץ נפרד, game-stats.json, והאפליקציה מעדיפה את הידני כשיש שניים.

**ומה שנאסף מאמת את עצמו לפני שהוא נכתב.** בטופס של הליגה יש שורת
״סה״כ״ מודפסת, ויש עמודת נקודות לכל שחקן. שתיהן נבדקות: סכום השחקנים
ועוד השורה הקבוצתית חייב לצאת בדיוק שורת הסה״כ, והנקודות של כל שחקן
חייבות לצאת מהקליעות שלו. אם משהו לא מסתדר, הטופס נזרק ולא נכתב. עדיף
בלי טופס מאשר טופס עם מספרים שזזו בעמודה.
"""

import datetime
import json
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; "
                    "+https://github.com/Behemot46/Hapoel)"}
GAME_URL = "https://basket.co.il/game-zone.asp?GameId={}"
OUT = "game-stats.json"


def log(*a):
    print("[stats]", *a, flush=True)


# **הכותרת המדויקת של הטופס, ובלעדיה לא מפרסרים כלום.** ללוח הזה יש שלוש
# עמודות ״זרק/קלע״ ושתי עמודות ״של״ ושתי ״על״, כלומר אי אפשר לזהות עמודה
# לפי הכותרת שלה לבדה. במקום לנחש, הכותרת כולה מושווית לחתימה הזאת, ואם
# האתר ישנה את הלוח הפרסר ייפול בקול במקום להזיז מספרים בשקט.
HEADER = ["#", "שם שחקן", "חמ", "דק", "נק", "זרק/קלע", "%", "זרק/קלע", "%",
          "זרק/קלע", "%", "הג", "הת", "סהכ", "של", "על", "חט", "אב", "אס",
          "של", "על", "מדד", "+/-"]
COL = {"no": 0, "name": 1, "starter": 2, "min": 3, "pts": 4,
       "p2": 5, "p3": 7, "ft": 9, "dreb": 11, "oreb": 12, "reb": 13,
       "pf": 14, "pfOn": 15, "stl": 16, "to": 17, "ast": 18,
       "blk": 19, "blkOn": 20, "pir": 21, "plusMinus": 22}
TOTAL_ROW = "סה"
TEAM_ROW = "קבוצתי"


def cells(row):
    return [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]


def fetch_page(game_id):
    url = GAME_URL.format(game_id)
    log("GET", url)
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    # **הדף UTF-8 אבל לא מצהיר על זה.** נמדד ב־27.9.2026: בלי לקבוע קידוד
    # requests מנחשת latin-1 ומחזירה ג׳יבריש, וגם windows-1255 מחזיר
    # ג׳יבריש, אחר. שני סוגי הג׳יבריש יחד הם מה שמוכיח שהדף UTF-8.
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def _int(s):
    m = re.search(r"-?\d+", (s or "").replace(",", ""))
    return int(m.group()) if m else 0


def _pair(s):
    """״8/12״ אל [8, 12]. הסדר נשמר כמו שנכתב, וזה חשוב: מספרים בתוך תא
    בעמוד מימין לשמאל מתהפכים על המסך, ולכן האפליקציה עוטפת אותם."""
    m = re.search(r"(\d+)\s*/\s*(\d+)", s or "")
    return [int(m.group(1)), int(m.group(2))] if m else [0, 0]


def player_row(c):
    p = {
        "no": _int(c[COL["no"]]),
        "name": c[COL["name"]].strip(),
        "min": c[COL["min"]].strip(),
        "starter": "*" in c[COL["starter"]],
        "pts": _int(c[COL["pts"]]),
        "p2": _pair(c[COL["p2"]]),
        "p3": _pair(c[COL["p3"]]),
        "ft": _pair(c[COL["ft"]]),
        "dreb": _int(c[COL["dreb"]]),
        "oreb": _int(c[COL["oreb"]]),
        "reb": _int(c[COL["reb"]]),
        "pf": _int(c[COL["pf"]]),
        "stl": _int(c[COL["stl"]]),
        "to": _int(c[COL["to"]]),
        "ast": _int(c[COL["ast"]]),
        "blk": _int(c[COL["blk"]]),
        "pir": _int(c[COL["pir"]]),
        "plusMinus": _int(c[COL["plusMinus"]]),
    }
    # שדה ומכלול, כדי שהטופס ייראה כמו הידני: זריקות שדה הן שתיים ושלוש יחד
    p["fg"] = [p["p2"][0] + p["p3"][0], p["p2"][1] + p["p3"][1]]
    return p


def team_from_rows(rows):
    """טופס של קבוצה אחת, מתוך שורות התאים של הטבלה שלה.

    מחזירה dict עם name, coach, players, teamRow ו־totals, או מרימה
    חריגה. **הפונקציה טהורה בכוונה**, בלי רשת ובלי קבצים, כדי שהמבחן
    יוכל להריץ אותה על השורות האמיתיות מאתר הליגה.
    """
    title = rows[0][0] if rows and rows[0] else ""
    name = re.sub(r"\(.*?\)", "", title).strip()
    coach = ""
    m = re.search(r"מאמן:\s*([^)]+)", title)
    if m:
        coach = m.group(1).strip()

    head_at = next((i for i, r in enumerate(rows) if r[:2] == HEADER[:2]), None)
    if head_at is None:
        raise ValueError(f"אין שורת כותרת בטופס של {name!r}")
    if rows[head_at] != HEADER:
        raise ValueError(
            f"הכותרת בטופס של {name!r} אינה זו שהפרסר מכיר.\n"
            f"  מצפה ל: {HEADER}\n  קיבלתי:  {rows[head_at]}")

    players, team_row, totals = [], None, None
    for c in rows[head_at + 1:]:
        if len(c) != len(HEADER):
            continue
        label = c[COL["name"]].strip()
        if label.startswith(TOTAL_ROW):
            totals = player_row(c)
        elif label == TEAM_ROW:
            team_row = player_row(c)
        elif label:
            players.append(player_row(c))
    if totals is None:
        raise ValueError(f"אין שורת סה\"כ בטופס של {name!r}")
    return {"name": name, "coach": coach, "players": players,
            "teamRow": team_row, "totals": totals}


# הסכומים שנבדקים מול שורת הסה״כ המודפסת. מה שלא נבדק כאן פשוט לא נאסף.
SUMS = ("pts", "reb", "dreb", "oreb", "ast", "to", "stl", "blk", "pf")
PAIRS = ("p2", "p3", "ft", "fg")


def verify(team):
    """כל מה שלא מסתדר עם שורת הסה״כ המודפסת, כמחרוזות."""
    bad = []
    rows = list(team["players"]) + ([team["teamRow"]] if team["teamRow"] else [])
    for key in SUMS:
        got = sum(r[key] for r in rows)
        want = team["totals"][key]
        if got != want:
            bad.append(f"{key}: סכום השורות {got}, בסה\"כ {want}")
    for key in PAIRS:
        for i, what in ((0, "קלע"), (1, "זרק")):
            got = sum(r[key][i] for r in rows)
            want = team["totals"][key][i]
            if got != want:
                bad.append(f"{key} {what}: סכום השורות {got}, בסה\"כ {want}")
    # ונקודות של שחקן חייבות לצאת מהקליעות שלו
    for r in rows + [team["totals"]]:
        made = r["p2"][0] * 2 + r["p3"][0] * 3 + r["ft"][0]
        if made != r["pts"]:
            bad.append(f"{r['name']}: {r['pts']} נקודות, ומהקליעות יוצא {made}")
    return bad


def quarters_from_rows(rows):
    """[[us, them], ...] מטבלת ״תוצאת רבע״, לפי סדר הקבוצות בטבלה."""
    out = []
    nums = [[_int(x) for x in r[1:] if x.strip()] for r in rows[1:3]]
    if len(nums) == 2 and len(nums[0]) == len(nums[1]):
        out = [[a, b] for a, b in zip(nums[0], nums[1])]
    return out


def extra_from_rows(rows):
    """״נתונים נוספים״ אל הצורה של teamStats: label, us, them."""
    if len(rows) < 4:
        return []
    labels = rows[1][1:]
    first, second = rows[2][1:], rows[3][1:]
    out = []
    for i, label in enumerate(labels):
        if i < len(first) and i < len(second) and label.strip():
            out.append({"label": label.strip(), "us": first[i], "them": second[i]})
    return out


# מי אנחנו בשני הטפסים. ״הפועל ב״ש״ גם מכילה ״הפועל״, ולכן נדרשת גם
# ירושלים, ובית״ר לעולם אינה ״הפועל״.
def is_us(name):
    n = (name or "").replace("״", '"').replace("־", "-")
    return "הפועל" in n and ("ירושלים" in n or "י-ם" in n or 'י"ם' in n)


def _norm_name(s):
    """שם עברי להשוואה: בלי גרשיים, בלי מקפים ובלי רווחים כפולים.

    ה־geresh מגיע בשלוש צורות שונות בין המקורות (׳ ' ’), ואתר הליגה כותב
    ״קנת׳ לופטון ג׳וניור״ במקום ״קני לופטון ג׳וניור״ שבסגל שלנו. לכן ההשוואה
    היא על שם המשפחה, והמספר על הגב הוא מה שמכריע.
    """
    s = (s or "")
    for ch in "׳'’\"״":
        s = s.replace(ch, "")
    return re.sub(r"\s+", " ", s.replace("-", " ")).strip()


def link_our_players(team, roster):
    """מוסיף slug ו־he לשורות של השחקנים שלנו.

    **המפתח הוא המספר על הגב, לא השם.** המספר ייחודי בקבוצה והוא זהה בשני
    המקורות, בעוד שהשם נכתב אחרת: אתר הליגה כותב ״קנת׳ לופטון ג׳וניור״
    והסגל שלנו ״Kenny Lofton Jr״. אבל מספר לבדו יכול להטעות אם שחקן החליף
    מספר, ולכן נדרשת גם חפיפה של מילה אחת בשם. מי שלא עבר את שני התנאים
    נשאר בלי קישור, וזה נרשם בלוג: שורה בלי קישור היא חיסרון קטן, קישור
    לשחקן הלא נכון הוא שקר.
    """
    by_no = {}
    for p in roster:
        if p.get("number") is not None:
            by_no.setdefault(int(p["number"]), p)
    linked, skipped = 0, []
    for row in team["players"]:
        mate = by_no.get(row["no"])
        if not mate:
            skipped.append(f"{row['no']} {row['name']}, אין מספר כזה בסגל")
            continue
        theirs = set(_norm_name(row["name"]).split())
        ours = set(_norm_name(mate.get("nameHe") or "").split())
        if not (theirs & ours):
            skipped.append(f"{row['no']} {row['name']} מול {mate.get('nameHe')}, "
                           "מספר תואם אבל שום מילה בשם")
            continue
        row["slug"] = mate["slug"]
        row["he"] = mate.get("nameHe") or mate.get("name")
        linked += 1
    if skipped:
        for s in skipped:
            log("  לא קושר:", s)
    return linked


def build_game(soup, roster):
    """הטופס המלא של משחק אחד, בסכמה של boxscores.json."""
    tables = soup.find_all("table")
    forms, quarters, extra = [], [], []
    for tb in tables:
        rows = [cells(r) for r in tb.find_all("tr")]
        if not rows:
            continue
        flat = " ".join(rows[0])
        if any(r[:2] == HEADER[:2] for r in rows if len(r) >= 2):
            forms.append(rows)
        elif rows[0] and rows[0][0].strip() == "תוצאת רבע":
            quarters = rows
        elif rows[0] and rows[0][0].strip() == "נתונים נוספים":
            extra = rows
    if len(forms) != 2:
        raise ValueError(f"מצאתי {len(forms)} טפסים בעמוד, צריך שניים")

    teams = [team_from_rows(rows) for rows in forms]
    for t in teams:
        bad = verify(t)
        if bad:
            raise ValueError(f"הטופס של {t['name']} לא מסתדר עם עצמו: "
                             + "; ".join(bad))

    ours = [i for i, t in enumerate(teams) if is_us(t["name"])]
    if len(ours) != 1:
        raise ValueError(f"לא הצלחתי לזהות איזו קבוצה אנחנו מתוך "
                         f"{[t['name'] for t in teams]}")
    mine = ours[0]
    for i, t in enumerate(teams):
        t["us"] = (i == mine)
        t["score"] = t["totals"]["pts"]
    link_our_players(teams[mine], roster)

    q = quarters_from_rows(quarters) if quarters else []
    # בטבלת הרבעים הקבוצות מופיעות בסדר של העמוד. אם אנחנו השורה השנייה,
    # הזוגות מתהפכים כדי ש־us יהיה תמיד ראשון.
    if q and quarters and len(quarters) > 2 and not is_us(quarters[1][0]):
        q = [[b, a] for a, b in q]
    stats = extra_from_rows(extra) if extra else []
    if stats and extra and len(extra) > 2 and not is_us(extra[2][0]):
        stats = [{"label": s["label"], "us": s["them"], "them": s["us"]}
                 for s in stats]
    return {"quarters": q, "teams": teams, "teamStats": stats}


DATE_IN_ROW = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def game_ids(soup):
    """{תאריך ISO: מזהה המשחק באתר הליגה} מתוך עמוד הקבוצה.

    כל משחק בלוח מקושר ל־game-zone, גם כשעוד לא שוחק, וטקסט הקישור הוא
    התוצאה. **והתוצאה שם כתובה אורחת-מארחת**, בגלל כתיבה מימין לשמאל:
    ב־8.9 מכבי אשדוד אירחה והפסידה 77, והקישור אומר ״110-77״. אנחנו לא
    קוראים את המספרים האלה בכלל, התוצאה נלקחת מהטופס עצמו, אבל מי שיקרא
    אותם פעם צריך לדעת.
    """
    out = {}
    for a in soup.find_all("a", href=re.compile("game-zone")):
        gid = re.search(r"GameId=(\d+)", a["href"])
        row = a.find_parent("tr")
        if not gid or row is None:
            continue
        text = " ".join(cells(row))
        d = DATE_IN_ROW.search(text)
        if not d:
            continue
        out[f"{d.group(3)}-{d.group(2)}-{d.group(1)}"] = gid.group(1)
    return out


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


COMMENT = (
    "טופסי משחק שנאספים אוטומטית מאתר הליגה. **הקובץ הזה נכתב על ידי "
    "scripts/game_stats.py ואין לערוך אותו ביד.** מה שנערך ביד יושב "
    "ב־boxscores.json, והאפליקציה מעדיפה אותו כשקיימים שניים לאותו משחק, "
    "כי שם כל מספר אומת מול הסכומים המודפסים בטופס הנייר. כל טופס כאן "
    "אימת את עצמו לפני שנכתב: סכום השחקנים ועוד השורה הקבוצתית יוצא בדיוק "
    "שורת הסה\"כ המודפסת, והנקודות של כל שחקן יוצאות מהקליעות שלו. טופס "
    "שלא עמד בזה נזרק ולא נכתב."
)


def update_game_stats():
    """אוסף טופס לכל משחק רשמי שנגמר ואין לו עדיין אחד."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import update_data as ud

    games = (load("games.json") or {}).get("games") or []
    roster = (load("roster.json") or {}).get("players") or []
    have = load(OUT) or {}
    done = dict(have.get("games") or {})
    manual = set(((load("boxscores.json") or {}).get("games") or {}))

    link = ud.find_team_link()
    if not link:
        raise RuntimeError("no team page, cannot find game ids")
    ids = game_ids(BeautifulSoup(ud.fetch(link), "html.parser"))
    log(f"{len(ids)} משחקים מקושרים בעמוד הקבוצה")

    todo = []
    for g in games:
        day = g["date"][:10]
        if g.get("homeScore") is None or day not in ids:
            continue
        if g["id"] in done or g["id"] in manual:
            continue
        todo.append((g, ids[day]))
    if not todo:
        log("אין טופס חדש לאסוף")
        return f"{len(done)} טפסים, אין חדש"

    added, failed = 0, 0
    for g, gid in todo:
        try:
            built = build_game(fetch_page(gid), roster)
        except Exception as e:
            failed += 1
            log(f"  {g['id']}: {e}")
            continue
        built.update({
            "date": g["date"],
            "competition": g.get("competition") or "",
            "venue": g.get("venue") or "",
            "source": {"name": "אתר מנהלת ליגת העל בכדורסל",
                       "note": f"טופס המשחק הרשמי, מזהה {gid}"},
            # הצורה היא זו שהאפליקציה קוראת: name הוא המפרסם ו־title הכיתוב
            "links": [{"name": "מנהלת ליגת העל",
                       "title": "טופס המשחק המלא באתר הליגה",
                       "url": GAME_URL.format(gid)}],
            # **הסימון הזה הוא מה שמונע שקר על המסך.** כרטיס המקורות
            # באפליקציה כתב ״המספרים כאן הועתקו ביד״, וזה נכון רק לטפסים
            # של הקובץ הידני.
            "collected": True,
        })
        done[g["id"]] = built
        added += 1
        score = " · ".join(f"{t['name']} {t['score']}" for t in built["teams"])
        log(f"  נאסף: {g['id']} · {score}")

    if not added:
        raise RuntimeError(f"{failed} טפסים נכשלו ואף אחד לא נאסף")
    payload = {
        "_comment": COMMENT,
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "games": dict(sorted(done.items())),
    }
    (DATA / OUT).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"נכתב {OUT}: {added} חדשים, {len(done)} בסך הכול"
        + (f", {failed} נכשלו" if failed else ""))
    return f"{added} טפסים חדשים, {len(done)} בסך הכול"


if __name__ == "__main__":
    update_game_stats()
