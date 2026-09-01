"""בדיקת מקורות: איפה האתר של המועדון מחזיק את הסמל שלו.

הסבב הקודם על hapoel.co.il חזר כמעט ריק: אפס תגיות icon, אפס og:image,
אפס גיליונות סגנון. עמוד אמיתי לא נראה ככה, ולכן השאלה עכשיו היא מה
בעצם חזר: עמוד מלא, שלד שנטען ב־JavaScript, או הפניה למקום אחר.

לכן כאן לא מסננים כלום: אורך התשובה, הכתובת הסופית, ה־head המלא, כל
תגיות img עם ה־alt שלהן, וכמה נתיבים מוסכמים שאתר מחזיק בהם את הסמל.
"""
import re
import sys
import pathlib
import urllib.parse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u

SITE = "https://hapoel.co.il/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def log(*a):
    print("[probe]", *a, flush=True)


r = requests.get(SITE, headers=UA, timeout=30)
html = r.text
log(f"=== התשובה: {r.status_code}, {len(html)} תווים, כתובת סופית {r.url}")
log(f"    content-type: {r.headers.get('content-type')}")
soup = BeautifulSoup(html, "html.parser")

log("=== head ===")
head = soup.find("head")
if head:
    for line in str(head).splitlines():
        line = line.strip()
        if line:
            log("  " + line[:200])
else:
    log("  אין head. 600 התווים הראשונים:")
    log("  " + html[:600].replace("\n", " "))

log("=== כל תגיות img ===")
imgs = soup.find_all("img")
log(f"  {len(imgs)} תגיות")
for i, im in enumerate(imgs[:60]):
    src = im.get("src") or im.get("data-src") or ""
    log(f"  [{i}] alt={im.get('alt')!r} class={im.get('class')} "
        f"{urllib.parse.unquote(requests.compat.urljoin(SITE, src))[:150]}")

log("=== נתיבים מוסכמים ===")
for path in ("favicon.ico", "apple-touch-icon.png", "apple-touch-icon-precomposed.png",
             "site.webmanifest", "manifest.json", "assets/images/logo.png",
             "assets/images/logo.svg", "wp-content/uploads/"):
    url = requests.compat.urljoin(SITE, path)
    try:
        h = requests.get(url, headers=UA, timeout=20, stream=True)
        body = h.raw.read(400_000, decode_content=True)
        log(f"  {h.status_code} {len(body):>8} {h.headers.get('content-type','?')[:30]} {path}")
    except Exception as e:
        log(f"  נפל {path}: {e}")

log("=== כל התמונות שמוזכרות ב־HTML (בלי סינון) ===")
urls = sorted({urllib.parse.unquote(requests.compat.urljoin(SITE, m))
               for m in re.findall(r'["\'(]([^"\'()\s]+\.(?:png|svg|webp|jpg|jpeg))', html, re.I)})
log(f"  {len(urls)} כתובות")
for x in urls[:80]:
    log("  " + x[:160])

log("=== סקריפטים וגיליונות ===")
for tag in soup.find_all(["script", "link"]):
    src = tag.get("src") or tag.get("href")
    if src:
        log(f"  <{tag.name} rel={tag.get('rel')}> {requests.compat.urljoin(SITE, src)[:160]}")
