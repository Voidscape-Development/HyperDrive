// Shared by the versus screens: building blocks (character names with their
// skins, character art or avatars, the info grid, the stage) and the
// standard versus screen, HD.layouts.versus, which the others build on.
//
// The avatar page option shows players' avatars instead of character art:
// HD.page({ avatar: "online" }) (their online avatar) or "player" (the one
// set in HyperDrive).
const VS = {
  // Character options that slide each side's art in from its edge
  slide: (way) => ({
    out: { x: `${way * -800}px`, z: "0px", stagger: 0.1 },
    in: { duration: 0.4, x: "0px", z: "-30px", ease: "in", autoAlpha: 1, stagger: 0.1 },
  }),

  // "Mario / Luigi", each with its skin's icon and name. With
  // force_variant_last, when only one character has a skin it goes at the
  // end instead.
  characterNames(players, forceLast) {
    const characters = players.flatMap((p) => Object.values(p.character || {}));
    const skinned = characters.filter((c) => c.variant && HD.ui.variant(c.variant));
    const last = forceLast && characters.length > 1 && skinned.length === 1 ? skinned[0].variant : null;
    const intercal = HD.html`<div class = "variant_intercal"></div>`;
    return HD.html`${HD.join(
      characters.map((c) => HD.join([c.name, !last && c.variant && HD.ui.variant(c.variant)], intercal)),
      " / ",
    )}${last && HD.ui.variant(last)}`;
  },

  // Pronouns, Twitter, seed and flags
  infoGrid: (p) => HD.html`${p.pronoun && HD.html`<div class="pronoun"><div class="pronoun_logo"></div>${p.pronoun}</div>`}${
    p.twitter && HD.html`<div class="twitter"><div class="twitter_logo"></div>${p.twitter}</div>`
  }${p.seed ? HD.html`<div class="seed"><div class="seed_logo"></div>Seed ${p.seed}</div>` : ""}${
    p.country && p.country.asset && HD.html`<div class="flagcountry">${HD.ui.flag(p.country, "flagname")}</div>`
  }${p.state && p.state.asset && HD.html`<div class="flagstate">${HD.ui.flag(p.state, "flagname")}</div>`}`,

  // A side's character art, or its players' avatars (the avatar option)
  art(s, t, options) {
    const sel = t.sel("&.character");
    const mode = s.settings.avatar;
    if (!mode) return s.characters(sel, { source: ["score", s.n, "team", t.n], scale_based_on_parent: true, ...options });
    const src = (p) => (mode === "online" ? p.online_avatar : HD.asset(p.avatar)) || "./person.svg";
    const players = s.isTeams ? t.players : [t.player];
    return HD.set(sel, HD.html`<div class="player_avatar">${players.map((p) => HD.img(src(p)))}</div>`, options);
  },

  // The stage picked, zooming in when it changes
  stage(s, { from = 1.6, to = 1.2, duration = 0.6 } = {}) {
    const stage = HD.stage(s.data, s.score);
    if (stage && s.scoreChanged("stage_strike.selectedStage")) {
      gsap.fromTo(".stage", { scale: from }, { scale: to, duration, ease: "power2.out" });
    }
    s.set(".stage", stage && HD.html`<div><div style="background-image: url('${HD.asset(stage.path)}');"></div></div>`);
  },

  // The losers badge fades in for a team in losers
  losers: (t) => gsap.to(t.sel(".losers_badge"), { autoAlpha: t.team.losers ? 1 : 0, overwrite: true, duration: 0.8 }),

  // A player's controller (Tokkon): its icon and short name
  controller: (t) =>
    t.set(
      ".controller",
      t.player.controller &&
        HD.html`<img src='${HD.asset(t.player.controller.icon_path)}' height="20"><span class="controller_name">${t.player.controller.short_name}</span>`,
    ),

  // The game being played: games played + 1, or the last one once a
  // player has won the set
  gameNumber(s) {
    const [a, b] = s.teams.map((t) => Number(t.team.score) || 0);
    const bestOf = Number(s.score.best_of) || 0;
    return bestOf > 0 && Math.max(a, b) >= Math.ceil(bestOf / 2) ? a + b : a + b + 1;
  },
};

// The standard versus screen. options: slide(way) (the character art's
// in and out), stage (VS.stage's), teamName(t) (a doubles team's name)
VS.layout = ({ slide = VS.slide, stage, teamName = (t) => HD.html`<div>${t.name}</div>` } = {}) => ({
  intro(tl) {
    const fade = { duration: 0.8, opacity: 0, ease: "power2.inOut" };
    tl.from(".phase.container", fade, 0)
      .from(".match", fade, 0)
      .from(".score_container", fade, 0)
      .from(".best_of.container", fade, 0)
      .from(".vs", { duration: 0.4, opacity: 0, scale: 4, ease: "out" }, 0.5)
      .from(".p1.container", { duration: 1, x: -100, ease: "out" }, 0)
      .from(".p2.container", { duration: 1, x: 100, ease: "out" }, 0);
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      if (s.isTeams) {
        // The team's name, its players' under it when it has one
        const names = HD.playerNames(team);
        t.set(".name", teamName(t));
        t.set(".real_name", t.name !== names ? names : "");
        t.set("> .sponsor_logo", "");
        const seed = t.players[0] && t.players[0].seed;
        t.set(".info_grid", seed ? HD.html`<div class="seed"><div class="seed_logo"></div>Seed ${seed}</div>` : "");
      } else {
        t.set(".name", HD.html`${player.team && HD.html`<span class="sponsor">${player.team}</span>`}${player.name}`);
        t.set("> .sponsor_logo", HD.img(HD.asset(player.sponsor_logo), "class='sponsor_logo'"));
        t.set(".real_name", player.real_name);
        t.set(".info_grid", VS.infoGrid(player));
      }
      t.set(
        ".character_name",
        !s.settings.avatar && VS.characterNames(s.isTeams ? t.players : [player], !s.isTeams && s.settings.force_variant_last),
      );
      t.set(".score", team.score);
      VS.losers(t);
      VS.art(s, t, slide(t.n === 1 ? 1 : -1));
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".tournament", s.data.tournamentInfo.tournamentName);
    s.set(".event", s.data.tournamentInfo.eventName);
    s.set(".match", s.score.match);
    s.set(".phase:not(.container)", s.score.phase);
    s.set(".container .best_of", s.score.best_of_text);
    VS.stage(s, stage);
  },
});

HD.layouts.versus = VS.layout();
