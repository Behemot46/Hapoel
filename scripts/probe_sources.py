"""בדיקת מקורות: השם המוצג מאחורי כל ידית.

בסבב הקודם התברר ש־oembed מבחין בין ידית קיימת (200) לידית מומצאת
(404), אבל קיום זה לא זהות. מסתבר שהתשובה מכילה גם את השם המוצג, בתוך
טקסט העוגן: ״Posts by ...״. זה בדיוק מה שחסר כדי לוודא שהחשבון שייך
לאדם שאני חושב, ולא לאדם אחר עם ידית דומה.

וגם: @JerusalemBasket החזיר 404 בזמן ש־@HJerusalem החזיר 200 עם כתיב
מדויק. אם המועדון החליף ידית בעקבות המיתוג החדש, השם המוצג יגיד את זה.
"""
import html as html_mod
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

HANDLES = ["shay_hausmann", "Barakhaklai", "HJerusalem", "JerusalemBasket",
           "WinnerLeague", "TherealIBBA", "thebasket13", "thesportsrabbi",
           "HapoelJLMfc"]


def log(*a):
    print("[probe]", *a, flush=True)


for h in HANDLES:
    try:
        r = requests.get("https://publish.twitter.com/oembed",
                         params={"url": f"https://twitter.com/{h}", "lang": "he"},
                         headers=UA, timeout=25)
    except Exception as e:
        log(f"  @{h:<18} נפל: {type(e).__name__}")
        continue
    if r.status_code != 200:
        log(f"  @{h:<18} HTTP {r.status_code}")
        continue
    d = r.json()
    anchor = re.sub(r"<[^>]+>", "", d.get("html", ""))
    anchor = html_mod.unescape(anchor).strip()
    log(f"  @{h:<18} url={d.get('url')}")
    log(f"  {'':<20} {anchor[:120]}")
