"""פרקים אחרונים מפודקאסטים על הפועל ועל הכדורסל הישראלי.

איך זה בנוי, ולמה:

  * הקונפיג לא מחזיק כתובות RSS אלא מזהה של תוכנית בחנות של אפל, והאיסוף
    פותר ממנו את כתובת הפיד בכל ריצה. תוכנית עוברת מארח (Acast, Buzzsprout,
    Omny, Spotify for Creators) בלי להודיע לאף אחד, וכתובת קבועה בקובץ היא
    כתובת שתמות בשקט. המזהה בחנות לא זז.
  * לכל תוכנית רשום גם expect, קטע מהשם שלה. אם השם שחזר מהחנות לא מכיל
    אותו, התוכנית מדולגת ונרשמת שורה בלוג. מזהה שהוקלד לא נכון מחזיר
    תוכנית אמיתית לגמרי, פשוט לא את זאת שרצינו, ובלי הבדיקה הזאת היא
    הייתה נכנסת לאפליקציה כאילו כלום.

וכלל אחד שנגזר מזה, במכוון, בדיוק כמו במדור החדשות: **כותרות בלבד**. שם
הפרק, שם התוכנית, מתי יצא וכמה הוא אורך. אף פעם לא תיאור הפרק ואף פעם לא
הקובץ עצמו. הפרק שייך למי שהקליט אותו, האפליקציה מפנה אליו ושולחת את
האוהד לשמוע אצלו.
"""
import datetime
import email.utils
import html
import json
import pathlib
import re
import xml.etree.ElementTree as ET

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}

LOOKUP = "https://itunes.apple.com/lookup"
SEARCH = "https://itunes.apple.com/search"

ITUNES_NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

DEFAULTS = {
    "shows": [],
    "maxPerShow": 4,
    "maxItems": 20,
    "maxAgeDays": 120,
}


def log(*a):
    print("[podcasts]", *a, flush=True)


def count(n, one, many):
    """עברית סופרת אחד אחרת, ולוג שכתוב ״1 תוכניות״ נקרא כמו מכונה."""
    return one if n == 1 else f"{n} {many}"


def _config():
    p = DATA / "podcast-sources.json"
    cfg = dict(DEFAULTS)
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if user.get(k):
                    cfg[k] = user[k]
        except Exception as e:
            log("podcast-sources.json unreadable, using defaults:", e)
    return cfg


