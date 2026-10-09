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

**צינור השחקנים הניגרי של מועדון הכדורגל, 10.9.2026.** שלוש כותרות על
החתמת ריימונד אוקון, ניגרי בן 18, עברו את כל הכללים. הפרוב שאל את הפיד
על השחקן ומצא שהמועדון בשם הזה מחתים ניגרים כבר שנים: ״מלך הבישולים של
ניגריה חתם בהפועל ירושלים״ (2025), עמודי שחקנים ב־365Scores לצד הפועל
רמת גן והפועל אום אל פאחם, וכיסוי של אליפות אפריקה. כלומר כדורגל.

מה שחשוב בזה הוא לא השחקן אלא הצורה: **בכותרת על החתמה אין שום סימן
לענף.** לא ליגה, לא שער, לא תפקיד, ולא שם של יריבה. שלושת הכללים כאן
קוראים כותרת, ולכן אף אחד מהם לא יכול לתפוס אותה, וגם לא יוכל. הכלי
הנכון למקרים האלה הוא חסימה לפי שם, ‏blockPhrases, שהיא מיידית והפיכה.

**וחסימה גורפת של ״ניגריה״ נשקלה ונדחתה.** היא הייתה תופסת את שלושתן
בבת אחת, אבל היא חוסמת מדינה ולא ענף: ביום שבו נחתום סנטר ניגרי, החדשות
עליו ייעלמו בשקט ואיש לא ידע. הפער נשאר פתוח בכוונה, והוא נסגר בבדיקת
התחזוקה שקוראת את כל הכותרות אחת ליומיים.

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

# **ספורט 5 מקצרת לפעמים ל״י-ם״ בלי ״הפועל״.** נמדד ב־12.9.2026: ״לופטון
# כיכב, י-ם פתחה עם 77:110 על אשדוד״ ו״על אלופת היורוקאפ: 80:87 לי-ם נגד
# בורג״, שתיהן עלינו, שתיהן נפלו כי אין בהן ״הפועל״.
#
# ״י-ם״ לבדו הוא קיצור של ירושלים ולא של המועדון, ולכן הוא לא מספיק: הוא
# מתקבל רק כשיש בכותרת **גם סימן כדורסל**. חסימת בית״ר ושאר NOT_US
# ממשיכה לחול אחרי זה, אז ״בית״ר י-ם״ עדיין נופל.
#
# **ורק צורות המקף, לא צורות הגרשיים.** ‏_norm מוריד גרשיים, ולכן ‏י״ם
# הופך ל־״ים״, שיושב בתוך ״ירושל**ים**״ ובתוך חצי מהמילים בעברית. הוספת
# הצורה הזאת כאן הייתה מכניסה כמעט כל כותרת.
SHORT_US = ("י-ם", "י־ם")
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
          "שלושער", "הבקיע", "נבקיע", "כבש שער", "בעיטת עונשין",
          # תצוגה מקדימה של הרכב היא כדורגל. בכדורסל כותבים חמישייה
          # פותחת, לא הרכב, וכך נכנסו שתי כותרות על משחק הפתיחה של
          # קבוצת הכדורגל מול מכבי ת״א ב־23.8.
          "בהרכב", "שחקני הרכב", "הרכבים",
          # קבוצת הנוער היא לא הקבוצה שהאפליקציה עוסקת בה
          "(נוער)", "לנוער",
          # 365Scores מייצר עמודי משחק אוטומטיים, לא ידיעות. אלה הביטויים
          # שמופיעים בכולם, בכל ענף.
          "תוצאות לייב", "מפגשי עבר",
          # **ועמוד שידור חי הוא לא ידיעה, והוא הופך למטעה בתוך שעה.**
          # ב־26.9 ישבה במדור הכותרת ״הפועל ירושלים - בני הרצליה 20:28
          # (רבע 2)״, כלומר תוצאה חלקית מהרבע השני של משחק שנגמר 68:88.
          # אוהד שקורא את המדור רואה מספר שהיה נכון לשעה אחת ומאז שקרי.
          # ״רבע 2״ בכותרת הוא תמיד תצלום רגע מאמצע משחק, ואף כתבה
          # אמיתית לא נקראת כך.
          "(רבע ", "עדכונים חיים", "דקה אחר דקה")

