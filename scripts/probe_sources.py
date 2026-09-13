#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה:** המשחק השני בטורניר בווילנה, הערב ב־19:30 מול ריטאס וילנה.
איפה הוא משודר.

**מה שכבר נשלל אתמול למשחק הראשון:** אתר הליגה (אין עמודת שידור),
לוחות השידורים של ספורט 5 ושל ONE (404), וערוץ היוטיוב של המועדון
(שנים־עשר הסרטונים האחרונים הם תקצירים, אף שידור חי).

**מה שהשתנה מאז:** היריבה ידועה עכשיו, וריטאס היא המארחת. מועדון מארח
הוא זה שמשדר, ולכן הצד הליטאי הוא המקום לחפש בו. אתמול rytas.lt ענה 200
בלי סימני שידור ובלי קישור ליוטיוב, אבל זה היה לפני שהמשחק התקרב.
"""

import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
HE = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"
EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

WORDS = ["שידור", "משודר", "צפייה ישירה", "לצפייה", "לייב", "ערוץ", "5STARS",
         "ספורט 5", "live", "stream", "tiesiogiai", "transliacija", "tv",
         "youtube", "žiūrėti"]


def get(url, note=""):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        print(f"  {url[:66]} · נכשל: {type(e).__name__}")
        return None
    print(f"  {url[:66]} · {r.status_code} · {len(r.content)} bytes {note}")
    if not r.ok:
        return None
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def look(text, label, needles=("hapoel", "jeruzal", "izrael", "הפועל")):
    soup = BeautifulSoup(text, "html.parser")
    for x in soup(["script", "style", "noscript"]):
        x.decompose()
    flat = re.sub(r"\s+", " ", soup.get_text(" "))
    low = flat.lower()
    found = {w: low.count(w.lower()) for w in WORDS if low.count(w.lower())}
    print(f"     [{label}] {found or 'אין סימני שידור'}")
    for n in needles:
        i = low.find(n.lower())
        if i >= 0:
            print(f"       ״{n}״ ...{flat[max(0, i - 100):i + 150]}...")
            break


def main():
    print("=" * 74)
    print("1. אתר המועדון: אולי הכרטיס של היום קיבל שידור מאז שהיריבה נקבעה")
    t = get("https://hapoel.co.il/games")
    if t:
        soup = BeautifulSoup(t, "html.parser")
        for g in soup.select(".game")[:4]:
            when = re.sub(r"\s+", " ", (g.select_one(".date-time") or soup).get_text(" ")).strip()
            teams = [i.get("alt", "") for i in g.select(".teams-container img") if i.get("alt")]
            cells = [re.sub(r"\s+", " ", c.get_text(" ")).strip()
                     for c in g.select(".game-type .container .text")]
            print(f"     {when[:30]:<30} {' vs '.join(teams)[:34]:<34} {cells}")

    print("\n" + "=" * 74)
    print("2. ריטאס, המארחת. אתר, וערוץ היוטיוב אם מקושר")
    for url in ["https://rytas.lt/", "https://rytas.lt/en/", "https://www.rytas.lt/"]:
        t = get(url)
        if not t:
            continue
        look(t, url.split("/")[2])
        cids = set(re.findall(r'(?:channel/|"channelId":")(UC[\w-]{20,24})', t))
        links = {a["href"].split("?")[0] for a in BeautifulSoup(t, "html.parser")
                 .find_all("a", href=True)
                 if any(s in a["href"] for s in ("youtube.com", "youtu.be", "facebook.com"))}
        print(f"     קישורים חברתיים: {sorted(links)[:5] or 'אין'}")
        print(f"     מזהי ערוץ: {sorted(cids) or 'אין'}")
        for cid in sorted(cids):
            xml = get(YT_RSS.format(cid=cid))
            if not xml:
                continue
            try:
                root = ET.fromstring(xml.encode("utf-8"))
            except Exception:
                continue
            ns = {"a": "http://www.w3.org/2005/Atom"}
            print(f"     ערוץ: {root.findtext('a:title', namespaces=ns)}")
            for e in root.findall("a:entry", ns)[:8]:
                ti = e.findtext("a:title", namespaces=ns) or ""
                wh = (e.findtext("a:published", namespaces=ns) or "")[:10]
                mark = "🔴" if any(w.lower() in ti.lower() for w in WORDS) else "  "
                print(f"       {mark} {wh} · {ti[:80]}")
        break

    print("\n" + "=" * 74)
    print("3. מה העיתונות אומרת")
    for feed, q in ((HE, '"הפועל ירושלים" ריטאס'),
                    (HE, '"הפועל ירושלים" שידור טורניר'),
                    (EN, '"Hapoel Jerusalem" Rytas'),
                    (EN, 'Rytas Vilnius tournament live stream September 2026')):
        try:
            r = requests.get(feed.format(q=urllib.parse.quote(q)), headers=UA, timeout=30)
            root = ET.fromstring(r.content)
            items = [((i.findtext("title") or "").strip(),
                      (i.findtext("pubDate") or "")[:16]) for i in root.iter("item")]
            print(f"\n   {q} · {len(items)} תוצאות")
            for ti, wh in items[:7]:
                mark = "📺" if any(w.lower() in ti.lower() for w in WORDS) else "  "
                print(f"     {mark} {wh} · {ti[:88]}")
        except Exception as e:
            print(f"\n   {q} · נכשל: {type(e).__name__}")


if __name__ == "__main__":
    main()
