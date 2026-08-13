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

def find_standings(soup):
    """Find a standings-looking table: a row mentions TEAM and has >=3 numeric cells."""
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 6:
            continue
        team_rows = [r for r in rows if TEAM in r.get_text()]
        if not team_rows:
            continue
        parsed = []
        for r in rows:
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            nums = [c for c in cells if re.fullmatch(r"\d+%?(\.\d+)?", c)]
            name = next((c for c in cells if re.search(r"[א-ת]{3,}", c)), None)
            if name and len(nums) >= 3:
                parsed.append({"team": name, "nums": [parse_int(n) for n in nums]})
        if any(p["team"] == TEAM or TEAM in p["team"] for p in parsed) and len(parsed) >= 6:
            return parsed
    return None

def update_standings():
    html = fetch(LEAGUE_HOME)
    soup = BeautifulSoup(html, "html.parser")
    parsed = find_standings(soup)
    if not parsed:
        # try linked standings pages
        for a in soup.find_all("a", href=True):
            label = a.get_text(strip=True)
            if any(k in label for k in ("טבלה", "טבלת הליגה", "דירוג")):
                try:
                    sub = BeautifulSoup(fetch(requests.compat.urljoin(LEAGUE_HOME, a["href"])), "html.parser")
                except Exception as e:
                    log("standings link failed:", e)
                    continue
                parsed = find_standings(sub)
                if parsed:
                    break
    if not parsed:
        raise RuntimeError("no standings table found containing team name")

    rows = []
    for i, p in enumerate(parsed, start=1):
        nums = p["nums"]
        rows.append({
            "pos": i,
            "team": p["team"],
            "played": nums[0],
            "wins": nums[1],
            "losses": nums[2],
        })
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
    """Extract games from a team page: rows containing a date and two team names."""
    games = []
    for tr in soup.find_all("tr"):
        txt = tr.get_text(" ", strip=True)
        if TEAM not in txt:
            continue
        dm = DATE_RE.search(txt)
        if not dm:
            continue
        day, month, year = (int(x) for x in dm.groups())
        if year < 100:
            year += 2000
        tm = TIME_RE.search(txt)
        hh, mm = (int(x) for x in tm.groups()) if tm else (20, 0)
        sm = SCORE_RE.search(txt)

        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        heb = [c for c in cells if re.search(r"[א-ת]{3,}", c) and not DATE_RE.search(c)]
        opp = next((h for h in heb if TEAM not in h), None)
        if not opp:
            continue

        idx_team = txt.find(TEAM)
        idx_opp = txt.find(opp)
        home = TEAM if idx_team < idx_opp else opp
        away = opp if home == TEAM else TEAM

        game = {
            "id": f"{year:04d}{month:02d}{day:02d}-{re.sub(r'[^א-ת]', '', opp)[:12]}",
            "date": f"{year:04d}-{month:02d}-{day:02d}T{hh:02d}:{mm:02d}:00+03:00",
            "competition": "ליגת ווינר סל",
            "home": home,
            "away": away,
            "venue": None,
            "status": "finished" if sm else "scheduled",
            "homeScore": int(sm.group(1)) if sm else None,
            "awayScore": int(sm.group(2)) if sm else None,
        }
        games.append(game)
    return games

def update_games():
    html = fetch(LEAGUE_HOME)
    soup = BeautifulSoup(html, "html.parser")
    team_link = None
    for a in soup.find_all("a", href=True):
        if TEAM in a.get_text():
            team_link = requests.compat.urljoin(LEAGUE_HOME, a["href"])
            break
    if not team_link:
        raise RuntimeError("no link to team page found on league homepage")
    team_soup = BeautifulSoup(fetch(team_link), "html.parser")
    games = parse_team_games(team_soup)
    if len(games) < 3:
        raise RuntimeError(f"only {len(games)} games parsed — refusing to overwrite")
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