# **שתי שיטות שנמדדו ונפסלו, 20.9.2026, אחרי שבע כותרות כדורגל ביום
# אחד.** המפרסמים יודעים בדיוק מה הענף וכותבים אותו בכתובת: ספורט 1
# תחת israeli-soccer, ספורט 5 ב־FolderID=64 מול 274 לכדורסל. שתי הדרכים
# להגיע לזה נסגרו במדידה:
#
#   1. **לחלץ את הכתובת האמיתית מהפריט של גוגל.** אין אותה בשום שדה: לא
#      ב־link, לא ב־guid, ולא ב־source שמחזיק רק את שורש האתר.
#   2. **למשוך פיד של המפרסם לפי מדור.** לספורט 5, לספורט 1, ל־ONE
#      ולוואלה אין פיד כזה באף כתובת שנוסתה. מה שקיים במעריב הוא פיד
#      ספורט כללי עם כתבות ישנות, ומאתר אחר.
#
# **וגם האשכול של גוגל נמדד ונפסל.** ה־description של כל פריט מחזיק את
# הכותרות שגוגל קיבצה כאותו סיפור, והרעיון היה שכותרת מוכרעת אחת תכריע
# את כל האשכול. זה עובד, אבל כמעט ולא קורה: כמעט כל פריט הוא אשכול של
# אחד. על שבע הכותרות של 20.9 זה תפס **אחת**, וזו כבר לא הצדקה לשכבה
# חדשה שיש בה גם סיכון לגרור כותרת כדורסל.
#
# **שיטה שנמדדה ונפסלה, 6.9.2026:** לשאול את גוגל את הכותרת פעמיים, פעם
# עם המילה ״כדורגל״ ופעם עם ״כדורסל״, ולראות איזה צד מחזיר יותר. זה לא
# מבחין: חמש כותרות חשודות החזירו 1 מול 1, כלומר בדיוק את אותה כותרת
# משני הצדדים, וגם ביקורת שידוע שהיא כדורסל (התביעה על קרינגטון) יצאה
# 4 מול 6 בלבד. גוגל מוצאת את הכותרת עצמה ומתעלמת מהמילה שהוספנו.
#
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
                "עירוני טבריה", "טבריה", "הפועל חדרה", "מ.ס. אשדוד", "מ.ס אשדוד",
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
    """ביטויים שנחסמו ביד ב־news-sources.json.

    **ולמה זה עדיין קיים, אחרי כל השכבות.** ב־22.9.2026 ישבו במדור שתי
    כותרות כמעט זהות על חסות מדים: ״זה המותג שיעלה על המדים״ ו״השם
    החדש שתראו על מדי הפועל ירושלים״. הראשונה היא הכדורגל, כי הלוגו
    עולה על לוח התוצאות בטדי והמנכ״ל מדבר על מגרשי כדורגל. השנייה היא
    שלנו, כי השם החדש הוא ״הפועל מידטאון ירושלים״. שום כלל שקורא כותרת
    לא יכול להפריד ביניהן, ורק בדיקה חיצונית של כל אחת הכריעה.
    """
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
    # ״חוד״ הוא חוד ההתקפה, ואצלנו אין כזה. הכותרת ״הרכש החדש מיועד
    # לפתוח בחוד״ עברה את כל הסינון ב־18.9, כי חוץ מהמילה הזאת אין בה
    # שום סימן לענף.
    #
    # **וזה צר בכוונה, אחרי שהגרסה הרחבה נפלה בבדיקה:** ״בחוד״ לבדו
    # חוסם גם ״הפועל ירושלים בחוד הטבלה״ וגם ״בחוד החנית״, ושתיהן עברית
    # תקינה לגמרי אצלנו. לכן רק ״בחוד ההתקפה״, או ״בחוד״ בסוף הכותרת.
    re.compile(r"(^|\s)בחוד(\s+ההתקפה|\s*[,.:]|\s*$)"),
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


