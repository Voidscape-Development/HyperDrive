// Versus splash: the two teams facing off, with big names and logos, and
// their rosters below as character portraits.
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  function teamHtml(t) {
    return `
      <div class="vs_team t${t}">
        <div class="vs_logo logo"></div>
        <div class="vs_name display"></div>
        <div class="vs_numbers">
          <div class="vs_big">
            <span class="vs_big_value display">0</span>
            <span class="vs_big_label"></span>
          </div>
          <div class="vs_score">
            <span class="vs_score_label">Score</span>
            <span class="vs_score_value display">0</span>
          </div>
        </div>
      </div>`;
  }

  function cardHtml(index) {
    return `
      <div class="vs_card">
        <div class="vs_card_frame">
          <div class="vs_render fades_when_dead"></div>
          <div class="vs_num display">${index + 1}</div>
          <div class="vs_plate fades_when_dead">
            <div class="vs_player_name"></div>
            <div class="vs_pips pips"></div>
          </div>
          <div class="sweep"></div>
        </div>
        <div class="x_mark"></div>
      </div>`;
  }

  document.getElementById("versus").innerHTML = `
    <div class="vs_bg t1"></div>
    <div class="vs_bg t2"></div>
    <div class="vs_slash"></div>
    <div class="vs_top">
      <div class="vs_tournament display"></div>
      <div class="vs_phase"></div>
    </div>
    ${teamHtml(1)}
    ${teamHtml(2)}
    <div class="vs_mid">
      <div class="vs_vs display">VS</div>
      <div class="vs_rule"></div>
    </div>
    <div class="vs_rosters">
      <div class="vs_roster t1"></div>
      <div class="vs_roster t2"></div>
    </div>`;

  let intro = null;
  let rendered = false;
  let builtFor = null;

  Start = async () => {
    if (intro) intro.progress(1).kill();
    intro = gsap.timeline();
    intro.from(".vs_bg.t1", { duration: 0.6, xPercent: -100, ease: "power4.out" }, 0);
    intro.from(".vs_bg.t2", { duration: 0.6, xPercent: 100, ease: "power4.out" }, 0);
    intro.from(".vs_slash", { duration: 0.5, scaleY: 0, ease: "power3.out" }, 0.3);
    intro.from(".vs_top", { duration: 0.5, y: -60, autoAlpha: 0, ease: "power3.out" }, 0.3);
    intro.from(".vs_team.t1 > *", { duration: 0.55, x: -200, autoAlpha: 0, stagger: 0.08, ease: "power3.out" }, 0.4);
    intro.from(".vs_team.t2 > *", { duration: 0.55, x: 200, autoAlpha: 0, stagger: 0.08, ease: "power3.out" }, 0.4);
    intro.from(".vs_vs", { duration: 0.45, scale: 4, autoAlpha: 0, ease: "power4.in" }, 0.6);
    intro.fromTo(".vs_vs", { x: 0 }, { keyframes: { x: [0, -14, 12, -8, 5, 0] }, duration: 0.35, ease: "none" }, 1.05);
    intro.from(".vs_rule", { duration: 0.4, y: 20, autoAlpha: 0 }, 1.1);
    intro.from(".vs_roster.t1 .vs_card", { duration: 0.5, y: 120, autoAlpha: 0, stagger: 0.06, ease: "power3.out" }, 0.8);
    intro.from(".vs_roster.t2 .vs_card", { duration: 0.5, y: 120, autoAlpha: 0, stagger: 0.06, ease: "power3.out" }, 0.8);
  };

  // Same card size on both sides, as wide as fits
  function build(teams, event) {
    const most = Math.max(teams[0].players.length, teams[1].players.length, 1);
    const roster = document.querySelector(".vs_roster");
    const gap = most > 6 ? 8 : 14;
    const cardW = Math.floor(Math.min(200, (roster.clientWidth - gap * (most - 1)) / most));
    const rosters = document.querySelector(".vs_rosters");
    rosters.style.setProperty("--card-w", `${cardW}px`);
    rosters.style.setProperty("--card-gap", `${gap}px`);

    for (const team of teams) {
      const el = document.querySelector(`.vs_roster.t${team.t}`);
      el.innerHTML = team.players.map((p, i) => cardHtml(i)).join("");
      el.querySelectorAll(".vs_card").forEach((card, i) => {
        TBCharacterRender(card.querySelector(".vs_render"), team.players[i], event, {
          custom_center: [0.5, 0.4],
        });
      });
    }
  }

  async function updateCard(card, p, team, animate) {
    SetInnerHtml($(card.querySelector(".vs_player_name")), await TBNameHtml(p));
    const pips = card.querySelector(".vs_pips");
    pips.style.display = TBIsStock() || p.active ? "" : "none";
    TBUpdatePips(pips, p, team, animate);
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

    SetInnerHtml($(".vs_tournament"), TBEscape(_.get(data, "tournamentInfo.tournamentName", "")));
    SetInnerHtml($(".vs_phase"), TBPhaseMatch(data));
    // e.g. "4 v 4 · 3 Stocks each"
    const sizes = teams.map((t) => t.players.length);
    SetInnerHtml(
      $(".vs_rule"),
      [Math.max(...sizes) ? sizes.join(" v ") : "", TBRuleText(teams)].filter(Boolean).join(" &middot; "),
    );

    for (const team of teams) {
      const el = document.querySelector(`.vs_team.t${team.t}`);
      SetInnerHtml($(el.querySelector(".vs_name")), TBEscape(team.displayName));
      TBSetHtml(el.querySelector(".vs_logo"), TBLogoHtml(team));
      TBAnimateNumber(el.querySelector(".vs_big_value"), team.big, rendered);
      el.querySelector(".vs_big_label").textContent = team.bigLabel;
      TBAnimateNumber(el.querySelector(".vs_score_value"), team.score, rendered);

      const cards = document.querySelectorAll(`.vs_roster.t${team.t} .vs_card`);
      for (const [i, p] of team.players.entries()) {
        await updateCard(cards[i], p, team, animate);
      }
    }

    rendered = true;
  };
});
