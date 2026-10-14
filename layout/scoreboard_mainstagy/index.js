// Mainstage-style scoreboard: drops down, then each side slides out with its
// name (uppercase), score and losers badge. The flag and sponsor logo, and
// the match and best of, take turns every 10 seconds.
let turn = 0;

const rotate = (s) => {
  for (const { n, player } of s.teams) {
    const logos = [player.sponsor_logo, player.country && player.country.asset].filter(Boolean);
    HD.set(`.p${n}.container .flagcountry`, HD.img(HD.asset(logos[turn % logos.length]), "class='flag'"));
  }
  const texts = [s.score.match, s.score.best_of && s.score.best_of_text].filter(Boolean);
  $(".tournament_container").toggleClass("hidden", texts.length === 0).toggleClass("unhidden", texts.length > 0);
  if (texts.length) s.set(".match", texts[turn % texts.length].toUpperCase());
};

HD.layout({
  init() {
    HD.every(10, (s) => {
      turn += 1;
      rotate(s);
    });
  },

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
    const upper = (text) => String(text || "").toUpperCase();
    for (const t of s.teams) {
      const { team, player } = t;
      if (!team.player || !team.player[1]) continue;
      $(t.sel(".losers_container")).toggleClass("unhidden", !!team.losers).toggleClass("hidden", !team.losers);
      t.set("&.container .name", HD.html`<span class="sponsor">${upper(player.team)}</span>${upper(player.name)}`);
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
