// VGBootcamp waiting screen: the two sides' names and score around the
// game screen
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    tl.from(".logo", { duration: 0.5, autoAlpha: 0, ease: "power2.inOut" }, 0.5)
      .from(".anim_container_outer", { duration: 1, width: 0, ease: "power2.inOut" }, 1)
      .from(".p1.twitter", { duration: 0.75, x: -373, ease: "power4.Out" }, "<25%")
      .from(".p2.twitter", { duration: 0.75, x: 373, ease: "power4.Out" }, "<")
      .from(".tournament_container", { duration: 0.75, x: -373, ease: "power4.Out" }, "<")
      .from(".tournament_logo", { opacity: 0, duration: 0.5, ease: "power4.Out" }, "<");
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      if (!team.player || !team.player[1]) continue;
      const losers = team.losers && "(L)";
      t.set("&.container .name", s.isTeams ? HD.text([t.name, losers]) : HD.html`${HD.ui.name(player)} ${losers}`);
      t.set("&.score", team.score);
    }
    HD.teamColors(s, ["score-bg-color"]);
  },
});
