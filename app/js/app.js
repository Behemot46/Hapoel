"use strict";

const TEAM = "הפועל ירושלים";
const state = {
  games: null, standings: null, meta: null, club: null,
  gamesTab: "upcoming", diaryScope: "season",
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
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(path + " → " + res.status);
  return res.json();
}

async function boot() {
  try {
    const [games, standings, meta, club, roster, names, profiles] = await Promise.all([
      loadJSON("data/games.json"),
      loadJSON("data/standings.json"),
      loadJSON("data/meta.json"),
      loadJSON("data/club.json"),
      loadJSON("data/roster.json").catch(() => ({ players: [] })),
      loadJSON("data/player-names.json").catch(() => ({})),
      loadJSON("data/player-profiles.json").catch(() => ({})),
    ]);
    state.games = games;
    state.standings = standings;
    state.meta = meta;
    state.club = club;
    state.roster = roster;
    state.playerNames = names || {};
    state.profiles = profiles || {};
    if (meta.sample) document.getElementById("sampleBanner").hidden = false;
    refreshDiary();
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

// the league lists the club under its sponsored or abbreviated name
// ("הפועל י-ם"), so match loosely
function isUs(name) {
  if (!name || !name.includes("הפועל")) return false;
  return ["ירושלים", "י-ם", "י־ם", 'י"ם', "י״ם"].some(j => name.includes(j));
}
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

const routes = {
  "": renderHome, "#/": renderHome, "#/games": renderGames,
  "#/table": renderTable, "#/roster": renderRoster, "#/diary": renderDiary,
  "#/meet": renderMeet,
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
    : hash === "#/diary" ? "diary" : "home";
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
  const wrap = el("div", "game-card");
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
  view.appendChild(text("div", "section-title",
    "טבלת " + state.standings.competition + " · עונת " + state.standings.season));
  const c = el("div", "card table-card");
  c.appendChild(standingsTable(state.standings.rows, true));
  view.appendChild(c);
  footer();
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
    if (p.photo) row.appendChild(playerPhoto(p, "thumb"));
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

function playerPhoto(p, cls) {
  const img = document.createElement("img");
  img.className = "player-photo " + (cls || "");
  img.src = p.photo;
  img.alt = playerName(p);
  img.loading = "lazy";
  img.onerror = () => img.remove();
  return img;
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
  if (p.photo) card.appendChild(playerPhoto(p, "big"));
  if (p.number != null) card.appendChild(text("div", "big-shirt", String(p.number)));
  card.appendChild(playerNameEl(p, "player-title"));
  if (p.position) card.appendChild(text("div", "player-pos", p.position));
  view.appendChild(card);

  // the shirt number is already the badge above, so it is not repeated here
  const facts = [
    ["גובה", p.height ? p.height + " ס״מ" : null],
    ["שנתון", p.born || null],
    ["מדינה", p.country || null],
  ].filter(([, v]) => v !== null && v !== undefined);
  if (facts.length) {
    const grid = el("div", "facts");
    facts.forEach(([l, v]) => {
      const cell = el("div", "fact");
      cell.appendChild(text("div", "fv", String(v)));
      cell.appendChild(text("div", "fl", l));
      grid.appendChild(cell);
    });
    view.appendChild(grid);
  }

  const prof = profileOf(p);
  if (prof) {
    view.appendChild(text("div", "section-title", "מי הוא"));
    const pc = el("div", "card");
    pc.appendChild(text("div", "meet-headline", prof.headline));
    pc.appendChild(text("p", "meet-summary", prof.summary));
    if (prof.strengths && prof.strengths.length) {
      const chips = el("div", "chips-row");
      prof.strengths.forEach(s => chips.appendChild(text("span", "strength", s)));
      pc.appendChild(chips);
    }
    if (prof.watch) {
      const w = el("div", "meet-watch");
      w.appendChild(text("span", "watch-label", "מה לשים לב"));
      w.appendChild(text("span", "", prof.watch));
      pc.appendChild(w);
    }
    if (prof.source) {
      const src = el("a", "meet-link muted-link");
      src.href = prof.source;
      src.target = "_blank";
      src.rel = "noopener";
      src.textContent = "המקור";
      pc.appendChild(src);
    }
    view.appendChild(pc);
  }

  // season averages arrive once games are played
  view.appendChild(text("div", "section-title", "סטטיסטיקת עונה"));
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

/* ---------- meet the squad ---------- */

function profileOf(p) {
  const src = state.profiles || {};
  if (src[p.name]) return src[p.name];
  // fall back to a surname match, so "Kenneth" vs "Kenny" still lands
  const last = (p.name || "").split(" ").pop().toLowerCase();
  const key = Object.keys(src).find(k => k !== "_comment" && k.toLowerCase().endsWith(last));
  return key ? src[key] : null;
}

function renderMeet() {
  const players = ((state.roster && state.roster.players) || []).slice()
    .sort((a, b) => (a.number ?? 999) - (b.number ?? 999));

  const intro = el("div", "card meet-intro");
  intro.appendChild(text("div", "eyebrow", "בואו נכיר"));
  intro.appendChild(text("div", "meet-title", "מי הם החבר׳ה האלה?"));
  intro.appendChild(text("p", "",
    "סגל חדש ברובו. ריכזנו לכל שחקן את מה שכתבו עליו סקאוטים ואת המספרים מהקריירה שלו, כדי שתגיעו למשחק הראשון ותדעו את מי אתם מריעים."));
  intro.appendChild(text("p", "meet-note",
    "הפרופילים נכתבו על ידי אוהדים על בסיס דוחות סקאוטינג ונתונים פומביים, ומצורף מקור לכל שחקן. אינם מטעם המועדון."));
  view.appendChild(intro);

  let written = 0;
  players.forEach(p => {
    const prof = profileOf(p);
    if (!prof) return;
    written++;
    const c = el("div", "card meet-card");

    const head = el("div", "meet-head");
    const num = el("div", "shirt");
    num.textContent = p.number != null ? p.number : "–";
    head.appendChild(num);
    if (p.photo) head.appendChild(playerPhoto(p, "thumb"));
    const who = el("div", "info");
    who.appendChild(playerNameEl(p));
    const bits = [];
    if (p.position) bits.push(p.position);
    if (p.height) bits.push(p.height + " ס״מ");
    if (p.country) bits.push(p.country);
    if (bits.length) who.appendChild(text("div", "sub", bits.join(" · ")));
    head.appendChild(who);
    c.appendChild(head);

    c.appendChild(text("div", "meet-headline", prof.headline));
    c.appendChild(text("p", "meet-summary", prof.summary));

    if (prof.strengths && prof.strengths.length) {
      const chips = el("div", "chips-row");
      prof.strengths.forEach(s => chips.appendChild(text("span", "strength", s)));
      c.appendChild(chips);
    }
    if (prof.watch) {
      const w = el("div", "meet-watch");
      w.appendChild(text("span", "watch-label", "מה לשים לב"));
      w.appendChild(text("span", "", prof.watch));
      c.appendChild(w);
    }

    const links = el("div", "meet-links");
    const page = el("a", "meet-link");
    page.href = "#/player/" + encodeURIComponent(p.slug || slugOf(p));
    page.textContent = "לעמוד השחקן";
    links.appendChild(page);
    if (prof.source) {
      const src = el("a", "meet-link muted-link");
      src.href = prof.source;
      src.target = "_blank";
      src.rel = "noopener";
      src.textContent = "המקור";
      links.appendChild(src);
    }
    c.appendChild(links);
    view.appendChild(c);
  });

  if (!written) {
    view.appendChild(text("div", "empty", "הפרופילים בהכנה — נעדכן בקרוב"));
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
    info.appendChild(text("div", "opp", "נגד " + e.opponent));
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
