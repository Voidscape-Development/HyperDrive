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
// For testing how smooth a move is (see the detail, below):
//   no_redraw_steps  the bracket isn't drawn again while the camera moves,
//                    only once it has stopped: softer during a zoom in
//   focus_after_move  the sets in focus are only lit and outlined, and the
//                     rest dimmed, once the camera has stopped, at once:
//                     nothing changes layer while it moves
// no_title.html has no title bar: the bracket takes the whole page.

// ---------------------------------------------------------------------
// Sizes

// Sizes in world pixels, before zooming. HyperDrive places the bracket
// (bracket.channels.<channel>.placement, src/Helpers/BracketPlacement.py),
// with this margin around it.
const MARGIN = 40;
// Room left around what's in focus, in screen pixels, and under it for the
// caption saying what it is
const PADDING = 60;
const LABEL_ROOM = 90;
// A round name's room above its sets (BracketPlacement.py's HEADER_H)
const HEADER_ROOM = 56;
// The camera's move, in seconds: the layout theme's "Bracket focus zoom time"
const cameraTime = () => HD.theme("bracket", "focus_time", 1000) / 1000;
const FADE_TIME = 0.6;
const STAGGER_TIME = 1.5;

// The layers the sets, round names and lines are in, bottom to top: the
// base (everything, dimmed while there's a focus), the ones fading out of
// focus and into it, and the ones in focus. Dimming is one opacity on a
// layer, not one on each of hundreds of sets and lines. Moving an element to
// another layer has it laid out again, so only the few changing focus move:
// zooming in from the whole bracket, the base fades out under the sets in
// focus.
const LAYERS = ["base", "to_dim", "to_lit", "lit"];
// Over them, the outlines of what's in focus (a ring around each set, a
// colored copy of each line, a bar under each round name): the ones staying,
// going and coming. An outline fading on its set would have the set drawn
// again every frame; a layer of them only changes opacity.
const GLOWS = ["glow_lit", "glow_out", "glow_in"];

// Nothing is drawn while the camera moves or the focus fades: each layer is
// drawn once by the browser, then only moved, scaled and faded by its
// compositor, with animations that run there (the Web Animations API), off
// the page's thread. So a move stays smooth whatever the page is doing
// (taking a new state in, filling sets in, moving sets between layers).
//
// A layer is drawn at one size, its detail (the scale its content has, see
// setDetail), and the camera scales that picture. Still, the detail is the
// camera's scale: sharp, and no more than a screen of pixels. Moving, the
// detail follows the scale in steps, so the picture is never enlarged by
// more than DETAIL_BLUR (soft) nor shrunk by more than DETAIL_SHRINK (which
// would be the whole bracket drawn at full size, zooming out of one set).
// Each step draws about a screen of pixels, off the page's thread too, and
// is swapped in when ready.
const DETAIL_BLUR = 1.3;
const DETAIL_SHRINK = 2;
// Zooming in, a step draws ahead by this much (what's on screen then, most
// of which is about to leave it, at more detail than it needs yet)
const DETAIL_AHEAD = 1.6;

// ---------------------------------------------------------------------
// State

// Set id: number used in class names (ids can be anything)
let setIndex = {};
// Set id: its element, as build() made it
let setElements = {};
// Where HyperDrive placed the bracket: {sets: {id: {x, y, w, h}}, headers,
// byes, standings, lines, width, height}
let placed = null;
let lastSignature = null;
let lastFocus = null;
let camera = null;
// Where the camera rests, or is going (see placeView), and its move under way:
// {from, to, at(t), start, duration, samples, animations, frame}
let view = null;
let move = null;
// The scale the layers are drawn at
let detail = null;
// The focus caption's text, and its fade under way
let shownLabel = null;
let labelTween = null;
// Layer name: its elements, {el, detail, html, shadows, lines, rings}, as
// build() made them
let layers = {};
// Each set, round name and line: the name of its layer
let layerOf = new Map();
// What's outlined ("set:<id>", "line:<from>><to>", "round:<key>") or
// pinned ("pin:<y>:<key>", see pinHeaders): its element and layer, {el, layer}
let glowOf = new Map();
// "<y>:<round key>": where a round name is pinned, {x, y, w, h, round, name}
let pins = {};
// "<from>><to>": the line's path
let linePaths = {};
// The layers' fades under way (animations), and putting what they faded
// where it goes
let fades = [];
let settling = null;

