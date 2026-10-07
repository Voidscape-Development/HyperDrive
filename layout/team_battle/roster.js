// Roster board: both teams' players in two columns, with their character,
// avatar, flag, pronouns and stocks or games won. The active players are lit
// and eliminated ones crossed out. Cards shrink to fit any number of players.
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  function teamHtml(t) {
    return `
      <div class="rs_team t${t}">
        <div class="rs_head">
          <div class="rs_logo logo"></div>
          <div class="rs_name display"></div>
          <div class="rs_big">
            <span class="rs_big_value display">0</span>
            <span class="rs_big_label"></span>
          </div>
        </div>
        <div class="rs_list"></div>
      </div>`;
  }

  function cardHtml(index) {
    return `
      <div class="rs_card">
        <div class="rs_card_bg"></div>
        <div class="rs_num display">${index + 1}</div>
        <div class="rs_render fades_when_dead"></div>
        <div class="rs_info fades_when_dead">
          <div class="rs_player_name"></div>
          <div class="rs_details">
            <div class="rs_chips chips"></div>
            <div class="rs_pips pips"></div>
          </div>
        </div>
        <img class="rs_avatar player_avatar fades_when_dead" />
        <div class="rs_status display"></div>
        <div class="sweep"></div>
        <div class="x_mark"></div>
      </div>`;
  }

  document.getElementById("roster").innerHTML = `
    <div class="rs_header">
      <img class="rs_tournament_logo" src="../logo.png" onerror="this.style.display='none'" />
      <div class="rs_titles">
        <div class="rs_tournament display"></div>
        <div class="rs_phase"></div>
      </div>
    </div>
    <div class="rs_body">
      ${teamHtml(1)}
      <div class="rs_center">
        <div class="rs_vs display">VS</div>
        <div class="rs_rule"></div>
        <div class="rs_scores">
          <span class="rs_score_value t1 display">0</span>
          <span class="rs_score_label">Score</span>
          <span class="rs_score_value t2 display">0</span>
        </div>
      </div>
      ${teamHtml(2)}
    </div>`;

  let intro = null;
  let rendered = false;
  let builtFor = null;

  Start = async () => {
    if (intro) intro.progress(1).kill();
    intro = gsap.timeline();
    intro.from(".rs_header", { duration: 0.5, y: -60, autoAlpha: 0, ease: "power3.out" }, 0);
    intro.from(".rs_team.t1 .rs_head", { duration: 0.6, x: -300, autoAlpha: 0, ease: "power3.out" }, 0.1);
    intro.from(".rs_team.t2 .rs_head", { duration: 0.6, x: 300, autoAlpha: 0, ease: "power3.out" }, 0.1);
    intro.from(".rs_vs", { duration: 0.6, scale: 3, autoAlpha: 0, ease: "power4.in" }, 0.2);
    intro.from([".rs_rule", ".rs_scores"], { duration: 0.4, y: 20, autoAlpha: 0, stagger: 0.1 }, 0.6);
    intro.from(".rs_big", { duration: 0.5, scale: 0, ease: "back.out(2)" }, 0.5);
    intro.from(".rs_team.t1 .rs_card", { duration: 0.5, x: -120, autoAlpha: 0, stagger: 0.07, ease: "power3.out" }, 0.4);
    intro.from(".rs_team.t2 .rs_card", { duration: 0.5, x: 120, autoAlpha: 0, stagger: 0.07, ease: "power3.out" }, 0.4);
  };

  // Every card is the same height on both sides, as big as fits
  function build(teams, event) {
    const most = Math.max(teams[0].players.length, teams[1].players.length, 1);
    const list = document.querySelector(".rs_list");
    const gap = most > 6 ? 8 : 14;
    const cardH = Math.floor(Math.min(170, (list.clientHeight - gap * (most - 1)) / most));
    document.querySelector(".rs_body").style.setProperty("--card-h", `${cardH}px`);
    document.querySelector(".rs_body").style.setProperty("--card-gap", `${gap}px`);
    document.querySelector(".rs_body").classList.toggle("compact", cardH < 90);

    for (const team of teams) {
      const el = document.querySelector(`.rs_team.t${team.t} .rs_list`);
      el.innerHTML = team.players.map((p, i) => cardHtml(i)).join("");
      el.querySelectorAll(".rs_card").forEach((card, i) => {
        TBCharacterRender(card.querySelector(".rs_render"), team.players[i], event);
      });
    }
  }

  async function updateCard(card, p, team, animate) {
    SetInnerHtml($(card.querySelector(".rs_player_name")), await TBNameHtml(p));
    TBSetHtml(card.querySelector(".rs_chips"), TBChipsHtml(p));
    // First To: games won count against the current opponent, so only the
    // active player has any
    const pips = card.querySelector(".rs_pips");
    pips.style.display = TBIsStock() || p.active ? "" : "none";
    TBUpdatePips(pips, p, team, animate);

    const avatar = TBAvatar(p.data);
    const img = card.querySelector(".rs_avatar");
    if (avatar) {
      if (img.getAttribute("src") !== avatar) img.setAttribute("src", avatar);
      img.style.display = "";
    } else {
      img.removeAttribute("src");
      img.style.display = "none";
    }

    const status = p.dead ? "Out" : p.active ? "Playing" : "";
    TBSetHtml(card.querySelector(".rs_status"), status);
    TBSetEliminated(card, p.dead, animate);
    TBSetActive(card, p.active && !p.dead, animate);
  }

  Update = async (event) => {
    const data = event.data;
    const teams = TBTeams(data);
    TBApplyColors(teams);

    const counts = teams.map((t) => t.players.length).join(",");
    const rebuilt = counts !== builtFor;
    if (rebuilt) {
      build(teams, event);
      builtFor = counts;
    }
    const animate = rendered && !rebuilt;

    SetInnerHtml($(".rs_tournament"), TBEscape(_.get(data, "tournamentInfo.tournamentName", "")));
    SetInnerHtml($(".rs_phase"), TBPhaseMatch(data));
    SetInnerHtml($(".rs_rule"), TBRuleText(teams));

    for (const team of teams) {
      const el = document.querySelector(`.rs_team.t${team.t}`);
      SetInnerHtml($(el.querySelector(".rs_name")), TBEscape(team.displayName));
      TBSetHtml(el.querySelector(".rs_logo"), TBLogoHtml(team));
      TBAnimateNumber(el.querySelector(".rs_big_value"), team.big, rendered);
      el.querySelector(".rs_big_label").textContent = team.bigLabel;
      TBAnimateNumber(document.querySelector(`.rs_score_value.t${team.t}`), team.score, rendered);

      const cards = el.querySelectorAll(".rs_card");
      for (const [i, p] of team.players.entries()) {
        await updateCard(cards[i], p, team, animate);
      }
    }

    rendered = true;
  };
});
