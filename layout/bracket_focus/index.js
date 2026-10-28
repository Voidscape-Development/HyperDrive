// Its channel's bracket (bracket.channels.<channel>), drawn once at full
// size and zoomed to what's in focus on the channel (bracket.focus.<channel>,
// see docs/layout-data.md): sets and rounds picked in the bracket widget, the
// winners or losers side, a player's run, the set on a scoreboard or a tour of
// the rounds. The sets in focus are outlined (unless the layout theme's "Focus
// glow" is off for the mode), the rest dimmed. Nothing in focus: the whole
// bracket.
// Options, page or URL (?channel=Losers%20cam&max_zoom=150):
//   channel       the channel shown (default: main), as named in the
//                 bracket widget's tabs
//   ignore_focus  always the whole bracket
//   max_zoom      the most a set is enlarged, in % (default: the layout
//                 theme's, 200)
// no_title.html has no title bar: the bracket takes the whole page.

// ---------------------------------------------------------------------
// Sizes

// Sizes in world pixels, before zooming
const PLAYER_H = 40;
const SET_GAP = 2;
const SET_W = 380;
const SET_H = PLAYER_H * 2 + SET_GAP;
const COLUMN_GAP = 100;
const ROW_GAP = 24;
const HEADER_H = 56;
const SECTION_GAP = 90;
const MARGIN = 40;
// Room left around what's in focus, in screen pixels, and under it for the
// caption saying what it is
const PADDING = 60;
const LABEL_ROOM = 90;
// The camera's move, in seconds: the layout theme's "Bracket focus zoom time"
const cameraTime = () => HD.theme("bracket", "focus_time", 1000) / 1000;
const FADE_TIME = 0.6;
const STAGGER_TIME = 1.5;

// The layers the sets, round names and lines are in, bottom to top: the
// base (everything, dimmed while there's a focus), the ones fading out of
// focus and into it, and the ones in focus. Dimming is one opacity on a
// layer, not one on each of hundreds of sets and lines, which the browser
// draws apart (and fading, each its own layer) every frame of a camera move.
// Moving an element to another layer has it laid out again, so only the few
// changing focus move: zooming in from the whole bracket, the base fades
// out under the sets in focus.
const LAYERS = ["base", "to_dim", "to_lit", "lit"];

// ---------------------------------------------------------------------
// State

// Set id: number used in class names (ids can be anything)
let setIndex = {};
// Set id: its element, as build() made it
let setElements = {};
// What build() placed: {sets: {id: {x, y, w, h}}, headers, byes, areas,
// standings, width, height}
let placed = null;
let lastSignature = null;
let lastFocus = null;
let camera = null;
// Where the camera is (see showView), and its move under way
let view = null;
let cameraTween = null;
// The focus caption's text, and its fade under way
let shownLabel = null;
let labelTween = null;
// Layer name: its elements, {html, shadows, lines}, as build() made them
let layers = {};
// Each set, round name and line: the name of its layer
let layerOf = new Map();
// The layers' fades under way, and putting what they faded where it goes
let fades = [];
let settling = null;

const setElement = (id) => setElements[id] || $();
const box = (b) => `left: ${b.x}px; top: ${b.y}px; width: ${b.w}px;${b.h ? ` height: ${b.h}px;` : ""}`;

// Every set is shown, waiting ones with where their players come from, but
// a grand final reset only when it's needed
const isShown = (set) => set && HDBracket.SetState(set, true) != "hidden";

// ---------------------------------------------------------------------
// Placing the bracket

