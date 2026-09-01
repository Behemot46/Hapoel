"""בדיקת מקורות: הסמל החדש של המועדון, הפעם עם הכתובת המלאה.

הסבב הקודם מצא את הכיוון וגם הראה למה אסור לתת להיוריסטיקה להחליט: היא
בחרה את הלוגו של הפועל חולון, כי הוא הכי גדול והמילה logo מופיעה
בכתובת שלו. הסמל שלנו הופיע שורה אחת מעליו, בגודל 300x300, עם
alt=״הפועל ׳מידטאון׳ ירושלים״ ובתיקייה 2026-2027.

כאן מסננים לפי מה שבאמת מזהה אותנו, מדפיסים את הכתובת המלאה, ומדפיסים
את התמונה עצמה ב־base64 כדי שאפשר יהיה להסתכל עליה בעיניים לפני שהיא
נכנסת לאפליקציה. יש תקרת גודל, כי סמל של 1.8 מגה בלוג הוא מה שקרה בסבב
הקודם.
"""
import base64
import io
import sys
import pathlib
import urllib.parse

import requests
from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u

SITE = "https://hapoel.co.il/"
US = ("ירושלים", "מידטאון", "hapoel-jer")
NOT_US = ("חולון", "העמק", "אשדוד", "מכבי", "ווינר", "winner", "ספונסר", "יורוקאפ")
MAX_B64 = 400_000


def log(*a):
    print("[probe]", *a, flush=True)


soup = BeautifulSoup(u.fetch(SITE), "html.parser")
seen, ours = set(), []
for tag in soup.find_all("img"):
    src = tag.get("src") or tag.get("data-src") or ""
    if not src:
        continue
    url = requests.compat.urljoin(SITE, src)
    if url in seen:
        continue
    seen.add(url)
    alt = (tag.get("alt") or "").strip()
    hay = alt + " " + urllib.parse.unquote(url)
    if any(w in hay for w in US) and not any(w.lower() in hay.lower() for w in NOT_US):
        ours.append((url, alt))

log(f"תמונות שמזוהות איתנו: {len(ours)}")
best = None
for url, alt in ours:
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        log(f"  {im.size} {im.mode} {len(r.content)} bytes  alt={alt!r}")
        log(f"    {url}")
        log(f"    מפוענח: {urllib.parse.unquote(url)}")
        square = abs(im.size[0] - im.size[1]) <= 2
        if square and (best is None or im.size[0] > best[1].size[0]):
            best = (url, im, r.content, alt)
    except Exception as e:
        log(f"  נפל: {url[:90]} · {e}")

if not best:
    log("לא נמצא סמל ריבועי שמזוהה איתנו")
else:
    url, im, data, alt = best
    log("=== המועמד ===")
    log(url)
    log(f"{im.size[0]}x{im.size[1]} {im.mode} · {len(data)} bytes · alt={alt!r}")
    b64 = base64.b64encode(data).decode()
    if len(b64) > MAX_B64:
        log(f"גדול מדי להדפסה ({len(b64)} תווים), לא מודפס")
    else:
        log(f"base64, {len(b64)} תווים ב־{(len(b64) + 2999) // 3000} חלקים")
        for i in range(0, len(b64), 3000):
            log(f"B64 {b64[i:i + 3000]}")
