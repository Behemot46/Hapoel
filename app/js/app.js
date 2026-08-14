"use strict";

const TEAM = "הפועל ירושלים";
const state = {
  games: null, standings: null, meta: null, club: null,
  gamesTab: "upcoming", tableTab: "league", diaryScope: "season",
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

// keep stored snapshots fresh — a game marked while upcoming gains its result later
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
  // blocked on file:// — so read from there first when it exists
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
    const [games, standings, meta, club, roster, names, profiles, details, teamNames, history, eurocup] = await Promise.all([
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
    if (meta.sample) document.getElementById("sampleBanner").hidden = false;
    // the single-file build is a frozen copy, so say so plainly
    if (window.__HAPOEL_SNAPSHOT__) {
      const b = document.getElementById("sampleBanner");
      b.textContent = "עותק להורדה — צילום מצב מ־" + window.__HAPOEL_SNAPSHOT__ +
        ". לגרסה המתעדכנת: behemot46.github.io/Hapoel";
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
  render();
  // a frozen single-file copy has no site to poll
  if (!window.__HAPOEL_SNAPSHOT__) watchLive();
}

/* ---------- helpers ---------- */

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
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
    : hash === "#/history" ? "home"
    : hash === "#/diary" ? "diary" : "home";
  document.querySelectorAll(".tabbar a").forEach(a =>
    a.classList.toggle("active", a.dataset.route === routeName));
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
  const num = text("span", "cd-num", "—");
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
// game is on. It may be missing entirely — that just means "nothing on".
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
    (g.competition || "") + (g.venue ? " · " + g.venue : "")));

  if (live.state === "live" || live.state === "final") {
    const us = live.ourScore, them = live.theirScore;
    const box = el("div", "live-score");
    const ours = el("div", "ls-side" + (us > them ? " lead" : ""));
    ours.appendChild(text("div", "ls-num", String(us)));
    ours.appendChild(text("div", "ls-who", "ירושלים"));
    const theirs = el("div", "ls-side" + (them > us ? " lead" : ""));
    theirs.appendChild(text("div", "ls-num", String(them)));
    theirs.appendChild(text("div", "ls-who", teamName(opp)));
    box.appendChild(ours);
    box.appendChild(text("div", "ls-sep", "–"));
    box.appendChild(theirs);
    c.appendChild(box);
    if (live.state === "live" && live.quarter) {
      c.appendChild(text("div", "live-when", quarterLabel(live.quarter)));
    }
  } else if (live.state === "starting") {
    c.appendChild(text("div", "live-when", "המשחק עולה לאוויר"));
  } else {
    // a domestic game: we know it is being played, we have no feed for it
    c.appendChild(text("div", "live-when", "המשחק מתנהל · אין הזנת תוצאות חיה"));
  }

  c.appendChild(text("div", "live-fresh", freshnessLabel(live.updated)));
  return c;
}

// swap the countdown out for the live card when a game starts, and back to
// the schedule when it ends — without the fan having to reload anything
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
// RFC 5545 wants lines folded at 75 octets — Hebrew is multi-byte, so fold
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
  return teamName(g.home) + " – " + teamName(g.away);
}

// calendar clients are happier with an ASCII UID, and our ids carry Hebrew
function icsUid(g) {
  let h = 0;
  for (let i = 0; i < g.id.length; i++) h = (h * 31 + g.id.charCodeAt(i)) >>> 0;
  return g.date.slice(0, 10).replace(/-/g, "") + "-" + h.toString(36) +
         "@hapoel-fan-app";
}

function gameLocation(g) {
  if (g.venue) return g.venue;
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
    // one reminder, two hours before — enough time to get to מלחה
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
  return text("div", "cal-note", "הקובץ יורד למכשיר — פתיחה שלו מוסיפה את המשחקים ליומן");
}

/* ---------- sharing the app itself ---------- */

// always the live site, never location.href — a standalone copy opened
// from disk would otherwise share a path on the sender's own device
function appUrl() {
  return (state.club && state.club.url) || "https://behemot46.github.io/Hapoel/";
}

