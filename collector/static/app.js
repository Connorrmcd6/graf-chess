// Shared helpers for the chess pages (same patterns as mealbot's app.js).

const api = {
  async get(path) {
    const res = await fetch(path, { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  },
};

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}

function getParam(name) { return new URLSearchParams(location.search).get(name); }
function store(key, value) {
  try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch { return null; }
}

// ------------------------------------------------------------------ player and mode

const MODES = [["all", "All"], ["rapid", "Rapid"], ["blitz", "Blitz"], ["bullet", "Bullet"], ["daily", "Daily"]];
const state = { player: getParam("player") || store("player"), mode: store("mode") || "all", players: [] };
// A shared link (?player=…) switches the remembered player, so the other tabs follow it.
if (getParam("player")) store("player", getParam("player"));

function query(extra = {}) {
  return new URLSearchParams({ player: state.player, mode: state.mode, ...extra }).toString();
}

function playerName() {
  return state.players.find((p) => p.username === state.player)?.name || state.player;
}

async function choosePlayer(onchange, required = false) {
  if (!state.players.length) state.players = (await api.get("/api/players")).players;
  const list = h("div", { class: "menu" }, state.players.map((p) =>
    h("button", { onclick: () => { closeSheet(); state.player = p.username; store("player", p.username); onchange(); } },
      h("span", { class: "ic", "aria-hidden": "true" }, p.username === state.player ? "●" : "○"),
      h("span", { class: "grow" }, p.name), h("span", { class: "small muted" }, `${p.analysed} analysed`))));
  sheet(h("div", { class: "title" }, required ? "Who's playing?" : "Switch player"),
    h("div", { class: "muted small" }, "Your choice is remembered on this phone."), list);
}

// Header with the page title, the current player (tap to switch) and mode chips. Calls load() when anything changes.
async function setup(title, load, { modes = true } = {}) {
  const page = document.querySelector(".page");
  try { state.players = (await api.get("/api/players")).players; } catch (e) { return fail(e); }
  if (!state.players.some((p) => p.username === state.player)) state.player = null;
  const head = h("div", { class: "header" },
    h("div", { class: "grow" }, h("h1", {}, title), h("div", { class: "sub", id: "sub" })),
    h("button", { class: "who", id: "who", onclick: () => choosePlayer(refresh) }, "Player ▾"));
  const chips = modes && h("div", { class: "chips", role: "group", "aria-label": "Game type" });
  const drawChips = () => chips && chips.replaceChildren(...MODES.map(([key, label]) =>
    h("button", { class: "chip", "aria-pressed": String(state.mode === key),
      onclick: () => { state.mode = key; store("mode", key); drawChips(); load(); } }, label)));
  page.prepend(head, chips || "");
  drawChips();
  function refresh() {
    document.getElementById("who").textContent = `${playerName()} ▾`;
    load();
  }
  if (!state.player) {
    document.getElementById("content").replaceChildren(h("div", { class: "card empty" },
      h("h2", {}, "Choose a player"), h("p", {}, "Pick whose games to look at."),
      h("button", { class: "btn primary", onclick: () => choosePlayer(refresh, true) }, "Choose player")));
    choosePlayer(refresh, true);
    return;
  }
  refresh();
}

// ------------------------------------------------------------------------ positions

const SUFFIX = { inaccuracy: "?!", mistake: "?", blunder: "??" };
const KIND = { positional: "Positional", allowed_tactic: "Allowed a tactic", missed_tactic: "Missed a tactic" };

function moveLabel(number, colour, san, cls) {
  return `${number}${colour === "white" ? ". " : "... "}${san}${SUFFIX[cls] || ""}`;
}

function boardUrl(fen, colour, you, best, play) {
  return "/board.svg?" + new URLSearchParams({ fen, o: colour, you: you || "", best: best || "", ...(play ? { p: play } : {}) });
}

function lichessUrl(fen, colour) {
  return `https://lichess.org/analysis/${fen.replaceAll(" ", "_")}?color=${colour}`;
}

function clock(seconds) {
  if (seconds == null) return null;
  const s = Math.round(seconds);
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} left` : `${s}s left`;
}

function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

// A position card: board (red = your move, green = engine's), the move, why it was wrong, and links out.
// p: {fen, colour, move_number, san, uci, best_san, best_uci, best_line?, classification?, kind?, win_loss?|avg_drop?,
//     times?, games?, opening?, url?, ended_at?, mode?, clock_seconds?}
function positionCard(p, { note } = {}) {
  const img = h("img", { src: boardUrl(p.fen, p.colour, p.uci, p.best_uci), alt: "Board position", loading: "lazy" });
  const drop = p.win_loss ?? p.avg_drop;
  return h("div", { class: "card pos" },
    h("button", { class: "board", "aria-label": "Show larger board", onclick: () => boardSheet(p) }, img),
    h("div", {},
      h("div", { class: "move" }, moveLabel(p.move_number, p.colour, p.san, p.classification)),
      h("div", { class: "meta" },
        p.classification && h("span", { class: "tag " + (p.classification === "blunder" ? "bad" : "warn") }, p.classification),
        p.kind && h("span", { class: "tag" }, KIND[p.kind]),
        note && h("span", { class: "tag accent" }, note)),
      h("div", { class: "best" }, "Engine: ", h("b", {}, p.best_san || "?")),
      h("div", { class: "small muted" }, [drop != null && `−${Math.round(drop)} pts`, clock(p.clock_seconds),
        p.mode, p.ended_at && shortDate(p.ended_at)].filter(Boolean).join(" · ")),
      p.opening && h("div", { class: "small muted ellipsis" }, p.opening),
      h("div", { class: "actions" },
        h("a", { class: "btn primary", href: lichessUrl(p.fen, p.colour), target: "_blank", rel: "noopener" }, "Lichess"),
        p.url && h("a", { class: "btn", href: p.url, target: "_blank", rel: "noopener" }, "Game"))));
}

function boardSheet(p) {
  sheet(h("div", { class: "title" }, moveLabel(p.move_number, p.colour, p.san, p.classification)),
    p.opening && h("div", { class: "muted small" }, p.opening),
    h("img", { class: "big-board", style: "margin-top:12px", src: boardUrl(p.fen, p.colour, p.uci, p.best_uci), alt: "Board position" }),
    legend(),
    h("p", {}, "Engine prefers ", h("b", {}, p.best_san || "?"), p.kind ? ` · ${KIND[p.kind].toLowerCase()}` : ""),
    p.best_line && h("div", { class: "line" }, p.best_line),
    h("div", { class: "row", style: "margin-top:14px" },
      h("a", { class: "btn primary grow", href: lichessUrl(p.fen, p.colour), target: "_blank", rel: "noopener" }, "Open in Lichess"),
      p.url && h("a", { class: "btn", href: p.url, target: "_blank", rel: "noopener" }, "Game")));
}

// A board you move on by tapping a piece then its square, or by dragging it there. legal: {uci: san}.
// Drawn in the browser so pieces slide between positions. Promotions become queens.
// set({fen, legal, you, best, play, last, check, locked}): you/best are red/green arrows, play is a move made
// on the board first (a wrong move, to take back), last highlights the previous move, check the king in check.
const FILES = "abcdefgh";
const PIECE_NAME = { p: "pawn", n: "knight", b: "bishop", r: "rook", q: "queen", k: "king" };
function pieceAt(fen) {
  const at = {};
  fen.split(" ")[0].split("/").forEach((rank, r) => {
    let file = 0;
    for (const c of rank) {
      if (/\d/.test(c)) file += Number(c);
      else at[FILES[file++] + (8 - r)] = c;
    }
  });
  return at;
}

function applyMove(at, uci) {
  const from = uci.slice(0, 2), to = uci.slice(2, 4), piece = at[from];
  if (!piece) return at;
  const next = { ...at };
  delete next[from];
  if (piece.toLowerCase() === "p" && from[0] !== to[0] && !at[to]) delete next[to[0] + from[1]];
  if (piece.toLowerCase() === "k" && Math.abs(FILES.indexOf(to[0]) - FILES.indexOf(from[0])) === 2) {
    const [rf, rt] = to[0] === "g" ? ["h", "f"] : ["a", "d"];
    next[rt + from[1]] = next[rf + from[1]];
    delete next[rf + from[1]];
  }
  next[to] = uci[4] ? (piece === piece.toUpperCase() ? uci[4].toUpperCase() : uci[4]) : piece;
  return next;
}

const SVG_NS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function tapBoard({ colour, onMove }) {
  let legal = {}, selected = null, locked = false, at = {}, drag = null, lastMove = "";
  const flip = colour === "black";
  const cell = (sq) => {
    const f = FILES.indexOf(sq[0]), r = Number(sq[1]) - 1;
    return flip ? [7 - f, r] : [f, 7 - r];
  };
  const place = (sq) => { const [c, r] = cell(sq); return `translate(${c * 100}%, ${r * 100}%)`; };
  for (const p of "pnbrqkPNBRQK") new Image().src = "/piece.svg?p=" + p;

  const marks = h("div", { class: "marks" });
  const layer = h("div", { class: "pieces" });
  const arrows = svgEl("svg", { class: "arrows", viewBox: "0 0 8 8", "aria-hidden": "true" });
  const grid = h("div", { class: "grid" });
  const squares = [];
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const name = flip ? FILES[7 - col] + (row + 1) : FILES[col] + (8 - row);
      // Pointer events do the work; click only fires on its own for the keyboard (detail 0).
      const sq = h("button", { class: "sq", "aria-label": name, onclick: (e) => { if (!e.detail) tap(name); } });
      sq.dataset.square = name;
      squares.push(sq);
      grid.append(sq);
    }
  }
  const coords = h("div", { class: "coords", "aria-hidden": "true" },
    [...Array(8)].map((_, k) => h("span", { class: "file " + (k % 2 ? "on-light" : "on-dark"), style: `left:${k * 12.5}%` },
      flip ? FILES[7 - k] : FILES[k])),
    [...Array(8)].map((_, k) => h("span", { class: "rank " + (k % 2 ? "on-dark" : "on-light"), style: `top:${k * 12.5}%` },
      flip ? k + 1 : 8 - k)));
  const el = h("div", { class: "drill-board" }, h("div", { class: "squares" }), coords, marks, layer, arrows, grid);
  let els = {};

  function redraw(next, animate) {
    const keep = {}, free = [];
    for (const [sq, p] of Object.entries(els)) (next[sq] === p.dataset.piece ? (keep[sq] = p) : free.push([sq, p]));
    const changed = Object.keys(next).filter((sq) => !keep[sq]).length;
    animate = animate && changed <= 4;
    el.classList.toggle("still", !animate);
    for (const [sq, piece] of Object.entries(next)) {
      if (keep[sq]) continue;
      const [c, r] = cell(sq);
      let best = -1, dist = Infinity;
      free.forEach(([from, p], k) => {
        if (!p || p.dataset.piece !== piece) return;
        const [fc, fr] = cell(from), d = Math.hypot(fc - c, fr - r);
        if (d < dist) { dist = d; best = k; }
      });
      let p;
      if (best >= 0) { p = free[best][1]; free[best][1] = null; }
      else {
        p = h("img", { class: "pc", src: "/piece.svg?p=" + piece, alt: "", draggable: "false" });
        p.dataset.piece = piece;
        p.style.transform = place(sq);
        layer.append(p);
      }
      p.classList.remove("drag");
      p.style.transform = place(sq);
      keep[sq] = p;
    }
    for (const [, p] of free) if (p) { p.classList.add("gone"); setTimeout(() => p.remove(), animate ? 180 : 0); }
    els = keep;
    if (!animate) void el.offsetWidth;  // apply the jump before transitions come back
    el.classList.remove("still");
  }

  function square(sq, cls) {
    const [c, r] = cell(sq);
    return h("i", { class: cls, style: `transform:translate(${c * 100}%, ${r * 100}%)` });
  }

  function drawArrows(list) {
    arrows.replaceChildren();
    for (const [uci, kind] of list) {
      if (!uci) continue;
      const [x1, y1] = cell(uci.slice(0, 2)), [x2, y2] = cell(uci.slice(2, 4));
      const len = Math.hypot(x2 - x1, y2 - y1), ux = (x2 - x1) / len, uy = (y2 - y1) / len;
      const head = 0.42, end = [x2 + .5 - ux * 0.2, y2 + .5 - uy * 0.2], base = [end[0] - ux * head, end[1] - uy * head];
      const g = svgEl("g", { class: "arrow " + kind });
      g.append(svgEl("line", { x1: x1 + .5, y1: y1 + .5, x2: base[0], y2: base[1] }),
        svgEl("polygon", { points: [end, [base[0] - uy * .26, base[1] + ux * .26], [base[0] + uy * .26, base[1] - ux * .26]]
          .map((p) => p.join(",")).join(" ") }));
      arrows.append(g);
    }
  }

  function highlight() {
    const targets = new Set(Object.keys(legal).filter((m) => m.startsWith(selected || "-")).map((m) => m.slice(2, 4)));
    for (const sq of squares) {
      const name = sq.dataset.square;
      sq.classList.toggle("sel", name === selected);
      sq.classList.toggle("target", targets.has(name) && !at[name]);
      sq.classList.toggle("capture", targets.has(name) && !!at[name]);
      sq.classList.toggle("lifted", !!drag?.moving && name === drag.from);
    }
  }
  function labels() {
    for (const sq of squares) {
      const p = at[sq.dataset.square];
      sq.setAttribute("aria-label", sq.dataset.square + (p ? `, ${p === p.toUpperCase() ? "white" : "black"} ${PIECE_NAME[p.toLowerCase()]}` : ""));
    }
  }
  const movable = (square) => Object.keys(legal).some((m) => m.startsWith(square));
  function play(from, to) {
    const moves = Object.keys(legal).filter((m) => m.startsWith(from + to));
    if (!moves.length) return false;
    selected = null;
    highlight();
    onMove(moves.find((m) => m.endsWith("q")) || moves[0]);
    return true;
  }
  function tap(square) {
    if (locked) return;
    if (selected && play(selected, square)) return;
    selected = movable(square) && square !== selected ? square : null;
    highlight();
  }
  function squareAt(x, y) {
    const r = grid.getBoundingClientRect();
    const col = Math.floor((x - r.left) / (r.width / 8)), row = Math.floor((y - r.top) / (r.height / 8));
    return col < 0 || col > 7 || row < 0 || row > 7 ? null : squares[row * 8 + col].dataset.square;
  }
  function moveDragged(e) {
    const box = el.getBoundingClientRect(), size = box.width / 8;
    const lift = e.pointerType === "touch" ? size * 0.5 : 0;  // keep the piece visible above your finger
    drag.el.style.transform = `translate(${e.clientX - box.left - size / 2}px, ${e.clientY - box.top - size / 2 - lift}px) scale(${e.pointerType === "touch" ? 1.25 : 1.08})`;
  }
  function endDrag(snapBack) {
    if (drag?.moving && snapBack) { drag.el.classList.remove("drag"); drag.el.style.transform = place(drag.from); }
    drag = null;
    highlight();
  }

  grid.addEventListener("pointerdown", (e) => {
    if (locked || !e.isPrimary || e.button > 0) return;
    const square = squareAt(e.clientX, e.clientY);
    if (!square) return;
    e.preventDefault();
    if (selected && selected !== square && play(selected, square)) return;
    if (!movable(square)) { selected = null; return highlight(); }
    const wasSelected = selected === square;
    selected = square;
    drag = { from: square, x: e.clientX, y: e.clientY, moving: false, wasSelected, el: els[square] };
    grid.setPointerCapture(e.pointerId);
    highlight();
  });
  grid.addEventListener("pointermove", (e) => {
    if (!drag || !drag.el) return;
    if (!drag.moving) {
      if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
      drag.moving = true;
      drag.el.classList.add("drag");
      highlight();
    }
    moveDragged(e);
  });
  grid.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const { from, moving, wasSelected } = drag;
    if (moving) {
      const to = squareAt(e.clientX, e.clientY);
      const played = to && to !== from && (() => { const d = drag; drag = null; const ok = play(from, to); drag = ok ? null : d; return ok; })();
      if (!played) endDrag(true);
    } else {
      endDrag(false);
      if (wasSelected) { selected = null; highlight(); }  // tapping the selected piece again puts it down
    }
  });
  grid.addEventListener("pointercancel", () => endDrag(true));

  function set({ fen, legal: moves, you = "", best = "", play: played = "", last = "", check = false, locked: lock = false }) {
    if (fen) {
      const first = !Object.keys(els).length;
      at = pieceAt(fen);
      if (played) { at = applyMove(at, played); you = played; last = ""; }
      lastMove = played || last;
      redraw(at, !first);
      const turn = played ? (fen.split(" ")[1] === "w" ? "b" : "w") : fen.split(" ")[1];
      const king = check && Object.keys(at).find((sq) => at[sq] === (turn === "w" ? "K" : "k"));
      marks.replaceChildren(...(lastMove ? [square(lastMove.slice(0, 2), "last"), square(lastMove.slice(2, 4), "last")] : []),
        king ? square(king, "check") : "");
      drawArrows([[you, "red"], [best !== you ? best : "", "green"]]);
      labels();
    }
    if (moves) legal = moves;
    locked = lock;
    selected = null;
    drag = null;
    grid.classList.toggle("locked", lock);
    highlight();
  }
  return { el, set };
}

function legend() {
  return h("div", { class: "legend", style: "margin-top:10px" },
    h("span", {}, h("i", { style: "background:#d0432b" }), "Your move"),
    h("span", {}, h("i", { style: "background:#2f8a50" }), "Engine's move"));
}

// --------------------------------------------------------------------- page chrome

let toastTimer;
function toast(message, { error } = {}) {
  document.querySelector(".toast")?.remove();
  const el = h("div", { class: "toast" + (error ? " error" : ""), role: "status" }, h("span", {}, message));
  document.body.append(el);
  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 250); }, 3500);
}

function fail(err) { toast(err.message || String(err), { error: true }); }

function sheet(...content) {
  closeSheet();
  const backdrop = h("div", { class: "backdrop", onclick: closeSheet });
  const panel = h("div", { class: "sheet", role: "dialog", "aria-modal": "true" }, h("div", { class: "grab" }), ...content);
  let startY = null;
  panel.addEventListener("touchstart", (e) => { startY = panel.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
  panel.addEventListener("touchend", (e) => {
    if (startY != null && e.changedTouches[0].clientY - startY > 80) closeSheet();
    startY = null;
  });
  document.body.append(backdrop, panel);
  requestAnimationFrame(() => { backdrop.classList.add("open"); panel.classList.add("open"); });
  return panel;
}

function closeSheet() {
  document.querySelectorAll(".sheet, .backdrop").forEach((el) => { el.classList.remove("open"); setTimeout(() => el.remove(), 220); });
}

document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

function empty(title, text) {
  return h("div", { class: "card empty" }, h("h2", {}, title), h("p", {}, text));
}

function section(title, ...children) {
  return [h("h3", { class: "section" }, title), ...children.flat()];
}

const ICONS = {
  patterns: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/></svg>',
  review: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></svg>',
  drill: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></svg>',
  openings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5V5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2"/><path d="M8 7h8M8 11h6"/></svg>',
  games: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>',
};

function renderTabs() {
  const here = location.pathname === "/game" ? "/games" : location.pathname;
  const tabs = [["/", "Patterns", "patterns"], ["/review", "Review", "review"], ["/drill", "Drill", "drill"], ["/openings", "Openings", "openings"], ["/games", "Games", "games"]];
  document.body.append(h("nav", { class: "tabs", "aria-label": "Main" },
    tabs.map(([href, label, icon]) => h("a", { href, "aria-current": href === here ? "page" : null, html: ICONS[icon] + `<span>${label}</span>` }))));
}

renderTabs();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
