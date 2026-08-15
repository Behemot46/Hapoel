"""Diagnostic probe — where can headlines about the club be read from?

The app is about to grow a news feed. Before writing a parser, find out which
Israeli sports sites actually publish a machine-readable feed, what each one
calls its fields, and — the part that decides everything — how many of the
items in a general basketball feed are about Hapoel Jerusalem at all.

Two traps this probe is meant to expose:
  1. "הפועל ירושלים" is also a football club. A naive keyword filter will
     put transfer news about a different team on a basketball app's home
     screen. Every match printed here shows its title, so the noise is
     visible rather than assumed.
  2. Several of these sites answer 200 with an HTML error page instead of
     404. Content-Type and the first bytes are printed for that reason.

Nothing here is committed. It prints, and the parser is written from the log.
"""
import re
import sys
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/rss+xml, application/xml, text/xml, application/json, */*"}

# the club, in the spellings the press actually uses
US = ("הפועל ירושלים", "הפועל י-ם", "הפועל י־ם", 'הפועל י"ם', "הפועל י״ם",
      "הפועל בנק יהב", "הפועל מידטאון", "ירושלים")
# words that mean the item is about the footballing namesake, or another sport
NOT_US = ("כדורגל", "ליגת העל בכדורגל", "בית\"ר", "ביתר ירושלים", "גביע הטוטו",
          "הפועל ירושלים בכדורגל")
BASKET = ("כדורסל", "ליגת ווינר", "יורוקאפ", "יורוליג", "פאיס ארנה", "סל")

CANDIDATES = [
    # --- aggregators: one query, every outlet, attribution included ---
    ("google-news כדורסל", "https://news.google.com/rss/search?"
     "q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D%22+"
     "%D7%9B%D7%93%D7%95%D7%A8%D7%A1%D7%9C&hl=iw&gl=IL&ceid=IL:iw"),
    ("google-news שם בלבד", "https://news.google.com/rss/search?"
     "q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D%22"
     "&hl=iw&gl=IL&ceid=IL:iw"),
    ("google-news when:7d", "https://news.google.com/rss/search?"
     "q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D%22+"
     "%D7%9B%D7%93%D7%95%D7%A8%D7%A1%D7%9C+when:7d&hl=iw&gl=IL&ceid=IL:iw"),

    # --- the club itself ---
    ("hapoel.co.il /feed", "https://hapoel.co.il/feed/"),
    ("hapoel.co.il wp-json", "https://hapoel.co.il/wp-json/wp/v2/posts?per_page=10"),
    ("hapoel.co.il /news", "https://hapoel.co.il/news/"),

    # --- the league ---
    ("basket.co.il news", "https://basket.co.il/news.asp"),
    ("basket.co.il rss", "https://basket.co.il/rss.asp"),

    # --- the sports press ---
    ("sport5 rss index", "https://www.sport5.co.il/rss.aspx"),
    ("sport5 basketball", "https://www.sport5.co.il/rss.aspx?FolderID=5"),
    ("ONE basketball", "https://www.one.co.il/cat/coop/xml/rss/rss.aspx?cat=6"),
    ("ONE index", "https://www.one.co.il/cat/coop/xml/rss/"),
    ("walla sport", "https://rss.walla.co.il/feed/32"),
    ("walla basketball", "https://rss.walla.co.il/feed/34"),
    ("ynet sport", "https://www.ynet.co.il/Integration/StoryRss3.xml"),
    ("sport1", "https://www.sport1.co.il/feed/"),
    ("sport1 maariv", "https://sport1.maariv.co.il/feed/"),
    ("mako sport", "https://rcs.mako.co.il/rss/sport-israelbasketball.xml"),
    ("israelhayom sport", "https://www.israelhayom.co.il/rss/sport.xml"),
    ("calcalist sport", "https://www.calcalist.co.il/GeneralRSS/0,16335,L-3856,00.xml"),
]


def log(*a):
    print("[probe]", *a, flush=True)


def strip_tags(s):
    return re.sub(r"<[^>]+>", " ", s or "").replace("&nbsp;", " ").strip()


def classify(title):
    """Is this item plausibly about our basketball club?"""
    t = strip_tags(title)
    hit = any(w in t for w in US)
    if not hit:
        return "  -"
    if any(w in t for w in NOT_US):
        return " ✗football"
    if any(w in t for w in BASKET):
        return " ✓basket"
    return " ?maybe"


def show_feed(body, label):
    """Print the shape of an RSS/Atom document and a sample of its items."""
    try:
        root = ET.fromstring(body.encode("utf-8") if isinstance(body, str) else body)
    except Exception as e:
        log(f"    not XML: {type(e).__name__} {str(e)[:70]}")
        return 0
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)
    log(f"    root <{root.tag.split('}')[-1]}>  items: {len(items)}")
    if not items:
        return 0
    first = items[0]
    log("    fields on item 1: " + ", ".join(
        sorted({c.tag.split('}')[-1] for c in first})))
    matched = 0
    for it in items:
        title = (it.findtext("title") or it.findtext("atom:title", "", ns) or "")
        mark = classify(title)
        if mark != "  -":
            matched += 1
    log(f"    items whose title names us: {matched}/{len(items)}")
    for it in items[:8]:
        title = strip_tags(it.findtext("title") or it.findtext("atom:title", "", ns) or "")
        link = it.findtext("link") or ""
        if not link:
            a = it.find("atom:link", ns)
            link = a.get("href") if a is not None else ""
        date = (it.findtext("pubDate") or it.findtext("atom:updated", "", ns)
                or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
        src = it.findtext("source") or ""
        log(f"    {classify(title)}  {date[:31]:<31} {title[:74]}")
        log(f"           link: {link[:110]}")
        if src:
            log(f"           source: {src[:60]}")
    return len(items)


def probe(label, url):
    log("")
    log("-" * 78)
    log(f"{label}  →  {url[:100]}")
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        log(f"    FAIL {type(e).__name__} {str(e)[:90]}")
        return
    ct = r.headers.get("Content-Type", "?")
    log(f"    {r.status_code}  {ct[:40]}  {len(r.content)}b")
    if r.status_code != 200:
        return
    r.encoding = r.apparent_encoding or "utf-8"
    body = r.text
    head = body[:160].replace("\n", " ")
    log(f"    starts: {head}")
    if "json" in ct or body.lstrip().startswith(("[", "{")):
        try:
            import json
            d = json.loads(body)
            if isinstance(d, list) and d:
                log(f"    JSON list, {len(d)} entries; keys: "
                    + ", ".join(sorted(d[0])[:22]))
                for e in d[:5]:
                    t = strip_tags((e.get("title") or {}).get("rendered")
                                   if isinstance(e.get("title"), dict) else e.get("title"))
                    log(f"    {classify(t)}  {str(e.get('date'))[:19]}  {str(t)[:70]}")
                    log(f"           link: {str(e.get('link'))[:100]}")
            else:
                log(f"    JSON {type(d).__name__}: {str(d)[:200]}")
        except Exception as e:
            log(f"    not JSON: {type(e).__name__} {str(e)[:70]}")
        return
    if "<rss" in body[:400].lower() or "<feed" in body[:400].lower() or "<?xml" in body[:80]:
        show_feed(body, label)
        return
    # an HTML page — is a feed advertised in its head?
    for m in re.findall(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*>', body, re.I)[:6]:
        log(f"    advertises feed: {m[:130]}")
    heads = re.findall(r'<h[23][^>]*>(.{5,120}?)</h[23]>', body, re.S)
    if heads:
        log(f"    HTML page, {len(heads)} h2/h3 headings; first few:")
        for h in heads[:6]:
            t = strip_tags(h)
            log(f"    {classify(t)}  {t[:80]}")


only = sys.argv[1] if len(sys.argv) > 1 else "all"
log("=" * 78)
log("NEWS SOURCES — what publishes headlines about the club, and in what shape")
log("=" * 78)
for label, url in CANDIDATES:
    if only not in ("all", "probe") and only not in label:
        continue
    probe(label, url)
log("")
log("=" * 78)
log("done")