// Places the columns of one part of the bracket from `top`, each set level
// with the sets that feed it, like the bracket widget does. Returns the
// part's bottom.
function placeArea(columns, sets, top, result) {
  let bottom = top;
  let lastX = MARGIN;
  const thirdPlace = [];
  const area = new Set(columns.flatMap((column) => column.sets));
  // Set id: the sets of the area whose winner goes to it
  const feedersOf = {};
  for (const id of area) {
    const next = sets[id] && sets[id].nextWin;
    if (next) (feedersOf[next.set] = feedersOf[next.set] || []).push(id);
  }

  const shown = [];
  for (const column of columns) {
    if (column.side == "third_place") {
      thirdPlace.push(column);
      continue;
    }
    const ids = column.sets.filter((id) => isShown(sets[id]));
    if (ids.length === 0) continue;
    lastX = MARGIN + shown.length * (SET_W + COLUMN_GAP);
    shown.push({ column, ids, x: lastX });
  }

  // Play-in rounds (fewer sets than the round after them) are placed last,
  // each set level with the slot its winner goes to
  let playIns = 0;
  while (
    playIns + 1 < shown.length &&
    shown[playIns].column.side == shown[playIns + 1].column.side &&
    shown[playIns].ids.length < shown[playIns + 1].ids.length
  ) {
    playIns += 1;
  }
  const order = shown.slice(playIns).concat(shown.slice(0, playIns).reverse());

  order.forEach(({ column, ids, x }, i) => {
    const playIn = i >= shown.length - playIns;
    let cursor = top + HEADER_H;
    let firstY = null;
    for (const id of ids) {
      const feeders = (feedersOf[id] || []).filter((f) => result.sets[f]);
      const next = sets[id].nextWin;
      const target = playIn && next ? result.sets[next.set] : null;
      let y = cursor;
      if (target) {
        // Centered on the slot's row, the top or bottom half of the set
        y = Math.max(cursor, target.y + (((next.slot || 0) * 2 - 1) * SET_H) / 4);
      } else if (feeders.length) {
        y = Math.max(cursor, _.mean(feeders.map((f) => result.sets[f].y)));
      } else if (column.side == "grand_final" && result.lastGrandFinal != null) {
        // The reset, level with the grand final
        y = Math.max(cursor, result.lastGrandFinal);
      }
      if (column.side == "grand_final") result.lastGrandFinal = y;
      if (firstY == null) firstY = y;
      result.sets[id] = { x, y, w: SET_W, h: SET_H };
      cursor = y + SET_H + ROW_GAP;
      bottom = Math.max(bottom, cursor);
    }
    // Grand finals have their name just above them
    result.headers[column.key] = {
      x,
      y: column.side == "grand_final" ? firstY - HEADER_H : top,
      w: SET_W,
      h: HEADER_H - 12,
    };
  });

  // The 3rd place match under the last column
  for (const column of thirdPlace) {
    const ids = column.sets.filter((id) => isShown(sets[id]));
    if (ids.length === 0) continue;
    let y = bottom + ROW_GAP;
    result.headers[column.key] = { x: lastX, y, w: SET_W, h: HEADER_H - 12 };
    y += HEADER_H;
    for (const id of ids) {
      result.sets[id] = { x: lastX, y, w: SET_W, h: SET_H };
      y += SET_H + ROW_GAP;
    }
    bottom = y;
  }
  return bottom;
}

// Round robin and swiss: a column per round, sets one under the other, the
// standings after them
function placePool(bracket, result) {
  const sets = bracket.sets || {};
  let bottom = MARGIN;
  let x = MARGIN;
  for (const column of HDBracket.Columns(bracket, "pool")) {
    result.headers[column.key] = { x, y: MARGIN, w: SET_W, h: HEADER_H - 12 };
    let y = MARGIN + HEADER_H;
    for (const id of column.sets) {
      if (!sets[id]) continue;
      result.sets[id] = { x, y, w: SET_W, h: SET_H };
      y += SET_H + ROW_GAP;
    }
    result.byes[column.key] = { x, y, w: SET_W };
    bottom = Math.max(bottom, y + 40);
    x += SET_W + COLUMN_GAP;
  }
  result.standings = { x, y: MARGIN, w: 800 };
  return bottom;
}

function place(bracket) {
  const result = { sets: {}, headers: {}, byes: {}, areas: [], standings: null };
  let bottom;
  if (HDBracket.IsPool(bracket)) {
    bottom = placePool(bracket, result);
  } else {
    const { upper, lower } = HDBracket.Areas(bracket);
    bottom = placeArea(upper, bracket.sets || {}, MARGIN, result);
    if (lower.length) bottom = placeArea(lower, bracket.sets || {}, bottom + SECTION_GAP, result);
    result.areas = [upper, lower];
  }
  const boxes = Object.values(result.sets).concat(Object.values(result.headers));
  result.width = Math.max(0, ...boxes.map((b) => b.x + b.w)) + MARGIN;
  result.height = Math.max(bottom, ...boxes.map((b) => b.y + (b.h || 0))) + MARGIN;
  return result;
}

