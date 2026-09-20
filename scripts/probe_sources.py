#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה, אחרי בדיקת התחזוקה של 20.9:** שבע מתוך שלושים הכותרות במדור
היו כדורגל, כולן מהסיקור של מכבי פתח תקווה מול מועדון הכדורגל שחולק
איתנו את השם. חסמתי את כולן ביד, וזו הפעם השלישית שאני עושה את זה.

**מה שגיליתי בדרך, וזה מה שהכלי בא למדוד:** המפרסמים עצמם יודעים בדיוק
מה הענף, והם כותבים את זה בכתובת. בספורט 1 הכתבות האלה יושבות תחת
israeli-soccer/ligat-haal, ובספורט 5 הן ב־FolderID=64 בעוד שכתבות
הכדורסל שלנו ב־FolderID=274. זה נתון ודאי, לא ניחוש מהכותרת.

אנחנו לא רואים את הכתובת הזאת, כי גוגל מחזירה בדל אטום. לכן שלוש שאלות:

  1. האם בפריט של גוגל יש **איפשהו** את הכתובת האמיתית, בשדה שאנחנו לא
     קוראים היום? מודפס כאן ה־XML הגולמי של פריט אחד, כולו.
  2. האם לספורט 5 ולספורט 1 יש פיד משלהם לפי מדור? אם כן, אפשר למשוך
     את פיד הכדורגל ולחסום כל כותרת שמופיעה בו. זו ראיה חיובית לכדורגל,
     ולכן הכיוון הבטוח: היא לעולם לא תחסום כותרת כדורסל.
  3. ואם יש פיד, האם הכותרת בו זהה לכותרת שגוגל מראה לנו? אם גוגל
     משכתבת, ההצלבה לא תעבוד, וצריך לדעת את זה לפני ולא אחרי.
"""

import re
import sys
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}

GOOGLE = ("https://news.google.com/rss/search?"
          "q=%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D"
          "&hl=iw&gl=IL&ceid=IL:iw")

# כתובות מועמדות. אין לי דרך לדעת מראש מה קיים, אז שואלים את כולן
# ומדפיסים את התשובה כמו שהיא.
CANDIDATES = [
    ("ספורט 5, מדור 64 (כדורגל?)", "https://www.sport5.co.il/rss.aspx?FolderID=64"),
    ("ספורט 5, מדור 274 (כדורסל?)", "https://www.sport5.co.il/rss.aspx?FolderID=274"),
    ("ספורט 5, rss כללי", "https://www.sport5.co.il/rss.aspx"),
    ("ספורט 5, RSS.aspx?FolderID=64", "https://www.sport5.co.il/RSS.aspx?FolderID=64"),
    ("ספורט 1, כדורגל ישראלי", "https://sport1.maariv.co.il/israeli-soccer/rss"),
    ("ספורט 1, rss.xml", "https://sport1.maariv.co.il/rss.xml"),
    ("ספורט 1, feed", "https://sport1.maariv.co.il/feed"),
    ("מעריב, rss כללי", "https://www.maariv.co.il/Rss/RssFeedsSport"),
    ("ONE, rss", "https://www.one.co.il/cat/rss/rss.aspx"),
    ("וואלה ספורט, rss", "https://rss.walla.co.il/feed/21"),
]


def head_of(text, n=400):
    return re.sub(r"\s+", " ", text)[:n]


def probe_google():
    print("=" * 70)
    print("1. פריט גולמי אחד מגוגל, כל השדות")
    print("=" * 70)
    try:
        r = requests.get(GOOGLE, headers=UA, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
    except Exception as e:
        print("נפל:", e)
        return
    root = ET.fromstring(r.text)
    items = root.findall(".//item")
    print(f"{len(items)} פריטים. הראשון, כמו שהוא:\n")
    if items:
        raw = ET.tostring(items[0], encoding="unicode")
        print(raw[:2500])
    print("\nוכל הכותרות, כדי לראות אם כדורגל בפנים עכשיו:")
    for it in items[:25]:
        print("  ", (it.findtext("title") or "")[:100])


def probe_feeds():
    print("\n" + "=" * 70)
    print("2. האם למפרסמים יש פיד לפי מדור")
    print("=" * 70)
    for name, url in CANDIDATES:
        try:
            r = requests.get(url, headers=UA, timeout=25)
        except Exception as e:
            print(f"\n{name}\n  {url}\n  נפל: {type(e).__name__}: {e}")
            continue
        ctype = r.headers.get("content-type", "")
        print(f"\n{name}\n  {url}\n  {r.status_code} · {ctype} · {len(r.content)} bytes")
        if r.status_code != 200:
            continue
        r.encoding = r.encoding or "utf-8"
        body = r.text
        if "xml" not in ctype and not body.lstrip().startswith("<?xml"):
            print("  לא XML:", head_of(body, 160))
            continue
        try:
            root = ET.fromstring(body)
        except Exception as e:
            print("  XML שבור:", e)
            continue
        items = root.findall(".//item")
        print(f"  {len(items)} פריטים")
        for it in items[:8]:
            title = (it.findtext("title") or "")[:78]
            link = (it.findtext("link") or "")[:95]
            print(f"    {title}")
            print(f"      {link}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "google"):
        probe_google()
    if which in ("all", "feeds"):
        probe_feeds()
