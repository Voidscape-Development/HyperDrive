// The standard versus screen, with each player's controller and the game
// being played, and an intro of its own
HD.layout({
  ...HD.layouts.versus,

  intro(tl) {
    tl.from(".info_bottom .phase", { duration: 0.8, opacity: 0, ease: "power2.inOut" }, 0)
      .from(".match", { duration: 0.8, opacity: 0, ease: "power2.inOut" }, 0)
      // The tournament box slides down from above the top edge
      .from(".info_top", { duration: 0.8, y: -60, opacity: 0, ease: "power2.out" }, 0)
      .from(".vs", { duration: 0.4, opacity: 0, scale: 4, ease: "out" }, 0.5)
      // The game number pops in as the VS lands, the best of drops out
      // from under it just after
      .from(".game_number", { duration: 0.35, opacity: 0, scale: 1.8, ease: "back.out(2)" }, 0.8)
      .from(".info_best_of .best_of", { duration: 0.4, opacity: 0, y: -30, ease: "back.out(2)" }, 0.9)
      .from(".p1.container", { duration: 1, x: -100, ease: "out" }, 0)
      .from(".p2.container", { duration: 1, x: 100, ease: "out" }, 0);
  },

  update(s) {
    HD.layouts.versus.update(s);
    if (!s.isTeams) s.teams.forEach(VS.controller);
    s.set(".container .game_number", `Game ${VS.gameNumber(s)}`);
  },
});
