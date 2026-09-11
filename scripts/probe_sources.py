#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שכבר הוכרע:** אתר המועדון מפרסם שידור בתוך
`.game-type .container .text`, במיקום השני אחרי המגרש. על פני 42
כרטיסים הוא מופיע שלוש פעמים בלבד: ״5STARS״ פעם אחת (הגביע ב־18.9),
ו״שידור טרם נקבע״ פעמיים. אתר הליגה לא מפרסם שידור, ועמודי לוח
השידורים של ספורט 5 ושל ONE מחזירים 404.

**השאלה שנשארה:** משחקי ההכנה בווילנה, 12.9 ו־13.9, מופיעים בלי שום
שידור. האם הם משודרים בכלל, ואם כן איפה. מועדון מודיע על צפייה ישירה
בעמוד החדשות שלו או בכותרות, ולא בלוח המשחקים.
"""

import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"

WORDS = ["שידור", "משודר", "צפייה ישירה", "לצפייה", "לייב", "בשידור חי",
         "ערוץ", "5STARS", "ספורט 5", "יוטיוב", "youtube", "סטרים", "stream"]


def look(text, label):
    soup = BeautifulSoup(text, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    flat = re.sub(r"\s+", " ", soup.get_text(" "))
    found = {w: flat.count(w) for w in WORDS if flat.count(w)}
    print(f"  [{label}] {found or 'אין סימני שידור'}")
    for w in WORDS:
        i = flat.find(w)
        if i >= 0:
            print(f"     ״{w}״ ...{flat[max(0, i - 100):i + 120]}...")


def main():
    print("=" * 74)
    print("1. עמודי המועדון: אולי ההודעה על השידור יושבת בחדשות ולא בלוח")
    for url in ["https://hapoel.co.il/", "https://hapoel.co.il/news",
                "https://hapoel.co.il/articles"]:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.encoding = "utf-8"
            print(f"\n--- {url} · {r.status_code} · {len(r.content)} bytes")
            if r.ok:
                look(r.text, url)
        except Exception as e:
            print(f"\n--- {url} · נכשל: {e}")

    print("\n" + "=" * 74)
    print("2. מה הפיד אומר על הטורניר בווילנה")
    for q in ['"הפועל ירושלים" וילנה', '"הפועל ירושלים" טורניר הכנה ליטא',
              '"הפועל ירושלים" בורג']:
        try:
            r = requests.get(FEED.format(q=urllib.parse.quote(q)),
                             headers=UA, timeout=30)
            root = ET.fromstring(r.content)
            items = [(i.findtext("title") or "").strip() for i in root.iter("item")]
            print(f"\n--- {q} · {len(items)} תוצאות")
            for t in items[:10]:
                mark = "📺" if any(w in t for w in WORDS) else "  "
                print(f"   {mark} {t[:105]}")
        except Exception as e:
            print(f"\n--- {q} · נכשל: {e}")


if __name__ == "__main__":
    main()
