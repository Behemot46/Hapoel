"""לוח המשחקים מאתר המועדון, hapoel.co.il/games.

זה מקור האמת הראשי ללוח, ומשתי סיבות. האחת, הוא היחיד שמפרסם משחקי הכנה
בכלל: אתר הליגה מנהל רק משחקים רשמיים והפיד של היורוקאפ רק את אירופה, ולכן
לוח שנשען רק עליהם מכריז על משחק שבעוד שבועיים בזמן שהקבוצה משחקת מחר.
השנייה, הוא של המועדון, וכשהוא סותר מקור אחר הוא זה שצודק לגבי הקבוצה שלו.

מבנה בלוק אחד בעמוד, כפי שנקרא מהמקור החי:

    .game
      .date-data .date-time      ״12 בספטמבר, שבת 16:30״   בלי שנה
      .date-data .cycle          ״משחקי הכנה״
      .league .game-type .text   ״וילנה״                    המקום
      .league .game-type .text   ״5STARS״                   השידור, אם יש
      .teams .teams-container img[alt] x2                    שתי הקבוצות, לפי סדר
      .game-data .score          ״0:0״

שלוש מוסכמות שנקראו מהנתונים עצמם ולא הונחו, כי כל אחת מהן מתהפכת בשקט:

**הראשונה היא המארחת.** נבדק על שלושה משחקים שהתשובה בהם ידועה ממקור אחר:
מכבי אשדוד ב־8.9 מופיעה ראשונה והמקום הוא הקריה אשדוד, בדיוק כמו בפיד
הליגה; ב״ש ב־18.9 מופיעה שנייה והמקום פיס ארנה; לובליאנה ב־6.10 ראשונה
והמקום לובליאנה. בכל משחקי החוץ היריבה ראשונה וגם המקום הוא העיר שלה.

**0:0 הוא ״טרם שוחק״.** כל 19 המשחקים בעמוד מציגים 0:0, כולל אלה שטרם
נשחקו. בכדורסל אין תיקו 0:0, ולכן אפשר לקרוא אותו כהיעדר תוצאה בלי סיכון.

**אין שנה בתאריך.** החודשים רצים אוגוסט עד ינואר, כלומר העונה חוצה שנה
אזרחית. חודש מספטמבר ומעלה שייך לשנת הפתיחה, ינואר עד יולי לזו שאחריה.

**השידור יושב באותו סלקטור של המקום, אחריו.** זה המקור **היחיד** שמפרסם
אותו: אתר הליגה לא מחזיק עמודת שידור, ועמודי לוח השידורים של ספורט 5 ושל
ONE מחזירים 404 (נמדד 11.9.2026). לכן `.game-type .container .text` מוחזר
כרשימה ולא ב־select_one, ומיקום 0 הוא המקום ומיקום 1 השידור.

ושלוש עובדות על השדה הזה, כדי שלא יצפו ממנו ליותר ממה שיש בו. על פני 42
כרטיסים הוא הופיע **שלוש פעמים בלבד**: ״5STARS״ פעם אחת, ו״שידור טרם
נקבע״ פעמיים. כלומר ברוב המשחקים המועדון לא כתב כלום, וזה **לא** אומר
שהמשחק לא משודר, רק שאיננו יודעים. ההבחנה בין השלושה נשמרת בנתונים: ערוץ,
״טרם נקבע״ שהוא אמירה של המועדון, והיעדר מוחלט שהוא היעדר ידיעה.
"""
import datetime
import re

from bs4 import BeautifulSoup

GAMES_URL = "https://hapoel.co.il/games"

MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5,
    "יוני": 6, "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10,
    "נובמבר": 11, "דצמבר": 12,
}

# איך המועדון קורא לעצמו בעמוד הזה
US = "הפועל י-ם"
TEAM = "הפועל ירושלים"

# שם המסגרת אצל המועדון מול השם שהאפליקציה מציגה
COMPETITION = {
    "משחקי הכנה": "משחק הכנה",
    "גביע ווינר סל": "גביע ווינר סל",
    "יורוקאפ": "יורוקאפ",
}

# חודש שממנו ומעלה עדיין שנת הפתיחה של העונה
SEASON_SPLIT = 8


