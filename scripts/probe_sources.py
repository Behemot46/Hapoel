#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**מה שכבר נשלל למשחק ההכנה מול בורג בווילנה, 12.9:**

  * אתר המועדון, לוח המשחקים: אין שדה שידור למשחק הזה.
  * אתר המועדון, עמוד הבית והחדשות: המילים ״שידור״, ״צפייה ישירה״,
    ״לייב״ ו״יוטיוב״ לא מופיעות בהם בכלל.
  * ערוץ היוטיוב של המועדון (UCM2ng9CAAebh7NIK_CmcsxA): שנים־עשר
    הסרטונים האחרונים, עד 13.7.2026, הם תקצירים וקטעי מועדון. **אין בהם
    אף שידור חי ואף משחק מלא**, והקרוב ביותר הוא ״סיכום משחק ההכנה נגד
    העמק״ שעלה יומיים אחרי המשחק.
  * אתר הליגה, לוח השידורים של ספורט 5 ושל ONE, והפיד העיתונאי.

**מה שנשאר, וזו השאלה כאן:** הצד הליטאי. הטורניר מתקיים בווילנה, והמארגן
או האולם או היריבה עשויים לשדר בעצמם. היריבה זוהתה מהפיד: ״בורג זכתה
ביורוקאפ״, כלומר JL Bourg הצרפתית.
"""

import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"

WORDS = ["live", "stream", "broadcast", "watch", "tv", "youtube",
         "tiesiogiai", "transliacija", "direct", "diffusion"]


def get(url, note=""):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        print(f"  {url[:72]} · נכשל: {type(e).__name__}")
        return None
    print(f"  {url[:72]} · {r.status_code} · {len(r.content)} bytes {note}")
    if not r.ok:
        return None
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def hits(text, label):
    soup = BeautifulSoup(text, "html.parser")
    for x in soup(["script", "style", "noscript"]):
        x.decompose()
    flat = re.sub(r"\s+", " ", soup.get_text(" "))
    low = flat.lower()
    found = {w: low.count(w) for w in WORDS if low.count(w)}
    print(f"     [{label}] {found or 'אין סימני שידור'}")
    for w in ("hapoel", "jeruzal", "jerusalem", "bourg"):
        i = low.find(w)
        if i >= 0:
            print(f"       ״{w}״ ...{flat[max(0, i - 90):i + 120]}...")
            break


def main():
    print("=" * 76)
    print("1. אתרים ליטאיים וצרפתיים שעשויים לשדר בעצמם")
    for url in ["https://www.rytas.lt/", "https://rytas.lt/en/",
                "https://www.jlbourgbasket.com/", "https://lkl.lt/en",
                "https://www.activevilnius.lt/"]:
        t = get(url)
        if t:
            hits(t, url.split("/")[2])

    print("\n" + "=" * 76)
    print("2. ערוצי יוטיוב של הליגה הליטאית ושל ריטאס, אם מקושרים")
    for url in ["https://www.rytas.lt/", "https://lkl.lt/en"]:
        t = get(url, "(לחיפוש מזהה ערוץ)")
        if not t:
            continue
        cids = set(re.findall(r'(?:channel/|"channelId":")(UC[\w-]{20,24})', t))
        print(f"     מזהים: {sorted(cids) or 'אין'}")
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
                t2 = e.findtext("a:title", namespaces=ns) or ""
                when = (e.findtext("a:published", namespaces=ns) or "")[:10]
                print(f"       {when} · {t2[:82]}")

    print("\n" + "=" * 76)
    print("3. מה העיתונות הבינלאומית אומרת על הטורניר")
    for q in ['"Hapoel Jerusalem" Vilnius tournament',
              '"Hapoel Jerusalem" "JL Bourg"',
              'Vilnius preseason basketball tournament 2026 stream']:
        try:
            r = requests.get(EN.format(q=urllib.parse.quote(q)), headers=UA, timeout=30)
            root = ET.fromstring(r.content)
            items = [((i.findtext("title") or "").strip(),
                      (i.findtext("pubDate") or "")[:16]) for i in root.iter("item")]
            print(f"\n   {q} · {len(items)} תוצאות")
            for t2, when in items[:8]:
                mark = "📺" if any(w in t2.lower() for w in WORDS) else "  "
                print(f"     {mark} {when} · {t2[:92]}")
        except Exception as e:
            print(f"\n   {q} · נכשל: {type(e).__name__}")


if __name__ == "__main__":
    main()
