// bracket_focus drawn another way, kept next to it until the two have been
// compared side by side: the same bracket, focus and camera (see
// ../bracket_focus/index.js), on one canvas.
//
// bracket_focus has the browser move and fade the bracket's elements, and
// the frames it drops come from the browser drawing or re-layering them
// while the camera moves. Here every set and round name is drawn by the
// browser once, off screen, with bracket_focus's CSS, and photographed into
// pictures (sheets). A move is then one canvas: each frame pastes the
// pictures in view at the camera's place and scale, more or less transparent
// for the dimming. Nothing is drawn again or changes layer while the camera
// moves. Still, the sets in view are pasted from the photograph itself (a
// vector), sharp at any scale.
//
// What changes in a set is photographed again, that set alone.
// Options, page or URL, as bracket_focus: channel, ignore_focus, max_zoom.
// And hud=1: a line of numbers at the bottom (pictures made, how long the
// last photograph took, the frames of the last move and how many were slow).
// no_title.html has no title bar: the bracket takes the whole page.

/* global XMLHttpRequest, FileReader, XMLSerializer, Blob, Path2D, ResizeObserver */

// ---------------------------------------------------------------------
// Sizes and the camera's path: as ../bracket_focus/index.js. HyperDrive
// places the bracket (bracket.channels.<channel>.placement).
const PLAYER_H = 40;
const SET_GAP = 2;
const SET_W = 380;
const SET_H = PLAYER_H * 2 + SET_GAP;
const MARGIN = 40;
const PADDING = 60;
const LABEL_ROOM = 90;
const cameraTime = () => HD.theme("bracket", "focus_time", 1000) / 1000;
const FADE_TIME = 0.6;

let placed = null;
let shownLabel = null;
let labelTween = null;

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
// A sheet's most pixels a side, and how many smaller copies of it are kept
// (each half the one before), so a picture is never shrunk by much more
// than 2 when pasted: sharp enough moving, and no shimmer
const SHEET_PX = 4096;
const LEVELS = 4;
// The glow reaches this far around a set
const RING_ROOM = 44;
// An element is photographed once it has stopped changing for this long, in
// ms (texts and images are filled in over a few frames)
const QUIET_TIME = 180;
// With more elements than this changed in a sheet, the whole sheet is
// photographed at once instead of each one
const MANY = 12;
// A set photographed again fades from its old picture to the new one, in ms
const CHANGE_TIME = 400;
// The sets' entrance: each in ENTER_TIME, all started within STAGGER_TIME
const ENTER_TIME = 400;
const STAGGER_TIME = 1500;

// What's drawn from a photograph: sets ("set:<id>"), round names
// ("round:<key>"), byes ("bye:<key>") and the pool standings ("standings"):
// {key, kind, id, box, el, sheet, cell, image, dirty, alpha, glow, enter,
// change}
// box is where it goes, in world pixels; cell where it is in its sheet,
// with SHOT_MARGIN around it; image its own photograph, once it was taken
// again by itself. change is its fade from the picture it had: {old, sharp,
// blend, start, time}.
let items = {};
// {el, items, width, height, scale, image, levels}
let sheets = [];
// {from, to, path, alpha, glow}
let paths = [];
// What bracket_focus's CSS gives the page: read once the bracket is built
let look = { dim: 0.3, focus: "#ffb800", line: "#000", radius: 0 };
let ring = null;
// The bracket came in (the sets' entrance), once all its sheets were
// photographed; and the lines' part of it
let entered = false;
let linesEnter = null;

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
  const faces = [];
  for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {
    const css = await readText(link.href);
    for (const rule of css.match(/@font-face\s*{[^}]*}/g) || []) {
      const family = (rule.match(/font-family:\s*([^;]+);/) || [])[1];
      const url = (rule.match(/url\(\s*["']?([^"')]+)["']?\s*\)/) || [])[1];
      const weight = ((rule.match(/font-weight:\s*([^;]+);/) || [])[1] || "400").trim();
      if (family && url) {
        faces.push({
          family: family.trim().replace(/^["']|["']$/g, ""),
          weight,
          url: new URL(url, link.href).href,
        });
      }
    }
  }
  fontFaces = faces;
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

// The style properties an element's style is written down with, and each
// tag's values for them with no style sheet (from an empty frame): only what
// differs from those is written
const SKIPPED_STYLES = /^(transition|animation|will-change|cursor|pointer-events|scroll|overscroll|view-transition)/;
let properties = null;
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
    const style = blank.contentWindow.getComputedStyle(probe);
    if (!properties) properties = [...style].filter((property) => !SKIPPED_STYLES.test(property));
    defaults.set(
      key,
      properties.map((property) => style.getPropertyValue(property)),
    );
    probe.remove();
  }
  return defaults.get(key);
}