// ---------------------------------------------------------------------
// Drawing

// Lines from each set to where its winner goes, within one part of the
// bracket, and arrows out of it for players going on to another phase:
// [{from, to (none for an arrow), d}]
function lines(bracket) {
  const sets = bracket.sets || {};
  const path = (points) => `M${points.map((p) => p.join(" ")).join(" L")}`;
  return placed.areas.flatMap((columns) => {
    const inArea = new Set(columns.flatMap((c) => c.sets));
    return [...inArea].flatMap((id) => {
      const set = sets[id];
      const from = placed.sets[id];
      if (!set || !from) return [];
      const a = [from.x + from.w, from.y + from.h / 2];
      const to = set.nextWin && inArea.has(set.nextWin.set) && placed.sets[set.nextWin.set];
      if (to) {
        if (to.x <= from.x) return [];
        const b = [to.x, to.y + PLAYER_H / 2 + (set.nextWin.slot || 0) * (PLAYER_H + SET_GAP)];
        const mid = a[0] + (b[0] - a[0]) / 2;
        return [{ from: id, to: set.nextWin.set, d: path([a, [mid, a[1]], [mid, b[1]], b]) }];
      }
      if (!set.nextWin && bracket.progressionsOut > 0 && ["winners", "losers"].includes(set.side)) {
        const [x, y] = [a[0] + 45, a[1]];
        return [{ from: id, d: `${path([a, [x, y]])} M${x - 10} ${y - 8} L${x} ${y} L${x - 10} ${y + 8}` }];
      }
      return [];
    });
  });
}

// The lines, or their shadows (a copy under each, see index.css)
const linesHtml = (paths, cls) =>
  paths.map(
    (p) =>
      HD.html`<path class="${cls}" data-from="${p.from}" ${p.to != null && HD.html`data-to="${p.to}"`} d="${p.d}" />`,
  );

function build(data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  setIndex = {};
  placed = place(bracket);
  settle();

  // Everything starts in the base; applyFocus() lifts what's in focus
  HD.render(".bf_sets", [
    Object.entries(placed.byes).map(
      ([key, b]) => HD.html`<div class="byes" data-round="${key}" style="${box(b)}"></div>`,
    ),
    LAYERS.map(
      (name) => HD.html`
        <div class="bf_layer bf_${name}">
          ${
            name == "base" && [
              Object.entries(placed.headers).map(
                ([key, h]) => HD.html`<div class="bf_round_name" data-round="${key}" style="${box(h)}"></div>`,
              ),
              Object.entries(placed.sets).map(([id, at]) => {
                setIndex[id] = Object.keys(setIndex).length + 1;
                return HD.html`
                  <div class="slot set_${setIndex[id]} side_${sets[id].side}" data-set="${id}" style="${box(at)}">
                    <div class="set_identifier"><div class="text"></div></div>
                    ${HDBracket.PlayerSlotHtml(0)}
                    ${HDBracket.PlayerSlotHtml(1)}
                  </div>`;
              }),
            ]
          }
        </div>`,
    ),
  ]);
  setElements = {};
  $(".bf_sets .slot").each((_i, el) => (setElements[el.dataset.set] = $(el)));
  const paths = lines(bracket);
  HD.render(
    $(".bf_lines").attr({ width: placed.width, height: placed.height }),
    LAYERS.map(
      (name) => HD.html`
        <g class="bf_layer bf_${name}">
          <g class="shadows">${name == "base" && linesHtml(paths, "line shadow")}</g>
          <g class="lines">${name == "base" && linesHtml(paths, "line")}</g>
        </g>`,
    ),
  );
  layers = {};
  for (const name of LAYERS) {
    const svg = document.querySelector(`.bf_lines .bf_${name}`);
    layers[name] = {
      html: document.querySelector(`.bf_sets .bf_${name}`),
      svg,
      shadows: svg.querySelector(".shadows"),
      lines: svg.querySelector(".lines"),
    };
  }
  layerOf = new Map();
  for (const el of document.querySelectorAll(".bf_layer .slot, .bf_layer .bf_round_name, .bf_layer path")) {
    layerOf.set(el, "base");
  }

  const standings = $(".bf_standings").removeData("hd-build").empty();
  if (placed.standings) standings.css({ left: placed.standings.x, top: placed.standings.y, width: placed.standings.w });
  $(".world").css({ width: placed.width, height: placed.height });
  $("body").toggleClass("pool_view", HDBracket.IsPool(bracket));

  // Sets come in column by column (then their styles are left to the CSS,
  // which dims them out of focus), all in at most STAGGER_TIME however
  // big the bracket
  const order = Object.keys(placed.sets).sort((a, b) => placed.sets[a].x - placed.sets[b].x);
  gsap.from(
    order.map((id) => setElement(id).get(0)),
    {
      autoAlpha: 0,
      x: -40,
      duration: 0.4,
      stagger: Math.min(0.015, STAGGER_TIME / order.length),
      clearProps: "opacity,visibility,transform",
    },
  );
  gsap.from(".bf_lines path, .bf_round_name", {
    autoAlpha: 0,
    duration: 0.6,
    delay: 0.3,
    clearProps: "opacity,visibility",
  });
}

