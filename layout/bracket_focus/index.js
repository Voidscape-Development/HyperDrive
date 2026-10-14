// Its channel's bracket (bracket.channels.<channel>), drawn once at full
// size and zoomed to what's in focus on the channel (bracket.focus.<channel>,
// see docs/layout-data.md): sets and rounds picked in the bracket widget, a
// player's run, the set on a scoreboard or a tour of the rounds. The sets in
// focus are outlined, the rest dimmed. Nothing in focus: the whole bracket.
// Options, page or URL (?channel=Losers%20cam&max_zoom=150):
//   channel       the channel shown (default: main), as named in the
//                 bracket widget's tabs
//   ignore_focus  always the whole bracket
//   max_zoom      the most a set is enlarged, in % (default: the layout
//                 theme's, 200)
// no_title.html has no title bar: the bracket takes the whole page.

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
const CAMERA_TIME = 1.0;

// Set id: number used in class names (ids can be anything)
let setIndex = {};
// What build() placed: {sets: {id: {x, y, w, h}}, headers, byes, areas,
// standings, width, height}
let placed = null;
let lastSignature = null;
let lastFocus = null;
let camera = null;

const setElement = (id) => $(`.set_${setIndex[id]}`);
const box = (b) => `left: ${b.x}px; top: ${b.y}px; width: ${b.w}px;${b.h ? ` height: ${b.h}px;` : ""}`;

// Every set is shown, waiting ones with where their players come from, but
// a grand final reset only when it's needed
const isShown = (set) => set && HDBracket.SetState(set, true) != "hidden";