// Whether an element has nothing to show and takes no room, so its copy can
// be left out: it isn't displayed, or it's out of the flow (placed by
// itself) with no content and nothing drawn of its box. An empty element in
// the flow stays: it can still push its neighbours (its size, its margins,
// a gap).
function leftOut(el, style) {
  if (style.getPropertyValue("display") == "none") return true;
  if (el.children.length || el.textContent.trim() !== "") return false;
  if (!["absolute", "fixed"].includes(style.getPropertyValue("position"))) return false;
  if (["img", "canvas", "svg", "video", "iframe"].includes(el.localName)) return false;
  const clear = (property, value) => style.getPropertyValue(property) == value;
  return (
    clear("background-image", "none") &&
    clear("background-color", "rgba(0, 0, 0, 0)") &&
    clear("box-shadow", "none") &&
    clear("outline-style", "none") &&
    ["top", "right", "bottom", "left"].every((side) => clear(`border-${side}-style`, "none"))
  );
}

// Writes each element's style, as the page has it, on its copy. Returns
// false for an element whose copy is to be left out instead (with what's
// inside it): writing styles down is most of what a photograph costs, and
// some of a set's elements are never shown (an avatar it doesn't have, its
// identifier with the theme's off).
function copyStyles(source, target, urls) {
  const style = getComputedStyle(source);
  if (leftOut(source, style)) return false;
  const base = defaultStyle(source);
  let css = "";
  for (let i = 0; i < properties.length; i++) {
    const value = style.getPropertyValue(properties[i]);
    if (value !== base[i]) css += `${properties[i]}:${value};`;
  }
  if (css.includes("url(")) for (const match of css.matchAll(/url\("([^"]+)"\)/g)) urls.add(match[1]);
  target.setAttribute("style", css);
  if (target.localName == "img" && source.currentSrc) {
    target.setAttribute("src", source.currentSrc);
    urls.add(source.currentSrc);
  }
  // The copies, before any is taken out
  const copies = [...target.children];
  for (let i = 0; i < source.children.length; i++) {
    if (!copyStyles(source.children[i], copies[i], urls)) copies[i].remove();
  }
  return true;
}

// A picture of elements as the browser draws them: copies of them with
// their styles, images and fonts written inside, in an SVG. width and
// height in world pixels, drawn scale times as big. null if it can't be
// made.
async function photograph(elements, width, height, scale) {
  const root = document.createElement("div");
  const urls = new Set();
  for (const { el, x, y } of elements) {
    const copy = el.cloneNode(true);
    // Not shown at all (the byes of a round without any)
    if (!copyStyles(el, copy, urls)) continue;
    copy.setAttribute("style", `${copy.getAttribute("style")}left:${x}px;top:${y}px;margin:0;`);
    root.appendChild(copy);
  }
  // What the elements inherit from the page
  const inherited = getComputedStyle(elements[0].el.parentNode);
  root.setAttribute(
    "style",
    `position:relative;width:${width}px;height:${height}px;overflow:hidden;` +
      ["color", "font-family", "font-size", "font-weight", "font-style", "letter-spacing", "line-height"]
        .map((property) => `${property}:${inherited.getPropertyValue(property)};`)
        .join(""),
  );

  const found = new Map(await Promise.all([...urls].map(async (url) => [url, await dataUrl(url)])));
  for (const el of root.querySelectorAll("*")) {
    let css = el.getAttribute("style");
    // Texts fully shown, even halfway through HD.set()'s fade
    if (el.classList.contains("text")) {
      css += "opacity:1;visibility:inherit;";
      el.setAttribute("style", css);
    }
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

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width * scale}" height="${height * scale}" ` +
    `viewBox="0 0 ${width} ${height}"><style>${await fontCss()}</style>` +
    `<foreignObject x="0" y="0" width="${width}" height="${height}">` +
    `${new XMLSerializer().serializeToString(root)}</foreignObject></svg>`;
  const image = new Image();
  const blob = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    image.src = blob;
    await image.decode();
    return image;
  } catch (e) {
    console.log("The photograph couldn't be made", e);
    stats.failed = String(e);
    return null;
  } finally {
    URL.revokeObjectURL(blob);
  }
}

