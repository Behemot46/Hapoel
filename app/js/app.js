"use strict";

const state = {
  games: null, standings: null, meta: null, club: null,
  gamesTab: "upcoming", tableTab: "league", diaryScope: "season",
  hofTab: "israeli", statsTab: "now", podcastsTab: "team",
};

const view = document.getElementById("view");

/* ---------- the fan diary: attendance kept on this device only ---------- */

const DIARY_KEY = "hapoel-diary-v1";

// id -> snapshot of the game, so the diary survives games leaving the feed
function loadDiary() {
  try { return JSON.parse(localStorage.getItem(DIARY_KEY)) || {}; }
  catch (e) { return {}; }
}
let diary = loadDiary();

function saveDiary() {
  try { localStorage.setItem(DIARY_KEY, JSON.stringify(diary)); } catch (e) {}
}

function attended(id) { return Object.prototype.hasOwnProperty.call(diary, id); }

function snapshot(g) {
  return {
    date: g.date,
    competition: g.competition,
    opponent: opponent(g),
    home: isHome(g),
    status: g.status,
    us: ourScore(g),
    them: theirScore(g),
  };
}

function toggleAttend(g) {
  if (attended(g.id)) delete diary[g.id];
  else diary[g.id] = snapshot(g);
  saveDiary();
}

// keep stored snapshots fresh, a game marked while upcoming gains its result later
function refreshDiary() {
  let dirty = false;
  (state.games.games || []).forEach(g => {
    if (attended(g.id)) {
      const next = snapshot(g);
      if (JSON.stringify(next) !== JSON.stringify(diary[g.id])) {
        diary[g.id] = next;
        dirty = true;
      }
    }
  });
  if (dirty) saveDiary();
}

async function loadJSON(path) {
  // the standalone single-file build embeds the data, because fetch() is
  // blocked on file://, so read from there first when it exists
  const embedded = window.__HAPOEL_DATA__;
  if (embedded) {
    const key = path.replace(/^data\//, "").replace(/\.json$/, "");
    if (Object.prototype.hasOwnProperty.call(embedded, key)) return embedded[key];
  }
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(path + " → " + res.status);
  return res.json();
}

async function boot() {
  try {
    const [games, standings, meta, club, roster, names, profiles, details, teamNames, history, eurocup, hof, lastSeason, seasonStats, feedback, venues, news, podcasts] = await Promise.all([
      loadJSON("data/games.json"),
      loadJSON("data/standings.json"),
      loadJSON("data/meta.json"),
      loadJSON("data/club.json"),
      loadJSON("data/roster.json").catch(() => ({ players: [] })),
      loadJSON("data/player-names.json").catch(() => ({})),
      loadJSON("data/player-profiles.json").catch(() => ({})),
      loadJSON("data/player-details.json").catch(() => ({})),
      loadJSON("data/team-names.json").catch(() => ({})),
      loadJSON("data/history.json").catch(() => (null)),
      loadJSON("data/eurocup.json").catch(() => (null)),
      loadJSON("data/hall-of-fame.json").catch(() => (null)),
      loadJSON("data/lastseason.json").catch(() => (null)),
      loadJSON("data/season-stats.json").catch(() => (null)),
      loadJSON("data/feedback.json").catch(() => (null)),
      loadJSON("data/venue-names.json").catch(() => (null)),
      loadJSON("data/news.json").catch(() => (null)),
      loadJSON("data/podcasts.json").catch(() => (null)),
    ]);
    state.games = games;
    state.standings = standings;
    state.meta = meta;
    state.club = club;
    state.roster = roster;
    state.playerNames = names || {};
    state.profiles = profiles || {};
    state.details = details || {};
    state.teamNames = teamNames || {};
    state.history = history;
    state.eurocup = eurocup;
    state.hof = hof;
    state.lastSeason = lastSeason;
    state.seasonStats = seasonStats;
    state.feedback = feedback;
    state.venues = venues;
    state.news = news;
    state.podcasts = podcasts;
    if (meta.sample) document.getElementById("sampleBanner").hidden = false;
    // the single-file build is a frozen copy, so say so plainly
    if (window.__HAPOEL_SNAPSHOT__) {
      const b = document.getElementById("sampleBanner");
      b.textContent = "עותק להורדה: צילום מצב מ־" + window.__HAPOEL_SNAPSHOT__ +
        ". לגרסה המתעדכנת: " + appHost();
      b.hidden = false;
    }
    refreshDiary();
  } catch (e) {
    view.innerHTML = '<div class="empty">לא הצלחנו לטעון את הנתונים.<br>בדקו את החיבור ונסו לרענן.</div>';
    return;
  }
  const sb = document.getElementById("shareBtn");
  if (sb) sb.onclick = shareApp;
  window.addEventListener("hashchange", render);
  watchInstall();
  render();
  // a frozen single-file copy has no site to poll
  if (!window.__HAPOEL_SNAPSHOT__) { watchLive(); watchPodcasts(); }
  pollWhenQuiet(countVisit());
}

/* ---------- helpers ---------- */

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}
// A score written inside Hebrew prose comes out backwards. Digits are weak
// left-to-right and the separator between them is neutral, so the RTL
// paragraph around them decides the order and puts the second number first:
// "10‑3" is painted as "3-10", and "ניצחון 92‑89" as "89-92", which reads
// as a defeat. Every such run gets its own isolate so it keeps the order it
// was written in. Applies to authored text; a bare number is unaffected,
// only pairs joined by a separator flip.
const NUM_RUN = /\d[\d,.]*(?:\s?[‑\-–:/]\s?\d[\d,.]*)+/g;

function proseInto(node, str) {
  const s = String(str == null ? "" : str);
  let last = 0;
  s.replace(NUM_RUN, (m, i) => {
    if (i > last) node.appendChild(document.createTextNode(s.slice(last, i)));
    const b = document.createElement("bdi");
    b.className = "numrun";
    b.textContent = m;
    node.appendChild(b);
    last = i + m.length;
    return m;
  });
  if (last < s.length) node.appendChild(document.createTextNode(s.slice(last)));
  return node;
}

// same shape as text(), for strings that come from the data files
function prose(tag, cls, str) {
  return proseInto(el(tag, cls), str);
}

function text(tag, cls, str) {
  const n = el(tag, cls);
  n.textContent = str;
  return n;
}

const MONTHS_SHORT = ["ינו׳", "פבר׳", "מרץ", "אפר׳", "מאי", "יוני", "יולי", "אוג׳", "ספט׳", "אוק׳", "נוב׳", "דצמ׳"];
const fmtFull = new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long" });
const fmtTime = new Intl.DateTimeFormat("he-IL", { hour: "2-digit", minute: "2-digit" });
const fmtUpdatedDate = new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "numeric" });
const fmtUpdated = { format: d => fmtUpdatedDate.format(d) + " בשעה " + fmtTime.format(d) };

// the league lists the club under its sponsored or abbreviated name
// ("הפועל י-ם"), so match loosely
function isUs(name) {
  if (!name) return false;
  const lat = name.toLowerCase();
  // European fixtures arrive in Latin ("Hapoel Midtown Jerusalem")
  if (lat.includes("jerusalem") && (lat.includes("hapoel") || lat.includes("midtown"))) return true;
  if (!name.includes("הפועל")) return false;
  return ["ירושלים", "י-ם", "י־ם", 'י"ם', "י״ם"].some(j => name.includes(j));
}

