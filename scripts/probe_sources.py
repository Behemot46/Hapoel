"""Diagnostic probe, round two: the shape of one fixture on hapoel.co.il/games.

Round one found the page and that it holds 19 blocks with classes game /
game-type / game-data, and times that match the schedule the club published.
What it could not answer is where the date lives, since no dd/mm token
appeared in the visible text at all.

So this dumps the blocks themselves: the full inner HTML of the first few,
every descendant class, and every attribute, because a date that is not in
the text is usually in an attribute or split across elements.

Hebrew is printed twice, once raw and once JSON escaped, because the runner
log mangled the raw form last time and the escapes survive it.
"""
import json
import re

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "he-IL,he;q=0.9"}
URL = "https://hapoel.co.il/games"


def log(*a):
    print("[probe]", *a, flush=True)


def both(label, s):
    """raw for reading, escaped for certainty."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    log(f"    {label}: {s[:150]}")
    log(f"    {label} (escaped): {json.dumps(s[:150], ensure_ascii=True)}")


r = requests.get(URL, headers=UA, timeout=30)
r.raise_for_status()
r.encoding = r.apparent_encoding or "utf-8"
log(f"{URL} -> HTTP {r.status_code}, {len(r.content)} bytes, encoding={r.encoding}")
soup = BeautifulSoup(r.text, "html.parser")

blocks = soup.select(".game")
log(f"blocks with class 'game': {len(blocks)}")
log("")

for i, g in enumerate(blocks[:4], 1):
    log("=" * 74)
    log(f"BLOCK {i}")
    log("=" * 74)
    both("full text", g.get_text(" ", strip=True))
    log(f"    own attrs: {dict(g.attrs)}")
    log("")
    log("    descendants with a class or a data attribute:")
    for d in g.find_all(True):
        cls = " ".join(d.get("class") or [])
        data = {k: v for k, v in d.attrs.items()
                if k.startswith("data-") or k in ("datetime", "title", "href", "content")}
        txt = re.sub(r"\s+", " ", d.get_text(" ", strip=True))[:70]
        if not cls and not data:
            continue
        log(f"      <{d.name}> class={cls!r} attrs={data}")
        if txt:
            log(f"          text: {txt}")
            log(f"          text (escaped): {json.dumps(txt, ensure_ascii=True)}")
    log("")
    log("    raw html of this block:")
    raw = re.sub(r"\s+", " ", str(g))
    for start in range(0, min(len(raw), 1600), 400):
        log(f"      {raw[start:start + 400]}")
    log("")

# where do the dates live, if anywhere
log("=" * 74)
log("date hunting across the whole page")
log("=" * 74)
text = soup.get_text(" ", strip=True)
for pat, name in (
        (r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", "dd.mm.yyyy"),
        (r"\d{1,2}[./]\d{1,2}", "dd.mm"),
        (r"\d{4}-\d{2}-\d{2}", "iso"),
        (r"\d{1,2}:\d{2}", "time")):
    found = re.findall(pat, text)
    log(f"  {name:<12} in visible text: {len(found)} {found[:12]}")
attrs_with_dates = []
for d in soup.find_all(True):
    for k, v in d.attrs.items():
        if isinstance(v, str) and re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{2,4}", v):
            attrs_with_dates.append((d.name, k, v[:60]))
log(f"  attributes that carry a date: {len(attrs_with_dates)}")
for a in attrs_with_dates[:12]:
    log(f"    {a}")

log("done. nothing was written.")
