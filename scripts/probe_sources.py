"""בדיקת מקורות: הסמל של המועדון מהאתר של המועדון עצמו.

המועמד מהסבב הקודם מגיע מהתיקייה של הליגה, ושם הקובץ שלו הוא
״ChatGPT Image Aug 23, 2026, 04_57_05 PM copy.png״. כלומר מישהו ייצר
אותו במחולל תמונות ביום ההשקה. זה אולי דומה לסמל האמיתי, וזה בדיוק
הסוג של דבר שאסור להכניס לאפליקציה בלי לדעת: סמל של מועדון אמיתי הוא
לא משהו שמשחזרים בקירוב.

כאן מחפשים את הנכס של המועדון עצמו, במקומות שבהם אתר מחזיק את הלוגו
שלו: תגיות icon ו־apple-touch, og:image, מניפסט, SVG מוטמע בעמוד,
ותמונות רקע ב־CSS.
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


def log(*a):
    print("[probe]", *a, flush=True)


html = u.fetch(SITE)
soup = BeautifulSoup(html, "html.parser")

log("=== icon / manifest / og ===")
for tag in soup.find_all("link", rel=True):
    rel = " ".join(tag.get("rel"))
    if any(k in rel.lower() for k in ("icon", "manifest", "mask")):
        log(f"  [{rel}] sizes={tag.get('sizes')} {requests.compat.urljoin(SITE, tag.get('href') or '')}")
for tag in soup.find_all("meta"):
    prop = tag.get("property") or tag.get("name") or ""
    if prop in ("og:image", "twitter:image", "og:image:secure_url"):
        log(f"  [{prop}] {requests.compat.urljoin(SITE, tag.get('content') or '')}")

log("=== svg מוטמע בעמוד ===")
svgs = soup.find_all("svg")
log(f"  {len(svgs)} תגיות svg")
for i, sv in enumerate(svgs[:6]):
    txt = str(sv)
    log(f"  [{i}] {len(txt)} תווים, class={sv.get('class')} · {txt[:120]}")

log("=== כתובות שנראות כמו לוגו בכל ה־HTML ===")
urls = set(re.findall(r'["\'(]([^"\'()\s]+\.(?:png|svg|webp|jpg))', html, re.I))
for raw in sorted(urls):
    full = requests.compat.urljoin(SITE, raw)
    dec = urllib.parse.unquote(full)
    if re.search(r"logo|crest|badge|semel|סמל|לוגו|header", dec, re.I):
        log(f"  {dec}")

log("=== גיליונות סגנון: תמונות רקע ===")
for tag in soup.find_all("link", rel=lambda v: v and "stylesheet" in " ".join(v)):
    href = requests.compat.urljoin(SITE, tag.get("href") or "")
    try:
        css = requests.get(href, timeout=25).text
    except Exception as e:
        log(f"  {href[:80]}: נפל {e}")
        continue
    hits = set(re.findall(r'url\(["\']?([^"\')]+)', css))
    logos = [h for h in hits if re.search(r"logo|crest|badge|header", h, re.I)]
    log(f"  {href.split('/')[-1][:40]}: {len(hits)} תמונות, מהן {len(logos)} שנראות כמו לוגו")
    for h in logos[:8]:
        log(f"    {urllib.parse.unquote(requests.compat.urljoin(href, h))}")