// ---------------------------------------------------------------------
// Camera and focus

// The world's size, with the pool standings once drawn
function worldSize() {
  let { width, height } = placed;
  const standings = $(".bf_standings");
  if (placed.standings && standings.children().length) {
    width = Math.max(width, placed.standings.x + standings.outerWidth() + MARGIN);
    height = Math.max(height, placed.standings.y + standings.outerHeight() + MARGIN);
  }
  return { width, height };
}

function maxZoom(s) {
  const zoom = parseFloat(s.settings.max_zoom || HD.theme("bracket", "focus_max_zoom", 200));
  return (isFinite(zoom) && zoom > 0 ? zoom : 200) / 100;
}

// The box around what's in focus, in world pixels
function focusBox(focus) {
  const boxes = [
    ...(focus.sets || []).map((id) => placed.sets[id]),
    ...(focus.rounds || []).map((key) => placed.headers[key]),
  ].filter(Boolean);
  if (boxes.length === 0) {
    const size = worldSize();
    return { x: 0, y: 0, w: size.width, h: size.height };
  }
  const left = Math.min(...boxes.map((b) => b.x));
  const top = Math.min(...boxes.map((b) => b.y));
  return {
    x: left,
    y: top,
    w: Math.max(...boxes.map((b) => b.x + b.w)) - left,
    h: Math.max(...boxes.map((b) => b.y + (b.h || 0))) - top,
  };
}

// Shows the world as a view: the world point (cx, cy) at (ax, ay) on screen,
// at a scale
function showView(v) {
  view = v;
  gsap.set(".world", {
    x: v.ax - v.cx * v.scale,
    y: v.ay - v.cy * v.scale,
    scale: v.scale,
    transformOrigin: "0 0",
    immediateRender: true,
  });
}

// The view t (0 to 1) of the way from a to b. Moving x, y and the scale
// each in a straight line zooms unevenly: zooming in, most of it happens at
// the start, and what's zoomed to swings out and back. Here each moment
// zooms by as much as the one before (the scale goes geometrically), around
// the one point that stays put on screen, so zooming in from the whole
// bracket feels like zooming out to it played backwards.
function between(a, b, t) {
  const lerp = (p, q, f) => p + (q - p) * f;
  const ratio = b.scale / a.scale;
  const scale = a.scale * Math.pow(ratio, t);
  // How far the center has moved: in step with 1 / scale, the size of the
  // world on screen, so the point that stays put does
  const u = Math.abs(Math.log(ratio)) < 0.01 ? t : (1 / scale - 1 / a.scale) / (1 / b.scale - 1 / a.scale);
  return {
    cx: lerp(a.cx, b.cx, u),
    cy: lerp(a.cy, b.cy, u),
    ax: lerp(a.ax, b.ax, t),
    ay: lerp(a.ay, b.ay, t),
    scale,
  };
}

