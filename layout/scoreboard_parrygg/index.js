// parry.gg scoreboard: each side's name, chips and character art behind
// it, and the tournament (with its short link, when there's room), match
// and best of
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
        { delay: 0.1, duration: 1, x: (i) => out(i) * 100, autoAlpha: 0, ease },
        0.2,
      )
      .from([".p1 .name", ".p2 .name"], { delay: 0.3, duration: 0.8, x: (i) => out(i) * 200, autoAlpha: 0, ease }, 0.2)
      .from(".info_container", { duration: 0.8, x: -50, autoAlpha: 0, ease }, 0)
      .from(".parrygg_logo", { duration: 0.6, scale: 0, rotation: -90, autoAlpha: 0, ease: "back.out(1.5)" }, 0.3)
      .from(".info > div", { duration: 0.6, x: -20, autoAlpha: 0, stagger: 0.1, ease }, 0.4);
  },

  update(s) {
    // The short link's path ("/my-tournament"), when there's room for it
    const link = s.data.tournamentInfo.shortLink;
    let path = "";
    if (link) {
      try {
        path = new URL(link).pathname;
      } catch (e) {
        path = link.startsWith("/") ? link : `/${link}`;
      }
    }
    const name = s.data.tournamentInfo.tournamentName;
    const full = HD.text([name, path, s.score.phase], " ⬣ ");
    s.set(".tournament_name", full.length > 50 ? HD.text([name, s.score.phase], " ⬣ ") : full);
    s.set(".info_container .match", s.score.match);
    s.set(".info_container .best_of", s.score.best_of_text);
    $(".p1.container, .p2.container").toggleClass("doubles", s.isTeams);

    const slash = HD.html`<span class="slash">/</span>`;
    for (const t of s.teams) {
      const { team, player } = t;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;
      const names = t.players.map((p) => p.name).filter(Boolean);
      t.set(
        ".name",
        s.isTeams
          ? HD.html`${team.teamName ? HD.join(team.teamName.split(/\s*\/\s*/), slash) : HD.join(names, HD.html` ${slash} `)}${losers}`
          : HD.ui.name(player, team),
      );
      if (!s.isTeams) {
        t.set(".twitter", HD.ui.chip("twitter", player.twitter));
        t.set(".pronoun", HD.ui.chip("pronoun", player.pronoun));
        t.set(".seed", HD.ui.chip("seed", player.seed, "Seed "));
      }
      t.set(".score", team.score);
      s.characters(t.sel(".character_bg"), {
        source: ["score", s.n, "team", t.n],
        flip_x: t.n === 2,
        slice_character: s.isTeams ? [0, 1] : undefined,
      });
    }
  },
});
