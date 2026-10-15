// The bracket widget's bracket (bracket.bracket, see docs/layout-data.md).
// Elimination brackets: winners and grand finals on top, losers below, with
// lines from each set to the next. Round robin and swiss pools: each round's
// sets with the standings beside them.
// Page options: always_expand shows every set from the start, winners_only
// / losers_only one side, standings_only just the standings, grid_only a
// round robin / swiss pool as a grid of who played who.
// ?channel=<name> in the URL shows that channel of the bracket widget (the
// main one without it).

// ---------------------------------------------------------------------
// State

// Per set id: its timeline, labels hidden > displayed > done
let animations = {};
let entryAnim = null;
// Set id: number used in class names (ids can be anything)
let setIndex = {};
let lastSignature = null;

const setElement = (id) => $(`.set_${setIndex[id]}`);

// ---------------------------------------------------------------------
// Markup and lines

// A line drawing itself
function animateLine(element) {
  const path = element.get(0);
  if (!path) return null;
  const length = path.getTotalLength();
  return gsap.from(path, {
    duration: 0.4,
    "stroke-dashoffset": length,
    "stroke-dasharray": length,
    autoAlpha: 0,
    onUpdate() {
      const progress = (this.progress() * 100) >> 0;
      const now = path.getTotalLength();
      gsap.set(path, {
        "stroke-dashoffset": (now / 100) * (100 - progress),
        "stroke-dasharray": now,
        autoAlpha: progress ? 1 : 0,
      });
    },
  });
}

function setBox(id, set) {
  setIndex[id] = Object.keys(setIndex).length + 1;
  return HD.html`
    <div class="slot set_${setIndex[id]} side_${set.side}" data-set="${id}">
      <div class="set_identifier"><div class="text"></div></div>
      ${HDBracket.PlayerSlotHtml(0)}
      ${HDBracket.PlayerSlotHtml(1)}
    </div>`;
}

function columnsHtml(columns, sets) {
  const shown = (column) => (column ? column.sets.filter((id) => sets[id]) : []);
  return columns.map((column, c) => {
    const ids = shown(column);
    const nextIds = shown(columns[c + 1]);
    const next = columns[c + 1];
    // A play-in round: each set level with the slot its winner goes to,
    // with spacers where the next round's sets have no play-in
    const playIn =
      column.side != "pool" &&
      next &&
      next.side == column.side &&
      ids.length < nextIds.length &&
      ids.every((id) => sets[id].nextWin && nextIds.includes(sets[id].nextWin.set));
    const content = playIn
      ? nextIds.map((nextId) => {
          const feeders = ids.filter((id) => sets[id].nextWin.set == nextId);
          if (feeders.length === 0) return HD.html`<div class="set_spacer"></div>`;
          const slot = feeders.length === 1 ? sets[feeders[0]].nextWin.slot || 0 : null;
          return HD.html`<div class="play_in ${slot != null && `play_in_slot_${slot}`}">${feeders.map((id) => setBox(id, sets[id]))}</div>`;
        })
      : ids.map((id) => setBox(id, sets[id]));
    return HD.html`
      <div class="round round_${c + 1} side_${column.side || "pool"}" data-round="${column.key}">
        <div class="round_name"><div class="text"></div></div>
        ${content}
        ${column.byes && HD.html`<div class="byes"><div class="text"></div></div>`}
      </div>`;
  });
}

