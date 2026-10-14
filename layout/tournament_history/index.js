// A player's last tournaments (page option player: 1 or 2, up to 6): each
// with its logo, the placement out of the entrants, the event and the
// seed performance rating (placement rounds above or below the seed)
const tournamentCard = (_t, i) => HD.html`
  <div class="tournament${i + 1} tournament_container">
    <div class="info">
      <div class="tournament_logo"></div>
      <div class="placement"></div>
      <div class="tournament_info">
        <div class="tournament_name"></div>
        <div class="event_name"></div>
        <div class="spr"></div>
      </div>
    </div>
  </div>`;

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  settings: { player: 1 },

  intro(tl) {
    $(".tournament_container").each((i, el) => tl.from(el, { x: -100, autoAlpha: 0, duration: 0.3 }, 0.2 + 0.2 * i));
  },

  update(s) {
    const tournaments = Object.values(_.get(s.score, ["history_sets", s.settings.player]) || {}).slice(0, 6);
    const built = HD.build(".player1_content", tournaments, () => tournaments.map(tournamentCard));

    tournaments.forEach((t, i) => {
      const card = `.player1_content .tournament${i + 1} .info`;
      const spr = t.spr;
      HD.set(`${card} .tournament_info .tournament_name`, t.tournament_name);
      HD.set(`${card} .tournament_info .event_name`, t.event_name);
      HD.set(
        `${card} .tournament_info .spr`,
        spr != null &&
          HD.html`<span class="seed">Seed ${t.seed}</span><span class="spr_value ${
            spr > 0 ? "positive" : spr < 0 ? "negative" : "even"
          }">SPR ${spr > 0 ? "+" : ""}${spr}</span>`,
      );
      HD.set(
        `${card} .tournament_logo`,
        HD.html`<span class="logo" style="background-image: url('${t.tournament_picture}')"></span>`,
      );
      HD.set(
        `${card} .placement`,
        HD.html`${t.placement}<span class="ordinal">${HD.ordinal(t.placement)}</span><span class="num_entrants">/${t.entrants}</span>`,
      );
    });

    // New tournaments slide in again
    if (built && !s.first) HD.restart();
  },
});