def _txt(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def is_us(name):
    n = (name or "").strip()
    return "הפועל" in n and ("י-ם" in n or "ירושלים" in n or "י״ם" in n)


def parse_when(raw, season_start, log=None):
    """״12 בספטמבר, שבת 16:30״ -> (date, time or None).

    השעה יכולה להיות ״טרם נקבע״, וזה מצב אמיתי שהמועדון מפרסם. במקרה כזה
    מוחזר None ולא שעה מומצאת, והקורא מחליט מה לעשות עם זה.
    """
    m = re.search(r"(\d{1,2})\s+ב?([א-ת]+)", raw or "")
    if not m:
        return None, None
    day, month_name = int(m.group(1)), m.group(2)
    month = MONTHS.get(month_name)
    if not month:
        if log:
            log(f"  לוח המועדון: חודש לא מוכר {month_name!r} בתוך {raw!r}")
        return None, None
    year = season_start if month >= SEASON_SPLIT else season_start + 1
    try:
        date = datetime.date(year, month, day)
    except ValueError:
        if log:
            log(f"  לוח המועדון: תאריך לא תקין מתוך {raw!r}")
        return None, None
    t = re.search(r"(\d{1,2}):(\d{2})", raw or "")
    time = (int(t.group(1)), int(t.group(2))) if t else None
    return date, time


def _score(raw):
    """המועדון כותב תוצאה כ־A:B. 0:0 פירושו שהמשחק טרם שוחק."""
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", raw or "")
    if not m:
        return None, None
    a, b = int(m.group(1)), int(m.group(2))
    if a == 0 and b == 0:
        return None, None
    return a, b


# מה שהמועדון כותב כשהוא יודע שיש משחק אבל עוד לא מי משדר אותו. זו
# אמירה, לא היעדר ידיעה, ולכן היא נשמרת בנפרד מ״לא כתוב כלום״.
TV_PENDING = "שידור טרם נקבע"


def _venue_and_tv(g):
    """המקום והשידור יושבים באותו סלקטור, בזה אחר זה.

    לא לפי מיקום קשיח: כרטיס שאין לו מקום אבל יש לו שידור היה מציב את
    הערוץ במיקום 0, ואז שם הערוץ היה מופיע לאוהד ככתובת האולם. לכן כל
    תא נשאל מה הוא, והראשון שאינו שידור הוא המקום.
    """
    cells = [_txt(c) for c in g.select(".game-type .container .text")]
    cells = [c for c in cells if c]
    venue, tv = None, None
    for c in cells:
        if c == TV_PENDING:
            tv = {"pending": True}
        elif _looks_like_channel(c):
            tv = {"channel": c}
        elif venue is None:
            venue = c
    return venue, tv


# שמות הערוצים שמשדרים כדורסל ישראלי, כפי שהמועדון כותב אותם. הרשימה
# קצרה בכוונה: עדיף שערוץ חדש ייפול לכאן כ״מקום״ ויתוקן, מאשר שכתובת
# אולם שלא הכרנו תוצג לאוהד כערוץ טלוויזיה.
#
# **וספקי הכבלים אינם ברשימה, וזה לא שכחה.** ״יס״ ו״הוט״ הם ספקים ולא
# ערוצים, והם גם קצרים מדי: הגרסה הראשונה של הקוד כללה את ״יס״, והמחרוזת
# הזאת יושבת בתוך ״פ**יס** ארנה, ירושלים״. התוצאה הייתה שהאולם הביתי שלנו
# סווג כערוץ טלוויזיה והמשחק הוצג בלי מקום.
CHANNELS = ("5STARS", "5 STARS", "ספורט 5", "SPORT 5", "SPORT5", "ONE",
            "ערוץ הספורט", "כאן 11", "WinnerLeague.TV")

# ההתאמה היא על מילה שלמה ולא על תת־מחרוזת, מאותה סיבה בדיוק.
_CHANNEL_RE = re.compile(
    "|".join(r"(?<![א-תA-Za-z0-9])" + re.escape(c) + r"(?![א-תA-Za-z0-9])"
             for c in sorted(CHANNELS, key=len, reverse=True)),
    re.IGNORECASE)


def _looks_like_channel(s):
    return bool(_CHANNEL_RE.search(s))


def parse_games(html, season_start, log=None):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for g in soup.select(".game"):
        teams = [i.get("alt", "").strip()
                 for i in g.select(".teams-container img") if i.get("alt")]
        if len(teams) < 2:
            continue
        raw_when = _txt(g.select_one(".date-time"))
        date, time = parse_when(raw_when, season_start, log=log)
        if not date:
            continue
        if not any(is_us(t) for t in teams):
            if log:
                log(f"  לוח המועדון: מדלג על משחק שאיננו שלנו, {teams}")
            continue

        home_raw, away_raw = teams[0], teams[1]
        a, b = _score(_txt(g.select_one(".score")))
        played = a is not None

        # השעה נכתבת בשעון ישראל. משחק בלי שעה נשמר על אמצע היום עם סימון,
        # כי תאריך נכון בלי שעה עדיף על שעה מומצאת.
        # למה 12:00 ולא חצות: האפליקציה מציגה תאריכים בשעון של המכשיר,
        # ולכן חצות בישראל היא היום הקודם אצל כל אוהד שנמצא ממערב לנו.
        # אמצע היום שורד כל אזור זמן סביר, והשעה עצמה לא מוצגת ממילא כי
        # timeTbd מסמן שאין מה להציג.
        hh, mm = time if time else (12, 0)
        when = datetime.datetime(date.year, date.month, date.day, hh, mm,
                                 tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
        opp = away_raw if is_us(home_raw) else home_raw
        cycle = _txt(g.select_one(".cycle"))
        venue, tv = _venue_and_tv(g)
        game = {
            "id": f"{date:%Y%m%d}-club-" + re.sub(r"[^א-תA-Za-z]", "", opp)[:12],
            "date": when.isoformat(),
            "competition": COMPETITION.get(cycle, cycle or "משחק"),
            "home": TEAM if is_us(home_raw) else home_raw,
            "away": TEAM if is_us(away_raw) else away_raw,
            "venue": venue or None,
            "status": "finished" if played else "scheduled",
            "homeScore": a,
            "awayScore": b,
            "source": "club",
        }
        if not time:
            game["note"] = "שעת הפתיחה טרם נקבעה"
            # דגל מפורש לצד ההערה, כדי שהאפליקציה תדע לא להדפיס שעון
            game["timeTbd"] = True
        if tv:
            game["broadcast"] = tv
        out.append(game)
    return out


def season_start_year(today=None):
    """עונה נפתחת בקיץ, אז עד יולי אנחנו עדיין בעונה שנפתחה בשנה שעברה."""
    today = today or datetime.date.today()
    return today.year if today.month >= SEASON_SPLIT else today.year - 1


def fetch_games(fetch, log=None, today=None):
    html = fetch(GAMES_URL)
    games = parse_games(html, season_start_year(today), log=log)
    if log:
        log(f"  לוח המועדון: {len(games)} משחקים מתוך {GAMES_URL}")
    return games
