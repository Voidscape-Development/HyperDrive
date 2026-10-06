// The bracket widget's bracket (bracket.bracket, see docs/layout-data.md).
// Elimination brackets: winners and grand finals on top, losers below, with
// lines from each set to the next. Round robin and swiss pools: each round's
// sets with the standings beside them.
// Options (set in the .html): ALWAYS_EXPAND shows every set from the start,
// WINNERS_ONLY / LOSERS_ONLY one side, STANDINGS_ONLY just the standings.
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  let startingAnimation = gsap.timeline({ paused: true });

  Start = async (event) => {
    startingAnimation.restart();
  };

  var entryAnim = gsap.timeline();
  // Per set id: its timeline, labels hidden > displayed > done
  var animations = {};
  // Set id: number used in class names (ids can be anything)
  var setIndex = {};
  var lastSignature = null;

  function AnimateLine(element) {
    let anim = null;

    if (element && element.get(0)) {
      element = element.get(0);
      let length = element.getTotalLength();
      anim = gsap.from(
        element,
        {
          duration: 0.4,
          "stroke-dashoffset": length,
          "stroke-dasharray": length,
          autoAlpha: 0,
          onUpdate: function () {
            let tlp = (this.progress() * 100) >> 0;
            if (element) {
              let length = element.getTotalLength();
              gsap.set(element, {
                "stroke-dashoffset": (length / 100) * (100 - tlp),
                "stroke-dasharray": length,
                autoAlpha: tlp == 0 ? 0 : 1,
              });
            }
          },
        },
        0
      );
    }

    return anim;
  }

  function SetElement(id) {
    return $(`.set_${setIndex[id]}`);
  }

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

  function SetHtml(id, set) {
    setIndex[id] = Object.keys(setIndex).length + 1;
    return `
      <div class="slot set_${setIndex[id]} side_${set.side}" data-set="${_.escape(id)}">
        <div class="set_identifier"><div class="text"></div></div>
        ${PlayerHtml(0)}
        ${PlayerHtml(1)}
      </div>
    `;
  }

  function ColumnsHtml(columns, sets) {
    let html = "";
    columns.forEach((column, c) => {
      html += `<div class="round round_${c + 1} side_${column.side || "pool"}" data-round="${_.escape(column.key)}">`;
      html += `<div class="round_name"><div class="text"></div></div>`;
      column.sets.forEach((id) => {
        if (sets[id]) html += SetHtml(id, sets[id]);
      });
      if (column.byes) {
        html += `<div class="byes"><div class="text"></div></div>`;
      }
      html += "</div>";
    });
    return html;
  }

  // Lines from each set to where its winner goes, within one part of the
  // bracket, and arrows out of it for players going on to another phase
  function LinesHtml(bracket, areas) {
    let lines = "";
    const sets = bracket.sets || {};
    const point = (el, side) => [
      side == "right" ? el.offset().left + el.outerWidth() : el.offset().left,
      el.offset().top + el.outerHeight() / 2,
    ];
    const path = (points) =>
      "M" + points.map((p) => p.join(" ")).join(" L");

    areas.forEach((columns) => {
      const inArea = new Set(columns.flatMap((c) => c.sets));
      columns.forEach((column) => {
        column.sets.forEach((id) => {
          const set = sets[id];
          const from = SetElement(id);
          if (!set || !from.offset()) return;
          if (set.nextWin && inArea.has(set.nextWin.set)) {
            const target = sets[set.nextWin.set];
            const to = SetElement(set.nextWin.set);
            if (!to.offset() || HDBracket.SetState(target, true) == "hidden") return;
            const a = point(from, "right");
            const b = point(to, "left");
            const mid = a[0] + (b[0] - a[0]) / 2;
            lines += `<path class="line line_${setIndex[id]}" d="${path([a, [mid, a[1]], [mid, b[1]], b])}" fill="none" />`;
          } else if (!set.nextWin && bracket.progressionsOut > 0 && ["winners", "losers"].includes(set.side)) {
            const a = point(from, "right");
            const tip = [a[0] + 45, a[1]];
            lines += `<path class="line line_out_${setIndex[id]}" d="${path([a, tip])} M${tip[0] - 10} ${tip[1] - 8} L${tip.join(" ")} L${tip[0] - 10} ${tip[1] + 8}" fill="none" />`;
          }
        });
      });
    });
    return lines;
  }

  // Fits the sets in the height there is
  function Resize(columnsList, containers) {
    let size = 32;
    $(":root").css("--player-height", size);

    columnsList.forEach((columns, i) => {
      const container = containers[i];
      // Parts not shown (e.g. winners on losers_only.html) don't count
      if (!container || columns.length == 0 || container.height() < 60) return;
      const biggest = Math.max(1, ...columns.map((c) => c.sets.length));
      while (biggest * (2 * size + 12) > container.height() - 40 && size > 8) {
        size -= 1;
      }
    });

    $(":root").css("--player-height", size);
    $(":root").css("--name-size", Math.min(size - size * 0.3, 24));
    $(":root").css("--score-size", size - size * 0.25);
    $(":root").css("--flag-height", size - size * 0.4);
  }

  function Build(data) {
    const bracket = data.bracket.bracket;
    const sets = bracket.sets || {};
    const pool = HDBracket.IsPool(bracket);
    setIndex = {};

    $("body").toggleClass("pool_view", pool);
    $("body").toggleClass("elimination_view", !pool);
    $(".winners_container, .losers_container, .pool_container").html("");

    let areas = [];

    if (pool) {
      const byes = HDBracket.ByesText(bracket);
      const columns = HDBracket.Columns(bracket, "pool").map((c) => ({
        ...c,
        side: "pool",
        byes: byes[c.key] || "",
      }));
      $(".pool_container").html(ColumnsHtml(columns, sets));
      Resize([columns], [$(".pool_container")]);
      areas = [columns];
    } else {
      let { upper, lower } = HDBracket.Areas(bracket);
      if (window.WINNERS_ONLY) lower = [];
      if (window.LOSERS_ONLY) upper = [];
      $("body").toggleClass("no_lower", lower.length == 0);
      $(".winners_container").html(ColumnsHtml(upper, sets));
      $(".losers_container").html(ColumnsHtml(lower, sets));
      Resize([upper, lower], [$(".winners_container"), $(".losers_container")]);
      areas = [upper, lower];
    }

    $(".lines").html(pool ? "" : LinesHtml(bracket, areas));

    // Animations
    animations = {};
    entryAnim = gsap.timeline();

    areas.forEach((columns) => {
      columns.forEach((column, c) => {
        column.sets.forEach((id, s) => {
          if (!sets[id]) return;
          let anim = gsap.timeline();
          anim.addLabel("hidden");
          anim.from(SetElement(id), { x: -50, autoAlpha: 0, duration: 0.4 }, 0);
          anim.addLabel("displayed");
          anim.add(AnimateLine($(`.line_${setIndex[id]}`)), 0.4);
          anim.add(AnimateLine($(`.line_out_${setIndex[id]}`)), 0.4);
          anim.addLabel("done");
          anim.pause();
          animations[id] = anim;
          entryAnim.add(ShowSet(id, sets[id]), c * 0.4 + s * 0.02);
        });
      });
    });

    entryAnim.play(0);
  }

  function ShowSet(id, set) {
    const anim = animations[id];
    if (!anim) return null;
    const state = HDBracket.SetState(set, window.ALWAYS_EXPAND || HDBracket.IsPool(data.bracket.bracket));
    return anim.tweenTo(state);
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

    // Round names and byes
    $(".round").each(function () {
      const key = $(this).attr("data-round");
      const column = Object.values(bracket.sides || {})
        .flat()
        .find((c) => c.key == key);
      SetInnerHtml($(this).find(".round_name"), column ? column.name : "");
    });
    const byes = HDBracket.ByesText(bracket);
    $(".pool_container .round").each(function () {
      const text = byes[$(this).attr("data-round")];
      SetInnerHtml($(this).find(".byes"), text ? `Bye: ${text}` : "");
    });

    for (const [id, set] of Object.entries(sets)) {
      const element = SetElement(id);
      if (!element.get(0)) continue;

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
    if (!$(".standings_container").get(0)) return;
    const bracket = data.bracket.bracket;
    const show = window.STANDINGS_ONLY || HDBracket.IsPool(bracket);
    $(".standings_container").toggleClass("hidden", !show);
    if (!show) return;
    const html = await HDBracket.StandingsHtml(data);
    if ($(".standings_container").data("html") != html) {
      $(".standings_container").data("html", html);
      $(".standings_container .standings").html(html);
      gsap.from($(".standings_container tbody tr"), { autoAlpha: 0, x: -20, stagger: 0.04, duration: 0.3 });
    }
  }

  Update = async (event) => {
    let data = event.data;
    let oldData = event.oldData;

    if (!data.bracket || !data.bracket.bracket || !data.bracket.bracket.sides) {
      $(".winners_container, .losers_container, .pool_container, .lines").html("");
      lastSignature = null;
      return;
    }

    if (
      lastSignature &&
      oldData.bracket &&
      JSON.stringify(data.bracket) == JSON.stringify(oldData.bracket) &&
      JSON.stringify(data.layout_theme) == JSON.stringify(oldData.layout_theme)
    ) {
      return;
    }

    if (!window.STANDINGS_ONLY) {
      const signature = HDBracket.Signature(data);
      if (signature != lastSignature) {
        lastSignature = signature;
        Build(data);
      } else if (entryAnim && entryAnim.progress() >= 1) {
        for (const [id, set] of Object.entries(data.bracket.bracket.sets || {})) {
          ShowSet(id, set);
        }
      }
      await UpdateSets(data, event);
    }

    await UpdateStandings(data);

    SetInnerHtml($(`.tournament_name`), data.tournamentInfo.tournamentName);
    SetInnerHtml($(`.event_name`), data.tournamentInfo.eventName);
    SetInnerHtml($(`.bracket_name`), data.bracket.phase || data.bracket.bracket.name);
    SetInnerHtml($(`.pool_name`), data.bracket.phaseGroup);
  };
});
