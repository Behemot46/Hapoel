"""בדיקת מקורות: האם אפשר לקרוא ציוצים ציבוריים בלי מפתח בתשלום.

הבקשה היא פיד של אנשי תקשורת שמסקרים את הפועל. ה־API הרשמי של X עולה
כסף, ולכן השאלה הראשונה היא לא איך מעצבים את המדור אלא אם בכלל יש
מאיפה לקרוא. כאן נמדדות כל הדרכים שאני מכיר, מהריצה של Actions ולא
מהסנדבוקס, ומודפס מה באמת חוזר: קוד תשובה, גודל, ואם נראה שיש בפנים
ציוצים.

אם כלום לא עונה, זו תשובה תקפה, והמדור ייבנה אחרת.
"""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}

WHO = "shay_hausmann"

ROUTES = [
    ("syndication timeline", f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{WHO}?dnt=true"),
    ("cdn syndication", f"https://cdn.syndication.twimg.com/timeline/profile?screen_name={WHO}&dnt=true"),
    ("publish oembed", f"https://publish.twitter.com/oembed?url=https://twitter.com/{WHO}"),
    ("nitter.net rss", f"https://nitter.net/{WHO}/rss"),
    ("xcancel rss", f"https://xcancel.com/{WHO}/rss"),
    ("nitter.poast rss", f"https://nitter.poast.org/{WHO}/rss"),
    ("nitter.privacydev rss", f"https://nitter.privacydev.net/{WHO}/rss"),
    ("rsshub twitter", f"https://rsshub.app/twitter/user/{WHO}"),
    ("x.com profile", f"https://x.com/{WHO}"),
    ("bluesky search", "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?q=hausmann"),
]


def log(*a):
    print("[probe]", *a, flush=True)


for name, url in ROUTES:
    try:
        r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
    except Exception as e:
        log(f"{name:<24} נפל: {type(e).__name__}: {str(e)[:110]}")
        continue
    body = r.text or ""
    hint = ""
    if "<item>" in body:
        hint = f" · {body.count('<item>')} פריטים ב־RSS"
    elif "__NEXT_DATA__" in body:
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
        if m:
            try:
                d = json.loads(m.group(1))
                s = json.dumps(d, ensure_ascii=False)
                hint = f" · __NEXT_DATA__ יש, מזכיר full_text {s.count('full_text')} פעמים"
            except Exception as e:
                hint = f" · __NEXT_DATA__ לא נפרס: {e}"
    elif body.strip().startswith("{"):
        hint = " · JSON: " + body[:120].replace("\n", " ")
    log(f"{name:<24} HTTP {r.status_code} · {len(body)} תווים · "
        f"{r.headers.get('content-type', '-')[:40]}{hint}")