const setElement = (id) => setElements[id] || $();
const box = (b) => `left: ${b.x}px; top: ${b.y}px; width: ${b.w}px;${b.h ? ` height: ${b.h}px;` : ""}`;

// ---------------------------------------------------------------------
// Drawing

// The lines, or their shadows (a copy under each, see index.css)
const lineKey = (p) => `${p.from}>${p.to == null ? "" : p.to}`;
const linesHtml = (paths, cls) =>
  paths.map(
    (p) =>
      HD.html`<path class="${cls}" data-from="${p.from}" ${p.to != null && HD.html`data-to="${p.to}"`} d="${p.d}" />`,
  );

function build(data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  setIndex = {};
  placed = data.bracket.placement;
  settle();
  stopMove();

  // Everything starts in the base; applyFocus() lifts what's in focus
  const paths = HDBracket.Lines(placed);
  linePaths = _.keyBy(paths, lineKey);
  const size = HD.raw(`width="${placed.width}" height="${placed.height}"`);
  HD.render(".world", [
    LAYERS.map(
      (name) => HD.html`
        <div class="bf_layer bf_${name}"><div class="bf_detail">
          <svg class="bf_lines" ${size}>
            <g class="shadows">${name == "base" && linesHtml(paths, "line shadow")}</g>
            <g class="lines">${name == "base" && linesHtml(paths, "line")}</g>
          </svg>
          <div class="bf_sets">
            ${
              name == "base" && [
                Object.entries(placed.byes).map(
                  ([key, b]) => HD.html`<div class="byes" data-round="${key}" style="${box(b)}"></div>`,
                ),
                Object.entries(placed.headers).map(
                  ([key, h]) => HD.html`<div class="bf_round_name" data-round="${key}" style="${box(h)}"></div>`,
                ),
                paths
                  .filter((p) => p.label)
                  .map(
                    (p) =>
                      HD.html`<div class="progression_label" data-from="${p.from}" style="left: ${p.end[0] + 10}px; top: ${p.end[1]}px">${p.label}</div>`,
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
          </div>
          ${name == "base" && HD.html`<div class="bf_standings"></div>`}
        </div></div>`,
    ),
    GLOWS.map(
      (name) => HD.html`
        <div class="bf_layer bf_glow bf_${name}"><div class="bf_detail">
          <svg class="bf_lines" ${size}><g class="lines"></g></svg>
          <div class="bf_rings"></div>
        </div></div>`,
    ),
  ]);
  setElements = {};
  $(".bf_sets .slot").each((_i, el) => (setElements[el.dataset.set] = $(el)));
  layers = {};
  for (const name of [...LAYERS, ...GLOWS]) {
    const el = document.querySelector(`.world .bf_${name}`);
    layers[name] = {
      el,
      detail: el.querySelector(".bf_detail"),
      html: el.querySelector(".bf_sets"),
      shadows: el.querySelector(".shadows"),
      lines: el.querySelector(".lines"),
      rings: el.querySelector(".bf_rings"),
    };
  }
  layerOf = new Map();
  for (const el of document.querySelectorAll(".bf_layer .slot, .bf_layer .bf_round_name, .bf_layer path")) {
    layerOf.set(el, "base");
  }
  glowOf = new Map();
  // The new layers, where the camera is
  detail = null;
  if (view) placeView(view);

  const standings = $(".bf_standings");
  if (placed.standings) standings.css({ left: placed.standings.x, top: placed.standings.y, width: placed.standings.w });
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

// A view shows the world point (cx, cy) at (ax, ay) on screen, at a scale.
// Where that puts the world's corner:
const cornerOf = (v) => ({ x: v.ax - v.cx * v.scale, y: v.ay - v.cy * v.scale });

// The layers' transform for a view: the layers are drawn at the detail, the
// rest of the scale is the camera's
function cameraCss(v) {
  const { x, y } = cornerOf(v);
  return `translate(${x}px, ${y}px) scale(${v.scale / detail})`;
}

// Draws the layers at a scale. Returns whether that changed.
function setDetail(scale) {
  if (scale === detail) return false;
  detail = scale;
  for (const layer of Object.values(layers)) layer.detail.style.transform = `scale(${scale})`;
  return true;
}

const now = () => document.timeline.currentTime ?? performance.now();

// Where the camera is, even halfway through a move
function viewNow() {
  if (!move) return view;
  const t = (now() - move.start) / move.duration;
  return t >= 1 ? move.to : move.at(Math.max(0, t));
}

// Stops the camera's move where it is. The layers are still where they
// were before it: placeView() or a new move puts them right.
function stopMove() {
  if (!move) return;
  view = viewNow();
  cancelAnimationFrame(move.frame);
  move.animations.forEach((animation) => animation.cancel());
  move = null;
}

// Puts the camera at a view, still: the layers drawn at its scale, and only
// moved (by whole pixels, or their picture would be drawn between pixels,
// soft)
function placeView(v) {
  const corner = cornerOf(v);
  const [x, y] = [Math.round(corner.x), Math.round(corner.y)];
  const moving = move;
  move = null;
  view = { ...v, ax: x + v.cx * v.scale, ay: y + v.cy * v.scale };
  setDetail(v.scale);
  for (const layer of Object.values(layers)) layer.el.style.transform = `translate(${x}px, ${y}px)`;
  if (moving) {
    cancelAnimationFrame(moving.frame);
    moving.animations.forEach((animation) => animation.cancel());
  }
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

// GSAP's power2.inOut and power2.out
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t) => 1 - Math.pow(1 - t, 3);

// The detail the layers should have at a moment (0 to 1) of the move
function detailFor(t) {
  const samples = move.samples;
  const scale = move.at(t).scale;
  if (scale > detail * DETAIL_BLUR) {
    // Zooming in: ahead, but no more than the move ever needs
    const most = Math.max(scale, ...samples.slice(Math.floor(t * (samples.length - 1))).map((v) => v.scale));
    const ahead = scale * DETAIL_AHEAD;
    return most <= ahead * DETAIL_BLUR ? most : ahead;
  }
  return scale < detail / DETAIL_SHRINK ? scale : detail;
}

// Starts the layers along the move (or along the rest of it, after their
// detail changed): one animation each, all on the same clock. The compositor
// runs them; one replaced by another takes over where it was, once what it
// shows is drawn.
function animateMove() {
  const last = move.samples.length - 1;
  const keyframes = move.samples.map((v, i) => ({ transform: cameraCss(v), offset: i / last }));
  const old = move.animations;
  move.animations = Object.values(layers).map((layer) => {
    const animation = layer.el.animate(keyframes, { duration: move.duration, fill: "both" });
    animation.startTime = move.start;
    return animation;
  });
  old.forEach((animation) => animation.cancel());
}

// Each frame of a move: the page only has to keep the detail in step and
// end the move. The frames also have the browser draw the parts of the
// bracket the camera is getting to.
function moveFrame() {
  if (!move) return;
  const t = (now() - move.start) / move.duration;
  if (t >= 1) return placeView(move.to);
  if (!HD.settings.no_redraw_steps && setDetail(detailFor(Math.max(0, t)))) animateMove();
  move.frame = requestAnimationFrame(moveFrame);
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

  // From wherever it is, even halfway through another move, which it then
  // carries on from at speed instead of starting from a stop
  const from = viewNow();
  const ease = move ? easeOut : easeInOut;
  // The layout theme's animation speed (none before the layout is first
  // shown, or with animations off)
  const speed = gsap.globalTimeline.timeScale();
  const duration = speed > 0 ? (cameraTime() * 1000) / speed : 0;
  if (!animate || !from || detail == null || duration < 20) return placeView(to);

  stopMove();
  // Ending on whole pixels, as placeView() leaves it
  const corner = cornerOf(to);
  to.ax += Math.round(corner.x) - corner.x;
  to.ay += Math.round(corner.y) - corner.y;
  move = { to, at: (t) => between(from, to, ease(t)), start: now(), duration, animations: [], frame: null };
  const steps = Math.max(2, Math.min(240, Math.ceil(duration / 16)));
  move.samples = Array.from({ length: steps + 1 }, (_v, i) => move.at(i / steps));
  view = to;
  animateMove();
  move.frame = requestAnimationFrame(moveFrame);
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

// Moves an outline to a layer of them
function moveGlow(glow, name) {
  (glow.el.tagName == "path" ? layers[name].lines : layers[name].rings).appendChild(glow.el);
  glow.layer = name;
}

// Fades a layer, on the compositor. Kept (fill) until settle() ends it.
function fade(name, from, to) {
  const duration = (FADE_TIME * 1000) / (gsap.globalTimeline.timeScale() || 1);
  // GSAP's power1.inOut, near enough
  const options = { duration, easing: "cubic-bezier(0.45, 0, 0.55, 1)", fill: "both" };
  return layers[name].el.animate([{ opacity: from }, { opacity: to }], options);
}

// Ends the layers' fades, the ones faded going to the base or lit layer,
// and with all, the ones lit while the base faded in going back to it
function settle(all = true) {
  fades.forEach((animation) => animation.cancel());
  fades = [];
  if (settling) settling.kill();
  settling = null;
  const hasFocus = document.body.classList.contains("has_focus");
  for (const [el, name] of layerOf) {
    if (name == "to_dim") moveTo(el, "base");
    else if (name == "to_lit") moveTo(el, "lit");
    else if (all && name == "lit" && !hasFocus) moveTo(el, "base");
  }
  for (const [key, glow] of glowOf) {
    if (glow.layer == "glow_in") moveGlow(glow, "glow_lit");
    else if (glow.layer == "glow_out") {
      glow.el.remove();
      glowOf.delete(key);
    }
  }
}

// Dims the sets, round names and lines out of focus (none with no set in
// it). In focus, they're in the lit layer, the rest in the base, dimmed with
// a focus; the ones changing focus are faded together, a layer each way.
function dim(focused, hasFocus, animate) {
  const base = layers.base.el;
  const hadFocus = document.body.classList.contains("has_focus");
  // Where the base is, even halfway through a fade
  const from = parseFloat(getComputedStyle(base).opacity);
  settle(false);
  $("body").toggleClass("has_focus", hasFocus);
  const to = parseFloat(getComputedStyle(base).opacity);

  const moved = { to_dim: false, to_lit: false };
  for (const [el, f] of focused) {
    const layer = hasFocus && f ? "lit" : "base";
    if (layerOf.get(el) == layer) continue;
    if (!animate || (!hadFocus && layer == "base")) {
      moveTo(el, layer);
    } else if (!hadFocus || !hasFocus) {
      // The base fading out under them, or in up to them: they stay lit
      if (layer == "lit") moveTo(el, layer);
    } else {
      const through = layer == "lit" ? "to_lit" : "to_dim";
      moveTo(el, through);
      moved[through] = true;
    }
  }
  if (!animate) return;

  // The base stays dimmed (to) while the ones changing focus fade
  if (moved.to_dim) fades.push(fade("to_dim", 1, to));
  if (moved.to_lit) fades.push(fade("to_lit", to, 1));
  if (from != to) fades.push(fade("base", from, to));
}

// The outline of a set, a line or a round name
function glowElement(key) {
  const [kind, id] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
  if (kind == "line") {
    if (!linePaths[id]) return null;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("class", "line");
    path.setAttribute("d", linePaths[id].d);
    return path;
  }
  const at = kind == "set" ? placed.sets[id] : kind == "pin" ? pins[id] : placed.headers[id];
  if (!at) return null;
  const el = document.createElement("div");
  el.className = kind == "set" ? "bf_ring" : kind == "pin" ? "bf_round_name bf_pin" : "bf_bar";
  el.style.cssText = box(at);
  if (kind == "pin") {
    el.dataset.round = at.round;
    HD.set(el, at.name, { duration: 0 });
  }
  return el;
}

// Outlines what's in focus (keys, see glowOf): outlines going and coming
// are faded together, a layer each way
function glow(keys, animate) {
  let [coming, going] = [false, false];
  for (const [key, entry] of glowOf) {
    if (keys.has(key)) continue;
    if (animate) {
      moveGlow(entry, "glow_out");
      going = true;
    } else {
      entry.el.remove();
      glowOf.delete(key);
    }
  }
  for (const key of keys) {
    if (glowOf.has(key)) continue;
    const el = glowElement(key);
    if (!el) continue;
    const entry = { el, layer: null };
    glowOf.set(key, entry);
    moveGlow(entry, animate ? "glow_in" : "glow_lit");
    coming = true;
  }
  if (!animate) return;
  if (going) fades.push(fade("glow_out", 1, 0));
  if (coming) fades.push(fade("glow_in", 0, 1));
}

// Where a set, round name or line is, in world pixels: its element, or its
// outline's key (see glowOf)
function boxOf(thing) {
  let key = thing;
  if (typeof thing != "string") {
    const { set, round, from, to } = thing.dataset;
    if (thing.tagName == "path") key = `line:${from}>${to == null ? "" : to}`;
    else key = set != null ? `set:${set}` : `round:${round}`;
  }
  const [kind, id] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
  if (kind == "set") return placed.sets[id];
  if (kind == "round") return placed.headers[id];
  if (kind == "pin") return pins[id];
  // A line: around the sets it joins
  const [from, to] = id.split(">").map((set) => placed.sets[set]);
  if (!from || !to) return from || to;
  const [x, y] = [Math.min(from.x, to.x), Math.min(from.y, to.y)];
  return {
    x,
    y,
    w: Math.max(from.x + from.w, to.x + to.w) - x,
    h: Math.max(from.y + from.h, to.y + to.h) - y,
  };
}

// Whether a box (world pixels) is on screen where the camera is now, even
// in part. Everything is, before the camera is placed.
function onScreen() {
  const v = viewNow();
  const viewport = $(".viewport");
  const [vw, vh] = [viewport.width(), viewport.height()];
  if (!v || !vw || !vh) return () => true;
  const corner = cornerOf(v);
  const [left, top] = [-corner.x / v.scale, -corner.y / v.scale];
  const [right, bottom] = [left + vw / v.scale, top + vh / v.scale];
  return (b) => !b || (b.x + b.w > left && b.x < right && b.y + (b.h || 0) > top && b.y < bottom);
}

function applyFocus(s, data, animate) {
  const focus = focusOf(s, data);
  const inFocus = new Set((focus.sets || []).filter((id) => placed.sets[id]));
  const rounds = new Set(focus.rounds || []);
  const hasFocus = inFocus.size > 0;

  // Each set, line and round name: whether it's in focus. Hundreds of
  // elements in a big bracket: without jQuery.
  const focused = new Map();
  // What's outlined, with the layout theme's "Focus glow" on for the mode
  const outlined = new Set();
  const outline = hasFocus && glows(focus);
  for (const el of document.querySelectorAll(".bf_sets .slot")) {
    const f = inFocus.has(el.dataset.set);
    focused.set(el, f);
    if (f && outline) outlined.add(`set:${el.dataset.set}`);
  }
  for (const el of document.querySelectorAll(".bf_layer:not(.bf_glow) .bf_lines path")) {
    const { from, to } = el.dataset;
    const f = inFocus.has(from) && (to == null || inFocus.has(to));
    focused.set(el, f);
    if (f && outline) outlined.add(`line:${from}>${to == null ? "" : to}`);
  }
  for (const el of document.querySelectorAll(".bf_sets .progression_label"))
    focused.set(el, inFocus.has(el.dataset.from));
  // A round is highlighted when it's in focus, and not dimmed while any of
  // its sets is
  const columns = _.keyBy(Object.values(_.get(data, "bracket.bracket.sides", {})).flat(), "key");
  for (const el of document.querySelectorAll(".bf_sets .bf_round_name")) {
    const column = columns[el.dataset.round];
    const f = rounds.has(el.dataset.round) || !!(column && column.sets.some((id) => inFocus.has(id)));
    focused.set(el, f);
    if (f && glows(focus)) outlined.add(`round:${el.dataset.round}`);
  }
  const target = pinHeaders(columns, inFocus, focusBox({ sets: [...inFocus], rounds: hasFocus ? [...rounds] : [] }));
  for (const key of Object.keys(pins)) outlined.add(`pin:${key}`);

  if (animate && HD.settings.focus_after_move) {
    // Testing: the camera moves over the bracket as it was
    settle();
    settling = gsap.delayedCall(cameraTime() + 0.05, () => {
      dim(focused, hasFocus, false);
      glow(outlined, false);
      settle();
    });
  } else if (!animate) {
    dim(focused, hasFocus, false);
    glow(outlined, false);
    settle();
  } else {
    // What's on screen changes layer now: the browser draws the layers it
    // changes before showing them, in one go. What's off screen would be
    // drawn as the camera gets to it, halfway through the move, and that
    // drops frames: it changes once the camera is still and it's on
    // screen. All that comes into focus together, and all that leaves it
    // together: a side isn't lit in two halves.
    const seen = onScreen();
    const isLit = (el) => ["lit", "to_lit"].includes(layerOf.get(el));
    const coming = [...focused].filter(([el, f]) => f && !isLit(el)).map(([el]) => el);
    const going = [...focused].filter(([el, f]) => !f && isLit(el)).map(([el]) => el);
    const comingGlows = [...outlined].filter((key) => !glowOf.has(key));
    const goingGlows = [...glowOf.keys()].filter((key) => !outlined.has(key));
    const allSeen = (things) => things.every((thing) => seen(boxOf(thing)));
    const comeNow = allSeen(coming) && allSeen(comingGlows);
    const goNow = allSeen(going) && allSeen(goingGlows);
    const later = !comeNow || !goNow;

    const now = new Map(focused);
    if (!comeNow) for (const el of coming) now.set(el, false);
    if (!goNow) for (const el of going) now.set(el, true);
    const outlinedNow = new Set(outlined);
    if (!comeNow) for (const key of comingGlows) outlinedNow.delete(key);
    if (!goNow) for (const key of goingGlows) outlinedNow.add(key);

    dim(now, hasFocus, true);
    glow(outlinedNow, true);
    // Once the camera is still and the fades are over
    const still = Math.max(cameraTime(), FADE_TIME);
    if (later) {
      settling = gsap.delayedCall(still + 0.05, () => {
        dim(focused, hasFocus, true);
        glow(outlined, true);
        settling = gsap.delayedCall(FADE_TIME + 0.1, settle);
      });
    } else {
      // Moving elements has them laid out again
      settling = gsap.delayedCall(still + 0.1, settle);
    }
  }
  for (const [el, f] of focused) if (el.classList.contains("focused") != f) el.classList.toggle("focused", f);

  // The player whose run it is
  $(".slot .player.focus_player").removeClass("focus_player");
  if (focus.mode == "player" && focus.player != null) {
    const sets = _.get(data, "bracket.bracket.sets", {});
    inFocus.forEach((id) =>
      (sets[id].players || []).forEach((p, slot) => {
        if (p && p.id == focus.player) setElement(id).find(`.slot_p_${slot}`).addClass("focus_player");
      }),
    );
  }

  showLabel(hasFocus ? focus.label || "" : "", animate);

  moveCamera(s, target, animate);
}

// The round names of the sets in focus that are above what's in focus (the
// winners side's, in a run through losers) are shown just above it: their
// own if near enough, else a copy pinned there (pins). Returns the box the
// camera shows, with them.
function pinHeaders(columns, inFocus, target) {
  pins = {};
  if (!inFocus.size || $("body").hasClass("hd-bracket-hide-round-names")) return target;
  const top = target.y - HEADER_ROOM;
  let above = false;
  for (const column of Object.values(columns)) {
    const h = placed.headers[column.key];
    if (!h || h.y >= target.y || !column.sets.some((id) => inFocus.has(id))) continue;
    above = true;
    if (h.y < top) pins[`${top}:${column.key}`] = { ...h, y: top, round: column.key, name: column.name };
  }
  return above ? { ...target, y: top, h: target.h + HEADER_ROOM } : target;
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

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides || !data.bracket.placement) {
      settle();
      stopMove();
      layers = {};
      layerOf = new Map();
      glowOf = new Map();
      detail = null;
      HD.render(".world", "");
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

    const focusKey = JSON.stringify([focus, glows(focus), s.settings.ignore_focus, maxZoom(s)]);
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
