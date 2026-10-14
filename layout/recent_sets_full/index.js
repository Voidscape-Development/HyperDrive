// The two players (names over the list) and their last sets against each
// other (up to 5): the score, their characters, the tournament and date,
// the event, phase and round
const DATE = { month: "short", day: "2-digit", year: "numeric" };

const setRow = (set, i) => HD.html`
  <div class="set_container set_${i}">
    <div class="${set.winner == 0 ? "set_winner" : "set_loser"}">${set.score[0]}</div>
    <div class="p1_char"></div>
    <div class="set_info">
      <div class="set_col col_1"><div class="set_text"></div><div class="set_subtext"></div></div>
      <div class="set_col col_2"><div class="set_text"></div><div class="set_subtext"></div></div>
    </div>
    <div class="p2_char"></div>
    <div class="${set.winner == 1 ? "set_winner" : "set_loser"}">${set.score[1]}</div>
  </div>`;

HD.layout({
  intro(tl) {
    tl.from(".recent_sets", { autoAlpha: 0 });
  },

  update(s) {
    HD.teamColors(s, ["score-bg-color"]);
    for (const { n, player } of s.teams) {
      HD.set(`.recent_sets_players .player_${n} .sponsor`, player.team);
      HD.set(`.recent_sets_players .player_${n} .name`, player.name);
    }

    const recent = s.score.recent_sets || {};
    const sets = (recent.sets || []).slice(0, 5);
    const loading = recent.state === "loading";
    HD.build(".recent_sets_content", [loading, sets], () =>
      loading
        ? HD.html`<div class="lds-ring"><div></div><div></div><div></div><div></div></div>`
        : sets.length
          ? HD.html`<div class="recent_sets_inner">${sets.map(setRow)}</div>`
          : "No sets found",
    );
    if (loading) return;

    sets.forEach((set, i) => {
      const row = `.set_${i}`;
      HD.set(`${row} .col_1 .set_text`, HD.html`${set.online && HD.html`<div class="wifi_icon"></div>`}${set.tournament}`);
      HD.set(`${row} .col_1 .set_subtext`, new Date(set.timestamp * 1000).toLocaleDateString("en-US", DATE));
      HD.set(`${row} .col_2 .set_text`, `${set.event} - ${set.phase_id}${set.phase_name}`);
      HD.set(`${row} .col_2 .set_subtext`, set.round);
      for (const side of ["p1_char", "p2_char"]) {
        s.characters(`${row} .${side}`, { source: ["score", s.n, "recent_sets", "sets", i, side] });
      }
    });
  },
});
