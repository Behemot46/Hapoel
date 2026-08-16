"""Every twelve hours: read the answers, and write what they add up to.

The raw answers already live as issues, one per fan. That is the right place
to keep them and the wrong place to read them: twenty cards tell you nothing
at a glance. This turns them into one page that says what fans are asking
for, who is asking, whether the app is getting more useful, and what broke.

Three things it does that a pile of cards cannot:

  * splits the wishes by kind of fan. That is the entire reason the form
    asks who is answering: a request that is third overall can be first
    among season-ticket holders, and building for the average of the two
    serves neither.
  * says what is new since the last run, so the page can be read in a
    minute without rereading what was already read.
  * keeps every word anybody wrote, verbatim and grouped. The counts say
    what to build; the sentences say why, and they are the part worth
    reading twice.

It writes docs/feedback/digest.md, keeps its own small state next to it, and
updates one tracking issue in place rather than opening a new one each time.
Nothing here changes an answer.
"""
import collections
import datetime
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "feedback" / "digest.md"
STATE = ROOT / "docs" / "feedback" / "state.json"

REPO = os.environ.get("GITHUB_REPOSITORY", "Behemot46/Hapoel")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL = "משוב"
SKIP_LABEL = "בדיקה"          # our own end-to-end tests are not fan answers
TRACKER_TITLE = "סיכום משוב מאוהדים"

FIELDS = {"fan": "איזה אוהד", "wants": "הכי יעזור", "rating": "שימושיות"}


def log(*a):
    print("[digest]", *a, flush=True)


