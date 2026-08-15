"""Diagnostic probe — round 12: last attempt at photos for Roddy and Lofton.

Round 11 established two things:
  * the Proballers player page is rendered client-side — its HTML carries one
    image, the site's generic Open Graph card, and no player photo at all;
  * in the EuroCup squad feed Roddy and Lofton come back with code=None, which
    is precisely why the updater never found a headshot for them. Everyone
    with a code already has one.

So try, in order of how much we would trust the result:
  A. the Proballers image without the expired resize cache, and a couple of
     other cache sizes — same file, different derivative;
  B. the EuroLeague person directory under other competitions, in case the two
     of them hold a person code we are not looking under.
"""
import io

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,image/*;q=0.9,*/*;q=0.8",
      "Referer": "https://www.proballers.com/basketball/player/190935/roddy-david"}

FILE = "ul/player/david-roddy-1f0fe381-d437-6f74-ad19-414dbecff047.png"
BASE = "https://www.proballers.com/"
CANDIDATES = [
    BASE + FILE,
    BASE + "media/cache/resize_600_png/https---www.proballers.com/" + FILE,
    BASE + "media/cache/resize_200_png/https---www.proballers.com/" + FILE,
    BASE + "media/cache/player_profile/https---www.proballers.com/" + FILE,
    BASE + "media/" + FILE,
]


def log(*a):
    print("[probe]", *a, flush=True)


def try_image(url, label):
    try:
        r = requests.get(url, headers=UA, timeout=30, stream=True)
        ctype = r.headers.get("Content-Type", "?")
        data = r.raw.read(900000)
        log(f"  {label}: {r.status_code} {ctype} {len(data)} bytes")
        if r.status_code == 200 and ctype.startswith("image/"):
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            log(f"    -> {im.size} {im.mode}  USABLE")
            return True
    except Exception as e:
        log(f"  {label}: FAIL {type(e).__name__} {str(e)[:110]}")
    return False


log("=" * 70)
log("A. the Proballers file without the expired resize cache")
log("=" * 70)
for u in CANDIDATES:
    try_image(u, u.replace(BASE, "")[:70])

log("")
log("=" * 70)
log("B. does either of them hold a person code in another competition?")
log("=" * 70)
for comp, season in (("E", "E2026"), ("U", "U2025"), ("E", "E2025")):
    url = (f"https://api-live.euroleague.net/v2/competitions/{comp}/seasons/"
           f"{season}/people?personName=Roddy")
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        log(f"  {comp}/{season}: {r.status_code} {r.text[:220]}")
    except Exception as e:
        log(f"  {comp}/{season}: FAIL {type(e).__name__} {str(e)[:110]}")

for name in ("Roddy", "Lofton"):
    url = f"https://api-live.euroleague.net/v2/people?name={name}"
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        log(f"  /v2/people?name={name}: {r.status_code} {r.text[:300]}")
    except Exception as e:
        log(f"  /v2/people?name={name}: FAIL {type(e).__name__} {str(e)[:110]}")
