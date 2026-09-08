"""בדיקת מקורות: איך תא התוצאה באתר הליגה כתוב באמת.

הלוח שלנו אומר שמכבי אשדוד קלעה 110 ואנחנו 77. שלוש כותרות עצמאיות
אומרות בדיוק ההפך: ״הפועל ירושלים פתחה את העונה עם ניצחון 77:110 על
מכבי אשדוד״ (הארץ), ״פירקה 77:110 את מכבי אשדוד״ (וואלה), ״הביסה את
אשדוד״ (ספורט 5). כלומר אנחנו קלענו 110.

מה שצריך לראות כאן הוא התא עצמו: מה בדיוק כתוב בעמודת התוצאה, באיזה
סדר, ואילו תווי כיווניות מוסתרים יש בו. מזה נגזר איזה מספר שייך למארחת
ואיזה לאורחת, במקום להמשיך לנחש.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import update_data as u


def log(*a):
    print("[probe]", *a, flush=True)


from bs4 import BeautifulSoup
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
    log("כותרות הטבלה:", hdr)
    for r in rows[hdr_idx + 1:]:
        cells = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cells) < 3:
            continue
        joined = " | ".join(cells)
        if not re.search(r"\d{2,3}\s*[:\-]\s*\d{2,3}", joined):
            continue
        log("שורה עם תוצאה:")
        for j, c in enumerate(cells):
            name = hdr[j] if j < len(hdr) else f"עמודה {j}"
            # repr כדי לראות תווי כיווניות מוסתרים, שהם בדיוק מה שיכול
            # להפוך את הסדר על המסך בלי לשנות את הטקסט
            log(f"   [{j}] {name}: {c!r}")
        break
    break
