"""בדיקת מקורות: לאתר כל כתבה אצל המפרסם שלה, ולקרוא איזה ענף היא.

הסבב הקודם נפל: הקישורים של גוגל ניוז מובילים לעמוד ביניים, והמזהה
שלהם כבר לא מכיל בתוכו את הכתובת המקורית. לכן במקום ללכת אחרי הקישור,
מחפשים את הכותרת עצמה במנוע חיפוש, לוקחים את הכתובת אצל המפרסם,
וקוראים משם.

הסיווג נמדד ולא מנוחש: כמה פעמים מופיעות בגוף העמוד מילים שמסגירות
ענף. עמוד כדורסל מזכיר כדורסל, ריבאונד ויורוליג. עמוד כדורגל מזכיר
שוער, בעיטה, מחצית ואצטדיון.
"""
import json
import pathlib
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

BASKET = ("כדורסל", "יורוליג", "יורוקאפ", "ווינר סל", "פיס ארנה", "ריבאונד",
          "חמישייה", "סלים", "נקודות", "אובראדוביץ", "אוברדוביץ", "מאמן הכדורסל")
SOCCER = ("כדורגל", "שוער", "בעיטה", "פנדל", "קרן", "מחצית", "ליגה לאומית",
          "אצטדיון", "טדי", "בעיטת", "הבקיע", "חלוץ", "קיצוני", "בלם",
          "מגרש הדשא", "ליגת העל בכדורגל")
SKIP = ("google.", "youtube.", "facebook.", "twitter.", "x.com", "duckduckgo")


def log(*a):
    print("[probe]", *a, flush=True)


def find_url(title):
    """הכתובת אצל המפרסם, לפי חיפוש הכותרת המדויקת."""
    q = urllib.parse.quote('"' + title[:90] + '"')
    for engine in (f"https://html.duckduckgo.com/html/?q={q}",
                   f"https://lite.duckduckgo.com/lite/?q={q}"):
        try:
            r = requests.get(engine, headers=UA, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("//duckduckgo.com/l/?uddg="):
                    href = urllib.parse.unquote(
                        urllib.parse.parse_qs(urllib.parse.urlparse("https:" + href).query)
                        .get("uddg", [""])[0])
                if href.startswith("http") and not any(s in href for s in SKIP):
                    return href
        except Exception as e:
            log(f"    מנוע נפל: {e}")
    return ""


def count(text, words):
    return sum(len(re.findall(re.escape(w), text)) for w in words)


items = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["items"]
log(f"{len(items)} פריטים במדור")
for i, it in enumerate(items):
    title = it["title"]
    url = find_url(title)
    if not url:
        log(f"[{i:2}] לא נמצא   | {it['source']} | {title}")
        time.sleep(1.5)
        continue
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.encoding = r.encoding or "utf-8"
        body = re.sub(r"\s+", " ", BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))
        b, s = count(body, BASKET), count(body, SOCCER)
        verdict = "כדורסל " if b > s * 1.5 else ("כדורגל!" if s > b * 1.5 else "לא ברור")
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        log(f"[{i:2}] {verdict} סל:{b:<3} רגל:{s:<3} {host} | {title}")
        if verdict == "כדורגל!":
            log(f"      {url}")
    except Exception as e:
        log(f"[{i:2}] נפל {e} | {title}")
    time.sleep(1.5)