// show a Hebrew name where we have one, otherwise the original
function teamName(name) {
  return (state.teamNames || {})[name] || name;
}
function isLatin(name) { return /^[\x00-\x7F\s'’.-]+$/.test(name || ""); }
function isHome(g) { return isUs(g.home); }
function opponent(g) { return isHome(g) ? g.away : g.home; }
function ourScore(g) { return isHome(g) ? g.homeScore : g.awayScore; }
function theirScore(g) { return isHome(g) ? g.awayScore : g.homeScore; }
function won(g) { return ourScore(g) > theirScore(g); }

function upcoming() {
  return state.games.games
    .filter(g => g.status !== "finished")
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}
function finished() {
  return state.games.games
    .filter(g => g.status === "finished")
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

/* ---------- routing ---------- */

const routes = {
  "": renderHome, "#/": renderHome, "#/games": renderGames,
  "#/table": renderTable, "#/roster": renderRoster, "#/diary": renderDiary,
  "#/meet": renderMeet, "#/history": renderHistory,
  "#/hof": renderHof, "#/stats": renderStats, "#/news": renderNews,
  "#/podcasts": renderPodcasts,
};

function render() {
  const hash = location.hash || "#/";
  // player detail lives under #/player/<slug>
  const playerMatch = hash.match(/^#\/player\/(.+)$/);
  const fn = playerMatch
    ? () => renderPlayer(decodeURIComponent(playerMatch[1]))
    : (routes[hash] || renderHome);
  const routeName = hash === "#/games" ? "games"
    : hash === "#/table" ? "table"
    : (hash === "#/roster" || hash === "#/meet" || playerMatch) ? "roster"
    : (hash === "#/history" || hash === "#/hof" || hash === "#/news"
       || hash === "#/podcasts") ? "home"
    : hash === "#/stats" ? "table"
    : hash === "#/diary" ? "diary" : "home";
  document.querySelectorAll(".tabbar a").forEach(a =>
    a.classList.toggle("active", a.dataset.route === routeName));
  // leaving the podcasts screen ends the visit, so the next arrival
  // recomputes what is new
  if (hash !== "#/podcasts") podcastFresh = null;
  noteScreen(hash); // distinct screens: four taps around the app, not four taps
  stopCountdown(); // the view is about to be wiped from under the ticking element
  view.innerHTML = "";
  fn();
  window.scrollTo(0, 0);
}

// "נגד X", with the Latin part isolated so RTL does not scramble it
function oppEl(cls, raw) {
  const name = teamName(raw);
  const d = el("div", cls);
  d.appendChild(document.createTextNode("נגד "));
  const s = text("span", isLatin(name) ? "latin" : "", name);
  d.appendChild(s);
  return d;
}

/* ---------- the live countdown the app is named after ---------- */

let countdownTimer = null;

function stopCountdown() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
}

function plural(n, one, many) { return n === 1 ? one : many; }

// builds the counter and keeps it ticking until the view changes
function countdownEl(game) {
  const wrap = el("div", "countdown");
  const big = el("div", "cd-minutes");
  const num = text("span", "cd-num", "-");
  big.appendChild(num);
  wrap.appendChild(big);
  const unit = text("div", "cd-unit", "דקות למשחק");
  wrap.appendChild(unit);
  const parts = el("div", "cd-parts");
  wrap.appendChild(parts);

  const target = new Date(game.date).getTime();

  const tick = () => {
    const left = target - Date.now();

    if (left <= 0) {
      // 2.5h is roughly a game; past that the result simply hasn't reached us yet
      const tipped = -left < 2.5 * 3600 * 1000;
      wrap.classList.add("live");
      wrap.classList.toggle("tipped", tipped);
      num.textContent = tipped ? "עכשיו" : "היום";
      unit.textContent = tipped ? "המשחק כבר התחיל" : "המשחק היה אמור להתחיל";
      parts.textContent = "";
      return;
    }

    const totalMin = Math.floor(left / 60000);
    num.textContent = totalMin.toLocaleString("he-IL");

    const days = Math.floor(left / 86400000);
    const hours = Math.floor(left / 3600000) % 24;
    const mins = Math.floor(left / 60000) % 60;
    const secs = Math.floor(left / 1000) % 60;

    parts.textContent = "";
    const bits = [];
    if (days) bits.push([days, plural(days, "יום", "ימים")]);
    if (days || hours) bits.push([hours, plural(hours, "שעה", "שעות")]);
    bits.push([mins, plural(mins, "דקה", "דקות")]);
    bits.push([secs, plural(secs, "שנייה", "שניות")]);
    bits.forEach(([v, label], i) => {
      if (i) parts.appendChild(text("span", "cd-sep", "·"));
      const b = el("span", "cd-part");
      b.appendChild(text("span", "cd-pv", String(v)));
      b.appendChild(text("span", "cd-pl", label));
      parts.appendChild(b);
    });
  };

  tick();
  stopCountdown();
  countdownTimer = setInterval(tick, 1000);
  return wrap;
}

/* ---------- the live score on game night ---------- */

// live.json is republished straight to the site every few minutes while a
// game is on. It may be missing entirely, that just means "nothing on".
let livePoll = null;

function stopLivePoll() {
  if (livePoll) { clearInterval(livePoll); livePoll = null; }
}

async function fetchLive() {
  try {
    const res = await fetch("data/live.json?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) return null;
    const d = await res.json();
    return d && d.state && d.state !== "idle" ? d : null;
  } catch (e) {
    return null;
  }
}

function minutesAgo(iso) {
  const t = new Date(iso).getTime();
  if (!t) return null;
  return Math.max(0, Math.round((Date.now() - t) / 60000));
}

function freshnessLabel(iso) {
  const m = minutesAgo(iso);
  if (m === null) return "";
  if (m < 1) return "עודכן ממש עכשיו";
  if (m === 1) return "עודכן לפני דקה";
  if (m < 60) return "עודכן לפני " + m + " דקות";
  const h = Math.floor(m / 60);
  return "עודכן לפני " + (h === 1 ? "שעה" : h + " שעות");
}

function quarterLabel(q) {
  if (!q) return "";
  return q >= 4 ? "רבע רביעי" : ["רבע ראשון", "רבע שני", "רבע שלישי"][q - 1] || "";
}

function liveCard(live) {
  const g = live.game || {};
  const done = live.state === "final";
  const c = el("div", "card live-game" + (done ? " done" : ""));
  const head = el("div", "live-head");
  head.appendChild(text("span", "live-dot", ""));
  head.appendChild(text("span", "live-label", done ? "המשחק הסתיים" : "עכשיו"));
  c.appendChild(head);

  const opp = isUs(g.home) ? g.away : g.home;
  c.appendChild(oppEl("opponent", opp));
  c.appendChild(text("div", "comp",
    (g.competition || "") + (g.venue ? " · " + venueLabel(g.venue) : "")));

  if (live.state === "live" || live.state === "final") {
    const us = live.ourScore, them = live.theirScore;
    const box = el("div", "live-score");
    const ours = el("div", "ls-side" + (us > them ? " lead" : ""));
    ours.appendChild(text("div", "ls-num", String(us)));
    ours.appendChild(text("div", "ls-who", "הפועל"));
    const theirs = el("div", "ls-side" + (them > us ? " lead" : ""));
    theirs.appendChild(text("div", "ls-num", String(them)));
    theirs.appendChild(text("div", "ls-who", teamName(opp)));
    box.appendChild(ours);
    box.appendChild(text("div", "ls-sep", "-"));
    box.appendChild(theirs);
    c.appendChild(box);
    if (live.state === "live" && live.quarter) {
      c.appendChild(text("div", "live-when", quarterLabel(live.quarter)));
    }
  } else if (live.state === "starting") {
    c.appendChild(text("div", "live-when", "רגע לפני הקפיצה"));
  } else {
    // a domestic game: we know it is being played, we have no feed for it
    c.appendChild(text("div", "live-when", "המשחק מתנהל · אין הזנת תוצאות חיה"));
  }

  c.appendChild(text("div", "live-fresh", freshnessLabel(live.updated)));
  return c;
}

// swap the countdown out for the live card when a game starts, and back to
// the schedule when it ends, without the fan having to reload anything
function watchLive() {
  stopLivePoll();
  const paint = async () => {
    const live = await fetchLive();
    const had = state.live;
    state.live = live;
    const changed = JSON.stringify(had || null) !== JSON.stringify(live || null);
    if (changed && (location.hash === "" || location.hash === "#/")) render();
  };
  paint();
  livePoll = setInterval(paint, 60000);
}

/* ---------- adding games to the phone's calendar ---------- */

// Two hours is a basketball game with its breaks; close enough that the
// slot in someone's calendar is honest without pretending to know the end.
const GAME_MINUTES = 120;

function icsStamp(d) {
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}
function icsEscape(s) {
  return String(s || "").replace(/[\\;,]/g, m => "\\" + m).replace(/\n/g, "\\n");
}
// RFC 5545 wants lines folded at 75 octets, Hebrew is multi-byte, so fold
// by byte count and never in the middle of a character
function icsFold(line) {
  const enc = new TextEncoder();
  if (enc.encode(line).length <= 74) return line;
  const out = [];
  let cur = "", bytes = 0, limit = 74;
  for (const ch of line) {
    const n = enc.encode(ch).length;
    if (bytes + n > limit) { out.push(cur); cur = " "; bytes = 1; limit = 73; }
    cur += ch; bytes += n;
  }
  out.push(cur);
  return out.join("\r\n");
}

// home team first, the way a fixture is normally written; which side we are
// on is spelled out in the description instead
function gameTitle(g) {
  return teamName(g.home) + ", " + teamName(g.away);
}

// calendar clients are happier with an ASCII UID, and our ids carry Hebrew
function icsUid(g) {
  let h = 0;
  for (let i = 0; i < g.id.length; i++) h = (h * 31 + g.id.charCodeAt(i)) >>> 0;
  return g.date.slice(0, 10).replace(/-/g, "") + "-" + h.toString(36) +
         "@hapoel-fan-app";
}

function gameLocation(g) {
  // the calendar entry is the one place a fan checks on the way out the
  // door, so the city belongs in it
  if (g.venue) {
    const v = venueInfo(g.venue);
    return v ? v.he + ", " + v.city : g.venue;
  }
  return isHome(g) ? ((state.club && state.club.arena) || "") : "";
}

function vevent(g, stamp) {
  const start = new Date(g.date);
  const end = new Date(start.getTime() + GAME_MINUTES * 60000);
  const lines = [
    "BEGIN:VEVENT",
    "UID:" + icsUid(g),
    "DTSTAMP:" + stamp,
    "DTSTART:" + icsStamp(start),
    "DTEND:" + icsStamp(end),
    "SUMMARY:" + icsEscape("🏀 " + gameTitle(g)),
    "DESCRIPTION:" + icsEscape(
      g.competition + " · " + (isHome(g) ? "משחק בית" : "משחק חוץ") +
      "\n" + appUrl()),
  ];
  const loc = gameLocation(g);
  if (loc) lines.push("LOCATION:" + icsEscape(loc));
  lines.push(
    "URL:" + appUrl(),
    // one reminder, two hours before, enough time to get to מלחה
    "BEGIN:VALARM",
    "ACTION:DISPLAY",
    "DESCRIPTION:" + icsEscape("היום " + gameTitle(g)),
    "TRIGGER:-PT2H",
    "END:VALARM",
    "END:VEVENT");
  return lines;
}

function buildIcs(games) {
  const stamp = icsStamp(new Date());
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Hapoel Jerusalem Fan App//HE",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:" + icsEscape("הפועל ירושלים"),
  ];
  games.forEach(g => lines.push(...vevent(g, stamp)));
  lines.push("END:VCALENDAR");
  return lines.map(icsFold).join("\r\n") + "\r\n";
}

function downloadIcs(games, filename) {
  const blob = new Blob([buildIcs(games)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function calButton(games, label, filename, cls) {
  const b = el("button", "cal-btn" + (cls ? " " + cls : ""));
  b.type = "button";
  b.appendChild(text("span", "cal-ico", "📅"));
  b.appendChild(text("span", "", label));
  b.onclick = () => downloadIcs(games, filename);
  return b;
}

// the file lands in Downloads/Files on some phones rather than opening the
// calendar straight away, so say so instead of leaving people confused
function calNote() {
  return text("div", "cal-note", "הקובץ יורד למכשיר, פתיחה שלו מוסיפה את המשחקים ליומן");
}

/* ---------- sharing the app itself ---------- */

// always the live site, never location.href, a standalone copy opened
// from disk would otherwise share a path on the sender's own device.
// The address lives in club.json and nowhere else: whatever the app is
// published under is what fans get sent, and moving hosts is one edit.
function appUrl() {
  return (state.club && state.club.url) || location.origin + "/";
}

// the same address without the scheme, for reading rather than clicking
function appHost() {
  return appUrl().replace(/^https?:\/\//, "").replace(/\/$/, "");
}

function shareApp() {
  const msg = [
    "יושב סופר את הדקות 🔴⚫",
    "אפליקציית האוהדים של הפועל ירושלים: לוח משחקים, טבלה, סגל ויומן אישי.",
    "חינם, בלי הרשמה, נכנסים ומשתמשים:",
    appUrl(),
  ].join("\n");
  window.open("https://wa.me/?text=" + encodeURIComponent(msg), "_blank", "noopener");
}

/* ---------- adding the app to the home screen ---------- */

// Chrome hands us the install prompt through an event and lets us fire it
// later; iOS Safari has no such API at all, so there the honest thing is to
// show the two taps rather than a button that cannot do anything.
const INSTALL_KEY = "hapoel-install-v1";
let installPrompt = null;

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
}

function isIosSafari() {
  const ua = navigator.userAgent;
  // iPadOS 13+ reports itself as a Mac, but a Mac has no touch screen
  const ios = /iphone|ipod|ipad/i.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return ios && !/crios|fxios|edgios/i.test(ua);
}

function installHidden() {
  try { return localStorage.getItem(INSTALL_KEY) === "hidden"; }
  catch (e) { return false; }
}

function hideInstall() {
  try { localStorage.setItem(INSTALL_KEY, "hidden"); } catch (e) {}
}

// nothing to offer once it is installed, when the fan waved it away, or on a
// browser that neither fires the event nor is an iOS we know the steps for
function canOfferInstall() {
  if (window.__HAPOEL_SNAPSHOT__ || isStandalone() || installHidden()) return false;
  return !!installPrompt || isIosSafari();
}

function watchInstall() {
  window.addEventListener("beforeinstallprompt", e => {
    e.preventDefault();          // keep Chrome's own mini-bar out of the way
    installPrompt = e;           // and fire it ourselves when the fan asks
    if (location.hash === "" || location.hash === "#/") render();
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    hideInstall();
    if (location.hash === "" || location.hash === "#/") render();
  });
}

function installCard() {
  if (!canOfferInstall()) return null;
  const c = el("div", "card install-card");

  const x = el("button", "install-x", "×");
  x.type = "button";
  x.setAttribute("aria-label", "לא להציע יותר");
  x.onclick = () => { hideInstall(); render(); };
  c.appendChild(x);

  const t = el("div", "install-text");
  t.appendChild(text("div", "share-title", "רוצים אותה על מסך הבית?"));
  t.appendChild(text("div", "share-sub",
    "נפתחת כמו אפליקציה רגילה, במסך מלא, ועובדת גם בלי אינטרנט"));
  c.appendChild(t);

  if (installPrompt) {
    const b = el("button", "wa-btn", "הוספה");
    b.type = "button";
    b.onclick = async () => {
      const p = installPrompt;
      installPrompt = null;      // a prompt may only be used once
      b.disabled = true;
      try {
        p.prompt();
        const res = await p.userChoice;
        if (res && res.outcome === "accepted") hideInstall();
      } catch (e) { /* dismissed mid-flight, leave the card for next time */ }
      render();
    };
    c.appendChild(b);
  } else {
    // iOS: spell out the two taps, with the share glyph drawn rather than
    // typed, because the character for it renders as a box on most fonts
    const steps = el("div", "install-steps");
    const one = el("span", "install-step");
    one.appendChild(document.createTextNode("הקישו "));
    one.appendChild(shareGlyph());
    one.appendChild(document.createTextNode(" בסרגל של ספארי"));
    steps.appendChild(one);
    steps.appendChild(text("span", "install-step", "ואז ״הוספה למסך הבית״"));
    c.appendChild(steps);
    c.classList.add("install-ios");
  }
  return c;
}

function shareGlyph() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "ios-share");
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(ns, "path");
  p.setAttribute("d", "M12 3l4 4-1.4 1.4L13 6.8V15h-2V6.8L9.4 8.4 8 7l4-4zM5 12h3v2H6v6h12v-6h-2v-2h3a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1z");
  svg.appendChild(p);
  return svg;
}

// The poll shows itself once and then never again. Fans who waved it away,
// or who only thought of something on the tenth visit, need a way in that is
// not a grey line of text at the bottom of the page.
function feedbackCard() {
  if (!pollConfig() || window.__HAPOEL_SNAPSHOT__) return null;
  const c = el("div", "card feedback-card");
  const t = el("div");
  t.appendChild(text("div", "share-title", "מה חסר לכם באפליקציה?"));
  t.appendChild(text("div", "share-sub",
    pollState().done ? "אמרתם כבר משהו. יש עוד? קדימה"
                     : "שלוש שאלות, פחות מדקה. זה מה שנבנה אחר כך"));
  c.appendChild(t);
  const b = el("button", "wa-btn", "לסקר");
  b.type = "button";
  b.onclick = openPoll;
  c.appendChild(b);
  return c;
}

/* ---------- news: headlines from the sports press ---------- */

// Headlines only, each one a link out to whoever published it. The text
// belongs to that outlet, the app quotes the headline, names the source
// and sends the reader there. Nothing is reproduced beyond the title.

function newsItems() {
  const n = state.news;
  return (n && Array.isArray(n.items)) ? n.items : [];
}

// "לפני שעתיים", "אתמול", "12.8", a fan reads freshness, not timestamps
function newsWhen(iso) {
  const t = new Date(iso).getTime();
  if (!t) return "";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 2) return "עכשיו";
  if (mins < 60) return "לפני " + mins + " דקות";
  const hours = Math.round(mins / 60);
  if (hours === 1) return "לפני שעה";
  if (hours === 2) return "לפני שעתיים";
  if (hours < 24) return "לפני " + hours + " שעות";
  const days = Math.round(hours / 24);
  if (days === 1) return "אתמול";
  if (days === 2) return "שלשום";
  if (days <= 6) return "לפני " + days + " ימים";
  // past a week a relative count stops meaning anything, but "4.8" can be
  // read as the fourth of August or the eighth of April, so name the month
  const d = new Date(t);
  return d.getDate() + " ב" + MONTHS_SHORT[d.getMonth()];
}

function newsItemEl(item) {
  const a = el("a", "news-item");
  a.href = item.url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  // a headline often carries a score, and a score in Hebrew prose flips
  a.appendChild(prose("div", "news-title", item.title));
  const meta = el("div", "news-meta");
  if (item.source) {
    meta.appendChild(text("span", "news-source" + (isLatin(item.source) ? " latin" : ""),
      item.source));
  }
  const when = newsWhen(item.published);
  if (when) {
    if (item.source) meta.appendChild(text("span", "dot", "·"));
    meta.appendChild(text("span", "", when));
  }
  a.appendChild(meta);
  return a;
}

function newsCard() {
  const items = newsItems();
  if (!items.length) return null;
  const c = el("div", "card news-card");
  c.appendChild(text("div", "eyebrow", "מה כותבים על הקבוצה"));
  items.slice(0, 3).forEach(i => c.appendChild(newsItemEl(i)));
  const more = el("a", "link-btn");
  more.href = "#/news";
  more.textContent = "לכל הכותרות";
  c.appendChild(more);
  return c;
}

function renderNews() {
  const items = newsItems();
  view.appendChild(text("div", "section-title", "מה כותבים על הקבוצה"));
  if (!items.length) {
    view.appendChild(el("div", "card")).appendChild(
      text("div", "empty", "עוד לא נאספו כותרות, נעדכן ברגע שיהיו"));
    footer();
    return;
  }
  const c = el("div", "card news-card");
  items.forEach(i => c.appendChild(newsItemEl(i)));
  view.appendChild(c);

  const outlets = [];
  items.forEach(i => { if (i.source && !outlets.includes(i.source)) outlets.push(i.source); });
  const note = el("div", "table-note");
  note.appendChild(document.createTextNode(
    "הכותרות " + prefixHe("מ", listHe(outlets)) +
    ". לחיצה על כותרת פותחת את הכתבה באתר שפרסם אותה, " +
    "והזכויות עליה שלו. האיסוף נעשה דרך חדשות Google, ואינו קשור למועדון."));
  view.appendChild(note);
  if (state.news && state.news.updated) {
    view.appendChild(text("div", "table-note", "נאסף " + newsWhen(state.news.updated)));
  }
  footer();
}

/* ---------- podcasts: what people are saying out loud ---------- */

// Same deal as the news section, and for the same reason. The episode
// belongs to whoever recorded it, so the app carries the title, the show
// and how long it runs, and sends the fan there to listen. No embedded
// player, no description, nothing lifted beyond the name of the episode.

const PODCASTS_KEY = "hapoel-podcasts-v1";
// how stale the list has to be before returning to the app refetches it
const PODCAST_STALE = 10 * 60 * 1000;
let podcastsFetched = Date.now();
// What was new when the fan walked into the screen. Held for the length of
// the visit, because opening the screen marks everything seen, and without
// this the marks would vanish the moment they switched tabs and looked back.
let podcastFresh = null;

function podcastItems() {
  const p = state.podcasts;
  return (p && Array.isArray(p.items)) ? p.items : [];
}

function podcastSeen() {
  try {
    const raw = JSON.parse(localStorage.getItem(PODCASTS_KEY));
    return (raw && raw.seen) ? new Date(raw.seen).getTime() : null;
  } catch (e) { return null; }
}

function savePodcastSeen(ms) {
  try {
    localStorage.setItem(PODCASTS_KEY,
      JSON.stringify({ seen: new Date(ms).toISOString() }));
  } catch (e) {}
}

// Episodes that dropped since the fan last opened the podcasts screen.
// On a first visit there is nothing to compare against, and marking the
// whole list as new would be a lie, so the clock simply starts now.
function newEpisodes() {
  const items = podcastItems();
  if (!items.length) return [];
  const seen = podcastSeen();
  if (seen === null) {
    savePodcastSeen(Date.now());
    return [];
  }
  return items.filter(i => new Date(i.published).getTime() > seen);
}

// "48 דקות", "שעה ו־12 דקות". An episode the feed gave no length for
// simply does not get the line.
function podcastLength(sec) {
  if (!sec || sec < 60) return "";
  const mins = Math.round(sec / 60);
  if (mins === 1) return "דקה";
  if (mins < 60) return mins + " דקות";
  const h = Math.floor(mins / 60), m = mins % 60;
  const hours = h === 1 ? "שעה" : h === 2 ? "שעתיים" : h + " שעות";
  if (!m) return hours;
  return hours + (m === 1 ? " ודקה" : " ו־" + m + " דקות");
}

// inGroup: the full screen already prints the show name above the rows,
// so repeating it under every title there is noise. The home card has no
// such heading and needs it.
function podcastItemEl(item, isNew, inGroup) {
  const a = el("a", "pod-item");
  a.href = item.url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  const head = el("div", "pod-head");
  // an episode name carries its number, and often a score from the game
  // it is about, and both flip inside an RTL line
  head.appendChild(prose("div", "pod-title", item.title));
  if (isNew) head.appendChild(text("span", "pod-new", "חדש"));
  a.appendChild(head);

  const meta = el("div", "pod-meta");
  if (item.show && !inGroup) {
    meta.appendChild(text("span", "pod-show" + (isLatin(item.show) ? " latin" : ""),
      item.show));
  }
  const len = podcastLength(item.duration);
  if (len) {
    if (meta.childNodes.length) meta.appendChild(text("span", "dot", "·"));
    meta.appendChild(text("span", "", len));
  }
  // the news section already turns a timestamp into what a fan actually
  // reads, and freshness means the same thing here
  const when = newsWhen(item.published);
  if (when) {
    if (meta.childNodes.length) meta.appendChild(text("span", "dot", "·"));
    meta.appendChild(text("span", "", when));
  }
  a.appendChild(meta);
  return a;
}

function podcastCard() {
  const items = podcastItems();
  if (!items.length) return null;
  const fresh = newEpisodes();
  if (!fresh.length) {
    const promo = el("a", "card promo");
    promo.href = "#/podcasts";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "🎧 פודקאסטים"));
    t.appendChild(text("div", "promo-sub",
      "מה מדברים על הפועל ועל הכדורסל הישראלי"));
    promo.appendChild(t);
    promo.appendChild(text("div", "chevron", "‹"));
    return promo;
  }
  const c = el("div", "card pod-card");
  c.appendChild(text("div", "eyebrow",
    fresh.length === 1 ? "פרק חדש" : fresh.length + " פרקים חדשים"));
  fresh.slice(0, 2).forEach(i => c.appendChild(podcastItemEl(i, true)));
  const more = el("a", "link-btn");
  more.href = "#/podcasts";
  more.textContent = "לכל הפודקאסטים";
  c.appendChild(more);
  return c;
}

function renderPodcasts() {
  const items = podcastItems();
  view.appendChild(text("div", "section-title", "פודקאסטים"));
  if (!items.length) {
    view.appendChild(el("div", "card")).appendChild(
      text("div", "empty", "עוד לא נאספו פרקים, נעדכן ברגע שיהיו"));
    footer();
    return;
  }

  // two kinds of show, and a fan looking for one is not looking for the
  // other: the ones about us, and the ones about the league as a whole
  const seg = el("div", "seg");
  const bUs = text("button", state.podcastsTab === "team" ? "active" : "", "על הפועל");
  const bAll = text("button", state.podcastsTab === "league" ? "active" : "", "כדורסל ישראלי");
  bUs.onclick = () => { state.podcastsTab = "team"; render(); };
  bAll.onclick = () => { state.podcastsTab = "league"; render(); };
  seg.appendChild(bUs);
  seg.appendChild(bAll);
  view.appendChild(seg);

  // work out what is new before the screen marks everything as seen
  if (!podcastFresh) {
    podcastFresh = new Set(newEpisodes().map(i => i.url));
    // seen means "you opened the screen", not "you scrolled past the card"
    const newest = items.reduce((max, i) => {
      const t = new Date(i.published).getTime();
      return t > max ? t : max;
    }, 0);
    if (newest) savePodcastSeen(newest);
  }
  const freshUrls = podcastFresh;

  const shows = (state.podcasts && state.podcasts.shows) || [];
  const shown = items.filter(i => i.about === state.podcastsTab);
  const order = [];
  shown.forEach(i => { if (!order.includes(i.showId)) order.push(i.showId); });

  if (!order.length) {
    view.appendChild(el("div", "card")).appendChild(text("div", "empty",
      state.podcastsTab === "team"
        ? "עוד לא נאספו פרקים על הפועל, נעדכן ברגע שיהיו"
        : "עוד לא נאספו פרקים על הכדורסל הישראלי, נעדכן ברגע שיהיו"));
  }

  order.forEach(id => {
    const mine = shown.filter(i => i.showId === id);
    if (!mine.length) return;
    const info = shows.find(s => s.id === id) || {};
    const c = el("div", "card pod-card");
    const head = el("div", "pod-group");
    head.appendChild(text("div", "pod-group-name" + (isLatin(mine[0].show) ? " latin" : ""),
      mine[0].show));
    c.appendChild(head);
    mine.forEach(i => c.appendChild(podcastItemEl(i, freshUrls.has(i.url), true)));
    if (info.url) {
      const all = el("a", "link-btn");
      all.href = info.url;
      all.target = "_blank";
      all.rel = "noopener noreferrer";
      all.textContent = "כל הפרקים של " + mine[0].show;
      c.appendChild(all);
    }
    view.appendChild(c);
  });

  const note = el("div", "table-note");
  note.appendChild(document.createTextNode(
    "כותרות הפרקים בלבד. לחיצה על פרק פותחת אותו אצל מי שהקליט, " +
    "והזכויות עליו שלו. אף אחת מהתוכניות אינה קשורה למועדון ולא לאפליקציה."));
  view.appendChild(note);
  if (state.podcasts && state.podcasts.updated) {
    view.appendChild(text("div", "table-note", "נאסף " + newsWhen(state.podcasts.updated)));
  }

  footer();
}

// A fan leaves the app open on the phone for days. Coming back to it should
// show what came out meanwhile, without a pull to refresh, so the list is
// refetched when the tab returns to the front and has gone stale.
function watchPodcasts() {
  document.addEventListener("visibilitychange", async () => {
    if (document.hidden) return;
    if (Date.now() - podcastsFetched < PODCAST_STALE) return;
    podcastsFetched = Date.now();
    let next;
    try {
      const res = await fetch("data/podcasts.json?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) return;
      next = await res.json();
    } catch (e) {
      return; // offline is not an error worth putting on the screen
    }
    if (JSON.stringify(next) === JSON.stringify(state.podcasts || null)) return;
    state.podcasts = next;
    const hash = location.hash || "#/";
    if (hash === "#/" || hash === "#/podcasts") render();
  });
}

function shareCard() {
  const c = el("div", "card share-card");
  const t = el("div");
  t.appendChild(text("div", "share-title", "מכירים אוהד שעוד לא ראה?"));
  t.appendChild(text("div", "share-sub", "שלחו לו את האפליקציה בוואטסאפ"));
  c.appendChild(t);
  const b = el("button", "wa-btn", "שיתוף");
  b.type = "button";
  b.onclick = shareApp;
  c.appendChild(b);
  return c;
}

/* ---------- the quick poll ---------- */

// Five questions, four of them taps, and the whole thing sends from inside
// the app: a fan on a phone should never be handed to a form on another
// site, and should never be asked to open an account to say something.
//
// The answers reach /api/feedback, a function that runs next to the app on
// the host and files each one on the project's issue tracker. When that
// endpoint is not configured the app falls back to the older destinations
// rather than showing a fan an error it caused itself.

const POLL_KEY = "hapoel-poll-v1";
const VISITS_KEY = "hapoel-visits-v1";

const POLL_FANS = [
  "מנוי לעונה",
  "בא מדי פעם לאולם",
  "צופה בשידורים",
  "עוקב מרחוק",
];

const POLL_WANTS = [
  "התראה לפני כל משחק",
  "תוצאה חיה",
  "חדשות על הקבוצה",
  "סטטיסטיקות מתקדמות",
  "שירי יציע",
  "נוסטלגיה והיסטוריה",
  "כרטיסים ומידע על האולם",
  "יומן אוהד אישי",
];

const POLL_WANTS_MAX = 3;

// Four possible destinations, first one configured wins. The endpoint is
// the only one that keeps the fan inside the app. A Google Form asks for no
// account but hands them to another site. WhatsApp is easy but publishes a
// phone number. A GitHub issue opened by hand needs no setup at all and
// works today, at the cost of asking for an account, so it is the floor.
function pollConfig() {
  const f = state.feedback || {};
  return (f.endpoint || f.formUrl || f.whatsapp || f.issueRepo) ? f : null;
}

function pollTarget() {
  const f = pollConfig();
  if (!f) return null;
  if (f.endpoint) return { kind: "endpoint", label: "התשובות הגיעו" };
  if (f.formUrl) return { kind: "form", label: "הטופס ייפתח בלשונית חדשה" };
  if (f.whatsapp) return { kind: "whatsapp", label: "ייפתח וואטסאפ עם התשובות מוכנות" };
  return { kind: "issue", label: "ייפתח גיטהאב. צריך חשבון, וזה חינם" };
}

function pollNote() {
  const t = pollTarget();
  if (!t) return "";
  if (t.kind === "endpoint") {
    // No address, and no promise the app cannot keep: the answers are kept
    // in the open, so the honest thing is to say so and to ask for nothing
    // that would identify anybody.
    return "השליחה נעשית מכאן, בלי חשבון ובלי לצאת מהאפליקציה. " +
           "מה שתכתבו נשמר אצלנו בארגז הפתוח של הפרויקט, אז אל תכתבו פרטים אישיים. " +
           "לא ביקשנו שם, טלפון או אימייל, ואין באפליקציה מעקב.";
  }
  if (t.kind === "form") {
    return "התשובות נשלחות לטופס של גוגל. אין חשבון, אין מעקב, " +
           "ושום דבר לא נשמר באפליקציה.";
  }
  if (t.kind === "whatsapp") {
    return "התשובות נפתחות כהודעת וואטסאפ מוכנה: אתם שולחים, אנחנו קוראים. " +
           "שום דבר לא נשמר באפליקציה.";
  }
  return "התשובות נפתחות ככרטיס פתוח בגיטהאב, במקום שבו הקוד של האפליקציה " +
         "נמצא. צריך חשבון גיטהאב. שום דבר לא נשמר באפליקציה.";
}

function pollState() {
  try { return JSON.parse(localStorage.getItem(POLL_KEY)) || {}; }
  catch (e) { return {}; }
}

function savePollState(s) {
  try { localStorage.setItem(POLL_KEY, JSON.stringify(s)); } catch (e) {}
}

// counted once per app start, so the poll waits for a fan who came back
function countVisit() {
  try {
    const n = (parseInt(localStorage.getItem(VISITS_KEY), 10) || 0) + 1;
    localStorage.setItem(VISITS_KEY, String(n));
    return n;
  } catch (e) { return 1; }
}

function shouldAskPoll(visits) {
  const cfg = pollConfig();
  if (!cfg || window.__HAPOEL_SNAPSHOT__) return false;
  const s = pollState();
  if (s.done) return false;
  if (visits < (cfg.afterVisits || 3)) return false;
  if (s.snoozedAt) {
    const days = (Date.now() - new Date(s.snoozedAt).getTime()) / 86400000;
    if (days < (cfg.snoozeDays || 30)) return false;
  }
  return true;
}

/* When it is fair to ask.
 *
 * A returning visit is not the same as having seen the app. Asking after
 * a couple of seconds on the home screen is asking someone what they think
 * of a book they have not opened: the answer is worthless, and being
 * interrupted that early is the reason people close things.
 *
 * So three gates, all of which must be passed, and none of which can be
 * passed by sitting still:
 *   · the fan came back              (afterVisits app openings)
 *   · they actually looked around    (afterScreens *different* screens)
 *   · they stayed a while            (afterSeconds in the app, this visit)
 *
 * A live game overrides all of it: nobody is answering a questionnaire
 * while the score is moving.
 */

const seenScreens = new Set();
let sessionStart = Date.now();
let pollAsked = false;
let pollWatch = null;

function pollGate() {
  const cfg = pollConfig() || {};
  return {
    screens: cfg.afterScreens || 4,
    seconds: cfg.afterSeconds || 90,
  };
}

// counted from render(), so it measures screens opened rather than taps
function noteScreen(hash) {
  seenScreens.add(hash);
}

function browsedEnough() {
  const g = pollGate();
  return seenScreens.size >= g.screens &&
    (Date.now() - sessionStart) / 1000 >= g.seconds;
}

function pollWhenQuiet(visits) {
  if (!shouldAskPoll(visits)) return;
  if (pollWatch) clearInterval(pollWatch);
  pollWatch = setInterval(() => {
    // the state can change under us: a snooze, an answer, a game starting
    if (pollAsked || !shouldAskPoll(visits)) return stopPollWatch();
    if (state.live || pollSheet || !browsedEnough()) return;
    stopPollWatch();
    pollAsked = true;
    openPoll();
  }, 5000);
}

function stopPollWatch() {
  if (pollWatch) clearInterval(pollWatch);
  pollWatch = null;
}

function answerFilled(a) {
  return !!(a.fan || (a.wants && a.wants.length) || a.rating || a.idea || a.bug);
}

// a value that can go in a URL or a line of text, the multi-answer question
// is the only one that is not already a string
function answerValue(a, key) {
  const v = a[key];
  return Array.isArray(v) ? v.join(", ") : (v || "");
}

// the message a human reads, when the destination is not the endpoint
function answersAsText(a) {
  const lines = ["משוב על ״יושב סופר את הדקות״", ""];
  if (a.fan) lines.push("איזה אוהד: " + a.fan);
  if (a.wants && a.wants.length) lines.push("הכי יעזור: " + a.wants.join(", "));
  if (a.rating) lines.push("שימושיות: " + a.rating + " מתוך 5");
  if (a.idea) lines.push("", "מה להוסיף או לשנות:", a.idea);
  if (a.bug) lines.push("", "מה לא עבד:", a.bug);
  return lines.join("\n");
}

// The endpoint answers 501 while it has no token, and any network at all can
// fail, either way the fan's words are not thrown away: the older
// destination opens with everything they typed already in it.
function sendToEndpoint(a) {
  const cfg = pollConfig();
  return fetch(cfg.endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fan: a.fan, wants: a.wants, rating: a.rating,
      idea: a.idea, bug: a.bug, nickname: a.nickname || "",
    }),
  }).then(res => res.ok);
}

