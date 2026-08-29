"""בדיקת מקורות: האם אתר הליגה באמת לא מפרסם שעות, או שאנחנו לא קוראים
אותן.

כל 26 משחקי הליגה אצלנו יושבים על 20:00 בדיוק, וזו בדיוק ברירת המחדל
בפרסר. שתי אפשרויות שדורשות תיקון הפוך: או שהעמוד באמת ריק בעמודת
״שעה״, ואז אסור להמציא שעה, או שהעמוד מפרסם שעה ואנחנו לא מצליחים
לקרוא אותה, ואז צריך לתקן את הקריאה. לכן מודפס כאן התא הגולמי כמו שהוא.
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
log("עמוד הקבוצה:", link)
soup = BeautifulSoup(u.fetch(link), "html.parser")

for table in soup.find_all("table"):
    rows = table.find_all("tr")
    hdr_idx = hdr = None
    for i, r in enumerate(rows[:3]):
        cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
        if any("תאריך" in c for c in cells) and any("מארחת" in c for c in cells):
            hdr_idx, hdr = i, cells
            break
    if hdr_idx is None:
        continue
    log("כותרת הטבלה:", hdr)
    j_time = next((j for j, c in enumerate(hdr) if "שעה" in c), None)
    log("אינדקס עמודת שעה:", j_time)
    shown = 0
    empty = filled = 0
    for r in rows[hdr_idx + 1:]:
        cells = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cells) < 3:
            continue
        raw = cells[j_time] if j_time is not None and j_time < len(cells) else "<אין תא>"
        if u.TIME_RE.search(raw or ""):
            filled += 1
        else:
            empty += 1
        if shown < 14:
            shown += 1
            log(f"  שורה: {cells}")
    log(f"סיכום: {filled} שורות עם שעה, {empty} בלי")
    break
