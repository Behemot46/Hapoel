"use strict";

// **ניתוח מתקדם: הגרפים והמדדים שנבנים מ־advanced.json.**
//
// הקובץ נטען לפני app.js ומגדיר רק פונקציות, בלי שום קוד שרץ מיד. הוא
// משתמש בעזרים של app.js (el, text, prose, num, gameById, teamName ועוד)
// רק בזמן הציור, וכשזה קורה שני הקבצים כבר נטענו.
//
// **כלל אחד לכיוון, בכל הגרפים: יותר זה שמאלה.** באפליקציה מימין לשמאל
// פס מתמלא מימין, והתקדמות היא לכיוון שמאל. לכן פס של ניצחון נמתח שמאלה
// מהציר, הרבע הראשון יושב מימין והרביעי משמאל, וגם בגרף הפיזור שחקן
// שמשתמש ביותר התקפות יושב שמאלה יותר. מי שלמד את זה בגרף אחד קורא נכון
// את כולם.
//
// **ושני צבעים בלבד.** אדום המועדון לנו, ואפור ליריבות או להפסד. זו לא
// פלטה של זהויות אלא הדגשה: הסיפור הוא תמיד הפועל, והשאר הקשר. האפור
// נבחר כך שיתבדל מהאדום גם בעיוורון צבעים (נבדק במדד ΔE של OKLab מול
// סימולציה של פרוטנופיה ודויטרנופיה, 11.4 בבהיר ו־8.9 בכהה), ובכהה הוא
// מתחת ל־3:1 מול הרקע, ולכן כל סימן אפור נושא גם מספר כתוב לידו.

const SVGNS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, parent) {
  const n = document.createElementNS(SVGNS, tag);
  Object.keys(attrs || {}).forEach(k => n.setAttribute(k, attrs[k]));
  if (parent) parent.appendChild(n);
  return n;
}

// **טקסט עברי בתוך SVG חייב כיוון משלו.** ה־SVG עצמו מוגדר משמאל לימין,
// כדי שהעיגון יתנהג כמו בגיאומטריה, אבל אז ״10 מתוך 12״ מצויר כך שקורא
// עברית קורא ״12 מתוך 10״, והגרש של ״מילטיץ׳״ קופץ לצד הלא נכון. נמדד
// בצילום מסך ב־1.11.2026. לכן כל תווית עם אות עברית מקבלת כיוון מימין
// לשמאל, והעיגון מתהפך כדי שהיא תישאר באותו מקום על המסך: ״end״ במובן
// הגיאומטרי, כלומר טקסט שנגמר בנקודה ונמשך שמאלה, הוא ״start״ בעברית.
const HEBREW = /[\u0590-\u05FF]/;

function svgText(parent, x, y, str, cls, anchor) {
  let a = anchor || "middle";
  const rtl = HEBREW.test(str);
  if (rtl && a !== "middle") a = a === "end" ? "start" : "end";
  const t = svgEl("text", { x, y, class: cls || "viz-label", "text-anchor": a }, parent);
  if (rtl) {
    t.setAttribute("direction", "rtl");
    t.style.direction = "rtl";
  }
  t.textContent = str;
  return t;
}

// הפרש עם סימן תמיד, כי ״4.2״ בלי פלוס נקרא כמו נתון ולא כמו יתרון
function signed(v, digits) {
  if (v === null || v === undefined) return "-";
  const s = Number(v).toFixed(digits === undefined ? 1 : digits);
  return v > 0 ? "+" + s : s;
}

// **כל מספר בטקסט של הגרפים מבודד, לא רק תוצאות.** prose() של app.js
// מבודד צמדים כמו ״90-83״, וזה מספיק לדיווח. כאן יש גם ״+4.2״ ו־״29.7%״,
// ובצילום מסך ב־1.11.2026 ״שימוש 29.7%, קליעה...״ נצבע בהסבר הצף עם
// האחוז בצד הלא נכון. לכן כל מספר, עם סימן ועם אחוז, נעטף ב־bdi.
// המספר נגמר בספרה, כדי שנקודה או פסיק בסוף משפט לא ייכנסו לבידוד ויצוירו
// בצד הלא נכון של המספר
const NUM_TOKEN = /[+\-]?\d(?:[\d,.]*\d)?(?:\s?[\u2011\-\u2013:/]\s?\d(?:[\d,.]*\d)?)*%?/g;

