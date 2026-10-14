// Dynamic scoreboard: each side's name, chips (seed, Twitter, pronouns,
// flags), avatar, score and character icon, or a doubles team's name and
// its players
HD.layout({
  intro(tl) {
    HD.classIntro(tl);
  },

  update(s) {
    const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;

    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team's name, its players' names under it
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;

      t.set("&.container .name", s.isTeams ? HD.html`${t.name}${losers}` : HD.ui.name(player, team));
      t.set(".flagcountry", HD.ui.flag(solo.country));
      t.set(".flagstate", HD.ui.flag(solo.state));
      t.set("&.container .sponsor_icon", background(HD.asset(solo.sponsor_logo)));
      t.set("&.container .avatar", background(HD.asset(solo.avatar)));
      t.set("&.container .online_avatar", background(solo.online_avatar));
      t.set(".twitter", s.isTeams ? team.teamName && HD.playerNames(team) : HD.ui.chip("twitter", player.twitter));
      t.set(".pronoun", solo.pronoun);
      t.set(".seed", solo.seed ? `Seed ${solo.seed}` : "");
      t.set("&.container .score", team.score);
      t.set("&.container .sponsor-container", !s.isTeams && HD.ui.sponsorLogo(player.sponsor_logo));
      s.characters(t.sel("&.container .character_container"), {
        asset_key: "base_files/icon",
        source: ["score", s.n, "team", t.n],
        slice_character: s.isTeams ? [0, 1] : undefined,
        scale_fill_x: true,
        scale_fill_y: true,
        custom_zoom: 1,
      });

      // SF6 online hides the chips when there's nothing in them
      if (!s.isTeams && $(".sf6.online").length > 0) {
        gsap.to(t.sel("&.chips"), { autoAlpha: player.twitter || player.pronoun ? 1 : 0 });
      }
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".match", s.score.match);
    s.set(".phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
  },
});