function fallbackUrl(a) {
  const cfg = pollConfig();
  if (cfg.formUrl) return prefilledFormUrl(a);
  if (cfg.whatsapp) {
    return "https://wa.me/" + String(cfg.whatsapp).replace(/[^0-9]/g, "") +
      "?text=" + encodeURIComponent(answersAsText(a));
  }
  if (cfg.issueRepo) {
    const first = (a.idea || a.bug || "").split("\n")[0].trim();
    const title = "משוב מאוהד" + (first ? ": " + first.slice(0, 70)
      : (a.wants && a.wants.length ? ": " + a.wants[0] : ""));
    return "https://github.com/" + cfg.issueRepo + "/issues/new?title=" +
      encodeURIComponent(title) + "&body=" + encodeURIComponent(answersAsText(a));
  }
  return null;
}

// what to promise a fan once the endpoint has already declined, the
// endpoint's own "התשובות הגיעו" would be a lie on this path
function fallbackLabel() {
  const cfg = pollConfig() || {};
  if (cfg.formUrl) return "הטופס נפתח בלשונית חדשה";
  if (cfg.whatsapp) return "וואטסאפ נפתח עם התשובות";
  if (cfg.issueRepo) return "נפתח כרטיס בגיטהאב. צריך חשבון, וזה חינם";
  return "";
}

