// A proof page, not a layout to use on stream: the same bracket, focus and
// camera as index.js, drawn another way, to see whether it stays smooth in
// OBS and looks the same.
//
// index.js has the browser move and fade the bracket's elements, and the
// frames it drops come from the browser drawing or re-layering them while
// the camera moves. Here every set and round name is drawn by the browser
// once, off screen, and photographed into pictures (sheets). A move is then
// one canvas: each frame pastes the pictures in view at the camera's place
// and scale, more or less transparent for the dimming. Nothing is drawn
// again or changes layer while the camera moves. Still, the sets in view
// are pasted from the photograph itself (a vector), sharp at any scale.
//
// Not done here: pool standings, byes, the player whose run is in focus,
// the sets' entrance. Options: channel, ignore_focus and max_zoom, as
// index.js.

/* global XMLHttpRequest, FileReader, XMLSerializer, Blob, Path2D */

// ---------------------------------------------------------------------
// Sizes, placing and the camera's path: as index.js
const PLAYER_H = 40;
const SET_GAP = 2;
const SET_W = 380;
const SET_H = PLAYER_H * 2 + SET_GAP;
const COLUMN_GAP = 100;
const ROW_GAP = 24;
const HEADER_H = 56;
const SECTION_GAP = 90;
const MARGIN = 40;
const PADDING = 60;
const LABEL_ROOM = 90;
const cameraTime = () => HD.theme("bracket", "focus_time", 1000) / 1000;
const FADE_TIME = 0.6;

let placed = null;
let shownLabel = null;
let labelTween = null;

const isShown = (set) => set && HDBracket.SetState(set, true) != "hidden";

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
        // To the middle of the set, so the two sets feeding it share one line into it
        const b = [to.x, to.y + to.h / 2];
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

function maxZoom(s) {
  const zoom = parseFloat(s.settings.max_zoom || HD.theme("bracket", "focus_max_zoom", 200));
  return (isFinite(zoom) && zoom > 0 ? zoom : 200) / 100;
}

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

const cornerOf = (v) => ({ x: v.ax - v.cx * v.scale, y: v.ay - v.cy * v.scale });
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
const channelOf = (s) => HDBracket.ChannelName(s.settings.channel) || "main";
const focusOf = (s, data) =>
  (!s.settings.ignore_focus && _.get(data, ["bracket", "focus", channelOf(s)])) || { sets: [], rounds: [] };
const glows = (focus) => !focus.mode || HD.theme("bracket", `focus_glow_${focus.mode}`, true) !== false;
const glowColor = (focus) =>
  focus.mode && HD.theme("bracket", `focus_glow_custom_${focus.mode}`, false) === true
    ? `var(--bracket-focus-glow-color-${focus.mode})`
    : null;

// ---------------------------------------------------------------------
// Photographs

// Room kept around an element for its shadow, in world pixels
const SHOT_MARGIN = 8;
const CELL_W = SET_W + SHOT_MARGIN * 2;
const CELL_H = SET_H + SHOT_MARGIN * 2;
// A sheet's most pixels a side, and how many smaller copies of it are kept
// (each half the one before), so a picture is never shrunk by much more
// than 2 when pasted: sharp enough moving, and no shimmer
const SHEET_PX = 4096;
const LEVELS = 4;
// The glow reaches this far around a set
const RING_ROOM = 44;

// "set:<id>" and "round:<key>": {key, box, el, sheet, cx, cy, alpha, glow},
// box in world pixels, (cx, cy) its cell's corner in its sheet
let items = {};
// {el, width, height, scale, image, levels, shot, pending, seen, version}
let sheets = [];
// {from, to, path, box, alpha, glow}
let paths = [];
// What index.css gives the page: read once the bracket is built
let look = { dim: 0.3, focus: "#ffb800", line: "#000", radius: 0 };
let ring = null;

