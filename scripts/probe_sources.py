#!/usr/bin/env python3
"""כלי אבחון ידני. נכתב מחדש בכל פעם לפי השאלה שנשאלת.

**השאלה הפעם, 12.10.2026:** הכותרת של טבלת הליגה היא תלת־שכבתית, וה־probe
הקודם הדפיס אותה. הפרסר תוקן לפיה, וכאן בודקים אותו מול הדף האמיתי:
מה ``find_standings`` מחזיר, והאם ``verify_standings`` מרוצה.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from bs4 import BeautifulSoup

import update_data as ud


def main():
    for url in ud.STANDINGS_URLS:
        try:
            soup = BeautifulSoup(ud.fetch(url), "html.parser")
        except Exception as e:
            print(f"### {url} נפל: {e}")
            continue
        parsed = ud.find_standings(soup)
        print(f"\n########## {url}: {len(parsed or [])} שורות")
        if not parsed:
            continue
        for p in parsed:
            print(f"  {p['team']:<16} {p['played']} מש  "
                  f"{p['wins']}-{p['losses']}  {p['points']} נק")
        try:
            ud.verify_standings(parsed)
            print("  האימות עבר")
        except Exception as e:
            print(f"  ### האימות נפל: {e}")
        return


if __name__ == "__main__":
    main()
