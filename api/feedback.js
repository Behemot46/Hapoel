"use strict";

/**
 * Where a fan's answers land — and who can read them.
 *
 * The app itself is static files: no server, nowhere to store anything.
 * Vercel runs this one function next to it, so the form can be filled and
 * sent without leaving the app, without an account and without a
 * third-party form service. Each submission becomes an issue.
 *
 * THE ANSWERS ARE PRIVATE. They go to a repository only the owner can
 * read, never to this public one, and that is enforced here rather than
 * left to whoever fills in the configuration: before the first write the
 * function asks GitHub whether the target repository is private, and
 * refuses to write to it if it is not. A misconfiguration therefore loses
 * a submission — it never publishes one.
 *
 * Two environment variables in Vercel, both required:
 *
 *     FEEDBACK_TOKEN   a GitHub token that may open issues on that repo
 *     FEEDBACK_REPO    owner/repo — a PRIVATE repository
 *
 * With either missing the function answers 501 and the app tells the fan
 * plainly that sending failed, keeping what they typed on screen. There is
 * deliberately no public fallback: a fan who was promised privacy must not
 * be handed to a public issue form instead.
 */

const REPO = process.env.FEEDBACK_REPO || "";
const TOKEN = process.env.FEEDBACK_TOKEN || "";

const LIMITS = { fan: 40, want: 40, wants: 4, text: 900 };
const RATE = { perIp: 5, windowMs: 60 * 60 * 1000, minGapMs: 20 * 1000 };

// Best effort only: a serverless instance is short-lived and there may be
// several at once. It stops a stuck finger and a naive script, not a
// determined flood — for that, Vercel's own bot protection is the tool.
const seen = new Map();

function rateLimited(ip) {
  const now = Date.now();
  const hits = (seen.get(ip) || []).filter(t => now - t < RATE.windowMs);
  if (hits.length && now - hits[hits.length - 1] < RATE.minGapMs) return true;
  if (hits.length >= RATE.perIp) return true;
  hits.push(now);
  seen.set(ip, hits);
  if (seen.size > 500) seen.delete(seen.keys().next().value);
  return false;
}

function clean(v, max) {
  if (typeof v !== "string") return "";
  // control characters would break the issue body; newlines and tabs stay,
  // and the rest is a fan's own words, left exactly as written
  return v.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "")
    .trim().slice(0, max);
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string") {
    try { return JSON.parse(req.body); } catch (e) { return null; }
  }
  return null;
}

function issueBody(a) {
  const lines = [];
  if (a.fan) lines.push("**איזה אוהד:** " + a.fan);
  if (a.wants.length) lines.push("**הכי יעזור:** " + a.wants.join(" · "));
  if (a.rating) lines.push("**שימושיות:** " + a.rating + " מתוך 5");
  if (a.idea) lines.push("", "**מה להוסיף או לשנות**", "", a.idea);
  if (a.bug) lines.push("", "**מה לא עבד**", "", a.bug);
  lines.push("", "---",
    "נשלח מהטופס באפליקציה · " + new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC");
  return lines.join("\n");
}

function issueTitle(a) {
  const first = (a.idea || a.bug || "").split("\n")[0].trim();
  if (first) return "משוב: " + first.slice(0, 70);
  if (a.wants.length) return "משוב: " + a.wants[0];
  if (a.rating) return "משוב: " + a.rating + " מתוך 5";
  return "משוב מאוהד";
}

// Asked once per warm instance, then remembered: whether the repository the
// answers are going to is actually private. This is the guarantee the form
// makes to the fan, so it is checked against GitHub and not against a
// comment in a config file.
let targetPrivate = null;

async function targetIsPrivate() {
  if (targetPrivate !== null) return targetPrivate;
  const res = await fetch("https://api.github.com/repos/" + REPO, {
    headers: {
      Authorization: "Bearer " + TOKEN,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "hapoel-fan-app",
    },
  });
  if (!res.ok) {
    console.error("cannot read target repo", REPO, res.status);
    return null; // unknown — treated as "do not write"
  }
  const repo = await res.json();
  targetPrivate = repo.private === true;
  if (!targetPrivate) {
    console.error("REFUSING: " + REPO + " is public, and answers are private");
  }
  return targetPrivate;
}

async function createIssue(payload) {
  const res = await fetch("https://api.github.com/repos/" + REPO + "/issues", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + TOKEN,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "hapoel-fan-app",
    },
    body: JSON.stringify(payload),
  });
  return res;
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");

  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, reason: "method" });
  }
  if (!TOKEN || !REPO) {
    // not an error the fan caused, and the app says so honestly
    return res.status(501).json({ ok: false, reason: "not-configured" });
  }

  const body = readBody(req);
  if (!body) return res.status(400).json({ ok: false, reason: "bad-json" });

  // a hidden field no human ever sees, and every naive bot fills in
  if (clean(body.nickname, 20)) return res.status(200).json({ ok: true });

  const a = {
    fan: clean(body.fan, LIMITS.fan),
    wants: Array.isArray(body.wants)
      ? body.wants.map(w => clean(w, LIMITS.want)).filter(Boolean).slice(0, LIMITS.wants)
      : [],
    rating: /^[1-5]$/.test(String(body.rating || "")) ? String(body.rating) : "",
    idea: clean(body.idea, LIMITS.text),
    bug: clean(body.bug, LIMITS.text),
  };
  if (!a.fan && !a.wants.length && !a.rating && !a.idea && !a.bug) {
    return res.status(400).json({ ok: false, reason: "empty" });
  }

  const ip = (req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  if (rateLimited(ip)) return res.status(429).json({ ok: false, reason: "too-fast" });

  const payload = { title: issueTitle(a), body: issueBody(a), labels: ["משוב"] };
  try {
    if ((await targetIsPrivate()) !== true) {
      // losing one answer beats publishing it
      return res.status(501).json({ ok: false, reason: "target-not-private" });
    }
    let gh = await createIssue(payload);
    if (gh.status === 422) {
      // a label the repository does not have yet and the token may not be
      // allowed to create — the answer matters more than the label
      delete payload.labels;
      gh = await createIssue(payload);
    }
    if (!gh.ok) {
      const detail = (await gh.text()).slice(0, 200);
      console.error("github refused", gh.status, detail);
      return res.status(502).json({ ok: false, reason: "upstream" });
    }
    const issue = await gh.json();
    return res.status(200).json({ ok: true, number: issue.number });
  } catch (e) {
    console.error("feedback failed", e && e.message);
    return res.status(502).json({ ok: false, reason: "upstream" });
  }
};
