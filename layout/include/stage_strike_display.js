// Stage strike display, shared by layout/stage_strike_display and its MTF
// variant: turns score.<n>.stage_strike and score.ruleset into an ordered
// list of bans and the picked stage, each tagged with who made the call,
// shown as a column, a minimal bar or full cards.
//
// Body classes pick the options: show-available (full: also the stages
// nobody struck yet), pick-center (full: the pick between the stage cards)
// and mtf (team colors tint the panels; the picked stage keeps its place
// among the available ones).
(() => {
  const body = (cls) => document.body.classList.contains(cls);

  // Team names and colors, in the order the stage strike widget uses for
  // strikedBy / currPlayer (reversed when swapped)
  function teams(s) {
    const list = s.teams.map(({ n, team, name }) => ({
      name: name || `P${n}`,
      color: team.color && !s.settings.forceDefaultScoreColors ? team.color : `var(--p${n}-score-bg-color)`,
    }));
    return s.score.teamsSwapped ? list.reverse() : list;
  }

  // Stages banned by the ruleset itself (DSR / MDSR), not by a player
  function rulesetBans(ruleset, strike) {
    if (ruleset.useDSR) return strike.stagesPicked || [];
    if (ruleset.useMDSR && strike.lastWinner !== -1) {
      return strike.stagesWon && strike.stagesWon.length > 0 ? strike.stagesWon[(strike.lastWinner + 1) % 2] : [];
    }
    return [];
  }

  // { teams, bans: [{stage, team, reason}], pick: {stage, team,
  // gentlemans}, turn: {team, action, verb}, game, available, hasContent }
  function strikeState(s) {
    const ruleset = s.data.score.ruleset || {};
    const strike = s.score.stage_strike || {};
    const sides = teams(s);
    const neutral = ruleset.neutralStages || [];
    const counterpick = ruleset.counterpickStages || [];

    const stages = {};
    for (const stage of [...neutral, ...counterpick]) stages[stage.codename] = stage;
    const selected = strike.selectedStageData;
    if (selected && !stages[selected.codename]) stages[selected.codename] = selected;

    const bans = [];
    const seen = new Set();
    const ban = (codename, team, reason) => {
      if (seen.has(codename) || !stages[codename]) return;
      seen.add(codename);
      bans.push({ stage: stages[codename], team, reason });
    };
    // Ruleset bans happen before anyone strikes, so they go first
    for (const codename of rulesetBans(ruleset, strike)) {
      if (codename !== strike.selectedStage) ban(codename, null, ruleset.useDSR ? "DSR" : "MDSR");
    }
    // One array per strike step: flattened, they're in order
    const strikedBy = strike.strikedBy || [[], []];
    for (const codename of Object.values(strike.strikedStages || []).flat()) {
      const t = strikedBy.findIndex((list) => list && list.includes(codename));
      ban(codename, t === -1 ? null : sides[t], null);
    }

    // Stages still in play: game 1 strikes from neutrals, later games add
    // counterpicks. MTF keeps the pick there, so cards keep their place.
    const pool = strike.currGame > 0 ? [...neutral, ...counterpick] : neutral;
    const available = pool.filter(
      (stage) => !seen.has(stage.codename) && (body("mtf") || stage.codename !== strike.selectedStage),
    );

    const pick =
      strike.selectedStage && stages[strike.selectedStage]
        ? {
            stage: stages[strike.selectedStage],
            team: strike.gentlemans ? null : sides[strike.currPlayer] || null,
            gentlemans: !!strike.gentlemans,
          }
        : null;

    // Whose turn it is while the pick is pending
    let turn = null;
    if (!pick && sides[strike.currPlayer]) {
      const picking =
        strike.currGame > 0 ? strike.currStep >= 1 : strike.currStep >= (ruleset.strikeOrder || []).length;
      const action = picking ? "pick" : strike.currGame > 0 ? "ban" : "strike";
      turn = { team: sides[strike.currPlayer], action, verb: { pick: "Picking", ban: "Banning", strike: "Striking" }[action] };
    }

    return {
      bans,
      pick,
      turn,
      game: (strike.currGame || 0) + 1,
      available,
      hasContent: bans.length > 0 || pick != null,
    };
  }

  const image = (stage) => (stage.path ? `url('${HD.asset(stage.path)}')` : "none");
  const stageName = (stage) => stage.display_name || stage.name || stage.codename;
  const neutralColor = "var(--ssd-neutral)";

  // Only what the display shows
  const changed = (s) =>
    s.scoreChanged((score) => [score.stage_strike, score.team, score.teamsSwapped]) || s.changed("score.ruleset");

  // Replaces a container's items, animating in only the ones (by data-key)
  // that weren't there before
  function renderItems(container, items, fromVars) {
    const el = $(container);
    const before = new Set(el.find("[data-key]").map((_i, e) => e.dataset.key).get());
    HD.render(el, items);
    const added = el.find("[data-key]").filter((_i, e) => !before.has(e.dataset.key)).get();
    if (added.length) gsap.from(added, { autoAlpha: 0, duration: 0.3, ease: "power2.out", stagger: 0.06, ...fromVars });
    HD.fit(el.find(".fit"));
  }

  // The panel slides in while there's something to show, out otherwise
  const setVisible = (panel, visible) =>
    gsap.to(panel, {
      autoAlpha: visible ? 1 : 0,
      y: visible ? 0 : 40,
      duration: 0.35,
      ease: visible ? "power3.out" : "power2.in",
      overwrite: true,
    });

  // Shared update: the state, if anything shown changed, after MTF's colors
  const variant = (render) => ({
    update(s) {
      if (!changed(s)) return;
      if (body("mtf")) HD.teamColors(s, ["score-bg-color"]);
      render(strikeState(s), s);
    },
  });

  // A chip naming who made the call, tinted with their color (.team for a
  // player's, so a theme can recolor them)
  const byChip = (label, name, color, team) => HD.html`
    <div class="by_chip ${team ? "team" : ""}" style="--by-color: ${color}">
      <div class="by_label">${label}</div>
      <div class="by_name fit"><div class="text">${name}</div></div>
    </div>`;

  HD.layouts.stageStrike = {
    // column.html: the bans, then the pick, as lines
    column: variant((state) => {
      $(".column_game").text(`Game ${state.game}`);
      const { pick, turn } = state;
      // Each ban's edge is the color of who struck it
      renderItems(
        ".bans",
        state.bans.map(
          ({ stage, team }) => HD.html`
            <div class="ban_line fit ${team ? "team" : ""}" data-key="ban-${stage.codename}" style="--by-color: ${team ? team.color : neutralColor}">
              <div class="text">${stageName(stage)}</div>
            </div>`,
        ),
        { y: -8 },
      );
      $(".pick_label").text(pick ? (pick.gentlemans ? "Gentleman's" : "Picked") : turn ? turn.verb : "Picked");
      renderItems(
        ".pick",
        pick
          ? HD.html`<div class="pick_line fit" data-key="pick-${pick.stage.codename}"><div class="text">${stageName(pick.stage)}</div></div>`
          : HD.html`
            <div class="pick_line pending fit ${turn ? "team" : ""}" data-key="pick-pending" style="--turn-color: ${turn ? turn.team.color : neutralColor}">
              <div class="text">${turn ? turn.team.name : "TBD"}</div>
            </div>`,
        { scale: 1.1 },
      );
      $(".bans_section").toggle(state.bans.length > 0);
      $(".pick_section").toggleClass("pending", !pick);
      setVisible(".ssd_column", state.hasContent);
    }),

    // minimal.html: the bans as thumbnails with a bar in the striker's
    // color, then the pick
    minimal: variant((state) => {
      $(".label_game").text(`Game ${state.game}`);
      const { pick, turn } = state;
      renderItems(
        ".bans",
        state.bans.map(
          ({ stage, team }) => HD.html`
            <div class="ban_item ${team ? "team" : ""}" data-key="ban-${stage.codename}" style="--by-color: ${team ? team.color : neutralColor}">
              <div class="thumb">
                <div class="thumb_image" style="background-image: ${image(stage)}"></div>
                <div class="strike_x"></div>
              </div>
              <div class="stage_name">${stageName(stage)}</div>
            </div>`,
        ),
        { x: -16 },
      );
      renderItems(
        ".pick",
        HD.html`
          <div class="pick_item ${!pick && "pending"}" data-key="${pick ? `pick-${pick.stage.codename}` : "pick-pending"}">
            <div class="thumb" ${pick && HD.html`style="background-image: ${image(pick.stage)}"`}></div>
            <div class="pick_text">
              <div class="pick_label">${pick ? (pick.gentlemans ? "Gentleman's" : "Picked") : turn ? turn.verb : "Picked"}</div>
              <div class="stage_name fit"><div class="text">${pick ? stageName(pick.stage) : "TBD"}</div></div>
            </div>
          </div>`,
        { scale: 1.08 },
      );
      $(".bar_divider").toggle(state.bans.length > 0);
      setVisible(".ssd_bar", state.hasContent);
    }),

    // full.html: cards with the stage art and who banned or picked it,
    // the picked stage blurred behind the panel
    full: (() => {
      let backdrop = null;
      return variant((state) => {
        const { pick, turn } = state;
        $(".header_game").text(`Game ${state.game}`);
        HD.render(
          ".header_status .text",
          pick
            ? pick.gentlemans
              ? "Gentleman's agreement"
              : "Stage locked in"
            : turn
              ? `${turn.team.name} ${turn.verb.toLowerCase()}`
              : "",
        );
        HD.fit($(".header_status"));

        const card = (cls, key, stage, chip) => HD.html`
          <div class="card ${cls}" data-key="${key}">
            <div class="card_image" style="background-image: ${image(stage)}"></div>
            ${cls === "ban" && HD.html`<div class="strike_x"></div>`}
            ${chip}
            <div class="card_name fit"><div class="text">${stageName(stage)}</div></div>
          </div>`;

        const cards = state.bans.map(({ stage, team, reason }) =>
          card(
            "ban",
            `ban-${stage.codename}`,
            stage,
            team ? byChip("Banned by", team.name, team.color, true) : byChip("Banned", reason || "Ruleset", neutralColor),
          ),
        );
        // show-available: also the stages nobody struck yet, .out once a
        // stage is picked (.chosen for the pick itself, with MTF)
        const showAvailable = body("show-available");
        if (showAvailable) {
          for (const stage of state.available) {
            const status = !pick ? "" : stage.codename === pick.stage.codename ? "chosen" : "out";
            cards.push(card(`open ${status}`, `open-${stage.codename}`, stage, ""));
          }
        }
        renderItems(".bans", cards, { y: 24 });

        renderItems(
          ".pick",
          pick
            ? card(
                "picked",
                `pick-${pick.stage.codename}`,
                pick.stage,
                pick.team
                  ? byChip("Picked by", pick.team.name, pick.team.color, true)
                  : byChip("Picked", "Gentleman's", "var(--ssd-pick-color)"),
              )
            : HD.html`
              <div class="card picked pending" data-key="pick-pending">
                <div class="pending_mark">?</div>
                ${turn && byChip(turn.verb, turn.team.name, turn.team.color, true)}
                <div class="card_name fit"><div class="text">TBD</div></div>
              </div>`,
          { scale: 1.06 },
        );

        // pick-center: half the stage cards left of the pick, half right
        if (body("pick-center")) {
          const all = $(".bans .card");
          all.each((i, el) => $(el).addClass(i < Math.ceil(all.length / 2) ? "left" : "right"));
        }

        // The picked stage, blurred, behind the whole panel
        const behind = pick ? image(pick.stage) : "none";
        if (behind !== backdrop) {
          backdrop = behind;
          gsap.fromTo(
            ".backdrop",
            { autoAlpha: 0 },
            { autoAlpha: pick ? 1 : 0, duration: 0.6, onStart: () => $(".backdrop").css("background-image", behind) },
          );
        }

        setVisible(".ssd_panel", state.hasContent || (showAvailable && state.available.length > 0));
      });
    })(),
  };
})();
