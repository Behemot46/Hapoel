"""Automatic data updater for the Hapoel Jerusalem fan app.

Runs on GitHub Actions a few times a day. Fetches the team's schedule,
results and league standings from public league pages and writes them as
JSON files under app/data/.

Design principles:
- Never clobber good data: if a fetch or parse fails, the existing JSON
  files are left untouched and the failure is recorded in meta.json.
- Be loud in logs: every step prints what it found, so a broken selector
  is easy to diagnose from the Actions run page.

NOTE (stage A): the sandbox this project is developed in cannot reach the
league sites, so the parsers below are written defensively against the
general structure of basket.co.il and will be finalized from the logs of
the first real Actions runs. Until a source parses successfully the app
keeps its current data and meta.sample stays true.
"""
import json
import re
import sys
import datetime
import pathlib
import time
import zoneinfo

import requests
from bs4 import BeautifulSoup

import club_games
import club_roster
import news_feed
import photo_crop
import podcast_feed

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
TEAM = "הפועל ירושלים"
UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; +https://github.com/Behemot46/Hapoel)"}

LEAGUE_HOME = "https://basket.co.il/"
# the league lists the club under its sponsored name or abbreviated
# ("הפועל י-ם"), so match loosely
def is_us(name):
    n = name or ""
    if "הפועל" not in n:
        return False
    return any(j in n for j in ("ירושלים", "י-ם", "י־ם", 'י"ם', "י״ם"))

def log(*args):
    print("[update]", *args, flush=True)

# The EuroCup API answers 429 to a burst. One source hammering it used to
# starve the sources that ran after it, so back off and retry here rather
# than letting a throttle look like a broken feed.
RETRY_WAITS = (2, 5, 12, 25)

def fetch(url):
    log("GET", url)
    last = None
    for i, wait in enumerate((0,) + RETRY_WAITS):
        if wait:
            time.sleep(wait)
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 429:
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        last = r
        retry_after = r.headers.get("Retry-After")
        log(f"  429 throttled (attempt {i + 1}), retry-after={retry_after or '-'}")
        if retry_after and retry_after.isdigit():
            time.sleep(min(int(retry_after), 30))
    last.raise_for_status()

