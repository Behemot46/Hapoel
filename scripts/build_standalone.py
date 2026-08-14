"""Build a single self-contained HTML file of the whole app.

Everything — styles, code, data and any player photos — is inlined, so the
file can be sent over WhatsApp or email and opened straight from disk with
no server and no internet. fetch() is blocked on file://, which is why the
data is embedded rather than loaded.

    python scripts/build_standalone.py [output.html]
"""
import base64
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "hapoel-standalone.html"

def read(p):
    return (APP / p).read_text(encoding="utf-8")

def build():
    html = read("index.html")
    css = read("css/style.css")
    js = read("js/app.js")

    # every data file the app asks for, keyed the way loadJSON looks them up
    data = {}
    for f in sorted((APP / "data").glob("*.json")):
        data[f.stem] = json.loads(f.read_text(encoding="utf-8"))

    # inline player photos as data URIs so the file stays self-contained
    photos = {}
    photo_dir = APP / "img" / "players"
    if photo_dir.exists():
        for img in sorted(photo_dir.glob("*.jpg")):
            b64 = base64.b64encode(img.read_bytes()).decode("ascii")
            photos["img/players/" + img.name] = "data:image/jpeg;base64," + b64
    if photos and "roster" in data:
        for p in data["roster"].get("players", []):
            if p.get("photo") in photos:
                p["photo"] = photos[p["photo"]]

    snapshot = datetime.date.today().strftime("%d.%m.%Y")
    payload = (
        "window.__HAPOEL_DATA__ = " + json.dumps(data, ensure_ascii=False) + ";\n"
        "window.__HAPOEL_SNAPSHOT__ = " + json.dumps(snapshot) + ";\n"
    )

    # drop the external references and inline the real thing in their place
    html = html.replace('<link rel="stylesheet" href="css/style.css">',
                        "<style>\n" + css + "\n</style>")
    html = html.replace('<link rel="manifest" href="manifest.webmanifest">', "")
    html = re.sub(r'\s*<link rel="icon"[^>]*>', "", html)
    html = re.sub(r'\s*<link rel="apple-touch-icon"[^>]*>', "", html)
    html = html.replace('<script src="js/app.js"></script>',
                        "<script>\n" + payload + js + "\n</script>")
    # the service worker block is dead weight in a file:// copy
    html = re.sub(r"<script>\s*// a single-file copy.*?</script>", "", html, flags=re.S)

    if "js/app.js" in html or "css/style.css" in html:
        raise SystemExit("build failed: external references remain")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({kb:.0f} KB, {len(data)} data files, {len(photos)} photos)")

if __name__ == "__main__":
    build()
