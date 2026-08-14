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

import requests
from bs4 import BeautifulSoup

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

def fetch(url):
    log("GET", url)
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

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
SCORE_RE = re.compile(r"(\d{2,3})\s*[-–:]\s*(\d{2,3})")

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
            tm = TIME_RE.search(cell(j_time))
            hh, mm = (int(x) for x in tm.groups()) if tm else (20, 0)
            home_raw, away_raw = cell(j_home), cell(j_away)
            if not home_raw or not away_raw:
                continue
            if not (is_us(home_raw) or is_us(away_raw)):
                continue
            # NOTE: score order vs. host/guest still unverified — no finished
            # games on the page yet; recheck when first results appear
            sm = SCORE_RE.search(cell(j_score))
            opp = away_raw if is_us(home_raw) else home_raw

            games.append({
                "id": f"{year:04d}{month:02d}{day:02d}-{re.sub(r'[^א-ת]', '', opp)[:12]}",
                "date": f"{year:04d}-{month:02d}-{day:02d}T{hh:02d}:{mm:02d}:00+03:00",
                "competition": cell(j_stage) or "ליגת ווינר סל",
                "home": TEAM if is_us(home_raw) else home_raw,
                "away": TEAM if is_us(away_raw) else away_raw,
                "venue": None,
                "status": "finished" if sm else "scheduled",
                "homeScore": int(sm.group(1)) if sm else None,
                "awayScore": int(sm.group(2)) if sm else None,
            })
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
        raise RuntimeError("no games parsed — refusing to overwrite (see DIAG lines)")
    games.sort(key=lambda g: g["date"])
    log("games parsed:", len(games))
    current = load_json("games.json") or {}
    current["games"] = games
    save_json("games.json", current)
    return True

# ---------------------------------------------------------------- main

def main():
    meta = load_json("meta.json") or {"sources": {}}
    ok_any = False
    status = {}
    for name, fn in [("standings", update_standings), ("games", update_games)]:
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
    # exit 0 either way — a failed scrape is recorded, not fatal;
    # the workflow commits meta.json so failures are visible in-app history
    return 0

if __name__ == "__main__":
    sys.exit(main())
