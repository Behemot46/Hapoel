"""בדיקת מקורות, סבב שני: מה כן נותן ציוצים.

בסבב הראשון כל הדרכים לקרוא ציוצים כטקסט נפלו: nitter.net מחזיר 410,
שני מראות לא עונות בכלל, rsshub מחזיר 404, נקודת ה־CDN מחזירה גוף ריק,
ונקודת ה־syndication של X מחזירה 429 מהכתובות של גיטהאב. היחיד שענה
יפה הוא publish.twitter.com/oembed, אבל הוא מחזיר רק את תגית ההטמעה,
בלי שום תוכן.

לכן שתי שאלות כאן:

1. ה־429 הוא חסימה או עומס רגעי? שלושה ניסיונות עם המתנה יגידו.
2. **השאלה האמיתית:** האם ההטמעה הרשמית של X בכלל מציגה ציוצים לגולש
   שלא מחובר? זה מה שאוהד יראה. הבדיקה מריצה דפדפן אמיתי, טוענת את
   הווידג׳ט בדיוק כמו שהאפליקציה הייתה טוענת אותו, וסופרת כמה ציוצים
   הופיעו בתוך ה־iframe. בלי הבדיקה הזאת אין דרך לדעת, כי הכול קורה
   ב־JavaScript.
"""
import subprocess
import sys
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}

WHO = "shay_hausmann"


def log(*a):
    print("[probe]", *a, flush=True)


log("===== 1. syndication, שלושה ניסיונות =====")
for attempt in range(1, 4):
    url = (f"https://syndication.twitter.com/srv/timeline-profile/"
           f"screen-name/{WHO}?dnt=true")
    try:
        r = requests.get(url, headers=UA, timeout=25)
        log(f"  ניסיון {attempt}: HTTP {r.status_code} · {len(r.text)} תווים · "
            f"{r.text[:80]!r}")
        if r.status_code == 200:
            log(f"  full_text מופיע {r.text.count('full_text')} פעמים")
            break
    except Exception as e:
        log(f"  ניסיון {attempt} נפל: {e}")
    time.sleep(attempt * 5)

log("===== 2. עוד מראות nitter שאולי חיות =====")
for host in ("nitter.tiekoetter.com", "nitter.space", "lightbrd.com",
             "nitter.kavin.rocks", "twiiit.com"):
    try:
        r = requests.get(f"https://{host}/{WHO}/rss", headers=UA, timeout=20)
        log(f"  {host:<24} HTTP {r.status_code} · {len(r.text)} תווים · "
            f"{r.text.count('<item>')} פריטים")
    except Exception as e:
        log(f"  {host:<24} נפל: {type(e).__name__}")

log("===== 3. ההטמעה הרשמית, בדפדפן אמיתי =====")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"],
               check=True)
subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps",
                "chromium"], check=True)

from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = f"""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8">
</head><body>
<a class="twitter-timeline" data-lang="he" data-theme="dark" data-height="600"
   data-chrome="noheader nofooter transparent"
   href="https://twitter.com/{WHO}">ציוצים מאת {WHO}</a>
<script async src="https://platform.twitter.com/widgets.js"
        charset="utf-8"></script>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    page = b.new_page(locale="he-IL", viewport={"width": 420, "height": 900})
    errors = []
    page.on("requestfailed", lambda r: errors.append(f"{r.url[:70]} {r.failure}"))
    page.set_content(PAGE)
    page.wait_for_timeout(12000)
    frames = page.frames
    log(f"  מסגרות בדף: {len(frames)}")
    found = False
    for f in frames:
        if "twitter" not in f.url and "x.com" not in f.url:
            continue
        try:
            tweets = f.locator("article, .timeline-Tweet").count()
            txt = (f.locator("body").inner_text() or "")[:300].replace("\n", " | ")
        except Exception as e:
            log(f"  מסגרת {f.url[:60]}: לא נקראה, {e}")
            continue
        log(f"  מסגרת {f.url[:60]}")
        log(f"    ציוצים שנספרו: {tweets}")
        log(f"    טקסט: {txt}")
        found = found or tweets > 0
    log(f"  ==> ההטמעה {'מציגה ציוצים' if found else 'לא הציגה כלום'}")
    for e in errors[:8]:
        log(f"  בקשה שנכשלה: {e}")
    page.screenshot(path="embed.png", full_page=True)
    b.close()
log("  צילום מסך נשמר ב־embed.png (ארטיפקט של הריצה, אם מוגדר)")