// Lines from each set to where its winner goes, within one part of the
// bracket, and arrows out of it for players going on to another phase
function linesHtml(bracket, areas) {
  const sets = bracket.sets || {};
  const point = (el, side) => [
    side == "right" ? el.offset().left + el.outerWidth() : el.offset().left,
    el.offset().top + el.outerHeight() / 2,
  ];
  const path = (points) => `M${points.map((p) => p.join(" ")).join(" L")}`;
  const lines = [];

  for (const columns of areas) {
    const inArea = new Set(columns.flatMap((c) => c.sets));
    for (const id of columns.flatMap((c) => c.sets)) {
      const set = sets[id];
      const from = setElement(id);
      if (!set || !from.offset()) continue;
      if (set.nextWin && inArea.has(set.nextWin.set)) {
        const to = setElement(set.nextWin.set);
        if (!to.offset() || HDBracket.SetState(sets[set.nextWin.set], true) == "hidden") continue;
        const a = point(from, "right");
        const b = point(to, "left");
        const mid = a[0] + (b[0] - a[0]) / 2;
        lines.push(
          HD.html`<path class="line line_${setIndex[id]}" d="${path([a, [mid, a[1]], [mid, b[1]], b])}" fill="none" />`,
        );
      } else if (!set.nextWin && bracket.progressionsOut > 0 && ["winners", "losers"].includes(set.side)) {
        const a = point(from, "right");
        const [x, y] = [a[0] + 45, a[1]];
        lines.push(
          HD.html`<path class="line line_out_${setIndex[id]}" d="${path([a, [x, y]])} M${x - 10} ${y - 8} L${x} ${y} L${x - 10} ${y + 8}" fill="none" />`,
        );
      }
    }
  }
  return lines;
}

// ---------------------------------------------------------------------
// Fitting the page

// Spacers as tall as a set, and play-in sets moved level with the slot
// they feed (a slot is the top or bottom half of the set)
function alignPlayIns() {
  const height = $(".round > .slot, .play_in > .slot").first().outerHeight() || 0;
  $(".set_spacer").css("height", height);
  $(".play_in_slot_0 > .slot").css("top", -height / 4);
  $(".play_in_slot_1 > .slot").css("top", height / 4);
}

// Fits the sets in the height there is
function resize(columnsList, containers) {
  let size = 32;
  columnsList.forEach((columns, i) => {
    const container = containers[i];
    // Parts not shown (e.g. winners on losers_only.html) don't count
    if (!container || columns.length === 0 || container.height() < 60) return;
    const biggest = Math.max(1, ...columns.map((c) => c.sets.length));
    while (biggest * (2 * size + 12) > container.height() - 40 && size > 8) size -= 1;
  });
  const root = $(":root");
  root.css("--player-height", size);
  root.css("--name-size", Math.min(size * 0.7, 24));
  root.css("--score-size", size * 0.75);
  root.css("--flag-height", size * 0.6);
}

// ---------------------------------------------------------------------
// Building and updating

// Plays a set's timeline to its state (pools show every set)
const showSet = (s, id, set, pool) =>
  animations[id] && animations[id].tweenTo(HDBracket.SetState(set, s.settings.always_expand || pool));

function build(s, data) {
  const bracket = data.bracket.bracket;
  const sets = bracket.sets || {};
  const pool = HDBracket.IsPool(bracket);
  setIndex = {};

  $("body").toggleClass("pool_view", pool).toggleClass("elimination_view", !pool);
  HD.render(".winners_container, .losers_container, .pool_container", "");

  let areas;
  if (pool) {
    const byes = HDBracket.ByesText(bracket);
    const columns = HDBracket.Columns(bracket, "pool").map((c) => ({ ...c, side: "pool", byes: byes[c.key] || "" }));
    HD.render(".pool_container", columnsHtml(columns, sets));
    resize([columns], [$(".pool_container")]);
    areas = [columns];
  } else {
    let { upper, lower } = HDBracket.Areas(bracket);
    if (s.settings.winners_only) lower = [];
    if (s.settings.losers_only) upper = [];
    $("body").toggleClass("no_lower", lower.length === 0);
    HD.render(".winners_container", columnsHtml(upper, sets));
    HD.render(".losers_container", columnsHtml(lower, sets));
    resize([upper, lower], [$(".winners_container"), $(".losers_container")]);
    alignPlayIns();
    areas = [upper, lower];
  }
  HD.render(".lines", pool ? "" : linesHtml(bracket, areas));

  // Each set slides in, then its lines draw; the timeline stops at the
  // set's state (hidden, displayed or done)
  animations = {};
  entryAnim = gsap.timeline();
  areas.forEach((columns) =>
    columns.forEach((column, c) =>
      column.sets.forEach((id, i) => {
        if (!sets[id]) return;
        const anim = gsap.timeline({ paused: true });
        anim.addLabel("hidden").from(setElement(id), { x: -50, autoAlpha: 0, duration: 0.4 }, 0).addLabel("displayed");
        anim.add(animateLine($(`.line_${setIndex[id]}`)), 0.4).add(animateLine($(`.line_out_${setIndex[id]}`)), 0.4);
        anim.addLabel("done");
        animations[id] = anim;
        entryAnim.add(showSet(s, id, sets[id], pool), c * 0.4 + i * 0.02);
      }),
    ),
  );
  entryAnim.play(0);
}

