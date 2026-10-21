// Versus splash: the two teams facing off, with big names and logos, and
// their rosters below as character portraits. When only some of the players
// play, a portrait per play: the players who came in, and empty ones for the
// rest, without the players on deck.

// ---------------------------------------------------------------------
// Markup

const teamSide = (t) => HD.html`
  <div class="vs_team t${t}">
    <div class="vs_logo logo"></div>
    <div class="vs_name display"></div>
    <div class="vs_numbers">
      <div class="vs_big"><span class="vs_big_value display">0</span><span class="vs_big_label"></span></div>
      <div class="vs_score"><span class="vs_score_label">Score</span><span class="vs_score_value display">0</span></div>
    </div>
  </div>`;

const portrait = (_p, i) => HD.html`
  <div class="vs_card">
    <div class="vs_card_frame">
      <div class="vs_render fades_when_dead"></div>
      <div class="vs_num display">${i + 1}</div>
      <div class="vs_plate fades_when_dead"><div class="vs_player_name"></div><div class="vs_pips pips"></div></div>
      <div class="sweep"></div>
    </div>
    <div class="x_mark"></div>
  </div>`;

// ---------------------------------------------------------------------
// Cards

// The same card width on both sides, as wide as fits
function sizeCards(teams) {
  const most = Math.max(teams[0].lineup.length, teams[1].lineup.length, 1);
  const gap = most > 6 ? 8 : 14;
  const width = Math.floor(Math.min(200, (document.querySelector(".vs_roster").clientWidth - gap * (most - 1)) / most));
  const rosters = document.querySelector(".vs_rosters");
  rosters.style.setProperty("--card-w", `${width}px`);
  rosters.style.setProperty("--card-gap", `${gap}px`);
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["team_battle", "score", "game", "tournamentInfo", "commentary"],
  init() {
    HD.render(
      "#versus",
      HD.html`
        <div class="vs_bg t1"></div>
        <div class="vs_bg t2"></div>
        <div class="vs_slash"></div>
        <div class="vs_top"><div class="vs_tournament display"></div><div class="vs_phase"></div></div>
        ${teamSide(1)}
        ${teamSide(2)}
        <div class="vs_mid"><div class="vs_vs display">VS</div><div class="vs_rule"></div></div>
        <div class="vs_rosters"><div class="vs_roster t1"></div><div class="vs_roster t2"></div></div>`,
    );
  },

  intro(tl) {
    const ease = "power3.out";
    tl.from(".vs_bg.t1", { duration: 0.6, xPercent: -100, ease: "power4.out" }, 0)
      .from(".vs_bg.t2", { duration: 0.6, xPercent: 100, ease: "power4.out" }, 0)
      .from(".vs_slash", { duration: 0.5, scaleY: 0, ease }, 0.3)
      .from(".vs_top", { duration: 0.5, y: -60, autoAlpha: 0, ease }, 0.3)
      .from(".vs_team.t1 > *", { duration: 0.55, x: -200, autoAlpha: 0, stagger: 0.08, ease }, 0.4)
      .from(".vs_team.t2 > *", { duration: 0.55, x: 200, autoAlpha: 0, stagger: 0.08, ease }, 0.4)
      .from(".vs_vs", { duration: 0.45, scale: 4, autoAlpha: 0, ease: "power4.in" }, 0.6)
      .fromTo(".vs_vs", { x: 0 }, { keyframes: { x: [0, -14, 12, -8, 5, 0] }, duration: 0.35, ease: "none" }, 1.05)
      .from(".vs_rule", { duration: 0.4, y: 20, autoAlpha: 0 }, 1.1)
      .from(".vs_roster.t1 .vs_card", { duration: 0.5, y: 120, autoAlpha: 0, stagger: 0.06, ease }, 0.8)
      .from(".vs_roster.t2 .vs_card", { duration: 0.5, y: 120, autoAlpha: 0, stagger: 0.06, ease }, 0.8);
  },

  update(s) {
    const teams = TB.teams(s.data);
    TB.applyColors(teams);

    // Portraits again when a team's size changes
    let rebuilt = false;
    for (const team of teams) {
      if (HD.build(`.vs_roster.t${team.t}`, team.lineup.length, () => team.lineup.map(portrait))) rebuilt = true;
    }
    if (rebuilt) sizeCards(teams);
    const animate = !s.first && !rebuilt;

    s.set(".vs_tournament", s.data.tournamentInfo.tournamentName);
    s.set(".vs_phase", TB.phaseMatch(s.data));
    // e.g. "4 v 4 · 3 Stocks each"
    const sizes = teams.map((t) => t.lineup.length);
    s.set(".vs_rule", HD.text([Math.max(...sizes) ? sizes.join(" v ") : "", TB.ruleText(teams)], " · "));

    for (const team of teams) {
      const el = (sel) => document.querySelector(`.vs_team.t${team.t} ${sel}`);
      TB.updateHeader(
        team,
        {
          name: el(".vs_name"),
          logo: el(".vs_logo"),
          big: el(".vs_big_value"),
          bigLabel: el(".vs_big_label"),
          score: el(".vs_score_value"),
        },
        !s.first,
      );
      $(`.vs_roster.t${team.t} .vs_card`).each((i, card) => {
        const p = team.lineup[i];
        // An empty portrait for a player the team hasn't picked yet
        card.classList.toggle("empty", !p);
        HD.set(card.querySelector(".vs_player_name"), p ? TB.name(p) : "");
        const pips = card.querySelector(".vs_pips");
        pips.style.display = p && (TB.isStock() || p.active) ? "" : "none";
        if (p) TB.updatePips(pips, p, team, animate);
        TB.setEliminated(card, !!p && p.dead, animate && !!p);
        TB.setActive(card, !!p && p.active && !p.dead, animate && !!p);
        TB.characterRender(s, card.querySelector(".vs_render"), p, { custom_center: [0.5, 0.4] });
      });
    }
  },
});
