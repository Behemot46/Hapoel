#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם, 12.10.2026:** אחרי המחזור הראשון בליגה טבלת האלופות
עודכנה בנקודות (2 לניצחון, 1 להפסד) אבל ``played``, ``wins`` ו־``losses``
נשארו 0 בכל 14 הקבוצות. כלומר העמודות שמהן הם נקראים אינן מה שהפרסר
חושב. ההערה ב־``find_standings`` אומרת שהכותרת היא
``# | שם הקבוצה | נק' | סה"כ | בית | חוץ | סטט'``, והמאזן מגיע מ־``סה"כ``
בתור ״3-1״.

הכלי מדפיס את הכותרת ואת השורות **מילה במילה**, כולל הבתים הגולמיים של
הכותרות, כדי לראות אם מדובר בעמודה שזזה, בתו מרכאות אחר, או בתא שמחזיק
מאזן בפורמט אחר.
"""
import re
import sys

import requests
from bs4 import BeautifulSoup

URLS = ["https://basket.co.il/table.asp?cYear=2027",
        "https://basket.co.il/table.asp"]


def fetch(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    # הדף מוגש בלי הצהרת קידוד, וזה מה שהתברר במדידה קודמת
    r.encoding = "utf-8"
    return r.text


def main():
    for url in URLS:
        try:
            html = fetch(url)
        except Exception as e:
            print(f"### {url} נפל: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        print(f"\n########## {url}  ({len(html)} תווים)")
        for ti, table in enumerate(soup.find_all("table")):
            rows = table.find_all("tr")
            if len(rows) < 5:
                continue
            flat = table.get_text(" ", strip=True)
            if "קבוצה" not in flat:
                continue
            print(f"\n=== table[{ti}], {len(rows)} שורות")
            for ri, r in enumerate(rows[:18]):
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if not cells:
                    continue
                print(f"  [{ri}] " + " | ".join(f"{j}:{repr(c)}" for j, c in enumerate(cells)))
            if len(rows) > 18:
                print(f"  ... ועוד {len(rows)-18} שורות")


if __name__ == "__main__":
    main()
