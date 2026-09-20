#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שהבדיקה הקודמת סגרה, ואין טעם לנסות שוב:**

  * בפריט של גוגל אין שום כתובת אמיתית. לא ב־link, לא ב־guid, ולא
    ב־source, שמחזיק רק את שורש האתר. גם ה־description מפנה לבדלים.
  * לספורט 5, לספורט 1, ל־ONE ולוואלה אין פיד לפי מדור בשום כתובת
    שניסיתי. מה שקיים במעריב הוא פיד ספורט כללי עם כתבות ישנות, ולא
    אותו אתר.

**ומה שהיא כן גילתה, וזה מה שנמדד כאן:** ה־description של כל פריט הוא
רשימה של הכותרות ש**גוגל עצמה** קיבצה כאותו סיפור. בפריט הראשון ישבו
יחד ״נדים וראסנה כבש שלושער, הפועל ירושלים ניצחה את מכבי פ״ת״, ״זו
הפילוסופיה, להתבסס על שחקני הבית״ ו״המספרים מוכיחים: הפועל ירושלים זו
כבר לא אותה קבוצה״. הראשונה מוכרעת מיד, והשלישית היא אחת משבע הכותרות
שחסמתי ביד ב־20.9.

**ההשערה:** אם באשכול יש כותרת אחת שמוכרעת ככדורגל, כל האשכול כדורגל.

**והמדידה, שני צדדים, ושניהם חייבים להיות טובים:**

  1. כמה משבע הכותרות שחסמתי ביד היו נתפסות ככה.
  2. וכמה כותרות כדורסל אמיתיות היו נופלות. זה התנאי הקשיח.
"""

import html
import re
import sys
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import news_feed

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}

QUERIES = ["הפועל ירושלים", "הפועל ירושלים כדורסל", "הפועל י-ם"]
FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"

# שבע הכותרות שחסמתי ביד ב־20.9, בדיוק כפי שהופיעו
HAND = [
    "המספרים מוכיחים: הפועל ירושלים זו כבר לא אותה קבוצה",
    "מטורף: הכושר האדיר של בן ה-20 מהפועל י-ם",
    "שני שחקני הגנה של הפועל ירושלים הצטרפו לרשימת הפצועים המתארכת",
    "משגע הגנות", "זיו אריה: הפועל ירושלים? מה שהיה לא רלוונטי",
    "המפגש עם הפועל ירושלים? לא רלוונטי",
    "הפועל ירושלים תתארח אצל זיו אריה",
]

LINK_TEXT = re.compile(r'<a href="[^"]*"[^>]*>(.*?)</a>', re.S)


def siblings(desc):
    """הכותרות שגוגל קיבצה יחד עם הפריט, מתוך ה־description."""
    if not desc:
        return []
    inner = html.unescape(desc)
    out = []
    for m in LINK_TEXT.findall(inner):
        t = html.unescape(re.sub(r"<[^>]+>", "", m)).strip()
        if t:
            out.append(t)
    return out


def decided_soccer(title):
    """כותרת שמוכרעת ככדורגל בכללים שכבר יש לנו, בלי החסימות הידניות.

    זה בכוונה לא כל about_us: חסימה ידנית היא לא ראיה, היא זיכרון שלי,
    ואם אשתמש בה כאן המדידה תמדוד את עצמה.
    """
    saved = news_feed._phrases_cache
    news_feed._phrases_cache = ()
    try:
        return not news_feed.about_us(title)
    finally:
        news_feed._phrases_cache = saved


def main():
    seen = {}
    for q in QUERIES:
        url = FEED.format(q=requests.utils.quote(q))
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            root = ET.fromstring(r.text)
        except Exception as e:
            print(f"השאילתה {q} נפלה: {e}")
            continue
        for it in root.findall(".//item"):
            title = news_feed._strip_source(
                it.findtext("title") or "", (it.find("source").text
                                             if it.find("source") is not None else ""))
            if title and title not in seen:
                seen[title] = siblings(it.findtext("description") or "")
    print(f"{len(seen)} כותרות ייחודיות משלוש שאילתות.\n")

    print("=" * 70)
    print("אשכולות שבהם יש הכרעה ככדורגל")
    print("=" * 70)
    caught = {}
    for title, sibs in seen.items():
        group = [title] + [s for s in sibs if s != title]
        proof = [s for s in group if decided_soccer(s)]
        if not proof:
            continue
        for s in group:
            if not decided_soccer(s):
                caught[s] = proof[0]
        print(f"\nהוכחה: {proof[0][:72]}")
        for s in group:
            mark = "מוכרע " if decided_soccer(s) else "נגרר  "
            print(f"  {mark} {s[:72]}")

    print("\n" + "=" * 70)
    print("מה זה היה תופס משבע הכותרות שחסמתי ביד")
    print("=" * 70)
    hit = 0
    for h in HAND:
        got = [k for k in caught if h in k or k in h]
        hit += bool(got)
        print(f"  {'נתפס ' if got else 'פוספס'} {h[:66]}")
    print(f"\n  {hit} מתוך {len(HAND)}")

    print("\n" + "=" * 70)
    print("**התנאי הקשיח:** כותרות שנגררו, ואני צריך לעבור עליהן בעיניים")
    print("=" * 70)
    for s, proof in caught.items():
        print(f"  {s[:74]}")
        print(f"      בגלל: {proof[:66]}")
    if not caught:
        print("  אף אחת")


if __name__ == "__main__":
    main()
