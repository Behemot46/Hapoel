"""בדיקת מקורות: מה באמת עומד מאחורי כל כותרת שבמדור.

הסינון קורא כותרת בלבד, וזאת בחירה מודעת: האפליקציה לא מעתיקה תוכן של
אף אחד. אבל כדי לדעת כמה טוב הסינון עובד צריך פעם אחת להסתכל על מה
שמעבר לקישור, וזה מה שקורה כאן, בריצה ידנית ולא באיסוף.

לכל פריט: לאן הקישור מוביל באמת אחרי ההפניות של גוגל, איזה עמוד זה,
וכמה פעמים מופיעות בגוף העמוד מילים שמסגירות ענף. עמוד כדורסל מזכיר
כדורסל, עמוד כדורגל מזכיר שוער ובעיטה. היחס בין השניים הוא הסיווג,
והוא נמדד ולא מנוחש.
"""
import json
import pathlib
import re
import sys
import urllib.parse

import requests
from bs4 import BeautifulSoup

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

BASKET = ("כדורסל", "יורוליג", "יורוקאפ", "ווינר סל", "פיס ארנה", "שלשה",
          "ריבאונד", "חמישייה פותחת", "סל", "אובראדוביץ", "אוברדוביץ")
SOCCER = ("כדורגל", "שוער", "בעיטה", "פנדל", "קרן", "מחצית", "ליגת העל",
          "ליגה לאומית", "שער", "הבקיע", "חלוץ", "קיצוני", "בלם", "אצטדיון",
          "טדי", "קטמון")


def log(*a):
    print("[probe]", *a, flush=True)


def count(text, words):
    return sum(len(re.findall(re.escape(w), text)) for w in words)


items = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["items"]
log(f"{len(items)} פריטים במדור")

for i, it in enumerate(items):
    title = it["title"]
    try:
        r = requests.get(it["url"], headers=UA, timeout=30, allow_redirects=True)
        r.encoding = r.encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        # גוגל מגישה עמוד ביניים שכל תוכנו הוא הפניה בג׳אווהסקריפט
        if "news.google.com" in r.url:
            m = re.search(r'https?://(?!news\.google)[^"\'<> ]{20,}', r.text)
            if m:
                r = requests.get(m.group(0), headers=UA, timeout=30)
                r.encoding = r.encoding or "utf-8"
                soup = BeautifulSoup(r.text, "html.parser")
                body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        b, s = count(body, BASKET), count(body, SOCCER)
        verdict = "כדורסל" if b > s * 1.5 else ("כדורגל" if s > b * 1.5 else "לא ברור")
        host = urllib.parse.urlparse(r.url).netloc.replace("www.", "")
        path = urllib.parse.urlparse(r.url).path[:60]
        log(f"[{i:2}] {verdict:<8} סל:{b:<3} רגל:{s:<3} {host}{path}")
        log(f"      {title}")
    except Exception as e:
        log(f"[{i:2}] נפל: {e}")
        log(f"      {title}")
