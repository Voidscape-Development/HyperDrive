// The bracket widget's bracket (bracket.bracket), drawn once at full size
// and zoomed to what's in focus on its channel (bracket.focus.<channel>,
// see docs/layout-data.md):
// sets and rounds picked in the bracket widget, a player's run, the set on
// a scoreboard or a tour of the rounds. The sets in focus are outlined, the
// rest dimmed. Nothing in focus: the whole bracket.
// Options, in the .html or the URL (?channel=Losers%20cam&max_zoom=150):
//   channel       the focus channel shown (default: main), as named in the
//                 bracket widget
//   NO_TITLE      no title bar, the bracket takes the whole page
//   ignore_focus  always the whole bracket
//   max_zoom      the most a set is enlarged, in % (default: the layout
//                 theme's, 200)
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

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
  // Room left around what's in focus, in screen pixels, and under it for
  // the caption saying what it is
  const PADDING = 60;
  const LABEL_ROOM = 90;
  const CAMERA_TIME = 1.0;

  Start = async () => {};

  // Set id: number used in class names (ids can be anything)
  let setIndex = {};
  // What Build() placed: {sets: {id: {x, y, w, h}}, headers: {key: {...}}, width, height}
  let placed = null;
  let lastSignature = null;
  let lastFocus = null;
  let camera = null;

  const SetElement = (id) => $(`.set_${setIndex[id]}`);

  function PlayerHtml(slot) {
    return `
      <div class="slot_p_${slot} player container" data-slot="${slot}">
        <div class="icon avatar"></div>
        <div class="icon online_avatar"></div>
        <div class="seed"></div>
        <div class="name_twitter">
          <div class="name"></div>
        </div>
        <div class="sponsor_icon"></div>
        <div class="flags">
          <div class="flagcountry"></div>
          <div class="flagstate"></div>
        </div>
        <div class="character_container"></div>
        <div class="score"></div>
      </div>
    `;
  }

  function SetHtml(id, set, at) {
    setIndex[id] = Object.keys(setIndex).length + 1;
    return `
      <div class="slot set_${setIndex[id]} side_${set.side}" data-set="${_.escape(id)}"
        style="left: ${at.x}px; top: ${at.y}px; width: ${at.w}px; height: ${at.h}px;">
        <div class="set_identifier"><div class="text"></div></div>
        ${PlayerHtml(0)}
        ${PlayerHtml(1)}
      </div>
    `;
  }

  function Shown(set) {
    // Every set is shown, waiting ones with where their players come from,
    // but a grand final reset only when it's needed
    return set && HDBracket.SetState(set, true) != "hidden";
  }

  // Places the columns of one part of the bracket from `top`, each set
  // level with the sets that feed it, like the bracket widget does.
  // Returns the part's bottom.
  function PlaceArea(columns, sets, top, result) {
    let bottom = top;
    let c = 0;
    let lastX = MARGIN;
    const thirdPlace = [];
    const area = new Set(columns.flatMap((column) => column.sets));

    columns.forEach((column) => {
      if (column.side == "third_place") {
        thirdPlace.push(column);
        return;
      }
      const ids = column.sets.filter((id) => Shown(sets[id]));
      if (ids.length == 0) return;
      const x = MARGIN + c * (SET_W + COLUMN_GAP);
      lastX = x;
      c += 1;
      let cursor = top + HEADER_H;
      let firstY = null;
      ids.forEach((id) => {
        const feeders = Object.keys(result.sets).filter(
          (f) => area.has(f) && sets[f].nextWin && sets[f].nextWin.set == id
        );
        let y = cursor;
        if (feeders.length) {
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
      });
      // Grand finals have their name just above them
      const headerY = column.side == "grand_final" ? firstY - HEADER_H : top;
      result.headers[column.key] = { x, y: headerY, w: SET_W, h: HEADER_H - 12, name: column.name };
    });

    // The 3rd place match under the last column
    thirdPlace.forEach((column) => {
      const ids = column.sets.filter((id) => Shown(sets[id]));
      if (ids.length == 0) return;
      let y = bottom + ROW_GAP;
      result.headers[column.key] = { x: lastX, y, w: SET_W, h: HEADER_H - 12, name: column.name };
      y += HEADER_H;
      ids.forEach((id) => {
        result.sets[id] = { x: lastX, y, w: SET_W, h: SET_H };
        y += SET_H + ROW_GAP;
      });
      bottom = y;
    });

    return bottom;
  }

  // Round robin and swiss: a column per round, sets one under the other
  function PlacePool(bracket, result) {
    const sets = bracket.sets || {};
    let bottom = MARGIN;
    let x = MARGIN;
    HDBracket.Columns(bracket, "pool").forEach((column) => {
      result.headers[column.key] = { x, y: MARGIN, w: SET_W, h: HEADER_H - 12, name: column.name };
      let y = MARGIN + HEADER_H;
      column.sets.forEach((id) => {
        if (!sets[id]) return;
        result.sets[id] = { x, y, w: SET_W, h: SET_H };
        y += SET_H + ROW_GAP;
      });
      result.byes[column.key] = { x, y, w: SET_W };
      bottom = Math.max(bottom, y + 40);
      x += SET_W + COLUMN_GAP;
    });
    result.standings = { x, y: MARGIN, w: 800 };
    return bottom;
  }

  function Place(bracket) {
    const sets = bracket.sets || {};
    const result = { sets: {}, headers: {}, byes: {}, areas: [], standings: null };
    let bottom;

    if (HDBracket.IsPool(bracket)) {
      bottom = PlacePool(bracket, result);
    } else {
      const { upper, lower } = HDBracket.Areas(bracket);
      bottom = PlaceArea(upper, sets, MARGIN, result);
      if (lower.length) bottom = PlaceArea(lower, sets, bottom + SECTION_GAP, result);
      result.areas = [upper, lower];
    }

    const boxes = Object.values(result.sets).concat(Object.values(result.headers));
    result.width = Math.max(0, ...boxes.map((b) => b.x + b.w)) + MARGIN;
    result.height = Math.max(bottom, ...boxes.map((b) => b.y + (b.h || 0))) + MARGIN;
    return result;
  }

  // Lines from each set to where its winner goes, within one part of the
  // bracket, and arrows out of it for players going on to another phase
  function LinesHtml(bracket) {
    const sets = bracket.sets || {};
    const path = (points) => "M" + points.map((p) => p.join(" ")).join(" L");
    let lines = "";
    placed.areas.forEach((columns) => {
      const inArea = new Set(columns.flatMap((c) => c.sets));
      inArea.forEach((id) => {
        const set = sets[id];
        const from = placed.sets[id];
        if (!set || !from) return;
        const a = [from.x + from.w, from.y + from.h / 2];
        if (set.nextWin && inArea.has(set.nextWin.set) && placed.sets[set.nextWin.set]) {
          const to = placed.sets[set.nextWin.set];
          if (to.x <= from.x) return;
          const b = [to.x, to.y + PLAYER_H / 2 + (set.nextWin.slot || 0) * (PLAYER_H + SET_GAP)];
          const mid = a[0] + (b[0] - a[0]) / 2;
          lines += `<path class="line" data-from="${_.escape(id)}" data-to="${_.escape(set.nextWin.set)}"
            d="${path([a, [mid, a[1]], [mid, b[1]], b])}" />`;
        } else if (!set.nextWin && bracket.progressionsOut > 0 && ["winners", "losers"].includes(set.side)) {
          const tip = [a[0] + 45, a[1]];
          lines += `<path class="line" data-from="${_.escape(id)}"
            d="${path([a, tip])} M${tip[0] - 10} ${tip[1] - 8} L${tip.join(" ")} L${tip[0] - 10} ${tip[1] + 8}" />`;
        }
      });
    });
    return lines;
  }

  function Build(data) {
    const bracket = data.bracket.bracket;
    const sets = bracket.sets || {};
    setIndex = {};
    placed = Place(bracket);

    let html = "";
    Object.entries(placed.headers).forEach(([key, h]) => {
      html += `<div class="bf_round_name" data-round="${_.escape(key)}"
        style="left: ${h.x}px; top: ${h.y}px; width: ${h.w}px; height: ${h.h}px;"></div>`;
    });
    Object.entries(placed.byes).forEach(([key, b]) => {
      html += `<div class="byes" data-round="${_.escape(key)}"
        style="left: ${b.x}px; top: ${b.y}px; width: ${b.w}px;"></div>`;
    });
    Object.entries(placed.sets).forEach(([id, at]) => {
      html += SetHtml(id, sets[id], at);
    });
    $(".bf_sets").html(html);

    $(".bf_lines")
      .attr({ width: placed.width, height: placed.height })
      .html(LinesHtml(bracket));

    $(".bf_standings").html("").data("html", null);
    if (placed.standings) {
      $(".bf_standings").css({ left: placed.standings.x, top: placed.standings.y, width: placed.standings.w });
    }

    $(".world").css({ width: placed.width, height: placed.height });
    $("body").toggleClass("pool_view", HDBracket.IsPool(bracket));

    // Sets come in column by column
    const order = Object.keys(placed.sets).sort((a, b) => placed.sets[a].x - placed.sets[b].x);
    // (then their styles are left to the CSS, which dims them out of focus)
    gsap.from(
      order.map((id) => SetElement(id).get(0)),
      { autoAlpha: 0, x: -40, duration: 0.4, stagger: 0.015, clearProps: "opacity,visibility,transform" }
    );
    gsap.from($(".bf_lines path, .bf_round_name"), {
      autoAlpha: 0,
      duration: 0.6,
      delay: 0.3,
      clearProps: "opacity,visibility",
    });
  }

  // The world's size, with the pool standings once drawn
  function WorldSize() {
    let width = placed.width;
    let height = placed.height;
    const standings = $(".bf_standings");
    if (placed.standings && standings.children().length) {
      width = Math.max(width, placed.standings.x + standings.outerWidth() + MARGIN);
      height = Math.max(height, placed.standings.y + standings.outerHeight() + MARGIN);
    }
    return { width, height };
  }

  function MaxZoom() {
    const zoom = parseFloat(window.max_zoom || ThemeValue("bracket", "focus_max_zoom", 200));
    return (isFinite(zoom) && zoom > 0 ? zoom : 200) / 100;
  }

  // The box around what's in focus, in world pixels
  function FocusBox(focus) {
    const boxes = [];
    (focus.sets || []).forEach((id) => {
      if (placed.sets[id]) boxes.push(placed.sets[id]);
    });
    (focus.rounds || []).forEach((key) => {
      if (placed.headers[key]) boxes.push(placed.headers[key]);
    });
    if (boxes.length == 0) {
      const size = WorldSize();
      return { x: 0, y: 0, w: size.width, h: size.height };
    }
    const left = Math.min(...boxes.map((b) => b.x));
    const top = Math.min(...boxes.map((b) => b.y));
    const right = Math.max(...boxes.map((b) => b.x + b.w));
    const bottom = Math.max(...boxes.map((b) => b.y + (b.h || 0)));
    return { x: left, y: top, w: right - left, h: bottom - top };
  }

  // Moves the camera to the box, animated or not
  function MoveCamera(box, animate) {
    const viewport = $(".viewport");
    const vw = viewport.width();
    const vh = viewport.height();
    if (!vw || !vh || !box.w || !box.h) return;
    const label =
      $(".focus_label").hasClass("shown") && !$("body").hasClass("hd-bracket-hide-focus-label")
        ? LABEL_ROOM
        : 0;
    const scale = Math.min(
      (vw - PADDING * 2) / box.w,
      (vh - PADDING * 2 - label) / box.h,
      MaxZoom()
    );
    const x = vw / 2 - (box.x + box.w / 2) * scale;
    const y = (vh - label) / 2 - (box.y + box.h / 2) * scale;
    camera = box;
    const target = { x, y, scale, transformOrigin: "0 0" };
    if (animate) {
      gsap.to(".world", { ...target, duration: CAMERA_TIME, ease: "power2.inOut", overwrite: true });
    } else {
      gsap.set(".world", target);
    }
  }

  // The channel's name as the app keeps it: no dots or extra spaces
  const CHANNEL =
    String(window.channel || "")
      .replace(/\./g, " ")
      .split(/\s+/)
      .filter((w) => w)
      .join(" ")
      .slice(0, 40)
      .trim() || "main";

  function Focus(data) {
    if (window.ignore_focus) return { sets: [], rounds: [] };
    return _.get(data, ["bracket", "focus", CHANNEL]) || { sets: [], rounds: [] };
  }

  function ApplyFocus(data, animate) {
    const focus = Focus(data);
    const inFocus = new Set((focus.sets || []).filter((id) => placed.sets[id]));
    const rounds = new Set(focus.rounds || []);

    $("body").toggleClass("has_focus", inFocus.size > 0);
    $(".slot").each(function () {
      $(this).toggleClass("focused", inFocus.has($(this).attr("data-set")));
    });
    $(".bf_lines path").each(function () {
      const from = $(this).attr("data-from");
      const to = $(this).attr("data-to");
      $(this).toggleClass("focused", inFocus.has(from) && (!to || inFocus.has(to)));
    });
    // A round is highlighted when it's in focus, and not dimmed while any
    // of its sets is
    const columns = Object.values(_.get(data, "bracket.bracket.sides", {})).flat();
    $(".bf_round_name").each(function () {
      const key = $(this).attr("data-round");
      const column = columns.find((c) => c.key == key);
      const any = column && column.sets.some((id) => inFocus.has(id));
      $(this).toggleClass("focused", rounds.has(key) || !!any);
    });

    // The player whose run it is
    const player = focus.mode == "player" ? focus.player : null;
    $(".slot .player").removeClass("focus_player");
    if (player != null) {
      const sets = _.get(data, "bracket.bracket.sets", {});
      inFocus.forEach((id) => {
        (sets[id].players || []).forEach((p, slot) => {
          if (p && p.id == player) SetElement(id).find(`.slot_p_${slot}`).addClass("focus_player");
        });
      });
    }

    const label = inFocus.size > 0 ? focus.label || "" : "";
    $(".focus_label").toggleClass("shown", label != "");
    SetInnerHtml($(".focus_label .label"), _.escape(label));

    MoveCamera(FocusBox({ sets: [...inFocus], rounds: inFocus.size ? [...rounds] : [] }), animate);
  }

  async function UpdatePlayer(element, playerExport, players, event) {
    const team = playerExport && playerExport.id ? players[playerExport.id] : null;
    const fields = [".name", ".flagcountry", ".flagstate", ".sponsor_icon", ".avatar", ".online_avatar", ".seed"];

    $(element).toggleClass("pending", !!(playerExport && playerExport.pending));
    $(element).toggleClass("empty", !team);

    if (!team) {
      for (const f of fields) SetInnerHtml($(element).find(f), "");
      SetInnerHtml($(element).find(".character_container"), "");
      if (playerExport && playerExport.pending && playerExport.source) {
        SetInnerHtml($(element).find(".name"), `<span class="pending_source">${_.escape(playerExport.source)}</span>`);
      }
      return;
    }

    SetInnerHtml($(element).find(".name"), await HDBracket.TeamName(team));
    SetInnerHtml($(element).find(".seed"), playerExport.seed ? String(playerExport.seed) : "");

    const singles = Object.values(team.player || {}).length == 1;
    const player = singles ? team.player["1"] : null;

    SetInnerHtml(
      $(element).find(".flagcountry"),
      player && _.get(player, "country.asset") ? `<img class='flag' src='../../${player.country.asset.toLowerCase()}' />` : ""
    );
    SetInnerHtml(
      $(element).find(".flagstate"),
      player && _.get(player, "state.asset") ? `<img class='flag' src='../../${player.state.asset}' />` : ""
    );
    SetInnerHtml(
      $(element).find(".sponsor_icon"),
      player && player.sponsor_logo ? `<img class='sponsor_icon' src='../../${player.sponsor_logo}' />` : ""
    );
    SetInnerHtml(
      $(element).find(".avatar"),
      player && player.avatar ? `<img class='avatar' src='../../${player.avatar}' />` : ""
    );
    SetInnerHtml(
      $(element).find(".online_avatar"),
      player && player.online_avatar ? `<img class='online_avatar' src='${player.online_avatar}' />` : ""
    );

    await CharacterDisplay(
      $(element).find(".character_container"),
      singles
        ? { source: `bracket.players.slot.${playerExport.id}` }
        : { slice_character: [0, 1], source: `bracket.players.slot.${playerExport.id}` },
      event
    );
  }

  async function UpdateSets(data, event) {
    const bracket = data.bracket.bracket;
    const sets = bracket.sets || {};
    const players = _.get(data, "bracket.players.slot", {});

    const columns = Object.values(bracket.sides || {}).flat();
    $(".bf_round_name").each(function () {
      const column = columns.find((c) => c.key == $(this).attr("data-round"));
      SetInnerHtml($(this), column ? column.name : "");
    });
    const byes = HDBracket.ByesText(bracket);
    $(".byes").each(function () {
      const text = byes[$(this).attr("data-round")];
      SetInnerHtml($(this), text ? `Bye: ${_.escape(text)}` : "");
    });

    for (const id of Object.keys(placed.sets)) {
      const set = sets[id];
      const element = SetElement(id);
      if (!set || !element.get(0)) continue;

      SetInnerHtml(element.find(".set_identifier"), set.identifier || "");

      const winner = HDBracket.Winner(set);
      for (const slot of [0, 1]) {
        const playerElement = element.find(`.slot_p_${slot}`);
        SetInnerHtml(playerElement.find(".score"), HDBracket.ScoreText(set, slot));
        playerElement.toggleClass("won", winner === slot);
        playerElement.toggleClass("lost", winner === 1 - slot);
        playerElement.toggleClass("draw", winner === "draw");
        await UpdatePlayer(playerElement, set.players[slot], players, event);
      }
    }
  }

  async function UpdateStandings(data) {
    const bracket = data.bracket.bracket;
    if (!HDBracket.IsPool(bracket)) return false;
    const html = await HDBracket.StandingsHtml(data);
    if ($(".bf_standings").data("html") == html) return false;
    $(".bf_standings").data("html", html).html(html);
    return true;
  }

  Update = async (event) => {
    const data = event.data;
    const oldData = event.oldData;

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      $(".bf_sets, .bf_lines, .bf_standings").html("");
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
      Build(data);
      built = true;
    }

    const bracketChanged =
      built ||
      JSON.stringify(_.get(data, "bracket.bracket")) != JSON.stringify(_.get(oldData, "bracket.bracket")) ||
      JSON.stringify(_.get(data, "bracket.players")) != JSON.stringify(_.get(oldData, "bracket.players")) ||
      JSON.stringify(data.layout_theme) != JSON.stringify(oldData.layout_theme);

    if (bracketChanged) {
      await UpdateSets(data, event);
    }
    const standingsChanged = await UpdateStandings(data);

    const focusKey = JSON.stringify([Focus(data), window.ignore_focus, MaxZoom()]);
    if (built || standingsChanged || focusKey != lastFocus) {
      // The first time it's just there; after that, the camera moves
      ApplyFocus(data, lastFocus != null && !built);
      lastFocus = focusKey;
    }

    SetInnerHtml($(`.tournament_name`), data.tournamentInfo.tournamentName);
    SetInnerHtml($(`.event_name`), data.tournamentInfo.eventName);
    SetInnerHtml($(`.bracket_name`), data.bracket.phase || data.bracket.bracket.name);
    SetInnerHtml($(`.pool_name`), data.bracket.phaseGroup);
  };

  // The page (e.g. the browser source) was resized
  $(window).on("resize", () => {
    if (placed && camera) MoveCamera(camera, false);
  });
});