function prefilledFormUrl(a) {
  const cfg = pollConfig();
  const base = cfg.formUrl.split("?")[0];
  const f = cfg.fields || {};
  const parts = ["usp=pp_url"];
  Object.keys(f).forEach(k => {
    const id = f[k];
    const v = answerValue(a, k);
    // an unmapped field is left for the fan to fill in the form itself
    if (id && v) parts.push(encodeURIComponent(id) + "=" + encodeURIComponent(v));
  });
  return base + "?" + parts.join("&");
}

let pollSheet = null;

function closePoll() {
  if (!pollSheet) return;
  document.removeEventListener("keydown", pollKeys);
  document.body.classList.remove("sheet-open");
  pollSheet.remove();
  pollSheet = null;
}

function pollKeys(e) {
  if (e.key === "Escape") { snoozePoll(); }
}

function snoozePoll() {
  const s = pollState();
  s.snoozedAt = new Date().toISOString();
  savePollState(s);
  closePoll();
}

// one question, one row of taps, single choice or up to `max` of them
function pollChips(list, onPick, max) {
  const box = el("div", "poll-chips");
  const chosen = [];
  list.forEach(w => {
    const b = el("button", "poll-chip", w);
    b.type = "button";
    b.setAttribute("aria-pressed", "false");
    b.onclick = () => {
      const at = chosen.indexOf(w);
      if (at >= 0) chosen.splice(at, 1);
      else if (max === 1) { chosen.length = 0; chosen.push(w); }
      else if (chosen.length < max) chosen.push(w);
      else return toast("אפשר לבחור עד " + max);
      box.querySelectorAll(".poll-chip").forEach(o => {
        const on = chosen.indexOf(o.textContent) >= 0;
        o.classList.toggle("on", on);
        o.setAttribute("aria-pressed", on ? "true" : "false");
      });
      onPick(chosen.slice());
    };
    box.appendChild(b);
  });
  return box;
}

function pollTextarea(placeholder, onInput) {
  const ta = el("textarea", "poll-text");
  ta.rows = 2;
  ta.placeholder = placeholder;
  ta.oninput = () => onInput(ta.value.slice(0, 900));
  return ta;
}

function openPoll() {
  if (pollSheet || !pollConfig()) return;
  const answers = { fan: "", wants: [], rating: "", idea: "", bug: "", nickname: "" };

  const wrap = el("div", "sheet-wrap");
  const sheet = el("div", "sheet");
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-modal", "true");
  sheet.setAttribute("aria-labelledby", "pollTitle");

  const head = el("div", "sheet-head");
  const h = text("div", "sheet-title", "רגע, מה דעתכם?");
  h.id = "pollTitle";
  head.appendChild(h);
  const x = el("button", "sheet-x", "×");
  x.type = "button";
  x.setAttribute("aria-label", "סגירה");
  x.onclick = snoozePoll;
  head.appendChild(x);
  sheet.appendChild(head);

  sheet.appendChild(text("div", "sheet-sub",
    "חמש שאלות, רובן בלחיצה. זה מה שיקבע מה נבנה אחר כך."));

  // 1, who is answering, so the wishes can be read by kind of fan
  sheet.appendChild(text("div", "poll-q", "איזה אוהד אתם?"));
  sheet.appendChild(pollChips(POLL_FANS, v => { answers.fan = v[0] || ""; }, 1));

  // 2, the roadmap question, and the one worth several answers
  sheet.appendChild(text("div", "poll-q", "מה הכי יעזור לכם באפליקציה?"));
  sheet.appendChild(text("div", "poll-hint", "עד " + POLL_WANTS_MAX + " בחירות"));
  sheet.appendChild(pollChips(POLL_WANTS, v => { answers.wants = v; }, POLL_WANTS_MAX));

  // 3, usefulness, not a beauty contest
  sheet.appendChild(text("div", "poll-q", "כמה האפליקציה שימושית לכם היום?"));
  const scale = el("div", "poll-scale");
  [1, 2, 3, 4, 5].forEach(n => {
    const b = el("button", "poll-star", String(n));
    b.type = "button";
    b.setAttribute("aria-label", n + " מתוך 5");
    b.onclick = () => {
      answers.rating = String(n);
      scale.querySelectorAll(".poll-star").forEach(o =>
        o.classList.toggle("on", parseInt(o.textContent, 10) <= n));
    };
    scale.appendChild(b);
  });
  const ends = el("div", "poll-ends");
  ends.appendChild(text("span", null, "בכלל לא"));
  ends.appendChild(text("span", null, "לא מוותר עליה"));
  sheet.appendChild(scale);
  sheet.appendChild(ends);

  // 4 and 5, the two that cannot be guessed from a list
  sheet.appendChild(text("div", "poll-q", "מה הייתם מוסיפים או משנים?"));
  sheet.appendChild(pollTextarea("במילים שלכם. קוראים הכול",
    v => { answers.idea = v; }));

  sheet.appendChild(text("div", "poll-q", "משהו לא עבד או לא היה ברור?"));
  sheet.appendChild(pollTextarea("מה קרה, ובאיזה מסך", v => { answers.bug = v; }));

  // the honeypot: off screen, never focusable, and only a bot fills it
  const trap = el("input", "poll-trap");
  trap.type = "text";
  trap.tabIndex = -1;
  trap.setAttribute("autocomplete", "off");
  trap.setAttribute("aria-hidden", "true");
  trap.oninput = () => { answers.nickname = trap.value; };
  sheet.appendChild(trap);

  const send = el("button", "wa-btn poll-send", "שליחה");
  send.type = "button";
  send.onclick = () => {
    if (!answerFilled(answers)) return toast("ענו על משהו אחד לפחות");
    const cfg = pollConfig();
    const done = () => {
      const s = pollState();
      s.done = true;
      savePollState(s);
      closePoll();
    };
    // The endpoint sends from here. A fallback exists only if one is
    // configured, and none is, deliberately: the fan was promised the
    // answers stay private, and every other destination is public or
    // exposes a phone number. With nowhere private to send, the honest
    // move is to say so and keep their words on the screen.
    const away = () => {
      const url = fallbackUrl(answers);
      if (!url) {
        send.disabled = false;
        send.textContent = "שליחה";
        return toast("לא הצלחנו לשלוח כרגע. מה שכתבתם עדיין כאן. נסו שוב עוד רגע");
      }
      window.open(url, "_blank", "noopener");
      done();
      const label = fallbackLabel();
      toast(label ? "תודה! " + label : "תודה!");
    };
    if (!cfg.endpoint) return away();
    send.disabled = true;
    send.textContent = "שולח…";
    sendToEndpoint(answers).then(ok => {
      if (ok) { done(); toast("תודה! התשובות הגיעו"); }
      else away();
    }).catch(away);
  };
  sheet.appendChild(send);

  const later = el("button", "poll-later", "לא עכשיו");
  later.type = "button";
  later.onclick = snoozePoll;
  sheet.appendChild(later);

  sheet.appendChild(text("div", "poll-note", pollNote()));

  wrap.appendChild(sheet);
  wrap.onclick = e => { if (e.target === wrap) snoozePoll(); };
  document.body.appendChild(wrap);
  pollSheet = wrap;
  document.addEventListener("keydown", pollKeys);
  document.body.classList.add("sheet-open");
  // focus the dialog itself, not the send button: a focus ring on the primary
  // action reads as though an answer has already been chosen
  sheet.tabIndex = -1;
  sheet.focus();
}

function toast(msg) {
  const t = text("div", "toast", msg);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

/* ---------- home ---------- */

function renderHome() {
  const next = upcoming()[0];
  const last = finished()[0];

  // a game in progress outranks everything else on the screen
  if (state.live) view.appendChild(liveCard(state.live));

  if (next && !state.live) {
    const c = el("div", "card next-game");
    c.appendChild(text("div", "eyebrow", "המשחק הבא"));
    c.appendChild(oppEl("opponent", opponent(next)));
    c.appendChild(text("div", "comp", next.competition + (next.round ? " · " + next.round : "")));
    const when = el("div", "when");
    const d = new Date(next.date);
    when.appendChild(text("span", "", fmtFull.format(d)));
    when.appendChild(text("span", "time", fmtTime.format(d)));
    c.appendChild(when);
    c.appendChild(countdownEl(next));
    const meta = el("div", "meta-row");
    meta.appendChild(text("span",
      "badge" + (isHome(next) && !isDisplacedHome(next) ? " home" : "") +
      (isDisplacedHome(next) ? " away-home" : ""),
      homeAwayLabel(next, true)));
    if (next.venue) meta.appendChild(text("span", "badge", venueLabel(next.venue)));
    if (next.note) meta.appendChild(proseInto(text("span", "badge note", ""), next.note));
    c.appendChild(meta);
    c.appendChild(calButton([next], "הוספה ליומן", "hapoel-next-game.ics"));
    c.appendChild(calNote());
    view.appendChild(c);
  } else if (!next) {
    const c = el("div", "card");
    c.appendChild(text("div", "eyebrow", "המשחק הבא"));
    c.appendChild(text("div", "empty", "לוח המשחקים לעונה טרם פורסם, נעדכן ברגע שיהיה"));
    view.appendChild(c);
  }

  if (last) {
    const c = el("div", "card");
    c.appendChild(text("div", "eyebrow", "התוצאה האחרונה"));
    const line = el("div", "result-line");
    const right = el("div");
    right.appendChild(oppEl("teams", opponent(last)));
    right.appendChild(text("div", "sub", last.competition + " · " + fmtFull.format(new Date(last.date))));
    line.appendChild(right);
    const left = el("div");
    left.style.textAlign = "center";
    const sc = text("div", "score", ourScore(last) + "-" + theirScore(last));
    left.appendChild(sc);
    left.appendChild(text("span", "chip " + (won(last) ? "win" : "loss"), won(last) ? "ניצחון" : "הפסד"));
    line.appendChild(left);
    c.appendChild(line);
    view.appendChild(c);
  }

  const nc = newsCard();
  if (nc) view.appendChild(nc);

  const pc = podcastCard();
  if (pc) view.appendChild(pc);

  const rows = state.standings.rows;
  if (rows && rows.length && seasonStarted(rows)) {
    view.appendChild(text("div", "section-title", "טבלת " + state.standings.competition));
    const c = el("div", "card table-card");
    const usIdx = rows.findIndex(r => isUs(r.team));
    let slice;
    if (usIdx < 0) slice = rows.slice(0, 4);
    else {
      const start = Math.max(0, Math.min(usIdx - 1, rows.length - 4));
      slice = rows.slice(start, start + 4);
    }
    c.appendChild(standingsTable(slice, false));
    const more = el("a", "link-btn");
    more.href = "#/table";
    more.textContent = "לטבלה המלאה";
    c.appendChild(more);
    view.appendChild(c);
  } else if (rows && rows.length) {
    // no games yet: a four‑team window around our position would be showing
    // last season's neighbours as if they were this season's
    const c = el("a", "card promo");
    c.href = "#/table";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "הליגה העונה"));
    t.appendChild(text("div", "promo-sub",
      rows.length + " קבוצות ב" + state.standings.competition +
      ". הטבלה תיפתח עם המשחק הראשון."));
    c.appendChild(t);
    c.appendChild(text("div", "chevron", "‹"));
    view.appendChild(c);
  }

  if (state.history) {
    const promo = el("a", "card promo");
    promo.href = "#/history";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "היסטוריה ומורשת"));
    t.appendChild(text("div", "promo-sub", "ארון התארים, הרגעים הגדולים ופינת כוכבי העבר"));
    promo.appendChild(t);
    promo.appendChild(text("div", "chevron", "‹"));
    view.appendChild(promo);
  }

  if (state.hof) {
    const promo = el("a", "card promo hof-promo");
    promo.href = "#/hof";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "🦁 אולם התהילה"));
    t.appendChild(text("div", "promo-sub",
      (state.hof.israelis || []).length + " ישראלים ו־" +
      (state.hof.foreigners || []).length + " זרים שהמועדון זוכר בשמם"));
    promo.appendChild(t);
    promo.appendChild(text("div", "chevron", "‹"));
    view.appendChild(promo);
  }

  if (state.lastSeason || state.seasonStats) {
    const promo = el("a", "card promo");
    promo.href = "#/stats";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "סטטיסטיקה"));
    t.appendChild(text("div", "promo-sub", "העונה הזו, והמאזן המלא של העונה שעברה"));
    promo.appendChild(t);
    promo.appendChild(text("div", "chevron", "‹"));
    view.appendChild(promo);
  }

  const ic = installCard();
  if (ic) view.appendChild(ic);
  const fc = feedbackCard();
  if (fc) view.appendChild(fc);
  view.appendChild(shareCard());
  footer();
}

/* ---------- games ---------- */