function vprose(tag, cls, str) {
  const node = el(tag, cls);
  const s = String(str == null ? "" : str);
  let last = 0;
  s.replace(NUM_TOKEN, (m, i) => {
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

function fix1(v) {
  return v === null || v === undefined ? "-" : Number(v).toFixed(1);
}

const QUARTER_NAMES = ["הראשון", "השני", "השלישי", "הרביעי"];
const GROUP_NAMES = { league: "ליגה", eurocup: "יורוקאפ", cup: "גביע" };

function advanced() {
  return state.advanced || null;
}

function advancedGame(id) {
  const a = advanced();
  return a ? (a.games || []).find(g => g.gameId === id) || null : null;
}

function advancedPlayer(slug) {
  const a = advanced();
  return a ? (a.players || []).find(p => p.slug === slug) || null : null;
}

// מי נכנס לגרפים של שחקנים: מי ששיחק מספיק כדי שהאחוז שלו יגיד משהו.
// שמונים דקות הן בערך שלושה משחקים של תפקיד אמיתי. מתחת לזה זריקה אחת
// מזיזה את האחוז בעשרות נקודות, וגרף שמציג את זה כאילו זה נתון משקר.
const MIN_MINUTES = 80;

function rotation() {
  const a = advanced();
  if (!a) return [];
  return (a.players || []).filter(p => p.min >= MIN_MINUTES);
}

/* ---------- tooltip ---------- */

// **הסבר צף לכל סימן, במעבר עכבר, בפוקוס של מקלדת ובנגיעה.** הוא מוסיף
// ולא חוסם: כל מספר שהוא מראה כתוב גם על הגרף או בטבלה שלידו.
function vizTip(wrap) {
  let tip = wrap.querySelector(".viz-tip");
  if (!tip) {
    tip = el("div", "viz-tip");
    tip.setAttribute("role", "status");
    tip.hidden = true;
    wrap.appendChild(tip);
  }
  return tip;
}

function bindTip(mark, wrap, lines, href) {
  const tip = vizTip(wrap);
  mark.setAttribute("tabindex", "0");
  mark.setAttribute("aria-label", lines.join(", "));
  const show = () => {
    tip.textContent = "";
    lines.forEach((l, i) => tip.appendChild(vprose("div", i === 0 ? "viz-tip-head" : "", l)));
    tip.hidden = false;
    const w = wrap.getBoundingClientRect();
    const m = mark.getBoundingClientRect();
    const tw = tip.offsetWidth;
    let left = m.left - w.left + m.width / 2 - tw / 2;
    left = Math.max(4, Math.min(left, w.width - tw - 4));
    let top = m.top - w.top - tip.offsetHeight - 8;
    if (top < 0) top = m.bottom - w.top + 8;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
    mark.classList.add("viz-hot");
  };
  const hide = () => { tip.hidden = true; mark.classList.remove("viz-hot"); };
  mark.addEventListener("pointerenter", show);
  mark.addEventListener("pointerleave", hide);
  mark.addEventListener("focus", show);
  mark.addEventListener("blur", hide);
  if (href) {
    mark.style.cursor = "pointer";
    mark.addEventListener("click", () => { location.hash = href; });
    mark.addEventListener("keydown", e => { if (e.key === "Enter") location.hash = href; });
  } else {
    mark.addEventListener("click", show);
  }
}

/* ---------- building blocks ---------- */

// שורת מדדים ראשיים. המספר הגדול הוא הסיפור, והשורה שמתחתיו אומרת במה
// הוא נמדד, כי ״117.4״ בלי יחידה הוא סתם מספר.
function kpiRow(items) {
  const row = el("div", "kpi-row");
  items.forEach(it => {
    const c = el("div", "kpi");
    c.appendChild(text("div", "kpi-label", it.label));
    const v = el("div", "kpi-value" + (it.tone ? " " + it.tone : ""));
    v.appendChild(num(it.value));
    c.appendChild(v);
    if (it.sub) c.appendChild(text("div", "kpi-sub", it.sub));
    row.appendChild(c);
  });
  return row;
}

function legend(items) {
  const l = el("div", "viz-legend");
  items.forEach(([cls, label]) => {
    const i = el("span", "viz-key");
    i.appendChild(el("span", "viz-swatch " + cls));
    i.appendChild(text("span", "", label));
    l.appendChild(i);
  });
  return l;
}

// **השוואה של שני פסים, לנו וליריבה, לכל שורה.** בניתי את זה ב־HTML ולא
// ב־SVG, כי פס בתוך מיכל מימין לשמאל כבר מתמלא מימין, והטקסט העברי
// מסתדר בלי שום חישוב. הערך כתוב בקצה של כל פס.
function compareRows(rows, names) {
  const box = el("div", "cmp");
  box.appendChild(legend([["us", names[0]], ["them", names[1]]]));
  rows.forEach(r => {
    if (r.us === null || r.us === undefined || r.them === null || r.them === undefined) return;
    const row = el("div", "cmp-row");
    const head = el("div", "cmp-head");
    head.appendChild(text("span", "cmp-label", r.label));
    const better = r.lowIsGood ? r.us < r.them : r.us > r.them;
    const even = r.us === r.them;
    if (!even && r.verdict !== false) {
      head.appendChild(text("span", "cmp-verdict" + (better ? " good" : ""),
        better ? "לטובתנו" : "לטובת " + (r.themShort || "היריבות")));
    }
    row.appendChild(head);
    if (r.note) row.appendChild(text("div", "cmp-note", r.note));
    const max = r.max || Math.max(r.us, r.them) * 1.15 || 1;
    [["us", r.us], ["them", r.them]].forEach(([side, v]) => {
      const line = el("div", "cmp-line");
      const track = el("div", "cmp-track");
      const fill = el("div", "cmp-fill " + side);
      fill.style.width = Math.max(1.5, Math.min(100, 100 * v / max)) + "%";
      track.appendChild(fill);
      line.appendChild(track);
      const strong = r.verdict !== false && !even && (side === "us") === better;
      const val = el("span", "cmp-val" + (strong ? " strong" : ""));
      val.appendChild(num(fix1(v) + (r.suffix || "")));
      line.appendChild(val);
      row.appendChild(line);
    });
    box.appendChild(row);
  });
  return box;
}

function fourFactorRows(four, themShort) {
  return [
    { label: "קליעה אפקטיבית", note: "קליעה מהשדה, כשלשה שווה חצי סל יותר",
      us: four.us.efg, them: four.them.efg, suffix: "%", max: 70, themShort },
    { label: "איבודים", note: "לכל 100 החזקות. כאן פחות זה טוב",
      us: four.us.tov, them: four.them.tov, lowIsGood: true, max: 30, themShort },
    { label: "ריבאונד בהתקפה", note: "כמה מהכדורים החוזרים בהתקפה לקחנו",
      us: four.us.orb, them: four.them.orb, suffix: "%", max: 55, themShort },
    { label: "הגעה לקו", note: "קליעות עונשין לכל 100 זריקות מהשדה",
      us: four.us.ftr, them: four.them.ftr, max: 45, themShort },
  ];
}

function tableTwin(head, rows) {
  const d = el("details", "viz-table");
  d.appendChild(text("summary", "", "הצגה כטבלה"));
  const t = el("table", "standings stats-table");
  const tr = el("tr");
  head.forEach((h, i) => tr.appendChild(text("th", i === 0 ? "team" : "", h)));
  t.appendChild(tr);
  rows.forEach(r => {
    const row = el("tr");
    r.forEach((c, i) => {
      const td = el("td", i === 0 ? "team" : "num");
      if (i === 0) td.textContent = c; else td.appendChild(num(String(c)));
      row.appendChild(td);
    });
    t.appendChild(row);
  });
  d.appendChild(t);
  return d;
}

/* ---------- charts ---------- */

// **הפרש הנקודות בכל משחק, כפס שיוצא מהציר.** שורה לכל משחק עם שם
// היריבה, כי בטלפון שתים עשרה תוויות לא נכנסות מתחת לעמודות. כל שורה
// היא קישור לעמוד המשחק.
function marginChart(games) {
  const box = el("div", "margins");
  const max = Math.max(10, ...games.map(g => Math.abs(g.us - g.them)));
  games.forEach(g => {
    const fx = gameById(g.gameId);
    const opp = fx ? teamName(opponent(fx)) : "";
    const d = g.us - g.them;
    const row = el("a", "mg-row");
    row.href = "#/game/" + encodeURIComponent(g.gameId);
    const who = el("div", "mg-who");
    who.appendChild(text("span", "mg-opp", opp));
    who.appendChild(text("span", "mg-date", fmtUpdatedDate.format(new Date(g.date))));
    row.appendChild(who);
    const area = el("div", "mg-area");
    area.appendChild(el("div", "mg-axis"));
    const bar = el("div", "mg-bar " + (d >= 0 ? "win" : "loss"));
    const w = 50 * Math.abs(d) / max;
    bar.style.width = Math.max(1, w) + "%";
    area.appendChild(bar);
    const v = el("span", "mg-val " + (d >= 0 ? "win" : "loss"));
    v.appendChild(num(signed(d, 0)));
    // הערך יושב בקצה של הפס, מחוץ לו
    if (d >= 0) v.style.right = "calc(50% + " + w + "% + 4px)";
    else v.style.left = "calc(50% + " + w + "% + 4px)";
    area.appendChild(v);
    row.appendChild(area);
    row.setAttribute("aria-label", opp + ", " + (d >= 0 ? "ניצחון" : "הפסד") + " " +
      g.us + "-" + g.them + ", " + signed(g.net) + " ל־100 החזקות");
    box.appendChild(row);
  });
  return box;
}

// **ההפרש הממוצע בכל רבע, כעמודות מעל ומתחת לאפס.** הרבע הראשון מימין.
function quarterChart(wrap, q) {
  const W = Math.max(280, wrap.clientWidth || 320);
  const H = 190;
  const top = 26, bottom = 46, pad = 12;
  const plotH = H - top - bottom;
  // **הציר במקום שהנתונים צריכים, ולא תמיד באמצע.** כשכל ארבעת הרבעים
  // בפלוס, חצי גרף ריק מתחת לאפס הוא מקום שהעמודות לא מקבלות. נמדד
  // בצילום מסך ב־1.11.2026: העמודות תפסו רבע מהגובה.
  // התחום כולל תמיד את האפס, ועוד מרווח קטן מעל ומתחת לתוויות
  const hi = Math.max(0, ...q.avg), lo = Math.min(0, ...q.avg);
  const pad2 = Math.max(4, hi - lo) * 0.08;
  const dHi = hi + (hi > 0 ? pad2 : 0), dLo = lo - (lo < 0 ? pad2 : 0);
  const max = Math.max(1, dHi - dLo);
  const s = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz-svg",
    role: "img", "aria-label": "ההפרש הממוצע בכל רבע: " +
      q.avg.map((v, i) => "רבע " + (i + 1) + " " + signed(v)).join(", ") });
  s.style.direction = "ltr";
  const zero = top + dHi / max * plotH;
  svgEl("line", { x1: pad, x2: W - pad, y1: zero, y2: zero, class: "viz-base" }, s);
  const slot = (W - 2 * pad) / 4;
  const bw = Math.min(28, slot * 0.4);
  q.avg.forEach((v, i) => {
    // הרבע הראשון מימין: מימין לשמאל, כמו הקריאה
    const cx = W - pad - slot * (i + 0.5);
    const h = Math.abs(v) / max * plotH;
    const y = v >= 0 ? zero - h : zero;
    const r = Math.min(4, h);
    // פינות מעוגלות רק בקצה של הנתון, ישרות על הציר
    const path = v >= 0
      ? `M${cx - bw / 2},${zero} V${y + r} Q${cx - bw / 2},${y} ${cx - bw / 2 + r},${y} H${cx + bw / 2 - r} Q${cx + bw / 2},${y} ${cx + bw / 2},${y + r} V${zero} Z`
      : `M${cx - bw / 2},${zero} V${zero + h - r} Q${cx - bw / 2},${zero + h} ${cx - bw / 2 + r},${zero + h} H${cx + bw / 2 - r} Q${cx + bw / 2},${zero + h} ${cx + bw / 2},${zero + h - r} V${zero} Z`;
    const bar = svgEl("path", { d: path, class: "viz-bar " + (v >= 0 ? "us" : "them") }, s);
    svgText(s, cx, v >= 0 ? y - 7 : zero + h + 15, signed(v), "viz-value");
    svgText(s, cx, H - 26, "רבע " + (i + 1), "viz-tick");
    svgText(s, cx, H - 10, q.won[i] + " מתוך " + q.games, "viz-tick muted");
    const hit = svgEl("rect", { x: cx - slot / 2 + 2, y: top - 10, width: slot - 4,
      height: plotH + 20, class: "viz-hit" }, s);
    bindTip(hit, wrap, ["רבע " + (i + 1) + ": " + signed(v) + " בממוצע",
      "ניצחנו בו ב־" + q.won[i] + " משחקים, הפסדנו ב־" + q.lost[i]]);
    hit.addEventListener("focus", () => bar.classList.add("viz-hot"));
    hit.addEventListener("blur", () => bar.classList.remove("viz-hot"));
  });
  wrap.appendChild(s);
}

// **מהלך משחק לפי רבעים: ההפרש המצטבר אחרי כל רבע.** חמש נקודות בלבד,
// כי זה מה שהטופס יודע. קו של מהלך אחר מהלך היה יפה יותר, וגם היה
// המצאה.
function flowChart(wrap, quarters, oppName) {
  const W = Math.max(280, wrap.clientWidth || 320);
  const H = 170;
  const top = 22, bottom = 30, padR = 18, padL = 44;
  const pts = [{ q: 0, d: 0, us: 0, them: 0 }];
  let us = 0, them = 0;
  quarters.forEach((p, i) => {
    us += p[0]; them += p[1];
    pts.push({ q: i + 1, d: us - them, us, them });
  });
  const max = Math.max(6, ...pts.map(p => Math.abs(p.d))) * 1.2;
  const plotH = H - top - bottom;
  const zero = top + plotH / 2;
  const n = pts.length - 1;
  const x = i => W - padR - (W - padR - padL) * i / n;
  const y = d => zero - d / max * (plotH / 2);
  const s = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz-svg",
    role: "img", "aria-label": "ההפרש אחרי כל רבע: " +
      pts.slice(1).map(p => "רבע " + p.q + " " + signed(p.d, 0)).join(", ") });
  s.style.direction = "ltr";
  svgEl("line", { x1: padL, x2: W - padR, y1: zero, y2: zero, class: "viz-base" }, s);
  svgText(s, padL - 6, zero + 4, "0", "viz-tick", "end");
  pts.forEach((p, i) => {
    if (i === 0) return;
    svgEl("line", { x1: x(i), x2: x(i), y1: top, y2: top + plotH, class: "viz-grid" }, s);
    svgText(s, x(i), H - 10, i <= 4 ? "רבע " + i : "הארכה", "viz-tick");
  });
  const d = pts.map((p, i) => (i ? "L" : "M") + x(i) + "," + y(p.d)).join(" ");
  svgEl("path", { d, class: "viz-line" }, s);
  pts.forEach((p, i) => {
    if (i === 0) return;
    const c = svgEl("circle", { cx: x(i), cy: y(p.d), r: 4.5, class: "viz-dot" }, s);
    const hit = svgEl("circle", { cx: x(i), cy: y(p.d), r: 14, class: "viz-hit" }, s);
    bindTip(hit, wrap, ["אחרי רבע " + p.q + ": " + signed(p.d, 0),
      "הפועל " + p.us + ", " + oppName + " " + p.them]);
    hit.addEventListener("pointerenter", () => c.classList.add("viz-hot"));
    hit.addEventListener("pointerleave", () => c.classList.remove("viz-hot"));
  });
  // התווית רק בסוף, כי שם הסיפור
  const last = pts[pts.length - 1];
  svgText(s, x(n) - 8, y(last.d) + 4, signed(last.d, 0), "viz-value", "end");
  wrap.appendChild(s);
}