def gh(path, data=None, method=None):
    url = "https://api.github.com/repos/" + REPO + path
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "hapoel-feedback-digest",
            **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
        })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def answers():
    """Every fan answer, newest first, with our own test cards left out."""
    out, page = [], 1
    while page <= 10:
        batch = gh(f"/issues?state=all&labels={urllib.parse.quote(LABEL)}"
                   f"&per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            break
        page += 1
    keep = []
    for i in out:
        if "pull_request" in i:
            continue
        if any(l.get("name") == SKIP_LABEL for l in i.get("labels", [])):
            continue
        keep.append(i)
    keep.sort(key=lambda i: i["created_at"], reverse=True)
    return keep


def field(body, name):
    m = re.search(r"\*\*" + re.escape(FIELDS[name]) + r":\*\*\s*(.+)", body or "")
    return m.group(1).strip() if m else ""


def section(body, heading):
    m = re.search(r"\*\*" + re.escape(heading) + r"\*\*\s*\n+(.*?)(?=\n\*\*|\n---|\Z)",
                  body or "", re.S)
    return m.group(1).strip() if m else ""


def parse(issue):
    b = issue.get("body") or ""
    rating = re.match(r"([1-5])", field(b, "rating"))
    return {
        "number": issue["number"],
        "when": issue["created_at"][:10],
        "created": issue["created_at"],
        "fan": field(b, "fan"),
        "wants": [w.strip() for w in field(b, "wants").split("·") if w.strip()],
        "rating": int(rating.group(1)) if rating else None,
        "idea": section(b, "מה להוסיף או לשנות"),
        "bug": section(b, "מה לא עבד"),
    }


def bar(n, top, width=22):
    return "█" * (0 if not top else round(width * n / top)) + "·" * (
        width - (0 if not top else round(width * n / top)))


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def digest(rows, state):
    now = datetime.datetime.now(datetime.timezone.utc)
    since = state.get("lastRun")
    fresh = [r for r in rows if since and r["created"] > since]
    prev_avg = state.get("avgRating")

    L = []
    add = L.append
    add("<div dir=\"rtl\">")
    add("")
    add("# סיכום משוב מאוהדים")
    add("")
    add(f"עודכן {now.strftime('%d.%m.%Y %H:%M')} UTC. מתעדכן מעצמו כל 12 שעות.")
    add("")

    if not rows:
        add("**עוד לא הגיעה אף תשובה.**")
        add("")
        add("הטופס באוויר ונפתח לאוהד רק אחרי שלוש כניסות, ארבעה מסכים ותשעים "
            "שניות באפליקציה, אז השקט הזה סביר כל עוד מעט אנשים נכנסו. "
            "כשתגיע התשובה הראשונה היא תופיע כאן מעצמה.")
        add("")
        add("</div>")
        return "\n".join(L), {"lastRun": now.isoformat(timespec="seconds"),
                              "count": 0, "avgRating": None}

    rated = [r["rating"] for r in rows if r["rating"]]
    avg = sum(rated) / len(rated) if rated else None

    add("## בשורה אחת")
    add("")
    add(f"- **{len(rows)} תשובות** בסך הכול"
        + (f", מתוכן **{len(fresh)} חדשות** מאז הסיכום הקודם" if since else ""))
    if avg:
        move = ""
        if prev_avg:
            d = avg - prev_avg
            move = (f", ללא שינוי" if abs(d) < 0.05
                    else f", {'עלה' if d > 0 else 'ירד'} ב־{abs(d):.1f} מאז הסיכום הקודם")
        add(f"- **שימושיות: {avg:.1f} מתוך 5** ({len(rated)} דירוגים){move}")
    bugs = [r for r in rows if r["bug"]]
    if bugs:
        add(f"- **{len(bugs)} דיווחים על משהו שלא עבד**, כולם למטה במילים שלהם")
    add("")

    # what to build, and for whom
    wants = collections.Counter(w for r in rows for w in r["wants"])
    add("## מה הכי יעזור לאוהדים")
    add("")
    if wants:
        top = wants.most_common()
        for name, n in top:
            add(f"`{bar(n, top[0][1])}` **{n}** {name}")
        add("")
        by_fan = collections.defaultdict(collections.Counter)
        for r in rows:
            if r["fan"]:
                by_fan[r["fan"]].update(r["wants"])
        if len(by_fan) > 1:
            add("### ולפי סוג האוהד")
            add("")
            add("זו הסיבה שהטופס שואל מי עונה: בקשה שהיא שלישית בסך הכול "
                "יכולה להיות ראשונה אצל קהל אחד, ובניית ממוצע בין השניים "
                "לא משרתת אף אחד מהם.")
            add("")
            overall_first = top[0][0]
            for fan, c in sorted(by_fan.items(), key=lambda kv: -sum(kv[1].values())):
                items = ", ".join(f"{k} ({v})" for k, v in c.most_common(3))
                add(f"- **{fan}** ({sum(1 for r in rows if r['fan'] == fan)} עונים): {items}")
                if c and c.most_common(1)[0][0] != overall_first:
                    add(f"  - שימו לב: אצלם הראשון הוא **{c.most_common(1)[0][0]}**, "
                        f"ולא ״{overall_first}״ שמוביל בסך הכול")
            add("")
    else:
        add("איש עוד לא בחר פיצ׳ר.")
        add("")

    if rated:
        add("## כמה האפליקציה שימושית")
        add("")
        dist = collections.Counter(rated)
        top = max(dist.values())
        for n in (5, 4, 3, 2, 1):
            add(f"`{bar(dist.get(n, 0), top)}` {n}: {dist.get(n, 0)}")
        add("")
        low = [r for r in rows if r["rating"] and r["rating"] <= 2]
        if low:
            add(f"**{len(low)} אוהדים נתנו 1 או 2.** מה שהם כתבו:")
            add("")
            for r in low:
                said = r["idea"] or r["bug"] or "(לא כתבו כלום)"
                add(f"- #{r['number']} ({r['when']}): {said}")
            add("")

    for title, key, note in (
            ("מה שלא עבד", "bug", "באג שאוהד טרח לדווח עליו הוא באג שהפריע לו מספיק."),
            ("מה להוסיף או לשנות", "idea", "במילים שלהם, מהחדש לישן.")):
        rows_k = [r for r in rows if r[key]]
        add(f"## {title} ({len(rows_k)})")
        add("")
        if note and rows_k:
            add(f"_{note}_")
            add("")
        for r in rows_k:
            mark = " **חדש**" if since and r["created"] > since else ""
            who = f" · {r['fan']}" if r["fan"] else ""
            add(f"**#{r['number']}** · {r['when']}{who}{mark}")
            add("")
            for line in r[key].splitlines():
                add("> " + line)
            add("")
        if not rows_k:
            add("_אין._")
            add("")

    add("---")
    add("")
    add(f"התשובות הגולמיות: הכרטיסים עם התווית ״{LABEL}״ בריפו. "
        "הדף הזה נכתב מהן ולא משנה אותן.")
    add("")
    add("</div>")
    return "\n".join(L), {
        "lastRun": now.isoformat(timespec="seconds"),
        "count": len(rows),
        "avgRating": round(avg, 3) if avg else None,
    }


def update_tracker(body):
    """One issue, edited in place. A new issue every twelve hours would be
    noise, and noise is what this page exists to remove."""
    if not TOKEN:
        log("no token, tracker issue left alone")
        return
    found = None
    for i in gh("/issues?state=all&per_page=100"):
        if i.get("title") == TRACKER_TITLE and "pull_request" not in i:
            found = i
            break
    short = body if len(body) < 60000 else body[:59000] + "\n\n_(נחתך)_\n"
    if found:
        gh(f"/issues/{found['number']}", data={"body": short}, method="PATCH")
        log(f"tracker issue #{found['number']} updated")
    else:
        made = gh("/issues", data={"title": TRACKER_TITLE, "body": short})
        log(f"tracker issue #{made['number']} opened")


def main():
    rows = [parse(i) for i in answers()]
    log(f"{len(rows)} answers")
    state = load_state()
    body, new_state = digest(rows, state)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body + "\n", encoding="utf-8")
    STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    log(f"wrote {OUT.relative_to(ROOT)} ({len(body)} characters)")
    update_tracker(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
