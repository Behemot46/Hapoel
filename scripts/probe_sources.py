"""בדיקת מקורות: מה הסדר בתא התוצאה, כשהמארחת היא זו שניצחה.

בתא של המשחק שלנו כתוב ״110-77״, המארחת היא מכבי אשדוד, האורחת היא
הפועל י-ם, והעיתונות אומרת שאנחנו ניצחנו 110. מדגם אחד לא מבחין בין שתי
השערות: ״האורחת ראשונה״ ו״המנצחת ראשונה״. שתיהן מסבירות אותו תא.

לכן צריך משחק שבו המארחת ניצחה. הסבב הזה עובר על עמודי הקבוצות האחרות
בליגה, מוצא משחקים גמורים שאנחנו לא בהם, ולכל אחד שואל את פיד החדשות מה
הייתה התוצאה. הצלבה בין השניים מכריעה.
"""
import re
import sys
import pathlib
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u

FEED = "https://news.google.com/rss/search?q={q}&hl=iw&gl=IL&ceid=IL:iw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def log(*a):
    print("[probe]", *a, flush=True)


# כל הקבוצות בליגה, מתוך עמוד הטבלה
table = BeautifulSoup(u.fetch("https://basket.co.il/table.asp?cYear=2027"), "html.parser")
links = []
for a in table.find_all("a", href=True):
    if "team.asp" in a["href"]:
        href = requests.compat.urljoin("https://basket.co.il/", a["href"])
        if href not in [l for l, _ in links]:
            links.append((href, a.get_text(strip=True)))
log(f"{len(links)} עמודי קבוצות")

found = 0
for href, name in links:
    if found >= 4:
        break
    try:
        soup = BeautifulSoup(u.fetch(href), "html.parser")
    except Exception as e:
        continue
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        hdr = None
        for r in rows[:3]:
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if any("תאריך" in c for c in cells) and any("מארחת" in c for c in cells):
                hdr = cells
                break
        if not hdr:
            continue
        j = {n: hdr.index(next(c for c in hdr if n in c)) for n in ("מארחת", "אורחת", "תוצאה")}
        for r in rows[1:]:
            cells = [c.get_text(strip=True) for c in r.find_all("td")]
            if len(cells) <= max(j.values()):
                continue
            host, guest, score = cells[j["מארחת"]], cells[j["אורחת"]], cells[j["תוצאה"]]
            if not re.search(r"\d{2,3}\s*[-:]\s*\d{2,3}", score):
                continue
            if u.is_us(host) or u.is_us(guest):
                continue
            log(f"משחק: מארחת {host!r} | אורחת {guest!r} | תא התוצאה {score!r}")
            q = urllib.parse.quote(f"{host} {guest} גביע ווינר")
            try:
                root = ET.fromstring(requests.get(FEED.format(q=q), headers=UA, timeout=30).content)
                for it in root.findall(".//item")[:3]:
                    log("   כותרת:", (it.findtext("title") or "")[:110])
            except Exception as e:
                log("   פיד נפל:", e)
            found += 1
            break
        break
