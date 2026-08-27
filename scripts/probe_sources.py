"""בדיקת מקורות: מה אוהד באמת מקבל עכשיו במדור החדשות.

הקובץ בריפו תוקן ואומת, אבל האוהד לא קורא את הריפו. זה מושך את
hapoel.site ואת גיטהאב פייג׳ס בדיוק כמו שהאפליקציה מושכת, ומדפיס מה
חזר: כמה כותרות, מאיזה תאריך, ואם הכותרת החדשה ביותר היא של היום.
"""
import datetime
import json

import requests

TARGETS = [
    ("hapoel.site", "https://hapoel.site/data/news.json"),
    ("github pages", "https://behemot46.github.io/Hapoel/data/news.json"),
]


def log(*a):
    print("[probe]", *a, flush=True)


today = datetime.datetime.now(datetime.timezone.utc).date()

for name, url in TARGETS:
    try:
        r = requests.get(url, timeout=30)
        log(f"===== {name} ===== HTTP {r.status_code} · "
            f"cache-control: {r.headers.get('cache-control', '-')}")
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        log(f"{name}: נפל, {e}")
        continue
    items = d.get("items", [])
    newest = items[0]["published"][:10] if items else "-"
    log(f"{len(items)} כותרות · עודכן {d.get('updated', '-')} · "
        f"הכי חדשה {newest}" + ("  (היום)" if newest == str(today) else ""))
    for i in items[:6]:
        log(f"  {i['published'][:10]}  {i.get('source', '?'):<14.14} {i['title'][:90]}")
