"""The squad as the club itself publishes it.

The EuroCup feed only knows the ten players registered for Europe, in Latin
transliteration and with no birth dates. hapoel.co.il/team carries the whole
squad, including the Israeli players who never appear in the European
registration, with Hebrew names, shirt numbers and dates of birth.

The page is server-rendered, and each player appears as a pair of links to
the league's own player page:

    <a href="player.asp?PlayerId=26038">1</a>
    <a href="player.asp?PlayerId=26038">ג'ארד הארפר</a>

so the id groups the number with the name, and the birth date lives in the
same card. Everything here is logged loudly, because the day the club
redesigns its site this is what will need recalibrating.
"""
import re

from bs4 import BeautifulSoup

TEAM_URL = "https://hapoel.co.il/team"
PLAYER_ID = re.compile(r"PlayerId=(\d+)")
DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./]((?:19|20)\d{2})\b")
HEIGHT = re.compile(r"\b(1\.\d{2}|[12]\d{2})\b")


def _hebrew(s):
    return bool(re.search(r"[א-ת]", s or ""))


def _card_of(tag, depth=6):
    """Climb to the smallest ancestor that holds a birth date, that is the
    player's card, whatever the site chooses to call its CSS classes."""
    node = tag
    for _ in range(depth):
        node = node.parent
        if node is None:
            return None
        if DATE.search(node.get_text(" ", strip=True)):
            return node
    return None


def parse_team_page(html, log=print):
    soup = BeautifulSoup(html, "html.parser")
    by_id = {}

    for a in soup.find_all("a", href=True):
        m = PLAYER_ID.search(a["href"])
        if not m:
            continue
        pid = m.group(1)
        txt = a.get_text(" ", strip=True)
        rec = by_id.setdefault(pid, {"clubId": pid, "name": None, "number": None,
                                     "born": None, "birthDate": None, "anchor": a})
        if txt.isdigit() and rec["number"] is None:
            rec["number"] = int(txt)
        elif _hebrew(txt) and not rec["name"]:
            rec["name"] = txt

    log(f"  club page: {len(by_id)} distinct player ids")

    for pid, rec in by_id.items():
        card = _card_of(rec.pop("anchor"))
        if not card:
            continue
        text = card.get_text(" | ", strip=True)
        d = DATE.search(text)
        if d:
            day, month, year = (int(x) for x in d.groups())
            rec["birthDate"] = f"{year:04d}-{month:02d}-{day:02d}"
            rec["born"] = year
        # height shows up as either 2.01 or 201 depending on the card
        for h in HEIGHT.findall(text):
            v = float(h)
            cm = int(v * 100) if v < 3 else int(v)
            if 165 <= cm <= 230:
                rec["height"] = cm
                break

    players = [r for r in by_id.values() if r.get("name")]
    players.sort(key=lambda r: (r["number"] is None, r["number"] or 0))
    for r in players:
        log(f"    #{str(r['number'] or '-'):>2} {r['name'][:26]:<26} "
            f"born={r.get('birthDate') or '-'} h={r.get('height') or '-'} id={r['clubId']}")
    missing = [r for r in by_id.values() if not r.get("name")]
    if missing:
        log(f"  {len(missing)} ids without a Hebrew name (ignored): "
            f"{[r['clubId'] for r in missing][:8]}")
    return players


def fetch_team(fetch, log=print):
    """fetch() is injected so this module stays importable without network."""
    html = fetch(TEAM_URL)
    log(f"  club team page: {len(html)} chars")
    return parse_team_page(html, log=log)