function shareApp() {
  const msg = [
    "יושב סופר את הדקות 🔴⚫",
    "אפליקציית האוהדים של הפועל ירושלים — לוח משחקים, טבלה, סגל ויומן אישי.",
    "חינם, בלי הרשמה, נכנסים ומשתמשים:",
    appUrl(),
  ].join("\n");
  window.open("https://wa.me/?text=" + encodeURIComponent(msg), "_blank", "noopener");
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
    meta.appendChild(text("span", "badge" + (isHome(next) ? " home" : ""), isHome(next) ? "משחק בית" : "משחק חוץ"));
    if (next.venue) meta.appendChild(text("span", "badge", next.venue));
    c.appendChild(meta);
    c.appendChild(calButton([next], "הוספה ליומן", "hapoel-next-game.ics"));
    c.appendChild(calNote());
    view.appendChild(c);
  } else if (!next) {
    const c = el("div", "card");
    c.appendChild(text("div", "eyebrow", "המשחק הבא"));
    c.appendChild(text("div", "empty", "לוח המשחקים לעונה טרם פורסם — נעדכן ברגע שיהיה"));
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
    const sc = text("div", "score", ourScore(last) + "–" + theirScore(last));
    left.appendChild(sc);
    left.appendChild(text("span", "chip " + (won(last) ? "win" : "loss"), won(last) ? "נצחון" : "הפסד"));
    line.appendChild(left);
    c.appendChild(line);
    view.appendChild(c);
  }

  const rows = state.standings.rows;
  if (rows && rows.length) {
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
      ? "אין משחקים קרובים בלוח — נעדכן ברגע שיהיו"
      : "עוד לא נרשמו תוצאות העונה"));
    footer();
    return;
  }

  // 16 fixtures in a season is not a season — say why rather than let the
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
  info.appendChild(text("div", "sub",
    g.competition + " · " + (isHome(g) ? "בית" : "חוץ") + (g.venue ? " · " + g.venue : "")));
  row.appendChild(info);

  const end = el("div", "end");
  if (g.status === "finished") {
    end.appendChild(text("div", "t score", ourScore(g) + "–" + theirScore(g)));
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
    view.appendChild(text("div", "section-title",
      "טבלת " + state.standings.competition + " · עונת " + state.standings.season));
    const c = el("div", "card table-card");
    c.appendChild(standingsTable(state.standings.rows, true));
    view.appendChild(c);
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
  view.appendChild(text("div", "section-title",
    groupLabel(ours.name) + " · " + euro.competition + " " + euro.season));
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
  view.appendChild(text("div", "table-note",
    "הטבלה נקבעת לפי ניצחונות; בשוויון מכריעים המפגשים הישירים והפרש הנקודות."));
}

function isUsEuro(r) { return r.code === "JER" || isUs(teamName(r.team)); }

