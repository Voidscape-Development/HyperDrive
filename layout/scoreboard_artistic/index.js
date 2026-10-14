// Artistic scoreboard: each side's name and pronouns, flags, avatar, score
// and character art sliding toward the middle (mirrored on the right)
HD.layout({
  intro(tl) {
    const ease = "power2.inOut";
    tl.from(".logo", { duration: 0.5, autoAlpha: 0, ease }, 0.5)
      .from(".floating .anim_container_outer", { duration: 1, width: 0, ease }, 1)
      .from(".floating .base_container_outer", { duration: 1, width: 0, ease }, 1);
  },

  update(s) {
    const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;
    const flag = (place) =>
      place &&
      place.asset &&
      HD.html`<div class='flag_container'>${HD.ui.flag(place, "flagname")}</div>`;

    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team's name (and its players under it), and only
      // the first player's Twitter
      const solo = s.isTeams ? {} : player;
      if (s.isTeams) {
        t.set(
          "&.container .name_twitter",
          HD.html`<div class="name">${t.name}</div>${
            team.teamName && HD.html`<div class="team-members">${HD.playerNames(team)}</div>`
          }`,
        );
      } else {
        const name = HD.html`<span class="sponsor">${player.team}</span><div class="name">${player.name}</div>`;
        const pronoun = HD.html`<div class="pronoun">${player.pronoun}</div>`;
        // Pronouns on the outer side
        t.set("&.container .name_twitter", t.n === 1 ? HD.html`${name}${pronoun}` : HD.html`${pronoun}${name}`);
      }
      t.set("&.container .losers", team.losers ? "losers" : "");
      t.set("&.container .flagcountry", flag(solo.country));
      t.set("&.container .flagstate", flag(solo.state));
      t.set("&.container .sponsor_icon", background(HD.asset(solo.sponsor_logo)));
      t.set("&.container .avatar", background(HD.asset(solo.avatar)));
      t.set("&.container .online_avatar", background(solo.online_avatar));
      t.set("&.container .twitter", HD.ui.chip("twitter", player.twitter));
      t.set("&.container .score", team.score);
      t.set("&.container .sponsor-container", HD.ui.sponsorLogo(player.sponsor_logo));
      s.characters(t.sel("&.character_container"), {
        source: ["score", s.n, "team", t.n],
        flip_x: t.n === 2,
        ...HD.slideToMiddle(t.n === 1 ? 1 : -1),
      });
    }
    HD.teamColors(s);

    s.set(".tournament_name", `${s.data.tournamentInfo.tournamentName} - ${s.data.tournamentInfo.eventName}`);
    s.set(".phase", s.score.phase);
    s.set(".match", s.score.match);
    s.set(".best_of", s.score.best_of_text);
  },
});
