"""בדיקת מקורות: האם יש עותק גדול יותר של הסמל, ומה יש בפאביקון.

הסבב הקודם סגר את שאלת המקור: האתר של המועדון עצמו מגיש את הקובץ הזה
כלוגו שלו בשלושה מקומות בעמוד הבית, כולל הסרגל העליון והפוטר, עם
alt=״הפועל ״מידטאון״ ירושלים״. שם הקובץ הוא איך שמנהל התוכן קרא לו,
לא ראיה לגבי מי מפרסם אותו.

נשארה שאלה אחת, והיא איכות: המועמד הוא 300x300, וסמל האפליקציה הגדול
הוא 512. לכן כאן מחפשים עותק גדול יותר בעמודים הפנימיים של האתר,
ובודקים מה יש בפאביקון של המועדון: אם גם הוא כבר הוחלף, זו עדות שנייה
מהאתר של המועדון, ואם הוא עדיין הישן, זה רק אומר שלא טרחו להחליף אותו.
"""
import base64
import io
import re
import sys
import urllib.parse

import requests
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITE = "https://hapoel.co.il/"
PAGES = ["", "games", "team", "about", "news", "club", "index.html"]


def log(*a):
    print("[probe]", *a, flush=True)


def get(url):
    return requests.get(url, headers=UA, timeout=30)


seen = set()
candidates = set()
for page in PAGES:
    url = requests.compat.urljoin(SITE, page)
    try:
        r = get(url)
    except Exception as e:
        log(f"{page or '/'}: נפל {e}")
        continue
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        log(f"{page or '/'}: {r.status_code} {r.headers.get('content-type')}")
        continue
    urls = {requests.compat.urljoin(url, m)
            for m in re.findall(r'["\'(]([^"\'()\s]+\.(?:png|svg|webp|jpg|jpeg))', r.text, re.I)}
    hit = {u for u in urls
           if re.search(r"logo|לוגו|crest|ChatGPT", urllib.parse.unquote(u), re.I)}
    log(f"{page or '/'}: {len(r.text)} תווים, {len(urls)} תמונות, {len(hit)} מועמדות")
    candidates |= hit

log("=== מועמדות, עם הגודל האמיתי ===")
best = None
for u in sorted(candidates):
    if u in seen:
        continue
    seen.add(u)
    try:
        r = get(u)
        im = Image.open(io.BytesIO(r.content))
        log(f"  {im.size} {im.mode} {len(r.content):>7}  {urllib.parse.unquote(u)[:120]}")
        if best is None or im.size[0] > best[0].size[0]:
            best = (im, u, r.content)
    except Exception as e:
        log(f"  נפל: {urllib.parse.unquote(u)[:100]} · {e}")

log("=== הפאביקון של המועדון ===")
try:
    r = get(requests.compat.urljoin(SITE, "favicon.ico"))
    im = Image.open(io.BytesIO(r.content))
    sizes = sorted(getattr(im, "ico", None).sizes()) if hasattr(im, "ico") else [im.size]
    log(f"  {len(r.content)} בתים, מסגרות: {sizes}")
    im.size = sizes[-1]
    im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    b = base64.b64encode(buf.getvalue()).decode()
    log(f"  base64 של המסגרת הגדולה ({im.size}), {len(b)} תווים:")
    for i in range(0, len(b), 200):
        print("[b64ico]", b[i:i + 200], flush=True)
except Exception as e:
    log(f"  נפל: {e}")

if best is not None:
    im, u, raw = best
    log(f"=== הגדולה מבין המועמדות: {im.size} · {urllib.parse.unquote(u)}")
    if im.size[0] > 300:
        b = base64.b64encode(raw).decode()
        log(f"  base64, {len(b)} תווים:")
        for i in range(0, len(b), 200):
            print("[b64logo]", b[i:i + 200], flush=True)
    else:
        log("  לא גדולה מ־300, אין טעם להוריד שוב.")