function renderGames() {
  const seg = el("div", "seg");
  const bUp = text("button", state.gamesTab === "upcoming" ? "active" : "", "המשחקים הקרובים");
  const bRes = text("button", state.gamesTab === "results" ? "active" : "", "תוצאות");
  bUp.onclick = () => { state.gamesTab = "upcoming"; render(); };
  bRes.onclick = () => { state.gamesTab = "results"; render(); };
  seg.appendChild(bUp);
  seg.appendChild(bRes);
  view.appendChild(seg);

  const list = state.gamesTab === "upcoming" ? upcoming() : finished();
  if (!list.length) {
    view.appendChild(text("div", "empty", state.gamesTab === "upcoming"
      ? "אין משחקים קרובים בלוח, נעדכן ברגע שיהיו"
      : "עוד לא נרשמו תוצאות העונה"));
    footer();
    return;
  }

  // 16 fixtures in a season is not a season, say why rather than let the
  // list look like the whole story
  if (state.gamesTab === "upcoming" && state.games.league &&
      state.games.league.published === false) {
    const n = el("div", "card notice");
    n.appendChild(text("div", "notice-title", "לוח הליגה עדיין לא פורסם"));
    n.appendChild(text("div", "notice-body",
      "מה שמופיע כאן הוא הגביע והיורוקאפ. ברגע שליגת ווינר סל תפרסם את " +
      "לוח המשחקים, הוא ייכנס לכאן מעצמו."));
    view.appendChild(n);
  }

  // a fan who reads "בית" and books nothing is fine; one who reads it and
  // drives to מלחה is not
  const note = state.venues && state.venues.awayNote;
  if (state.gamesTab === "upcoming" && note &&
      upcoming().some(isDisplacedHome)) {
    const n = el("div", "card notice");
    n.appendChild(text("div", "notice-title", "משחקי הבית באירופה: בבלגרד"));
    n.appendChild(prose("div", "notice-body", note));
    view.appendChild(n);
  }

  if (state.gamesTab === "upcoming") {
    const c = el("div", "card cal-card");
    c.appendChild(text("div", "share-title", "כל המשחקים ביומן שלך"));
    c.appendChild(text("div", "share-sub",
      list.length + " משחקים, עם תזכורת שעתיים לפני כל אחד"));
    c.appendChild(calButton(list, "הוספה ליומן", "hapoel-season.ics"));
    c.appendChild(calNote());
    view.appendChild(c);
  }

  let lastMonth = -1;
  list.forEach(g => {
    const d = new Date(g.date);
    const mKey = d.getFullYear() * 12 + d.getMonth();
    if (mKey !== lastMonth) {
      lastMonth = mKey;
      view.appendChild(text("div", "month-label",
        new Intl.DateTimeFormat("he-IL", { month: "long", year: "numeric" }).format(d)));
    }
    view.appendChild(gameRow(g));
  });
  footer();
}


/* ---------- where a game is actually played ---------- */

// European "home" games are staged in Belgrade by decision of Euroleague
// Basketball. They count as home in the table, which is why the feed marks
// them that way, but a fan reading "בית" packs for Malha, and the game is
// 1,500 km away. Wherever a home game is not at our own arena, say the city.

function venueInfo(name) {
  const v = (state.venues && state.venues.venues) || {};
  return v[name] || null;
}

function venueLabel(name) {
  if (!name) return "";
  const v = venueInfo(name);
  return v ? v.he : name;
}

function isOurArena(name) {
  if (!name) return true;              // nothing said, assume the usual place
  const home = (state.venues && state.venues.homeArena) || [];
  return home.some(h => h.toLowerCase() === String(name).toLowerCase());
}

// "בית", or "בית בבלגרד" when home is somewhere else entirely
function homeAwayLabel(g, long) {
  if (!isHome(g)) return long ? "משחק חוץ" : "חוץ";
  if (isOurArena(g.venue)) return long ? "משחק בית" : "בית";
  const v = venueInfo(g.venue);
  const city = v && v.city;
  return (long ? "משחק בית" : "בית") + (city ? " ב" + city : " מחוץ לישראל");
}

function isDisplacedHome(g) {
  return isHome(g) && !isOurArena(g.venue);
}

function gameRow(g) {
  const wrap = el("div", "game-card");
  const row = el("div", "game-row");
  const d = new Date(g.date);

  const date = el("div", "date-block");
  date.appendChild(text("div", "d", String(d.getDate())));
  date.appendChild(text("div", "m", MONTHS_SHORT[d.getMonth()]));
  row.appendChild(date);

  const info = el("div", "info");
  info.appendChild(oppEl("opp", opponent(g)));
  const sub = el("div", "sub");
  sub.appendChild(document.createTextNode(g.competition + " · "));
  sub.appendChild(text("span", isDisplacedHome(g) ? "away-home" : "",
    homeAwayLabel(g, false)));
  if (g.venue) sub.appendChild(document.createTextNode(" · " + venueLabel(g.venue)));
  info.appendChild(sub);
  // מה שהמועדון עצמו פרסם על המשחק, למשל ״עם קהל״ או יריבה שטרם נקבעה.
  // אוהד שמתכנן להגיע צריך לדעת את זה לפני שהוא יוצא מהבית.
  if (g.note) info.appendChild(proseInto(text("div", "game-note", ""), g.note));
  row.appendChild(info);

  const end = el("div", "end");
  if (g.status === "finished") {
    end.appendChild(text("div", "t score", ourScore(g) + "-" + theirScore(g)));
    end.appendChild(text("span", "chip " + (won(g) ? "win" : "loss"), won(g) ? "נ׳" : "ה׳"));
  } else {
    end.appendChild(text("div", "t", fmtTime.format(d)));
  }
  row.appendChild(end);
  wrap.appendChild(row);
  wrap.appendChild(attendButton(g));
  return wrap;
}

function attendButton(g) {
  const past = g.status === "finished";
  const b = el("button", "attend");
  b.type = "button";
  const paint = () => {
    const on = attended(g.id);
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
    b.textContent = on
      ? (past ? "✓ הייתי שם" : "✓ אני מגיע")
      : (past ? "הייתי שם" : "אני מגיע");
  };
  paint();
  b.onclick = () => { toggleAttend(g); paint(); };
  return b;
}

/* ---------- table ---------- */

function renderTable() {
  const euro = state.eurocup;
  if (euro && euro.groups && euro.groups.length) {
    const seg = el("div", "seg");
    const bL = text("button", state.tableTab === "euro" ? "" : "active", "ווינר סל");
    const bE = text("button", state.tableTab === "euro" ? "active" : "", "יורוקאפ");
    bL.onclick = () => { state.tableTab = "league"; render(); };
    bE.onclick = () => { state.tableTab = "euro"; render(); };
    seg.appendChild(bL);
    seg.appendChild(bE);
    view.appendChild(seg);
  }

  if (state.tableTab === "euro" && euro) {
    renderEurocup(euro);
  } else {
    const started = seasonStarted(state.standings.rows);
    view.appendChild(text("div", "section-title",
      (started ? "טבלת " : "קבוצות ") + state.standings.competition +
      " · עונת " + state.standings.season));
    const c = el("div", "card table-card");
    c.appendChild(standingsTable(state.standings.rows, true));
    view.appendChild(c);
    if (!started) {
      view.appendChild(text("div", "table-note",
        "העונה טרם החלה. אלה הקבוצות שמשחקות השנה, לא דירוג. " +
        "הטבלה תסתדר מעצמה עם המשחק הראשון."));
    }
  }
  footer();
}

// "Group A" is how the competition names it; in Hebrew a group is בית
function groupLabel(name) {
  const m = /^group\s+(\S+)$/i.exec(name || "");
  return m ? "בית " + m[1] : (name || "");
}

function renderEurocup(euro) {
  const ourFirst = euro.groups;
  const ours = ourFirst[0];
  const euroStarted = seasonStarted(ours.rows);
  view.appendChild(text("div", "section-title",
    groupLabel(ours.name) + " · " + euro.competition + " " + euro.season +
    (euroStarted ? "" : " · ההגרלה")));
  const c = el("div", "card table-card");
  c.appendChild(eurocupTable(ours.rows));
  view.appendChild(c);

  const rest = ourFirst.slice(1);
  if (rest.length) {
    const d = el("details", "card groups-more");
    const s = el("summary");
    s.textContent = "שאר הבתים";
    d.appendChild(s);
    rest.forEach(g => {
      d.appendChild(text("div", "group-name", groupLabel(g.name)));
      d.appendChild(eurocupTable(g.rows));
    });
    view.appendChild(d);
  }
  view.appendChild(text("div", "table-note", euroStarted
    ? "הטבלה נקבעת לפי ניצחונות; בשוויון מכריעים המפגשים הישירים והפרש הנקודות."
    : "אלה הקבוצות שהוגרלו לבית, לפי סדר האלף־בית. עוד לא שוחק אף משחק. " +
      "הטבלה נקבעת לפי ניצחונות; בשוויון מכריעים המפגשים הישירים והפרש הנקודות."));
}

function isUsEuro(r) { return r.code === "JER" || isUs(teamName(r.team)); }

function eurocupTable(rows) {
  // same as the league table: before the first tip-off these are the eight
  // clubs drawn into the group, not an order any of them earned
  const started = seasonStarted(rows);
  const t = el("table", "standings");
  const head = el("tr");
  [started ? "#" : "", "קבוצה", "מש׳", "נצ׳", "הפ׳", "הפרש"].forEach((h, i) => {
    const th = el("th", i === 1 ? "team" : "");
    th.textContent = h;
    head.appendChild(th);
  });
  t.appendChild(head);
  rows.forEach(r => {
    const tr = el("tr", isUsEuro(r) ? "us" : "");
    tr.appendChild(text("td", "num",
      !started ? "·" : (r.pos == null ? "-" : String(r.pos))));
    const name = teamName(r.team);
    const td = el("td", "team");
    td.appendChild(text("span", isLatin(name) ? "latin" : "", name));
    tr.appendChild(td);
    tr.appendChild(text("td", "num", String(r.played ?? 0)));
    tr.appendChild(text("td", "num", String(r.wins ?? 0)));
    tr.appendChild(text("td", "num", String(r.losses ?? 0)));
    const diff = (r.for ?? 0) - (r.against ?? 0);
    tr.appendChild(text("td", "num diff", diff > 0 ? "+" + diff : String(diff)));
    t.appendChild(tr);
  });
  return t;
}

// Before a ball is thrown the feed still hands back a full table: every team
// at 0‑0, numbered 1 to 14, in last season's finishing order. Rendered as a
// table that reads as a standing, a fan sees "3 הפועל י־ם" and believes it.
// It is last year's position wearing this year's clothes, so the position
// column is dropped until somebody has actually played.
function seasonStarted(rows) {
  return (rows || []).some(r => (r.played || 0) > 0);
}

function standingsTable(rows, full) {
  const hasPoints = rows.some(r => r.points !== undefined);
  const started = seasonStarted(rows);
  const t = el("table", "standings");
  const head = el("tr");
  const cols = [started ? "#" : "", "קבוצה", "מש׳", "נצ׳", "הפ׳"]
    .concat(hasPoints ? ["נק׳"] : []);
  cols.forEach((h, i) => {
    const th = el("th", i === 1 ? "team" : "");
    th.textContent = h;
    head.appendChild(th);
  });
  t.appendChild(head);
  rows.forEach(r => {
    const tr = el("tr", isUs(r.team) ? "us" : "");
    tr.appendChild(text("td", "num", started ? String(r.pos) : "·"));
    tr.appendChild(text("td", "team", r.team));
    tr.appendChild(text("td", "num", String(r.played)));
    tr.appendChild(text("td", "num", String(r.wins)));
    tr.appendChild(text("td", "num", String(r.losses)));
    if (hasPoints) tr.appendChild(text("td", "num", r.points !== undefined ? String(r.points) : "-"));
    t.appendChild(tr);
  });
  return t;
}

// Most photos come from the EuroCup feed, but a player the feed has no person
// record for is filled in by hand from another source. Naming only the feed
// would credit it for pictures that are not its, so list what is actually here.
function photoCredit() {
  const players = (state.roster && state.roster.players) || [];
  const shown = players.filter(p => p.photo);
  if (!shown.length) return null;
  const others = [];
  shown.forEach(p => {
    if (p.photoCredit && !others.includes(p.photoCredit)) others.push(p.photoCredit);
  });
  const from = shown.some(p => !p.photoCredit)
    ? ["הפיד הרשמי של היורוקאפ"].concat(others)
    : others;
  return text("div", "table-note",
    "תמונות השחקנים מ" + listHe(from) +
    ". שחקן בלי תמונה מוצג בראשי תיבות.");
}

// "א", "א וב", "א, ב וג", the vav attaches straight to a Hebrew word, and
// takes a maqaf only before a Latin word or a digit
function listHe(items) {
  if (items.length <= 1) return items[0] || "";
  const last = items[items.length - 1];
  // the vav attaches straight to a Hebrew word, except to one that already
  // opens with a vav, where "ווואלה ספורט" would grow a third vav
  const vav = (/^[֐-׿]/.test(last) && !/^ו/.test(last)) ? "ו" : "ו־";
  return items.slice(0, -1).join(", ") + " " + vav + last;
}

// the same rule for a prefix letter: "מספורט 5", but "מ־ONE"
function prefixHe(letter, word) {
  return letter + (/^[֐-׿]/.test(word) ? "" : "־") + word;
}

/* ---------- roster ---------- */

function renderRoster() {
  const r = state.roster || {};
  const players = r.players || [];
  view.appendChild(text("div", "section-title",
    "הסגל" + (r.season ? " · עונת " + r.season : "")));

  if (!players.length) {
    const c = el("div", "card");
    c.appendChild(text("div", "empty", "הסגל טרם פורסם, נעדכן ברגע שיהיה"));
    view.appendChild(c);
    footer();
    return;
  }

  // gateway into the "get to know the squad" profiles
  if (Object.keys(state.profiles || {}).length > 1) {
    const promo = el("a", "card promo");
    promo.href = "#/meet";
    const t = el("div");
    t.appendChild(text("div", "promo-title", "בואו נכיר את הסגל"));
    t.appendChild(text("div", "promo-sub", "מי הם החבר׳ה האלה? פרופיל לכל שחקן"));
    promo.appendChild(t);
    promo.appendChild(text("div", "chevron", "‹"));
    view.appendChild(promo);
  }

  const sorted = [...players].sort((a, b) => {
    if (a.number != null && b.number != null) return a.number - b.number;
    if (a.number != null) return -1;
    if (b.number != null) return 1;
    return a.name.localeCompare(b.name, "he");
  });

  sorted.forEach(p => {
    const row = el("a", "player-row");
    row.href = "#/player/" + encodeURIComponent(p.slug || slugOf(p));
    const num = el("div", "shirt");
    num.textContent = p.number != null ? p.number : "-";
    row.appendChild(num);
    row.appendChild(playerAvatar(p, "thumb"));
    const info = el("div", "info");
    info.appendChild(playerNameEl(p));
    // keep the list line short, the birth year lives on the player page
    const bits = [];
    if (p.position) bits.push(p.position);
    if (p.height) bits.push(p.height + " ס״מ");
    if (bits.length) info.appendChild(text("div", "sub", bits.join(" · ")));
    row.appendChild(info);
    row.appendChild(text("div", "chevron", "‹"));
    view.appendChild(row);
  });
  const cr = photoCredit();
  if (cr) view.appendChild(cr);
  footer();
}