# ============================================================================
# ההצלבה מול לוח המשחקים שלנו
#
# **למה זה קיים.** מועדון הכדורגל חולק איתנו את השם, ועונת הליגה שלו
# התחילה ב־15.9.2026. מאז מגיע סיקור משחק שלו כל שבוע, ולכותרת כזאת אין
# שום סימן לענף: לא ליגה, לא שער, לא תפקיד ולא שם של יריבה. שלוש כאלה
# נכנסו למדור בשלושה ימים, וכל אחת דרשה בדיקה ידנית כדי להכריע.
#
# **מה שהכריע בכל שלוש הפעמים לא היה בכותרת אלא מחוצה לה:** לקבוצת
# הכדורסל שלנו לא היה משחק באותו יום. זה נתון שיש לנו בבית, ב־games.json,
# והכלל כאן הופך אותו לבדיקה.
#
# **הכלל צר בכוונה, ושלושת התנאים חייבים להתקיים יחד:**
#
#   1. בכותרת יש סימן שמשחק בדיוק נגמר: פועל של תוצאה, המילה ״משחק״,
#      ״מחזור״, או תבנית של תוצאה.
#   2. אין בכותרת שום סימן כדורסל. כותרת שכתוב בה ״גביע ווינר״ היא שלנו
#      גם אם לא שיחקנו אתמול, כי היא בוודאי לא על הכדורגל.
#   3. לא שיחקנו בחלון סביב מועד הפרסום.
#
# **והחלון רחב בכוונה:** יומיים אחורה ויממה קדימה. חלון רחב גורם לכלל
# לירות **פחות**, וזה הכיוון הבטוח: כותרת כדורגל שנשארה היא מטרד, וכותרת
# כדורסל שנחסמה נעלמת בלי להשאיר סימן.
#
# **וכשאין לוח, הכלל לא חל.** קובץ חסר או שבור מחזיר רשימה ריקה, ואז
# ״לא שיחקנו״ לא ניתן לקביעה, והכותרת נשארת.

# פועל של תוצאה, או המילה משחק. ״עלתה ל״ נכנס כי הוא מסמן העפלה אחרי
# משחק, ו״הודחה״ מהצד השני.
# **ומה שבכוונה אינו כאן: ״ניצחון״ ו״הפסד״ כשמות עצם.** הם מופיעים גם
# בתצוגה מקדימה (״מחפשת ניצחון ראשון״), ותצוגה מקדימה מתפרסמת לפעמים
# שלושה ימים לפני המשחק, כלומר מחוץ לחלון. הם היו קונים כיסוי במחיר
# חסימה של כותרות כדורסל אמיתיות. אותו שיקול פסל מילות רגש כמו ״תסכול״,
# שמופיעות גם בידיעה על פציעה ביום שלא שיחקנו בו.
MATCH_WORDS = (
    "ניצח", "הפסיד", "גבר", "נכנע", "הביס", "פירק", "הודח", "העפיל",
    "תיקו", "משחק", "מחזור", "דרבי", "רבע גמר", "חצי גמר", "עלתה ל",
    "איבדה נקודות", "השיגה נקודה",
)
# תוצאה כתובה, בכל אחת משתי הצורות שהעיתונות משתמשת בהן
MATCH_SCORE = re.compile(r"\b\d{1,3}\s*[:\-]\s*\d{1,3}\b")


def our_game_times():
    """מועדי המשחקים שלנו, מהלוח שכבר נאסף. רשימה ריקה כשאין לוח."""
    try:
        raw = json.loads(
            (DATA / "games.json").read_text(encoding="utf-8")).get("games") or []
    except Exception:
        return []
    out = []
    for g in raw:
        try:
            d = datetime.datetime.fromisoformat(g["date"])
        except Exception:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        out.append(d.astimezone(datetime.timezone.utc))
    return out


PLAYED_BEFORE = datetime.timedelta(hours=48)
PLAYED_AFTER = datetime.timedelta(hours=24)


def played_around(when, games):
    """האם שיחקנו בחלון סביב הרגע הזה."""
    if not when or not games:
        return True          # בלי נתון, מניחים שכן, והכלל לא חל
    return any(when - PLAYED_BEFORE <= g <= when + PLAYED_AFTER for g in games)


# SCORE מוגבל לשתי ספרות, כי הוא מחפש תוצאות כדורגל. כאן צריך שלוש:
# ״הפסידה 104:95״ לא נתפסה בלעדיה, וזו בדיוק הכותרת שהכי חשוב להגן עליה.
ANY_SCORE = re.compile(r"(?<!\d)(\d{1,3})\s*[-:]\s*(\d{1,3})(?!\d)")


