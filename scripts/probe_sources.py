#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שנמצא עד כה:** אתר המועדון מפרסם שידור, והוא יושב בתוך
`.game-type .container .text`, כלומר **אותו סלקטור שממנו club_games.py
כבר לוקח את המגרש** ב־select_one, כלומר רק את הראשון. בכרטיס אחד נראו
שני ערכים: ״פיס ארנה, ירושלים״ ואחריו ״5STARS״.

אתר הליגה לא מפרסם עמודת שידור, ועמודי לוח השידורים של ספורט 5 ושל ONE
מחזירים 404.

**השאלה עכשיו:** מה אוצר המילים המלא של השדות האלה על פני כל 42
הכרטיסים, ובאיזה סדר הם מופיעים. בלי זה אי אפשר לדעת מה מגרש ומה ערוץ.
"""

import collections
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def main():
    r = requests.get("https://hapoel.co.il/games", headers=UA, timeout=30)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    games = soup.select(".game")
    print(f"{len(games)} כרטיסים\n")

    slots = collections.defaultdict(collections.Counter)
    print("=" * 78)
    print("כל כרטיס: תאריך, קבוצות, וכל הערכים של .game-type לפי סדרם")
    for g in games:
        teams = [i.get("alt", "").strip()
                 for i in g.select(".teams-container img") if i.get("alt")]
        when = txt(g.select_one(".date-time"))
        cycle = txt(g.select_one(".cycle"))
        cells = [txt(t) for t in g.select(".game-type .container .text")]
        stadium = txt(g.select_one(".stadium"))
        for i, c in enumerate(cells):
            slots[i][c] += 1
        print(f"  {when[:26]:<26} {cycle[:16]:<16} {' vs '.join(teams)[:38]:<38}")
        print(f"      .stadium={stadium!r}  .text={cells}")

    print("\n" + "=" * 78)
    print("אוצר המילים לפי מיקום. אם מיקום 0 הוא תמיד מגרש ומיקום 1 תמיד")
    print("ערוץ, אפשר לפרסר לפי מיקום. אם לא, צריך לזהות לפי התוכן.")
    for i in sorted(slots):
        print(f"\n  מיקום {i} ({sum(slots[i].values())} הופעות):")
        for v, c in slots[i].most_common(30):
            print(f"     {c:>3} · {v!r}")

    print("\n" + "=" * 78)
    print("וכל ערכי .stadium")
    st = collections.Counter(txt(g.select_one(".stadium")) for g in games)
    for v, c in st.most_common():
        print(f"     {c:>3} · {v!r}")


if __name__ == "__main__":
    main()