// Mirrors slugify() in scripts/update_data.py, and has to keep mirroring it:
// the collector writes p.slug, this is only the fallback when it is missing.
// A name written in Hebrew has no Latin letters, so stripping to [a-z0-9]
// left every Israeli in the squad with the same empty slug, and the roster
// page sent all of them to whichever one came first.
function slugOf(p) {
  const s = (p.name || "").trim().toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  if (s) return s;
  return p.clubId ? "p-" + p.clubId : "";
}

// Hebrew name when we have one; otherwise the Latin name, isolated so it
// keeps its own direction inside the RTL layout
// order of preference: the hand-kept transliteration file, then the Hebrew
// name the club itself publishes, then whatever the European feed calls them
function playerName(p) {
  return (state.playerNames || {})[p.name] || p.nameHe || p.name;
}
function playerNameEl(p, cls) {
  const he = (state.playerNames || {})[p.name] || p.nameHe;
  return text("div", (cls || "opp") + (he ? "" : " latin"), he || p.name);
}

// The EuroCup feed carries no player images, and press photos are not ours
// to publish. So when there is no photo, draw something deliberate rather
// than leave a hole: initials on a tint of the club's own palette.
const AVATAR_HUES = [348, 3, 18, 335, 356, 12];

// Given name then surname, in that order. Kept in logical order so Hebrew
// initials read right-to-left and Latin ones left-to-right, each correctly.
function initialsOf(p) {
  const name = (playerName(p) || "").replace(/,/g, " ");
  const parts = name.split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  // ג׳ and צ׳ are one sound, keep the geresh with its letter
  const head = w => (/^[א-ת][׳']/.test(w) ? w.slice(0, 2) : w[0]);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (head(parts[0]) + head(parts[1])).toUpperCase();
}

function playerAvatar(p, cls) {
  if (p.photo) return playerPhoto(p, cls);
  return initialsAvatar(p, cls);
}

function initialsAvatar(p, cls) {
  const d = el("div", "player-photo avatar " + (cls || ""));
  const key = (p.name || "") + (p.number ?? "");
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  d.style.setProperty("--h", String(AVATAR_HUES[h % AVATAR_HUES.length]));
  d.textContent = initialsOf(p);
  d.setAttribute("aria-hidden", "true"); // the name is right next to it
  return d;
}

function playerPhoto(p, cls) {
  const img = document.createElement("img");
  img.className = "player-photo " + (cls || "");
  img.src = p.photo;
  img.alt = playerName(p);
  img.loading = "lazy";
  // a missing file should leave initials behind, not a hole in the layout
  img.onerror = () => {
    const fallback = initialsAvatar(p, cls);
    if (img.parentNode) img.parentNode.replaceChild(fallback, img);
  };
  return img;
}

/* ---------- player attributes, shown as bars ---------- */

function detailsOf(p) {
  const src = state.details || {};
  if (src[p.name]) return src[p.name];
  const last = (p.name || "").split(" ").pop().toLowerCase();
  const key = Object.keys(src).find(k => k !== "_comment" && k.toLowerCase().endsWith(last));
  return key ? src[key] : null;
}

function ageOf(p, det) {
  const iso = (det && det.bornDate) || p.birthDate;
  const born = iso ? new Date(iso) : null;
  if (born && !isNaN(born)) {
    const now = new Date();
    let a = now.getFullYear() - born.getFullYear();
    const m = now.getMonth() - born.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < born.getDate())) a--;
    return a;
  }
  return p.born ? new Date().getFullYear() - p.born : null;
}

// a bar is only meaningful against a scale, so measure each player
// against the squad's own range
function squadRange(getter) {
  const vals = ((state.roster && state.roster.players) || [])
    .map(getter).filter(v => typeof v === "number" && !isNaN(v));
  if (!vals.length) return null;
  return { min: Math.min(...vals), max: Math.max(...vals) };
}

function attrBar(label, value, display, range, note) {
  const row = el("div", "attr");
  const top = el("div", "attr-top");
  top.appendChild(text("span", "attr-label", label));
  top.appendChild(text("span", "attr-value", display));
  row.appendChild(top);

  const track = el("div", "attr-track");
  const fill = el("div", "attr-fill");
  let pct = 50;
  if (range && range.max > range.min) {
    pct = ((value - range.min) / (range.max - range.min)) * 100;
  }
  fill.style.width = Math.max(6, Math.min(100, pct)) + "%";
  track.appendChild(fill);
  row.appendChild(track);

  if (range) {
    const ends = el("div", "attr-ends");
    ends.appendChild(text("span", "", String(range.min)));
    ends.appendChild(text("span", "", note || ""));
    ends.appendChild(text("span", "", String(range.max)));
    row.appendChild(ends);
  }
  return row;
}

function rankNote(value, getter, lowIsFirst) {
  const vals = ((state.roster && state.roster.players) || [])
    .map(getter).filter(v => typeof v === "number" && !isNaN(v));
  if (vals.length < 3 || typeof value !== "number") return "";
  const sorted = [...vals].sort((a, b) => lowIsFirst ? a - b : b - a);
  if (value === sorted[0]) return lowIsFirst ? "הצעיר בסגל" : "הגבוה בסגל";
  if (value === sorted[sorted.length - 1]) return lowIsFirst ? "הוותיק בסגל" : "הנמוך בסגל";
  return "";
}

function statBar(label, value, max, suffix) {
  const row = el("div", "statbar");
  const top = el("div", "attr-top");
  top.appendChild(text("span", "attr-label", label));
  top.appendChild(text("span", "attr-value", value + (suffix || "")));
  row.appendChild(top);
  const track = el("div", "attr-track");
  const fill = el("div", "attr-fill stat");
  fill.style.width = Math.max(6, Math.min(100, (value / max) * 100)) + "%";
  track.appendChild(fill);
  row.appendChild(track);
  return row;
}

function fmtMoney(n, cur) {
  if (n >= 1000000) {
    const m = (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1);
    return m + " מיליון " + (cur || "$");
  }
  return Math.round(n / 1000) + " אלף " + (cur || "$");
}

function renderPlayer(slug) {
  const players = (state.roster && state.roster.players) || [];
  const p = players.find(x => (x.slug || slugOf(x)) === slug);

  const back = el("a", "back-link");
  back.href = "#/roster";
  back.textContent = "› חזרה לסגל";
  view.appendChild(back);

  if (!p) {
    view.appendChild(text("div", "empty", "לא מצאנו את השחקן הזה"));
    footer();
    return;
  }

  const card = el("div", "card player-hero");
  card.appendChild(playerAvatar(p, "big"));
  if (p.number != null) card.appendChild(text("div", "big-shirt", String(p.number)));
  card.appendChild(playerNameEl(p, "player-title"));
  if (p.position) card.appendChild(text("div", "player-pos", p.position));
  view.appendChild(card);

  const prof = profileOf(p);
  if (prof) {
    view.appendChild(text("div", "section-title", "דוח סקאוטינג"));
    const pc = el("div", "card");
    pc.appendChild(reportBody(prof));
    view.appendChild(pc);
  }

  const det = detailsOf(p);
  const age = ageOf(p, det);

  // attributes as bars, measured against the squad's own range
  const attrs = el("div", "card");
  attrs.appendChild(text("div", "eyebrow", "נתונים"));
  if (age) {
    const ageRange = squadRange(x => ageOf(x, detailsOf(x)));
    attrs.appendChild(attrBar("גיל", age, age, ageRange,
      rankNote(age, x => ageOf(x, detailsOf(x)), true)));
  }
  if (p.height) {
    attrs.appendChild(attrBar("גובה", p.height, p.height + " ס״מ",
      squadRange(x => x.height), rankNote(p.height, x => x.height, false)));
  }
  const chips = el("div", "chips-row");
  if (p.position) chips.appendChild(text("span", "strength", p.position));
  if (p.country) chips.appendChild(text("span", "strength", p.country));
  if (det && det.birthPlace) chips.appendChild(text("span", "strength", "נולד ב" + det.birthPlace));
  if (chips.children.length) attrs.appendChild(chips);
  view.appendChild(attrs);

  // contract and salary, only what has actually been reported
  if (det && (det.contract || det.salary)) {
    view.appendChild(text("div", "section-title", "חוזה"));
    const cc = el("div", "card");
    const row = el("div", "contract-row");
    if (det.contract) {
      const box = el("div", "contract-box");
      box.appendChild(text("div", "cv",
        det.contract.years + (det.contract.years === 1 ? " עונה" : " עונות")));
      box.appendChild(text("div", "cl", det.contract.until ? "עד " + det.contract.until : "משך החוזה"));
      row.appendChild(box);
    }
    const sal = el("div", "contract-box");
    if (det.salary && det.salary.perSeason) {
      sal.appendChild(text("div", "cv", fmtMoney(det.salary.perSeason, det.salary.currency)));
      sal.appendChild(text("div", "cl", "לעונה · לפי דיווח"));
    } else {
      sal.appendChild(text("div", "cv muted-value", "לא פורסם"));
      sal.appendChild(text("div", "cl", "שכר"));
    }
    row.appendChild(sal);
    cc.appendChild(row);
    if (det.contract && det.contract.note) {
      cc.appendChild(prose("div", "contract-note", det.contract.note));
    }
    if (det.salary && det.salary.reported) {
      cc.appendChild(text("div", "disclaimer-line",
        "נתוני שכר מבוססים על דיווחי תקשורת ואינם רשמיים."));
    }
    view.appendChild(cc);
  }

  // last season, as bars so the numbers register at a glance
  if (det && det.lastSeason) {
    const ls = det.lastSeason;
    view.appendChild(text("div", "section-title", "העונה שעברה"));
    const lc = el("div", "card");
    const cap = [ls.label, ls.team].filter(Boolean).join(" · ");
    if (cap) lc.appendChild(text("div", "season-cap", cap));
    if (ls.honor) lc.appendChild(text("div", "honor", "★ " + ls.honor));
    if (typeof ls.pts === "number") lc.appendChild(statBar("נקודות", ls.pts, 25));
    if (typeof ls.reb === "number") lc.appendChild(statBar("ריבאונדים", ls.reb, 12));
    if (typeof ls.ast === "number") lc.appendChild(statBar("אסיסטים", ls.ast, 8));
    if (typeof ls.threePct === "number") lc.appendChild(statBar("אחוזי 3", ls.threePct, 50, "%"));
    if (ls.games) lc.appendChild(text("div", "season-games", ls.games + " משחקים"));
    view.appendChild(lc);
  }

  // season averages arrive once games are played
  view.appendChild(text("div", "section-title", "העונה הנוכחית"));
  const sc = el("div", "card");
  const st = p.stats;
  if (st && Object.keys(st).length) {
    const grid = el("div", "facts");
    [["נקודות", st.pts], ["ריבאונדים", st.reb], ["אסיסטים", st.ast],
     ["דקות", st.min], ["מדד", st.pir], ["משחקים", st.games]]
      .filter(([, v]) => v !== undefined && v !== null)
      .forEach(([l, v]) => {
        const cell = el("div", "fact");
        cell.appendChild(text("div", "fv", String(v)));
        cell.appendChild(text("div", "fl", l));
        grid.appendChild(cell);
      });
    sc.appendChild(grid);
  } else {
    sc.appendChild(text("div", "empty", "העונה טרם החלה. הנתונים יופיעו כאן אחרי המשחק הראשון"));
  }
  view.appendChild(sc);

  footer();
}

/* ---------- history, trophies and past stars ---------- */

/* ---------- hall of fame ---------- */

// one coach card, shared by the history screen and the hall of fame
function coachCard(c) {
  const card = el("div", "card coach-card" + (c.highlight ? " coach-big" : ""));
  const top = el("div", "coach-top");
  const who = el("div");
  who.appendChild(text("div", "coach-name", c.name));
  if (c.title) who.appendChild(prose("div", "coach-title", c.title));
  top.appendChild(who);
  const yr = el("div", "coach-years" + (c.current ? " now" : ""));
  yr.textContent = c.years;
  top.appendChild(yr);
  card.appendChild(top);

  card.appendChild(prose("p", "meet-summary", c.text));
  if (c.achievements && c.achievements.length) {
    const chips = el("div", "chips-row");
    c.achievements.forEach(a => chips.appendChild(prose("span", "strength trophy-chip", "🏆 " + a)));
    card.appendChild(chips);
  }
  if (c.source) {
    const a = el("a", "meet-link muted-link");
    a.href = c.source; a.target = "_blank"; a.rel = "noopener";
    a.textContent = "המקור";
    card.appendChild(a);
  }
  return card;
}

function hofCard(p, foreign) {
  const c = el("div", "card hof-card");
  const head = el("div", "hof-head");
  const av = el("div", "hof-badge");
  av.textContent = initialsOf({ name: p.name });
  let h = 0;
  for (let i = 0; i < p.name.length; i++) h = (h * 31 + p.name.charCodeAt(i)) >>> 0;
  av.style.setProperty("--h", String(AVATAR_HUES[h % AVATAR_HUES.length]));
  head.appendChild(av);
  const who = el("div", "info");
  who.appendChild(text("div", "hof-name", p.name));
  // the name the stands actually used
  if (p.nickname) who.appendChild(text("div", "hof-nick", "״" + p.nickname + "״"));
  const bits = [p.position, p.era];
  if (foreign && p.country) bits.splice(1, 0, p.country);
  who.appendChild(prose("div", "sub", bits.filter(Boolean).join(" · ")));
  head.appendChild(who);
  c.appendChild(head);

  if (p.latin) {
    const lat = text("div", "hof-latin", p.latin);
    c.appendChild(lat);
  }
  c.appendChild(prose("div", "hof-headline", p.headline));
  c.appendChild(prose("p", "hof-bio", p.bio));

  if (p.highlights && p.highlights.length) {
    const ul = el("ul", "hof-list");
    p.highlights.forEach(x => ul.appendChild(prose("li", "", x)));
    c.appendChild(ul);
  }
  if (p.source) {
    const a = el("a", "src-link");
    a.href = p.source;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "מקור";
    c.appendChild(a);
  }
  return c;
}

