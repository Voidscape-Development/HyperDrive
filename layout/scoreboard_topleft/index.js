// Top-left scoreboard: the tournament, then each side's name, pronouns,
// flags, avatar, score and character (portraits on index_portraits.html)
HD.layout({
  intro(tl) {
    const ease = "power2.inOut";
    tl.from(".logo", { duration: 0.5, autoAlpha: 0, ease }, 0.5)
      .from(".anim_container_outer", { duration: 1, width: 0, ease }, 1)
      .from(".base_container_outer", { duration: 1, width: 0, ease }, 1)
      .from([".fgc .top", ".fgc .player"], { duration: 1, y: -100, ease }, 0)
      .from(".fgc:not(.bblue) .bottom", { duration: 1, y: 100, ease }, 0)
      .from(".fgc.bblue .bottom", { duration: 1, autoAlpha: 0, ease }, 0.2);
  },

  update(s) {
    const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;
    const flag = (place) => place && place.asset && HD.html`<img class='flag' src='${HD.asset(place.asset)}' />`;

    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team's name, and only the first player's Twitter
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;

      t.set(
        "&.container .name",
        s.isTeams
          ? HD.html`${t.name} ${losers}`
          : HD.html`<span class="sponsor">${player.team}</span>${player.name} <span class="pronoun">${player.pronoun}</span> ${losers}`,
      );
      t.set("&.container .flagcountry", flag(solo.country));
      t.set("&.container .flagstate", flag(solo.state));
      t.set("&.container .sponsor_icon", background(HD.asset(solo.sponsor_logo)));
      t.set("&.container .avatar", background(HD.asset(solo.avatar)));
      t.set("&.container .online_avatar", background(solo.online_avatar));
      t.set("&.container .twitter", HD.ui.chip("twitter", player.twitter));
      t.set("&.container .score", team.score);
      t.set("&.container .sponsor-container", HD.ui.sponsorLogo(player.sponsor_logo));
      s.characters(t.sel("&.container .character_container"), {
        source: ["score", s.n, "team", t.n],
        scale_based_on_parent: !s.isTeams && !!s.settings.portraits,
        slice_character: s.isTeams ? [0, 1] : undefined,
      });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".event_name", s.data.tournamentInfo.eventName);
    s.set(".phase", s.score.phase);
    s.set(".match", s.score.match);
    s.set(".best_of", s.score.best_of_text);
  },
});
