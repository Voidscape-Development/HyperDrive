// VGBootcamp classic scoreboard: each side's name, flag, sponsor and score.
// A player's Twitter and pronouns, and the match and best of, take turns
// every 9 seconds.
const rotate = (s) => {
  for (const t of s.teams) {
    const { player } = t;
    const shown = !s.isTeams && (player.twitter || player.pronoun);
    $(t.sel("&.twitter")).toggleClass("hidden", !shown).toggleClass("unhidden", !!shown);
    t.set("&.twitter", turns.pick([HD.ui.chip("twitter", player.twitter, "@"), player.pronoun]));
  }
  const text = turns.pick([s.score.match, s.score.best_of && s.score.best_of_text]);
  $(".tournament_container").toggleClass("hidden", !text).toggleClass("unhidden", !!text);
  if (text) s.set(".match", text);
};
const turns = HD.turns(9, rotate);

HD.layout({
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
      // Doubles show the team's name, and none of the player's info
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && "(L)";

      t.set(
        "&.container .name",
        s.isTeams ? HD.html`<span>${HD.text([t.name, losers])}</span>` : HD.html`${HD.ui.name(player)} ${losers}`,
      );
      t.set("&.container .flagcountry", solo.country && HD.img(HD.asset(solo.country.asset), "class='flag'"));
      t.set(".sponsor-container", solo.sponsor_logo && HD.ui.sponsorLogo(solo.sponsor_logo));
      t.set("&.score", team.score);
    }
    HD.teamColors(s, ["score-bg-color"]);
    rotate(s);
  },
});
