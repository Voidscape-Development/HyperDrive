// A team's characters in a line, or one player's (page options team and
// player); the _vertical pages stack them
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  update(s) {
    const { team, player } = s.settings;
    s.characters(".container", {
      source: ["score", s.n, "team", team, ...(player != null ? ["player", player] : [])],
    });
  },
});
