"""Diagnostic probe: the club's honours, printed verbatim.

The first cross-check asked a weak question, whether a year appears anywhere
on the club's Wikipedia page. A year appearing somewhere proves nothing
about the title it is attached to. The counts are the claim worth checking:
the app tells fans the club has eight State Cups and seven Winner Cups, and
a wrong number there is exactly the kind of mistake nobody notices.

So this prints the honours section itself, and the infobox rows, so the
counts can be read rather than inferred. It also prints every line that
names a cup with a year, which is what a timeline entry would be built from.
"""
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; HapoelFanApp/1.0; cross-check)"}
WIKI = ("https://he.wikipedia.org/wiki/"
        "%D7%94%D7%A4%D7%95%D7%A2%D7%9C_%D7%99%D7%A8%D7%95%D7%A9%D7%9C%D7%99%D7%9D_"
        "(%D7%9B%D7%93%D7%95%D7%A8%D7%A1%D7%9C)")


def log(*a):
    print("[check]", *a, flush=True)


r = requests.get(WIKI, headers=UA, timeout=30)
r.raise_for_status()
r.encoding = "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

log("=" * 78)
log("A. the infobox, row by row")
log("=" * 78)
box = soup.find("table", class_=re.compile("infobox|itemsbox"))
if box:
    for tr in box.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        line = " | ".join(c for c in cells if c)
        if line and re.search(r"אליפ|גביע|תואר|הישג", line):
            log(f"  {line[:150]}")
else:
    log("  no infobox found")

log("")
log("=" * 78)
log("B. the honours section")
log("=" * 78)
head = None
for h in soup.find_all(["h2", "h3"]):
    if re.search(r"הישג|תארים|כבוד", h.get_text(" ", strip=True)):
        head = h
        break
if head:
    log(f"  section: {head.get_text(' ', strip=True)}")
    node, printed = head, 0
    while printed < 40:
        node = node.find_next()
        if node is None or node.name in ("h2",) and node is not head:
            break
        if node.name in ("li", "p"):
            t = node.get_text(" ", strip=True)
            if t and re.search(r"אליפ|גביע", t):
                log(f"    {t[:170]}")
                printed += 1
else:
    log("  no honours heading found")

log("")
log("=" * 78)
log("C. every sentence naming a cup and a year")
log("=" * 78)
text = soup.get_text(" ", strip=True)
seen = set()
for m in re.finditer(r"[^.]{0,110}?(גביע[^.]{0,60}?)((?:19|20)\d{2})[^.]{0,40}", text):
    line = re.sub(r"\s+", " ", m.group(0)).strip()
    key = line[:60]
    if key in seen:
        continue
    seen.add(key)
    log(f"  {line[:165]}")
    if len(seen) >= 30:
        break

log("")
log("=" * 78)
log("done. nothing was written.")
