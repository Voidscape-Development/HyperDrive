// Stage strike: every stage in play, stamped as struck (with who struck
// it), banned by the ruleset (DSR / MDSR) or picked. With the autohide page
// option, it fades out 5 seconds after a stage is picked.
let hideTimer = null;

// Stages the ruleset itself bans (DSR / MDSR)
const rulesetBans = (ruleset, strike) => {
  if (ruleset.useDSR) return strike.stagesPicked || [];
  if (ruleset.useMDSR && strike.lastWinner !== -1) {
    return strike.stagesWon && strike.stagesWon.length > 0 ? strike.stagesWon[(strike.lastWinner + 1) % 2] : [];
  }
  return [];
};

HD.layout({
  update(s) {
    if (!s.scoreChanged((score) => [score.stage_strike, score.team])) return;

    const ruleset = s.data.score.ruleset || {};
    const strike = s.score.stage_strike || {};
    // Team names in the widget's order (reversed when swapped)
    const names = s.teams.map((t) => t.name || `P${t.n}`);
    if (s.score.teamsSwapped) names.reverse();

    const stages = [...(ruleset.neutralStages || []), ...(strike.currGame > 0 ? ruleset.counterpickStages || [] : [])];
    const struck = Object.values(strike.strikedStages || {}).flat();
    const banned = rulesetBans(ruleset, strike);
    const strikedBy = strike.strikedBy || [[], []];

    HD.render(
      ".container",
      stages.map((stage) => {
        const code = stage.codename;
        const isStruck = struck.includes(code);
        const isBanned = banned.includes(code);
        const picked = strike.selectedStage && strike.selectedStage === code;
        const by = isStruck && (strikedBy[0].includes(code) ? names[0] : strikedBy[1].includes(code) ? names[1] : null);
        const label = (text) => HD.html`<div class="banned-by-name"><div class="text">${text}</div></div>`;
        return HD.html`
          <div class="stage-container ${(isStruck || isBanned) && "striked"} ${picked && "selected"}">
            <div class="stage-icon" style="background-image: url('${HD.asset(stage.path)}')">
              ${isStruck && HD.html`<div class="stage-striked stamp"></div>`}
              ${isBanned && HD.html`<div class="stage-dsr stamp"></div>`}
              ${picked && HD.html`<div class="${strike.gentlemans ? "stage-selected-gentlemans" : "stage-selected"} stamp"></div>`}
            </div>
            <div class="stage-name"><div class="text">${stage.name}</div></div>
            ${by && label(by)}
            ${picked && label(strike.gentlemans ? "Gentlemans" : names[strike.currPlayer])}
          </div>`;
      }),
    );
    HD.fit($(".container").find(".stage-name, .banned-by-name"));

    // Autohide: fades out once a stage is picked, back in for the next game
    clearTimeout(hideTimer);
    if (s.settings.autohide && strike.selectedStage && !_.get(s.old, ["score", s.n, "stage_strike", "selectedStage"])) {
      hideTimer = setTimeout(() => gsap.to(".container", { autoAlpha: 0 }), 5000);
    }
    if (!strike.selectedStage) gsap.to(".container", { autoAlpha: 1, overwrite: true });
  },
});
