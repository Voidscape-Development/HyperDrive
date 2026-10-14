// Player presentation: both players (name, pronouns, real name, seed, bio,
// chips, characters and art), and for one of them (page option player: 1
// or 2) their recent tournament results and their run in this bracket
const TOURNAMENTS = 4;
const SETS = 4;

const slide = (way) => ({
  out: { x: `${-way * 100}%`, stagger: 0.1 },
  in: { x: 0, duration: 1, ease: "expo.out", autoAlpha: 1, stagger: 0.2 },
});

// Names with styled slashes between them
const slashed = (names) => HD.join(names.map((n) => HD.html`<span>${n}</span>`), HD.html`<span class="slash">/</span>`);

// The rows slide in from the side the player is on
const slideRows = (selector, player, duration) => {
  const tl = gsap.timeline();
  $(selector).each((i, el) => tl.from(el, { x: player == 1 ? 100 : -100, autoAlpha: 0, duration }, 0.2 + 0.2 * i));
};

const resultCard = (_t, i) => HD.html`
  <div class="tournament${i + 1} tournament_container">
    <div class="tournament_container_inner">
      <div class="tournament_logo"></div>
      <div class="placement"></div>
      <div class="tournament_info"><div class="tournament_name"></div><div class="event_name"></div></div>
    </div>
  </div>`;

const setCard = ([, set], i) => {
  const won = set.player_score > set.oponent_score;
  return HD.html`
    <div class="set${i + 1} set_container">
      <div class="set_container_inner">
        <div class="result_tag ${won && "winner"}">${won ? "W" : "L"}</div>
        <div class="phase_match"></div>
        <div class="player_char"></div>
        <div class="set_score"></div>
        <div class="oponent_char"></div>
        <div class="name"></div>
      </div>
    </div>`;
};

HD.layout({
  settings: { player: 1, display_titles: true },

  intro(tl) {
    const fade = (duration) => ({ duration, opacity: 0, ease: "power2.inOut" });
    tl.to(".logo", { duration: 0.8, top: 160, scale: 0.4 }, 0)
      .from(".tournament", fade(0.6), 0.2)
      .from(".match", fade(0.6), 0.4)
      .from(".score_container", fade(0.8), 0)
      .from(".best_of.container", fade(0.8), 0)
      .from(".vs1", { duration: 0.1, opacity: 0, scale: 10, ease: "in" }, 1.2)
      .from(".vs2", { duration: 0.01, opacity: 0 }, 1.3)
      .to(".vs2", { opacity: 0, scale: 2, ease: "power2.out" }, 1.31)
      .from(".p1.container", { duration: 1, x: -200, ease: "out" }, 0)
      .from(".p2.container", { duration: 1, x: 200, ease: "out" }, 0);
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      const solo = s.isTeams ? {} : player;
      const names = t.players.map((p) => p.name).filter(Boolean);

      if (s.isTeams) {
        t.set(".name", team.teamName && team.teamName.trim() ? team.teamName : slashed(names));
        // The players under a team name that isn't just their names
        const sameNames =
          team.teamName && _.isEqual(team.teamName.split("/").map((n) => n.trim()).sort(), [...names].sort());
        t.set(".real_name", team.teamName && team.teamName.trim() && !sameNames && slashed(names));
        VS.losers(t);
      } else {
        t.set("&.player.container .name", HD.html`<span class="sponsor">${player.team}</span> ${player.name}`);
        t.set(".real_name", player.real_name);
      }
      t.set(".pronoun", HD.ui.chip("pronoun", solo.pronoun));
      t.set("> .sponsor_logo", HD.img(HD.asset(solo.sponsor_logo), "class='sponsor_icon'"));
      const seed = s.isTeams ? t.players[0] && t.players[0].seed : player.seed;
      t.set(".seed", HD.ui.chip("seed", seed, "Seed "));
      // bio.txt in the player's folder in user_data/custom_player_export/
      t.set(".custom_bio", HD.custom(solo, "bio", ""));
      t.set(".twitter", solo.twitter && HD.html`<div class="twitter_logo"></div> ${solo.twitter}`);
      t.set(".flagcountry", HD.ui.flag(solo.country, "flagname"));
      t.set(".flagstate", HD.ui.flag(solo.state, "flagname"));
      t.set(
        ".character_name",
        !s.settings.avatar &&
          (s.isTeams
            ? t.players.flatMap((p) => Object.values(p.character || {}).map((c) => c.name)).filter(Boolean).join(" / ")
            : VS.characterNames([player], s.settings.force_variant_last)),
      );
      t.set(".score", team.score);
      VS.art(s, t, { flip_x: t.n === 2, ...slide(t.n === 1 ? 1 : -1) });
    }
    HD.teamColors(s);
    if (s.isTeams) return;

    // The player's recent tournament results
    const player = s.settings.player;
    const path = ["score", s.n];
    const titles = s.settings.display_titles;
    const results = Object.values(_.get(s.score, ["history_sets", player]) || {}).slice(0, TOURNAMENTS);
    if (
      HD.build(".results", results, () => [
        HD.html`<div class="info title">${titles ? "Recent Results" : " "}</div>`,
        results.map(resultCard),
      ])
    ) {
      slideRows(".results .tournament_container", player, 0.3);
    }
    results.forEach((t, i) => {
      const card = `.results .tournament${i + 1} .tournament_container_inner`;
      HD.set(`${card} .tournament_info .tournament_name`, t.tournament_name);
      HD.set(`${card} .tournament_info .event_name`, t.event_name);
      HD.set(`${card} .tournament_logo`, HD.html`<span class="logo" style="background-image: url('${t.tournament_picture}')"></span>`);
      HD.set(
        `${card} .placement`,
        HD.html`${t.placement}<span class="ordinal">${HD.ordinal(t.placement)}</span><span class="num_entrants">/${t.entrants}</span>`,
      );
    });

    // Their run in this bracket, oldest set first
    const sets = Object.entries(_.get(s.score, ["last_sets", player]) || {})
      .slice(0, SETS)
      .reverse();
    if (
      HD.build(".sets", sets, () => [HD.html`<div class="info title">${titles ? "Current Run" : " "}</div>`, sets.map(setCard)])
    ) {
      slideRows(".sets .set_container", player, 0.4);
    }
    sets.forEach(([key, set], i) => {
      const card = `.sets .set${i + 1}`;
      HD.set(`${card} .phase_match`, `${HD.text([set.phase_name, set.phase_id])} - ${set.round_name}`);
      HD.set(
        `${card} .name`,
        HD.html`<div class="versus">VS</div>${set.oponent_team && HD.html`<span class="sponsor">${set.oponent_team}</span>`} ${set.oponent_name}`,
      );
      const scores = [set.player_score, set.oponent_score];
      HD.set(`${card} .set_score`, (player == 2 ? scores.reverse() : scores).join(" - "));
      for (const side of ["player_char", "oponent_char"]) {
        s.characters(`${card} .${side}`, { source: [...path, "last_sets", player, key, side] });
      }
    });
  },
});
