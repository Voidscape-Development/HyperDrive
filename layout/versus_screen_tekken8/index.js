// Tekken 8 versus screen: each side's name, chips and character art
// building up slowly to the VS, the stage and its name, and the phase and
// best of on one line
const slide = (way) => ({
  out: { x: `${-way * 100}%`, stagger: 0.1 },
  in: { x: 0, duration: 1, ease: "expo.out", autoAlpha: 1, stagger: 0.2 },
});

const unskew = (content) => content && HD.html`<div class="unskew">${content}</div>`;
const place = (p) =>
  p &&
  p.asset &&
  unskew(HD.html`<img class='flagimage' src='${HD.asset(p.asset)}' /><div class="flagname">${p.name}</div>`);

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    const out = "power2.out";
    tl.to(".logo", { duration: 0.8, top: 160, scale: 0.4 }, 0);
    // Character names drift in, then the art slams in and drifts too
    for (const [n, way] of [
      [1, -1],
      [2, 1],
    ]) {
      tl.fromTo(
        `.p${n}.character_name`,
        { x: 100 * way, autoAlpha: 0 },
        { x: 60 * way, autoAlpha: 1, duration: 2, ease: out },
        0,
      )
        .to(`.p${n}.character_name`, { duration: 0.2, x: 20 * way, scale: 1.1, ease: out }, 2)
        .to(`.p${n}.character_name`, { duration: 2, x: 0, ease: out }, 2.2)
        .fromTo(
          `.p${n}.character`,
          { x: 1000 * way, autoAlpha: 0 },
          { x: 50 * way, autoAlpha: 1, duration: 0.2, ease: out },
          2,
        )
        .to(`.p${n}.character`, { x: 0, duration: 4, ease: "power1.out" }, 2.2);
    }
    const fade = (duration) => ({ duration, opacity: 0, ease: "power2.inOut" });
    tl.from(".tournament", fade(0.6), 0.2)
      .from(".match", fade(0.6), 0.4)
      .from(".phase_best_of", fade(0.6), 0.6)
      .from(".score_container", fade(0.8), 0)
      .from(".best_of.container", fade(0.8), 0)
      .fromTo(".vs1", { opacity: 0, scale: 1.2 }, { opacity: 0.8, ease: "in", duration: 2.1 }, 0)
      .to(".vs1", { duration: 0.03, opacity: 1, scale: 1 }, 2.1)
      .from(".vs2", { duration: 0.01, opacity: 0 }, 2.13)
      .to(".vs2", { opacity: 0, scale: 1.2, ease: out, duration: 1 }, 2.4);
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team's name, its players' under it
      const solo = s.isTeams ? {} : player;
      const names = HD.playerNames(team);

      t.set(
        ".name",
        s.isTeams
          ? t.name
          : HD.html`${player.team && HD.html`<span class="sponsor">${player.team}</span>`}${player.name}${
              team.losers && HD.html`<span class='losers'>L</span>`
            }`,
      );
      t.set(".real_name", s.isTeams ? t.name !== names && names : player.real_name);
      t.set(".pronoun", solo.pronoun);
      t.set("&.sponsor_logo", HD.img(HD.asset(solo.sponsor_logo), "class='sponsor-logo'"));
      const seed = s.isTeams ? t.players[0] && t.players[0].seed : player.seed;
      t.set(".seed", seed ? unskew(`Seed ${seed}`) : "");
      t.set(".twitter", solo.twitter && HD.html`<div class="twitter_logo"></div> ${solo.twitter}`);
      t.set(".country", place(solo.country));
      t.set(".state", place(solo.state));
      t.set("&.score", team.score);

      // Smaller the more characters there are
      const players = s.isTeams ? t.players : [player];
      const count = players.reduce((n, p) => n + _.size(p.character), 0);
      t.set(
        "&.character_name",
        !s.settings.avatar && VS.characterNames(players, !s.isTeams && s.settings.force_variant_last),
      );
      $(t.sel("&.character_name")).css("font-size", `${500 / Math.max(count, 1)}px`);

      if (s.settings.avatar) {
        VS.art(s, { ...t, sel: () => t.sel("&.character > div") }, slide(t.n === 1 ? 1 : -1));
      } else {
        s.characters(t.sel("&.character > div"), {
          source: ["score", s.n, "team", t.n],
          scale_based_on_parent: true,
          custom_center: [0.4, 0.4],
          ...slide(t.n === 1 ? 1 : -1),
        });
      }
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament", s.data.tournamentInfo.tournamentName);
    s.set(".match", s.score.match);
    VS.stage(s, { from: 2, duration: 0.8 });
    const stage = HD.stage(s.data, s.score);
    s.set(".stage_name", stage && HD.html`<div class="title">STAGE</div><div class="name">${stage.name}</div>`);
    s.set(".phase_best_of", HD.text([s.score.phase, s.score.best_of_text], " | "));
  },
});
