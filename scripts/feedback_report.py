"""What the fans answered, counted and quoted.

Each submission from the form arrives as an issue on the project's
repository. This reads them back and prints one report: how many answered,
what kind of fans they are, what they asked for, how useful they find the
app, and then every word they wrote, verbatim. The counted part says what
to build; the written part says why.

Run it from Actions ("דוח משוב מאוהדים"), or locally:

    FEEDBACK_REPO=Behemot46/Hapoel GITHUB_TOKEN=… python scripts/feedback_report.py

The answers live in a public repository, so this report shows nothing that
was not already readable there. If FEEDBACK_REPO is ever pointed at a
private repository, do not run it from Actions here: a public workflow log
would republish what that repository was chosen to keep. The script checks
and refuses.

Nothing here writes anything. It reads, counts and prints.
"""
import collections
import datetime
import json
import os
import re
import urllib.parse
import urllib.request

REPO = os.environ.get("FEEDBACK_REPO") or os.environ.get("GITHUB_REPOSITORY", "Behemot46/Hapoel")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL = "משוב"
MARKER = "נשלח מהטופס באפליקציה"

FIELDS = {
    "fan": "איזה אוהד",
    "wants": "הכי יעזור",
    "rating": "שימושיות",
}


def log(*a):
    print(*a, flush=True)


def api(path, **params):
    url = "https://api.github.com/repos/" + REPO + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "hapoel-feedback-report",
        **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def all_issues():
    """Every issue that came from the form, by label first, and by the
    marker line the function writes, so a submission filed before the label
    existed is still counted."""
    out, page = [], 1
    while True:
        batch = api("/issues", state="all", per_page=100, page=page, labels=LABEL)
        out += batch
        if len(batch) < 100:
            break
        page += 1
    if not out:
        page = 1
        while True:
            batch = api("/issues", state="all", per_page=100, page=page)
            out += [i for i in batch if MARKER in (i.get("body") or "")]
            if len(batch) < 100:
                break
            page += 1
    # the issues endpoint returns pull requests too
    return [i for i in out if "pull_request" not in i]


def field(body, name):
    m = re.search(r"\*\*" + re.escape(FIELDS[name]) + r":\*\*\s*(.+)", body or "")
    return m.group(1).strip() if m else ""


def section(body, heading):
    """The free-text answers are written under a bold heading of their own."""
    m = re.search(r"\*\*" + re.escape(heading) + r"\*\*\s*\n+(.*?)(?=\n\*\*|\n---|\Z)",
                  body or "", re.S)
    return m.group(1).strip() if m else ""


def bar(n, total, width=28):
    filled = 0 if not total else round(width * n / total)
    return "█" * filled + "·" * (width - filled)


def check_target():
    """Read the target, and refuse the one combination that would publish
    something: a private repository printed into a public workflow log."""
    try:
        repo = api("")
    except Exception as e:
        log(f"אי אפשר לקרוא את {REPO}: {e}")
        log("צריך GITHUB_TOKEN עם הרשאת קריאה לכרטיסים באותו ריפו.")
        raise SystemExit(1)
    if repo.get("private") and os.environ.get("GITHUB_ACTIONS") \
            and not os.environ.get("FEEDBACK_ALLOW_CI"):
        raise SystemExit(
            f"{REPO} פרטי, והלוג של ריפו ציבורי גלוי לכולם. "
            "להריץ מקומית, או להגדיר FEEDBACK_ALLOW_CI אם זה בכל זאת מה שרוצים.")


def main():
    check_target()
    issues = all_issues()
    log("=" * 74)
    log(f"משוב מאוהדים, {REPO}")
    log("=" * 74)
    if not issues:
        log("עוד לא הגיעה אף תשובה.")
        log("")
        log("אם הטופס כבר באוויר וזה עדיין ריק, בדקו ש־FEEDBACK_TOKEN מוגדר")
        log("ב־Vercel ושהפריסה האחרונה כוללת אותו.")
        return 0

    dates = sorted(i["created_at"] for i in issues)
    log(f"{len(issues)} תשובות · מ־{dates[0][:10]} עד {dates[-1][:10]}")

    fans, wants, ratings = collections.Counter(), collections.Counter(), collections.Counter()
    ideas, bugs = [], []
    for i in issues:
        b = i.get("body") or ""
        f = field(b, "fan")
        if f:
            fans[f] += 1
        w = field(b, "wants")
        for one in [x.strip() for x in w.split("·") if x.strip()]:
            wants[one] += 1
        r = field(b, "rating")
        m = re.match(r"([1-5])", r)
        if m:
            ratings[int(m.group(1))] += 1
        idea = section(b, "מה להוסיף או לשנות")
        if idea:
            ideas.append((i["number"], i["created_at"][:10], idea))
        bug = section(b, "מה לא עבד")
        if bug:
            bugs.append((i["number"], i["created_at"][:10], bug))

    log("")
    log("-" * 74)
    log("מי ענה")
    log("-" * 74)
    for name, n in fans.most_common():
        log(f"  {n:>3}  {bar(n, len(issues))}  {name}")
    if not fans:
        log("  (לא נבחרה תשובה)")

    log("")
    log("-" * 74)
    log("מה הכי יעזור, כל אוהד בחר עד שלושה")
    log("-" * 74)
    top = wants.most_common()
    for name, n in top:
        log(f"  {n:>3}  {bar(n, top[0][1])}  {name}")
    if not top:
        log("  (לא נבחרה תשובה)")

    log("")
    log("-" * 74)
    log("כמה האפליקציה שימושית")
    log("-" * 74)
    total_r = sum(ratings.values())
    if total_r:
        avg = sum(k * v for k, v in ratings.items()) / total_r
        for n in (5, 4, 3, 2, 1):
            log(f"  {n}  {bar(ratings.get(n, 0), max(ratings.values()))}  {ratings.get(n, 0)}")
        log(f"  ממוצע: {avg:.1f} מתוך 5  ({total_r} דירוגים)")
    else:
        log("  (לא ניתן דירוג)")

    for title, rows in (("מה להוסיף או לשנות", ideas), ("מה לא עבד", bugs)):
        log("")
        log("-" * 74)
        log(f"{title}, {len(rows)} תשובות, במילים שלהם")
        log("-" * 74)
        for num, when, txt in rows:
            log(f"  #{num} · {when}")
            for line in txt.splitlines():
                log("    " + line)
            log("")
        if not rows:
            log("  (אין)")

    log("")
    log("=" * 74)
    log("סוף הדוח · " + datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%d %H:%M UTC"))
    log("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
