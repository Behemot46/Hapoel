"""Diagnostic probe: two shows to add, and one Spotify link to identify.

The ask is to add ״דאבל דריבל״ and ״אנחנו במפה״, with a single Spotify show
link that can only belong to one of them. So this answers three questions,
in order, and writes nothing:

  1. which show is behind that Spotify id. Spotify's oEmbed endpoint is
     public and keyless, so the title can be read without an API key.
  2. whether either show is in Apple's store. If it is, it gets an appleId
     like the others and the collector follows it across hosts by itself.
  3. if it is there, what its feedUrl and its newest episodes look like, so
     the entry can be verified before it reaches fans rather than after.
"""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
SEARCH = "https://itunes.apple.com/search"
SPOTIFY_SHOW = "https://open.spotify.com/show/0345nCU3sMSN0lpBVs6osA"

TERMS = ["דאבל דריבל", "אנחנו במפה", "דאבל דריבל כדורסל", "אנחנו במפה כדורסל"]


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 74)
log("A. who is behind the Spotify link")
log("=" * 74)
log(f"  {SPOTIFY_SHOW}")
try:
    r = requests.get("https://open.spotify.com/oembed",
                     params={"url": SPOTIFY_SHOW}, headers=UA, timeout=30)
    log(f"  oembed HTTP {r.status_code}")
    if r.ok:
        d = json.loads(r.text)
        for k in ("title", "provider_name", "thumbnail_url"):
            log(f"    {k}: {str(d.get(k))[:120]}")
except Exception as e:
    log(f"  oembed failed: {e}")

# the page itself carries og: tags server side, which name the show too
try:
    r = requests.get(SPOTIFY_SHOW, headers=UA, timeout=30)
    log(f"  page HTTP {r.status_code}, {len(r.content)} bytes")
    import re
    for prop in ("og:title", "og:description", "og:type"):
        m = re.search(r'<meta[^>]+property="' + prop + r'"[^>]+content="([^"]*)"',
                      r.text)
        log(f"    {prop}: {(m.group(1) if m else '(not found)')[:160]}")
except Exception as e:
    log(f"  page fetch failed: {e}")
log("")

log("=" * 74)
log("B. are they in Apple's store")
log("=" * 74)
hits = {}
for term in TERMS:
    for country in ("IL", None):
        p = {"term": term, "media": "podcast", "limit": 10}
        if country:
            p["country"] = country
        try:
            r = requests.get(SEARCH, params=p, headers=UA, timeout=30)
            r.raise_for_status()
            res = json.loads(r.text).get("results") or []
        except Exception as e:
            log(f'  term="{term}" country={country or "(none)"}: ERROR {e}')
            continue
        log(f'  term="{term}" country={country or "(none)"}  ->  {len(res)} results')
        for i, x in enumerate(res[:6], 1):
            name = (x.get("collectionName") or "").strip()
            feed = (x.get("feedUrl") or "").strip()
            log(f"    {i}. {name[:80]}")
            log(f"       artist : {(x.get('artistName') or '')[:60]}")
            log(f"       id     : {x.get('collectionId')}   episodes: {x.get('trackCount')}")
            log(f"       feedUrl: {feed[:105] or '(NONE)'}")
            log(f"       genres : {', '.join(x.get('genres') or [])[:70]}")
            if feed and name:
                hits[name] = (x.get("collectionId"), feed)
        log("")

log("=" * 74)
log("C. feeds that turned up, newest episodes")
log("=" * 74)
if not hits:
    log("  none.")
for name, (cid, feed) in hits.items():
    log(f"  {name}  (id {cid})")
    log(f"  {feed}")
    try:
        x = requests.get(feed, headers=UA, timeout=30)
        x.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(x.content)
        items = root.findall(".//item")
        chan_title = root.findtext(".//channel/title") or "(no title)"
        log(f"    channel title: {chan_title[:90]}")
        log(f"    parsed ok, {len(items)} items. newest three:")
        for it in items[:3]:
            log(f"      - {(it.findtext('title') or '')[:85]}")
            log(f"        pubDate: {(it.findtext('pubDate') or '')[:40]}")
            log(f"        link   : {(it.findtext('link') or '(none)')[:95]}")
    except Exception as e:
        log(f"    feed fetch/parse FAILED: {e}")
    log("")

log("done. nothing was written.")
