// Half screen stats for split screen displays (page option player: 1 or 2).
// Player 1's page fills the right half of the screen and player 2's the left,
// so each player's stats sit beside the other player's view. Shows the
// player's name, seed, record in this event (last_sets), recent tournament
// finishes (history_sets) and recent sets.

const finishCard = (_t, i) => HD.html`
  <div class="finish finish${i + 1}">
    <div class="placement"></div>
    <div class="finish_info"><div class="tournament_name"></div><div class="event_name"></div></div>
    <div class="spr"></div>
  </div>`;

const setCard = (_s, i) => HD.html`
  <div class="set set${i + 1}">
    <div class="result_tag"></div>
    <div class="set_info"><div class="oponent"></div><div class="round"></div></div>
    <div class="set_score"></div>
  </div>`;

HD.layout({
  subscribe: ["score", "game", "tournamentInfo"],
  settings: { player: 1, finishes_displayed: 4, sets_displayed: 4, bio_key: "bio" },

  intro(tl, s) {
    // Slides in from the screen edge it sits against
    const from = s.settings.player == 1 ? 120 : -120;
    tl.from(".panel", { autoAlpha: 0, x: from, duration: 0.6, ease: "power3.out" }, 0)
      .from(".tile", { autoAlpha: 0, y: 20, duration: 0.35, stagger: 0.08 }, 0.3)
      .from(".finish, .set", { autoAlpha: 0, x: from / 3, duration: 0.3, stagger: 0.06 }, 0.5);
  },

  update(s) {
    const c = s.settings;
    const n = Number(c.player) === 2 ? 2 : 1;
    $("body").toggleClass("right", n === 1).toggleClass("left", n === 2);
    HD.teamColors(s);
    document.documentElement.style.setProperty("--side-color", `var(--p${n}-score-bg-color)`);

    const t = s.teams[n - 1];
    if (!t) return;
    HD.set(".name", s.isTeams ? t.name : HD.ui.name(t.player, t.team));
    HD.set(
      ".details",
      s.isTeams
        ? t.team.teamName && HD.playerNames(t.team)
        : HD.join(
            [HD.ui.flag(t.player.country), t.player.real_name, t.player.pronoun],
            HD.html`<span class="dot">·</span>`,
          ),
    );
    const bio = c.bio_key && !s.isTeams && HD.custom(t.player, c.bio_key);
    s.set(".bio", typeof bio === "string" ? bio : "");
    s.characters(".character", {
      source: ["score", s.n, "team", n],
      flip_x: n === 2,
      ...HD.slideToMiddle(n === 1 ? 1 : -1),
    });

    // Seed and record in this event
    const sets = Object.values(_.get(s.score, ["last_sets", n]) || {}).filter(Boolean);
    const won = sets.filter((x) => Number(x.player_score) > Number(x.oponent_score)).length;
    const seed = t.player.seed;
    $(".seed_tile").toggleClass("hidden", !seed);
    $(".record_tile").toggleClass("hidden", sets.length === 0);
    s.set(".seed_tile .tile_value", seed || "");
    s.set(".record_tile .tile_value", `${won}–${sets.length - won}`);

    // Recent tournament finishes
    const finishes = Object.values(_.get(s.score, ["history_sets", n]) || {})
      .filter((h) => h && h.placement)
      .slice(0, Math.max(Number(c.finishes_displayed) || 0, 0));
    $(".finishes_section").toggleClass("hidden", finishes.length === 0);
    HD.build(".finishes", finishes, () => finishes.map(finishCard));
    finishes.forEach((h, i) => {
      const sel = `.finishes .finish${i + 1}`;
      HD.set(
        `${sel} .placement`,
        HD.html`${h.placement}<span class="ordinal">${HD.ordinal(h.placement)}</span><span class="num_entrants">/${h.entrants}</span>`,
      );
      HD.set(`${sel} .tournament_name`, h.tournament_name);
      HD.set(`${sel} .event_name`, h.event_name);
      const spr = h.spr;
      HD.set(
        `${sel} .spr`,
        spr != null && HD.html`<span class="${spr > 0 ? "positive" : spr < 0 ? "negative" : "even"}">SPR ${spr > 0 ? "+" : ""}${spr}</span>`,
      );
    });

    // Recent sets in this event
    const recent = sets.slice(0, Math.max(Number(c.sets_displayed) || 0, 0));
    $(".sets_section").toggleClass("hidden", recent.length === 0);
    HD.build(".sets", recent, () => recent.map(setCard));
    recent.forEach((set, i) => {
      const sel = `.sets .set${i + 1}`;
      const w = Number(set.player_score) > Number(set.oponent_score);
      $(`${sel} .result_tag`).toggleClass("winner", w).toggleClass("loser", !w);
      HD.set(`${sel} .result_tag`, w ? "W" : "L");
      HD.set(`${sel} .oponent`, HD.html`<span class="sponsor">${set.oponent_team}</span>${set.oponent_name}`);
      HD.set(`${sel} .round`, HD.text([set.phase_name, set.round_name], " · "));
      HD.set(`${sel} .set_score`, `${set.player_score}–${set.oponent_score}`);
    });
  },
});
