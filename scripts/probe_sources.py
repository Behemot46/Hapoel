#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה, 27.9.2026:** גבי ביקש סטטיסטיקה כמה שיותר מלאה על המשחקים. מה
שיש לנו היום הוא שלושה טפסים של משחקי הכנה שהעתקתי ביד מאתר המועדון,
ו־season-stats.json שהוא ממוצעי יורוקאפ בלבד ועדיין ריק כי העונה
האירופית נפתחת ב־29.9. **כלומר לשלושת משחקי הגביע הרשמיים, 8.9, 18.9
ו־25.9, אין שום סטטיסטיקה.** זה הפער.

לפני שכותבים פרסר צריך לדעת מה המקורות באמת מפרסמים, ולכן שלוש שאלות:

  1. **הליגה, basket.co.il.** האם מעמוד הקבוצה אפשר להגיע לעמוד משחק עם
     מזהה, והאם בעמוד המשחק יש טופס מלא? אם כן, יש לנו טפסים לכל משחק
     ישראלי רשמי, אוטומטית, במקום העתקה ביד.
  2. **היורוקאפ, api-live.euroleague.net.** איזה שדה מזהה משחק בפיד
     שאנחנו כבר קוראים, ואיזו כתובת מחזירה טופס? נבדק על משחק שנגמר
     מהעונה הקודמת, כי לנו עוד לא היה משחק אירופי העונה.
  3. ואיזה שדות בכלל יש בטופס, כדי לדעת מה אפשר להציג בלי להמציא.
"""

import json
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as ud

HEAD = "=" * 70


def jshow(o, limit=1400):
    return json.dumps(o, ensure_ascii=False, indent=1)[:limit]


def probe_league():
    print(HEAD, "\n1. basket.co.il: עמוד הקבוצה, ומשם לעמוד משחק\n", HEAD)
    link = ud.find_team_link()
    print("עמוד הקבוצה:", link)
    if not link:
        return
    html = ud.fetch(link)
    soup = BeautifulSoup(html, "html.parser")

    print("\nכל הקישורים שנראים כמו עמוד משחק:")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"(game|match)", href, re.I) and href not in seen:
            seen.add(href)
            print(f"  {(a.get_text(' ', strip=True) or '')[:40]:<40} {href[:110]}")
    if not seen:
        print("  אף אחד. מדפיס כל href ייחודי כדי לראות מה יש:")
        for href in list(dict.fromkeys(a["href"] for a in soup.find_all("a", href=True)))[:40]:
            print("   ", href[:120])

    # המשחק של 25.9 מול בני הרצליה, שהוא הרשמי האחרון שנגמר
    for gid in ("25331",):
        for pat in ("https://basket.co.il/game-zone.asp?GameId={}",
                    "https://basket.co.il/game.asp?GameId={}"):
            url = pat.format(gid)
            print(f"\n--- {url}")
            try:
                r = requests.get(url, headers=ud.UA, timeout=30)
            except Exception as e:
                print("  נפל:", type(e).__name__, e)
                continue
            print(f"  {r.status_code} · {len(r.content)} bytes")
            if r.status_code != 200:
                continue
            r.encoding = r.encoding or "utf-8"
            s = BeautifulSoup(r.text, "html.parser")
            title = (s.title.get_text(strip=True) if s.title else "")
            print("  title:", title[:90])
            tables = s.find_all("table")
            print(f"  {len(tables)} טבלאות")
            for i, tb in enumerate(tables[:14]):
                rows = tb.find_all("tr")
                if not rows:
                    continue
                head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
                print(f"   טבלה {i}: {len(rows)} שורות · כותרות {head[:14]}")
                for row in rows[1:3]:
                    cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
                    if any(cells):
                        print(f"      {cells[:14]}")


EURO = "https://api-live.euroleague.net"


def probe_eurocup():
    print("\n" + HEAD, "\n2. היורוקאפ: איך מזוהה משחק, ומה מחזיר טופס\n", HEAD)
    try:
        data = requests.get(f"{EURO}/v2/competitions/U/seasons/U2026/games",
                            headers=ud.UA, timeout=30).json()
    except Exception as e:
        print("הפיד של העונה נפל:", e)
        data = {}
    raw = data.get("data") if isinstance(data, dict) else data
    if isinstance(raw, list) and raw:
        print("פריט משחק אחד, כל השדות:")
        print(jshow(raw[0], 1800))

    # משחק שנגמר: העונה הקודמת, כי העונה שלנו נפתחת ב־29.9
    print("\nמשחק שנגמר מהעונה הקודמת, כדי שיהיה טופס אמיתי:")
    code = None
    try:
        prev = requests.get(f"{EURO}/v2/competitions/U/seasons/U2025/games",
                            headers=ud.UA, timeout=30).json()
        prow = prev.get("data") if isinstance(prev, dict) else prev
        ours = [g for g in (prow or [])
                if "JER" in (((g.get("local") or {}).get("club") or {}).get("code"),
                             ((g.get("road") or {}).get("club") or {}).get("code"))
                and g.get("played")]
        print(f"  {len(ours)} משחקים שלנו שנגמרו בעונה הקודמת")
        if ours:
            g = ours[0]
            code = g.get("gameCode") or g.get("code") or g.get("gameNumber") or g.get("id")
            print("  נבחר:", g.get("utcDate"), "| מזהים בפריט:",
                  {k: g[k] for k in g if re.search(r"code|id|number", k, re.I)})
    except Exception as e:
        print("  נפל:", e)

    if code is None:
        print("  אין קוד, אי אפשר להמשיך")
        return
    tries = [
        f"{EURO}/v2/competitions/U/seasons/U2025/games/{code}",
        f"{EURO}/v2/competitions/U/seasons/U2025/games/{code}/stats",
        f"{EURO}/v2/competitions/U/seasons/U2025/games/{code}/boxscore",
        f"{EURO}/v2/competitions/U/seasons/U2025/games/{code}/players",
        f"{EURO}/v2/competitions/U/seasons/U2025/games/{code}/report",
        f"{EURO}/v1/games?seasonCode=U2025&gameCode={code}",
        f"{EURO}/v1/boxscore?seasonCode=U2025&gamecode={code}",
        f"{EURO}/v1/playerstats?seasonCode=U2025&gamecode={code}",
    ]
    for url in tries:
        print(f"\n--- {url}")
        try:
            r = requests.get(url, headers=ud.UA, timeout=30)
        except Exception as e:
            print("  נפל:", type(e).__name__, e)
            continue
        ct = r.headers.get("content-type", "")
        print(f"  {r.status_code} · {ct} · {len(r.content)} bytes")
        if r.status_code != 200:
            continue
        if "json" in ct:
            try:
                body = r.json()
            except Exception as e:
                print("  JSON שבור:", e)
                continue
            if isinstance(body, dict):
                print("  מפתחות:", list(body.keys())[:20])
            print(" ", jshow(body, 1500))
        else:
            print("  לא JSON:", re.sub(r"\s+", " ", r.text)[:220])


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "league"):
        probe_league()
    if which in ("all", "euro"):
        probe_eurocup()
