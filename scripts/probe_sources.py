"""בדיקת מקורות: לאיזה ענף שייכת כותרת, לפי מה שגוגל מוצאת עליה.

חמש כותרות במדור נראות כדורגל, ואין בהן מילה שמכריעה. במקום לנחש,
שואלים את אותה שאלה פעמיים: הכותרת יחד עם המילה ״כדורגל״, והכותרת יחד
עם המילה ״כדורסל״. גוגל מחפשת בכל העמוד, כולל תגיות ומדור, ולכן הצד
שמחזיר תוצאות הוא הצד שהסיפור יושב בו.

זה לא מדע מדויק, ולכן התוצאה כאן היא ראיה ולא פסק דין: מה שמוכרע כאן
נכנס ל־blockPhrases ביד, אחרי קריאה.
"""
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"

SUSPECTS = [
    "הפועל ירושלים בהודעה חריפה: השוטרים יצרו עימות אגרסיבי",
    "הפועל ירושלים ביצעה מהפך היסטורי לא נבקיע כל משחק רביעייה",
    "השינוי של הפועל ירושלים והמסר צריך להיות יציבים הגנתית",
    "הפועל ירושלים משנה גישה השחקן שמגיע ממועדון בכיר בדנמרק",
    "פרופיל לא שגרתי הפועל ירושלים בדרך לצרף את צ׳ילופיה",
    # ביקורת: כותרת שאני בטוח שהיא כדורסל, כדי לראות שהמדידה מבחינה
    "הפועל ירושלים תובעת את הפועל תל אביב על קאדין קרינגטון",
]


def log(*a):
    print("[probe]", *a, flush=True)


def hits(query):
    url = FEED.format(q=urllib.parse.quote(query))
    try:
        r = requests.get(url, headers=UA, timeout=30)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        return len(items), [i.findtext("title", "")[:70] for i in items[:2]]
    except Exception as e:
        return -1, [str(e)[:60]]


for s in SUSPECTS:
    a, ta = hits(s + " כדורגל")
    time.sleep(1.5)
    b, tb = hits(s + " כדורסל")
    time.sleep(1.5)
    verdict = "כדורגל!" if a > b else ("כדורסל " if b > a else "תיקו   ")
    log(f"{verdict} רגל:{a:<3} סל:{b:<3} | {s[:60]}")
    if ta: log(f"     רגל→ {ta[0]}")
    if tb: log(f"     סל → {tb[0]}")
