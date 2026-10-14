// In-game scoreboard: a bar at the top center with each team's name, logo,
// big number (stocks or players left) and team score, the active player
// (character icon, tag, stocks or games won) under it, and the roster
const teamPanel = (t) => HD.html`
  <div class="sb_team t${t}">
    <div class="sb_panel">
      <div class="sb_logo logo"></div>
      <div class="sb_name display"></div>
      <div class="sb_score"><span class="sb_score_label">Score</span><span class="sb_score_value display">0</span></div>
    </div>
    <div class="sb_big"><span class="sb_big_value display">0</span><span class="sb_big_label"></span></div>
  </div>`;

const sidePanel = (t) => HD.html`
  <div class="sb_side t${t}">
    <div class="sb_active">
      <div class="sb_active_inner fades_when_dead">
        <div class="sb_char"><img /></div>
        <div class="sb_player_name"></div>
        <div class="sb_pips pips"></div>
      </div>
      <div class="sweep"></div>
      <div class="x_mark"></div>
    </div>
    <div class="sb_roster"></div>
  </div>`;

// Which player each team's plate shows, to slide the next one in
const activeKeys = {};

function updateRoster(t, team, animate) {
  const roster = document.querySelector(`.sb_side.t${t} .sb_roster`);
  const rebuilt = HD.build(roster, team.players.length, () =>
    team.players.map(() => HD.html`<div class="mini"><img class="fades_when_dead" /><div class="x_mark"></div></div>`),
  );
  // Smaller icons for big teams
  if (rebuilt)
    roster.style.setProperty("--mini-size", `${Math.max(14, Math.min(28, 260 / Math.max(team.players.length, 1)))}px`);

  roster.querySelectorAll(".mini").forEach((mini, i) => {
    const p = team.players[i];
    const icon = TB.characterIcon(p.character);
    TB.setImage(mini.querySelector("img"), icon);
    mini.classList.toggle("no_icon", !icon);
    TB.setEliminated(mini, p.dead, animate && !rebuilt);
    TB.setActive(mini, p.active, animate && !rebuilt);
  });
}

function updateActive(t, team, animate) {
  const plate = document.querySelector(`.sb_side.t${t} .sb_active`);
  const p = team.active;
  const swapped = activeKeys[t] !== (p ? p.key : null);
  activeKeys[t] = p ? p.key : null;
  plate.classList.toggle("empty", !p);
  if (!p) return;

  TB.setImage(plate.querySelector(".sb_char img"), TB.characterIcon(p.character), "visibility");
  HD.set(plate.querySelector(".sb_player_name"), TB.name(p));
  TB.updatePips(plate.querySelector(".sb_pips"), p, team, animate && !swapped);
  TB.setEliminated(plate, p.dead, animate && !swapped);

  if (animate && swapped) {
    // The next player comes in
    gsap.fromTo(
      plate.querySelector(".sb_active_inner"),
      { x: t === 1 ? -80 : 80, autoAlpha: 0 },
      { x: 0, autoAlpha: 1, duration: 0.45, ease: "power3.out", overwrite: true },
    );
    TB.sweep(plate.querySelector(".sweep"), 0.15);
  }
}

HD.layout({
  subscribe: ["team_battle", "score", "game", "tournamentInfo", "commentary"],
  init() {
    HD.render(
      "#scoreboard",
      HD.html`
        <div class="sb_main">
          ${teamPanel(1)}
          <div class="sb_center"><div class="sb_phase"></div><div class="sb_rule"></div></div>
          ${teamPanel(2)}
        </div>
        <div class="sb_sub">${sidePanel(1)}<div class="sb_sub_gap"></div>${sidePanel(2)}</div>`,
    );
  },

  intro(tl) {
    const ease = "power3.out";
    tl.from(".sb_center", { duration: 0.45, y: -90, ease }, 0)
      .from(".sb_team.t1 .sb_panel", { duration: 0.55, x: 260, autoAlpha: 0, ease }, 0.15)
      .from(".sb_team.t2 .sb_panel", { duration: 0.55, x: -260, autoAlpha: 0, ease }, 0.15)
      .from(".sb_big", { duration: 0.5, scale: 0, ease: "back.out(2.2)" }, 0.35)
      .from(".sb_active", { duration: 0.45, y: -50, autoAlpha: 0, ease }, 0.55)
      .from(".sb_roster .mini", { duration: 0.3, scale: 0, autoAlpha: 0, stagger: 0.04, ease: "back.out(2)" }, 0.75);
  },

  update(s) {
    const teams = TB.teams(s.data);
    const animate = !s.first;
    TB.applyColors(teams);
    s.set(".sb_phase", TB.phaseMatch(s.data));
    s.set(".sb_rule", TB.ruleText(teams));

    for (const team of teams) {
      const el = (sel) => document.querySelector(`.sb_team.t${team.t} ${sel}`);
      TB.updateHeader(
        team,
        {
          name: el(".sb_name"),
          logo: el(".sb_logo"),
          big: el(".sb_big_value"),
          bigLabel: el(".sb_big_label"),
          score: el(".sb_score_value"),
        },
        animate,
      );
      updateRoster(team.t, team, animate);
      updateActive(team.t, team, animate);
    }
  },
});
