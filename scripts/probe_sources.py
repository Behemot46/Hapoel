"""בדיקת מקורות: לשאול את גוגל איזה ענף כל כתבה במדור.

שני הסבבים הקודמים נכשלו מסיבות טובות: הקישורים של גוגל ניוז מובילים
לעמוד ביניים ואי אפשר ללכת אחריהם, ומנוע חיפוש חיצוני חוסם את הריצות
של גיטהאב. אז במקום להביא את הכתבה, שואלים עליה את מי שכבר קרא אותה.

גוגל מחפשת בכל העמוד ולא רק בכותרת, וזאת בדיוק התכונה שהכשילה אותנו
פעם כשניסינו מילת שלילה בשאילתה. כאן היא עובדת לטובתנו: אם הכותרת
המדויקת חוזרת בשאילתה שדורשת ״כדורסל״, העמוד מזכיר כדורסל. אם היא
חוזרת רק בשאילתה שדורשת ״כדורגל״, זאת כתבת כדורגל.

הכל דרך אותו פיד שהאפליקציה כבר משתמשת בו, בלי תלות חדשה.
"""
import json
import pathlib
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"


def log(*a):
    print("[probe]", *a, flush=True)


def norm(s):
    return re.sub(r"[^֐-׿0-9a-zA-Z]+", "", s or "")


def asks(title, marker):
    """האם הכותרת המדויקת חוזרת כשדורשים מהעמוד את המילה הזאת."""
    q = urllib.parse.quote(f'"{title[:80]}" {marker}')
    try:
        r = requests.get(FEED.format(q=q), headers=UA, timeout=30)
        root = ET.fromstring(r.content)
    except Exception as e:
        return None
    want = norm(title)[:40]
    for item in root.iter("item"):
        got = norm(item.findtext("title") or "")
        if want and want in got:
            return True
    return False


items = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["items"]
log(f"{len(items)} פריטים במדור")
for i, it in enumerate(items):
    t = it["title"]
    b = asks(t, "כדורסל")
    time.sleep(1.2)
    s = asks(t, "כדורגל")
    time.sleep(1.2)
    if b is None or s is None:
        verdict = "נפל   "
    elif b and not s:
        verdict = "כדורסל"
    elif s and not b:
        verdict = "כדורגל!"
    elif b and s:
        verdict = "שניהם "
    else:
        verdict = "לא חזר"
    log(f"[{i:2}] {verdict} | סל:{b} רגל:{s} | {it['source']} | {t}")