def _basketball_score(title):
    """תוצאה כמו 69:83 היא משחק כדורסל, וזה כל מה שצריך לדעת.

    **זה נוסף אחרי מדידה, לא מראש.** בלעדיו שלוש כותרות כדורסל אמיתיות
    היו תלויות רק בלוח המשחקים: ״הפועל י־ם הפסידה 104:95 לריטאס וילנה״
    לא מכילה שום מילה מזהה, ואם המשחק חסר מהלוח או שהסיקור הגיע יומיים
    אחריו, היא הייתה נחסמת בשקט. זה ההפך המדויק של _soccer_score, שקובע
    שתוצאה של עד 20 היא כדורגל.
    """
    return any(int(a) >= 40 and int(b) >= 40 for a, b in ANY_SCORE.findall(title))


def other_sport_match_report(title, when, games):
    """כותרת על משחק שהיה, ביום שבו אנחנו לא שיחקנו.

    מחזירה את הסיבה כמחרוזת, או None כשהכלל לא חל. הסיבה נרשמת בלוג, כי
    כותרת שנעלמת בלי סימן היא בדיוק מה שאי אפשר לתקן אחר כך.
    """
    flat = _norm(title)
    if any(_norm(w) in flat for w in BASKET) or _basketball_score(title):
        return None
    hit = [w for w in MATCH_WORDS if w in title]
    if not hit and not MATCH_SCORE.search(title):
        return None
    if played_around(when, games):
        return None
    if not hit:
        hit = ["תוצאה כתובה"]
    return f"סימני משחק {hit} ולנו לא היה משחק בסביבות {when:%d.%m}"


# **עמוד מפגש הוא לא ידיעה, וכל משחק מייצר אחד.** למדור נכנסו שתי
# כותרות כאלה: ״מכבי אשדוד נגד הפועל ירושלים״ מ־ONE ב־8.9, ו״א. לובליאנה
# נגד הפועל ירושלים - יורוקאפ - מחזור 1״ מאותו אתר ב־6.10. אין בהן
# ידיעה, יש בהן תווית: שני שמות קבוצות והמפגש ביניהן. ספורט 5 מייצרת את
# אותו עמוד בנוסח ״סיקור משחק X נגד Y״, שפורסם שעה ועשרים לפני השריקה.
#
# זה חוזר פעם או פעמיים בכל משחק, וליתר העונה זה 26 מחזורי ליגה ועוד
# יורוקאפ, כלומר שתי משבצות מתוך שלושים שהמדור מבזבז על עמודים ריקים.
#
# **ההפרדה היא המבנה ולא המילים.** בעמוד מפגש הכותרת היא תווית שטוחה:
# אין בה נקודתיים, פסיק, מרכאות או סימן שאלה. בכותרת אמיתית שמזכירה
# ״נגד״ תמיד יש אחד מאלה, ובכל ארבע הכותרות האמיתיות בהיסטוריה שמכילות
# ״נגד״ אלה נקודתיים: ״במיליונים: תביעת הפועל ירושלים נגד הפועל ת״א״.
#
# נמדד על 168 הכותרות הייחודיות שעברו במדור: הכלל תופס בדיוק את שני
# עמודי המפגש ואת עמוד הסיקור של ספורט 5, ואף כותרת אחרת.
#
# כל חסימה נרשמת ללוג, כמו תמיד, כי כותרת שנעלמה בשקט היא מה שאי אפשר
# לגלות בדיעבד.
LIVE_PAGE = (
    re.compile(r"^\s*סיקור\s+משחק\s"),
    re.compile(r"^[^:,\"\u05f4?!]+\sנגד\s[^:,\"\u05f4?!]+$"),
)


def about_us(title):
    """True when the headline itself is about our basketball club."""
    flat = _norm(title)
    if not any(_norm(w) in flat for w in US):
        # הקיצור של ספורט 5, ורק לצד סימן כדורסל. ראו SHORT_US.
        if not (any(_norm(w) in flat for w in SHORT_US)
                and any(_norm(w) in flat for w in BASKET)):
            return False
    if any(_norm(w) in flat for w in NOT_US) or any(_norm(w) in flat for w in soccer_clubs()):
        return False
    if any(_norm(w) in flat for w in blocked_phrases()):
        return False
    if any(r.search(title) for r in SOCCER_ROLE):
        return False
    if any(r.search(title.strip()) for r in LIVE_PAGE):
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