// Photographs a whole sheet, and keeps the picture at a few sizes
async function shootSheet(sheet) {
  const started = performance.now();
  const image = await photograph(
    sheet.items.map((item) => ({ el: item.el, x: item.cell.x + SHOT_MARGIN, y: item.cell.y + SHOT_MARGIN })),
    sheet.width,
    sheet.height,
    sheet.scale,
  );
  // The bracket was built again meanwhile
  if (!image || !sheets.includes(sheet)) return;
  const levels = [];
  for (let level = 0; level < LEVELS; level++) {
    const copy = document.createElement("canvas");
    copy.width = Math.max(1, Math.round((sheet.width * sheet.scale) / 2 ** level));
    copy.height = Math.max(1, Math.round((sheet.height * sheet.scale) / 2 ** level));
    const c = copy.getContext("2d");
    c.imageSmoothingQuality = "high";
    c.drawImage(level ? levels[level - 1] : image, 0, 0, copy.width, copy.height);
    levels.push(copy);
  }
  sheet.image = image;
  sheet.levels = levels;
  for (const item of sheet.items) {
    item.image = null;
    item.change = null;
    if (item.dirty <= started) item.dirty = 0;
  }
  stats.shots += 1;
  stats.shotTime = Math.round(performance.now() - started);
}

// Photographs one element again, into its place in its sheet
async function shootItem(item) {
  const started = performance.now();
  const { sheet, cell } = item;
  const image = await photograph([{ el: item.el, x: SHOT_MARGIN, y: SHOT_MARGIN }], cell.w, cell.h, sheet.scale);
  if (!image || !sheets.includes(sheet) || !sheet.levels) return;
  // The picture it had, to fade from
  const old = document.createElement("canvas");
  old.width = Math.max(1, Math.round(cell.w * sheet.scale));
  old.height = Math.max(1, Math.round(cell.h * sheet.scale));
  old
    .getContext("2d")
    .drawImage(
      sheet.levels[0],
      cell.x * sheet.scale,
      cell.y * sheet.scale,
      cell.w * sheet.scale,
      cell.h * sheet.scale,
      0,
      0,
      old.width,
      old.height,
    );
  sheet.levels.forEach((copy, level) => {
    const k = sheet.scale / 2 ** level;
    const c = copy.getContext("2d");
    c.imageSmoothingQuality = "high";
    // Whole pixels around the cell: its neighbours start past its margin
    const [x, y] = [Math.floor(cell.x * k), Math.floor(cell.y * k)];
    const [w, h] = [Math.ceil((cell.x + cell.w) * k) - x, Math.ceil((cell.y + cell.h) * k) - y];
    c.clearRect(x, y, w, h);
    c.drawImage(image, cell.x * k, cell.y * k, cell.w * k, cell.h * k);
  });
  // And the photograph it was in, for the fade when the camera is still
  const [sw, sh] = [cell.w * sheet.scale, cell.h * sheet.scale];
  const sharp = item.image
    ? [item.image, 0, 0, sw, sh]
    : [sheet.image, cell.x * sheet.scale, cell.y * sheet.scale, sw, sh];
  item.image = image;
  if (item.dirty <= started) item.dirty = 0;
  if (entered) {
    item.change = {
      old,
      sharp,
      blend: document.createElement("canvas"),
      start: performance.now(),
      time: CHANGE_TIME / (gsap.globalTimeline.timeScale() || 1),
    };
  }
  stats.shots += 1;
  stats.shotTime = Math.round(performance.now() - started);
}

// Photographs what changed, once it has stopped changing: one at a time,
// and not while the camera moves or the focus fades (drawing a photograph
// would hold a frame up)
let pumping = false;
async function pump() {
  if (pumping) return;
  pumping = true;
  try {
    for (;;) {
      const t = performance.now();
      if (moving(t)) break;
      const quiet = (item) => t - item.dirty > QUIET_TIME;
      let job = null;
      for (const sheet of sheets) {
        const dirty = sheet.items.filter((item) => item.dirty);
        if (dirty.length === 0) continue;
        if (!sheet.levels || dirty.length > MANY) {
          if (dirty.every(quiet)) job = () => shootSheet(sheet).then(() => true);
        } else {
          const item = dirty.find(quiet);
          if (item) job = () => shootItem(item);
        }
        if (job) break;
      }
      if (!job) break;
      const whole = await job();
      if (!entered) enter();
      // One element: only its part of the picture, fading
      if (whole || !sharp) redraw();
      else if (frame == null) frame = requestAnimationFrame(tick);
    }
  } finally {
    pumping = false;
  }
}

function touch(node) {
  const el = node && (node.nodeType == 1 ? node : node.parentElement);
  const marked = el && el.closest("[data-item]");
  const item = marked && items[marked.dataset.item];
  if (item) item.dirty = performance.now();
}

