// Rivals of Aether II scoreboard: each side's name, losers badge, chips
// (seed, Twitter, pronouns, flags), avatar, score and character art
// (mirrored on the right), or a doubles team's name and its players
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    HD.classIntro(tl);
  },

  update(s) {
    const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;

    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team's name, its players' names under it
      const solo = s.isTeams ? {} : player;

      t.set(
        "&.container .name",
        s.isTeams ? t.name : HD.html`<span class="sponsor">${player.team}</span>${player.name}`,
      );
      t.set("&.losers_container", team.losers && HD.html`<div class='losers container'>L</div>`);
      t.set(".flagcountry", HD.ui.flag(solo.country));
      t.set(".flagstate", HD.ui.flag(solo.state));
      t.set("&.container .sponsor_icon", background(HD.asset(solo.sponsor_logo)));
      t.set("&.container .avatar", background(HD.asset(solo.avatar)));
      t.set("&.container .online_avatar", background(solo.online_avatar));
      t.set(
        ".twitter",
        s.isTeams ? t.name !== HD.playerNames(team) && HD.playerNames(team) : HD.ui.chip("twitter", player.twitter),
      );
      t.set(".pronoun", HD.ui.chip("pronoun", solo.pronoun));
      t.set(".seed", HD.ui.chip("seed", solo.seed, "Seed "));
      t.set("&.container .score", team.score);
      t.set("&.floating_score", team.score);
      t.set("&.container .sponsor-container", !s.isTeams && HD.ui.sponsorLogo(player.sponsor_logo));
      s.characters(t.sel("&.container .character_container"), {
        source: ["score", s.n, "team", t.n],
        flip_x: t.n === 2,
        slice_character: s.isTeams ? [0, 1] : undefined,
      });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".event_name", s.data.tournamentInfo.eventName);
    s.set(".match", s.score.match);
    s.set(".phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
  },
});
