#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה:** ריימונד אוקון, ניגרי בן 18 שאותר בטורניר כשרונות, חתם
ב״הפועל ירושלים״. יש לנו גם מועדון כדורגל באותו שם, וסיפור כזה הוא
בצורת כדורגל. אי אפשר להכריע מהכותרות.

**מה שכבר נוסה ונכשל, כדי שלא ינוסה שוב:** ללכת לקישור שב־news.json.
הוא הפניה של גוגל, והדף שמאחוריו הוא בדל של 267 תווים בלי הכתבה. גם
פענוח base64 של האסימון לא עוזר: הפורמט החדש (AU_yqL...) אטום וצריך
קריאה נוספת לגוגל כדי לפתוח אותו.

**מה שכן עובד:** לשאול את הפיד עצמו על השחקן. אם הוא כדורגלן, כותרת
כלשהי עליו תזכיר ליגה, מגרש או שער, ואם הוא כדורסלן, כותרת תזכיר סל.
בנוסף אנחנו שואלים על מועדון הכדורגל בשמו המלא, כדי לראות איך הפיד
מדבר עליו בכלל.
"""

import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import requests

FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

FOOT = ["כדורגל", "ליגת העל", "הליגה הלאומית", "שער", "שערים", "בלם",
        "חלוץ", "קיצוני", "כבש", "דשא", "בית״ר", "בית\"ר", "מכבי חיפה",
        "הפועל באר שבע", "עירוני", "טוטו"]
BALL = ["כדורסל", "ווינר", "יורוליג", "יורוקאפ", "סל", "רכז", "פורוורד",
        "סנטר", "ריבאונד", "נקודות", "מלחה", "אשדוד"]


def ask(q):
    url = FEED.format(q=urllib.parse.quote(q))
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        src = item.find("{*}source")
        src = (src.text if src is not None else "") or ""
        out.append((title, src, (item.findtext("pubDate") or "")[:16]))
    return out


def verdict(text):
    f = [w for w in FOOT if w in text]
    b = [w for w in BALL if w in text]
    return f, b


def main():
    # ה־workflow מעביר תמיד ״all״ כשלא נבחר משהו אחר, וזו לא שאילתה
    args = [a for a in sys.argv[1:] if a not in ("all", "")]
    queries = args or [
        '"ריימונד אוקון"',
        'אוקון "הפועל ירושלים"',
        '"הפועל ירושלים" כדורגל ניגריה',
    ]
    for q in queries:
        print("=" * 74)
        print(f"שאילתה: {q}")
        try:
            items = ask(q)
        except Exception as e:
            print(f"  נכשלה: {e}")
            continue
        if not items:
            print("  אין תוצאות.")
            continue
        blob = " ".join(t for t, _, _ in items)
        f, b = verdict(blob)
        print(f"  {len(items)} תוצאות · סימני כדורגל: {f or 'אין'} · "
              f"סימני כדורסל: {b or 'אין'}")
        for title, src, when in items[:14]:
            ff, bb = verdict(title)
            mark = "⚽" if ff and not bb else ("🏀" if bb and not ff else "  ")
            print(f"   {mark} {when} · {src[:14]:<14} · {title[:100]}")


if __name__ == "__main__":
    main()