function renderHof() {
  const h = state.hof;
  if (!h) {
    view.appendChild(text("div", "empty", "אולם התהילה בהכנה"));
    footer();
    return;
  }
  const intro = el("div", "card meet-intro");
  intro.appendChild(text("div", "eyebrow", "אולם התהילה"));
  intro.appendChild(text("div", "meet-title", "מי שזוכרים בשמם"));
  intro.appendChild(prose("p", "", h.intro));
  view.appendChild(intro);

  // coaches live in history.json, one list, shown in both places
  const coaches = (state.history && state.history.coaches) || [];
  const seg = el("div", "seg");
  const tabs = [
    ["israeli", "ישראלים · " + (h.israelis || []).length],
    ["foreign", "זרים · " + (h.foreigners || []).length],
  ];
  if (coaches.length) tabs.push(["coaches", "מאמנים · " + coaches.length]);
  if ((h.flops || []).length) tabs.push(["flops", "אכזבות · " + h.flops.length]);
  tabs.forEach(([key, label]) => {
    const b = text("button", state.hofTab === key ? "active" : "", label);
    b.onclick = () => { state.hofTab = key; render(); };
    seg.appendChild(b);
  });
  view.appendChild(seg);

  if (state.hofTab === "coaches") {
    if (h.coachesIntro) view.appendChild(text("div", "table-note", h.coachesIntro));
    coaches.forEach(c => view.appendChild(coachCard(c)));
    const note = (state.history && state.history.coachesNote);
    if (note) view.appendChild(text("div", "table-note", note));
    footer();
    return;
  }

  if (state.hofTab === "flops") {
    if (h.flopsIntro) view.appendChild(prose("div", "table-note", h.flopsIntro));
    h.flops.forEach(p => {
      const c = hofCard(p, true);
      c.classList.add("flop-card");
      view.appendChild(c);
    });
    footer();
    return;
  }

  const foreign = state.hofTab === "foreign";
  (foreign ? h.foreigners : h.israelis).forEach(p =>
    view.appendChild(hofCard(p, foreign)));

  if (h.note) view.appendChild(prose("div", "table-note", h.note));
  footer();
}

/* ---------- last season, and this one ---------- */

function renderStats() {
  const seg = el("div", "seg");
  const bT = text("button", state.statsTab === "last" ? "" : "active", "העונה הזו");
  const bL = text("button", state.statsTab === "last" ? "active" : "", "העונה שעברה");
  bT.onclick = () => { state.statsTab = "now"; render(); };
  bL.onclick = () => { state.statsTab = "last"; render(); };
  seg.appendChild(bT);
  seg.appendChild(bL);
  view.appendChild(seg);

  if (state.statsTab === "last") renderLastSeason();
  else renderThisSeason();
  footer();
}

function statRow(p, cols) {
  const tr = el("tr");
  const td = el("td", "team");
  td.appendChild(text("span", "", playerName({ name: p.name })));
  tr.appendChild(td);
  cols.forEach(c => tr.appendChild(text("td", "num", p[c.key] == null ? "-" : String(p[c.key]))));
  return tr;
}

function renderThisSeason() {
  const s = state.seasonStats;
  if (!s || !s.started || !(s.players || []).length) {
    const c = el("div", "card notice");
    c.appendChild(text("div", "notice-title", "העונה עוד לא התחילה"));
    c.appendChild(text("div", "notice-body",
      "ברגע שיישחק המשחק הראשון, הסטטיסטיקות ייכנסו לכאן מעצמן, ממוצעים " +
      "לשחקן ישירות מהפיד הרשמי של היורוקאפ, בלי הקלדה ידנית."));
    view.appendChild(c);
    advancedCard();
    return;
  }

  view.appendChild(text("div", "section-title",
    "ממוצעים למשחק · " + s.competition + " " + s.season));
  const cols = [
    { key: "games", label: "מש׳" }, { key: "pts", label: "נק׳" },
    { key: "reb", label: "ריב׳" }, { key: "ast", label: "אס׳" },
    { key: "val", label: "מדד" },
  ];
  const card = el("div", "card table-card");
  const t = el("table", "standings stats-table");
  const head = el("tr");
  const th0 = el("th", "team");
  th0.textContent = "שחקן";
  head.appendChild(th0);
  cols.forEach(c => {
    const th = el("th", "");
    th.textContent = c.label;
    head.appendChild(th);
  });
  t.appendChild(head);
  s.players.forEach(p => t.appendChild(statRow(p, cols)));
  card.appendChild(t);
  view.appendChild(card);
  if (s.note) view.appendChild(prose("div", "table-note", s.note));
  advancedCard();
}

// Deliberately a promise, not a fake chart: everything here needs play-by-play
// data we do not have yet, and inventing it would be worse than waiting.
function advancedCard() {
  view.appendChild(text("div", "section-title", "סטטיסטיקה מתקדמת"));
  const c = el("div", "card notice");
  c.appendChild(text("div", "notice-title", "בדרך"));
  c.appendChild(text("div", "notice-body",
    "יעילות התקפה והגנה ל־100 מחזורים, אחוז שימוש, True Shooting והפרש " +
    "כשעל הפרקט. המדדים האלה דורשים נתוני מחזורים שעדיין לא אספנו, " +
    "וטבלה שנראית מרשים אבל מבוססת על ניחוש שווה פחות מכלום."));
  view.appendChild(c);
}

// Averages for the season that ended. Two rows per player: the counting stats
// on top, the shooting underneath, a phone cannot hold nine columns, and
// splitting beats dropping half the numbers.
function lastSeasonPlayers(ps) {
  if (!ps || !(ps.players || []).length) return;
  view.appendChild(text("div", "section-title",
    "ממוצעים למשחק · " + ps.competition + " " + ps.season));

  const card = el("div", "card table-card");
  const t = el("table", "standings stats-table");
  const head = el("tr");
  const th0 = el("th", "team");
  th0.textContent = "שחקן";
  head.appendChild(th0);
  [["דק׳", "דקות"], ["נק׳", "נקודות"], ["ריב׳", "ריבאונדים"],
   ["אס׳", "אסיסטים"], ["מדד", "מדד יעילות"]].forEach(([short, full]) => {
    const th = el("th", "");
    th.textContent = short;
    th.title = full;
    head.appendChild(th);
  });
  t.appendChild(head);

  ps.players.forEach(p => {
    const tr = el("tr");
    const td = el("td", "team");
    td.appendChild(text("span", "", p.nameHe || p.name));
    td.appendChild(text("span", "ps-games", p.games + " מש׳"));
    tr.appendChild(td);
    [p.min, p.pts, p.reb, p.ast, p.val].forEach(v =>
      tr.appendChild(text("td", "num", v == null ? "-" : v.toFixed(1))));
    t.appendChild(tr);

    // the shooting line, only when the feed actually recorded attempts
    const shots = [["2", p.fg2], ["3", p.fg3], ["עונשין", p.ft]]
      .filter(([, v]) => v);
    if (shots.length) {
      const sr = el("tr", "ps-shot");
      const sc = el("td");
      sc.colSpan = 6;
      shots.forEach(([label, v]) => {
        const b = el("span", "ps-pct");
        b.appendChild(text("span", "ps-pct-k", label));
        b.appendChild(text("span", "ps-pct-v", v));
        sc.appendChild(b);
      });
      sr.appendChild(sc);
      t.appendChild(sr);
    }
  });
  card.appendChild(t);
  view.appendChild(card);
  if (ps.note) view.appendChild(prose("div", "table-note", ps.note));
}

function renderLastSeason() {
  const l = state.lastSeason;
  if (!l) {
    view.appendChild(text("div", "empty", "נתוני העונה שעברה בהכנה"));
    return;
  }
  const lg = l.league || {};
  view.appendChild(text("div", "section-title", "עונת " + l.season + " · " + lg.name));

  const c = el("div", "card");
  const row = el("div", "ls-summary");
  [["מקום", String(lg.ourPos)], ["מאזן", lg.ourRecord],
   ["נקודות", String(lg.ourPoints)],
   ["הפרש", (lg.ourDiff > 0 ? "+" : "") + lg.ourDiff]].forEach(([k, v]) => {
    const b = el("div", "lsx");
    b.appendChild(text("div", "lsx-v", v));
    b.appendChild(text("div", "lsx-k", k));
    row.appendChild(b);
  });
  c.appendChild(row);
  const split = el("div", "ls-split");
  [["בבית", lg.home], ["בחוץ", lg.away]].forEach(([k, s]) => {
    if (!s) return;
    const d = el("div", "lsp");
    d.appendChild(text("div", "lsp-k", k));
    d.appendChild(text("div", "lsp-v", s.wins + "‑" + s.losses));
    d.appendChild(text("div", "lsp-s", s.for + ":" + s.against));
    split.appendChild(d);
  });
  c.appendChild(split);
  view.appendChild(c);

  (l.headlines || []).forEach(h => {
    const b = el("div", "card");
    b.appendChild(prose("div", "notice-title", h.title));
    b.appendChild(prose("div", "notice-body", h.text));
    view.appendChild(b);
  });

  lastSeasonPlayers(l.playerStats);

  if (lg.rows && lg.rows.length) {
    view.appendChild(text("div", "section-title", "הטבלה הסופית"));
    const tc = el("div", "card table-card");
    const t = el("table", "standings");
    const head = el("tr");
    ["#", "קבוצה", "מש׳", "נצ׳", "הפ׳", "נק׳"].forEach((x, i) => {
      const th = el("th", i === 1 ? "team" : "");
      th.textContent = x;
      head.appendChild(th);
    });
    t.appendChild(head);
    lg.rows.forEach(r => {
      const tr = el("tr", isUs(r.team) ? "us" : "");
      tr.appendChild(text("td", "num", String(r.pos)));
      tr.appendChild(text("td", "team", r.team));
      tr.appendChild(text("td", "num", String(r.played)));
      tr.appendChild(text("td", "num", String(r.wins)));
      tr.appendChild(text("td", "num", String(r.losses)));
      tr.appendChild(text("td", "num", String(r.points)));
      t.appendChild(tr);
    });
    tc.appendChild(t);
    view.appendChild(tc);
    if (lg.champion) {
      view.appendChild(text("div", "table-note", "אלופת העונה: " + lg.champion + "."));
    }
  }

  const eu = l.europe;
  if (eu) {
    view.appendChild(text("div", "section-title", eu.name));
    const b = el("div", "card");
    if (eu.mvp) b.appendChild(text("div", "notice-title", eu.mvp));
    b.appendChild(prose("div", "notice-body", eu.note));
    if (eu.source) {
      const a = el("a", "src-link");
      a.href = eu.source;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "מקור";
      b.appendChild(a);
    }
    view.appendChild(b);
  }
  if (lg.source) {
    const a = el("a", "src-link block");
    a.href = lg.source;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "מקור הטבלה: אתר הליגה";
    view.appendChild(a);
  }
}

function renderHistory() {
  const h = state.history;
  if (!h) {
    view.appendChild(text("div", "empty", "ההיסטוריה בהכנה"));
    footer();
    return;
  }

  const intro = el("div", "card meet-intro");
  intro.appendChild(text("div", "eyebrow", "המורשת"));
  intro.appendChild(text("div", "meet-title", "מאז " + h.founded));
  intro.appendChild(text("p", "",
    "שמונים שנה של המתנה לאליפות הראשונה, לילה אחד בבלגיה ששינה הכול, ודרך שעדיין נמשכת."));
  view.appendChild(intro);

  // trophy cabinet
  if (h.trophies && h.trophies.length) {
    view.appendChild(text("div", "section-title", "ארון התארים"));
    const grid = el("div", "trophy-grid");
    h.trophies.forEach(t => {
      const c = el("div", "trophy");
      c.appendChild(text("div", "tr-emoji", t.emoji || "🏆"));
      c.appendChild(text("div", "tr-count", String(t.count)));
      c.appendChild(text("div", "tr-name", t.name));
      if (t.years) c.appendChild(text("div", "tr-years", t.years));
      grid.appendChild(c);
    });
    view.appendChild(grid);
  }

  // timeline
  if (h.timeline && h.timeline.length) {
    view.appendChild(text("div", "section-title", "רגעים"));
    const line = el("div", "timeline");
    h.timeline.forEach(e => {
      const item = el("div", "tl-item" + (e.highlight ? " tl-big" : ""));
      item.appendChild(text("div", "tl-year", e.year));
      const body = el("div", "tl-body");
      body.appendChild(prose("div", "tl-title", e.title));
      body.appendChild(prose("p", "tl-text", e.text));
      if (e.source) {
        const a = el("a", "meet-link muted-link");
        a.href = e.source; a.target = "_blank"; a.rel = "noopener";
        a.textContent = "המקור";
        body.appendChild(a);
      }
      item.appendChild(body);
      line.appendChild(item);
    });
    view.appendChild(line);
  }

  // the same history told through whoever was paying for it
  if (h.owners && h.owners.length) {
    view.appendChild(text("div", "section-title", "עידני הבעלות"));
    if (h.ownersIntro) view.appendChild(prose("div", "list-note", h.ownersIntro));
    h.owners.forEach(o => view.appendChild(coachCard(o)));
  }

  // eras, told through the coaches who shaped them
  if (h.coaches && h.coaches.length) {
    view.appendChild(text("div", "section-title", "עידני מאמנים"));
    h.coaches.forEach(c => view.appendChild(coachCard(c)));
    if (h.coachesNote) {
      view.appendChild(text("div", "list-note", h.coachesNote));
    }
  }

  // the nights nobody puts on a poster
  if (h.affairs && h.affairs.length) {
    view.appendChild(text("div", "section-title", "פרשות"));
    if (h.affairsIntro) view.appendChild(prose("div", "list-note", h.affairsIntro));
    h.affairs.forEach(a => {
      const c = el("div", "card affair-card");
      const head = el("div", "affair-head");
      head.appendChild(text("span", "affair-year", a.year));
      head.appendChild(prose("span", "affair-title", a.title));
      c.appendChild(head);
      c.appendChild(prose("p", "affair-text", a.text));
      if (a.source) {
        const link = el("a", "meet-link muted-link");
        link.href = a.source; link.target = "_blank"; link.rel = "noopener";
        link.textContent = "המקור";
        c.appendChild(link);
      }
      view.appendChild(c);
    });
  }

  // the founder's special request
  if (h.legends && h.legends.length) {
    view.appendChild(text("div", "section-title", "פינת כוכבי העבר"));
    h.legends.forEach(l => {
      const c = el("div", "card meet-card");
      const head = el("div", "meet-head");
      const badge = el("div", "shirt legend-badge");
      badge.textContent = "★";
      head.appendChild(badge);
      const who = el("div", "info");
      who.appendChild(text("div", "opp", l.name));
      const sub = el("div", "sub");
      if (l.role) sub.appendChild(document.createTextNode(l.role + (l.era ? " · " : "")));
      if (l.era) sub.appendChild(text("span", "yr", l.era));
      who.appendChild(sub);
      head.appendChild(who);
      c.appendChild(head);
      c.appendChild(prose("p", "meet-summary", l.text));
      if (l.source) {
        const a = el("a", "meet-link muted-link");
        a.href = l.source; a.target = "_blank"; a.rel = "noopener";
        a.textContent = "המקור";
        c.appendChild(a);
      }
      view.appendChild(c);
    });
  }

  footer();
}

