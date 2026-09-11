#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה:** איפה משודר כל משחק, ובאיזה ערוץ. אין לנו היום שום שדה כזה,
ולכן השאלה הראשונה היא בכלל האם מישהו מהמקורות שאנחנו כבר קוראים מפרסם
את זה, ואם לא, מי כן.

הכלי לא מחפש מילה אחת אלא מדפיס מבנה: כמה עמודות יש בטבלת המשחקים של
אתר הליגה ומה כתוב בכל אחת, מה יש בעמוד המשחקים של המועדון, ואיזה
עמודי לוח שידורים בכלל עונים.
"""

import re
import sys

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}

# מילים שמסגירות שידור, בעברית ובאנגלית
TV = ["שידור", "ערוץ", "משודר", "לצפייה", "שידורים", "ספורט 5", "sport5",
      "sport 5", "ONE", "צפייה ישירה", "לייב", "broadcast", "tv", "live on",
      "יס", "הוט", "cellcom", "סלקום", "פרטנר"]


def get(url, note=""):
    print(f"\n--- GET {url}  {note}")
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        print(f"    נכשל: {e}")
        return None
    print(f"    {r.status_code} · {len(r.content)} bytes · "
          f"content-type={r.headers.get('content-type','?')[:40]}")
    if r.status_code >= 400:
        return None
    # האתרים האלה מצהירים UTF-8 רק בתגית, ובלי זה העברית חוזרת ג'יבריש
    r.encoding = "utf-8"
    return r.text


def hits(text, label):
    soup = BeautifulSoup(text, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    flat = re.sub(r"\s+", " ", soup.get_text(" "))
    found = {w: flat.count(w) for w in TV if flat.count(w)}
    print(f"    [{label}] סימני שידור: {found or 'אין'}")
    for w in ("שידור", "ערוץ", "משודר"):
        i = flat.find(w)
        if i >= 0:
            print(f"      ...{flat[max(0,i-110):i+110]}...")
    return flat


def league_table(text):
    """טבלת המשחקים של אתר הליגה: כמה עמודות, ומה יושב בכל אחת."""
    soup = BeautifulSoup(text, "html.parser")
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        if len(rows) < 4:
            continue
        widths = {len(r.find_all(["td", "th"])) for r in rows}
        if max(widths) < 4:
            continue
        print(f"    טבלה עם {len(rows)} שורות, רוחב {sorted(widths)}")
        for r in rows[:4]:
            cells = [re.sub(r"\s+", " ", c.get_text(" ")).strip()[:34]
                     for c in r.find_all(["td", "th"])]
            print("      | " + " | ".join(cells))
        break


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "all")

    print("=" * 74)
    print("1. אתר הליגה, עמוד הקבוצה. האם יש עמודת שידור בטבלה?")
    t = get("https://basket.co.il/team.asp?TeamId=2114", "(המקור שאנחנו כבר קוראים)")
    if t:
        league_table(t)
        hits(t, "basket.co.il/team")

    print("\n" + "=" * 74)
    print("2. אתר המועדון, עמוד המשחקים")
    t = get("https://hapoel.co.il/games", "(המקור השני שאנחנו קוראים)")
    if t:
        hits(t, "hapoel.co.il/games")

    print("\n" + "=" * 74)
    print("3. עמודי לוח שידורים: מי בכלל עונה")
    for url in [
        "https://www.sport5.co.il/tv",
        "https://www.sport5.co.il/schedule",
        "https://www.sport5.co.il/broadcasts",
        "https://www.one.co.il/cat/tv/",
        "https://basket.co.il/games.asp",
        "https://basket.co.il/schedule.asp",
        "https://www.winner-league.co.il/",
    ]:
        t = get(url)
        if t:
            hits(t, url.split("/")[2])


if __name__ == "__main__":
    main()
