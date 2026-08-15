"""Diagnostic probe: a parking place for an answer, with no key to create.

The function that receives the form cannot write to GitHub, because writing
needs a token and a token can only be minted by a human in a browser. But
GitHub Actions already holds a token of its own, and a workflow can open an
issue with it. The only missing link is somewhere for an answer to wait
between the moment a fan taps send and the moment the next workflow runs.

That parking place has to be writable with no account and readable later by
the runner. ntfy.sh is built for exactly that shape: publish to a topic over
plain HTTP, poll the same topic for what has been published.

Three things decide whether this works, and all three are measured here:

  1. can it be published to with no credentials at all
  2. does polling return what was published, in a parseable form
  3. how long is a message kept, which sets how often the drain must run

Nothing is sent anywhere near a real inbox, and the topic below is a
throwaway used only by this probe.
"""
import json
import time
import urllib.error
import urllib.request

TOPIC = "hapoel-probe-8f3a19c4d7e2"
BASE = "https://ntfy.sh/" + TOPIC
UA = {"User-Agent": "hapoel-fan-app-probe"}


def log(*a):
    print("[probe]", *a, flush=True)


def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})},
                               method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as res:
            return res.status, res.read().decode("utf-8", "replace"), dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300], dict(e.headers)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", {}


log("=" * 74)
log("1. publish, with no account and no key")
log("=" * 74)
payload = json.dumps({"fan": "מנוי לעונה", "rating": "5",
                      "idea": "בדיקה אוטומטית, לא תשובה אמיתית"}, ensure_ascii=False)
status, body, headers = req(BASE, data=payload.encode("utf-8"),
                            headers={"Title": "probe", "Content-Type": "text/plain"})
log(f"  POST → {status}")
log(f"    {body[:220]}")
for k in ("x-rate-limit-remaining", "x-ratelimit-remaining", "retry-after"):
    if k in {h.lower() for h in headers}:
        log(f"    {k}: {[v for h, v in headers.items() if h.lower() == k]}")

log("")
log("=" * 74)
log("2. poll the same topic back")
log("=" * 74)
time.sleep(2)
status, body, _ = req(BASE + "/json?poll=1")
log(f"  GET  → {status}  {len(body)} bytes")
for line in [l for l in body.splitlines() if l.strip()][:5]:
    try:
        m = json.loads(line)
    except Exception:
        log(f"    unparseable: {line[:120]}")
        continue
    log(f"    id={m.get('id')} time={m.get('time')} event={m.get('event')}")
    log(f"      message: {str(m.get('message'))[:160]}")

log("")
log("=" * 74)
log("3. how far back does it remember")
log("=" * 74)
for since in ("10m", "12h", "all"):
    status, body, _ = req(f"{BASE}/json?poll=1&since={since}")
    n = len([l for l in body.splitlines()
             if l.strip() and '"event":"message"' in l.replace(" ", "")])
    log(f"  since={since:<4} → {status}, {n} messages")

log("")
log("=" * 74)
log("done")
