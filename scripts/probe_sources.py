#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**החשד:** שתי כותרות מ־16.9 בבוקר נכנסו למדור:

    ״שוב חוזר הניגון: תסכול עמוק בהפועל ירושלים״
    ״הפועל ירושלים שוב חזרה, ושוב מתוסכלת: היה משחק שלנו״

שתיהן מדברות על משחק שזה עתה נגמר. **לקבוצת הכדורסל שלנו לא היה משחק
ב־15.9:** האחרון היה מול ריטאס ב־13.9 והבא הוא הגביע ב־18.9. כלומר או
שהן על מועדון הכדורגל שחולק איתנו את השם, או שאני מפספס משהו.

זה לא מספיק כדי להכריע, ולכן הכלי שואל את הפיד מה עוד פורסם באותו יום
ומחפש את ההקשר: יריבה, ליגה, מחזור, או שם של שחקן מהסגל שלנו.
"""

import datetime
import json
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

FOOT = ["כדורגל", "ליגת העל", "ליגה לאומית", "שער", "שערים", "הבקיע", "כבש",
        "בעיטה", "פנדל", "שוער", "הרכב", "מחצית", "דקה ה", "טבריה", "בית\"ר",
        "מכבי חיפה", "הפועל באר שבע", "עירוני", "סכנין", "אשדוד ", "נתניה"]
BALL = ["כדורסל", "יורוקאפ", "יורוליג", "ווינר", "סל", "ריבאונד", "שלשה",
        "רבע", "נקודות", "פיס ארנה", "ריטאס", "הכנה"]


def roster_names():
    r = json.loads((news_feed.DATA / "roster.json").read_text(encoding="utf-8"))
    out = set()
    for p in r["players"]:
        he = (p.get("nameHe") or "").split()
        out.update(w for w in he if len(w) > 3)
    return out


def ask(q):
    r = requests.get(FEED.format(q=urllib.parse.quote(q)), headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        src_el = it.find("{*}source")
        src = (src_el.text if src_el is not None else "") or ""
        title = news_feed._strip_source(
            news_feed._clean(it.findtext("title")), src)
        out.append((title, src, news_feed._published(it)))
    return out


def main():
    names = roster_names()
    print(f"שמות מהסגל לזיהוי: {sorted(names)[:8]} ...\n")
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)

    seen = {}
    for q in ['"הפועל ירושלים"', '"הפועל ירושלים" תסכול',
              '"הפועל ירושלים" 15 בספטמבר', '"הפועל ירושלים" כדורגל']:
        try:
            items = ask(q)
        except Exception as e:
            print(f"{q}: נכשל {e}")
            continue
        fresh = [(t, s, d) for t, s, d in items if d and d >= cutoff]
        print(f"{'=' * 76}\n{q} · {len(items)} תוצאות, {len(fresh)} מיומיים אחרונים")
        for t, s, d in fresh:
            if t in seen:
                continue
            seen[t] = True
            f = [w for w in FOOT if w in t]
            b = [w for w in BALL if w in t]
            nm = [w for w in names if w in t]
            mark = "⚽" if f and not b else ("🏀" if (b or nm) and not f else "  ")
            print(f"   {mark} {d:%d.%m %H:%M} · {s[:13]:<13} · {t[:80]}")
            if f or b or nm:
                print(f"        כדורגל={f} כדורסל={b} סגל={nm}")

    print(f"\n{'=' * 76}\nלמי היה משחק ב־15.9 לפי הלוח שלנו:")
    games = json.loads((news_feed.DATA / "games.json").read_text(encoding="utf-8"))["games"]
    for g in games:
        if "2026-09-1" in g["date"][:9] + g["date"][9]:
            pass
    near = [g for g in games if "2026-09-12" <= g["date"][:10] <= "2026-09-19"]
    for g in near:
        print(f"   {g['date'][:10]}  {g['home']} vs {g['away']}  [{g['status']}]")


if __name__ == "__main__":
    main()
