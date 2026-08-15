"""Diagnostic probe, round 2 — can a headline link reach the publisher?

Round 1 settled the source: every Israeli sports site's own RSS is dead
(404/403/500) except ynet's general sport feed, which carries no basketball
about us. Google News answers with 100 items, each carrying <source>, so it
is the feed. One thing decides the data model:

    <link> is https://news.google.com/rss/articles/CBMi... — an opaque id,
    not the article. Does following it land on the publisher, and can the
    real address be stored at collection time instead of sending every fan
    through Google?

Also re-checks the two sites whose feed might exist under another path, and
prints the fields of a full item verbatim, because round 1 only summarised.
"""
import re
import sys
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"}

FEED = ("https://news.google.com/rss/search?"
        "q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D%22+"
        "%D7%9B%D7%93%D7%95%D7%A8%D7%A1%D7%9C&hl=iw&gl=IL&ceid=IL:iw")


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 78)
log("A. one item, every field, verbatim")
log("=" * 78)
r = requests.get(FEED, headers=UA, timeout=30)
r.encoding = "utf-8"
root = ET.fromstring(r.text.encode("utf-8"))
items = root.findall(".//item")
log(f"items: {len(items)}")
ch = root.find("channel")
log(f"channel title: {ch.findtext('title')}")
log(f"channel lastBuildDate: {ch.findtext('lastBuildDate')}")
for it in items[:2]:
    log("-" * 70)
    for c in it:
        tag = c.tag.split("}")[-1]
        val = (c.text or "").strip().replace("\n", " ")
        attrs = dict(c.attrib)
        log(f"  <{tag}> attrs={attrs}")
        log(f"      {val[:300]}")

log("")
log("=" * 78)
log("B. following the link — where does it actually land?")
log("=" * 78)
for it in items[:5]:
    link = it.findtext("link")
    title = (it.findtext("title") or "")[:58]
    log("-" * 70)
    log(f"  {title}")
    try:
        rr = requests.get(link, headers=UA, timeout=25, allow_redirects=True)
        log(f"  {rr.status_code}  hops={len(rr.history)}  {rr.headers.get('Content-Type','?')[:32]}")
        log(f"  final: {rr.url[:150]}")
        if "news.google" in rr.url:
            body = rr.text
            # google's new format hands back a page that redirects with JS
            for pat in (r'data-n-au="([^"]+)"', r'<c-wiz[^>]*data-p="([^"]{0,120})',
                        r'url=(https?://[^"\'&]+)', r'href="(https?://(?!\w*\.?google)[^"]+)"'):
                m = re.findall(pat, body)
                if m:
                    log(f"  in-page {pat[:22]}… → {str(m[:3])[:220]}")
                    break
            else:
                log(f"  no publisher url in body ({len(body)}b); starts: "
                    f"{body[:150].replace(chr(10), ' ')}")
    except Exception as e:
        log(f"  FAIL {type(e).__name__} {str(e)[:90]}")

log("")
log("=" * 78)
log("C. the batch endpoint Google News uses to resolve those ids")
log("=" * 78)
first = items[0].findtext("link").rsplit("/", 1)[-1].split("?")[0]
log(f"  id: {first[:60]}…")
try:
    rr = requests.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data={"f.req": '[[["Fbv4je","[\\"garturlreq\\",[[\\"X\\",\\"X\\",[\\"X\\",\\"X\\"],'
                       'null,null,1,1,\\"IL:iw\\",null,1,null,null,null,null,null,0,1],'
                       '\\"X\\",\\"IL\\",1,[2,3,4],1,1,null,0,0,null,0],\\"' + first +
                       '\\",0,0]",null,"generic"]]]'},
        timeout=25)
    log(f"  {rr.status_code}  {len(rr.content)}b")
    m = re.findall(r'https?://(?!\w*\.?google)[^\\"]{12,140}', rr.text)
    log(f"  urls found: {str(m[:4])[:400]}")
except Exception as e:
    log(f"  FAIL {type(e).__name__} {str(e)[:90]}")

log("")
log("=" * 78)
log("D. the two sites that might still have a feed under another path")
log("=" * 78)
for u in ("https://sport1.maariv.co.il/?feed=rss2",
          "https://sport1.maariv.co.il/category/basketball/feed/",
          "https://www.sport5.co.il/rss/rss.aspx",
          "https://www.sport5.co.il/RSS/BasketBall.xml",
          "https://www.one.co.il/rss/basketball.xml",
          "https://www.ynet.co.il/Integration/StoryRss1854.xml",
          "https://www.jpost.com/rss/rssfeedsisraelsports.aspx"):
    try:
        rr = requests.get(u, headers=UA, timeout=20)
        ct = rr.headers.get("Content-Type", "?")[:34]
        body = rr.text[:120].replace("\n", " ")
        n = 0
        if rr.status_code == 200 and ("xml" in ct or body.lstrip().startswith("<?xml")):
            try:
                n = len(ET.fromstring(rr.text.encode("utf-8")).findall(".//item"))
            except Exception:
                n = -1
        log(f"  {rr.status_code}  items={n:>3}  {ct:<34} {u}")
    except Exception as e:
        log(f"  FAIL {type(e).__name__:<18} {u}  {str(e)[:50]}")

log("")
log("=" * 78)
log("done")
