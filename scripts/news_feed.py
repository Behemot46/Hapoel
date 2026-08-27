"""Headlines about the club, from the Israeli sports press.

What the probe found, and why this is built the way it is:

  * Every Israeli sports site's own RSS is gone. sport5, ONE, mako and
    calcalist answer 404/403, walla's feed host answers 500, and the club's
    own hapoel.co.il returns "אופס! תקלה" for /feed, /news and wp-json.
    ynet's sport feed is alive but is general sport: in a sample of 30
    items, none were about us.
  * Google News still indexes all of them and answers an RSS query with 100
    items, each carrying <source url="…">, a pubDate and a headline. That is
    the only working route, so it is the route.

Two rules follow from that, and both are deliberate:

  1. Headlines only. The title, who published it and when: never the
     article body, never the publisher's photo. The text belongs to the
     outlet that wrote it; the app quotes the headline and sends the reader
     there. Every item is a link out, with the source named on it.
  2. The <link> is a news.google.com id, not the article address. Following
     it server-side lands on a JavaScript page, and the endpoint that
     resolves those ids needs a signed request, so the id is what gets
     stored. In a browser it redirects to the publisher, which is how a
     Google News link is meant to be opened.

The filter is the delicate part. "הפועל ירושלים" is also a football club,
and a search for the name alone returned items about Maccabi Tel Aviv that
merely mentioned us in the body. So an item is kept only when the club is
named in the *headline*, and dropped when the headline reads as football.
"""
import datetime
import email.utils
import html
import json
import pathlib
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}

FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"

# spellings the press actually uses for the club
US = ("הפועל ירושלים", "הפועל י-ם", "הפועל י־ם", 'הפועל י"ם', "הפועל י״ם",
      "הפועל בנק יהב", "הפועל מידטאון", "אדומי הבירה")
# כותרת שנקראת ככדורגל, או ככדורסל של מישהו אחר. הרשימה הזאת התארכה
# כשהשאילתות התרחבו: כל עוד כל שאילתה דרשה את המילה ״כדורסל״, גוגל סיננה
# בשבילנו וכמעט שום כדורגל לא הגיע. בלי הדרישה הזאת מגיעות גם כותרות על
# קבוצת הכדורגל שחולקת את השם, ולכן הסינון חייב לעמוד בזה לבד.
NOT_US = ("כדורגל", "בית\"ר", "ביתר ירושלים", "ליגת העל בכדורגל", "גביע הטוטו",
          "המכבייה", "כדורעף", "כדוריד",
          # אוצר מילים שהוא כדורגל ולא כדורסל
          "ליגה לאומית", "ליגת העל", "שוער", "פנדל", "בעיטה", "בעיטת",
          "קרן", "אדום ישיר", "כרטיס צהוב", "צהוב שני", "הארכה בכדורגל",
          "מחצית", "דקה ה־", "דקה ה-", "מהספסל בכדורגל", "שער בדקה",
          "ליגת אלופות", "הליגה האנגלית", "פרמייר ליג", "לה ליגה",
          "שלושער", "הבקיע", "כבש שער", "בעיטת עונשין",
          # קבוצת הנוער היא לא הקבוצה שהאפליקציה עוסקת בה
          "(נוער)", "לנוער",
          # 365Scores מייצר עמודי משחק אוטומטיים, לא ידיעות. אלה הביטויים
          # שמופיעים בכולם, בכל ענף.
          "תוצאות לייב", "מפגשי עבר")

# הכלל החלש מבין השלושה, וזה שיצטרך תוספות: מועדוני כדורגל ישראליים
# שהופיעו בכותרת לצידנו. כותרת כמו ״הפועל י-ם גברה על מכבי פ״ת״ היא
# כדורגל, ואין בה אף מילה שמסגירה את זה חוץ מהשם של היריבה. כל שם כאן
# הוצלב מול טבלת ליגת ווינר סל כדי לוודא שהוא לא קבוצת כדורסל שאנחנו
# משחקים מולה.
NOT_US_CLUBS = ("מכבי פתח תקווה", "מכבי פ\"ת", "מכבי פ״ת", "מכבי פ''ת",
                "הפועל רעננה", "בני סכנין", "עירוני קרית שמונה",
                "מכבי בני ריינה", "הפועל כפר סבא")

# תוצאה בכדורסל לא נגמרת 2-1. כותרת עם שני מספרים קטנים היא כדורגל, והיא
# עוברת את רשימת המילים בקלות כי אפשר לכתוב אותה בלי אף מילה מהכדורגל.
SCORE = re.compile(r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)")
# חוץ ממקום אחד שבו מספרים קטנים הם דווקא כדורסל: תוצאה בסדרת פלייאוף.
BASKET = ("כדורסל", "יורוליג", "יורוקאפ", "ווינר", "סדרה", "פלייאוף",
          "פיס ארנה")

