#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**התסמין:** מדור החדשות קפא על 9.9. הקובץ נכתב מחדש בכל איסוף, הפריטים
מסתדרים מהחדש לישן, ובכל זאת הפריט החדש ביותר הוא מלפני שלושה ימים.
בינתיים הקבוצה ניצחה את בורג ב־12.9, ושתי כותרות על זה קיימות בגוגל
**ועוברות את הסינון שלנו**, כפי שנמדד בפרוב הקודם.

**ההבדל היחיד בין הפרוב שמצא אותן לאיסוף שלא:** קידוד השאילתה. האיסוף
משתמש ב־quote_plus, כלומר רווח הופך ל־+, והפרוב השתמש ב־quote, כלומר
%20. בתוך מרכאות זה יכול להיות ההבדל בין ביטוי לחיפוש מילולי.

הכלי שולח את אותה שאילתה בשני הקידודים ומשווה מה חוזר.
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


def fetch(q, enc):
    url = FEED.format(q=enc(q))
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    items = ET.fromstring(r.text.encode("utf-8")).findall(".//item")
    out = []
    for it in items:
        src_el = it.find("source")
        src = news_feed._clean(src_el.text if src_el is not None else "")
        title = news_feed._strip_source(
            news_feed._clean(it.findtext("title")), src)
        when = news_feed._published(it)
        out.append((title, src, when))
    return url, out


def main():
    cfg = news_feed._config()
    print(f"maxItems={cfg['maxItems']} · maxAgeDays={cfg['maxAgeDays']}")
    now = datetime.datetime.now(datetime.timezone.utc)

    for q in cfg["queries"]:
        print("\n" + "=" * 74)
        print(f"שאילתה: {q}")
        for name, enc in (("quote_plus, כמו באיסוף", urllib.parse.quote_plus),
                          ("quote, כמו בפרוב", urllib.parse.quote)):
            try:
                url, items = fetch(q, enc)
            except Exception as e:
                print(f"  {name}: נכשל {e}")
                continue
            ok = [(t, s, d) for t, s, d in items if d and news_feed.about_us(t)]
            ok.sort(key=lambda x: x[2], reverse=True)
            print(f"  {name}")
            print(f"     {url[:96]}")
            if not ok:
                print(f"     {len(items)} פריטים · אף אחד לא עובר את הסינון")
                continue
            newest = ok[0][2]
            age = (now - newest).total_seconds() / 3600
            print(f"     {len(items)} פריטים · {len(ok)} עוברים · "
                  f"החדש ביותר {newest:%d.%m %H:%M}, לפני {age:.1f} שעות")
            for t, s, d in ok[:4]:
                print(f"       {d:%d.%m %H:%M} · {s[:13]:<13} · {t[:66]}")


if __name__ == "__main__":
    main()
