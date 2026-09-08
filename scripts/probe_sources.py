"""בדיקת מקורות: עמוד המשחק עצמו, שבו כל מספר יושב ליד שם הקבוצה שלו.

בטבלת הקבוצה יש רק תא ״110-77״, ואי אפשר לדעת ממנו לבד אם הסדר הוא
מארחת־אורחת, אורחת־מארחת או מנצחת קודם. בעמוד המשחק המספרים כתובים ליד
השמות, וזה מקור ישיר במקום הסקה.

הסבב הזה מוצא את הקישור מהשורה של המשחק שלנו, פותח אותו, ומדפיס את
מה שכתוב שם: כותרת, שמות, מספרים, וגם את הטבלאות הראשונות.
"""
import re
import sys
import pathlib

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u


def log(*a):
    print("[probe]", *a, flush=True)


link = u.find_team_link()
soup = BeautifulSoup(u.fetch(link), "html.parser")

target = None
for tr in soup.find_all("tr"):
    cells = [c.get_text(strip=True) for c in tr.find_all("td")]
    if any("08/09/2026" in c for c in cells) and any(re.search(r"\d{2,3}-\d{2,3}", c) for c in cells):
        target = tr
        break

if target is None:
    log("לא נמצאה שורה של 08/09")
    raise SystemExit

log("תאי השורה:", [c.get_text(strip=True) for c in target.find_all("td")])
hrefs = [requests.compat.urljoin(link, a["href"]) for a in target.find_all("a", href=True)]
log("קישורים בשורה:", hrefs)

for href in hrefs:
    if "team.asp" in href:
        continue
    log("=== פותח:", href)
    page = BeautifulSoup(u.fetch(href), "html.parser")
    title = page.find("title")
    log("title:", (title.get_text(strip=True) if title else "אין")[:120])
    text = re.sub(r"\s+", " ", page.get_text(" ", strip=True))
    log("600 התווים הראשונים:", text[:600])
    for i, tbl in enumerate(page.find_all("table")[:3]):
        rows = tbl.find_all("tr")[:4]
        log(f"טבלה {i}:")
        for r in rows:
            log("   ", [c.get_text(strip=True)[:22] for c in r.find_all(["td", "th"])][:8])
    break
