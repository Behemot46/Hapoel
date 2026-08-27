"""Diagnostic probe: why ״מאחורי הסלים״ does not reach the podcast section.

The config asks for it by search phrase, and every collection run so far has
skipped it. Three explanations fit that, and they need different fixes:

  1. the show is not in Apple's store at all, so there is nothing to find
  2. it is there, but its title does not contain the expect string, so our
     own guard rejects a correct match
  3. it is there and the title matches, but Apple returns no feedUrl, which
     is what happens to a show distributed only inside a walled platform

So this prints, verbatim, what the store answers for several spellings, with
every field the resolver actually reads. It also prints the runner up
results, because ״not in the top five״ is a fourth explanation and the
current search asks for only five.

Nothing here is written anywhere. This is a scratch tool, rewritten per
question by design.
"""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; podcast-probe)"}
SEARCH = "https://itunes.apple.com/search"

TERMS = [
    "מאחורי הסלים",
    "מאחורי הסלים פודקאסט",
    "מאחורי הסלים כדורסל",
    "maachorei hasalim",
]


def log(*a):
    print("[probe]", *a, flush=True)


def ask(term, country, limit=15):
    p = {"term": term, "media": "podcast", "limit": limit}
    if country:
        p["country"] = country
    try:
        r = requests.get(SEARCH, params=p, headers=UA, timeout=30)
        r.raise_for_status()
        return json.loads(r.text)
    except Exception as e:
        log(f"  !! {e}")
        return {"results": []}


for term in TERMS:
    for country in ("IL", None):
        tag = f'term="{term}" country={country or "(none)"}'
        data = ask(term, country)
        res = data.get("results") or []
        log("=" * 74)
        log(f"{tag}  ->  {len(res)} results")
        log("=" * 74)
        for i, r in enumerate(res, 1):
            name = (r.get("collectionName") or "").strip()
            feed = (r.get("feedUrl") or "").strip()
            log(f"  {i:>2}. name   : {name[:90]}")
            log(f"      artist : {(r.get('artistName') or '')[:70]}")
            log(f"      id     : {r.get('collectionId')}")
            log(f"      feedUrl: {feed[:110] or '(NONE, this is what would skip it)'}")
            log(f"      view   : {(r.get('collectionViewUrl') or '')[:110]}")
            log(f"      expect ״מאחורי הסלים״ in name? {'YES' if 'מאחורי הסלים' in name else 'no'}")
            log("")
        if not res:
            log("  (nothing)")
        log("")

# If any feed turned up, show that it actually parses and what it carries.
log("=" * 74)
log("feed check: fetching any feedUrl whose title matched")
log("=" * 74)
seen = set()
for term in TERMS:
    for r in (ask(term, "IL").get("results") or []):
        name = (r.get("collectionName") or "").strip()
        feed = (r.get("feedUrl") or "").strip()
        if "מאחורי הסלים" not in name or not feed or feed in seen:
            continue
        seen.add(feed)
        log(f"  {name}")
        log(f"  {feed}")
        try:
            x = requests.get(feed, headers=UA, timeout=30)
            x.raise_for_status()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(x.content)
            items = root.findall(".//item")
            log(f"  parsed ok, {len(items)} items. newest three:")
            for it in items[:3]:
                log(f"    - {(it.findtext('title') or '')[:80]}")
                log(f"      pubDate: {(it.findtext('pubDate') or '')[:40]}")
                log(f"      link   : {(it.findtext('link') or '(none)')[:90]}")
        except Exception as e:
            log(f"  feed fetch/parse FAILED: {e}")
        log("")
if not seen:
    log("  no matching feedUrl found anywhere above.")

log("done. nothing was written.")
