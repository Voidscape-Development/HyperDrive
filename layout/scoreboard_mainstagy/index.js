// Mainstage-style scoreboard: drops down, then each side slides out with its
// name, score and losers badge. The flag and sponsor logo, and the match
// and best of, take turns every 10 seconds.
const rotate = (s) => {
  for (const { n, player } of s.teams) {
    const logo = turns.pick([player.sponsor_logo, player.country && player.country.asset]);
    HD.set(`.p${n}.container .flagcountry`, HD.img(HD.asset(logo), "class='flag'"));
  }
  const text = turns.pick([s.score.match, s.score.best_of && s.score.best_of_text]);
  $(".tournament_container").toggleClass("hidden", !text).toggleClass("unhidden", !!text);
  if (text) s.set(".match", text);
};
const turns = HD.turns(10, rotate);

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    const vars = { duration: 0.65, ease: "power2.Out" };
    const inner = 255; // .inner_container's width
    const losers = 295;
    tl.from(".anim_container_outer", { ...vars, duration: 0.5, y: -130 }, 1)
      .from(".p1 .inner_container", { ...vars, x: inner }, "<50%")
      .from(".p2 .inner_container", { ...vars, x: -inner }, "<")
      .from(".p1 .sponsor_container", { ...vars, x: -inner }, "<")
      .from(".p2 .sponsor_container", { ...vars, x: inner }, "<")
      .from(".p1 .name_container", { ...vars, x: inner }, "<50%")
      .from(".p2 .name_container", { ...vars, x: -inner }, "<")
      .from(".p1 .flags_container", { ...vars, x: inner }, "<")
      .from(".p2 .flags_container", { ...vars, x: -inner }, "<")
      .from(".p1 .losers_container", { ...vars, x: losers }, "<")
      .from(".p2 .losers_container", { ...vars, x: -losers }, "<");
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      if (!team.player || !team.player[1]) continue;
      $(t.sel(".losers_container")).toggleClass("unhidden", !!team.losers).toggleClass("hidden", !team.losers);
      t.set("&.container .name", HD.ui.name(player));
      t.set(".losers_container", team.losers && HD.html`<span class='losers'>[L]</span>`);
      t.set(".score", team.score);
      t.set(
        ".sponsor_container",
        HD.html`<div class='sponsor_logo' style="background-image: url('${HD.asset(player.sponsor_logo)}')"></div>`,
      );
    }
    HD.teamColors(s, ["score-bg-color"]);
    rotate(s);
  },
});