// **נפח מול יעילות: כל נקודה היא שחקן.** שמאלה זה יותר התקפות שנגמרות
// אצלו, ולמעלה זה יותר נקודות מכל זריקה. הקווים הדקים הם הממוצע של
// הקבוצה, ולכן ארבעת הרבעים של הגרף מסבירים את עצמם.
function scatterChart(wrap, players, tsOf, avgUsg, avgTs) {
  const W = Math.max(290, wrap.clientWidth || 320);
  const H = Math.round(Math.min(360, W * 0.9));
  const top = 16, bottom = 40, padR = 40, padL = 14;
  const data = players.map(p => ({ p, u: p.usg, t: tsOf(p) }))
    .filter(d => d.u !== null && d.t !== null && d.t !== undefined);
  if (!data.length) return;
  const uMin = Math.floor(Math.min(...data.map(d => d.u), avgUsg) / 5) * 5 - 1;
  const uMax = Math.ceil(Math.max(...data.map(d => d.u), avgUsg) / 5) * 5 + 1;
  const tMin = Math.floor(Math.min(...data.map(d => d.t), avgTs) / 5) * 5 - 2;
  const tMax = Math.ceil(Math.max(...data.map(d => d.t), avgTs) / 5) * 5 + 2;
  const plotW = W - padR - padL, plotH = H - top - bottom;
  // יותר שימוש זה שמאלה
  const x = u => W - padR - (u - uMin) / (uMax - uMin) * plotW;
  const y = t => top + plotH - (t - tMin) / (tMax - tMin) * plotH;
  const s = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz-svg",
    role: "img", "aria-label": "אחוז שימוש מול קליעה אמיתית, לכל שחקן" });
  s.style.direction = "ltr";
  for (let t = Math.ceil(tMin / 5) * 5; t <= tMax; t += 5) {
    svgEl("line", { x1: padL, x2: W - padR, y1: y(t), y2: y(t), class: "viz-grid" }, s);
    svgText(s, W - padR + 6, y(t) + 4, t + "%", "viz-tick", "start");
  }
  for (let u = Math.ceil(uMin / 5) * 5; u <= uMax; u += 5) {
    svgText(s, x(u), H - 22, u + "%", "viz-tick");
  }
  svgEl("line", { x1: x(avgUsg), x2: x(avgUsg), y1: top, y2: top + plotH, class: "viz-avg" }, s);
  svgEl("line", { x1: padL, x2: W - padR, y1: y(avgTs), y2: y(avgTs), class: "viz-avg" }, s);
  svgText(s, x(avgUsg) - 4, top + 10, "ממוצע", "viz-tick muted", "end");
  // החץ בסוף המחרוזת: בעברית הוא נצבע בקצה השמאלי, ו־← לא מתהפך
  svgText(s, (padL + W - padR) / 2, H - 4, "יותר התקפות נגמרות אצלו ←", "viz-tick muted");

  // **תוויות בלי התנגשויות.** שם נכתב רק אם הוא לא דורס שם שכבר נכתב.
  // מי שלא קיבל תווית עדיין נגיש: בנגיעה, ובטבלה שמתחת.
  const placed = data.map(d => ({ x: x(d.u) - 6, y: y(d.t) - 6, w: 12, h: 12 }));
  const order = data.slice().sort((a, b) => b.p.min - a.p.min);
  const dots = svgEl("g", {}, s);
  order.forEach(d => {
    const cx = x(d.u), cy = y(d.t);
    svgEl("circle", { cx, cy, r: 5, class: "viz-dot" }, dots);
    const label = shortName(d.p.name);
    const w = label.length * 6.6 + 4;
    // התווית משמאל לנקודה, ואם אין מקום, מימין לה
    const own = { x: cx - 6, y: cy - 6, w: 12, h: 12 };
    const clash = box => placed.some(o => o !== own && !(box.x + box.w < o.x || o.x + o.w < box.x ||
                                         box.y + box.h < o.y || o.y + o.h < box.y) &&
                                     !(o.x === cx - 6 && o.y === cy - 6));
    const left = { x: cx - 8 - w, y: cy - 9, w, h: 13, tx: cx - 8, anchor: "end" };
    const right = { x: cx + 8, y: cy - 9, w, h: 13, tx: cx + 8, anchor: "start" };
    const spot = [left, right].find(b => b.x >= padL - 2 && b.x + b.w <= W - padR + 2 && !clash(b));
    if (spot) {
      placed.push(spot);
      svgText(s, spot.tx, cy + 4, label, "viz-name", spot.anchor);
    }
    const hit = svgEl("circle", { cx, cy, r: 13, class: "viz-hit" }, s);
    bindTip(hit, wrap, [d.p.name,
      "שימוש " + fix1(d.u) + "%, קליעה אמיתית " + fix1(d.t) + "%",
      d.p.games + " משחקים, " + fix1(d.p.mpg) + " דקות למשחק"],
      "#/player/" + encodeURIComponent(d.p.slug));
  });
  wrap.appendChild(s);
}

