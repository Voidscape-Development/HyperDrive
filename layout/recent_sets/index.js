// The two players' last sets against each other (up to 5): the score,
// their characters, the tournament and its date
const DATE = { month: "short", day: "2-digit", year: "numeric" };

const setRow = (set, i) => HD.html`
  <div class="set_container set_${i}">
    <div class="${set.winner == 0 ? "set_winner" : "set_loser"}">${set.score[0]}</div>
    <div class="p1_char"></div>
    <div class="set_info">
      <div class="set_title">${set.online && HD.html`<div class="wifi_icon"></div>`} ${set.tournament}</div>
      <div class="set_date">${new Date(set.timestamp * 1000).toLocaleDateString("en-US", DATE)}</div>
    </div>
    <div class="p2_char"></div>
    <div class="${set.winner == 1 ? "set_winner" : "set_loser"}">${set.score[1]}</div>
  </div>`;

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    tl.from(".recent_sets", { autoAlpha: 0 });
  },

  update(s) {
    HD.teamColors(s, ["score-bg-color"]);

    const recent = s.score.recent_sets || {};
    const sets = (recent.sets || []).slice(0, 5);
    const loading = recent.state === "loading";
    HD.build(".recent_sets_content", [loading, sets], () =>
      loading
        ? HD.html`<div class="lds-ring"><div></div><div></div><div></div><div></div></div>`
        : sets.length
          ? sets.map(setRow)
          : "No sets found",
    );
    if (loading) return;
    sets.forEach((_set, i) => {
      for (const side of ["p1_char", "p2_char"]) {
        s.characters(`.set_${i} .${side}`, { source: ["score", s.n, "recent_sets", "sets", i, side] });
      }
    });
  },
});
