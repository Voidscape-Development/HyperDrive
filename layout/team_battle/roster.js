// Roster board: both teams' players in two columns, with their character,
// avatar, flag, pronouns and stocks or games won. The active players are lit
// and eliminated ones crossed out. Cards shrink to fit any number of players.
const teamColumn = (t) => HD.html`
  <div class="rs_team t${t}">
    <div class="rs_head">
      <div class="rs_logo logo"></div>
      <div class="rs_name display"></div>
      <div class="rs_big"><span class="rs_big_value display">0</span><span class="rs_big_label"></span></div>
    </div>
    <div class="rs_list"></div>
  </div>`;

const playerCard = (_p, i) => HD.html`
  <div class="rs_card">
    <div class="rs_card_bg"></div>
    <div class="rs_num display">${i + 1}</div>
    <div class="rs_render fades_when_dead"></div>
    <div class="rs_info fades_when_dead">
      <div class="rs_player_name"></div>
      <div class="rs_details"><div class="rs_chips chips"></div><div class="rs_pips pips"></div></div>
    </div>
    <img class="rs_avatar player_avatar fades_when_dead" />
    <div class="rs_status display"></div>
    <div class="sweep"></div>
    <div class="x_mark"></div>
  </div>`;

// Every card the same height on both sides, as big as fits
function sizeCards(teams) {
  const most = Math.max(teams[0].players.length, teams[1].players.length, 1);
  const gap = most > 6 ? 8 : 14;
  const height = Math.floor(Math.min(170, (document.querySelector(".rs_list").clientHeight - gap * (most - 1)) / most));
  const body = document.querySelector(".rs_body");
  body.style.setProperty("--card-h", `${height}px`);
  body.style.setProperty("--card-gap", `${gap}px`);
  body.classList.toggle("compact", height < 90);
}

function updateCard(card, p, team, animate) {
  HD.set(card.querySelector(".rs_player_name"), TB.name(p));
  TB.setHtml(card.querySelector(".rs_chips"), TB.chips(p));
  // First To: games won count against the current opponent, so only the
  // active player has any
  const pips = card.querySelector(".rs_pips");
  pips.style.display = TB.isStock() || p.active ? "" : "none";
  TB.updatePips(pips, p, team, animate);
  TB.setImage(card.querySelector(".rs_avatar"), TB.avatar(p.data));
  TB.setHtml(card.querySelector(".rs_status"), p.dead ? "Out" : p.active ? "Playing" : "");
  TB.setEliminated(card, p.dead, animate);
  TB.setActive(card, p.active && !p.dead, animate);
}

HD.layout({
  init() {
    HD.render(
      "#roster",
      HD.html`
        <div class="rs_header">
          <img class="rs_tournament_logo" src="../logo.png" onerror="this.style.display='none'" />
          <div class="rs_titles"><div class="rs_tournament display"></div><div class="rs_phase"></div></div>
        </div>
        <div class="rs_body">
          ${teamColumn(1)}
          <div class="rs_center">
            <div class="rs_vs display">VS</div>
            <div class="rs_rule"></div>
            <div class="rs_scores">
              <span class="rs_score_value t1 display">0</span>
              <span class="rs_score_label">Score</span>
              <span class="rs_score_value t2 display">0</span>
            </div>
          </div>
          ${teamColumn(2)}
        </div>`,
    );
  },

  intro(tl) {
    const ease = "power3.out";
    tl.from(".rs_header", { duration: 0.5, y: -60, autoAlpha: 0, ease }, 0)
      .from(".rs_team.t1 .rs_head", { duration: 0.6, x: -300, autoAlpha: 0, ease }, 0.1)
      .from(".rs_team.t2 .rs_head", { duration: 0.6, x: 300, autoAlpha: 0, ease }, 0.1)
      .from(".rs_vs", { duration: 0.6, scale: 3, autoAlpha: 0, ease: "power4.in" }, 0.2)
      .from([".rs_rule", ".rs_scores"], { duration: 0.4, y: 20, autoAlpha: 0, stagger: 0.1 }, 0.6)
      .from(".rs_big", { duration: 0.5, scale: 0, ease: "back.out(2)" }, 0.5)
      .from(".rs_team.t1 .rs_card", { duration: 0.5, x: -120, autoAlpha: 0, stagger: 0.07, ease }, 0.4)
      .from(".rs_team.t2 .rs_card", { duration: 0.5, x: 120, autoAlpha: 0, stagger: 0.07, ease }, 0.4);
  },

  update(s) {
    const teams = TB.teams(s.data);
    TB.applyColors(teams);

    // Cards again when a team's size changes
    let rebuilt = false;
    for (const team of teams) {
      if (HD.build(`.rs_team.t${team.t} .rs_list`, team.players.length, () => team.players.map(playerCard))) rebuilt = true;
    }
    if (rebuilt) sizeCards(teams);
    const animate = !s.first && !rebuilt;

    s.set(".rs_tournament", s.data.tournamentInfo.tournamentName);
    s.set(".rs_phase", TB.phaseMatch(s.data));
    s.set(".rs_rule", TB.ruleText(teams));

    for (const team of teams) {
      const el = (sel) => document.querySelector(`.rs_team.t${team.t} ${sel}`);
      TB.updateHeader(
        team,
        { name: el(".rs_name"), logo: el(".rs_logo"), big: el(".rs_big_value"), bigLabel: el(".rs_big_label"), score: document.querySelector(`.rs_score_value.t${team.t}`) },
        !s.first,
      );
      $(`.rs_team.t${team.t} .rs_card`).each((i, card) => {
        updateCard(card, team.players[i], team, animate);
        TB.characterRender(s, card.querySelector(".rs_render"), team.players[i]);
      });
    }
  },
});
