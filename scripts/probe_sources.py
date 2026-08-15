"""Diagnostic probe: one answer, all the way through, on the live site.

Everything in the feedback path has been tested in isolation. This is the
join: it sends a single answer to the endpoint the app actually calls, on
the address fans actually use, and prints what comes back. What happens
after that is not this script's job, the drain workflow collects it and the
issue it opens is the proof.

The answer is marked as a test in its own text, so if it does become an
issue there is no mistaking it for a fan's.

    200  the function is live and the answer is parked, id and all
    501  an old deployment is still being served
    502  the function is live but could not reach the parking place
"""
import json
import urllib.error
import urllib.request

SITE = "https://www.hapoel.site"
ANSWER = {
    "fan": "עוקב מרחוק",
    "wants": ["חדשות על הקבוצה", "התראה לפני כל משחק"],
    "rating": "4",
    "idea": "בדיקה אוטומטית של נתיב המשוב, אפשר לסגור את הכרטיס הזה",
    "bug": "",
    "nickname": "",
}


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 74)
log("one answer through the live endpoint")
log("=" * 74)
req = urllib.request.Request(
    SITE + "/api/feedback", method="POST",
    data=json.dumps(ANSWER, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json", "User-Agent": "hapoel-probe"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        status, body = r.status, r.read().decode()
except urllib.error.HTTPError as e:
    status, body = e.code, e.read().decode()[:300]
except Exception as e:
    status, body = None, f"{type(e).__name__}: {e}"

log(f"  POST {SITE}/api/feedback  →  {status}")
log(f"    {body[:300]}")
if status == 200:
    log("    ok, parked. the drain workflow turns it into an issue.")
elif status == 501:
    log("    an older deployment is still being served, wait and retry.")
elif status == 502:
    log("    the function is live but could not park the answer.")

log("")
log("=" * 74)
log("done")