// Everything is photographed again: the look changed (the theme, a font
// that arrived)
function touchAll() {
  const t = performance.now();
  for (const item of Object.values(items)) item.dirty = t;
}

// The outline of a set in focus, drawn once: a ring and its glow, as
// bracket_focus's .bf_ring
function makeRing() {
  const scale = 2;
  const sprite = document.createElement("canvas");
  sprite.width = (SET_W + RING_ROOM * 2) * scale;
  sprite.height = (SET_H + RING_ROOM * 2) * scale;
  const c = sprite.getContext("2d");
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
  return sprite;
}

// The colors and sizes bracket_focus's CSS gives the page
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
  const changed = !ring || next.focus != look.focus || next.radius != look.radius;
  look = next;
  if (changed) ring = makeRing();
}

// ---------------------------------------------------------------------
// Building

// Puts the elements in sheets, row after row: gives each its sheet and
// cell. Each element is {key, kind, id, box, html}.
function pack(things, scale) {
  const side = Math.floor(SHEET_PX / scale);
  const stage = document.querySelector(".stage");
  let sheet = null;
  let [x, y, row] = [0, 0, 0];
  const newSheet = () => {
    sheet = { el: document.createElement("div"), items: [], width: 0, height: 0, scale, image: null, levels: null };
    sheet.el.className = "sheet";
    stage.appendChild(sheet.el);
    sheets.push(sheet);
    [x, y, row] = [0, 0, 0];
  };
  for (const thing of things) {
    const [w, h] = [thing.box.w + SHOT_MARGIN * 2, thing.box.h + SHOT_MARGIN * 2];
    if (!sheet) newSheet();
    if (x + w > side && x > 0) [x, y, row] = [0, y + row, 0];
    if (y + h > side && y > 0) newSheet();
    const holder = document.createElement("div");
    holder.innerHTML = String(thing.html);
    const el = holder.firstElementChild;
    el.dataset.item = thing.key;
    el.style.left = `${x + SHOT_MARGIN}px`;
    el.style.top = `${y + SHOT_MARGIN}px`;
    el.style.width = `${thing.width || thing.box.w}px`;
    if (thing.kind != "bye") el.style.height = `${thing.box.h}px`;
    sheet.el.appendChild(el);
    const item = {
      key: thing.key,
      kind: thing.kind,
      id: thing.id,
      box: thing.box,
      el,
      sheet,
      cell: { x, y, w, h },
      image: null,
      dirty: performance.now(),
      alpha: still(1),
      glow: still(0),
      enter: null,
      change: null,
    };
    items[item.key] = item;
    sheet.items.push(item);
    x += w;
    row = Math.max(row, h);
    sheet.width = Math.max(sheet.width, x);
    sheet.height = Math.max(sheet.height, y + row);
  }
  for (const made of sheets) {
    made.el.style.cssText = `position:relative;width:${made.width}px;height:${made.height}px;`;
  }
}

function build(data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  placed = data.bracket.placement;
  move = null;
  items = {};
  sheets = [];
  entered = false;
  linesEnter = null;
  document.querySelector(".stage").innerHTML = "";
  $("body").toggleClass("pool_view", HDBracket.IsPool(bracket));

  pack(
    [
      ...Object.entries(placed.headers).map(([id, box]) => ({
        key: `round:${id}`,
        kind: "round",
        id,
        box,
        html: HD.html`<div class="bf_round_name" data-round="${id}"></div>`,
      })),
      // A line of text under a pool's round
      ...Object.entries(placed.byes).map(([id, at]) => ({
        key: `bye:${id}`,
        kind: "bye",
        id,
        // Room for its padding, which its width doesn't count
        box: { ...at, w: at.w + 40, h: 34 },
        width: at.w,
        html: HD.html`<div class="byes" data-round="${id}"></div>`,
      })),
      ...Object.entries(placed.sets).map(([id, box]) => ({
        key: `set:${id}`,
        kind: "set",
        id,
        box,
        html: HD.html`
          <div class="slot side_${sets[id].side}" data-set="${id}">
            <div class="set_identifier"><div class="text"></div></div>
            ${HDBracket.PlayerSlotHtml(0)}
            ${HDBracket.PlayerSlotHtml(1)}
          </div>`,
      })),
    ],
    maxZoom(HD.scope()),
  );

  paths = HDBracket.Lines(placed).map((line) => ({
    ...line,
    path: new Path2D(line.d),
    alpha: still(1),
    glow: still(0),
  }));
}