// Url: a promise of it as a data: URL (null if it can't be read). With
// XMLHttpRequest, which also reads files when OBS opens the page from one.
const dataUrls = new Map();
function dataUrl(url) {
  if (url.startsWith("data:")) return Promise.resolve(url);
  if (!dataUrls.has(url)) {
    dataUrls.set(
      url,
      new Promise((resolve) => {
        const request = new XMLHttpRequest();
        request.open("GET", url);
        request.responseType = "blob";
        request.onerror = () => resolve(null);
        request.onload = () => {
          if (request.status && request.status >= 400) return resolve(null);
          const reader = new FileReader();
          reader.onerror = () => resolve(null);
          reader.onload = () => resolve(reader.result);
          reader.readAsDataURL(request.response);
        };
        request.send();
      }),
    );
  }
  return dataUrls.get(url);
}

function readText(url) {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("GET", url);
    request.onerror = () => resolve("");
    request.onload = () => resolve(request.responseText || "");
    request.send();
  });
}

// The @font-face rules of the page's style sheets, read as text (their rules
// can't be listed when the page is opened from a file):
// [{family, weight, url}]
let fontFaces = null;
async function loadFontFaces() {
  if (fontFaces) return fontFaces;
  fontFaces = [];
  for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {
    const css = await readText(link.href);
    for (const rule of css.match(/@font-face\s*{[^}]*}/g) || []) {
      const family = (rule.match(/font-family:\s*([^;]+);/) || [])[1];
      const url = (rule.match(/url\(\s*["']?([^"')]+)["']?\s*\)/) || [])[1];
      const weight = ((rule.match(/font-weight:\s*([^;]+);/) || [])[1] || "400").trim();
      if (family && url) {
        fontFaces.push({
          family: family.trim().replace(/^["']|["']$/g, ""),
          weight,
          url: new URL(url, link.href).href,
        });
      }
    }
  }
  return fontFaces;
}

// The fonts the page has loaded (the ones it uses), as @font-face rules
// with the font inside: a photograph can't load files
async function fontCss() {
  const faces = await loadFontFaces();
  const loaded = [...document.fonts].filter((f) => f.status == "loaded");
  const used = faces.filter((face) =>
    loaded.some((f) => f.family.replace(/^["']|["']$/g, "") == face.family && f.weight == face.weight),
  );
  const rules = await Promise.all(
    used.map(async (face) => {
      const data = await dataUrl(face.url);
      return data ? `@font-face{font-family:"${face.family}";src:url("${data}");font-weight:${face.weight};}` : "";
    }),
  );
  return rules.join("");
}

// A tag's style with no style sheet, from an empty frame: an element's
// style is written down as what differs from it
let blank = null;
const defaults = new Map();
function defaultStyle(el) {
  const key = `${el.namespaceURI} ${el.localName}`;
  if (!defaults.has(key)) {
    if (!blank) {
      blank = document.createElement("iframe");
      blank.style.cssText = "position:absolute;left:-10000px;width:10px;height:10px;border:0;visibility:hidden";
      document.body.appendChild(blank);
    }
    const doc = blank.contentDocument;
    const probe = doc.createElementNS(el.namespaceURI, el.localName);
    doc.body.appendChild(probe);
    defaults.set(key, blank.contentWindow.getComputedStyle(probe));
  }
  return defaults.get(key);
}

const SKIPPED_STYLES = /^(transition|animation|will-change|cursor|pointer-events|scroll|overscroll|view-transition)/;

// Writes each element's style, as the page has it, on its copy
function copyStyles(source, target, urls) {
  const style = getComputedStyle(source);
  const base = defaultStyle(source);
  let css = "";
  for (const property of style) {
    if (SKIPPED_STYLES.test(property)) continue;
    const value = style.getPropertyValue(property);
    if (value !== base.getPropertyValue(property)) css += `${property}:${value};`;
  }
  for (const match of css.matchAll(/url\("([^"]+)"\)/g)) urls.add(match[1]);
  target.setAttribute("style", css);
  if (target.localName == "img" && source.currentSrc) {
    target.setAttribute("src", source.currentSrc);
    urls.add(source.currentSrc);
  }
  for (let i = 0; i < source.children.length; i++) copyStyles(source.children[i], target.children[i], urls);
}

// Photographs a sheet: a copy of its elements with their styles, images and
// fonts written inside, as an SVG picture, and that picture at a few sizes
async function shoot(sheet) {
  const version = ++sheet.version;
  const started = performance.now();
  const html = sheet.el.innerHTML;
  // Not started again for the same elements while this one is being made
  sheet.pending = html;
  const copy = sheet.el.cloneNode(true);
  const urls = new Set();
  copyStyles(sheet.el, copy, urls);
  copy.setAttribute(
    "style",
    `${copy.getAttribute("style")}position:relative;left:0;top:0;margin:0;width:${sheet.width}px;height:${sheet.height}px;`,
  );

  const found = new Map(await Promise.all([...urls].map(async (url) => [url, await dataUrl(url)])));
  for (const el of [copy, ...copy.querySelectorAll("*")]) {
    const css = el.getAttribute("style");
    if (css && css.includes("url(")) {
      el.setAttribute(
        "style",
        css.replace(/url\("([^"]+)"\)/g, (all, url) => (found.get(url) ? `url("${found.get(url)}")` : all)),
      );
    }
    if (el.localName == "img" && found.get(el.getAttribute("src"))) {
      el.setAttribute("src", found.get(el.getAttribute("src")));
    }
  }

  const fonts = await fontCss();
  const [w, h] = [sheet.width, sheet.height];
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w * sheet.scale}" height="${h * sheet.scale}" ` +
    `viewBox="0 0 ${w} ${h}"><style>${fonts}</style>` +
    `<foreignObject x="0" y="0" width="${w}" height="${h}">${new XMLSerializer().serializeToString(copy)}` +
    `</foreignObject></svg>`;
  const image = new Image();
  const blob = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    image.src = blob;
    await image.decode();
  } catch (e) {
    console.log("The photograph couldn't be made", e);
    stats.failed = String(e);
    return;
  } finally {
    URL.revokeObjectURL(blob);
  }
  // A newer one was started meanwhile
  if (version != sheet.version) return;

  const levels = [];
  for (let level = 0; level < LEVELS; level++) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round((w * sheet.scale) / 2 ** level));
    canvas.height = Math.max(1, Math.round((h * sheet.scale) / 2 ** level));
    const context = canvas.getContext("2d");
    context.imageSmoothingQuality = "high";
    context.drawImage(level ? levels[level - 1] : image, 0, 0, canvas.width, canvas.height);
    levels.push(canvas);
  }
  sheet.image = image;
  sheet.levels = levels;
  sheet.shot = html;
  stats.shots += 1;
  stats.shotTime = Math.round(performance.now() - started);
  stats.svgSize = Math.round(svg.length / 1024);
  redraw();
}

// Photographs the sheets whose elements changed, once they've stopped
// changing (texts and images are filled in over a few frames)
function checkSheets() {
  for (const sheet of sheets) {
    const html = sheet.el.innerHTML;
    if (html !== sheet.shot && html !== sheet.pending && html === sheet.seen) shoot(sheet);
    sheet.seen = html;
  }
}

// The outline of a set in focus, drawn once: a ring and its glow, as
// index.css's .bf_ring
function makeRing() {
  const scale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = (SET_W + RING_ROOM * 2) * scale;
  canvas.height = (SET_H + RING_ROOM * 2) * scale;
  const c = canvas.getContext("2d");
  c.scale(scale, scale);
  c.translate(RING_ROOM, RING_ROOM);
  c.fillStyle = look.focus;
  c.shadowColor = look.focus;
  c.shadowBlur = 28 * scale;
  c.beginPath();
  c.roundRect(-4, -4, SET_W + 8, SET_H + 8, look.radius + 4);
  c.fill();
  c.shadowColor = "transparent";
  c.beginPath();
  c.roundRect(-4, -4, SET_W + 8, SET_H + 8, look.radius + 4);
  c.fill();
  // Only around the set
  c.globalCompositeOperation = "destination-out";
  c.beginPath();
  c.roundRect(0, 0, SET_W, SET_H, look.radius);
  c.fill();
  return canvas;
}

// The colors and sizes index.css gives the page
function readLook(focus) {
  document.body.style.setProperty("--focus-color", glowColor(focus));
  const probe = document.createElement("div");
  probe.className = "slot";
  probe.style.cssText = "position:absolute;left:-10000px;color:var(--focus-color);";
  probe.style.setProperty("outline-color", "var(--bracket-line-color, var(--lines))");
  document.body.appendChild(probe);
  const style = getComputedStyle(probe);
  const dim = parseFloat(getComputedStyle(document.body).getPropertyValue("--focus-dim"));
  const next = {
    focus: style.color,
    line: style.outlineColor,
    radius: parseFloat(style.borderTopLeftRadius) || 0,
    dim: isFinite(dim) ? (dim > 1 ? dim / 100 : dim) : 0.3,
  };
  probe.remove();
  if (!ring || next.focus != look.focus || next.radius != look.radius) {
    look = next;
    ring = makeRing();
  }
  look = next;
}

// ---------------------------------------------------------------------
// Building

function build(data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  placed = place(bracket);
  move = null;

  const scale = maxZoom(HD.scope());
  const columns = Math.max(1, Math.floor(SHEET_PX / (CELL_W * scale)));
  const rows = Math.max(1, Math.floor(SHEET_PX / (CELL_H * scale)));
  const boxes = [
    ...Object.entries(placed.headers).map(([key, box]) => ({ key: `round:${key}`, kind: "round", id: key, box })),
    ...Object.entries(placed.sets).map(([id, box]) => ({ key: `set:${id}`, kind: "set", id, box })),
  ];

  items = {};
  sheets = [];
  const stage = document.querySelector(".stage");
  stage.innerHTML = "";
  for (let first = 0; first < boxes.length; first += columns * rows) {
    const batch = boxes.slice(first, first + columns * rows);
    const el = document.createElement("div");
    el.className = "sheet";
    const sheet = {
      el,
      width: Math.min(batch.length, columns) * CELL_W,
      height: Math.ceil(batch.length / columns) * CELL_H,
      scale,
      image: null,
      levels: null,
      shot: null,
      pending: null,
      seen: null,
      version: 0,
    };
    el.style.cssText = `position:relative;width:${sheet.width}px;height:${sheet.height}px;`;
    el.innerHTML = String(
      HD.html`${batch.map(({ kind, id, box }, i) => {
        const cx = (i % columns) * CELL_W;
        const cy = Math.floor(i / columns) * CELL_H;
        const at = `left: ${cx + SHOT_MARGIN}px; top: ${cy + SHOT_MARGIN}px; width: ${box.w}px; height: ${box.h}px;`;
        return kind == "round"
          ? HD.html`<div class="bf_round_name" data-round="${id}" style="${at}"></div>`
          : HD.html`
              <div class="slot side_${sets[id].side}" data-set="${id}" style="${at}">
                <div class="set_identifier"><div class="text"></div></div>
                ${HDBracket.PlayerSlotHtml(0)}
                ${HDBracket.PlayerSlotHtml(1)}
              </div>`;
      })}`,
    );
    stage.appendChild(el);
    batch.forEach((item, i) => {
      items[item.key] = {
        ...item,
        el: el.children[i],
        sheet,
        cx: (i % columns) * CELL_W,
        cy: Math.floor(i / columns) * CELL_H,
        alpha: still(1),
        glow: still(0),
      };
    });
    sheets.push(sheet);
  }

  paths = lines(bracket).map((line) => ({
    ...line,
    path: new Path2D(line.d),
    alpha: still(1),
    glow: still(0),
  }));
}

function updateSets(s, data) {
  const bracket = data.bracket.bracket;
  const columns = _.keyBy(Object.values(bracket.sides || {}).flat(), "key");
  for (const item of Object.values(items)) {
    if (item.kind == "round") {
      HD.set(item.el, columns[item.id] ? columns[item.id].name : "");
    } else if (bracket.sets[item.id]) {
      HDBracket.UpdateSet(s, $(item.el), bracket.sets[item.id], data);
    }
  }
}

// ---------------------------------------------------------------------
// Drawing

let canvas = null;
let context = null;
let view = null;
let move = null;
let frame = null;
// The picture on screen is the sharp one
let sharp = false;
const stats = { shots: 0, shotTime: 0, svgSize: 0, frames: 0, worst: 0, slow: 0, last: 0, sharpTime: 0, failed: "" };

// A value going from one number to another: {from, to, start, time}
const still = (value) => ({ from: value, to: value, start: 0, time: 0 });
function valueAt(a, t) {
  if (!a.time || t >= a.start + a.time) return a.to;
  const k = Math.max(0, (t - a.start) / a.time);
  // GSAP's power1.inOut
  const eased = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
  return a.from + (a.to - a.from) * eased;
}
function go(a, to, t, time) {
  const from = valueAt(a, t);
  a.from = from;
  a.to = to;
  a.start = t;
  a.time = from == to ? 0 : time;
}
const changing = (a, t) => !!a.time && t < a.start + a.time;

function viewAt(t) {
  if (!move) return view;
  const k = (t - move.start) / move.duration;
  if (k >= 1) {
    view = move.to;
    move = null;
    return view;
  }
  return move.at(Math.max(0, k));
}

function resize() {
  const viewport = document.querySelector(".viewport");
  canvas.width = Math.max(1, Math.round(viewport.clientWidth));
  canvas.height = Math.max(1, Math.round(viewport.clientHeight));
}

// One picture of the bracket for a view. Moving, the sets are pasted from
// the photographs' copies; still (crisp), from the photographs themselves,
// drawn at the size they're shown.
function draw(v, t, crisp) {
  const c = context;
  c.setTransform(1, 0, 0, 1, 0, 0);
  c.clearRect(0, 0, canvas.width, canvas.height);
  if (!v || !placed) return;
  const corner = cornerOf(v);
  c.setTransform(v.scale, 0, 0, v.scale, corner.x, corner.y);
  // What's in view, in world pixels
  const left = -corner.x / v.scale;
  const top = -corner.y / v.scale;
  const right = left + canvas.width / v.scale;
  const bottom = top + canvas.height / v.scale;
  const inView = (b, room) =>
    b.x + b.w + room > left && b.x - room < right && b.y + (b.h || 0) + room > top && b.y - room < bottom;

  // Lines as dim as each other are drawn as one, or the parts they share
  // would be drawn twice, darker
  const groups = new Map();
  for (const line of paths) {
    const alpha = Math.round(valueAt(line.alpha, t) * 1000) / 1000;
    if (!groups.has(alpha)) groups.set(alpha, new Path2D());
    groups.get(alpha).addPath(line.path);
  }
  c.lineJoin = "miter";
  for (const [alpha, path] of groups) {
    c.globalAlpha = alpha;
    // Their shadow: a wider, faint copy, a little lower
    c.strokeStyle = "rgba(0, 0, 0, 0.15)";
    c.lineWidth = 9;
    c.translate(0, 2);
    c.stroke(path);
    c.translate(0, -2);
    c.strokeStyle = look.line;
    c.lineWidth = 5;
    c.stroke(path);
  }

  // The copy of the photographs to paste from: the smallest that isn't
  // enlarged
  for (const item of Object.values(items)) {
    const sheet = item.sheet;
    if (!sheet.levels || !inView(item.box, SHOT_MARGIN)) continue;
    let level = 0;
    while (level + 1 < LEVELS && sheet.scale / 2 ** (level + 1) >= v.scale) level += 1;
    const source = crisp ? sheet.image : sheet.levels[level];
    const k = crisp ? sheet.scale : sheet.scale / 2 ** level;
    c.globalAlpha = valueAt(item.alpha, t);
    c.drawImage(
      source,
      item.cx * k,
      item.cy * k,
      CELL_W * k,
      CELL_H * k,
      item.box.x - SHOT_MARGIN,
      item.box.y - SHOT_MARGIN,
      CELL_W,
      CELL_H,
    );
  }

  // The outlines of what's in focus, over everything
  for (const line of paths) {
    const glow = valueAt(line.glow, t);
    if (glow <= 0) continue;
    c.globalAlpha = glow;
    c.strokeStyle = look.focus;
    c.lineWidth = 6;
    c.stroke(line.path);
  }
  for (const item of Object.values(items)) {
    const glow = valueAt(item.glow, t);
    if (glow <= 0 || !inView(item.box, RING_ROOM)) continue;
    c.globalAlpha = glow;
    if (item.kind == "set") {
      c.drawImage(ring, item.box.x - RING_ROOM, item.box.y - RING_ROOM, SET_W + RING_ROOM * 2, SET_H + RING_ROOM * 2);
    } else {
      c.fillStyle = look.focus;
      c.fillRect(item.box.x, item.box.y + item.box.h - 4, item.box.w, 4);
    }
  }
  c.globalAlpha = 1;
}

function busy(t) {
  if (move) return true;
  for (const item of Object.values(items)) if (changing(item.alpha, t) || changing(item.glow, t)) return true;
  for (const line of paths) if (changing(line.alpha, t) || changing(line.glow, t)) return true;
  return false;
}

function tick(t) {
  frame = null;
  if (stats.last) {
    const gap = t - stats.last;
    stats.frames += 1;
    stats.worst = Math.max(stats.worst, gap);
    if (gap > 25) stats.slow += 1;
  }
  const v = viewAt(t);
  const moving = busy(t);
  if (moving) {
    draw(v, t, false);
    sharp = false;
    stats.last = t;
    frame = requestAnimationFrame(tick);
  } else {
    // Still: the sharp picture, once
    const started = performance.now();
    draw(v, t, true);
    sharp = true;
    stats.sharpTime = Math.round(performance.now() - started);
    stats.last = 0;
  }
  showStats();
}

function redraw() {
  if (frame == null) frame = requestAnimationFrame(tick);
}

function showStats() {
  const hud = document.querySelector(".hud");
  if (!hud || !HD.settings.hud) return;
  hud.style.display = "block";
  hud.textContent =
    `${Object.keys(items).length} pictures in ${sheets.length} sheet(s), ${stats.shots} photographed, ` +
    `last in ${stats.shotTime} ms (${stats.svgSize} KB) | last move: ${stats.frames} frames, ` +
    `${stats.slow} over 25 ms, worst ${Math.round(stats.worst)} ms | sharp picture: ${stats.sharpTime} ms` +
    (stats.failed ? ` | FAILED: ${stats.failed}` : "");
}

// ---------------------------------------------------------------------
// Camera and focus

let camera = null;
let lastSignature = null;
let lastFocus = null;

function focusBox(focus) {
  const boxes = [
    ...(focus.sets || []).map((id) => placed.sets[id]),
    ...(focus.rounds || []).map((key) => placed.headers[key]),
  ].filter(Boolean);
  if (boxes.length === 0) return { x: 0, y: 0, w: placed.width, h: placed.height };
  const left = Math.min(...boxes.map((b) => b.x));
  const top = Math.min(...boxes.map((b) => b.y));
  return {
    x: left,
    y: top,
    w: Math.max(...boxes.map((b) => b.x + b.w)) - left,
    h: Math.max(...boxes.map((b) => b.y + (b.h || 0))) - top,
  };
}

function moveCamera(s, target, animate) {
  const [vw, vh] = [canvas.width, canvas.height];
  if (!target.w || !target.h) return;
  camera = target;
  if (vw <= 1 || vh <= 1) return;
  const label =
    $(".focus_label").hasClass("shown") && !$("body").hasClass("hd-bracket-hide-focus-label") ? LABEL_ROOM : 0;
  const scale = Math.min((vw - PADDING * 2) / target.w, (vh - PADDING * 2 - label) / target.h, maxZoom(s));
  const to = { cx: target.x + target.w / 2, cy: target.y + target.h / 2, ax: vw / 2, ay: (vh - label) / 2, scale };
  // Ending on whole pixels
  const corner = cornerOf(to);
  to.ax += Math.round(corner.x) - corner.x;
  to.ay += Math.round(corner.y) - corner.y;

  const t = performance.now();
  const from = viewAt(t);
  const ease = move ? easeOut : easeInOut;
  const speed = gsap.globalTimeline.timeScale();
  const duration = speed > 0 ? (cameraTime() * 1000) / speed : 0;
  if (!animate || !from || duration < 20) {
    move = null;
    view = to;
  } else {
    move = { to, at: (k) => between(from, to, ease(k)), start: t, duration };
    stats.frames = stats.slow = stats.worst = stats.last = 0;
  }
  redraw();
}

function applyFocus(s, data, animate) {
  const focus = focusOf(s, data);
  const inFocus = new Set((focus.sets || []).filter((id) => placed.sets[id]));
  const rounds = new Set(focus.rounds || []);
  const hasFocus = inFocus.size > 0;
  const outline = hasFocus && glows(focus);
  const columns = _.keyBy(Object.values(_.get(data, "bracket.bracket.sides", {})).flat(), "key");
  readLook(focus);

  const t = performance.now();
  const time = animate ? (FADE_TIME * 1000) / (gsap.globalTimeline.timeScale() || 1) : 0;
  const light = (thing, focused, outlined) => {
    go(thing.alpha, !hasFocus || focused ? 1 : look.dim, t, time);
    go(thing.glow, outlined ? 1 : 0, t, time);
  };
  for (const item of Object.values(items)) {
    if (item.kind == "set") {
      light(item, inFocus.has(item.id), outline && inFocus.has(item.id));
    } else {
      const column = columns[item.id];
      const focused = rounds.has(item.id) || !!(column && column.sets.some((id) => inFocus.has(id)));
      light(item, focused, focused && glows(focus));
    }
  }
  for (const line of paths) {
    const focused = inFocus.has(line.from) && (line.to == null || inFocus.has(line.to));
    light(line, focused, outline && focused);
  }

  showLabel(hasFocus ? focus.label || "" : "", animate);
  moveCamera(s, focusBox({ sets: [...inFocus], rounds: hasFocus ? [...rounds] : [] }), animate);
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["bracket", "score", "game", "tournamentInfo", "commentary"],
  init() {
    canvas = document.querySelector(".bf_canvas");
    context = canvas.getContext("2d");
    resize();
    $(window).on("resize", () => {
      resize();
      if (placed && camera) moveCamera(HD.scope(), camera, false);
    });
    setInterval(checkSheets, 300);
    // A font that arrived changes how the sets look
    document.fonts.addEventListener("loadingdone", () =>
      sheets.forEach((sheet) => (sheet.shot = sheet.pending = null)),
    );
  },

  update(s) {
    const channel = channelOf(s);
    const data = HDBracket.ForChannel(s.data, channel);

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      placed = null;
      items = {};
      sheets = [];
      paths = [];
      move = null;
      lastSignature = null;
      document.querySelector(".stage").innerHTML = "";
      showLabel("", false);
      redraw();
      return;
    }

    let built = false;
    const signature = HDBracket.Signature(data) + maxZoom(s);
    if (signature != lastSignature) {
      lastSignature = signature;
      build(data);
      built = true;
    }
    // The photographs follow (checkSheets)
    updateSets(s, data);

    const focus = focusOf(s, data);
    const focusKey = JSON.stringify([focus, glows(focus), s.settings.ignore_focus, maxZoom(s)]);
    if (built || focusKey != lastFocus) {
      applyFocus(s, data, lastFocus != null && !built);
      lastFocus = focusKey;
    } else {
      readLook(focus);
    }

    s.set(".tournament_name", data.tournamentInfo.tournamentName);
    s.set(".event_name", data.tournamentInfo.eventName);
    s.set(".bracket_name", data.bracket.phase || data.bracket.bracket.name);
    s.set(".pool_name", data.bracket.phaseGroup);
  },
});