// Places the columns of one part of the bracket from `top`, each set level
// with the sets that feed it, like the bracket widget does. Returns the
// part's bottom.
function placeArea(columns, sets, top, result) {
  let bottom = top;
  let lastX = MARGIN;
  const thirdPlace = [];
  const area = new Set(columns.flatMap((column) => column.sets));

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
      const feeders = Object.keys(result.sets).filter((f) => area.has(f) && sets[f].nextWin && sets[f].nextWin.set == id);
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

// Lines from each set to where its winner goes, within one part of the
// bracket, and arrows out of it for players going on to another phase
function lines(bracket) {
  const sets = bracket.sets || {};
  const path = (points) => `M${points.map((p) => p.join(" ")).join(" L")}`;
  return placed.areas.flatMap((columns) => {
    const inArea = new Set(columns.flatMap((c) => c.sets));
    return [...inArea].map((id) => {
      const set = sets[id];
      const from = placed.sets[id];
      if (!set || !from) return "";
      const a = [from.x + from.w, from.y + from.h / 2];
      const to = set.nextWin && inArea.has(set.nextWin.set) && placed.sets[set.nextWin.set];
      if (to) {
        if (to.x <= from.x) return "";
        const b = [to.x, to.y + PLAYER_H / 2 + (set.nextWin.slot || 0) * (PLAYER_H + SET_GAP)];
        const mid = a[0] + (b[0] - a[0]) / 2;
        return HD.html`<path class="line" data-from="${id}" data-to="${set.nextWin.set}" d="${path([a, [mid, a[1]], [mid, b[1]], b])}" />`;
      }
      if (!set.nextWin && bracket.progressionsOut > 0 && ["winners", "losers"].includes(set.side)) {
        const [x, y] = [a[0] + 45, a[1]];
        return HD.html`<path class="line" data-from="${id}" d="${path([a, [x, y]])} M${x - 10} ${y - 8} L${x} ${y} L${x - 10} ${y + 8}" />`;
      }
      return "";
    });
  });
}

function build(data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  setIndex = {};
  placed = place(bracket);

  HD.render(".bf_sets", [
    Object.entries(placed.headers).map(([key, h]) => HD.html`<div class="bf_round_name" data-round="${key}" style="${box(h)}"></div>`),
    Object.entries(placed.byes).map(([key, b]) => HD.html`<div class="byes" data-round="${key}" style="${box(b)}"></div>`),
    Object.entries(placed.sets).map(([id, at]) => {
      setIndex[id] = Object.keys(setIndex).length + 1;
      return HD.html`
        <div class="slot set_${setIndex[id]} side_${sets[id].side}" data-set="${id}" style="${box(at)}">
          <div class="set_identifier"><div class="text"></div></div>
          ${HDBracket.PlayerSlotHtml(0)}
          ${HDBracket.PlayerSlotHtml(1)}
        </div>`;
    }),
  ]);
  HD.render($(".bf_lines").attr({ width: placed.width, height: placed.height }), lines(bracket));

  const standings = $(".bf_standings").removeData("hd-build").empty();
  if (placed.standings) standings.css({ left: placed.standings.x, top: placed.standings.y, width: placed.standings.w });
  $(".world").css({ width: placed.width, height: placed.height });
  $("body").toggleClass("pool_view", HDBracket.IsPool(bracket));

  // Sets come in column by column (then their styles are left to the CSS,
  // which dims them out of focus)
  const order = Object.keys(placed.sets).sort((a, b) => placed.sets[a].x - placed.sets[b].x);
  gsap.from(
    order.map((id) => setElement(id).get(0)),
    { autoAlpha: 0, x: -40, duration: 0.4, stagger: 0.015, clearProps: "opacity,visibility,transform" },
  );
  gsap.from(".bf_lines path, .bf_round_name", { autoAlpha: 0, duration: 0.6, delay: 0.3, clearProps: "opacity,visibility" });
}

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

// Moves the camera to a box, animated or not
function moveCamera(s, target, animate) {
  const viewport = $(".viewport");
  const vw = viewport.width();
  const vh = viewport.height();
  if (!vw || !vh || !target.w || !target.h) return;
  const label = $(".focus_label").hasClass("shown") && !$("body").hasClass("hd-bracket-hide-focus-label") ? LABEL_ROOM : 0;
  const scale = Math.min((vw - PADDING * 2) / target.w, (vh - PADDING * 2 - label) / target.h, maxZoom(s));
  camera = target;
  const vars = {
    x: vw / 2 - (target.x + target.w / 2) * scale,
    y: (vh - label) / 2 - (target.y + target.h / 2) * scale,
    scale,
    transformOrigin: "0 0",
  };
  if (animate) gsap.to(".world", { ...vars, duration: CAMERA_TIME, ease: "power2.inOut", overwrite: true });
  else gsap.set(".world", vars);
}

const channelOf = (s) => HDBracket.ChannelName(s.settings.channel) || "main";

const focusOf = (s, data) =>
  (!s.settings.ignore_focus && _.get(data, ["bracket", "focus", channelOf(s)])) || { sets: [], rounds: [] };

function applyFocus(s, data, animate) {
  const focus = focusOf(s, data);
  const inFocus = new Set((focus.sets || []).filter((id) => placed.sets[id]));
  const rounds = new Set(focus.rounds || []);

  $("body").toggleClass("has_focus", inFocus.size > 0);
  $(".slot").each((_i, el) => $(el).toggleClass("focused", inFocus.has(el.dataset.set)));
  $(".bf_lines path").each((_i, el) => {
    const { from, to } = el.dataset;
    $(el).toggleClass("focused", inFocus.has(from) && (to == null || inFocus.has(to)));
  });
  // A round is highlighted when it's in focus, and not dimmed while any of
  // its sets is
  const columns = Object.values(_.get(data, "bracket.bracket.sides", {})).flat();
  $(".bf_round_name").each((_i, el) => {
    const column = columns.find((c) => c.key == el.dataset.round);
    $(el).toggleClass("focused", rounds.has(el.dataset.round) || !!(column && column.sets.some((id) => inFocus.has(id))));
  });

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

  const label = inFocus.size > 0 ? focus.label || "" : "";
  $(".focus_label").toggleClass("shown", label !== "");
  HD.set(".focus_label .label", label);

  moveCamera(s, focusBox({ sets: [...inFocus], rounds: inFocus.size ? [...rounds] : [] }), animate);
}

function updateSets(s, data) {
  const bracket = data.bracket.bracket;
  const columns = Object.values(bracket.sides || {}).flat();
  $(".bf_round_name").each((_i, el) => {
    const column = columns.find((c) => c.key == el.dataset.round);
    HD.set(el, column ? column.name : "");
  });
  const byes = HDBracket.ByesText(bracket);
  $(".byes").each((_i, el) => HD.set(el, byes[el.dataset.round] ? `Bye: ${byes[el.dataset.round]}` : ""));

  for (const id of Object.keys(placed.sets)) {
    const set = bracket.sets[id];
    const element = setElement(id);
    if (set && element.get(0)) HDBracket.UpdateSet(s, element, set, data);
  }
}

HD.layout({
  init() {
    // The page (e.g. the browser source) was resized
    $(window).on("resize", () => placed && camera && moveCamera(HD.scope(), camera, false));
  },

  update(s) {
    const channel = channelOf(s);
    const data = HDBracket.ForChannel(s.data, channel);
    const old = HDBracket.ForChannel(s.old, channel) || {};

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      HD.render(".bf_sets, .bf_lines, .bf_standings", "");
      $("body").removeClass("has_focus");
      $(".focus_label").removeClass("shown");
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

    const changed =
      built ||
      !_.isEqual(_.get(data, "bracket.bracket"), _.get(old, "bracket.bracket")) ||
      !_.isEqual(_.get(data, "bracket.players"), _.get(old, "bracket.players")) ||
      s.changed("layout_theme");
    if (changed) updateSets(s, data);

    const standings = HDBracket.IsPool(data.bracket.bracket) ? HDBracket.StandingsHtml(data) : null;
    const standingsChanged = !!standings && HD.build(".bf_standings", String(standings), standings);

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
