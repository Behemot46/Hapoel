#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה:** משחק ההכנה מול בורג בווילנה, 12.9, לא פורסם לו שידור בשום
מקור שנבדק אתמול. האם הוא בכל זאת זמין לצפייה חוקית, למשל בערוץ היוטיוב
של המועדון, אצל מארגן הטורניר, או אצל היריבה.

**מה שכבר נבדק ונשלל אתמול:** אתר המועדון בלוח המשחקים (אין שדה),
אתר הליגה (אין עמודה), לוח השידורים של ספורט 5 ושל ONE (404), והפיד
העיתונאי (46 תוצאות, אף אחת לא מזכירה שידור).

**מה שנבדק כאן:** ערוץ היוטיוב של המועדון דרך פיד ה־RSS שלו, שהוא ציבורי
ולא דורש מפתח; עמודי המועדון מחדש, אולי הודיעו מאז; ומה הפיד אומר על
הטורניר ועל היריבה.
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
YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"

WORDS = ["שידור", "משודר", "צפייה ישירה", "לצפייה", "לייב", "בשידור חי",
         "ערוץ", "5STARS", "ספורט 5", "יוטיוב", "סטרים", "live", "stream"]


def get(url, note=""):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        print(f"  {url[:70]} · נכשל: {e}")
        return None
    print(f"  {url[:70]} · {r.status_code} · {len(r.content)} bytes {note}")
    if not r.ok:
        return None
    r.encoding = "utf-8"
    return r.text


def main():
    print("=" * 76)
    print("1. מה מקושר מאתר המועדון, וממנו מזהה ערוץ היוטיוב")
    html = get("https://hapoel.co.il/")
    cids, links = set(), set()
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if any(s in h for s in ("youtube.com", "youtu.be", "facebook.com",
                                    "instagram.com", "twitter.com", "x.com")):
                links.add(h.split("?")[0])
        for m in re.finditer(r'(?:channel/|"channelId":")(UC[\w-]{20,24})', html):
            cids.add(m.group(1))
        for l in sorted(links):
            print(f"     {l}")
        print(f"     מזהי ערוץ שנמצאו: {sorted(cids) or 'אין'}")

        # אם יש קישור ליוטיוב בלי מזהה, הולכים לעמוד הערוץ ומוציאים משם
        for l in sorted(links):
            if "youtube" in l and not cids:
                page = get(l, "(עמוד הערוץ)")
                if page:
                    for m in re.finditer(r'"(?:channelId|externalId)":"(UC[\w-]{20,24})"', page):
                        cids.add(m.group(1))
                    print(f"     מזהים מעמוד הערוץ: {sorted(cids) or 'אין'}")
                break

    print("\n" + "=" * 76)
    print("2. הסרטונים האחרונים בערוץ. מועדון שמשדר משחק מעלה אותו לכאן.")
    for cid in sorted(cids):
        xml = get(YT_RSS.format(cid=cid))
        if not xml:
            continue
        try:
            root = ET.fromstring(xml.encode("utf-8"))
        except Exception as e:
            print(f"     לא נפרסר: {e}")
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        title = root.findtext("a:title", namespaces=ns)
        print(f"     ערוץ: {title}")
        for e in root.findall("a:entry", ns)[:12]:
            t = e.findtext("a:title", namespaces=ns) or ""
            when = (e.findtext("a:published", namespaces=ns) or "")[:10]
            mark = "🔴" if any(w.lower() in t.lower() for w in WORDS) else "  "
            print(f"       {mark} {when} · {t[:88]}")

    print("\n" + "=" * 76)
    print("3. עמודי המועדון מחדש, אולי הודיעו היום")
    for url in ["https://hapoel.co.il/", "https://hapoel.co.il/news"]:
        t = get(url)
        if not t:
            continue
        soup = BeautifulSoup(t, "html.parser")
        for x in soup(["script", "style"]):
            x.decompose()
        flat = re.sub(r"\s+", " ", soup.get_text(" "))
        for w in ("שידור", "צפייה ישירה", "לייב", "בשידור חי", "יוטיוב"):
            i = flat.find(w)
            if i >= 0:
                print(f"     ״{w}״ ...{flat[max(0, i - 110):i + 130]}...")

    print("\n" + "=" * 76)
    print("4. מה הפיד אומר על שידור הטורניר")
    for q in ['"הפועל ירושלים" שידור וילנה', '"הפועל ירושלים" צפייה ישירה',
              '"הפועל ירושלים" בורג הכנה שידור']:
        try:
            r = requests.get(FEED.format(q=urllib.parse.quote(q)), headers=UA, timeout=30)
            root = ET.fromstring(r.content)
            items = [(i.findtext("title") or "").strip() for i in root.iter("item")]
            print(f"\n   {q} · {len(items)} תוצאות")
            for t in items[:8]:
                mark = "📺" if any(w in t for w in WORDS) else "  "
                print(f"     {mark} {t[:100]}")
        except Exception as e:
            print(f"\n   {q} · נכשל: {e}")


if __name__ == "__main__":
    main()
