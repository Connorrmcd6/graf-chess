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
// Promotions become queens. Returns {el, set({fen, legal, you, best, play, locked})}: the image is redrawn
// server-side with the arrows; play draws the position after that move (a wrong move, to take back).
const FILES = "abcdefgh";
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

function tapBoard({ colour, onMove }) {
  let legal = {}, selected = null, locked = false, pieces = {}, drag = null;
  const img = h("img", { class: "big-board", alt: "Board position", draggable: "false" });
  const ghost = h("img", { class: "ghost hidden", alt: "", draggable: "false" });
  const grid = h("div", { class: "grid" });
  const squares = [];
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const name = colour === "white" ? FILES[col] + (8 - row) : FILES[7 - col] + (row + 1);
      // Pointer events do the work; click only fires on its own for the keyboard (detail 0).
      const sq = h("button", { class: "sq", "aria-label": name, onclick: (e) => { if (!e.detail) tap(name); } });
      sq.dataset.square = name;
      squares.push(sq);
      grid.append(sq);
    }
  }
  const el = h("div", { class: "drill-board" }, img, grid, ghost);

  function highlight() {
    const targets = new Set(Object.keys(legal).filter((m) => m.startsWith(selected || "-")).map((m) => m.slice(2, 4)));
    for (const sq of squares) {
      sq.classList.toggle("sel", sq.dataset.square === selected);
      sq.classList.toggle("target", targets.has(sq.dataset.square));
      sq.classList.toggle("lifted", !!drag?.moving && sq.dataset.square === drag.from);
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
  function moveGhost(e) {
    const box = el.getBoundingClientRect(), size = grid.getBoundingClientRect().width / 8 * 1.3;
    const lift = e.pointerType === "touch" ? size * 0.45 : 0;  // keep the piece visible above your finger
    ghost.style.width = ghost.style.height = size + "px";
    ghost.style.transform = `translate(${e.clientX - box.left - size / 2}px, ${e.clientY - box.top - size / 2 - lift}px)`;
  }
  function endDrag() {
    drag = null;
    ghost.classList.add("hidden");
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
    drag = { from: square, x: e.clientX, y: e.clientY, moving: false, wasSelected };
    grid.setPointerCapture(e.pointerId);
    highlight();
  });
  grid.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.moving) {
      if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
      drag.moving = true;
      ghost.src = "/piece.svg?p=" + pieces[drag.from];
      ghost.classList.remove("hidden");
      highlight();
    }
    moveGhost(e);
  });
  grid.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const { from, moving, wasSelected } = drag;
    endDrag();
    if (moving) {
      const to = squareAt(e.clientX, e.clientY);
      if (to && to !== from) play(from, to);
    } else if (wasSelected) {  // tapping the selected piece again puts it down
      selected = null;
      highlight();
    }
  });
  grid.addEventListener("pointercancel", endDrag);

  function set({ fen, legal: moves, you = "", best = "", play: played = "", locked: lock = false }) {
    if (fen) { img.src = boardUrl(fen, colour, you, best, played); pieces = pieceAt(fen); }
    if (moves) legal = moves;
    locked = lock;
    selected = null;
    if (drag) endDrag();
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