/* ---------- meet the squad ---------- */

function profileOf(p) {
  const src = state.profiles || {};
  if (src[p.name]) return src[p.name];
  // fall back to a surname match, so "Kenneth" vs "Kenny" still lands
  const last = (p.name || "").split(" ").pop().toLowerCase();
  const key = Object.keys(src).find(k => k !== "_comment" && k.toLowerCase().endsWith(last));
  return key ? src[key] : null;
}

function skillRow(label, value) {
  const row = el("div", "skill");
  row.appendChild(text("span", "skill-label", label));
  const dots = el("div", "skill-dots");
  for (let i = 1; i <= 5; i++) {
    dots.appendChild(el("span", "dot" + (i <= value ? " on" : "")));
  }
  row.appendChild(dots);
  return row;
}

function reportBody(prof, opts) {
  const frag = document.createDocumentFragment();
  frag.appendChild(prose("div", "meet-headline", prof.headline));
  frag.appendChild(prose("p", "meet-summary", prof.summary));

  if (prof.skills && Object.keys(prof.skills).length) {
    const box = el("div", "skills-box");
    box.appendChild(text("div", "skills-cap", "פרופיל יכולות"));
    Object.keys(prof.skills).forEach(k => box.appendChild(skillRow(k, prof.skills[k])));
    box.appendChild(text("div", "disclaimer-line", "הערכה שנגזרה מדוחות פומביים, לא מדד רשמי."));
    frag.appendChild(box);
  }

  if (prof.strengths && prof.strengths.length) {
    const b = el("div", "pros");
    b.appendChild(text("div", "list-cap", "חוזקות"));
    const ul = el("ul");
    prof.strengths.forEach(x => ul.appendChild(prose("li", "", x)));
    b.appendChild(ul);
    frag.appendChild(b);
  }
  if (prof.weaknesses && prof.weaknesses.length) {
    const b = el("div", "cons");
    b.appendChild(text("div", "list-cap", "לשים לב"));
    const ul = el("ul");
    prof.weaknesses.forEach(x => ul.appendChild(prose("li", "", x)));
    b.appendChild(ul);
    frag.appendChild(b);
  }
  if (prof.watch) {
    const w = el("div", "meet-watch");
    w.appendChild(text("span", "watch-label", "למה לשים לב"));
    w.appendChild(text("span", "", prof.watch));
    frag.appendChild(w);
  }
  if (prof.role) {
    const r = el("div", "role-box");
    r.appendChild(text("span", "watch-label", "התפקיד בהפועל"));
    r.appendChild(prose("span", "", prof.role));
    frag.appendChild(r);
  }
  if (prof.comparison) {
    const c = el("div", "chips-row");
    c.appendChild(prose("span", "strength compare", "משווים אותו ל" + prof.comparison));
    frag.appendChild(c);
  }
  const srcs = prof.sources || (prof.source ? [prof.source] : []);
  if (srcs.length && (!opts || !opts.hideSources)) {
    const links = el("div", "meet-links");
    srcs.forEach((u, i) => {
      const a = el("a", "meet-link muted-link");
      a.href = u; a.target = "_blank"; a.rel = "noopener";
      a.textContent = srcs.length > 1 ? "מקור " + (i + 1) : "המקור";
      links.appendChild(a);
    });
    frag.appendChild(links);
  }
  return frag;
}

function renderMeet() {
  const players = ((state.roster && state.roster.players) || []).slice()
    .sort((a, b) => (a.number ?? 999) - (b.number ?? 999));

  const intro = el("div", "card meet-intro");
  intro.appendChild(text("div", "eyebrow", "בואו נכיר"));
  intro.appendChild(text("div", "meet-title", "מי הם החבר\u05f3ה האלה?"));
  intro.appendChild(text("p", "",
    "סגל חדש ברובו. לכל שחקן דוח מלא: מה הוא נותן, איפה הוא פחות חזק, ומה התפקיד שלו בקבוצה הזאת."));
  intro.appendChild(text("p", "meet-note",
    "הדוחות נכתבו על ידי אוהדים על בסיס דוחות סקאוטינג ונתונים פומביים, עם מקורות. אינם מטעם המועדון."));
  view.appendChild(intro);

  let written = 0;
  players.forEach(p => {
    const prof = profileOf(p);
    if (!prof) return;
    written++;
    const c = el("div", "card meet-card");

    const head = el("div", "meet-head");
    const num = el("div", "shirt");
    num.textContent = p.number != null ? p.number : "\u2013";
    head.appendChild(num);
    head.appendChild(playerAvatar(p, "thumb"));
    const who = el("div", "info");
    who.appendChild(playerNameEl(p));
    const bits = [];
    if (p.position) bits.push(p.position);
    if (p.height) bits.push(p.height + " ס\u05f4מ");
    if (p.country) bits.push(p.country);
    if (bits.length) who.appendChild(text("div", "sub", bits.join(" · ")));
    head.appendChild(who);
    c.appendChild(head);

    c.appendChild(reportBody(prof));

    const page = el("a", "meet-link");
    page.href = "#/player/" + encodeURIComponent(p.slug || slugOf(p));
    page.textContent = "לעמוד השחקן";
    c.appendChild(page);
    view.appendChild(c);
  });

  if (!written) {
    view.appendChild(text("div", "empty", "הדוחות בהכנה, נעדכן בקרוב"));
  }
  const cr = photoCredit();
  if (cr) view.appendChild(cr);
  footer();
}

/* ---------- diary ---------- */

const SEASON_START = new Date(new Date().getFullYear(), 6, 1); // 1 July of this year

function diaryEntries(scope) {
  return Object.entries(diary)
    .map(([id, e]) => ({ id, ...e }))
    .filter(e => scope === "all" || new Date(e.date) >= SEASON_START)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

function diaryStats(entries) {
  const played = entries.filter(e => e.status === "finished");
  const wins = played.filter(e => e.us > e.them).length;
  return {
    total: entries.length,
    home: entries.filter(e => e.home).length,
    away: entries.filter(e => !e.home).length,
    europe: entries.filter(e => /יורו|אירופ|BCL|צ׳מפיונס|ליגת האלופות/i.test(e.competition || "")).length,
    played: played.length,
    wins,
    losses: played.length - wins,
  };
}

const BADGES = [
  { key: "veteran10", emoji: "🏆", name: "ותיק היציע", need: 10,
    got: s => s.total, hint: "10 משחקים" },
  { key: "veteran25", emoji: "🎖️", name: "ותיק כבוד", need: 25,
    got: s => s.total, hint: "25 משחקים" },
  { key: "veteran50", emoji: "👑", name: "אגדת יציע", need: 50,
    got: s => s.total, hint: "50 משחקים" },
  { key: "away5", emoji: "🚌", name: "נאמן בחוץ", need: 5,
    got: s => s.away, hint: "5 משחקי חוץ" },
  // Hapoel Jerusalem-Maccabi Tel Aviv is the קלאסיקו; a דרבי would mean
  // two clubs from the same city, which this is not
  { key: "clasico", emoji: "🔥", name: "קלאסיקו", need: 1,
    got: (s, e) => e.filter(x => /מכבי ת|מכבי תל אביב/.test(x.opponent || "")).length,
    hint: "משחק מול מכבי ת״א" },
  { key: "europe", emoji: "✈️", name: "לילה אירופי", need: 1,
    got: s => s.europe, hint: "משחק אירופי" },
  { key: "rain", emoji: "☔", name: "נאמן גם בגשם", need: 1,
    got: (s, e) => e.filter(x => x.status === "finished" && x.us < x.them).length,
    hint: "נשארת גם בהפסד" },
  { key: "charm", emoji: "🍀", name: "קמע", need: 5,
    got: (s, e) => {
      const played = e.filter(x => x.status === "finished")
        .sort((a, b) => new Date(a.date) - new Date(b.date));
      let best = 0, run = 0;
      played.forEach(x => { run = x.us > x.them ? run + 1 : 0; best = Math.max(best, run); });
      return best;
    }, hint: "5 ניצחונות ברצף" },
];

function renderDiary() {
  const scope = state.diaryScope;
  const entries = diaryEntries(scope);
  const s = diaryStats(entries);

  const seg = el("div", "seg");
  const bS = text("button", scope === "season" ? "active" : "", "העונה");
  const bA = text("button", scope === "all" ? "active" : "", "הכול");
  bS.onclick = () => { state.diaryScope = "season"; render(); };
  bA.onclick = () => { state.diaryScope = "all"; render(); };
  seg.appendChild(bS);
  seg.appendChild(bA);
  view.appendChild(seg);

  if (!s.total) {
    const c = el("div", "card");
    c.appendChild(text("div", "eyebrow", "היומן שלי"));
    const e = el("div", "empty");
    e.innerHTML = 'עוד לא סימנת אף משחק.<br>בלשונית ״משחקים״ סמנו ״הייתי שם״, והיומן יתחיל להיבנות.<br><br>' +
      '<span class="tiny">הכול נשמר במכשיר שלך בלבד. בלי הרשמה, בלי שרת.</span>';
    c.appendChild(e);
    view.appendChild(c);
    footer();
    return;
  }

  // hero
  const hero = el("div", "card diary-hero");
  hero.appendChild(text("div", "eyebrow", scope === "season" ? "העונה שלי" : "מאז ומתמיד"));
  hero.appendChild(text("div", "big", String(s.total)));
  hero.appendChild(text("div", "cap", s.total === 1 ? "משחק שהייתי בו" : "משחקים שהייתי בהם"));
  const grid = el("div", "stat-grid");
  [["בית", s.home], ["חוץ", s.away], ["אירופה", s.europe]].forEach(([l, n]) => {
    const cell = el("div", "stat-cell");
    cell.appendChild(text("div", "n", String(n)));
    cell.appendChild(text("div", "l", l));
    grid.appendChild(cell);
  });
  hero.appendChild(grid);
  if (s.played) {
    const rec = el("div", "record" + (s.wins >= s.losses ? "" : " bad"));
    rec.appendChild(text("span", "lab", "המאזן שלי ביציע"));
    rec.appendChild(text("span", "val", s.wins + "-" + s.losses));
    hero.appendChild(rec);
  }
  const share = el("button", "share-btn", "שיתוף בוואטסאפ");
  share.type = "button";
  share.onclick = () => shareDiary(s, scope);
  hero.appendChild(share);
  view.appendChild(hero);

  // badges
  view.appendChild(text("div", "section-title", "תגים"));
  const bc = el("div", "card");
  const bl = el("div", "badge-list");
  BADGES.forEach(b => {
    const got = b.got(s, entries);
    const done = got >= b.need;
    const chip = el("div", "bdg" + (done ? "" : " locked"));
    chip.appendChild(text("span", "bdg-emoji", b.emoji));
    const t = el("span");
    t.appendChild(text("span", "bdg-name", b.name));
    t.appendChild(text("span", "bdg-sub", done ? b.hint : b.hint + " · " + got + " מתוך " + b.need));
    chip.appendChild(t);
    bl.appendChild(chip);
  });
  bc.appendChild(bl);
  view.appendChild(bc);

  // history
  view.appendChild(text("div", "section-title", "המשחקים שלי"));
  entries.forEach(e => {
    const row = el("div", "game-row");
    const d = new Date(e.date);
    const date = el("div", "date-block");
    date.appendChild(text("div", "d", String(d.getDate())));
    date.appendChild(text("div", "m", MONTHS_SHORT[d.getMonth()]));
    row.appendChild(date);
    const info = el("div", "info");
    info.appendChild(oppEl("opp", e.opponent));
    info.appendChild(text("div", "sub",
      (e.competition || "") + " · " + (e.home ? "בית" : "חוץ") + " · " + d.getFullYear()));
    row.appendChild(info);
    const end = el("div", "end");
    if (e.status === "finished") {
      end.appendChild(text("div", "t score", e.us + "-" + e.them));
      end.appendChild(text("span", "chip " + (e.us > e.them ? "win" : "loss"), e.us > e.them ? "נ׳" : "ה׳"));
    } else {
      end.appendChild(text("div", "t", fmtTime.format(d)));
    }
    row.appendChild(end);
    view.appendChild(row);
  });

  footer();
}

function shareDiary(s, scope) {
  const lines = [
    scope === "season" ? "העונה שלי עם הפועל ירושלים 🔴⚫" : "אני והפועל ירושלים 🔴⚫",
    s.total + (s.total === 1 ? " משחק ביציע" : " משחקים ביציע") +
      " (" + s.home + " בית, " + s.away + " חוץ)",
  ];
  if (s.played) lines.push("המאזן שלי: " + s.wins + "-" + s.losses);
  const earned = BADGES.filter(b => b.got(s, diaryEntries(scope)) >= b.need);
  if (earned.length) lines.push(earned.map(b => b.emoji + " " + b.name).join(" · "));
  lines.push("יושב סופר את הדקות");
  const txt = lines.join("\n");

  if (navigator.share) {
    navigator.share({ text: txt }).catch(() => {});
  } else {
    window.open("https://wa.me/?text=" + encodeURIComponent(txt), "_blank", "noopener");
  }
}

/* ---------- footer ---------- */

function footer() {
  const f = el("div", "footer-note");
  const updated = state.meta.lastUpdated
    ? "עודכן לאחרונה: " + fmtUpdated.format(new Date(state.meta.lastUpdated)) : "";
  f.innerHTML = (updated ? updated + "<br>" : "") +
    'מיזם אוהדים לא רשמי, נבנה באהבה <span class="heart">♥</span> קוד פתוח';
  // the poll shows itself once; this is the way back in for anyone who
  // waved it away and later had something to say
  if (pollConfig()) {
    const a = el("button", "footer-link", "יש לכם רעיון? ספרו לנו");
    a.type = "button";
    a.onclick = openPoll;
    f.appendChild(el("br"));
    f.appendChild(a);
  }
  view.appendChild(f);
}

boot();