def _clean(s):
    """כותרות פרק מגיעות מקודדות ב־HTML ולפעמים עם תגיות תועות."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _published(item):
    raw = item.findtext("pubDate") or ""
    try:
        d = email.utils.parsedate_to_datetime(raw)
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc)


def _duration(item):
    """itunes:duration נכתב או בשניות, או כ־mm:ss, או כ־hh:mm:ss."""
    raw = (item.findtext("itunes:duration", namespaces=ITUNES_NS) or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    if not all(p.strip().isdigit() for p in parts) or len(parts) > 3:
        return None
    secs = 0
    for p in parts:
        secs = secs * 60 + int(p)
    return secs


def _episode_url(item):
    """רוב הפידים נותנים <link> לעמוד הפרק. כשאין, נופלים לקובץ עצמו, שהוא
    עדיין כתובת אצל מי שהקליט ולא העתקה שלה."""
    link = (item.findtext("link") or "").strip()
    if link:
        return link
    enc = item.find("enclosure")
    return ((enc.get("url") if enc is not None else "") or "").strip()


def _apple(url, params):
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    # החנות מחזירה text/javascript, ו־r.json() מסרב לו בגרסאות מסוימות
    return json.loads(r.text)


def _resolve(show):
    """מזהה או ביטוי חיפוש בחנות של אפל, החוצה שם התוכנית, כתובת הפיד
    וכתובת העמוד. מחזיר None כשאין התאמה, אחרי שרשם למה."""
    expect = (show.get("expect") or "").strip()
    try:
        if show.get("appleId"):
            data = _apple(LOOKUP, {"id": str(show["appleId"]), "entity": "podcast"})
        else:
            data = _apple(SEARCH, {"term": show.get("search", ""), "media": "podcast",
                                   "country": "IL", "limit": 5})
    except Exception as e:
        log("דילוג:", expect or show.get("search"), "החנות לא ענתה,", e)
        return None

    for r in data.get("results") or []:
        name = _clean(r.get("collectionName"))
        feed = (r.get("feedUrl") or "").strip()
        if not name or not feed:
            continue
        if expect and expect not in name:
            continue
        return {
            "id": str(r.get("collectionId") or show.get("appleId") or name),
            "title": name,
            "feed": feed,
            "url": (r.get("collectionViewUrl") or "").strip(),
        }

    found = ", ".join(_clean(r.get("collectionName"))
                      for r in (data.get("results") or [])[:3]) or "כלום"
    log("דילוג:", expect or show.get("search"), "לא נמצא. החנות החזירה:", found)
    return None


def _episodes(feed_url, limit):
    r = requests.get(feed_url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    root = ET.fromstring(r.text.encode("utf-8"))
    out, seen = [], set()
    for it in root.findall(".//item"):
        title = _clean(it.findtext("title"))
        url = _episode_url(it)
        when = _published(it)
        if not title or not url or when is None:
            continue
        key = re.sub(r"\W+", "", title)
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "url": url, "published": when,
                    "duration": _duration(it)})
        if len(out) >= limit:
            break
    return out


def collect():
    cfg = _config()
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=int(cfg["maxAgeDays"])))
    per_show = int(cfg["maxPerShow"])

    shows, items = [], []
    skipped = 0
    for s in cfg["shows"]:
        info = _resolve(s)
        if not info:
            skipped += 1
            continue
        try:
            # מושכים קצת יותר מהמכסה, כי פרקים ישנים ייפלו על הגיל
            eps = _episodes(info["feed"], per_show * 3)
        except Exception as e:
            log("דילוג:", info["title"], "הפיד לא נקרא,", e)
            skipped += 1
            continue

        fresh = [e for e in eps if e["published"] >= cutoff][:per_show]
        if not fresh:
            log(info["title"], "בלי פרק חדש מ־" + str(cfg["maxAgeDays"]) + " ימים")
            continue

        shows.append({
            "id": info["id"],
            "title": info["title"],
            "about": s.get("about") or "league",
            "url": info["url"],
            "latest": fresh[0]["published"].isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        for e in fresh:
            items.append({
                "showId": info["id"],
                "show": info["title"],
                "about": s.get("about") or "league",
                "title": e["title"],
                "url": e["url"],
                "published": e["published"].isoformat(timespec="seconds").replace("+00:00", "Z"),
                "duration": e["duration"],
            })
        log(" ", info["title"] + ":", count(len(fresh), "פרק אחד", "פרקים"))

    items.sort(key=lambda i: i["published"], reverse=True)
    items = items[: int(cfg["maxItems"])]
    kept = {i["showId"] for i in items}
    shows = [s for s in shows if s["id"] in kept]

    log(count(len(shows), "תוכנית אחת", "תוכניות"), "·",
        count(len(items), "פרק אחד", "פרקים"), "·",
        count(skipped, "דילוג אחד", "דילוגים"))
    for i in items[:6]:
        log(f"  {i['published'][:10]}  {i['show'][:16]:<16} {i['title'][:60]}")
    return shows, items


def update_podcasts():
    """כותב את app/data/podcasts.json. זורק כשלא חזר כלום, כדי שהקורא ירשום
    כישלון והקובץ הקודם יישאר במקומו במקום להתרוקן."""
    shows, items = collect()
    if not items:
        raise RuntimeError("אף תוכנית לא החזירה פרק, משאירים את הקובץ הקודם")
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "note": "פרקים אחרונים מפודקאסטים על הפועל ועל הכדורסל הישראלי. "
                "לחיצה על פרק פותחת אותו אצל מי שהקליט.",
        "shows": shows,
        "items": items,
    }
    (DATA / "podcasts.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("wrote podcasts.json -", count(len(items), "פרק אחד", "פרקים"),
        "מ־" + count(len(shows), "תוכנית אחת", "תוכניות"))
    return payload


if __name__ == "__main__":
    update_podcasts()
