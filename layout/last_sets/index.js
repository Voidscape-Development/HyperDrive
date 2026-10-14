// A player's last 3 sets in the event (page option player: 1 or 2), oldest
// first along a bracket line: each with its round, both players' names,
// scores and characters
const setCard = (set, i, player) => {
  const won = set.player_score > set.oponent_score;
  const side = (n, result) => HD.html`
    <div class="p${n} color${(player == 1) === (n === 1) ? 1 : 2} ${result}">
      <div class="character_icon"></div>
      <div class="name"></div>
      <div class="score"></div>
    </div>`;
  return HD.html`
    <div class="set${i + 1} set_container">
      <div class="info"><div class="phase"></div><div class="match"></div></div>
      ${side(1, won ? "winner" : "loser")}
      ${side(2, won ? "loser" : "winner")}
    </div>`;
};

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  settings: { player: 1 },

  intro(tl) {
    $(".set_container").each((i, el) => tl.from(el, { x: -100, autoAlpha: 0, duration: 0.4 }, 0.2 + 0.2 * i));
    tl.fromTo(".bracket_line", { width: 0 }, { width: "calc(100% + 240px)", duration: 1, ease: "Power2.easeOut" }, 0);
  },

  update(s) {
    const player = s.settings.player;
    const path = ["score", s.n, "last_sets", player];
    const sets = Object.entries(_.get(s.data, path) || {})
      .slice(0, 3)
      .reverse();

    const built = HD.build(".player1_content", sets, () => [
      sets.map(([, set], i) => setCard(set, i, player)),
      sets.length > 0 && HD.html`<div class="bracket_line"><div class="line_arrow"></div></div>`,
    ]);

    sets.forEach(([key, set], i) => {
      const card = `.player1_content .set${i + 1}`;
      HD.set(`${card} .phase`, HD.text([set.phase_name, set.phase_id]));
      HD.set(`${card} .match`, set.round_name);
      HD.set(`${card} .p1 .name`, HD.html`<span class="sponsor">${set.player_team}</span>${set.player_name}`);
      HD.set(`${card} .p1 .score`, set.player_score);
      HD.set(`${card} .p2 .name`, HD.html`<span class="sponsor">${set.oponent_team}</span>${set.oponent_name}`);
      HD.set(`${card} .p2 .score`, set.oponent_score);
      s.characters(`${card} .p1 .character_icon`, { source: [...path, key, "player_char"] });
      s.characters(`${card} .p2 .character_icon`, { source: [...path, key, "oponent_char"] });
    });

    // New sets slide in again
    if (built && !s.first) HD.restart();
  },
});