function updateSets(s, data) {
  const bracket = data.bracket.bracket;

  // Round names and byes
  const columns = Object.values(bracket.sides || {}).flat();
  $(".round").each((_i, el) => {
    const column = columns.find((c) => c.key == el.dataset.round);
    HD.set($(el).find(".round_name"), column ? column.name : "");
  });
  const byes = HDBracket.ByesText(bracket);
  $(".pool_container .round").each((_i, el) => {
    const text = byes[el.dataset.round];
    HD.set($(el).find(".byes"), text ? `Bye: ${text}` : "");
  });

  for (const [id, set] of Object.entries(bracket.sets || {})) {
    const element = setElement(id);
    if (element.get(0)) HDBracket.UpdateSet(s, element, set, data);
  }
}

function updateStandings(s, data) {
  const container = $(".standings_container");
  if (!container.get(0)) return;
  const show = s.settings.standings_only || HDBracket.IsPool(data.bracket.bracket);
  container.toggleClass("hidden", !show);
  if (!show) return;
  const html = HDBracket.StandingsHtml(data);
  if (HD.build(container.find(".standings"), String(html), html)) {
    gsap.from(container.find("tbody tr"), { autoAlpha: 0, x: -20, stagger: 0.04, duration: 0.3 });
  }
}

function updateGrid(data) {
  const container = $(".grid_container");
  if (!container.get(0)) return;
  const show = HDBracket.IsPool(data.bracket.bracket);
  container.toggleClass("hidden", !show);
  if (!show) return;
  const html = HDBracket.GridHtml(data);
  // Rows slide in only when the pool's shape changed, not for a score
  const reshaped = container.data("shape") !== HDBracket.Signature(data);
  container.data("shape", HDBracket.Signature(data));
  if (HD.build(container, String(html), html) && reshaped) {
    gsap.from(container.find("tr"), { autoAlpha: 0, x: -20, stagger: 0.04, duration: 0.3 });
  }
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["bracket", "score", "game", "tournamentInfo", "commentary"],
  update(s) {
    const channel = HDBracket.ChannelName(s.settings.channel);
    const forChannel = (d) => (channel ? HDBracket.ForChannel(d, channel) : d);
    let data = forChannel(s.data);
    const old = forChannel(s.old) || {};
    if (data.bracket && !data.bracket.playersPath)
      data = { ...data, bracket: { ...data.bracket, playersPath: "bracket.players" } };

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      HD.render(".winners_container, .losers_container, .pool_container, .grid_container, .lines", "");
      $(".grid_container").removeData("hd-build");
      lastSignature = null;
      return;
    }
    if (lastSignature && _.isEqual(data.bracket, old.bracket) && !s.changed("layout_theme")) return;

    if (s.settings.grid_only) {
      updateGrid(data);
    } else if (!s.settings.standings_only) {
      const signature = HDBracket.Signature(data);
      if (signature != lastSignature) {
        lastSignature = signature;
        build(s, data);
      } else if (entryAnim && entryAnim.progress() >= 1) {
        for (const [id, set] of Object.entries(data.bracket.bracket.sets || {})) {
          showSet(s, id, set, HDBracket.IsPool(data.bracket.bracket));
        }
      }
      updateSets(s, data);
    }
    updateStandings(s, data);

    s.set(".tournament_name", data.tournamentInfo.tournamentName);
    s.set(".event_name", data.tournamentInfo.eventName);
    s.set(".bracket_name", data.bracket.phase || data.bracket.bracket.name);
    s.set(".pool_name", data.bracket.phaseGroup);
  },
});
