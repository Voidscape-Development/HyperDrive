// The ruleset: its neutral and counterpick stages, and its rules (DSR,
// strike order, bans)
const stageList = (stages) =>
  stages.map(
    (stage) => HD.html`
      <div class="stage-container">
        <div class="stage-icon" style="background-image: url('${HD.asset(stage.path)}')"></div>
        <div class="stage-name"><div class="text">${stage.name}</div></div>
      </div>`,
  );

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  update(s) {
    const ruleset = s.data.score.ruleset;
    if (!ruleset || !s.changed("score.ruleset")) return;

    HD.render(".neutral", stageList(ruleset.neutralStages));
    HD.render(".counterpick", stageList(ruleset.counterpickStages));
    HD.fit($(".stage-name"));
    $(".counterpick_stages").css("display", ruleset.counterpickStages.length ? "" : "none");

    const rules = [
      ruleset.useDSR && "DSR: You cannot counterpick to any stage you previously won on during the set.",
      ruleset.useMDSR && "MDSR: You cannot counterpick to the last stage you won on during the set.",
      ruleset.strikeOrder ? `First match strike order: ${ruleset.strikeOrder.map((p) => `P${p}`).join(", ")}` : "",
      ruleset.banCount ? `After each match, winner bans ${ruleset.banCount} stages` : "",
    ];
    HD.render(".rules", HD.join(rules, HD.html`<br/>`));
    $(".title.ruleset").text(ruleset.name);
  },
});