// The pool standings, beside the rounds: a sheet of their own, as big as
// they are. Returns whether they changed size (the whole bracket is then
// placed in the page again).
function updateStandings(data) {
  const html = HDBracket.IsPool(data.bracket.bracket) ? HDBracket.StandingsHtml(data) : null;
  let item = items.standings;
  if (!html || !placed.standings) {
    if (!item) return false;
    item.sheet.el.remove();
    sheets = sheets.filter((sheet) => sheet !== item.sheet);
    delete items.standings;
    return true;
  }
  if (!item) {
    const sheet = { el: document.createElement("div"), items: [], width: 1, height: 1, scale: 1, image: null };
    sheet.levels = null;
    sheet.el.className = "sheet";
    sheet.el.innerHTML = '<div class="bf_standings" data-item="standings"></div>';
    document.querySelector(".stage").appendChild(sheet.el);
    const el = sheet.el.firstElementChild;
    el.style.cssText = `left:${SHOT_MARGIN}px;top:${SHOT_MARGIN}px;width:${placed.standings.w}px;`;
    item = items.standings = {
      key: "standings",
      kind: "standings",
      id: null,
      box: { x: placed.standings.x, y: placed.standings.y, w: 0, h: 0 },
      el,
      sheet,
      cell: { x: 0, y: 0, w: 1, h: 1 },
      image: null,
      dirty: performance.now(),
      alpha: still(document.body.classList.contains("has_focus") ? look.dim : 1),
      glow: still(0),
      enter: null,
      change: null,
    };
    sheet.items.push(item);
    sheets.push(sheet);
    // Their size settles a little later (their font, their flags): the
    // whole bracket is then fitted in the page again
    new ResizeObserver(() => {
      if (items.standings === item && measureStandings() && !lastHasFocus && camera) {
        moveCamera(HD.scope(), focusBox({}), false);
      }
    }).observe(el);
  }
  HD.build(item.el, String(html), html);
  return measureStandings();
}

// Gives the standings' sheet the size they have now. Returns whether that
// changed: they're then photographed whole again.
function measureStandings() {
  const item = items.standings;
  if (!item) return false;
  const [w, h] = [item.el.offsetWidth, item.el.offsetHeight];
  if (w == item.box.w && h == item.box.h) return false;
  const sheet = item.sheet;
  item.box = { ...item.box, w, h };
  item.cell = { x: 0, y: 0, w: w + SHOT_MARGIN * 2, h: h + SHOT_MARGIN * 2 };
  sheet.width = item.cell.w;
  sheet.height = item.cell.h;
  sheet.scale = Math.min(maxZoom(HD.scope()), SHEET_PX / Math.max(sheet.width, sheet.height));
  sheet.el.style.cssText = `position:relative;width:${sheet.width}px;height:${sheet.height}px;`;
  sheet.levels = null;
  item.dirty = performance.now();
  return true;
}

