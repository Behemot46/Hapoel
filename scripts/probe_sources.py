#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה:** מדור החדשות לא הביא אף כותרת חדשה מאז 9.9, וב־12.9 הקבוצה
שיחקה משחק הכנה מול בורג בווילנה. שלושה ימים של שקט ביום שיש בו משחק
הם או אמת, או סינון שאוכל כותרות אמיתיות. צריך להבחין.

הכלי שואל את הפיד בדיוק כמו האיסוף, ואז מריץ את **הסינון עצמו** על כל
כותרת ומדפיס למה היא נפלה. כך רואים אם המקור שקט או שאנחנו חוסמים.
"""

import datetime
import pathlib
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import news_feed

FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}


def why(title):
    """אותם כללים של about_us, אבל מדווחים מי מהם הפיל."""
    flat = news_feed._norm(title)
    if not any(news_feed._norm(w) in flat for w in news_feed.US):
        return "לא מזכיר אותנו בכותרת"
    hit = [w for w in news_feed.NOT_US if news_feed._norm(w) in flat]
    if hit:
        return f"NOT_US: {hit}"
    hit = [w for w in news_feed.soccer_clubs() if news_feed._norm(w) in flat]
    if hit:
        return f"מועדון כדורגל: {hit}"
    hit = [w for w in news_feed.blocked_phrases() if news_feed._norm(w) in flat]
    if hit:
        return f"blockPhrases: {hit}"
    if any(r.search(title) for r in news_feed.SOCCER_ROLE):
        return "SOCCER_ROLE"
    if news_feed._soccer_score(title):
        return "תוצאה שנראית ככדורגל"
    return None


def ask(q):
    r = requests.get(FEED.format(q=urllib.parse.quote(q)), headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        t = (item.findtext("title") or "").strip()
        src = item.find("{*}source")
        src = (src.text if src is not None else "") or ""
        t = news_feed._strip_source(t, src)
        out.append((t, src, news_feed._published(item)))
    return out


def main():
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=4)
    seen = {}
    for q in ['"הפועל ירושלים"', '"הפועל י-ם"', '"הפועל ירושלים" כדורסל',
              '"הפועל ירושלים" בורג', '"הפועל ירושלים" הכנה וילנה']:
        try:
            items = ask(q)
        except Exception as e:
            print(f"שאילתה {q} נכשלה: {e}")
            continue
        print(f"\n{'=' * 74}\n{q} · {len(items)} תוצאות")
        fresh = [(t, s, d) for t, s, d in items if d and d >= cutoff]
        print(f"   מתוכן {len(fresh)} מארבעת הימים האחרונים")
        for t, s, d in fresh:
            if t in seen:
                continue
            seen[t] = True
            r = why(t)
            mark = "נחסם " if r else "עובר "
            print(f"   {mark} {d:%d.%m %H:%M} · {s[:13]:<13} · {t[:78]}")
            if r:
                print(f"          הסיבה: {r}")

    print(f"\n{'=' * 74}")
    print(f"סך הכול {len(seen)} כותרות ייחודיות מארבעת הימים האחרונים.")
    if not seen:
        print("כלומר המקור עצמו שקט, והסינון לא אשם.")


if __name__ == "__main__":
    main()
