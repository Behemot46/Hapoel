"""בדיקת מקורות: איפה נמצא הסמל החדש של המועדון.

המועדון השיק סמל חדש ומיתוג חדש ב־23.8.2026, וזה הופיע גם במדור החדשות
שלנו. הסמל באפליקציה הוא עדיין הישן. הקובץ אצלנו הוא 160x160, הכי גדול
שנמצא בזמנו, וכל שאר האייקונים נגזרים ממנו.

כאן מחפשים את הקובץ הרשמי החדש: כל תמונה בעמוד הבית של המועדון, תגיות
og:image ו־favicon, וכל כתובת שנראית כמו לוגו. מודפס גם הגודל האמיתי של
כל מועמד, כי סמל ב־48 פיקסלים לא שווה כלום לאייקון של 512.

ובסוף, המועמד הטוב ביותר מודפס כ־base64 כדי שאפשר יהיה להסתכל עליו
בעיניים לפני שהוא נכנס לריפו. סמל הוא הדבר היחיד באפליקציה שאסור
״להתקין ולראות אחר כך״.
"""
import base64
import io
import re
import sys
import pathlib

import requests
from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u

SITE = "https://hapoel.co.il/"


def log(*a):
    print("[probe]", *a, flush=True)


def measure(url):
    try:
        r = requests.get(url, headers=u.UA if hasattr(u, "UA") else {}, timeout=25)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        return r.content, im.size, im.mode
    except Exception as e:
        return None, ("שגיאה", str(e)[:60]), None


html = u.fetch(SITE)
log("עמוד הבית:", len(html), "תווים")
soup = BeautifulSoup(html, "html.parser")

cands = []
for tag in soup.find_all("img"):
    src = tag.get("src") or tag.get("data-src") or ""
    if src:
        cands.append(("img", requests.compat.urljoin(SITE, src), tag.get("alt") or ""))
for tag in soup.find_all("link", rel=True):
    rel = " ".join(tag.get("rel"))
    if "icon" in rel.lower():
        cands.append((rel, requests.compat.urljoin(SITE, tag.get("href") or ""), ""))
for tag in soup.find_all("meta", property=True):
    if tag.get("property") in ("og:image", "twitter:image"):
        cands.append((tag["property"], requests.compat.urljoin(SITE, tag.get("content") or ""), ""))

seen, uniq = set(), []
for kind, url, alt in cands:
    if url in seen:
        continue
    seen.add(url)
    uniq.append((kind, url, alt))

log(f"מועמדים: {len(uniq)}")
best = None
for kind, url, alt in uniq[:40]:
    looks = re.search(r"logo|crest|badge|symbol|icon|semel|סמל", url, re.I)
    data, size, mode = measure(url)
    mark = ""
    if data and isinstance(size, tuple) and isinstance(size[0], int):
        px = size[0] * size[1]
        if looks and (best is None or px > best[0]):
            best = (px, url, data, size)
            mark = "  <== מועמד"
    log(f"  [{kind}] {size} {mode or ''} {url[:95]} {('alt=' + alt[:30]) if alt else ''}{mark}")

if best:
    px, url, data, size = best
    log("=== הטוב ביותר ===")
    log(url, size, f"{len(data)} bytes")
    b64 = base64.b64encode(data).decode()
    log(f"base64 באורך {len(b64)}, ב־{(len(b64) + 2999) // 3000} חלקים")
    for i in range(0, len(b64), 3000):
        log(f"B64[{i // 3000}] {b64[i:i + 3000]}")
else:
    log("לא נמצא מועמד שנראה כמו לוגו")