function eurocupTable(rows) {
  const t = el("table", "standings");
  const head = el("tr");
  ["#", "קבוצה", "מש׳", "נצ׳", "הפ׳", "הפרש"].forEach((h, i) => {
    const th = el("th", i === 1 ? "team" : "");
    th.textContent = h;
    head.appendChild(th);
  });
  t.appendChild(head);
  rows.forEach(r => {
    const tr = el("tr", isUsEuro(r) ? "us" : "");
    tr.appendChild(text("td", "num", r.pos == null ? "–" : String(r.pos)));
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

function standingsTable(rows, full) {
  const hasPoints = rows.some(r => r.points !== undefined);
  const t = el("table", "standings");
  const head = el("tr");
  const cols = ["#", "קבוצה", "מש׳", "נצ׳", "הפ׳"].concat(hasPoints ? ["נק׳"] : []);
  cols.forEach((h, i) => {
    const th = el("th", i === 1 ? "team" : "");
    th.textContent = h;
    head.appendChild(th);
  });
  t.appendChild(head);
  rows.forEach(r => {
    const tr = el("tr", isUs(r.team) ? "us" : "");
    tr.appendChild(text("td", "num", String(r.pos)));
    tr.appendChild(text("td", "team", r.team));
    tr.appendChild(text("td", "num", String(r.played)));
    tr.appendChild(text("td", "num", String(r.wins)));
    tr.appendChild(text("td", "num", String(r.losses)));
    if (hasPoints) tr.appendChild(text("td", "num", r.points !== undefined ? String(r.points) : "–"));
    t.appendChild(tr);
  });
  return t;
}

/* ---------- roster ---------- */

function renderRoster() {
  const r = state.roster || {};
  const players = r.players || [];
  view.appendChild(text("div", "section-title",
    "הסגל" + (r.season ? " · עונת " + r.season : "")));

  if (!players.length) {
    const c = el("div", "card");
    c.appendChild(text("div", "empty", "הסגל טרם פורסם — נעדכן ברגע שיהיה"));
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
    num.textContent = p.number != null ? p.number : "–";
    row.appendChild(num);
    row.appendChild(playerAvatar(p, "thumb"));
    const info = el("div", "info");
    info.appendChild(playerNameEl(p));
    // keep the list line short — the birth year lives on the player page
    const bits = [];
    if (p.position) bits.push(p.position);
    if (p.height) bits.push(p.height + " ס״מ");
    if (bits.length) info.appendChild(text("div", "sub", bits.join(" · ")));
    row.appendChild(info);
    row.appendChild(text("div", "chevron", "‹"));
    view.appendChild(row);
  });
  footer();
}

function slugOf(p) {
  return (p.name || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// Hebrew name when we have one; otherwise the Latin name, isolated so it
// keeps its own direction inside the RTL layout
function playerName(p) { return (state.playerNames || {})[p.name] || p.name; }
function playerNameEl(p, cls) {
  const he = (state.playerNames || {})[p.name];
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
  // ג׳ and צ׳ are one sound — keep the geresh with its letter
  const head = w => (/^[א-ת][׳']/.test(w) ? w.slice(0, 2) : w[0]);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (head(parts[0]) + head(parts[1])).toUpperCase();
}

function playerAvatar(p, cls) {
  if (p.photo) return playerPhoto(p, cls);
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
  img.onerror = () => img.remove();
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
  const born = (det && det.bornDate) ? new Date(det.bornDate) : null;
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

  // contract and salary — only what has actually been reported
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
      cc.appendChild(text("div", "contract-note", det.contract.note));
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
    sc.appendChild(text("div", "empty", "העונה טרם החלה — הנתונים יופיעו כאן אחרי המשחק הראשון"));
  }
  view.appendChild(sc);

  footer();
}

/* ---------- history, trophies and past stars ---------- */

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
      body.appendChild(text("div", "tl-title", e.title));
      body.appendChild(text("p", "tl-text", e.text));
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

  // eras, told through the coaches who shaped them
  if (h.coaches && h.coaches.length) {
    view.appendChild(text("div", "section-title", "עידני מאמנים"));
    h.coaches.forEach(c => {
      const card = el("div", "card coach-card" + (c.highlight ? " coach-big" : ""));
      const top = el("div", "coach-top");
      const who = el("div");
      who.appendChild(text("div", "coach-name", c.name));
      if (c.title) who.appendChild(text("div", "coach-title", c.title));
      top.appendChild(who);
      const yr = el("div", "coach-years" + (c.current ? " now" : ""));
      yr.textContent = c.years;
      top.appendChild(yr);
      card.appendChild(top);

      card.appendChild(text("p", "meet-summary", c.text));
      if (c.achievements && c.achievements.length) {
        const chips = el("div", "chips-row");
        c.achievements.forEach(a => chips.appendChild(text("span", "strength trophy-chip", "🏆 " + a)));
        card.appendChild(chips);
      }
      if (c.source) {
        const a = el("a", "meet-link muted-link");
        a.href = c.source; a.target = "_blank"; a.rel = "noopener";
        a.textContent = "המקור";
        card.appendChild(a);
      }
      view.appendChild(card);
    });
    if (h.coachesNote) {
      view.appendChild(text("div", "list-note", h.coachesNote));
    }
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
      c.appendChild(text("p", "meet-summary", l.text));
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
  frag.appendChild(text("div", "meet-headline", prof.headline));
  frag.appendChild(text("p", "meet-summary", prof.summary));

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
    prof.strengths.forEach(x => ul.appendChild(text("li", "", x)));
    b.appendChild(ul);
    frag.appendChild(b);
  }
  if (prof.weaknesses && prof.weaknesses.length) {
    const b = el("div", "cons");
    b.appendChild(text("div", "list-cap", "לשים לב"));
    const ul = el("ul");
    prof.weaknesses.forEach(x => ul.appendChild(text("li", "", x)));
    b.appendChild(ul);
    frag.appendChild(b);
  }
  if (prof.watch) {
    const w = el("div", "meet-watch");
    w.appendChild(text("span", "watch-label", "מה לשים לב"));
    w.appendChild(text("span", "", prof.watch));
    frag.appendChild(w);
  }
  if (prof.role) {
    const r = el("div", "role-box");
    r.appendChild(text("span", "watch-label", "התפקיד בירושלים"));
    r.appendChild(text("span", "", prof.role));
    frag.appendChild(r);
  }
  if (prof.comparison) {
    const c = el("div", "chips-row");
    c.appendChild(text("span", "strength compare", "משווים אותו ל" + prof.comparison));
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
    view.appendChild(text("div", "empty", "הדוחות בהכנה — נעדכן בקרוב"));
  }
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
  // Hapoel Jerusalem–Maccabi Tel Aviv is the קלאסיקו; a דרבי would mean
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
    }, hint: "5 נצחונות ברצף" },
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
    e.innerHTML = 'עוד לא סימנת אף משחק.<br>בלשונית ״משחקים״ סמנו ״הייתי שם״ — והיומן יתחיל להיבנות.<br><br>' +
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
    rec.appendChild(text("span", "val", s.wins + "–" + s.losses));
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
      end.appendChild(text("div", "t score", e.us + "–" + e.them));
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
  if (s.played) lines.push("המאזן שלי: " + s.wins + "–" + s.losses);
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
  view.appendChild(f);
}

boot();