// Moves the camera to a box, animated or not
function moveCamera(s, target, animate) {
  const viewport = $(".viewport");
  const vw = viewport.width();
  const vh = viewport.height();
  if (!target.w || !target.h) return;
  // Kept even while the page has no size yet (a browser source starting
  // hidden), so it's moved there once it's resized
  camera = target;
  if (!vw || !vh) return;
  const label =
    $(".focus_label").hasClass("shown") && !$("body").hasClass("hd-bracket-hide-focus-label") ? LABEL_ROOM : 0;
  const scale = Math.min((vw - PADDING * 2) / target.w, (vh - PADDING * 2 - label) / target.h, maxZoom(s));
  const to = { cx: target.x + target.w / 2, cy: target.y + target.h / 2, ax: vw / 2, ay: (vh - label) / 2, scale };

  if (cameraTween) cameraTween.kill();
  cameraTween = null;
  if (animate && view) {
    // From wherever it is, even halfway through another move
    const from = view;
    const progress = { t: 0 };
    cameraTween = gsap.to(progress, {
      t: 1,
      duration: cameraTime(),
      ease: "power2.inOut",
      onUpdate: () => showView(between(from, to, progress.t)),
      onComplete: () => (cameraTween = null),
    });
  } else {
    // Right away: GSAP's timeline is frozen until the layout is first shown,
    // and the bracket would show at full size until then
    showView(to);
  }
}

const channelOf = (s) => HDBracket.ChannelName(s.settings.channel) || "main";

const focusOf = (s, data) =>
  (!s.settings.ignore_focus && _.get(data, ["bracket", "focus", channelOf(s)])) || { sets: [], rounds: [] };

// The layout theme's "Focus glow" for the focus mode: off, the sets in focus
// aren't outlined (they're still zoomed to, and the rest dimmed)
const glows = (focus) => !focus.mode || HD.theme("bracket", `focus_glow_${focus.mode}`, true) !== false;

// The mode's own glow color with "own color" on, else the focus highlight's
// (null)
const glowColor = (focus) =>
  focus.mode && HD.theme("bracket", `focus_glow_custom_${focus.mode}`, false) === true
    ? `var(--bracket-focus-glow-color-${focus.mode})`
    : null;

// The caption saying what's in focus, faded in and out whole, never shown
// empty while its text fades: a new caption is filled in while the bar is
// hidden, then faded in as the camera gets there. Going, its text is kept
// for the fade out.
function showLabel(label, animate) {
  const bar = $(".focus_label");
  const wasShown = bar.hasClass("shown");
  bar.toggleClass("shown", label !== "");
  if (wasShown && label === shownLabel) return;
  if (labelTween) labelTween.kill();
  labelTween = gsap.timeline();
  if (label === "") {
    if (wasShown) labelTween.to(bar, { autoAlpha: 0, duration: animate ? 0.3 : 0 });
    return;
  }
  shownLabel = label;
  const fill = () => HD.set(".focus_label .label", label, { duration: 0 });
  if (wasShown && animate) {
    labelTween.to(bar, { autoAlpha: 0, duration: 0.25 }).call(fill);
  } else {
    gsap.set(bar, { autoAlpha: 0 });
    fill();
  }
  labelTween.to(bar, { autoAlpha: 1, duration: animate ? 0.4 : 0 }, animate ? cameraTime() * 0.6 : 0);
}

// Moves a set, round name or line to a layer
function moveTo(el, name) {
  const layer = layers[name];
  const parent = el.tagName != "path" ? layer.html : el.classList.contains("shadow") ? layer.shadows : layer.lines;
  parent.appendChild(el);
  layerOf.set(el, name);
}

const layerElements = (name) => [layers[name].html, layers[name].svg];

