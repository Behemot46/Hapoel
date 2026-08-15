"use strict";

/**
 * Where a fan's answers land, with nothing for anyone to set up.
 *
 * The app is static files: no server, nowhere to store anything. Vercel
 * runs this one function next to it so the form can be filled and sent
 * without leaving the app and without an account.
 *
 * What this function does not have is a way into GitHub. Writing an issue
 * needs a token, and a token can only be minted by a human in a browser.
 * So it does not try. It parks the answer on a public ntfy topic, which
 * takes a plain POST from anybody, and a scheduled workflow collects it
 * from there and opens the issue with the token GitHub Actions already
 * holds. Nothing has to be created, by anyone, ever.
 *
 * The one number that matters: ntfy keeps a message for 12 hours, measured
 * rather than assumed. The drain runs hourly, so an answer gets a dozen
 * chances to be collected before it expires. If ntfy refuses the publish
 * this function says so, and the app tells the fan the send failed instead
 * of swallowing it.
 *
 * The topic is readable by anyone who knows its name, and the name is in
 * this file, in a public repository. That is the deliberate trade: the
 * answers end up in public issues regardless, and the alternative was a
 * token that was never going to be created. Nothing identifying is asked
 * for, and the form tells fans not to type anything personal.
 */

const TOPIC = process.env.FEEDBACK_TOPIC || "hapoel-fan-app-mnf24qkz7yv9";
const NTFY = "https://ntfy.sh/";

const LIMITS = { fan: 40, want: 40, wants: 4, text: 900 };
const RATE = { perIp: 5, windowMs: 60 * 60 * 1000, minGapMs: 20 * 1000 };

// Best effort only: a serverless instance is short-lived and there may be
// several at once. It stops a stuck finger and a naive script, not a
// determined flood, for that, Vercel's own bot protection is the tool.
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

// The issue itself is written by scripts/feedback_drain.py, which is the
// side that has a token. This one only has to hand over the answers.

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");

  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, reason: "method" });
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

  a.sent = new Date().toISOString();

  try {
    // the JSON publish form, because a Hebrew title in an HTTP header is
    // not something to rely on
    const parked = await fetch(NTFY, {
      method: "POST",
      headers: { "Content-Type": "application/json", "User-Agent": "hapoel-fan-app" },
      body: JSON.stringify({ topic: TOPIC, title: "hapoel-feedback",
                             message: JSON.stringify(a) }),
    });
    if (!parked.ok) {
      console.error("ntfy refused", parked.status, (await parked.text()).slice(0, 200));
      return res.status(502).json({ ok: false, reason: "upstream" });
    }
    const note = await parked.json();
    return res.status(200).json({ ok: true, id: note.id });
  } catch (e) {
    console.error("feedback failed", e && e.message);
    return res.status(502).json({ ok: false, reason: "upstream" });
  }
};
