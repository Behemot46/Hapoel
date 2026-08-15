"""Diagnostic probe — why hapoel.site does not answer yet.

The previous round failed on every request with a truncated cause. The
decisive question is whether the name resolves at all: a domain bought
minutes ago usually has not propagated, which looks identical to a broken
configuration from the outside. Ask DNS directly, then try the host.
"""
import socket
import ssl

import requests

HOSTS = ["hapoel.site", "www.hapoel.site"]


def log(*a):
    print("[probe]", *a, flush=True)


log("=" * 74)
log("A. does the name resolve?")
log("=" * 74)
resolved = {}
for h in HOSTS:
    try:
        infos = socket.getaddrinfo(h, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        resolved[h] = ips
        log(f"  {h:<18} -> {', '.join(ips)}")
    except Exception as e:
        resolved[h] = []
        log(f"  {h:<18} -> NO DNS RECORD  ({type(e).__name__}: {e})")

log("")
log("=" * 74)
log("B. if it resolves, does it serve TLS and our app?")
log("=" * 74)
for h, ips in resolved.items():
    if not ips:
        log(f"  {h}: skipped, nothing to connect to")
        continue
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((h, 443), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=h) as ss:
                cert = ss.getpeercert()
                log(f"  {h}: TLS ok, issued to "
                    f"{dict(x[0] for x in cert['subject']).get('commonName','?')}")
    except Exception as e:
        log(f"  {h}: TLS FAIL {type(e).__name__}: {str(e)[:120]}")
    try:
        r = requests.get(f"https://{h}/", timeout=20, allow_redirects=True)
        log(f"    GET / -> {r.status_code}, server={r.headers.get('server','?')}, "
            f"{len(r.content)}b")
        if "יושב סופר את הדקות" in r.text:
            log("    ^ this is our app")
    except Exception as e:
        log(f"    GET / FAIL {type(e).__name__}: {str(e)[:160]}")

log("")
log("=" * 74)
log("C. what the registrar's nameservers say (is it pointed at Vercel?)")
log("=" * 74)
try:
    r = requests.get("https://dns.google/resolve?name=hapoel.site&type=NS", timeout=20)
    log("  NS:", [a.get("data") for a in r.json().get("Answer", [])] or "none published")
    for t in ("A", "CNAME"):
        r = requests.get(f"https://dns.google/resolve?name=hapoel.site&type={t}", timeout=20)
        j = r.json()
        log(f"  {t}: status={j.get('Status')} "
            f"{[a.get('data') for a in j.get('Answer', [])] or 'none'}")
except Exception as e:
    log(f"  public resolver FAIL {type(e).__name__}: {str(e)[:120]}")
