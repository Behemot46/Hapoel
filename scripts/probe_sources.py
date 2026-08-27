"""Diagnostic probe: why the news section goes quiet for days.

Two facts from the repo history frame the question. First, no version of
news.json ever held an item older than 60 days, so ״ידיעות מלפני שנים״
cannot come from the collected data; the age cutoff is enforced at 45 days.
Second, the newest headline sat frozen on 18.8 for five days straight,
21.8 through 23.8, which is exactly ״חסר חדשות עדכניות״.

The collector asks Google News two questions, both demanding the exact
quoted club name next to the word כדורסל. The club now brands itself
Hapoel Midtown Jerusalem, so a headline using the sponsored name, or the
short form, or no כדורסל at all, is invisible to us.

So this measures candidate queries against the live feed and reports, for
each: how many items come back, how many survive the club-in-headline
filter and the 45 day cutoff, and crucially how many are NOT already in
our file. A query that only re-finds what we have is not worth adding.
"""
import datetime
import json
import pathlib
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
RSS = "https://news.google.com/rss/search"

CANDIDATES = [
    '"הפועל ירושלים" כדורסל',        # קיים
    '"הפועל י-ם" כדורסל',            # קיים
    '"הפועל מידטאון ירושלים"',
    '"מידטאון ירושלים"',
    '"הפועל ירושלים" סל',
    'הפועל ירושלים כדורסל יורוקאפ',
    '"הפועל ירושלים"',
]

FOOTBALL = re.compile(r"כדורגל|ליגת העל|בית\"ר|ביתר|שער|גול\b")
CLUB = re.compile(r"הפועל\s*(ירושלים|י-ם|י״ם|מידטאון)")


def log(*a):
    print("[probe]", *a, flush=True)


have = set()
try:
    n = json.loads(pathlib.Path("app/data/news.json").read_text(encoding="utf-8"))
    have = {re.sub(r"\W+", "", i["title"]) for i in n["items"]}
    log(f"already in our file: {len(have)} headlines, newest {n['items'][0]['published'][:10]}")
except Exception as e:
    log("could not read our file:", e)

cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)
log(f"cutoff: {cutoff:%Y-%m-%d}")
log("")

for q in CANDIDATES:
    url = f"{RSS}?q={urllib.parse.quote(q)}&hl=iw&gl=IL&ceid=IL:iw"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        log(f'  {q!r}: ERROR {e}')
        continue
    items = root.findall(".//item")
    kept, fresh_new, samples = 0, [], []
    for it in items:
        title = (it.findtext("title") or "").strip()
        raw = (it.findtext("pubDate") or "").strip()
        try:
            import email.utils
            when = email.utils.parsedate_to_datetime(raw)
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            continue
        if when < cutoff:
            continue
        if not CLUB.search(title) or FOOTBALL.search(title):
            continue
        kept += 1
        key = re.sub(r"\W+", "", title)
        if key not in have:
            fresh_new.append((when, title))
    fresh_new.sort(reverse=True)
    log(f'  {q}')
    log(f'    raw {len(items):>3} | on-topic and fresh {kept:>3} | NOT already ours {len(fresh_new):>3}')
    for when, t in fresh_new[:4]:
        log(f'      + {when:%Y-%m-%d}  {t[:74]}')
    log("")

log("done. nothing was written.")
