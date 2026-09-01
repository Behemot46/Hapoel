"""לחסום כותרת מהמדור, בלי לכתוב קוד.

הסינון האוטומטי קורא כותרת בלבד, ויש סיפורים ששום כלל לא יסווג נכון:
הפועל ירושלים היא גם מועדון כדורגל, וכתבה על ״המאבק״ או על החלטה של
בעל תפקיד לא נושאת שום סימן לענף. עד היום כל כותרת כזאת חייבה שינוי
קוד, וזה אומר שהיא נשארת על המסך של האוהד עד שמישהו מגיע.

הסקריפט הזה מקבל ביטוי, מוסיף אותו ל־blockPhrases ב־news-sources.json,
ומיד מנקה את הקובץ החי מכל כותרת שנופלת בגללו. הוא מודפס לפני ואחרי כדי
שיהיה ברור מה בדיוק ירד, ואם ביטוי מפיל כותרות כדורסל אמיתיות רואים את
זה מיד ומבטלים.

    python scripts/block_headline.py "פוקסמן" "בסמטה"

ההרצה הרגילה היא דרך .github/workflows/block-headline.yml, כלומר מהטלפון.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import news_feed

DATA = pathlib.Path(__file__).resolve().parent.parent / "app" / "data"


def main(argv):
    phrases = [p.strip() for p in argv if p.strip()]
    if not phrases:
        print("צריך ביטוי אחד לפחות. דוגמה: python scripts/block_headline.py \"פוקסמן\"")
        return 1

    src_path = DATA / "news-sources.json"
    src = json.loads(src_path.read_text(encoding="utf-8"))
    have = list(src.get("blockPhrases") or [])
    added = [p for p in phrases if p not in have]
    if not added:
        print("כל הביטויים כבר ברשימה, אין מה להוסיף.")
    else:
        src["blockPhrases"] = have + added
        src_path.write_text(json.dumps(src, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print("נוספו לרשימת החסימה:", ", ".join(added))

    # הקובץ החי מנוקה עכשיו ולא מחכה לאיסוף הבא
    news_feed._phrases_cache = None
    news_path = DATA / "news.json"
    news = json.loads(news_path.read_text(encoding="utf-8"))
    items = news.get("items") or []
    keep = [i for i in items if news_feed.about_us(i["title"])]
    dropped = [i for i in items if not news_feed.about_us(i["title"])]

    print(f"\nבמדור היו {len(items)} כותרות, נשארות {len(keep)}.")
    if dropped:
        print("ירדו:")
        for i in dropped:
            print("   -", i["title"])
    else:
        print("שום כותרת לא ירדה. אם ציפית שכן, כנראה הביטוי לא מופיע בכותרת עצמה.")

    if len(keep) != len(items):
        news["items"] = keep
        news_path.write_text(json.dumps(news, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
