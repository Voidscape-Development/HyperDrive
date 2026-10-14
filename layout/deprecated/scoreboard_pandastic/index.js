// Pandastic scoreboard: each side's name with pronouns (on the outer side),
// flags, sponsor, avatar, Twitter, score and character
const flag = (place) => place && place.asset && HD.html`<div class='flag' style="background-image: url('${HD.asset(place.asset)}')"></div>`;
const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;

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
    for (const t of s.teams) {
      const { team, player } = t;
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;
      const pronoun = HD.html`<span class="pronoun">${player.pronoun}</span>`;

      t.set(
        "&.container .name",
        s.isTeams
          ? HD.html`${t.name} ${losers}`
          : HD.html`${t.n === 2 && pronoun}<span class="sponsor">${player.team}</span> ${player.name} ${t.n === 1 && pronoun}${losers}`,
      );
      t.set("&.container .flagcountry", flag(solo.country));
      t.set("&.container .flagstate", flag(solo.state));
      t.set("&.container .sponsor_icon", background(HD.asset(solo.sponsor_logo)));
      t.set("&.container .avatar", background(HD.asset(solo.avatar)));
      t.set("&.container .online_avatar", background(solo.online_avatar));
      t.set("&.container .twitter", HD.ui.chip("twitter", player.twitter));
      t.set("&.container .score", team.score);
      t.set("&.container .sponsor-container", HD.ui.sponsorLogo(player.sponsor_logo));
      s.characters(t.sel("&.character_container"), { source: ["score", s.n, "team", t.n] });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament_name", `${s.data.tournamentInfo.tournamentName} - ${s.data.tournamentInfo.eventName}`);
    s.set(".phase", s.score.phase);
    s.set(".match", s.score.match);
    s.set(".best_of", s.score.best_of_text);
  },
});