# **הזמן שראינו ראשון הוא הזמן שנשאר.** גוגל מדווחת את מועד הפרסום
# במדויק כל עוד הידיעה טרייה, ואחרי כמה ימים היא מחליפה אותו בתאריך גס:
# אותו יום בשעה 07:00 בדיוק. עד כאן זה שלה, אבל אנחנו דרסנו בו את הזמן
# המדויק שכבר היה בידינו, וזה כן שלנו.
#
# נמדד ב־7.10.2026 על 65 הגרסאות של news.json בגיט: 28 כותרות עברו
# ל־07:00, כולן מזמן מדויק וכולן אחרי שהידיעה התיישנה. הכתבה של הארץ על
# 68:88 מול הרצליה נכתבה ב־25.9 בשעה 12:58, כך נרשמה אצלנו שמונה איסופים
# ברצף, וב־3.10 הפכה ל־07:00.
#
# האוהד רואה את זה בשני מקומות: התאריך היחסי מתחת לכותרת, והסדר, כי
# המדור ממוין לפי הזמן וכותרות שהתאריך שלהן זז מקפצות במדור.
#
# **ומה שהנעילה לא פותרת, וכתוב כאן כדי שלא ייראה כאילו כן.** הידיעה של
# 0404 על 88:71 בחצי הגמר, משחק של 4.10, מתוארכת ל־3.10 בשעה 07:00, יום
# לפני המשחק שהיא מסקרת. שם הזמן היה שגוי כבר בתצפית הראשונה, ולנעילה אין
# מה לשחזר. הארץ סיקרה את אותו משחק בכותרת אחרת ובזמן נכון, 4.10 בשעה
# 18:14, אז זו לא כפילות שאפשר לנכש. אפשר היה להסיק את הזמן הנכון מהלוח
# שלנו, אבל זה כבר זמן שלא ראינו בשום מקום, וזמן מומצא הוא לא תיקון.
#
# הכלל פשוט בכוונה: לא בוחרים בין שני זמנים ולא מחליטים מי מהם נראה
# אמין, אלא נועלים את הראשון. הוא נרשם כשהפיד היה מדויק, וזה היתרון
# היחיד שאפשר להוכיח.
def _item_key(title):
    """אותו מפתח שמשמש לזיהוי כפילויות: כותרת בלי רווחים ובלי פיסוק."""
    return re.sub(r"\W+", "", title)


def _iso(raw):
    try:
        when = datetime.datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except Exception:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when.astimezone(datetime.timezone.utc)


def first_seen(items):
    """מתי כל כותרת במדור הקיים נרשמה אצלנו בפעם הראשונה."""
    out = {}
    for it in items or ():
        when = _iso(it.get("published"))
        if it.get("title") and when is not None:
            out[_item_key(it["title"])] = when
    return out


def keep_first(known, title, when):
    """הזמן שנרשם אצלנו, אם הכותרת כבר הייתה במדור. אחרת זמן הפיד."""
    return known.get(_item_key(title), when)


def _stored_items():
    try:
        return json.loads(
            (DATA / "news.json").read_text(encoding="utf-8")).get("items") or []
    except Exception:
        return []


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
    stats = {"raw": 0, "off_topic": 0, "old": 0, "blocked": 0, "dupe": 0,
             "other_sport": 0, "pinned": 0}
    known = first_seen(_stored_items())
    fixtures = our_game_times()
    log(f"לוח המשחקים להצלבה: {len(fixtures)} משחקים"
        if fixtures else "אין לוח משחקים, ההצלבה מול המשחקים לא תחול")
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
            # הנעילה קודמת לכל בדיקה שתלויה בזמן, כדי שגם הגיל וגם
            # ההצלבה מול הלוח יישענו על אותו זמן שהאוהד יראה
            first = keep_first(known, title, when)
            if first != when:
                stats["pinned"] += 1
                when = first
            if not about_us(title):
                stats["off_topic"] += 1
                continue
            if when < cutoff:
                stats["old"] += 1
                continue
            # ההצלבה מול הלוח שלנו. נרשמת בלוג תמיד, כי כותרת שנעלמת
            # בלי סימן היא בדיוק מה שאי אפשר לתקן אחר כך.
            why = other_sport_match_report(title, when, fixtures)
            if why:
                stats["other_sport"] += 1
                log(f"  לא שיחקנו, ולכן זה לא אנחנו: {title[:64]}")
                log(f"    {why}")
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
        f"{stats['dupe']} duplicates, {stats['blocked']} blocked, "
        f"{stats['other_sport']} match reports on days we did not play")
    if stats["pinned"]:
        log(f"  {stats['pinned']} כותרות שמרו על הזמן שנרשם אצלנו, "
            f"כי גוגל דיווחה עליהן זמן אחר")
    for i in items[:6]:
        log(f"  {i['published'][:10]}  {i['source']:<14} {i['title'][:66]}")
    return items