// Ends the layers' fades, the ones faded going to the base or lit layer,
// and with all, the ones lit while the base faded in going back to it
function settle(all = true) {
  fades.forEach((tween) => tween.kill());
  fades = [];
  if (settling) settling.kill();
  settling = null;
  const hasFocus = document.body.classList.contains("has_focus");
  for (const [el, name] of layerOf) {
    if (name == "to_dim") moveTo(el, "base");
    else if (name == "to_lit") moveTo(el, "lit");
    else if (all && name == "lit" && !hasFocus) moveTo(el, "base");
  }
  if (layers.base) gsap.set([...layerElements("to_dim"), ...layerElements("to_lit")], { clearProps: "opacity" });
}

// Dims the sets, round names and lines out of focus (none with no set in
// it). In focus, they're in the lit layer, the rest in the base, dimmed with
// a focus; the ones changing focus are faded together, a layer each way.
function dim(focused, hasFocus, animate) {
  const base = layerElements("base");
  const hadFocus = document.body.classList.contains("has_focus");
  // Where the base is, even halfway through a fade
  const from = parseFloat(getComputedStyle(base[0]).opacity);
  settle(false);
  $("body").toggleClass("has_focus", hasFocus);
  gsap.set(base, { clearProps: "opacity" });
  const to = parseFloat(getComputedStyle(base[0]).opacity);

  for (const [el, f] of focused) {
    const layer = hasFocus && f ? "lit" : "base";
    if (layerOf.get(el) == layer) continue;
    if (!animate || (!hadFocus && layer == "base")) {
      moveTo(el, layer);
    } else if (!hadFocus || !hasFocus) {
      // The base fading out under them, or in up to them: they stay lit
      if (layer == "lit") moveTo(el, layer);
    } else {
      moveTo(el, layer == "lit" ? "to_lit" : "to_dim");
    }
  }
  if (!animate) return settle();

  const fade = (targets, from, to) =>
    gsap.fromTo(targets, { opacity: from }, { opacity: to, duration: FADE_TIME, ease: "power1.inOut" });
  // The base stays dimmed (to) while the ones changing focus fade
  fades = [fade(layerElements("to_dim"), 1, to), fade(layerElements("to_lit"), to, 1)];
  if (from != to) {
    fades.push(fade(base, from, to).eventCallback("onComplete", () => gsap.set(base, { clearProps: "opacity" })));
  }
  // Once the camera is still: moving elements has them laid out again
  settling = gsap.delayedCall(Math.max(cameraTime(), FADE_TIME) + 0.1, settle);
}

function applyFocus(s, data, animate) {
  const focus = focusOf(s, data);
  const inFocus = new Set((focus.sets || []).filter((id) => placed.sets[id]));
  const rounds = new Set(focus.rounds || []);

  // Each set, line and round name: whether it's in focus. Hundreds of
  // elements in a big bracket: without jQuery.
  const focused = new Map();
  for (const el of document.querySelectorAll(".bf_sets .slot")) {
    focused.set(el, inFocus.has(el.dataset.set));
  }
  for (const el of document.querySelectorAll(".bf_lines path")) {
    const { from, to } = el.dataset;
    focused.set(el, inFocus.has(from) && (to == null || inFocus.has(to)));
  }
  // A round is highlighted when it's in focus, and not dimmed while any of
  // its sets is
  const columns = _.keyBy(Object.values(_.get(data, "bracket.bracket.sides", {})).flat(), "key");
  for (const el of document.querySelectorAll(".bf_round_name")) {
    const column = columns[el.dataset.round];
    focused.set(el, rounds.has(el.dataset.round) || !!(column && column.sets.some((id) => inFocus.has(id))));
  }

  dim(focused, inFocus.size > 0, animate);
  // After they're moved: an element is styled where it is before its
  // outline is transitioned in (or out)
  void getComputedStyle(layers.lit.html).opacity;
  for (const [el, f] of focused) el.classList.toggle("focused", f);

  // The player whose run it is
  $(".slot .player").removeClass("focus_player");
  if (focus.mode == "player" && focus.player != null) {
    const sets = _.get(data, "bracket.bracket.sets", {});
    inFocus.forEach((id) =>
      (sets[id].players || []).forEach((p, slot) => {
        if (p && p.id == focus.player) setElement(id).find(`.slot_p_${slot}`).addClass("focus_player");
      }),
    );
  }

  showLabel(inFocus.size > 0 ? focus.label || "" : "", animate);

  moveCamera(s, focusBox({ sets: [...inFocus], rounds: inFocus.size ? [...rounds] : [] }), animate);
}

