"""בדיקת מקורות: האם מילת שלילה בשאילתה חותכת את הכדורגל במקור.

הכותרות שנכנסות בטעות הן כדורגל של הקבוצה שחולקת את השם, וחלקן כתובות
בלי אף מילה שמסגירה את הענף: ״הפועל י-ם גברה על מכבי פ״ת״, ״השינוי
המסתמן בהרכב מכבי תל אביב מול הפועל ירושלים״. רשימת מילים אף פעם לא
תדביק את זה, כי כל כותרת כזאת היא מילה חדשה.

אבל גוגל מחפשת בכל הכתבה, לא בכותרת. כתבה על משחק כדורגל כמעט תמיד
מכילה את המילה כדורגל איפשהו: מדור, תגית, גוף הידיעה. אז זו השאלה
שנמדדת כאן: מה מפילה ״-כדורגל״ בשאילתה, וכמה כתבות כדורסל אמיתיות היא
מפילה יחד איתן.

מודפס הכול, כי את התשובה קוראים בעיניים ולא סופרים.
"""
import datetime
import email.utils
import html
import json
import pathlib
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import news_feed

UA = news_feed.UA
RSS = "https://news.google.com/rss/search"

QUERIES = [
    '"הפועל ירושלים"',
    '"הפועל ירושלים" -כדורגל',
    '"הפועל י-ם"',
    '"הפועל י-ם" -כדורגל',
]

# הכותרות שכבר ידוע שהן כדורגל, מהריצות היבשות של היום
KNOWN_SOCCER = ("מכבי פ", "שלושער", "(נוער)", "בהרכב", "שחקני הרכב")


def log(*a):
    print("[probe]", *a, flush=True)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)

for q in QUERIES:
    url = RSS + "?q=" + urllib.parse.quote_plus(q) + "&hl=iw&gl=IL&ceid=IL:iw"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        items = ET.fromstring(r.text.encode("utf-8")).findall(".//item")
    except Exception as e:
        log(f"{q}: נפל, {e}")
        continue

    kept, raw = [], 0
    for it in items:
        raw += 1
        src = it.find("source")
        src_raw = clean(src.text if src is not None else "")
        title = news_feed._strip_source(clean(it.findtext("title")), src_raw)
        when = news_feed._published(it)
        if not title or when is None or when < cutoff:
            continue
        if not news_feed.about_us(title):
            continue
        kept.append((when, src_raw, title))

    kept.sort(reverse=True)
    log(f"===== {q} =====")
    log(f"{raw} פריטים, {len(kept)} עוברים את הסינון הקיים")
    for when, src, title in kept:
        mark = "  <== חשוד ככדורגל" if any(w in title for w in KNOWN_SOCCER) else ""
        log(f"  {when:%Y-%m-%d}  {src:<14.14} {title[:100]}{mark}")