# **קצב המדור: פעם ביומיים.** גבי ביקש את זה ב־27.9.2026, ויש לזה גם
# היגיון מעבר להעדפה: מדור החדשות הוא המקום היחיד שבו מגיע אלינו תוכן
# שאף כלל לא מסווג בוודאות, וכל אצווה חדשה היא הזדמנות לכותרת כדורגל
# להגיע למסך האוהד. בדיקת התחזוקה רצה גם היא פעם ביומיים, ולכן הקצב הזה
# אומר שכל אצווה נקראת בעיניים זמן קצר אחרי שהיא נוחתת, במקום לשבת
# יומיים בלי שאף אחד ראה אותה.
#
# הזמן נמדד מול ה־updated שבקובץ עצמו ולא מתחילת המשמרת, בדיוק מאותה
# סיבה שהאיסוף נמדד מול meta.json: משמרת חדשה מתחילה כמה פעמים ביום.
NEWS_EVERY = datetime.timedelta(hours=48)

# **וחצי מרווח איסוף של חסד, אחרת ״פעם ביומיים״ הוא בפועל יומיים וחצי.**
# הגייט נבדק רק כשהאיסוף רץ, והאיסוף רץ על רשת של 11 שעות, אז השוואה
# ישירה ל־48 כמעט תמיד מחמיצה ומתקנת רק בסיבוב הבא. נמדד ב־3.10.2026:
# באיסוף של 09:17 המדור היה בן 47 שעות, דילג, והרענון נדחה ל־20:30,
# כלומר 58 שעות. ההטיה הזאת שיטתית ומצטברת.
#
# החסד מרכז את הרענון סביב 48 במקום לדחוף אותו תמיד מעבר: עם סף של
# 42.5 שעות הוא נוחת בין 42.5 ל־53.5, ובמקרה שנמדד היה נוחת על 47.
NEWS_GRACE = datetime.timedelta(hours=5, minutes=30)


def news_age():
    """כמה זמן עבר מאז שהמדור נכתב, או None כשאין קובץ או שאין בו חתימה."""
    try:
        raw = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["updated"]
        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc) - when


def update_news(force=False):
    """Write app/data/news.json. Raises if nothing usable came back, so the
    caller records a failure and the previous file survives untouched.

    **בלי force הפעולה מדלגת על מדור שנכתב לפני פחות מ־NEWS_EVERY.** זה
    הגייט של האיסוף המתוזמן, ולכן הוא לא חל על הרצה ידנית: ‏
    ``python scripts/news_feed.py`` אוסף תמיד, וזה הרענון בזמן תחזוקה.
    """
    age = news_age()
    if not force and age is not None and age < NEWS_EVERY - NEWS_GRACE:
        left = NEWS_EVERY - NEWS_GRACE - age
        log(f"המדור נכתב לפני {age.total_seconds() / 3600:.1f} שעות, "
            f"והקצב הוא פעם ביומיים. הבא בעוד {left.total_seconds() / 3600:.1f} שעות.")
        return (f"הקצב הוא פעם ביומיים, והמדור נכתב לפני "
                f"{age.total_seconds() / 3600:.0f} שעות")
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
    # הרצה ידנית היא בקשה מפורשת, ולכן היא עוקפת את הגייט של הקצב
    update_news(force=True)