// ---------------------------------------------------------------------
// Updating sets

// Every set with all, else only those that changed since old, or whose
// players did (a big bracket has hundreds of sets, a dozen fields each)
function updateSets(s, data, old, all) {
  const bracket = data.bracket.bracket;
  const columns = _.keyBy(Object.values(bracket.sides || {}).flat(), "key");
  $(".bf_round_name").each((_i, el) => {
    const column = columns[el.dataset.round];
    HD.set(el, column ? column.name : "");
  });
  const byes = HDBracket.ByesText(bracket);
  $(".byes").each((_i, el) => HD.set(el, byes[el.dataset.round] ? `Bye: ${byes[el.dataset.round]}` : ""));

  const oldSets = _.get(old, "bracket.bracket.sets") || {};
  const players = _.get(data, "bracket.players.slot") || {};
  const oldPlayers = _.get(old, "bracket.players.slot") || {};
  const changedPlayers = new Set(
    all
      ? []
      : _.union(Object.keys(players), Object.keys(oldPlayers)).filter((id) => !_.isEqual(players[id], oldPlayers[id])),
  );
  const changed = (id, set) =>
    all || !_.isEqual(set, oldSets[id]) || set.players.some((p) => p && p.id && changedPlayers.has(String(p.id)));

  for (const id of Object.keys(placed.sets)) {
    const set = bracket.sets[id];
    const element = setElement(id);
    if (set && element.get(0) && changed(id, set)) HDBracket.UpdateSet(s, element, set, data);
  }
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["bracket", "score", "game", "tournamentInfo", "commentary"],
  init() {
    // The page (e.g. the browser source) was resized
    $(window).on("resize", () => placed && camera && moveCamera(HD.scope(), camera, false));
  },

  update(s) {
    const channel = channelOf(s);
    const data = HDBracket.ForChannel(s.data, channel);
    const old = HDBracket.ForChannel(s.old, channel) || {};

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      settle();
      layers = {};
      layerOf = new Map();
      HD.render(".bf_sets, .bf_lines, .bf_standings", "");
      $("body").removeClass("has_focus");
      showLabel("", false);
      lastSignature = null;
      placed = null;
      return;
    }

    let built = false;
    const signature = HDBracket.Signature(data);
    if (signature != lastSignature) {
      lastSignature = signature;
      build(data);
      built = true;
    }

    const all = built || s.changed("layout_theme") || old.bracket?.playersPath !== data.bracket.playersPath;
    const changed =
      all ||
      !_.isEqual(_.get(data, "bracket.bracket"), _.get(old, "bracket.bracket")) ||
      !_.isEqual(_.get(data, "bracket.players"), _.get(old, "bracket.players"));
    if (changed) updateSets(s, data, old, all);

    const standings = HDBracket.IsPool(data.bracket.bracket) ? HDBracket.StandingsHtml(data) : null;
    const standingsChanged = !!standings && HD.build(".bf_standings", String(standings), standings);

    // Every update, so a change to the theme shows right away
    const focus = focusOf(s, data);
    $("body").toggleClass("no_focus_glow", !glows(focus));
    document.body.style.setProperty("--focus-color", glowColor(focus));

    const focusKey = JSON.stringify([focusOf(s, data), s.settings.ignore_focus, maxZoom(s)]);
    if (built || standingsChanged || focusKey != lastFocus) {
      // The first time it's just there; after that, the camera moves
      applyFocus(s, data, lastFocus != null && !built);
      lastFocus = focusKey;
    }

    s.set(".tournament_name", data.tournamentInfo.tournamentName);
    s.set(".event_name", data.tournamentInfo.eventName);
    s.set(".bracket_name", data.bracket.phase || data.bracket.bracket.name);
    s.set(".pool_name", data.bracket.phaseGroup);
  },
});
