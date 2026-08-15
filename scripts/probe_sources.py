"""Diagnostic probe, did the feedback function actually deploy?

vercel.json sets `outputDirectory: app`, and the function lives in `api/` at
the root of the repository, outside it. Vercel is documented to pick up a
root-level `api/` directory anyway, but "documented" and "deployed" are not
the same sentence, and the difference is only visible from outside:

    404  → the function was never built; the app would fall back forever
    501  → the function is live and says it has no token yet   ← expected now
    400  → the function is live AND configured                 ← after setup

The probe deliberately sends an *empty* body: with a token configured that
answers 400 without creating anything, so running this never files a real
card. Nothing here writes to the repository.
"""
import json
import urllib.error
import urllib.request

# the apex redirects to www with a 308, and a POST that is not followed
# looks like a failure that is not one, so ask both, as the app would
SITES = ["https://hapoel.site", "https://www.hapoel.site"]
UA = {"User-Agent": "Mozilla/5.0 (probe)", "Content-Type": "application/json"}


def log(*a):
    print("[probe]", *a, flush=True)


def call(site, method, body=None):
    req = urllib.request.Request(
        site + "/api/feedback", method=method, headers=UA,
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


log("=" * 74)
log("the feedback endpoint, from outside")
log("=" * 74)

for site in SITES:
    log("")
    log(f"  {site}")
    status, body = call(site, "POST", {})
    log(f"    POST empty body → {status}  {body}")
    if status == 404:
        log("       !! the function did not deploy, vercel is not building api/")
    elif status == 501:
        log("       ok, deployed, waiting for FEEDBACK_TOKEN")
    elif status == 400:
        log("       ok, deployed AND configured: it refused an empty answer")
    elif status == 200:
        log("       !! it accepted an empty answer, which it should not")
    elif status == 308:
        log("       redirect, a browser would follow it and keep the POST")

    status, body = call(site, "GET")
    log(f"    GET             → {status}  {body}")
    log("       " + ("ok, only POST is allowed" if status == 405 else "unexpected"))

log("")
log("=" * 74)
log("done, nothing was written")
