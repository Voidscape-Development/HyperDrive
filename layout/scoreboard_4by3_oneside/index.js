// One-sided 4:3 scoreboard (parry.gg style): both sides in one column,
// each with its name, chips, location and character art behind
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    HD.classIntro(tl);
    const ease = "power2.out";
    const out = (i) => (i === 0 ? -1 : 1); // p1 from the left, p2 the right
    tl.from(".p1.container", { duration: 0.8, x: -150, autoAlpha: 0, ease }, 0)
      .from(".p2.container", { duration: 0.8, x: 150, autoAlpha: 0, ease }, 0)
      .from(
        [".p1 .character_bg", ".p2 .character_bg"],
        { duration: 0.8, x: (i) => out(i) * 200, autoAlpha: 0, ease },
        0.2,
      )
      .from(
        [".p1 .top-row", ".p2 .top-row"],
        { delay: 0.1, duration: 0.5, x: (i) => out(i) * 50, autoAlpha: 0, ease },
        0.2,
      )
      .from([".p1 .name", ".p2 .name"], { delay: 0.3, duration: 0.5, x: (i) => out(i) * 50, autoAlpha: 0, ease }, 0.2)
      .from(".info_container", { duration: 0.8, x: -50, autoAlpha: 0, ease }, 0)
      .from(".parrygg_logo", { duration: 0.6, scale: 0, rotation: -90, autoAlpha: 0, ease: "back.out(1.5)" }, 0.3)
      .from(".info > div", { duration: 0.6, x: -20, autoAlpha: 0, stagger: 0.1, ease }, 0.4);
  },

  update(s) {
    const info = s.data.tournamentInfo;
    s.set(".tournament_name", HD.text([info.tournamentName, info.eventName], " - "));
    s.set(".match", s.score.match);
    s.set(".phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
    $(".p1.container, .p2.container").toggleClass("doubles", s.isTeams);

    // Names with styled slashes between them
    const slash = HD.html`<span class="slash">/</span>`;

    for (const t of s.teams) {
      const { team, player } = t;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;
      const names = t.players.map((p) => p.name).filter(Boolean);
      const seed = (s.isTeams ? t.players[0] || {} : player).seed;
      const solo = s.isTeams ? {} : player;
      const location = solo.country && solo.country.code && HD.text([solo.country.code, solo.state.code], "/");

      t.set(
        ".team_name",
        s.isTeams
          ? HD.html`${HD.join(
              team.teamName ? team.teamName.split(/\s*\/\s*/) : names.map((n) => HD.html`<span>${n}</span>`),
              slash,
            )}${losers}`
          : HD.ui.name(player, team),
      );
      // A doubles team with a name lists its players under it
      t.set(
        ".team_members",
        s.isTeams &&
          team.teamName &&
          HD.join(
            names.map((n) => HD.html`<span>${n}</span>`),
            slash,
          ),
      );
      t.set(".seed", HD.ui.chip("seed", seed, "Seed "));
      t.set(".twitter", HD.ui.chip("twitter", solo.twitter));
      t.set(".pronoun", HD.ui.chip("pronoun", solo.pronoun));
      t.set(".location", HD.ui.chip("location", location, "", "location_icon"));
      t.set(".sponsor_icon", HD.img(HD.asset(s.isTeams ? team.logo : player.sponsor_logo)));
      t.set(".score", team.score);
      s.characters(t.sel(".character_bg"), {
        source: ["score", s.n, "team", t.n],
        slice_character: s.isTeams ? [0, 1] : undefined,
      });
    }
    HD.teamColors(s, ["score-bg-color"]);
  },
});
