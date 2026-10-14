// VGBootcamp-style scoreboard: each side's name, flag, sponsor, score and
// Twitter (singles only), and the tournament, match and phase
HD.layout({
  intro(tl) {
    tl.from(".logo", { duration: 0.5, autoAlpha: 0, ease: "power2.inOut" }, 0.5)
      .from(".anim_container_outer", { duration: 1, width: 0, ease: "power2.inOut" }, 1)
      .from(".p1.twitter", { duration: 0.75, x: -373, ease: "power4.Out" }, "<25%")
      .from(".p2.twitter", { duration: 0.75, x: 373, ease: "power4.Out" }, "<")
      .from(".tournament_container", { opacity: 0, duration: 0.5, ease: "power4.Out" }, "<80%")
      .from(".tournament_logo", { opacity: 0, duration: 0.5, ease: "power4.Out" }, "<");
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      if (!team.player || !team.player[1]) continue;
      // Doubles show the team's name, and none of the player's info
      const solo = s.isTeams ? {} : player;

      t.set("&.container .name", s.isTeams ? HD.text([t.name, team.losers && "(L)"]) : HD.ui.name(player));
      t.set(".losers_container", team.losers && HD.html`<span class='losers'>L</span>`);
      // Empty placeholders keep the bar's spacing
      t.set(
        "&.container .flagcountry",
        solo.country && solo.country.asset
          ? HD.img(HD.asset(solo.country.asset), "class='flag'")
          : HD.html`<div class='flag' style=''></div>`,
      );
      t.set(
        ".sponsor-container",
        solo.sponsor_logo ? HD.ui.sponsorLogo(solo.sponsor_logo) : HD.html`<div class='sponsor-logo' style=''></div>`,
      );
      $(t.sel("&.twitter")).toggleClass("hidden", !solo.twitter).toggleClass("unhidden", !!solo.twitter);
      t.set("&.twitter", HD.ui.chip("twitter", player.twitter, "@"));
      t.set("&.container .score", team.score);
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".match", s.score.match);
    s.set(".phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
  },
});
