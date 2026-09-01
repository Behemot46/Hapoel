"""בדיקת מקורות: לאן מוביל הקישור של וואלה, ומה יש בכתבה.

גבי שלח קישור share.google לכתבה של וואלה ספורט על המשחק מול הפועל
חולון. הסביבה שבה אני עובד חוסמת כל אתר חיצוני, ולכן הפתיחה של הקישור
נעשית כאן, בריצה של גיטהאב.

מה שמעניין: הכתובת הסופית אחרי ההפניות, הכותרת, התאריך והשורות
הראשונות. הטקסט עצמו לא נכנס לאפליקציה, המדיניות היא כותרת וקישור
בלבד, אבל צריך לדעת מה עומד מאחורי הקישור לפני שמפנים אליו אוהד.
"""
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
LINK = "https://share.google/aJnpDqPGqGHdHFAxc"


def log(*a):
    print("[probe]", *a, flush=True)


r = requests.get(LINK, headers=UA, timeout=30, allow_redirects=True)
log(f"סטטוס {r.status_code}, {len(r.history)} הפניות")
for h in r.history:
    log(f"  {h.status_code} -> {h.headers.get('location', '')[:160]}")
log(f"כתובת סופית: {r.url}")

r.encoding = r.encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")
log(f"title: {(soup.title.string or '').strip() if soup.title else '(אין)'}")
for prop in ("og:title", "og:url", "og:description", "article:published_time"):
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    if tag:
        log(f"{prop}: {(tag.get('content') or '')[:220]}")

h1 = soup.find("h1")
if h1:
    log(f"h1: {h1.get_text(' ', strip=True)[:200]}")
text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
log(f"פסקאות ראשונות: {text[:600]}")
