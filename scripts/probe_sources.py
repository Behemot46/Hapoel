#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שכבר נמצא:** אתר המועדון, hapoel.co.il/games, כן מפרסם שידור לכל
משחק. בגוף העמוד הופיע ״משחק חוץ שידור טרם נקבע״. אתר הליגה לא מפרסם
עמודת שידור, ועמודי לוח השידורים של ספורט 5 ו־ONE מחזירים 404.

**השאלה עכשיו:** באיזה אלמנט יושב הטקסט הזה, ואילו ערכים הוא מקבל.
כדי לבנות פרסר צריך לראות את שניהם, ולא לנחש מחלקה.
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
    print(f"{r.status_code} · {len(r.content)} bytes")
    soup = BeautifulSoup(r.text, "html.parser")
    games = soup.select(".game")
    print(f"{len(games)} כרטיסי משחק\n")

    # 1. המבנה המלא של שלושת הכרטיסים הראשונים, מחלקה ומה כתוב בה
    for n, g in enumerate(games[:3], 1):
        print("=" * 70)
        print(f"כרטיס {n}")
        for el in g.find_all(True):
            cls = " ".join(el.get("class") or [])
            t = txt(el)
            # רק אלמנטים שיש בהם טקסט משלהם, אחרת כל אב מדפיס את כל הבנים
            own = "".join(c for c in el.children if isinstance(c, str)).strip()
            if own and cls:
                print(f"   .{cls:<34} | {t[:60]}")
        print()

    # 2. איפה בדיוק יושבת המילה ״שידור״
    print("=" * 70)
    print("כל אלמנט שהטקסט שלו מכיל ״שידור״, עם שרשרת המחלקות שמעליו")
    seen = collections.Counter()
    for g in games:
        for el in g.find_all(True):
            own = "".join(c for c in el.children if isinstance(c, str)).strip()
            if "שידור" in own or (own and any(
                    w in own for w in ("ספורט", "ONE", "ערוץ", "יס "))):
                chain = " > ".join(
                    "." + " ".join(p.get("class")) if p.get("class") else p.name
                    for p in list(el.parents)[:3][::-1])
                seen[(chain, el.name, " ".join(el.get("class") or []))] += 1
                if seen[(chain, el.name, " ".join(el.get("class") or []))] == 1:
                    print(f"   {chain} > {el.name}.{' '.join(el.get('class') or [])}")
                    print(f"      ״{own[:70]}״")

    # 3. אילו ערכים בכלל מופיעים, ובכמה משחקים
    print("\n" + "=" * 70)
    print("כל הערכים של שדה השידור, לפי שכיחות")
    values = collections.Counter()
    for g in games:
        for el in g.find_all(True):
            own = "".join(c for c in el.children if isinstance(c, str)).strip()
            if own and ("שידור" in own or "ספורט 5" in own or "ONE" in own):
                values[own[:70]] += 1
    for v, c in values.most_common(25):
        print(f"   {c:>3} · ״{v}״")


if __name__ == "__main__":
    main()
