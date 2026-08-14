"use strict";

const TEAM = "הפועל ירושלים";
const state = { games: null, standings: null, meta: null, club: null, gamesTab: "upcoming" };

const view = document.getElementById("view");

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(path + " → " + res.status);
  return res.json();
}

async function boot() {
  try {
    const [games, standings, meta, club] = await Promise.all([
      loadJSON("data/games.json"),
      loadJSON("data/standings.json"),
      loadJSON("data/meta.json"),
      loadJSON("data/club.json"),
    ]);
    state.games = games;
    state.standings = standings;
    state.meta = meta;
    state.club = club;
    if (meta.sample) document.getElementById("sampleBanner").hidden = false;
  } catch (e) {
    view.innerHTML = '<div class="empty">לא הצלחנו לטעון את הנתונים.<br>בדקו את החיבור ונסו לרענן.</div>';
    return;
  }
  window.addEventListener("hashchange", render);
  render();
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

function isHome(g) { return g.home === TEAM; }
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

function daysUntil(dateStr) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const d = new Date(dateStr);
  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  return Math.round((day - today) / 86400000);
}
function countdownLabel(dateStr) {
  const n = daysUntil(dateStr);
  if (n === 0) return "היום!";
  if (n === 1) return "מחר";
  return "בעוד " + n + " ימים";
}

/* ---------- routing ---------- */

const routes = { "": renderHome, "#/": renderHome, "#/games": renderGames, "#/table": renderTable };

function render() {
  const hash = location.hash || "#/";
  const fn = routes[hash] || renderHome;
  const routeName = hash === "#/games" ? "games" : hash === "#/table" ? "table" : "home";
  document.querySelectorAll(".tabbar a").forEach(a =>
    a.classList.toggle("active", a.dataset.route === routeName));
  view.innerHTML = "";
  fn();
  window.scrollTo(0, 0);
}

/* ---------- home ---------- */

function renderHome() {
  const next = upcoming()[0];
  const last = finished()[0];

  if (next) {
    const c = el("div", "card next-game");
    c.appendChild(text("div", "eyebrow", "המשחק הבא"));
    c.appendChild(text("div", "opponent", "נגד " + opponent(next)));
    c.appendChild(text("div", "comp", next.competition + (next.round ? " · " + next.round : "")));
    const when = el("div", "when");
    const d = new Date(next.date);
    when.appendChild(text("span", "", fmtFull.format(d)));
    when.appendChild(text("span", "time", fmtTime.format(d)));
    c.appendChild(when);
    const meta = el("div", "meta-row");
    meta.appendChild(text("span", "badge" + (isHome(next) ? " home" : ""), isHome(next) ? "משחק בית" : "משחק חוץ"));
    meta.appendChild(text("span", "badge countdown", countdownLabel(next.date)));
    if (next.venue) meta.appendChild(text("span", "badge", next.venue));
    c.appendChild(meta);
    view.appendChild(c);
  } else {
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
    right.appendChild(text("div", "teams", "נגד " + opponent(last)));
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
    const usIdx = rows.findIndex(r => r.team === TEAM);
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
  const row = el("div", "game-row");
  const d = new Date(g.date);

  const date = el("div", "date-block");
  date.appendChild(text("div", "d", String(d.getDate())));
  date.appendChild(text("div", "m", MONTHS_SHORT[d.getMonth()]));
  row.appendChild(date);

  const info = el("div", "info");
  info.appendChild(text("div", "opp", "נגד " + opponent(g)));
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
  return row;
}

/* ---------- table ---------- */

function renderTable() {
  view.appendChild(text("div", "section-title",
    "טבלת " + state.standings.competition + " · עונת " + state.standings.season));
  const c = el("div", "card table-card");
  c.appendChild(standingsTable(state.standings.rows, true));
  view.appendChild(c);
  footer();
}

function standingsTable(rows, full) {
  const t = el("table", "standings");
  const head = el("tr");
  ["#", "קבוצה", "מש׳", "נצ׳", "הפ׳"].forEach((h, i) => {
    const th = el("th", i === 1 ? "team" : "");
    th.textContent = h;
    head.appendChild(th);
  });
  t.appendChild(head);
  rows.forEach(r => {
    const tr = el("tr", r.team === TEAM ? "us" : "");
    tr.appendChild(text("td", "num", String(r.pos)));
    tr.appendChild(text("td", "team", r.team));
    tr.appendChild(text("td", "num", String(r.played)));
    tr.appendChild(text("td", "num", String(r.wins)));
    tr.appendChild(text("td", "num", String(r.losses)));
    t.appendChild(tr);
  });
  return t;
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