// Every set with all, else only those that changed since old, or whose
// players did (a big bracket has hundreds of sets, a dozen fields each)
function updateSets(s, data, old, all) {
  const bracket = data.bracket.bracket;
  const columns = _.keyBy(Object.values(bracket.sides || {}).flat(), "key");
  const byes = HDBracket.ByesText(bracket);
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

  for (const item of Object.values(items)) {
    if (item.kind == "round") {
      HD.set(item.el, columns[item.id] ? columns[item.id].name : "");
    } else if (item.kind == "bye") {
      HD.set(item.el, byes[item.id] ? `Bye: ${byes[item.id]}` : "");
    } else if (item.kind == "set") {
      const set = bracket.sets[item.id];
      if (set && changed(item.id, set)) HDBracket.UpdateSet(s, $(item.el), set, data);
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
// The picture on the canvas is the sharp one, whole, for the view as it is
let sharp = false;
const stats = { shots: 0, shotTime: 0, frames: 0, worst: 0, slow: 0, last: 0, sharpTime: 0, failed: "" };

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

// How far in an entrance is ({start, time}), 0 to 1: GSAP's power1.out
function entering(enter, t) {
  if (!enter) return entered ? 1 : 0;
  const k = Math.min(1, Math.max(0, (t - enter.start) / enter.time));
  return 1 - (1 - k) * (1 - k);
}

// The bracket comes in, once every sheet has been photographed: the sets
// column by column, all within STAGGER_TIME however big the bracket, and
// the lines and round names fading in after them
function enter() {
  if (entered || sheets.length === 0 || sheets.some((sheet) => !sheet.levels)) return;
  entered = true;
  const speed = gsap.globalTimeline.timeScale() || 1;
  const t = performance.now();
  const sets = Object.values(items).filter((item) => item.kind == "set");
  sets.sort((a, b) => a.box.x - b.box.x);
  const stagger = Math.min(15, STAGGER_TIME / Math.max(1, sets.length)) / speed;
  sets.forEach((item, i) => (item.enter = { start: t + i * stagger, time: ENTER_TIME / speed }));
  const fade = { start: t + 300 / speed, time: 600 / speed };
  for (const item of Object.values(items)) if (item.kind != "set") item.enter = fade;
  linesEnter = fade;
}

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

// An element halfway from the picture it had to its new one, k times the
// world's size: the two added up, so much of each, which is what a
// cross-fade is. Pasted one over the other, a dimmed set would get more
// solid during the fade. Each picture is [what it's taken from, x, y, width,
// height].
function blended(item, k, t, before, after) {
  const { change, cell } = item;
  const mix = Math.min(1, Math.max(0, (t - change.start) / change.time));
  const [w, h] = [Math.max(1, Math.round(cell.w * k)), Math.max(1, Math.round(cell.h * k))];
  const blend = change.blend;
  if (blend.width != w || blend.height != h) {
    blend.width = w;
    blend.height = h;
  }
  const c = blend.getContext("2d");
  c.imageSmoothingQuality = "high";
  c.globalCompositeOperation = "copy";
  c.globalAlpha = 1 - mix;
  c.drawImage(...before, 0, 0, w, h);
  c.globalCompositeOperation = "lighter";
  c.globalAlpha = mix;
  c.drawImage(...after, 0, 0, w, h);
  return blend;
}

// One picture of the bracket for a view. Moving, the sets are pasted from
// the photographs' copies; still (crisp), from the photographs themselves,
// drawn at the size they're shown. With a region ({x, y, w, h}, world
// pixels), only that part of the picture is drawn again.
function draw(v, t, crisp, region) {
  const c = context;
  c.setTransform(1, 0, 0, 1, 0, 0);
  if (!v || !placed) return c.clearRect(0, 0, canvas.width, canvas.height);
  const corner = cornerOf(v);
  // The part drawn, in whole pixels of the canvas
  let [px, py, pw, ph] = [0, 0, canvas.width, canvas.height];
  if (region) {
    px = Math.max(0, Math.floor(region.x * v.scale + corner.x));
    py = Math.max(0, Math.floor(region.y * v.scale + corner.y));
    pw = Math.min(canvas.width, Math.ceil((region.x + region.w) * v.scale + corner.x)) - px;
    ph = Math.min(canvas.height, Math.ceil((region.y + region.h) * v.scale + corner.y)) - py;
    if (pw <= 0 || ph <= 0) return;
  }
  c.save();
  c.beginPath();
  c.rect(px, py, pw, ph);
  c.clip();
  c.clearRect(px, py, pw, ph);
  c.setTransform(v.scale, 0, 0, v.scale, corner.x, corner.y);
  // The same, in world pixels
  const left = (px - corner.x) / v.scale;
  const top = (py - corner.y) / v.scale;
  const right = left + pw / v.scale;
  const bottom = top + ph / v.scale;
  const inView = (b, room) =>
    b.x + b.w + room > left && b.x - room < right && b.y + (b.h || 0) + room > top && b.y - room < bottom;

  // Lines as dim as each other are drawn as one, or the parts they share
  // would be drawn twice, darker
  const lineIn = entering(linesEnter, t);
  const groups = new Map();
  for (const line of paths) {
    const alpha = Math.round(valueAt(line.alpha, t) * lineIn * 1000) / 1000;
    if (alpha <= 0) continue;
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

  const shown = [];
  for (const item of Object.values(items)) {
    const sheet = item.sheet;
    if (!sheet.levels || !inView(item.box, SHOT_MARGIN + 40)) continue;
    const came = entering(item.enter, t);
    if (came <= 0) continue;
    shown.push([item, came]);
    // The copy of the photograph to paste from: the smallest that isn't
    // enlarged. Crisp, the photograph itself (its own, if it has one).
    let level = 0;
    while (level + 1 < LEVELS && sheet.scale / 2 ** (level + 1) >= v.scale) level += 1;
    const cell = item.cell;
    const own = crisp && item.image;
    let source = own || (crisp ? sheet.image : sheet.levels[level]);
    const k = crisp ? sheet.scale : sheet.scale / 2 ** level;
    let whole = !!own;
    if (item.change) {
      // Crisp, both pictures from the photographs themselves, at the size
      // they're shown: what didn't change stays exactly as it was
      const old = item.change.old;
      source = crisp
        ? blended(item, v.scale, t, item.change.sharp, [item.image, 0, 0, cell.w * k, cell.h * k])
        : blended(
            item,
            k,
            t,
            [old, 0, 0, old.width, old.height],
            [sheet.levels[level], cell.x * k, cell.y * k, cell.w * k, cell.h * k],
          );
      whole = true;
    }
    c.globalAlpha = valueAt(item.alpha, t) * came;
    c.drawImage(
      source,
      whole ? 0 : cell.x * k,
      whole ? 0 : cell.y * k,
      item.change ? source.width : cell.w * k,
      item.change ? source.height : cell.h * k,
      // A set slides in from its left
      item.box.x - SHOT_MARGIN - (item.kind == "set" ? 40 * (1 - came) : 0),
      item.box.y - SHOT_MARGIN,
      cell.w,
      cell.h,
    );
  }

  // The outlines of what's in focus, over everything
  for (const line of paths) {
    const glow = valueAt(line.glow, t) * lineIn;
    if (glow <= 0) continue;
    c.globalAlpha = glow;
    c.strokeStyle = look.focus;
    c.lineWidth = 6;
    c.stroke(line.path);
  }
  for (const [item, came] of shown) {
    const glow = valueAt(item.glow, t) * came;
    if (glow <= 0) continue;
    c.globalAlpha = glow;
    if (item.kind == "set") {
      c.drawImage(ring, item.box.x - RING_ROOM, item.box.y - RING_ROOM, SET_W + RING_ROOM * 2, SET_H + RING_ROOM * 2);
    } else if (item.kind == "round") {
      c.fillStyle = look.focus;
      c.fillRect(item.box.x, item.box.y + item.box.h - 4, item.box.w, 4);
    }
  }
  c.restore();
}

// The camera is moving, the focus fading or the bracket coming in: no
// photograph is taken meanwhile
function moving(t) {
  if (move) return true;
  if (linesEnter && t < linesEnter.start + linesEnter.time) return true;
  for (const item of Object.values(items)) {
    if (changing(item.alpha, t) || changing(item.glow, t)) return true;
    if (item.enter && t < item.enter.start + item.enter.time) return true;
  }
  for (const line of paths) if (changing(line.alpha, t) || changing(line.glow, t)) return true;
  return false;
}

// The elements fading from the picture they had, and those that just got
// there (their fades end here)
function fading(t) {
  const found = { going: [], done: [] };
  for (const item of Object.values(items)) {
    if (!item.change) continue;
    if (t < item.change.start + item.change.time) {
      found.going.push(item);
    } else {
      item.change = null;
      found.done.push(item);
    }
  }
  return found;
}

// Where an element is drawn, with its outline's glow
const regionOf = (item) => ({
  x: item.box.x - RING_ROOM,
  y: item.box.y - RING_ROOM,
  w: item.box.w + RING_ROOM * 2,
  h: item.box.h + RING_ROOM * 2,
});

function tick(t) {
  frame = null;
  if (stats.last) {
    const gap = t - stats.last;
    stats.frames += 1;
    stats.worst = Math.max(stats.worst, gap);
    if (gap > 25) stats.slow += 1;
  }
  const v = viewAt(t);
  const { going, done } = fading(t);
  if (moving(t)) {
    draw(v, t, false);
    sharp = false;
    stats.last = t;
    frame = requestAnimationFrame(tick);
  } else {
    // Still: the sharp picture, once, and after that only the elements
    // fading from the picture they had. The rest stays as sharp as it was.
    const started = performance.now();
    if (!sharp) draw(v, t, true);
    else for (const item of [...going, ...done]) draw(v, t, true, regionOf(item));
    if (!sharp) stats.sharpTime = Math.round(performance.now() - started);
    sharp = true;
    stats.last = 0;
    if (going.length) frame = requestAnimationFrame(tick);
  }
  showStats();
}

// The picture is to be drawn again, whole
function redraw() {
  sharp = false;
  if (frame == null) frame = requestAnimationFrame(tick);
}

function showStats() {
  const hud = document.querySelector(".hud");
  if (!hud || !HD.settings.hud) return;
  hud.style.display = "block";
  hud.textContent =
    `${Object.keys(items).length} pictures in ${sheets.length} sheet(s), ${stats.shots} photographs, ` +
    `last in ${stats.shotTime} ms | last move: ${stats.frames} frames, ` +
    `${stats.slow} over 25 ms, worst ${Math.round(stats.worst)} ms | sharp picture: ${stats.sharpTime} ms` +
    (stats.failed ? ` | FAILED: ${stats.failed}` : "");
}

// ---------------------------------------------------------------------
// Camera and focus

let camera = null;
let lastSignature = null;
let lastFocus = null;
// Whether anything is in focus (else the camera is on the whole bracket)
let lastHasFocus = false;

function focusBox(focus) {
  const boxes = [
    ...(focus.sets || []).map((id) => placed.sets[id]),
    ...(focus.rounds || []).map((key) => placed.headers[key]),
  ].filter(Boolean);
  if (boxes.length === 0) {
    // The whole bracket, with the pool standings once drawn
    let { width, height } = placed;
    const standings = items.standings;
    if (standings && standings.box.w) {
      width = Math.max(width, standings.box.x + standings.box.w + MARGIN);
      height = Math.max(height, standings.box.y + standings.box.h + MARGIN);
    }
    return { x: 0, y: 0, w: width, h: height };
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
  $("body").toggleClass("has_focus", hasFocus);
  lastHasFocus = hasFocus;

  const t = performance.now();
  const time = animate ? (FADE_TIME * 1000) / (gsap.globalTimeline.timeScale() || 1) : 0;
  const light = (thing, focused, outlined) => {
    go(thing.alpha, !hasFocus || focused ? 1 : look.dim, t, time);
    go(thing.glow, outlined ? 1 : 0, t, time);
  };
  for (const item of Object.values(items)) {
    if (item.kind == "set") {
      light(item, inFocus.has(item.id), outline && inFocus.has(item.id));
    } else if (item.kind == "round") {
      const column = columns[item.id];
      const focused = rounds.has(item.id) || !!(column && column.sets.some((id) => inFocus.has(id)));
      light(item, focused, focused && glows(focus));
    } else {
      // The byes and the pool standings are never in focus
      light(item, false, false);
    }
  }
  for (const line of paths) {
    const focused = inFocus.has(line.from) && (line.to == null || inFocus.has(line.to));
    light(line, focused, outline && focused);
  }

  // The player whose run it is: their sets are photographed again
  const sets = _.get(data, "bracket.bracket.sets", {});
  const mine = new Set();
  if (focus.mode == "player" && focus.player != null) {
    inFocus.forEach((id) =>
      (sets[id].players || []).forEach((p, slot) => {
        if (p && p.id == focus.player && items[`set:${id}`]) {
          mine.add(items[`set:${id}`].el.querySelector(`.slot_p_${slot}`));
        }
      }),
    );
  }
  for (const el of document.querySelectorAll(".stage .player")) {
    if (el.classList.contains("focus_player") != mine.has(el)) el.classList.toggle("focus_player", mine.has(el));
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

    // What changes in the elements is photographed again
    const stage = document.querySelector(".stage");
    // A text fading (HD.set() fades the old one out, then the new one in)
    // isn't a change: the photograph has it fully shown, as soon as it's in
    const fade = (record) =>
      record.type == "attributes" && record.attributeName == "style" && record.target.classList.contains("text");
    new MutationObserver((records) => records.forEach((r) => fade(r) || touch(r.target))).observe(stage, {
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true,
    });
    // An image that arrived: load events don't bubble
    stage.addEventListener("load", (e) => touch(e.target), true);
    document.fonts.addEventListener("loadingdone", touchAll);
    setInterval(pump, 60);
  },

  update(s) {
    const channel = channelOf(s);
    const data = HDBracket.ForChannel(s.data, channel);
    const old = HDBracket.ForChannel(s.old, channel) || {};

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides || !data.bracket.placement) {
      placed = null;
      items = {};
      sheets = [];
      paths = [];
      move = null;
      lastSignature = null;
      document.querySelector(".stage").innerHTML = "";
      $("body").removeClass("has_focus");
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

    const all = built || s.changed("layout_theme") || old.bracket?.playersPath !== data.bracket.playersPath;
    const changed =
      all ||
      !_.isEqual(_.get(data, "bracket.bracket"), _.get(old, "bracket.bracket")) ||
      !_.isEqual(_.get(data, "bracket.players"), _.get(old, "bracket.players"));
    if (changed) updateSets(s, data, old, all);
    const standingsChanged = updateStandings(data);
    // The theme changes how everything looks, without changing an element
    if (!built && s.changed("layout_theme")) touchAll();

    const focus = focusOf(s, data);
    const focusKey = JSON.stringify([focus, glows(focus), s.settings.ignore_focus, maxZoom(s)]);
    if (built || standingsChanged || focusKey != lastFocus) {
      // The first time it's just there; after that, the camera moves
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