def load_json(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def save_json(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("wrote", name)

def parse_int(s):
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None

# The league site prints Israeli wall-clock time. Stamping every game +03:00
# is right in summer and an hour early all winter, so resolve the real offset
# for the date instead of assuming one.
ISRAEL = zoneinfo.ZoneInfo("Asia/Jerusalem")

def israel_iso(year, month, day, hh, mm):
    d = datetime.datetime(year, month, day, hh, mm, tzinfo=ISRAEL)
    return d.isoformat(timespec="seconds")

# ---------------------------------------------------------------- standings

def dump_tables(soup, url):
    """Diagnostic: log a summary of every table so selectors can be calibrated."""
    tables = soup.find_all("table")
    log(f"DIAG {url}: {len(tables)} tables")
    for i, t in enumerate(tables[:12]):
        rows = t.find_all("tr")
        first = rows[0].get_text(" | ", strip=True)[:110] if rows else ""
        second = rows[1].get_text(" | ", strip=True)[:110] if len(rows) > 1 else ""
        log(f"  table[{i}] rows={len(rows)} head='{first}' next='{second}'")

def parse_record(s):
    """'3-1' → (3, 1)"""
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", (s or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None

def find_standings(soup):
    """Header-driven parse: locate a table whose header names a team column,
    map columns by header text, and require our team among the rows.
    Real header on basket.co.il: # | שם הקבוצה | נק' | סה"כ | בית | חוץ | סטט'"""
    best = None
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 5:
            continue
        hdr_idx = hdr = None
        for i, r in enumerate(rows[:3]):
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if any("קבוצה" in c for c in cells):
                hdr_idx, hdr = i, cells
                break
        if hdr_idx is None:
            continue

        def col(*prefixes):
            for j, c in enumerate(hdr):
                if any(c.startswith(p) for p in prefixes):
                    return j
            return None

        j_team = col("שם הקבוצה") if col("שם הקבוצה") is not None else col("קבוצה")
        j_pts, j_played = col("נק"), col("מש")
        j_wins, j_losses = col("נצ"), col("הפ")
        j_rec = col('סה"כ', "סה״כ", "מאזן")

        parsed = []
        for r in rows[hdr_idx + 1:]:
            cells = [c.get_text(strip=True) for c in r.find_all("td")]
            if len(cells) < 2:
                continue

            def cell(j):
                return cells[j] if j is not None and j < len(cells) else None

            team = cell(j_team)
            if not team or not re.search(r"[א-ת]{2,}", team):
                continue
            # drop header fragments that parse as rows (e.g. "סלים", "נצ'")
            if len(team) < 5 or team in ("ליגת ווינר סל", "שם הקבוצה"):
                continue
            wins = int(cell(j_wins)) if (cell(j_wins) or "").isdigit() else None
            losses = int(cell(j_losses)) if (cell(j_losses) or "").isdigit() else None
            if wins is None:
                rec = parse_record(cell(j_rec))
                if rec:
                    wins, losses = rec
            played = int(cell(j_played)) if (cell(j_played) or "").isdigit() else None
            if played is None and wins is not None and losses is not None:
                played = wins + losses
            points = int(cell(j_pts)) if (cell(j_pts) or "").isdigit() else None
            parsed.append({"team": team, "played": played or 0,
                           "wins": wins or 0, "losses": losses or 0, "points": points})
        if len(parsed) >= 5 and any(is_us(p["team"]) for p in parsed):
            if best is None or len(parsed) > len(best):
                best = parsed
    return best

# season pages: 2026/27 is cYear=2027 on basket.co.il; fall back to the
# previous season during the off-season, when the new table is still empty
STANDINGS_URLS = [
    "https://basket.co.il/table.asp?cYear=2027",
    "https://basket.co.il/table.asp",
    "https://basket.co.il/table.asp?cYear=2026",
]

def update_standings():
    parsed = None
    for url in STANDINGS_URLS:
        try:
            soup = BeautifulSoup(fetch(url), "html.parser")
        except Exception as e:
            log("standings fetch failed:", url, e)
            continue
        parsed = find_standings(soup)
        if parsed:
            break
        dump_tables(soup, url)
    if not parsed:
        raise RuntimeError("no standings table found containing team name (see DIAG lines)")

    rows = []
    for i, p in enumerate(parsed, start=1):
        row = {"pos": i, "team": p["team"], "played": p["played"],
               "wins": p["wins"], "losses": p["losses"]}
        if p.get("points") is not None:
            row["points"] = p["points"]
        rows.append(row)
    log("standings rows:", len(rows))
    current = load_json("standings.json") or {}
    current.update({"rows": rows})
    save_json("standings.json", current)
    return True

# ---------------------------------------------------------------- games

DATE_RE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
SCORE_RE = re.compile(r"(\d{2,3})\s*[--:]\s*(\d{2,3})")

def parse_team_games(soup):
    """Header-driven parse of the team schedule table.
    Real header on team.asp: תאריך | שעה | שלב | מארחת | אורחת | תוצאה"""
    games = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        hdr_idx = hdr = None
        for i, r in enumerate(rows[:3]):
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if any("תאריך" in c for c in cells) and any("מארחת" in c for c in cells):
                hdr_idx, hdr = i, cells
                break
        if hdr_idx is None:
            continue

        def col(name):
            for j, c in enumerate(hdr):
                if name in c:
                    return j
            return None

        j_date, j_time, j_stage = col("תאריך"), col("שעה"), col("שלב")
        j_home, j_away, j_score = col("מארחת"), col("אורחת"), col("תוצאה")

        for r in rows[hdr_idx + 1:]:
            cells = [c.get_text(strip=True) for c in r.find_all("td")]
            if len(cells) < 3:
                continue

            def cell(j):
                return cells[j] if j is not None and j < len(cells) else ""

            dm = DATE_RE.search(cell(j_date) or " ".join(cells))
            if not dm:
                continue
            day, month, year = (int(x) for x in dm.groups())
            if year < 100:
                year += 2000
            # שעה חסרה היא לא 20:00. עד היום היא הייתה: המשחק מול מכבי
            # אשדוד ב־8.9 הופיע אצלנו כ־20:00 בזמן שאתר הליגה עוד לא
            # פרסם שעה בכלל, ואוהד שקרא את זה לא היה יכול לדעת שהמספר
            # הזה הומצא אצלנו. כשהליגה פרסמה, התברר ש־17:00. אז אותה
            # מוסכמה כמו בלוח של המועדון: אמצע היום והערה גלויה, ולא ניחוש
            # שנראה כמו עובדה. נמדד ב־29.8.2026: 26 מ־28 השורות בעמוד
            # מגיעות עם תא שעה ריק.
            tm = TIME_RE.search(cell(j_time))
            # 12:00 ולא חצות: האפליקציה מציגה תאריכים בשעון של המכשיר,
            # וחצות בישראל היא היום הקודם אצל אוהד שנמצא ממערב לנו.
            hh, mm = (int(x) for x in tm.groups()) if tm else (12, 0)
            # והליגה גם אומרת בעצמה מתי המועד עוד לא סופי, בתוך תא
            # התאריך: ״22/11/2026לא סופי״. עד היום המילה הזאת נזרקה,
            # והתאריך הוצג לאוהד כאילו הוא סגור.
            provisional = "לא סופי" in cell(j_date)
            home_raw, away_raw = cell(j_home), cell(j_away)
            if not home_raw or not away_raw:
                continue
            if not (is_us(home_raw) or is_us(away_raw)):
                continue
            # NOTE: score order vs. host/guest still unverified, no finished
            # games on the page yet; recheck when first results appear
            sm = SCORE_RE.search(cell(j_score))
            opp = away_raw if is_us(home_raw) else home_raw

            game = {
                "id": f"{year:04d}{month:02d}{day:02d}-{re.sub(r'[^א-ת]', '', opp)[:12]}",
                "date": israel_iso(year, month, day, hh, mm),
                "competition": cell(j_stage) or "ליגת ווינר סל",
                "home": TEAM if is_us(home_raw) else home_raw,
                "away": TEAM if is_us(away_raw) else away_raw,
                "venue": None,
                "status": "finished" if sm else "scheduled",
                "homeScore": int(sm.group(1)) if sm else None,
                "awayScore": int(sm.group(2)) if sm else None,
            }
            if provisional and not tm:
                game["note"] = "המועד לא סופי, והשעה טרם נקבעה"
            elif provisional:
                game["note"] = "המועד לא סופי"
            elif not tm:
                game["note"] = "שעת הפתיחה טרם נקבעה"
            if not tm:
                # דגל מפורש, כי ההערה היא טקסט חופשי והאפליקציה צריכה
                # לדעת בוודאות מתי אסור לה להדפיס שעון
                game["timeTbd"] = True
            if provisional:
                game["provisional"] = True
            games.append(game)
    return games

def find_team_link():
    """Find our team page: a link whose text is our team and whose href looks
    like a team page. Logs link diagnostics when nothing matches so the
    pattern can be calibrated from Actions logs."""
    candidates = STANDINGS_URLS + [LEAGUE_HOME]
    for url in candidates:
        try:
            soup = BeautifulSoup(fetch(url), "html.parser")
        except Exception as e:
            log("team-link fetch failed:", url, e)
            continue
        links = [(a.get_text(" ", strip=True), a["href"]) for a in soup.find_all("a", href=True)]
        for txt, href in links:
            if is_us(txt) and ("team" in href.lower() or "id=" in href.lower()):
                return requests.compat.urljoin(url, href)
        ours = [(t, h) for t, h in links if "הפועל" in t or "team" in h.lower()]
        log(f"DIAG links on {url}: {len(ours)} candidates")
        for t, h in ours[:25]:
            log(f"  '{t[:45]}' -> {h[:100]}")
    return None

def preserve_missing(games, previous, now=None):
    """משחקים מהקובץ הקודם שאף מקור כבר לא מציע, ושצריך לשמור.

    יורדת רשומה רק כשיש עדות חיובית שהיא הוזזה: אותה יריבה באותה תחרות
    בתאריך אחר, והתאריך הישן עוד בעתיד. שתיקה של מקור אינה עדות.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    known = {g.get("id") for g in games if g.get("id")}
    dates = {g["date"][:10] for g in games}
    pairs = {(g.get("home"), g.get("away"), g.get("competition")) for g in games}

    keep = []
    for g in previous:
        if g.get("id") in known or g["date"][:10] in dates:
            continue
        try:
            when = datetime.datetime.fromisoformat(g["date"])
        except Exception:
            continue
        moved = (when > now
                 and (g.get("home"), g.get("away"), g.get("competition")) in pairs)
        if not moved:
            keep.append(g)
    return keep


def update_games():
    team_link = find_team_link()
    if not team_link:
        raise RuntimeError("no team.asp link for our team found on league pages")
    log("team page:", team_link)
    team_soup = BeautifulSoup(fetch(team_link), "html.parser")
    games = parse_team_games(team_soup)
    # the pre-season schedule can legitimately hold just a game or two
    if len(games) < 1:
        dump_tables(team_soup, team_link)
        raise RuntimeError("no games parsed, refusing to overwrite (see DIAG lines)")
    log("domestic games parsed:", len(games))

    # the league site carries only domestic games, so add the European ones
    try:
        euro = eurocup_games()
    except Exception as e:
        log("eurocup games failed:", e)
        euro = []
    if euro:
        # a fixture already known from the league site wins, its names are Hebrew
        have = {g["date"][:10] for g in games}
        added = [g for g in euro if g["date"][:10] not in have]
        games.extend(added)
        log(f"european games added: {len(added)} of {len(euro)}")
    else:
        # never drop European fixtures already published just because a fetch failed
        previous = (load_json("games.json") or {}).get("games", [])
        kept = [g for g in previous if g.get("competition") == "יורוקאפ"]
        if kept:
            games.extend(kept)
            log(f"kept {len(kept)} previously known european games")

    # לוח המועדון הוא מקור האמת הראשי, והוא היחיד שמפרסם משחקי הכנה בכלל.
    # אתר הליגה והפיד של אירופה מנהלים רק את התחרויות שלהם, ולכן לוח
    # שנשען רק עליהם מכריז על משחק שבעוד שבועיים בזמן שהקבוצה משחקת מחר.
    # מה שכבר הגיע ממקור רשמי נשאר, כי שם השעה מדויקת והתוצאה מתעדכנת
    # לבד; מה שחסר שם נלקח מהמועדון.
    try:
        club = club_games.fetch_games(fetch, log=log)
    except Exception as e:
        log("club schedule failed:", e)
        club = []
    if club:
        have = {g["date"][:10] for g in games}
        fresh = [g for g in club if g["date"][:10] not in have]
        games.extend(fresh)
        log(f"club schedule: {len(club)} games, {len(fresh)} of them new to the board")
        for g in fresh:
            log(f"    + {g['date'][:16]}  {g['competition']}  "
                f"{g['home']} vs {g['away']}  {g.get('venue') or ''}")
    else:
        log("club schedule empty, board relies on the official feeds alone")

    # קובץ ידני למה שגם המועדון לא פרסם, למשל משחק בטורניר שהיריבה בו
    # תלויה בתוצאות. נשאר אחרון, ורק למה שאף מקור לא כיסה.
    friendly = (load_json("friendlies.json") or {}).get("games", [])
    if friendly:
        have = {g["date"][:10] for g in games}
        fresh = [g for g in friendly if g["date"][:10] not in have]
        games.extend(fresh)
        log(f"manual entries added: {len(fresh)} of {len(friendly)}")

    # משחק שנעלם מהמקורות. אתר המועדון מוריד משחק מהעמוד ברגע שהוא
    # נגמר, ויומן האוהד מסמן נוכחות לפי מזהה משחק, אז משחק שנמחק גורר
    # איתו גם את הסימון. לכן מה שכבר היה על הלוח ואינו מוצע יותר על ידי
    # אף מקור נשמר מהקובץ הקודם.
    #
    # **למה בלי חלון זמן:** הניסוח הקודם שמר רק משחקים שהתחילו לפני
    # שעתיים ומעלה, מתוך הנחה שמשחק נעלם אחרי שהוא נגמר. המשחק מול
    # הפועל חולון ב־31.8.2026 הראה שההנחה לא נכונה: הוא נמחק מהקובץ
    # בריצה של 16:04 UTC, שעה **לפני** הקפיצה ב־17:05 UTC, ולכן הוא היה
    # עדיין בעתיד, החלון פסל אותו, והוא ירד מהלוח ביום המשחק עצמו.
    #
    # מקור ששותק אינו עדות שהמשחק בוטל, ולכן ברירת המחדל היא לשמור. מה
    # שכן מפיל רשומה הוא עדות חיובית להזזה: אותה יריבה באותה תחרות
    # מופיעה בתאריך אחר, והתאריך הישן עוד לא הגיע. משחק ששוחק כבר לא
    # יורד לעולם, מה שהיה גם הכוונה המקורית.
    previous = (load_json("games.json") or {}).get("games", [])
    revived = preserve_missing(games, previous)
    if revived:
        games.extend(revived)
        log(f"שמרנו {len(revived)} משחקים שכבר לא מופיעים באף מקור:")
        for g in revived:
            log(f"    = {g['date'][:16]}  {g['home']} vs {g['away']}  status={g['status']}")

    games.sort(key=lambda g: g["date"])
    log("games total:", len(games))
    current = load_json("games.json") or {}
    current["games"] = games
    current["league"] = league_status(games)
    save_json("games.json", current)
    return True

# A cup tie or two is all the league publishes before the season is drawn.
# Rather than let the app quietly show a near-empty schedule for weeks, note
# how many league fixtures exist so the app can say so, and shout in the log
# on the day the real list finally appears.
def is_league_game(g):
    """Domestic and not a cup tie. The league site puts whatever the stage is
    called in the column, so match by exclusion rather than by one string."""
    comp = g.get("competition") or ""
    return comp != "יורוקאפ" and "גביע" not in comp

def league_status(games):
    league = [g for g in games if is_league_game(g)]
    previous = ((load_json("games.json") or {}).get("league") or {}).get("count", 0)
    count = len(league)
    if count and not previous:
        log("*" * 60)
        log(f"THE LEAGUE SCHEDULE IS OUT, {count} fixtures appeared")
        log("*" * 60)
    elif count > previous:
        log(f"league fixtures grew: {previous} -> {count}")
    elif not count:
        log("league schedule still unpublished (0 fixtures)")
    return {"count": count, "published": bool(count)}

# ---------------------------------------------------------------- eurocup games

EUROCUP_GAME_ENDPOINTS = [
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/clubs/JER/games",
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/games?clubCode=JER",
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/games",
    "https://api-live.euroleague.net/v1/results?seasonCode=U2026&clubCode=JER",
    "https://api-live.euroleague.net/v1/schedules?seasonCode=U2026&clubCode=JER",
]

SIDE_KEYS = [("local", "road"), ("home", "away"), ("hometeam", "awayteam"),
             ("teama", "teamb"), ("club", "opponent")]

def _name_of(v):
    """A side may be a plain name or an object wrapping one."""
    if isinstance(v, str) and len(v.strip()) >= 3:
        return v.strip()
    if isinstance(v, dict):
        low = {k.lower(): val for k, val in v.items()}
        for k in ("name", "clubname", "teamname", "fullname"):
            if isinstance(low.get(k), str) and low[k].strip():
                return low[k].strip()
        club = low.get("club")
        if isinstance(club, dict):
            return _name_of(club)
    return None

def _score_of(v, sibling, key):
    if isinstance(v, dict):
        low = {k.lower(): val for k, val in v.items()}
        for k in ("score", "points", "pts"):
            if isinstance(low.get(k), (int, float)):
                return int(low[k])
    s = sibling.get(key)
    return int(s) if isinstance(s, (int, float)) else None

ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})")

def _date_of(d):
    for k, v in d.items():
        if "date" in k.lower() and isinstance(v, str):
            m = ISO_DATE.search(v)
            if m:
                y, mo, da, hh, mm = m.groups()
                return f"{y}-{mo}-{da}T{hh}:{mm}:00+03:00"
            dm = DATE_RE.search(v)
            if dm:
                da, mo, y = (int(x) for x in dm.groups())
                if y < 100:
                    y += 2000
                tm = TIME_RE.search(" ".join(str(x) for x in d.values() if isinstance(x, str)))
                hh, mm = (int(x) for x in tm.groups()) if tm else (20, 0)
                return f"{y:04d}-{mo:02d}-{da:02d}T{hh:02d}:{mm:02d}:00+03:00"
    return None

def _extract_games(obj, out):
    if isinstance(obj, list):
        for x in obj:
            _extract_games(x, out)
        return
    if not isinstance(obj, dict):
        return
    low = {k.lower(): v for k, v in obj.items()}
    date = _date_of(low)
    if date:
        for hk, ak in SIDE_KEYS:
            if hk in low and ak in low:
                home = _name_of(low[hk])
                away = _name_of(low[ak])
                if home and away:
                    hs = _score_of(low[hk], low, "homescore")
                    as_ = _score_of(low[ak], low, "awayscore")
                    played = bool(low.get("played")) or (hs is not None and as_ is not None and (hs or as_))
                    out.append({
                        "date": date, "home": home, "away": away,
                        "homeScore": hs if played else None,
                        "awayScore": as_ if played else None,
                        "status": "finished" if played else "scheduled",
                        "round": low.get("round") or low.get("roundnumber"),
                    })
                    break
    for v in obj.values():
        _extract_games(v, out)

def is_us_latin(name):
    n = (name or "").lower()
    return "jerusalem" in n and ("hapoel" in n or "midtown" in n)

# The v2 feed gives three times per game and they are NOT the same:
#   date       CET, the competition's own clock
#   localDate  local to the venue, Belgrade for our "home" European games
#   utcDate    the actual instant, and the only one worth storing
# Reading `date` as if it were Israeli time put every European fixture an
# hour early on the schedule. Store the instant; the app renders it local.
EUROCUP_V2_GAMES = "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/games"

def _club_name(side):
    club = (side or {}).get("club") or {}
    return club.get("name") or club.get("editorialName") or club.get("code")

def _club_code(side):
    return ((side or {}).get("club") or {}).get("code")

def _partials(side):
    p = (side or {}).get("partials") or {}
    out = [p.get(f"partials{i}") for i in range(1, 5)]
    return [int(x) for x in out if isinstance(x, (int, float))]

def parse_eurocup_game(g):
    """One game object → our schema, or None if it is not ours."""
    local, road = g.get("local") or {}, g.get("road") or {}
    if "JER" not in (_club_code(local), _club_code(road)):
        return None
    when = g.get("utcDate")
    if not when:
        return None
    home, away = _club_name(local), _club_name(road)
    we_are_home = _club_code(local) == "JER"
    opp = away if we_are_home else home
    played = bool(g.get("played"))
    venue = (g.get("venue") or {}).get("name") or None
    day = when[:10].replace("-", "")
    return {
        "id": f"{day}-euro-{re.sub(r'[^A-Za-z]', '', opp or '')[:12]}",
        "date": when,
        "competition": "יורוקאפ",
        "round": g.get("roundName") or (f"מחזור {g['round']}" if g.get("round") else None),
        "home": TEAM if we_are_home else home,
        "away": TEAM if not we_are_home else away,
        # a European "home" game is often played abroad, so never hide the venue
        "venue": venue.title() if venue else None,
        "status": "finished" if played else "scheduled",
        "homeScore": int(local.get("score")) if played else None,
        "awayScore": int(road.get("score")) if played else None,
        "homePartials": _partials(local) if played else None,
        "awayPartials": _partials(road) if played else None,
    }

def eurocup_games():
    try:
        data = json.loads(fetch(EUROCUP_V2_GAMES))
    except Exception as e:
        log("eurocup v2 games failed:", e)
        return eurocup_games_fallback()
    raw = data.get("data") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        log("eurocup v2 games: unexpected envelope", list(data)[:8] if isinstance(data, dict) else type(data))
        return eurocup_games_fallback()
    games = [x for x in (parse_eurocup_game(g) for g in raw) if x]
    log(f"eurocup v2 games: {len(raw)} in feed, {len(games)} ours")
    if games:
        log("  sample:", json.dumps(games[0], ensure_ascii=False)[:220])
        return games
    return eurocup_games_fallback()

def eurocup_games_fallback():
    """Older endpoints, kept in case the v2 shape moves under us."""
    for url in EUROCUP_GAME_ENDPOINTS:
        try:
            data = json.loads(fetch(url))
        except Exception as e:
            log("eurocup games endpoint failed:", url, e)
            continue
        found = []
        _extract_games(data, found)
        ours = [g for g in found if is_us_latin(g["home"]) or is_us_latin(g["away"])]
        log(f"  eurocup games {url}: {len(found)} parsed, {len(ours)} ours")
        if ours:
            games = []
            for g in ours:
                opp = g["away"] if is_us_latin(g["home"]) else g["home"]
                day = g["date"][:10].replace("-", "")
                games.append({
                    "id": f"{day}-euro-{re.sub(r'[^A-Za-z]', '', opp)[:12]}",
                    "date": g["date"],
                    "competition": "יורוקאפ",
                    "home": TEAM if is_us_latin(g["home"]) else g["home"],
                    "away": TEAM if is_us_latin(g["away"]) else g["away"],
                    "venue": None,
                    "status": g["status"],
                    "homeScore": g["homeScore"],
                    "awayScore": g["awayScore"],
                })
            return games
        if found:
            log(f"  DIAG sample parsed game: {found[0]}")
    return []

# ---------------------------------------------------------------- roster

POSITION_WORDS = ("שוער", "רכז", "קלע", "כנף", "סמ\"ק", "סמ״ק", "פורוורד", "סנטר", "מרכז", "גארד")

def parse_roster(soup):
    """Find the squad table on the team page and map it by header text.
    Expected headers vary; we look for a table whose header mentions שחקן/שם
    together with at least one of מספר / תפקיד / גובה / לידה."""
    best = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 4:
            continue
        hdr_idx = hdr = None
        for i, r in enumerate(rows[:3]):
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            joined = " ".join(cells)
            if ("שחקן" in joined or "שם" in joined) and any(
                    k in joined for k in ("מס", "תפקיד", "גובה", "לידה", "עמדה")):
                hdr_idx, hdr = i, cells
                break
        if hdr_idx is None:
            continue

        def col(*names):
            for j, c in enumerate(hdr):
                if any(n in c for n in names):
                    return j
            return None

        j_name = col("שחקן", "שם")
        j_num = col("מס")
        j_pos = col("תפקיד", "עמדה")
        j_height = col("גובה")
        j_born = col("לידה", "שנתון")

        players = []
        for r in rows[hdr_idx + 1:]:
            cells = [c.get_text(strip=True) for c in r.find_all("td")]
            if len(cells) < 2:
                continue

            def cell(j):
                return cells[j] if j is not None and j < len(cells) else ""

            name = cell(j_name)
            if not name or len(name) < 3 or not re.search(r"[א-תA-Za-z]{2,}", name):
                continue
            p = {"name": name}
            if parse_int(cell(j_num)) is not None:
                p["number"] = parse_int(cell(j_num))
            if cell(j_pos):
                p["position"] = cell(j_pos)
            if parse_int(cell(j_height)):
                p["height"] = parse_int(cell(j_height))
            if parse_int(cell(j_born)):
                p["born"] = parse_int(cell(j_born))
            players.append(p)
        if len(players) > len(best):
            best = players
    return best

ROSTER_WORDS = ("סגל", "שחקנים", "הרכב", "שחקני")

# --- EuroCup as a roster source ------------------------------------------
# basket.co.il publishes no squad at all, but the club plays in the EuroCup,
# whose official feeds do list players. Team code JER, competition U (EuroCup).
EUROCUP_ENDPOINTS = [
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/clubs/JER/people",
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2025/clubs/JER/people",
    "https://api-live.euroleague.net/v1/teams?seasonCode=U2026&teamCode=JER",
    "https://api-live.euroleague.net/v1/teams?seasonCode=U2025&teamCode=JER",
]
EUROCUP_PAGE = "https://www.euroleaguebasketball.net/en/eurocup/teams/hapoel-midtown-jerusalem/jer/"

NAME_KEYS = ("name", "personname", "fullname", "displayname", "playername")
NUM_KEYS = ("dorsal", "jersey", "number", "shirtnumber", "dorsalraw")
POS_KEYS = ("positionname", "position", "role")

IMAGE_EXT = re.compile(r"\.(jpg|jpeg|png|webp)(\?|$)", re.I)

def find_image(d):
    """Pull a headshot URL out of a player record, whatever it is called."""
    for k, v in d.items():
        if isinstance(v, str) and v.startswith("http") and (
                IMAGE_EXT.search(v) or any(w in k for w in ("image", "photo", "picture", "headshot"))):
            return v
        if isinstance(v, dict) and any(w in k for w in ("image", "photo", "picture")):
            # prefer a headshot-ish entry, else any URL in there
            for kk in ("headshot", "profile", "player", "medium", "small"):
                vv = v.get(kk)
                if isinstance(vv, str) and vv.startswith("http"):
                    return vv
            for vv in v.values():
                if isinstance(vv, str) and vv.startswith("http"):
                    return vv
    return None

def find_country(d):
    for k in ("country", "nationality", "countryname", "birthcountry"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            n = v.get("name") or v.get("Name")
            if isinstance(n, str) and n.strip():
                return n.strip()
    return None

def _walk_json(obj, out):
    """Collect dicts that look like a player record, anywhere in the tree."""
    if isinstance(obj, list):
        for x in obj:
            _walk_json(x, out)
        return
    if not isinstance(obj, dict):
        return
    lower = {k.lower(): v for k, v in obj.items()}
    # a record often splits across two levels: {"person": {...}, "dorsal": 5}
    # so read both as one merged view, with the outer level taking precedence
    for nest in ("person", "player", "personinfo"):
        inner = lower.get(nest)
        if isinstance(inner, dict):
            merged = {k.lower(): v for k, v in inner.items()}
            merged.update(lower)
            lower = merged
            break

    name = None
    for k in NAME_KEYS:
        v = lower.get(k)
        if isinstance(v, str) and len(v.strip()) >= 3:
            name = v.strip()
            break
    has_player_marker = any(k in lower for k in NUM_KEYS + POS_KEYS + ("height", "birthdate"))
    if name and has_player_marker:
        p = {"name": name}
        for k in NUM_KEYS:
            n = parse_int(str(lower.get(k, "")))
            if n is not None:
                p["number"] = n
                break
        for k in POS_KEYS:
            v = lower.get(k)
            if isinstance(v, str) and v.strip():
                p["position"] = v.strip()
                break
        h = lower.get("height")
        if isinstance(h, (int, float)) and h:
            p["height"] = int(h if h > 100 else h * 100)
        bd = lower.get("birthdate") or lower.get("birthdatestring")
        if isinstance(bd, str):
            m = re.search(r"(19|20)\d{2}", bd)
            if m:
                p["born"] = int(m.group())
        img = find_image(lower)
        if img:
            p["photoUrl"] = img
        country = find_country(lower)
        if country:
            p["country"] = country
        code = lower.get("code") or lower.get("personcode") or lower.get("id")
        if isinstance(code, (str, int)) and str(code).strip():
            p["code"] = str(code).strip()
        out.append(p)
    for v in obj.values():
        _walk_json(v, out)

POSITION_HE = {
    "guard": "גארד",
    "point guard": "רכז",
    "shooting guard": "קלע",
    "forward": "פורוורד",
    "small forward": "כנף",
    "power forward": "סמ״ק",
    "center": "סנטר",
    "coach": "מאמן",
    "head coach": "מאמן ראשי",
}

def tidy_word(w):
    """Capitalise a name word, respecting hyphens and apostrophes."""
    return "-".join(
        "'".join(bit.capitalize() for bit in part.split("'"))
        for part in w.split("-")
    )

def tidy_name(raw):
    """'CACOK, DEVONTAE' -> 'Devontae Cacok'"""
    s = " ".join((raw or "").split())
    if "," in s:
        last, first = s.split(",", 1)
        s = f"{first.strip()} {last.strip()}"
    return " ".join(tidy_word(w) for w in s.split() if w)

def tidy_position(raw):
    return POSITION_HE.get((raw or "").strip().lower(), (raw or "").strip())

def dedupe_players(players):
    seen, out = set(), []
    for p in players:
        key = p["name"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out

def roster_from_eurocup():
    for url in EUROCUP_ENDPOINTS:
        try:
            body = fetch(url)
        except Exception as e:
            log("eurocup endpoint failed:", url, e)
            continue
        players = []
        try:
            _walk_json(json.loads(body), players)
        except ValueError:
            # v1 endpoints answer XML, pull player nodes out of it
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup.find_all(["player", "playeritem"]):
                nm = tag.find("name")
                if not nm:
                    continue
                p = {"name": nm.get_text(strip=True)}
                for field, key in (("dorsal", "number"), ("position", "position"),
                                   ("height", "height"), ("birthdate", "born")):
                    node = tag.find(field)
                    if not node:
                        continue
                    txt = node.get_text(strip=True)
                    if key in ("number", "height"):
                        v = parse_int(txt)
                        if v:
                            p[key] = v
                    elif key == "born":
                        m = re.search(r"(19|20)\d{2}", txt)
                        if m:
                            p[key] = int(m.group())
                    elif txt:
                        p[key] = txt
                players.append(p)
        players = dedupe_players([p for p in players if len(p["name"]) >= 3])
        # the feed mixes staff into the squad (the head coach has no shirt
        # number), so keep only numbered entries
        squad, staff = [], []
        for p in players:
            (squad if p.get("number") is not None else staff).append(p)
        for p in squad:
            p["name"] = tidy_name(p["name"])
            if p.get("position"):
                p["position"] = tidy_position(p["position"])
        log(f"  eurocup attempt {url}: {len(squad)} players"
            + (f" (excluded non-numbered: {[tidy_name(s['name']) for s in staff]})" if staff else ""))
        if len(squad) >= 5:
            return squad
    return []

def roster_candidates(team_link, soup):
    """The team page itself carries the schedule and standings, not the squad,
    so collect pages that look like they hold the roster."""
    urls, seen = [], set()
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = a["href"]
        if any(w in label for w in ROSTER_WORDS) or \
           any(w in href.lower() for w in ("player", "squad", "roster")):
            u = requests.compat.urljoin(team_link, href)
            if u not in seen:
                seen.add(u)
                urls.append(u)
    return urls

COUNTRY_HE = {
    "united states of america": "ארה״ב", "united states": "ארה״ב", "usa": "ארה״ב",
    "israel": "ישראל", "serbia": "סרביה", "montenegro": "מונטנגרו",
    "croatia": "קרואטיה", "slovenia": "סלובניה", "bosnia and herzegovina": "בוסניה",
    "north macedonia": "מקדוניה הצפונית", "greece": "יוון", "spain": "ספרד",
    "france": "צרפת", "italy": "איטליה", "germany": "גרמניה", "turkey": "טורקיה",
    "lithuania": "ליטא", "latvia": "לטביה", "estonia": "אסטוניה", "poland": "פולין",
    "ukraine": "אוקראינה", "russia": "רוסיה", "georgia": "גאורגיה",
    "canada": "קנדה", "brazil": "ברזיל", "argentina": "ארגנטינה",
    "nigeria": "ניגריה", "senegal": "סנגל", "cameroon": "קמרון",
    "dominican republic": "הרפובליקה הדומיניקנית", "puerto rico": "פוארטו ריקו",
    "australia": "אוסטרליה", "united kingdom": "בריטניה", "great britain": "בריטניה",
    "belgium": "בלגיה", "netherlands": "הולנד", "portugal": "פורטוגל",
    "czech republic": "צ׳כיה", "czechia": "צ׳כיה", "finland": "פינלנד", "sweden": "שוודיה",
}

def tidy_country(raw):
    return COUNTRY_HE.get((raw or "").strip().lower(), (raw or "").strip())

# the squad feed carries no headshots, so try the per-player detail endpoints
# The squad payload carries images:{} for everyone, but the competition-wide
# person record does have a headshot, and being season-less it also covers a
# summer signing whose EuroCup history is at another club. One request per
# player, which the API tolerates; a full box-score sweep does not (429).
PERSON_ENDPOINTS = [
    "https://api-live.euroleague.net/v2/competitions/U/people/{code}",
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2026/people/{code}",
    "https://api-live.euroleague.net/v2/competitions/U/seasons/U2025/people/{code}",
]

def photos_from_team_page(players):
    """Last resort: the EuroCup team page embeds its data as JSON. Pull
    headshot URLs from it and match them to players by surname."""
    try:
        html = fetch(EUROCUP_PAGE)
    except Exception as e:
        log("  team page fetch failed:", e)
        return 0
    blobs = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                       html, re.S)
    blobs += re.findall(r'__NEXT_DATA__[^>]*>(.*?)</script>', html, re.S)
    found = []
    for b in blobs:
        try:
            _walk_json(json.loads(b), found)
        except ValueError:
            continue
    have = {tidy_name(f["name"]).lower(): f["photoUrl"] for f in found if f.get("photoUrl")}
    log(f"  team page: {len(blobs)} json blobs, {len(have)} names with images")
    if not have:
        # fall back to any image URL that carries a player surname
        urls = re.findall(r'https://[^"\'\s]+\.(?:jpg|jpeg|png|webp)[^"\'\s]*', html)
        log(f"  team page raw image urls: {len(urls)}")
        for p in players:
            last = p["name"].split()[-1].lower()
            for u in urls:
                if last in u.lower():
                    p["photoUrl"] = u
                    break
        return sum(1 for p in players if p.get("photoUrl"))
    hits = 0
    for p in players:
        key = p["name"].lower()
        url = have.get(key)
        if not url:  # match on surname when the full name differs
            last = p["name"].split()[-1].lower()
            url = next((v for k, v in have.items() if last in k), None)
        if url:
            p["photoUrl"] = url
            hits += 1
    return hits

def _headshot_from_person(data):
    """{"data": [ {images:{headshot}}, ... ]}, newest entry wins, because a
    player who has been round the block has one record per club-season."""
    rows = data.get("data") if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return None
    best, best_key = None, ""
    for r in rows:
        if not isinstance(r, dict):
            continue
        url = ((r.get("images") or {}).get("headshot")
               or (r.get("images") or {}).get("action"))
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        key = str((r.get("season") or {}).get("code") or r.get("startDate") or "")
        if best is None or key >= best_key:
            best, best_key = url, key
    return best

def photo_url_for(code, template=None):
    """Return (url, template_that_worked). Reuses a known-good template."""
    templates = [template] if template else PERSON_ENDPOINTS
    for t in templates:
        try:
            data = json.loads(fetch(t.format(code=code)))
        except Exception as e:
            log(f"  person endpoint failed ({t}): {e}")
            continue
        url = _headshot_from_person(data)
        if url:
            return url, t
        # fall back to the loose walker in case the shape moves
        found = []
        _walk_json(data, found)
        for rec in found:
            if rec.get("photoUrl"):
                return rec["photoUrl"], t
        if isinstance(data, dict):
            log(f"  no headshot for {code} at {t} (keys {sorted(data.keys())[:8]})")
    return None, None

PHOTO_DIR = ROOT / "app" / "img" / "players"

# how many new headshots to look up in a single run, see the note in
# update_roster(); the cap exists to protect the other sources, not the images
PHOTO_LOOKUPS_PER_RUN = 4

def slugify(name, club_id=""):
    """A stable, unique id for a player, used in the url and in the photo
    filename. A name written in Hebrew has no Latin letters at all, so the
    obvious version of this returned the same fallback for every Israeli in
    the squad: four players sharing one address, and four headshots sharing
    one filename. The league's own player id is the thing here that is both
    stable and unique, so that is what stands in."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower()).strip("-")
    if s:
        return s
    return f"p-{club_id}" if club_id else "player"


def assign_slugs(players):
    """Slugs after this are unique, whatever the feed sends. Two players can
    share a name, and a name can carry no Latin letters at all."""
    taken = {}
    for p in players:
        s = slugify(p.get("name"), p.get("clubId"))
        if s in taken:
            s = f"{s}-{p.get('clubId') or len(taken)}"
            log(f"  slug clash on {p.get('name')}, using {s}")
        taken[s] = p.get("name")
        p["slug"] = s
    return players

def fetch_photos(players):
    """Download headshots into the repo so the app stays self-contained:
    works offline, and no third-party request from the fan's device."""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    kept = set()
    for p in players:
        url = p.pop("photoUrl", None)
        # the slug assigned to the squad, not a fresh guess: a headshot filed
        # under the wrong name is worse than no headshot at all
        slug = p.get("slug") or slugify(p.get("name"), p.get("clubId"))
        rel = f"img/players/{slug}.jpg"
        dest = PHOTO_DIR / f"{slug}.jpg"
        if not url:
            if dest.exists():
                p["photo"] = rel
                kept.add(dest.name)
            continue
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            data = r.content
            if Image is not None:
                import io
                im = Image.open(io.BytesIO(data))
                # some sources ship the cut-out on a transparent canvas.
                # Dropping alpha would leave whatever colour hides underneath,                 # black in one source, white in another, so flatten onto white
                # deliberately, which is what the rest of the squad looks like.
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGBA")
                    flat = Image.new("RGB", im.size, (255, 255, 255))
                    flat.paste(im, mask=im.split()[-1])
                    im = flat
                else:
                    im = im.convert("RGB")
                # the feed ships waist-up cut-outs; a round frame wants a head.
                # skip_square=False: these bytes are fresh off the network, so a
                # square canvas is the source's framing, not our earlier crop.
                im = photo_crop.crop_to_face(im, skip_square=False)
                im.thumbnail((400, 400))
                im.save(dest, "JPEG", quality=85, optimize=True)
            else:
                dest.write_bytes(data)
            p["photo"] = rel
            kept.add(dest.name)
            log(f"  photo saved: {slug} ({dest.stat().st_size // 1024} KB)")
        except Exception as e:
            log(f"  photo failed for {p['name']}: {e}")
            if dest.exists():
                p["photo"] = rel
                kept.add(dest.name)
    # drop photos of players who left the squad
    for f in PHOTO_DIR.glob("*.jpg"):
        if f.name not in kept:
            f.unlink()
            log("  photo removed (left squad):", f.name)

def merge_club_and_euro(club, euro):
    """The club page is the source of truth for who is in the squad, the shirt
    number, the Hebrew name and the date of birth. The European feed is the
    only place with height, country, position and the person code the photos
    hang off, so take those from it wherever a player appears in both."""
    he_to_lat = {}
    for lat, he in (load_json("player-names.json") or {}).items():
        if not lat.startswith("_"):
            he_to_lat[he] = lat
    by_lat = {p["name"]: p for p in euro}
    by_num = {p.get("number"): p for p in euro if p.get("number") is not None}

    merged, matched = [], 0
    for c in club:
        lat = he_to_lat.get(c["name"])
        e = by_lat.get(lat) if lat else None
        if e is None:
            e = by_num.get(c["number"])
            # a shirt number alone is weak evidence; only trust it when the
            # European feed has nobody else it could be
            if e and lat and e["name"] != lat:
                e = None
        if e:
            matched += 1
        rec = dict(e or {})
        rec["name"] = (e or {}).get("name") or c["name"]
        rec["nameHe"] = c["name"]
        rec["number"] = c["number"] if c["number"] is not None else rec.get("number")
        for k in ("birthDate", "born", "height", "clubId"):
            if c.get(k):
                rec[k] = c[k]
        rec["source"] = "club" + ("+eurocup" if e else "")
        merged.append(rec)

    # anyone the European feed knows but the club page did not list
    listed = {r.get("name") for r in merged}
    for e in euro:
        if e["name"] not in listed:
            log(f"  in the european squad but not on the club page: {e['name']}")
            e["source"] = "eurocup"
            merged.append(e)

    log(f"  merged squad: {len(merged)} players, {matched} matched to the european feed")
    merged.sort(key=lambda r: (r.get("number") is None, r.get("number") or 0))
    return merged

def update_roster():
    # The club's own squad page lists more players than the European
    # registration ever will, and is the only source with dates of birth.
    club = []
    try:
        club = club_roster.fetch_team(fetch, log=log)
    except Exception as e:
        log("club squad page failed:", e)

    euro = []
    try:
        euro = roster_from_eurocup()
    except Exception as e:
        log("eurocup roster failed:", e)

    if len(club) >= 5:
        players = merge_club_and_euro(club, euro)
        return _save_roster(players)
    log(f"club page gave {len(club)} players, falling back to the league site")

    team_link = find_team_link()
    if not team_link:
        raise RuntimeError("no team page found for roster")
    soup = BeautifulSoup(fetch(team_link), "html.parser")

    players = parse_roster(soup)
    tried = [team_link]
    if len(players) < 5:
        for u in roster_candidates(team_link, soup)[:6]:
            try:
                sub = BeautifulSoup(fetch(u), "html.parser")
            except Exception as e:
                log("roster page fetch failed:", u, e)
                continue
            tried.append(u)
            found = parse_roster(sub)
            log(f"  roster attempt {u}: {len(found)} players")
            if len(found) >= 5:
                players = found
                break

    # the squad may live on a team-scoped stats page rather than behind a link
    if len(players) < 5:
        m = re.search(r"TeamId=(\d+)", team_link)
        if m:
            tid = m.group(1)
            for path in ("stats-individual.asp?TeamId={}", "stats-individual.asp?TeamId={}&cYear=2027",
                         "team-players.asp?TeamId={}", "players.asp?TeamId={}",
                         "stats-accumulate.asp?TeamId={}"):
                u = requests.compat.urljoin(LEAGUE_HOME, path.format(tid))
                try:
                    sub = BeautifulSoup(fetch(u), "html.parser")
                except Exception as e:
                    log("roster url failed:", u, e)
                    continue
                tried.append(u)
                found = parse_roster(sub)
                log(f"  roster attempt {u}: {len(found)} players")
                if len(found) >= 5:
                    players = found
                    break

    # EuroCup feeds, the club plays there, and they do publish squads
    if len(players) < 5:
        players = roster_from_eurocup()
        if players:
            tried.append("eurocup")

    if len(players) < 5:
        log("DIAG roster: tried", tried)
        # summarise what the team page links to, by page, so the squad page
        # can be identified without dumping 292 rows
        from collections import Counter
        pats = Counter()
        example = {}
        for a in soup.find_all("a", href=True):
            key = a["href"].split("?")[0] or "#"
            pats[key] += 1
            example.setdefault(key, (a.get_text(" ", strip=True)[:30], a["href"][:80]))
        log(f"DIAG link patterns on team page ({len(pats)} distinct):")
        for key, n in pats.most_common(25):
            t, h = example[key]
            log(f"  {n:>3}x {key}  e.g. '{t}' -> {h}")
        dump_tables(soup, team_link)
        raise RuntimeError(f"only {len(players)} players parsed, refusing to overwrite (see DIAG lines)")
    return _save_roster(players)

def apply_overrides(players):
    """Hand-kept corrections win over anything scraped. A source that stops
    publishing a field should not silently blank it out, and an override left
    behind by a departed player should not rot unnoticed, so say both."""
    src = load_json("player-overrides.json") or {}
    used = set()
    for p in players:
        for key in (p.get("nameHe"), p.get("name")):
            o = src.get(key)
            if not isinstance(o, dict):
                continue
            used.add(key)
            for field, value in o.items():
                if field.startswith("_"):
                    continue
                if p.get(field) != value:
                    log(f"  override: {key} {field} {p.get(field)!r} -> {value!r}")
                p[field] = value
            break
    stale = [k for k in src if not k.startswith("_") and k not in used]
    if stale:
        log("  overrides with nobody in the squad (stale?):", stale)
    return players

def _save_roster(players):
    apply_overrides(players)
    log("roster players:", len(players))
    # one-time visibility into what the feed actually offers per player
    log("  fields present:", sorted({k for p in players for k in p}))
    assign_slugs(players)
    for p in players:
        if p.get("country"):
            p["country"] = tidy_country(p["country"])

    # Headshots are not in the squad payload; the competition-wide person
    # record has them. A photo does not change, so only look up players whose
    # file is missing, a steady-state run makes no image requests at all.
    # New players are fetched a few per run so a squad overhaul never eats the
    # rate limit that the other sources need.
    # a hand-curated URL beats any lookup: it is the one case where somebody
    # has actually looked at the picture and confirmed who is in it
    curated = load_json("player-photo-sources.json") or {}
    used_curated = []
    for p in players:
        for key in (p.get("nameHe"), p.get("name")):
            src = curated.get(key)
            if isinstance(src, dict) and src.get("url"):
                if not (PHOTO_DIR / f"{p['slug']}.jpg").exists():
                    p["photoUrl"] = src["url"]
                    log(f"  curated photo for {key}: {src.get('credit') or src['url'][:60]}")
                # the credit sticks to the player even on later runs, when the
                # file is already on disk and no request is made
                if src.get("credit"):
                    p["photoCredit"] = src["credit"]
                used_curated.append(key)
                break
    stale = [k for k in curated if not k.startswith("_") and k not in used_curated]
    if stale:
        log("  curated photo urls with nobody in the squad (stale?):", stale)

    template = None
    missing = [p for p in players
               if not p.get("photoUrl") and p.get("code")
               and not (PHOTO_DIR / f"{p['slug']}.jpg").exists()]
    log(f"  headshots on disk: {len(players) - len(missing)}/{len(players)}")
    for p in missing[:PHOTO_LOOKUPS_PER_RUN]:
        url, template = photo_url_for(p["code"], template)
        if url:
            p["photoUrl"] = url
        time.sleep(1.5)
    if len(missing) > PHOTO_LOOKUPS_PER_RUN:
        log(f"  {len(missing) - PHOTO_LOOKUPS_PER_RUN} headshots left for the next run")
    if not any(p.get("photoUrl") for p in players):
        hits = photos_from_team_page(players)
        log(f"  headshots matched from team page: {hits}/{len(players)}")
    fetch_photos(players)
    current = load_json("roster.json") or {}
    current["players"] = players
    current["sample"] = False
    save_json("roster.json", current)
    return True

# ---------------------------------------------------------------- main

# ---------------------------------------------------------------- eurocup table

# The group table lives per round. Only rounds that have been reached answer
# with content; the rest return an empty list, so walk down from the top and
# take the first round that has anything in it, that is the current table.
EUROCUP_STANDINGS = ("https://api-live.euroleague.net"
                     "/v2/competitions/U/seasons/U2026/rounds/{r}/standings")
MAX_ROUND = 18

def eurocup_groups():
    for rnd in range(MAX_ROUND, 0, -1):
        try:
            data = json.loads(fetch(EUROCUP_STANDINGS.format(r=rnd)))
        except Exception as e:
            log("eurocup standings round", rnd, "failed:", e)
            continue
        groups = data if isinstance(data, list) else data.get("data") or []
        if groups:
            log(f"eurocup standings: round {rnd}, {len(groups)} groups")
            return rnd, groups
    return None, []

def update_eurocup_standings():
    rnd, groups = eurocup_groups()
    if not groups:
        raise RuntimeError("no eurocup group table returned by any round")

    ours = None
    out = []
    for g in groups:
        info = g.get("group") or {}
        rows = []
        for r in g.get("standings") or []:
            club = r.get("club") or {}
            d = r.get("data") or {}
            name = club.get("name") or club.get("editorialName") or club.get("code")
            rows.append({
                "pos": d.get("position"),
                "team": name,
                "code": club.get("code"),
                "played": d.get("gamesPlayed"),
                "wins": d.get("gamesWon"),
                "losses": d.get("gamesLost"),
                "for": d.get("pointsFavour"),
                "against": d.get("pointsAgainst"),
            })
        rows.sort(key=lambda x: (x["pos"] is None, x["pos"]))
        entry = {"name": info.get("name") or info.get("rawName") or "", "rows": rows}
        out.append(entry)
        if any(r["code"] == "JER" for r in rows):
            ours = entry["name"]

    if not ours:
        # better no table than a table the club is missing from
        raise RuntimeError("eurocup table parsed but our club is not in it")

    out.sort(key=lambda g: (g["name"] != ours, g["name"]))
    log("eurocup groups:", [g["name"] for g in out], "ours:", ours)
    save_json("eurocup.json", {
        "competition": "יורוקאפ",
        "season": "2026/27",
        "round": rnd,
        "ourGroup": ours,
        "groups": out,
    })
    return True

# ---------------------------------------------------------------- season stats

# Per-player season averages, straight from the competition's own feed. Before
# a ball is thrown the list is empty, and the app says so rather than drawing
# a table of zeros.
SEASON_STATS = ("https://api-live.euroleague.net"
                "/v2/competitions/U/seasons/U2026/clubs/JER/people/stats")

def _num(v):
    return round(float(v), 1) if isinstance(v, (int, float)) else None

def update_season_stats():
    try:
        data = json.loads(fetch(SEASON_STATS))
    except Exception as e:
        raise RuntimeError(f"season stats fetch failed: {e}")

    rows = data.get("playerStats") if isinstance(data, dict) else None
    if rows is None:
        rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected season stats envelope: {list(data)[:8]}")

    out = []
    for r in rows:
        person = (r.get("player") or {}).get("person") or r.get("person") or {}
        avg = r.get("averagePerGame") or {}
        tot = r.get("accumulated") or r.get("total") or {}
        name = person.get("name") or person.get("alias")
        if not name:
            continue
        out.append({
            "name": tidy_name(name),
            "games": r.get("gamesPlayed") or tot.get("gamesPlayed"),
            "min": _num(avg.get("timePlayed")),
            "pts": _num(avg.get("points")),
            "reb": _num(avg.get("totalRebounds")),
            "ast": _num(avg.get("assistances") or avg.get("assists")),
            "stl": _num(avg.get("steals")),
            "blk": _num(avg.get("blocksFavour") or avg.get("blocks")),
            "val": _num(avg.get("valuation")),
            "fg2m": _num(avg.get("fieldGoalsMade2")),
            "fg2a": _num(avg.get("fieldGoalsAttempted2")),
            "fg3m": _num(avg.get("fieldGoalsMade3")),
            "fg3a": _num(avg.get("fieldGoalsAttempted3")),
            "ftm": _num(avg.get("freeThrowsMade")),
            "fta": _num(avg.get("freeThrowsAttempted")),
        })

    played = [p for p in out if (p.get("games") or 0) > 0]
    log(f"season stats: {len(out)} players in feed, {len(played)} with minutes")
    if out:
        log("  sample:", json.dumps(out[0], ensure_ascii=False)[:200])

    save_json("season-stats.json", {
        "competition": "יורוקאפ",
        "season": "2026/27",
        "note": "ממוצעים למשחק בתחרות האירופית, מהפיד הרשמי של היורוקאפ.",
        "players": sorted(played, key=lambda p: -(p.get("pts") or 0)),
        "started": bool(played),
    })
    return True

# order matters: the image lookups are the only greedy step, so everything
# that shares the same API budget runs before them
SOURCES = [("standings", update_standings), ("games", update_games),
           ("eurocup", update_eurocup_standings),
           ("seasonStats", update_season_stats),
           ("news", news_feed.update_news),
           ("podcasts", podcast_feed.update_podcasts),
           ("roster", update_roster)]


def main(argv=None):
    """--only news,podcasts אוסף רק חלק מהמקורות.

    האיסוף רץ עכשיו בלולאה ארוכה ולא פעם בכמה שעות, וזה מעלה שאלה של
    דרך ארץ: לוח המשחקים, הטבלה והסגל משתנים אולי פעם ביום, ואין שום
    סיבה לשלוח בשבילם בקשה לאתר הליגה ולאתר המועדון כל עשרים דקות.
    החדשות והפודקאסטים כן זזים במהלך היום, והם גם מגיעים מפידים שנועדו
    לקריאה תכופה.

    לכן הלולאה עושה מעבר קל תכוף ומעבר מלא כל שעתיים, כמו קודם. הדגל
    הזה הוא מה שמאפשר את זה.

    מקור שלא נאסף בריצה הזאת שומר על הסטטוס הקודם שלו ב־meta.json, כדי
    שמעבר קל לא יימחק לאתר את הידיעה שהאיסוף המלא הצליח.
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="",
                    help="רשימת מקורות מופרדת בפסיק. ריק = הכל.")
    args = ap.parse_args(argv)
    wanted = [w.strip() for w in args.only.split(",") if w.strip()]
    known = [n for n, _ in SOURCES]
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise SystemExit(f"מקור לא מוכר: {unknown}. המוכרים: {known}")

    meta = load_json("meta.json") or {"sources": {}}
    ok_any = False
    status = dict(meta.get("sources") or {})
    running = [(n, f) for n, f in SOURCES if not wanted or n in wanted]
    log("אוסף:", ", ".join(n for n, _ in running))
    for name, fn in running:
        try:
            fn()
            status[name] = {"ok": True, "detail": "עודכן בהצלחה"}
            ok_any = True
        except Exception as e:
            log(f"ERROR updating {name}: {e}")
            status[name] = {"ok": False, "detail": str(e)[:300]}

    meta["lastUpdated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    meta["sources"] = status
    # sample flag clears only once real data has replaced the seed
    if ok_any:
        meta["sample"] = False
    save_json("meta.json", meta)
    log("done. any source ok:", ok_any)
    # exit 0 either way, a failed scrape is recorded, not fatal;
    # the workflow commits meta.json so failures are visible in-app history
    return 0

if __name__ == "__main__":
    sys.exit(main())
