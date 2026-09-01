"""בדיקת מקורות: שתי הכותרות החשודות, דרך החיפוש של המפרסם עצמו.

גבי מדווח על כתבה במדור שעוסקת באכזבה מפתיחת העונה, והיא כדורגל.
עונת הכדורסל בכלל לא נפתחה, ולכן זה בטוח נכון, אבל שתי כותרות במדור
יכולות להתאים לתיאור ואי אפשר לחסום את שתיהן בלי לדעת.

שלושה סבבים קודמים נכשלו: הקישורים של גוגל ניוז מובילים לעמוד ביניים,
מנוע חיפוש חיצוני חוסם את הריצות של גיטהאב, ושאילתה לגוגל עם ״כדורסל״
מול ״כדורגל״ לא מבדילה, כי אתר ספורט מזכיר את שני הענפים בסרגל הצד.
זאת בדיוק הסיבה שמילת שלילה בשאילתה נפסלה בזמנו.

לכן כאן פונים לחיפוש של המפרסם עצמו, ואז קוראים את הכתבה ומודדים מה
יש בה: לא מילים שיכולות להגיע מהתפריט, אלא מילים שיכולות להופיע רק
בגוף של כתבה על משחק.
"""
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

SUSPECTS = [
    ("כל העיר", "https://www.kolhair.co.il/?s={q}", "האמת הלא נעימה מאחורי המאבק של הפועל ירושלים"),
    ("וואלה ספורט", "https://sports.walla.co.il/search?q={q}", "שוב פעם? הפועל ירושלים חוששת מעוד עונה קשה, והמומה מפוקסמן"),
    ("ספורט 1", "https://www.sport1.co.il/?s={q}", "הפועל ירושלים עדיין בהלם מההחלטה של דוד פוקסמן"),
    ("בחדרי חרדים", "https://www.bhol.co.il/search?q={q}", "'הפועל ירושלים' חזרה בה מהתמיכה בקפה \"בסמטה\" בעקבות חשיפת הקשר למיסיון"),
]

# מילים שיכולות להופיע רק בגוף של כתבה, לא בתפריט של אתר ספורט
BASKET = ("ריבאונד", "שלשה", "חמישייה", "עונשין", "סלים", "אובראדוביץ",
          "אוברדוביץ", "ליגת ווינר", "יורוליג", "יורוקאפ", "פיס ארנה", "אולם")
SOCCER = ("שוער", "בעיטה", "פנדל", "קרן", "מחצית", "הבקיע", "כדרור",
          "אצטדיון", "טדי", "דשא", "ליגה לאומית", "מגרש", "הרכב פותח")


def log(*a):
    print("[probe]", *a, flush=True)


def count(text, words):
    hits = {w: len(re.findall(re.escape(w), text)) for w in words}
    return sum(hits.values()), {k: v for k, v in hits.items() if v}


def words_of(title):
    return " ".join(re.sub(r"[\"'״׳:?!.,]", " ", title).split()[:6])


for name, search, title in SUSPECTS:
    log(f"=== {name}: {title}")
    url = search.format(q=urllib.parse.quote(words_of(title)))
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.encoding = r.encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log(f"    החיפוש נפל: {e}")
        continue
    log(f"    חיפוש: {r.status_code}, {len(r.text)} תווים")

    key = re.sub(r"[^֐-׿]", "", title)[:12]
    hit = None
    for a in soup.find_all("a", href=True):
        txt = re.sub(r"[^֐-׿]", "", a.get_text(" ", strip=True))
        if key and key in txt:
            hit = requests.compat.urljoin(r.url, a["href"])
            break
    if not hit:
        log("    לא נמצאה הכתבה בתוצאות החיפוש של האתר")
        continue
    log(f"    נמצאה: {hit}")
    try:
        p = requests.get(hit, headers=UA, timeout=30)
        p.encoding = p.encoding or "utf-8"
        body = re.sub(r"\s+", " ", BeautifulSoup(p.text, "html.parser").get_text(" ", strip=True))
    except Exception as e:
        log(f"    הכתבה נפלה: {e}")
        continue
    b, bh = count(body, BASKET)
    s, sh = count(body, SOCCER)
    log(f"    כדורסל:{b} {bh}")
    log(f"    כדורגל:{s} {sh}")
    log(f"    ==> {'כדורגל' if s > b else 'כדורסל' if b > s else 'לא ברור'}")
