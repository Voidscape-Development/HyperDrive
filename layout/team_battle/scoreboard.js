// In-game scoreboard: a bar at the top center with each team's name, logo,
// big number (stocks or players left) and team score, the active player
// (character icon, tag, stocks or games won) under it, and the roster.
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  function teamHtml(t) {
    return `
      <div class="sb_team t${t}">
        <div class="sb_panel">
          <div class="sb_logo logo"></div>
          <div class="sb_name display"></div>
          <div class="sb_score">
            <span class="sb_score_label">Score</span>
            <span class="sb_score_value display">0</span>
          </div>
        </div>
        <div class="sb_big">
          <span class="sb_big_value display">0</span>
          <span class="sb_big_label"></span>
        </div>
      </div>`;
  }

  function sideHtml(t) {
    return `
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
  }

  document.getElementById("scoreboard").innerHTML = `
    <div class="sb_main">
      ${teamHtml(1)}
      <div class="sb_center">
        <div class="sb_phase"></div>
        <div class="sb_rule"></div>
      </div>
      ${teamHtml(2)}
    </div>
    <div class="sb_sub">
      ${sideHtml(1)}
      <div class="sb_sub_gap"></div>
      ${sideHtml(2)}
    </div>`;

  let intro = null;
  let rendered = false;
  const activeKeys = { 1: undefined, 2: undefined };

  Start = async () => {
    if (intro) intro.progress(1).kill();
    intro = gsap.timeline();
    intro.from(".sb_center", { duration: 0.45, y: -90, ease: "power3.out" }, 0);
    intro.from(".sb_team.t1 .sb_panel", { duration: 0.55, x: 260, autoAlpha: 0, ease: "power3.out" }, 0.15);
    intro.from(".sb_team.t2 .sb_panel", { duration: 0.55, x: -260, autoAlpha: 0, ease: "power3.out" }, 0.15);
    intro.from(".sb_big", { duration: 0.5, scale: 0, ease: "back.out(2.2)" }, 0.35);
    intro.from(".sb_active", { duration: 0.45, y: -50, autoAlpha: 0, ease: "power3.out" }, 0.55);
    intro.from(".sb_roster .mini", { duration: 0.3, scale: 0, autoAlpha: 0, stagger: 0.04, ease: "back.out(2)" }, 0.75);
  };

  function updateRoster(t, team, animate) {
    const roster = document.querySelector(`.sb_side.t${t} .sb_roster`);
    let minis = [...roster.querySelectorAll(".mini")];
    const rebuilt = minis.length != team.players.length;
    if (rebuilt) {
      roster.innerHTML = team.players
        .map(() => `<div class="mini"><img class="fades_when_dead" /><div class="x_mark"></div></div>`)
        .join("");
      minis = [...roster.querySelectorAll(".mini")];
      // Smaller icons for big teams
      roster.style.setProperty("--mini-size", `${Math.max(14, Math.min(28, 260 / Math.max(team.players.length, 1)))}px`);
    }
    team.players.forEach((p, i) => {
      const mini = minis[i];
      const icon = TBCharacterIcon(p.character);
      const img = mini.querySelector("img");
      if (icon) {
        if (img.getAttribute("src") !== icon) img.setAttribute("src", icon);
        mini.classList.remove("no_icon");
      } else {
        img.removeAttribute("src");
        mini.classList.add("no_icon");
      }
      TBSetEliminated(mini, p.dead, animate && !rebuilt);
      TBSetActive(mini, p.active, animate && !rebuilt);
    });
  }

  async function updateActive(t, team, animate) {
    const plate = document.querySelector(`.sb_side.t${t} .sb_active`);
    const p = team.active;
    const key = p ? p.key : null;
    const swapped = activeKeys[t] !== key;
    activeKeys[t] = key;

    plate.classList.toggle("empty", !p);
    if (!p) return;

    const img = plate.querySelector(".sb_char img");
    const icon = TBCharacterIcon(p.character);
    if (icon) {
      if (img.getAttribute("src") !== icon) img.setAttribute("src", icon);
      img.style.visibility = "";
    } else {
      img.removeAttribute("src");
      img.style.visibility = "hidden";
    }

    SetInnerHtml($(plate.querySelector(".sb_player_name")), await TBNameHtml(p));
    TBUpdatePips(plate.querySelector(".sb_pips"), p, team, animate && !swapped);
    TBSetEliminated(plate, p.dead, animate && !swapped);

    if (animate && swapped) {
      // The next player comes in
      gsap.fromTo(
        plate.querySelector(".sb_active_inner"),
        { x: t == 1 ? -80 : 80, autoAlpha: 0 },
        { x: 0, autoAlpha: 1, duration: 0.45, ease: "power3.out", overwrite: true },
      );
      TBSweep(plate.querySelector(".sweep"), 0.15);
    }
  }

  Update = async (event) => {
    const data = event.data;
    const teams = TBTeams(data);
    const animate = rendered;
    TBApplyColors(teams);

    SetInnerHtml($(".sb_phase"), TBPhaseMatch(data));
    SetInnerHtml($(".sb_rule"), TBRuleText(teams));

    for (const team of teams) {
      const t = team.t;
      const el = document.querySelector(`.sb_team.t${t}`);
      SetInnerHtml($(el.querySelector(".sb_name")), TBEscape(team.displayName));
      TBSetHtml(el.querySelector(".sb_logo"), TBLogoHtml(team));
      TBAnimateNumber(el.querySelector(".sb_big_value"), team.big, animate);
      el.querySelector(".sb_big_label").textContent = team.bigLabel;
      TBAnimateNumber(el.querySelector(".sb_score_value"), team.score, animate);

      updateRoster(t, team, animate);
      await updateActive(t, team, animate);
    }

    rendered = true;
  };
});
