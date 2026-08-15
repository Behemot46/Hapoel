"""Collect the answers waiting on the topic and file each one as an issue.

This is the half of the feedback path that has a token. The function on the
site cannot write to GitHub, so it parks each answer on a public ntfy topic;
this runs on a schedule inside Actions, where GITHUB_TOKEN already exists,
and turns whatever is waiting there into issues.

Two facts shape the whole design:

  * ntfy keeps a message for 12 hours. So the drain polls the last 12 hours
    every time, rather than tracking a position, and runs hourly. Losing the
    state file, or skipping a run, costs nothing.
  * Polling a window means seeing the same answers again. Deduplication is
    therefore not optional, and it is done on the message id, which is
    written into the issue body and read back from the issues themselves.
    There is no state to lose.

Anyone can publish to the topic, because that is what makes the whole thing
work without a key. So nothing here trusts what arrives: fields are checked
and truncated, anything shaped wrong is dropped and counted, and a single
run will not open more than MAX_NEW issues no matter what is waiting.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

TOPIC = os.environ.get("FEEDBACK_TOPIC", "hapoel-fan-app-mnf24qkz7yv9")
REPO = os.environ.get("GITHUB_REPOSITORY", "Behemot46/Hapoel")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL = "משוב"
MARKER = "נשלח מהטופס באפליקציה"

MAX_NEW = 20          # one run will not flood the tracker
LIMITS = {"fan": 40, "want": 40, "wants": 4, "text": 900}
CTRL = re.compile("[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]")


def log(*a):
    print("[drain]", *a, flush=True)


def gh(path, data=None, method=None):
    url = "https://api.github.com/repos/" + REPO + path
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "hapoel-feedback-drain",
            **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
        })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def waiting():
    """Everything published in the window ntfy still remembers."""
    url = f"https://ntfy.sh/{urllib.parse.quote(TOPIC)}/json?poll=1&since=12h"
    req = urllib.request.Request(url, headers={"User-Agent": "hapoel-feedback-drain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            note = json.loads(line)
        except ValueError:
            continue
        if note.get("event") == "message" and note.get("id"):
            out.append(note)
    return out


def already_filed():
    """The ids of answers that became issues, read from the issues."""
    ids, page = set(), 1
    while page <= 5:
        batch = gh(f"/issues?state=all&per_page=100&page={page}")
        for i in batch:
            m = re.search(r"ntfy:([A-Za-z0-9]+)", i.get("body") or "")
            if m:
                ids.add(m.group(1))
        if len(batch) < 100:
            break
        page += 1
    return ids


def text(v, limit):
    return CTRL.sub("", v).strip()[:limit] if isinstance(v, str) else ""


def answer_of(note):
    """Parse one parked message, or return None if it is not one of ours."""
    try:
        raw = json.loads(note.get("message") or "")
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    a = {
        "fan": text(raw.get("fan"), LIMITS["fan"]),
        "wants": [text(w, LIMITS["want"]) for w in (raw.get("wants") or [])
                  if isinstance(w, str)][:LIMITS["wants"]],
        "rating": str(raw.get("rating") or "") if str(raw.get("rating") or "") in "12345" else "",
        "idea": text(raw.get("idea"), LIMITS["text"]),
        "bug": text(raw.get("bug"), LIMITS["text"]),
        "sent": text(raw.get("sent"), 32),
    }
    a["wants"] = [w for w in a["wants"] if w]
    if not (a["fan"] or a["wants"] or a["rating"] or a["idea"] or a["bug"]):
        return None
    return a


def title_of(a):
    first = (a["idea"] or a["bug"] or "").split("\n")[0].strip()
    if first:
        return "משוב: " + first[:70]
    if a["wants"]:
        return "משוב: " + a["wants"][0]
    if a["rating"]:
        return "משוב: " + a["rating"] + " מתוך 5"
    return "משוב מאוהד"


def body_of(a, note):
    """The shape scripts/feedback_report.py reads back, plus the id it is
    deduplicated on."""
    lines = []
    if a["fan"]:
        lines.append("**איזה אוהד:** " + a["fan"])
    if a["wants"]:
        lines.append("**הכי יעזור:** " + " · ".join(a["wants"]))
    if a["rating"]:
        lines.append("**שימושיות:** " + a["rating"] + " מתוך 5")
    if a["idea"]:
        lines += ["", "**מה להוסיף או לשנות**", "", a["idea"]]
    if a["bug"]:
        lines += ["", "**מה לא עבד**", "", a["bug"]]
    when = (a["sent"] or "")[:16].replace("T", " ")
    lines += ["", "---", f"{MARKER} · {when} UTC · ntfy:{note['id']}"]
    return "\n".join(lines)


def file_issue(a, note):
    payload = {"title": title_of(a), "body": body_of(a, note), "labels": [LABEL]}
    try:
        return gh("/issues", data=payload)
    except urllib.error.HTTPError as e:
        if e.code == 422:
            # a label the repository does not have yet: the answer matters
            # more than the label
            payload.pop("labels")
            return gh("/issues", data=payload)
        raise


def main():
    notes = waiting()
    filed = already_filed()
    log(f"{len(notes)} waiting on the topic, {len(filed)} already filed")

    fresh = [n for n in notes if n["id"] not in filed]
    if len(fresh) > MAX_NEW:
        log(f"only the first {MAX_NEW} of {len(fresh)} will be filed this run, "
            "the rest are still on the topic and the next run takes them")
        fresh = fresh[:MAX_NEW]

    made, junk = 0, 0
    for note in fresh:
        a = answer_of(note)
        if a is None:
            junk += 1
            continue
        issue = file_issue(a, note)
        made += 1
        log(f"  #{issue['number']}  {issue['title'][:60]}")

    log(f"filed {made}, skipped {len(notes) - len(fresh)} already there, "
        f"dropped {junk} that were not answers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
