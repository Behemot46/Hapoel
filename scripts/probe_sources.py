"""בדיקת מקורות: מי באמת עומד מאחורי כל ידית, לפני ששם של אדם אמיתי
נכנס לאפליקציה.

חיפוש ברשת נתן לי ידיות, אבל ידית שנראית נכונה בתוצאת חיפוש היא עדיין
ניחוש. שתי נקודות ציבוריות עונות בלי מפתח ואפשר להצליב ביניהן:

  * publish.twitter.com/oembed מחזיר 200 לחשבון קיים ו־404 לחשבון שאינו
    קיים, וגם את הכתיבה המדויקת של הידית.
  * cdn.syndication.twimg.com/widgets/followbutton/info.json מחזיר, אם
    הוא עוד חי, את השם המוצג ואת התיאור. זה מה שמאשר שהידית שייכת לאדם
    שאני חושב, ולא רק שהיא קיימת.

מה שלא יאומת, לא ייכנס.
"""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

CANDIDATES = [
    ("שי האוזמן", "shay_hausmann"),
    ("ברק חקלאי", "Barakhaklai"),
    ("הפועל ירושלים, המועדון", "JerusalemBasket"),
    ("הפועל ירושלים, חשבון נוסף", "hjerusalem"),
    ("ליגת ווינר סל", "WinnerLeague"),
    ("איגוד הכדורסל", "TherealIBBA"),
    ("עולם הכדורסל", "thebasket13"),
    ("Sports Rabbi", "thesportsrabbi"),
    ("ידית שלא קיימת, בקרה", "hapoel_probe_no_such_user_xyz"),
]


def log(*a):
    print("[probe]", *a, flush=True)


log("===== oembed: קיים או לא =====")
alive = []
for who, handle in CANDIDATES:
    try:
        r = requests.get("https://publish.twitter.com/oembed",
                         params={"url": f"https://twitter.com/{handle}"},
                         headers=UA, timeout=25)
        ok = r.status_code == 200
        extra = ""
        if ok:
            try:
                extra = " · " + json.dumps(r.json(), ensure_ascii=False)[:150]
            except Exception:
                pass
            alive.append(handle)
        log(f"  {who:<26} @{handle:<32} HTTP {r.status_code}{extra}")
    except Exception as e:
        log(f"  {who:<26} @{handle:<32} נפל: {type(e).__name__}")

log("===== followbutton: מי זה בעצם =====")
try:
    r = requests.get("https://cdn.syndication.twimg.com/widgets/followbutton/info.json",
                     params={"screen_names": ",".join(h for _, h in CANDIDATES)},
                     headers=UA, timeout=25)
    log(f"  HTTP {r.status_code} · {len(r.text)} תווים")
    if r.text.strip():
        for row in r.json():
            log(f"  @{row.get('screen_name'):<24} {row.get('name', '')} · "
                f"עוקבים {row.get('followers_count', '?')} · "
                f"{(row.get('description') or '')[:90]}")
except Exception as e:
    log(f"  נפל: {e}")
