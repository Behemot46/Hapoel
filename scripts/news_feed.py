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

The obvious shortcut, asking Google for the name minus the word כדורגל, was
measured on 27.8.2026 and rejected. Google matches the whole page, sidebars
and tags included, so a basketball article on a sports site loses just as
often as a football one: the short-name query fell from 17 kept headlines
to 4, and among the dead were the EuroLeague bid coverage and the new kit.
The filtering has to happen here, on the headline, one rule at a time.
"""
import datetime
import email.utils
import html
import json
import pathlib
import re
import time
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
          # תצוגה מקדימה של הרכב היא כדורגל. בכדורסל כותבים חמישייה
          # פותחת, לא הרכב, וכך נכנסו שתי כותרות על משחק הפתיחה של
          # קבוצת הכדורגל מול מכבי ת״א ב־23.8.
          "בהרכב", "שחקני הרכב", "הרכבים",
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
# מועדוני כדורגל ישראליים. כותרת שמזכירה אותנו לצד אחד מהם היא כדורגל,
# וזה הכלל היחיד שתופס כותרת כמו ״מדמון ייעדר מול הפועל פ״ת״, שאין בה אף
# מילה מהכדורגל חוץ מהשם של היריבה.
#
# **הרשימה הזאת לא נסמכת על הזיכרון שלי לגבי מי משחק באיזה ענף.** לפני
# שהיא מופעלת היא מוצלבת מול יקום הכדורסל שלנו, כלומר טבלת הליגה
# והיריבות שלנו העונה, וכל שם שנמצא שם יורד ממנה. כך שם שמשמש את שני
# הענפים, או מועדון שיעלה לליגת הכדורסל בעונה הבאה, לא יחסום לנו חדשות
# כדורסל אמיתיות. מה שיורד נרשם בלוג של האיסוף.
SOCCER_CLUBS = ("מכבי פתח תקווה", "מכבי פ\"ת", "מכבי פ״ת", "מכבי פ''ת",
                "הפועל פתח תקווה", "הפועל פ\"ת", "הפועל פ״ת", "הפועל פ''ת",
                "הפועל רעננה", "בני סכנין", "עירוני קרית שמונה",
                "מכבי בני ריינה", "הפועל כפר סבא", "מכבי נתניה",
                "עירוני טבריה", "הפועל חדרה", "מ.ס. אשדוד", "מ.ס אשדוד",
                "הפועל עכו", "הפועל ניר רמת השרון", "מכבי הרצליה",
                "הפועל רמת גן", "הפועל נוף הגליל", "הפועל אום אל פחם",
                "הפועל ראשון לציון", "מכבי חיפה", "הפועל חיפה",
                "מכבי קריית ים", "הפועל כפר שלם", "הפועל ירושלים בכדורגל",
                "מכבי קריית גת", "קריית גת", "קרית גת")


def _norm(s):
    """אותו שם נכתב בכמה צורות, וההשוואה חייבת להיות עיוורת להן.

    ״הפועל פתח תקוה״ בכותרת מול ״הפועל פתח תקווה״ ברשימה הן אותה קבוצה,
    וההבדל היחיד הוא וו אחת. בדיוק ההבדל הזה החזיר לנו את הכותרת
    ״קימבידי כבש, הפועל פתח תקוה השיגה נקודות ראשונות העונה מול הפועל
    ירושלים״, שהיא כדורגל מהמילה הראשונה עד האחרונה. אותו סיפור עם
    גרשיים: פ״ת, פ"ת ופת הם אותו דבר.

    הנרמול מופעל על שני הצדדים, על הכותרת ועל הרשימה, ולכן הוא לא יכול
    ליצור אי־התאמה חדשה.
    """
    s = s or ""
    for ch in ('"', "״", "'", "׳", "`"):
        s = s.replace(ch, "")
    return s.replace("וו", "ו")


def _our_basketball_world():
    """השמות שאנחנו חיים בתוכם: טבלת הליגה והיריבות שלנו העונה."""
    names = set()
    for fn, key in (("standings.json", "rows"), ("games.json", "games")):
        try:
            d = json.loads((DATA / fn).read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in (d.get(key) or []):
            for k in ("team", "home", "away"):
                v = (row.get(k) or "").strip()
                if v:
                    names.add(v)
    return names


_phrases_cache = None


def blocked_phrases():
    """ביטויים שנחסמו ביד ב־news-sources.json."""
    global _phrases_cache
    if _phrases_cache is None:
        _phrases_cache = tuple(_config().get("blockPhrases") or ())
    return _phrases_cache


_clubs_cache = None


def soccer_clubs():
    global _clubs_cache
    if _clubs_cache is not None:
        return _clubs_cache
    world = {_norm(t) for t in _our_basketball_world()}
    live, dropped = [], []
    for name in SOCCER_CLUBS:
        n = _norm(name)
        if any(n in team or team in n for team in world):
            dropped.append(name)
        else:
            live.append(name)
    if dropped:
        log("לא ייחסמו, כי הם ביקום הכדורסל שלנו:", ", ".join(dropped))
    _clubs_cache = tuple(live)
    return _clubs_cache

# תפקיד בכדורגל הוא לא תפקיד בכדורסל. אצלנו כותבים רכז, קלע, כנף,
# פורוורד וסנטר, ואף פעם לא חלוץ, קיצוני או בלם. הכותרת ״קיצוני ממיטיולן
# סיכם בהפועל ירושלים״ עברה את כל הסינון הקודם כי אין בה שום מילה
# מהכדורגל חוץ מהתפקיד עצמו, וגם היריבה בה היא מועדון דני שלעולם לא יהיה
# ברשימת המועדונים הישראליים. אותו סיפור פורסם אחר כך כ״חלוץ ממיטיולן״.
#
# הביטויים כתובים כביטוי רגולרי ולא כרשימת מילים, כי ״קיצוני״ הוא גם שם
# תואר תמים (״שינוי קיצוני״) והוא נחשב תפקיד רק כשמגיע אחריו מקור או
# שייכות, ו״כבש״ הוא גם כיבוש (״כבשה את אירופה״) והוא נחשב שער רק כשלא
# בא אחריו ״את״.
SOCCER_ROLE = (
    re.compile(r"(^|\s)[הלכבו]?חלוץ(\s|,|\.|:|$)"),
    re.compile(r"(^|\s)[הלכבו]?קיצוני\s+(מ|של|ה)"),
    re.compile(r"(^|\s)[הלכבו]?בלם(\s|,|\.|:|$)"),
    re.compile(r"כבש(?!\s+את)(\s|,|\.|$)"),
)

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
    # ביטויים שנחסמים ביד. יש סיפורים ששום כלל אוטומטי לא יסווג נכון, כי
    # הם על ״הפועל ירושלים״ בלי שום רמז לענף. הרשימה הזאת היא המקום
    # להגיד ״הסיפור הזה הוא של הכדורגל״ בלי לגעת בקוד.
    "blockPhrases": [],
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
    flat = _norm(title)
    if not any(_norm(w) in flat for w in US):
        return False
    if any(_norm(w) in flat for w in NOT_US) or any(_norm(w) in flat for w in soccer_clubs()):
        return False
    if any(_norm(w) in flat for w in blocked_phrases()):
        return False
    if any(r.search(title) for r in SOCCER_ROLE):
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


def _fetch_query(q, tries=3):
    """גוגל מחזירה 503 מדי פעם, במיוחד כששואלים אותה כמה פעמים ברצף
    מאותה כתובת. זה חולף, אז מנסים שוב לפני שמוותרים."""
    url = FEED.format(q=urllib.parse.quote_plus(q))
    log("GET", q)
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            return ET.fromstring(r.text.encode("utf-8")).findall(".//item")
        except Exception as e:
            if attempt == tries:
                raise
            log(f"  ניסיון {attempt} נכשל ({e}), עוד רגע ננסה שוב")
            time.sleep(attempt * 3)


def collect():
    cfg = _config()
    names = cfg["names"]
    block = {b.lower() for b in cfg["block"]}
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=int(cfg["maxAgeDays"])))

    seen, items = set(), []
    stats = {"raw": 0, "off_topic": 0, "old": 0, "blocked": 0, "dupe": 0}
    # שאילתה אחת שנופלת היא לא סיבה לזרוק את השלוש האחרות. ב־27.8.2026
    # גוגל החזירה 503 על הראשונה, וכל האיסוף מת איתה: המדור נשאר עם
    # הקובץ הישן בזמן ששלוש שאילתות תקינות חיכו בתור.
    dead = []
    for q in cfg["queries"]:
        try:
            batch = _fetch_query(q)
        except Exception as e:
            dead.append(q)
            log(f"שאילתה נפלה, ממשיכים בלעדיה: {q} ({e})")
            continue
        for it in batch:
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

    if dead and len(dead) == len(cfg["queries"]):
        raise RuntimeError("כל השאילתות נפלו")
    if dead:
        log("שאילתה אחת" if len(dead) == 1 else f"{len(dead)} שאילתות",
            f"מתוך {len(cfg['queries'])} לא ענתה" if len(dead) == 1
            else f"מתוך {len(cfg['queries'])} לא ענו")

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
