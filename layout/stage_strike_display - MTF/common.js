/* ═══════════════════════════════════════════════════════════
   STAGE STRIKE DISPLAY — common.js
   Shared data helpers for the minimal / full variants.
   Turns score.<n>.stage_strike + score.ruleset into an ordered
   list of bans and the picked stage, each tagged with who made
   the call, so each variant only has to worry about markup.
   ═══════════════════════════════════════════════════════════ */

function SSD_Escape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Team display names + colors, in the same order the stage strike
// widget uses for strikedBy / currPlayer (reversed when swapped)
function SSD_GetTeams(score) {
  let teams = [score.team["1"], score.team["2"]].map((team, t) => {
    let name = team.teamName;

    if (!name) {
      name = Object.values(team.player || {})
        .filter((player) => player && player.name)
        .map((player) => player.name)
        .join(" / ");
    }

    return {
      name: name || "P" + (t + 1),
      color:
        team.color && !tsh_settings["forceDefaultScoreColors"]
          ? team.color
          : `var(--p${t + 1}-score-bg-color)`,
    };
  });

  if (score.teamsSwapped == true) {
    teams.reverse();
  }

  return teams;
}

// Stages banned by the ruleset itself (DSR / MDSR), not by a player
function SSD_GetRulesetBans(ruleset, state) {
  if (ruleset.useDSR) {
    return state.stagesPicked || [];
  }
  if (ruleset.useMDSR && state.lastWinner !== -1) {
    return state.stagesWon && state.stagesWon.length > 0
      ? state.stagesWon[(state.lastWinner + 1) % 2]
      : [];
  }
  return [];
}

function SSD_GetState(data) {
  const score = data.score[window.scoreboardNumber];
  const ruleset = data.score.ruleset || {};
  const state = score.stage_strike || {};
  const teams = SSD_GetTeams(score);

  let stages = {};
  [...(ruleset.neutralStages || []), ...(ruleset.counterpickStages || [])].forEach(
    (stage) => (stages[stage.codename] = stage)
  );
  if (state.selectedStageData && !stages[state.selectedStageData.codename]) {
    stages[state.selectedStageData.codename] = state.selectedStageData;
  }

  const strikedBy = state.strikedBy || [[], []];
  let bans = [];
  let seen = new Set();

  // Ruleset bans happen before anyone strikes, so they go first
  SSD_GetRulesetBans(ruleset, state).forEach((codename) => {
    if (codename === state.selectedStage || seen.has(codename) || !stages[codename]) return;
    seen.add(codename);
    bans.push({ stage: stages[codename], team: null, reason: ruleset.useDSR ? "DSR" : "MDSR" });
  });

  // strikedStages is one array per strike step, so flattening keeps chronological order
  Object.values(state.strikedStages || []).flat().forEach((codename) => {
    if (seen.has(codename) || !stages[codename]) return;
    seen.add(codename);

    let t = strikedBy.findIndex((list) => list && list.includes(codename));
    bans.push({ stage: stages[codename], team: t === -1 ? null : teams[t], reason: null });
  });

  // Stages still in play: game 1 strikes from neutrals only, later games add counterpicks.
  // The picked stage stays in the list so cards keep their place once it's chosen.
  let pool = [...(ruleset.neutralStages || [])];
  if (state.currGame > 0) {
    pool = pool.concat(ruleset.counterpickStages || []);
  }
  const available = pool.filter((stage) => !seen.has(stage.codename));

  let pick = null;
  if (state.selectedStage && stages[state.selectedStage]) {
    pick = {
      stage: stages[state.selectedStage],
      team: state.gentlemans ? null : teams[state.currPlayer] || null,
      gentlemans: !!state.gentlemans,
    };
  }

  // Whose turn it is while the pick is still pending
  let turn = null;
  if (!pick && teams[state.currPlayer]) {
    let picking =
      state.currGame > 0
        ? state.currStep >= 1
        : state.currStep >= (ruleset.strikeOrder || []).length;

    let action = picking ? "pick" : state.currGame > 0 ? "ban" : "strike";
    turn = {
      team: teams[state.currPlayer],
      action,
      verb: { pick: "Picking", ban: "Banning", strike: "Striking" }[action],
    };
  }

  return {
    teams,
    bans,
    pick,
    turn,
    game: (state.currGame || 0) + 1,
    available,
    hasContent: bans.length > 0 || pick != null,
  };
}

// MTF pages tint panels from team colors, same as the MTF scoreboard:
// team 1 → --p1-score-bg-color (washes), team 2 → --p2-score-bg-color (accents)
function SSD_ApplyMtfColors(data) {
  if (!$("body").hasClass("mtf")) return;

  const score = data.score[window.scoreboardNumber];
  [1, 2].forEach((t) => {
    const team = score.team[String(t)];
    if (team && team.color && !tsh_settings["forceDefaultScoreColors"]) {
      document.querySelector(":root").style.setProperty(`--p${t}-score-bg-color`, team.color);
    }
  });
}

function SSD_StageImage(stage) {
  return stage.path ? `url('../../${stage.path}')` : "none";
}

function SSD_StageName(stage) {
  return SSD_Escape(stage.display_name || stage.name || stage.codename);
}

// Only re-render when something that affects the display changed
function SSD_HasChanged(data, oldData) {
  if (!oldData || !oldData.score) return true;

  const pick = (d) => {
    const score = d.score[window.scoreboardNumber] || {};
    return JSON.stringify([score.stage_strike, score.team, score.teamsSwapped, d.score.ruleset]);
  };
  return pick(data) != pick(oldData);
}

// Replace a container's content, animating in only the items
// (matched by data-key) that weren't there before
function SSD_Render(container, html, fromVars) {
  const $container = $(container);
  const previous = new Set(
    $container.find("[data-key]").map((i, el) => $(el).attr("data-key")).get()
  );

  $container.html(html);

  const added = $container
    .find("[data-key]")
    .filter((i, el) => !previous.has($(el).attr("data-key")))
    .get();

  if (added.length > 0) {
    gsap.from(added, { autoAlpha: 0, duration: 0.3, ease: "power2.out", stagger: 0.06, ...fromVars });
  }

  $container.find(".fit").each(function () {
    FitText($(this));
  });
}

// Slide the whole lower third in/out depending on whether there's anything to show
function SSD_SetVisible(panel, visible) {
  gsap.to(panel, {
    autoAlpha: visible ? 1 : 0,
    y: visible ? 0 : 40,
    duration: 0.35,
    ease: visible ? "power3.out" : "power2.in",
    overwrite: true,
  });
}