DEFAULTS = {
    # שתי השאילתות הראשונות דרשו את המילה ״כדורסל״, וזה מה שהחניק את המדור:
    # רוב הכותרות על המועדון לא כותבות ״כדורסל״ בכותרת. פרוב מ־27.8.2026
    # מדד את זה: השאילתה הרחבה החזירה 58 פריטים טריים ורלוונטיים שלא היו
    # אצלנו, ובהם שלושה מאותו יום שהמדור פשוט לא הכיר.
    "queries": ['"הפועל ירושלים"', '"הפועל י-ם"',
                '"הפועל ירושלים" כדורסל', '"הפועל י-ם" כדורסל'],
    "names": {},
    "block": [],
    "maxItems": 24,
    "maxAgeDays": 45,
}


def log(*a):
    print("[news]", *a, flush=True)


def _config():
    p = DATA / "news-sources.json"
    cfg = dict(DEFAULTS)
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if user.get(k):
                    cfg[k] = user[k]
        except Exception as e:
            log("news-sources.json unreadable, using defaults:", e)
    return cfg


def _clean(s):
    """RSS titles arrive HTML-escaped and occasionally with stray markup."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _strip_source(title, source):
    """Google appends " - Publisher" to every headline. Take it back off,
    but only when the tail really is the publisher, a headline can legally
    end in a dash-separated phrase of its own."""
    if not source:
        return title
    tail = " - " + source
    return title[: -len(tail)].strip() if title.endswith(tail) else title


def _host(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _soccer_score(title):
    """A basketball game does not end 2-1."""
    if any(w in title for w in BASKET):
        return False
    return any(int(a) <= 20 and int(b) <= 20 for a, b in SCORE.findall(title))


def about_us(title):
    """True when the headline itself is about our basketball club."""
    if not any(w in title for w in US):
        return False
    if any(w in title for w in NOT_US) or any(w in title for w in NOT_US_CLUBS):
        return False
    return not _soccer_score(title)


def _published(item):
    raw = item.findtext("pubDate") or ""
    try:
        d = email.utils.parsedate_to_datetime(raw)
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc)


def _fetch_query(q):
    url = FEED.format(q=urllib.parse.quote_plus(q))
    log("GET", q)
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    root = ET.fromstring(r.text.encode("utf-8"))
    return root.findall(".//item")


def collect():
    cfg = _config()
    names = cfg["names"]
    block = {b.lower() for b in cfg["block"]}
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=int(cfg["maxAgeDays"])))

    seen, items = set(), []
    stats = {"raw": 0, "off_topic": 0, "old": 0, "blocked": 0, "dupe": 0}
    for q in cfg["queries"]:
        for it in _fetch_query(q):
            stats["raw"] += 1
            src_el = it.find("source")
            src_raw = _clean(src_el.text if src_el is not None else "")
            src_url = (src_el.get("url") if src_el is not None else "") or ""
            title = _strip_source(_clean(it.findtext("title")), src_raw)
            link = (it.findtext("link") or "").strip()
            when = _published(it)

            if not title or not link or when is None:
                continue
            if not about_us(title):
                stats["off_topic"] += 1
                continue
            if when < cutoff:
                stats["old"] += 1
                continue
            host = _host(src_url)
            if host in block or src_raw.lower() in block:
                stats["blocked"] += 1
                continue
            # two outlets running the identical headline is one story to a fan
            key = re.sub(r"\W+", "", title)
            if key in seen:
                stats["dupe"] += 1
                continue
            seen.add(key)

            items.append({
                "title": title,
                "url": link,
                "source": names.get(host) or names.get(src_raw) or src_raw or host,
                "sourceUrl": src_url,
                "published": when.isoformat(timespec="seconds").replace("+00:00", "Z"),
            })

    items.sort(key=lambda i: i["published"], reverse=True)
    items = items[: int(cfg["maxItems"])]
    log(f"{stats['raw']} items seen · kept {len(items)} · "
        f"dropped: {stats['off_topic']} not about us, {stats['old']} too old, "
        f"{stats['dupe']} duplicates, {stats['blocked']} blocked")
    for i in items[:6]:
        log(f"  {i['published'][:10]}  {i['source']:<14} {i['title'][:66]}")
    return items


def update_news():
    """Write app/data/news.json. Raises if nothing usable came back, so the
    caller records a failure and the previous file survives untouched."""
    items = collect()
    if not items:
        raise RuntimeError("no headlines matched, leaving the previous feed in place")
    sources = []
    for i in items:
        if i["source"] and i["source"] not in sources:
            sources.append(i["source"])
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "note": "כותרות מאתרי הספורט, נאספות דרך חדשות Google. "
                "לחיצה על כותרת פותחת את הכתבה באתר שפרסם אותה.",
        "sources": sources,
        "items": items,
    }
    (DATA / "news.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("wrote news.json -", len(items), "headlines from", len(sources), "outlets")
    return payload


if __name__ == "__main__":
    update_news()
