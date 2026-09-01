"""בדיקת מקורות: כל תמונה שהאתר של המועדון מסמן כשלנו, עם הגודל שלה.

הסבב הקודם בחר ״את הגדולה מבין המועמדות״, וזה בדיוק הכלל שפעם בחר את
הסמל של הפועל חולון. הגודל לא מעיד על כלום: הבאנר של הליגה בפוטר גדול
יותר מהסמל שלנו.

לכן כאן הזיהוי הוא לא לפי שם הקובץ ולא לפי הגודל, אלא לפי מה שהאתר של
המועדון כותב על התמונה: תגית img שה־alt שלה מזכיר את המועדון. רק
הרשימה מודפסת, בלי base64, כדי שאפשר יהיה לקרוא אותה.
"""
import io
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITE = "https://hapoel.co.il/"
PAGES = ["", "games", "team", "about", "news", "club"]
US = ("ירושלים", "מידטאון", "הפועל י")

# האתר מכריז utf-8 רק בתגית meta ולא בכותרת ה־HTTP, ולכן requests מנחשת
# latin-1 וכל העברית חוזרת כג׳יבריש. בסבב הקודם זה הפיל את כל ההתאמות
# לאפס בלי שום שגיאה.
ENC = "utf-8"


def log(*a):
    print("[probe]", *a, flush=True)


found = {}
for page in PAGES:
    url = requests.compat.urljoin(SITE, page)
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.encoding = ENC
    except Exception as e:
        log(f"{page or '/'}: נפל {e}")
        continue
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        log(f"{page or '/'}: {r.status_code}, מדלגים")
        continue
    soup = BeautifulSoup(r.text, "html.parser")
    hits = 0
    for im in soup.find_all("img"):
        alt = im.get("alt") or ""
        src = im.get("src") or im.get("data-src") or ""
        if not src or not any(w in alt for w in US):
            continue
        full = requests.compat.urljoin(url, src)
        found.setdefault(full, set()).add(alt.strip())
        hits += 1
    log(f"{page or '/'}: {hits} תמונות שה־alt שלהן מזכיר אותנו")

log("=== מה שנמצא, עם הגודל האמיתי ===")
for u, alts in sorted(found.items()):
    try:
        r = requests.get(u, headers=UA, timeout=30)
        im = Image.open(io.BytesIO(r.content))
        size = f"{im.size[0]}x{im.size[1]} {im.mode}"
    except Exception as e:
        size = f"נפל: {e}"
    log(f"  {size:<18} {len(r.content):>7} בתים")
    log(f"     alt: {' | '.join(sorted(alts))}")
    log(f"     {urllib.parse.unquote(u)}")