// שם משפחה בלבד בגרף צפוף, ושם מלא בהסבר הצף
function shortName(name) {
  const parts = String(name || "").trim().split(/\s+/);
  if (parts.length <= 1) return parts[0] || "";
  const last = parts[parts.length - 1];
  // ״לופטון ג׳וניור״: הסיומת לבדה היא לא שם
  if (/^(ג['׳]וניור|Jr\.?)$/i.test(last) && parts.length > 2) return parts[parts.length - 2];
  return last;
}

// **המדד בכל משחק, כעמודות לפי הסדר.** הראשון מימין והאחרון משמאל, והקו
// הדק הוא הממוצע שלו. כל עמודה פותחת את עמוד המשחק.
function pirChart(wrap, log, avg) {
  const games = (log || []).slice().sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  if (!games.length) return;
  const W = Math.max(280, wrap.clientWidth || 320);
  const H = 170;
  const top = 18, bottom = 26, padR = 10, padL = 30;
  const vals = games.map(g => Number(g.pir) || 0);
  const vMax = Math.max(10, ...vals) * 1.15;
  const vMin = Math.min(0, ...vals);
  const plotH = H - top - bottom;
  const y = v => top + plotH - (v - vMin) / (vMax - vMin) * plotH;
  const slot = (W - padR - padL) / games.length;
  const bw = Math.max(4, Math.min(18, slot * 0.6));
  const s = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz-svg",
    role: "img", "aria-label": "מדד בכל משחק: " + vals.join(", ") });
  s.style.direction = "ltr";
  const base = y(0);
  svgEl("line", { x1: padL, x2: W - padR, y1: base, y2: base, class: "viz-base" }, s);
  games.forEach((g, i) => {
    const v = vals[i];
    const cx = W - padR - slot * (i + 0.5);
    const h = Math.abs(y(v) - base);
    const yy = v >= 0 ? base - h : base;
    const r = Math.min(3, h / 2);
    svgEl("rect", { x: cx - bw / 2, y: yy, width: bw, height: Math.max(1, h), rx: r,
      class: "viz-bar " + (v >= 0 ? "us" : "them") }, s);
    const fx = gameById(g.gameId);
    const opp = fx ? teamName(opponent(fx)) : (g.opponent || "");
    const hit = svgEl("rect", { x: cx - slot / 2, y: top, width: slot, height: plotH + 4,
      class: "viz-hit" }, s);
    bindTip(hit, wrap, [opp + ", " + fmtUpdatedDate.format(new Date(g.date)),
      (g.win ? "ניצחון " : "הפסד ") + g.us + "-" + g.them,
      "מדד " + v + ", " + (g.pts == null ? 0 : g.pts) + " נקודות"],
      "#/game/" + encodeURIComponent(g.gameId));
  });
  if (avg !== null && avg !== undefined) {
    svgEl("line", { x1: padL, x2: W - padR, y1: y(avg), y2: y(avg), class: "viz-avg" }, s);
    svgText(s, padL - 4, y(avg) + 4, fix1(avg), "viz-tick", "end");
  }
  // התווית רק על השיא
  const bi = vals.indexOf(Math.max(...vals));
  svgText(s, W - padR - slot * (bi + 0.5), y(vals[bi]) - 5, String(vals[bi]), "viz-value");
  svgText(s, W - padR - slot * 0.5, H - 8, "ראשון", "viz-tick muted");
  if (games.length > 1) svgText(s, padL + slot * 0.5, H - 8, "אחרון", "viz-tick muted");
  wrap.appendChild(s);
}

/* ---------- the stats page ---------- */

// **הקבוצה במספרים מתקדמים: ראש עמוד הסטטיסטיקה.** מה שהאוהד שואל אחרי
// ״כמה ניצחנו״ הוא ״למה״, וכאן התשובה מחולקת לפי מה שבאמת מכריע משחק.
function renderTeamAnalytics() {
  const a = advanced();
  if (!a || !a.team || !a.team.games) return;
  const t = a.team;

  view.appendChild(text("div", "section-title", "הקבוצה במספרים מתקדמים"));
  const top = el("div", "card");
  top.appendChild(text("div", "eyebrow",
    t.games + " משחקים רשמיים · " + t.wins + " ניצחונות"));
  top.appendChild(kpiRow([
    { label: "התקפה", value: fix1(t.ortg), sub: "נקודות ל־100 החזקות" },
    { label: "הגנה", value: fix1(t.drtg), sub: "ספגנו ל־100 החזקות" },
    { label: "הפרש", value: signed(t.net), sub: "ל־100 החזקות",
      tone: t.net >= 0 ? "good" : "" },
    { label: "קצב", value: fix1(t.pace), sub: "החזקות למשחק" },
  ]));
  top.appendChild(vprose("div", "viz-note",
    "החזקה היא התקפה אחת, מהרגע שהכדור אצלנו ועד שהוא עובר ליריבה. " +
    "נקודות ל־100 החזקות מנטרלות את הקצב: משחק מהיר מייצר יותר נקודות " +
    "לשתי הקבוצות, וזה לא אומר שהוא טוב יותר. מספר ההחזקות הוא ההערכה " +
    "המקובלת משורת הסה״כ, זו שבה משתמשים גם היורוליג ו־Basketball Reference."));
  view.appendChild(top);

  // ארבעת הגורמים
  const ff = el("div", "card");
  ff.appendChild(text("div", "eyebrow", "ארבעת הגורמים"));
  ff.appendChild(vprose("div", "viz-lede",
    "דין אוליבר הראה שכמעט כל משחק מוכרע בארבעה דברים: קליעה, שמירה על " +
    "הכדור, ריבאונד בהתקפה והגעה לקו. כאן אנחנו מול כל היריבות של העונה, " +
    "ביחד."));
  ff.appendChild(compareRows(fourFactorRows(t.four), ["הפועל", "היריבות"]));
  view.appendChild(ff);

  // מאיפה הנקודות
  if (t.share && t.share.us && t.share.them) {
    const sh = el("div", "card");
    sh.appendChild(text("div", "eyebrow", "מאיפה הנקודות"));
    sh.appendChild(compareRows([
      { label: "שתיים", us: t.share.us.p2, them: t.share.them.p2, suffix: "%", max: 70, verdict: false },
      { label: "שלוש", us: t.share.us.p3, them: t.share.them.p3, suffix: "%", max: 70, verdict: false },
      { label: "עונשין", us: t.share.us.ft, them: t.share.them.ft, suffix: "%", max: 70, verdict: false },
    ], ["הפועל", "היריבות"]));
    sh.appendChild(vprose("div", "viz-note",
      "החלק של כל סוג זריקה מכלל הנקודות. זה סגנון ולא ציון, ולכן אין " +
      "כאן ״לטובתנו״."));
    view.appendChild(sh);
  }

  // משחק אחר משחק
  const games = a.games || [];
  if (games.length) {
    const mc = el("div", "card");
    mc.appendChild(text("div", "eyebrow", "ההפרש בכל משחק"));
    mc.appendChild(marginChart(games));
    mc.appendChild(vprose("div", "viz-note",
      "ניצחון נמתח שמאלה, הפסד ימינה. לחיצה על שורה פותחת את המשחק."));
    view.appendChild(mc);
  }

  // רבעים
  const q = a.quarters;
  if (q && q.games) {
    const qc = el("div", "card");
    qc.appendChild(text("div", "eyebrow", "באיזה רבע אנחנו שוברים משחקים"));
    const best = q.avg.indexOf(Math.max(...q.avg));
    const worst = q.avg.indexOf(Math.min(...q.avg));
    let lede = "הרבע " + QUARTER_NAMES[best] + " הוא החזק שלנו: " + signed(q.avg[best]) +
      " בממוצע, וניצחנו בו ב־" + q.won[best] + " משחקים מתוך " + q.games + ".";
    if (worst !== best) {
      lede += q.avg[worst] >= 0
        ? " הכי פחות: הרבע " + QUARTER_NAMES[worst] + ", " + signed(q.avg[worst]) +
          ", וגם הוא בפלוס."
        : " והחלש: הרבע " + QUARTER_NAMES[worst] + ", " + signed(q.avg[worst]) + " בממוצע.";
    }
    qc.appendChild(vprose("div", "viz-lede", lede));
    const wrap = el("div", "viz");
    qc.appendChild(wrap);
    view.appendChild(qc);
    quarterChart(wrap, q);
    qc.appendChild(vprose("div", "viz-note",
      "ההפרש הממוצע בכל רבע, ומתחת כמה רבעים כאלה ניצחנו. הארכות לא נספרות."));
  }

  // לפי תחרות
  const split = a.split || {};
  const keys = ["league", "eurocup", "cup"].filter(k => split[k]);
  if (keys.length > 1) {
    const sc = el("div", "card table-card");
    sc.appendChild(text("div", "eyebrow split-eyebrow", "לפי תחרות"));
    const tb = el("table", "standings stats-table");
    const h = el("tr");
    ["תחרות", "מש׳", "התקפה", "הגנה", "הפרש"].forEach((x, i) =>
      h.appendChild(text("th", i === 0 ? "team" : "", x)));
    tb.appendChild(h);
    keys.forEach(k => {
      const r = split[k];
      const tr = el("tr");
      tr.appendChild(text("td", "team", GROUP_NAMES[k]));
      [String(r.games), fix1(r.ortg), fix1(r.drtg), signed(r.net)].forEach(v => {
        const td = el("td", "num");
        td.appendChild(num(v));
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    sc.appendChild(tb);
    view.appendChild(sc);
    view.appendChild(vprose("div", "table-note",
      "התקפה והגנה בנקודות ל־100 החזקות. מדגם קטן בכל תחרות, ולכן זה כיוון ולא פסק דין."));
  }
}

// **השחקנים במספרים מתקדמים: גרף הפיזור וטבלת השיעורים.**
function renderPlayerAnalytics() {
  const a = advanced();
  const rot = rotation();
  if (!a || rot.length < 3) return;
  const tsBySlug = {};
  ((state.playerSeason && state.playerSeason.players) || []).forEach(p => {
    tsBySlug[p.slug] = p.avg ? p.avg.ts : null;
  });
  const tsOf = p => tsBySlug[p.slug];
  const withTs = rot.filter(p => tsOf(p) !== null && tsOf(p) !== undefined && p.usg !== null);

  if (withTs.length >= 3) {
    view.appendChild(text("div", "section-title", "נפח מול יעילות"));
    const c = el("div", "card");
    c.appendChild(vprose("div", "viz-lede",
      "כל נקודה היא שחקן. ככל שהיא שמאלה יותר, יותר התקפות של הקבוצה " +
      "נגמרות אצלו. ככל שהיא גבוהה יותר, הוא מפיק יותר נקודות מכל זריקה. " +
      "הקווים הדקים הם הממוצע של הקבוצה."));
    const wrap = el("div", "viz");
    c.appendChild(wrap);
    view.appendChild(c);
    // הממוצע משוקלל בדקות, כי ממוצע פשוט נותן לשחקן ספסל משקל של פותח
    const mins = withTs.reduce((s, p) => s + p.min, 0);
    const avgUsg = withTs.reduce((s, p) => s + p.usg * p.min, 0) / mins;
    const avgTs = withTs.reduce((s, p) => s + tsOf(p) * p.min, 0) / mins;
    scatterChart(wrap, withTs, tsOf, avgUsg, avgTs);
    c.appendChild(tableTwin(["שחקן", "שימוש", "TS", "דק׳ למשחק"],
      withTs.map(p => [p.name, fix1(p.usg) + "%", fix1(tsOf(p)) + "%", fix1(p.mpg)])));
  }

  view.appendChild(text("div", "section-title", "שיעורים מתקדמים"));
  const rows = rot.slice().sort((x, y) => (y.usg || 0) - (x.usg || 0));
  const cols = [
    { key: "usg", label: "שימוש", from: r => pctOrDash(r.usg) },
    // בבידוד משמאל לימין, אחרת בכותרת עברית הוא מצויר ״-/+״
    { key: "pm", label: "\u2066+/-\u2069", from: r => signed(r.pmPer40) },
    { key: "ast", label: "אס׳", from: r => pctOrDash(r.ast) },
    { key: "reb", label: "ריב׳", from: r => pctOrDash(r.reb) },
    { key: "tov", label: "איב׳", from: r => pctOrDash(r.tov) },
  ];
  view.appendChild(seasonTable(rows, cols));
  view.appendChild(vprose("div", "table-note",
    "שימוש: כמה מההתקפות של הקבוצה נגמרות אצלו, בזריקה, בעונשין או באיבוד, " +
    "כשהוא על המגרש. אסיסטים וריבאונדים: איזה חלק מהסלים של חבריו הוא בישל, " +
    "ואיזה חלק מהכדורים הפנויים הוא לקח, בזמן שהיה על המגרש. איבודים: כמה " +
    "מהשימושים שלו נגמרו באיבוד. פלוס/מינוס: ההפרש כשהוא על המגרש, לכל 40 דקות. " +
    "רק מי ששיחק " + MIN_MINUTES + " דקות ומעלה."));
}

function pctOrDash(v) {
  return v === null || v === undefined ? "-" : fix1(v) + "%";
}

/* ---------- the game page ---------- */

const KEY_PHRASE = {
  efg: (u, t) => ["הקליעה", fix1(u.efg) + "% קליעה אפקטיבית, מול " + fix1(t.efg) + "% שלהם."],
  tov: (u, t) => ["השמירה על הכדור", fix1(u.tov) + " איבודים לכל 100 החזקות, מול " +
                   fix1(t.tov) + " שלהם."],
  orb: (u, t) => ["הריבאונד בהתקפה", "לקחנו " + fix1(u.orb) + "% מהכדורים החוזרים בהתקפה, " +
                   "הם " + fix1(t.orb) + "%."],
  ftr: (u, t) => ["קו העונשין", fix1(u.ftr) + " קליעות עונשין לכל 100 זריקות, מול " +
                   fix1(t.ftr) + " שלהם."],
};

// **ניתוח של משחק אחד, מתחת לתוצאה.** המשפט הראשון עונה על השאלה ״איפה
// זה הוכרע״, לפי ארבעת הגורמים במשקלות של אוליבר, ואחריו המספרים
// שמהם הוא נגזר, כדי שכל אחד יוכל לבדוק.
function renderGameAnalytics(g, box) {
  const ag = advancedGame(g.id);
  if (!ag) return;
  const opp = teamName(opponent(g));
  const c = el("div", "card");
  c.appendChild(text("div", "eyebrow", "ניתוח המשחק"));
  if (ag.key && KEY_PHRASE[ag.key]) {
    const [what, detail] = KEY_PHRASE[ag.key](ag.four.us, ag.four.them);
    const k = el("div", "key-line");
    k.appendChild(text("span", "key-what",
      (ag.win ? "המפתח לניצחון: " : "מה שהכריע את ההפסד: ") + what + "."));
    k.appendChild(vprose("span", "key-detail", " " + detail));
    c.appendChild(k);
  }
  c.appendChild(kpiRow([
    { label: "החזקות", value: fix1(ag.poss), sub: "לכל קבוצה" },
    { label: "התקפה", value: fix1(ag.ortg), sub: "ל־100 החזקות" },
    { label: "הגנה", value: fix1(ag.drtg), sub: "ל־100 החזקות" },
  ]));
  c.appendChild(compareRows(fourFactorRows(ag.four, opp), ["הפועל", opp]));
  view.appendChild(c);

  if ((ag.quarters || []).length >= 2) {
    const fc = el("div", "card");
    fc.appendChild(text("div", "eyebrow", "מהלך המשחק"));
    fc.appendChild(vprose("div", "viz-lede", "ההפרש המצטבר בסוף כל רבע. מעל הקו אנחנו מובילים."));
    const wrap = el("div", "viz");
    fc.appendChild(wrap);
    view.appendChild(fc);
    flowChart(wrap, ag.quarters, opp);
  }
}

/* ---------- the player page ---------- */

function squadRank(slug, key) {
  const rot = rotation().filter(p => p[key] !== null && p[key] !== undefined);
  const sorted = rot.slice().sort((a, b) => b[key] - a[key]);
  const i = sorted.findIndex(p => p.slug === slug);
  return i < 0 ? null : { rank: i + 1, of: sorted.length };
}

// **השחקן במספרים מתקדמים.** כל שיעור מקבל לידו את המקום שלו בקבוצה,
// כי ״20.2%״ לבד לא אומר לאוהד אם זה הרבה.
function renderPlayerAdvanced(p, season) {
  const ap = advancedPlayer(p.slug);
  if (!ap || ap.min < MIN_MINUTES / 2) return;
  view.appendChild(text("div", "section-title", "במספרים מתקדמים"));
  const c = el("div", "card");
  const grid = el("div", "facts");
  const ts = season && season.avg ? season.avg.ts : null;
  [["שימוש", pctOrDash(ap.usg), "usg"],
   ["קליעה אמיתית", ts === null || ts === undefined ? "-" : fix1(ts) + "%", null],
   ["פלוס/מינוס ל־40 דקות", signed(ap.pmPer40), "pmPer40"],
   ["אסיסטים", pctOrDash(ap.ast), "ast"],
   ["ריבאונדים", pctOrDash(ap.reb), "reb"],
   ["איבודים", pctOrDash(ap.tov), null]].forEach(([label, value, key]) => {
    const cell = el("div", "fact");
    const fv = el("div", "fv");
    fv.appendChild(num(value));
    cell.appendChild(fv);
    cell.appendChild(text("div", "fl", label));
    const r = key && ap.min >= MIN_MINUTES ? squadRank(p.slug, key) : null;
    if (r) cell.appendChild(text("div", "fr", "מקום " + r.rank + " מתוך " + r.of));
    grid.appendChild(cell);
  });
  c.appendChild(grid);
  c.appendChild(vprose("div", "viz-note",
    "שימוש: כמה מההתקפות של הקבוצה נגמרות אצלו כשהוא על המגרש. אסיסטים " +
    "וריבאונדים באחוזים מההזדמנויות בזמן שהיה על המגרש. המקום הוא מתוך מי " +
    "ששיחק " + MIN_MINUTES + " דקות ומעלה."));
  view.appendChild(c);

  if (season && (season.log || []).length >= 2) {
    const pc = el("div", "card");
    pc.appendChild(text("div", "eyebrow", "מדד בכל משחק"));
    const wrap = el("div", "viz");
    pc.appendChild(wrap);
    view.appendChild(pc);
    pirChart(wrap, season.log, season.avg ? season.avg.pir : null);
    pc.appendChild(vprose("div", "viz-note",
      "הראשון מימין, האחרון משמאל. הקו הדק הוא הממוצע שלו. לחיצה על עמודה פותחת את המשחק."));
  }
}
