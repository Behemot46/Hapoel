#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם:** ארבע כותרות במדור מדברות על ריימונד אוקון, ניגרי בן 18
שאותר בטורניר כשרונות. אצלנו יש גם מועדון כדורגל בשם ״הפועל ירושלים״,
והחתמת נער ניגרי מטורניר כשרונות היא סיפור בצורת כדורגל. אבל הכותרת
הרביעית משווה אותו להארפר, שהוא הרכז שלנו בכדורסל, ולכן אי אפשר להכריע
מהכותרות.

הכלי הולך לגוף הכתבות עצמן, סופר את המילים ״כדורגל״ ו״כדורסל״ ומדפיס
את ההקשר שסביבן. הקישורים ב־news.json הם הפניות של גוגל, אז צריך
לעקוב אחריהן עד המפרסם האמיתי.
"""

import json
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# מילים שמכריעות. הראשונות הן הענף עצמו, השאר הן ההקשר שסביבו.
FOOT = ["כדורגל", "ליגת העל", "הליגה הלאומית", "שער", "בלם", "חלוץ",
        "קיצוני", "מגרש הדשא", "טוטו"]
BALL = ["כדורסל", "ליגת ווינר", "יורוליג", "יורוקאפ", "סל", "רכז",
        "פורוורד", "סנטר", "ריבאונד"]


def resolve(url):
    """הקישור מ־news.json הוא הפניה של גוגל. עוקבים עד המפרסם."""
    r = requests.get(url, headers={"User-Agent": UA}, timeout=25,
                     allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    final = r.url
    # גוגל מגישה לפעמים דף ביניים עם ריענון או עם קישור בגוף
    if "news.google.com" in final:
        m = re.search(r'https?://(?!news\.google)[^"\'<>\s]+', r.text)
        if m:
            final = m.group(0)
            r = requests.get(final, headers={"User-Agent": UA}, timeout=25)
            r.encoding = r.apparent_encoding or "utf-8"
    return final, r.text


def words(text):
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def main():
    items = json.loads(
        pathlib.Path("app/data/news.json").read_text(encoding="utf-8"))
    items = items["items"] if isinstance(items, dict) else items
    how_many = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4

    for i, it in enumerate(items[:how_many], 1):
        print("=" * 72)
        print(f"{i}. {it.get('source')} | {it.get('title')}")
        try:
            final, html = resolve(it.get("link") or it.get("url"))
        except Exception as e:
            print(f"   נכשל: {e}")
            continue
        print(f"   המפרסם: {final[:120]}")
        body = words(html)
        print(f"   אורך הטקסט: {len(body)} תווים")

        for name, bag in (("כדורגל", FOOT), ("כדורסל", BALL)):
            hits = {w: body.count(w) for w in bag if body.count(w)}
            total = sum(hits.values())
            print(f"   {name}: {total} · {hits or 'אין'}")

        # ההקשר סביב ההופעה הראשונה של כל אחת משתי המילים המכריעות
        for w in ("כדורגל", "כדורסל"):
            j = body.find(w)
            if j >= 0:
                print(f"   ...{body[max(0, j - 90):j + 90]}...")
        # ההקשר סביב שם השחקן, אם הוא מופיע
        for name in ("אוקון", "Okon"):
            j = body.find(name)
            if j >= 0:
                print(f"   [{name}] ...{body[max(0, j - 130):j + 130]}...")
                break


if __name__ == "__main__":
    main()
