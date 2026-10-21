// Nexus - Teams Overview: both teams of a Crew/Team Battle side by side,
// with their logo, name and stocks (or players) left, the team scores around
// the tournament logo, a card per play (the character, the player's stocks or
// wins, crossed out once eliminated, empty until a player comes in) and the
// players on standby below. Uses the Team Battle layouts' team_battle.js.

// ---------------------------------------------------------------------
// Markup

const teamHeader = (t) => HD.html`
  <div class="nx_head t${t}">
    <div class="nx_logo logo"></div>
    <div class="nx_name"></div>
    <div class="nx_big"></div>
  </div>`;

const teamColumn = (t) => HD.html`
  <div class="nx_team t${t}">
    <div class="nx_cards"></div>
    <div class="nx_standby">
      <div class="nx_standby_label"></div>
      <div class="nx_standby_list"></div>
    </div>
  </div>`;

const card = () => HD.html`
  <div class="nx_card">
    <div class="nx_render fades_when_dead"></div>
    <div class="nx_badge"><span class="nx_badge_value"></span><span class="nx_badge_label"></span></div>
    <div class="nx_player_name"></div>
    <div class="sweep"></div>
    <div class="x_mark"></div>
  </div>`;

// ---------------------------------------------------------------------
// Cards

// "06": the big numbers have two digits
const twoDigits = (n) => String(n).padStart(2, "0");

function updateCard(cardEl, p, team, animate) {
  // A play the team hasn't picked a player for yet
  cardEl.classList.toggle("empty", !p);
  const name = cardEl.querySelector(".nx_player_name");
  const badge = cardEl.querySelector(".nx_badge");
  if (!p) {
    HD.set(name, "");
    badge.style.display = "none";
    TB.setEliminated(cardEl, false, false);
    TB.setActive(cardEl, false, false);
    return;
  }
  HD.set(name, TB.name(p));
  // First To: games won count against the current opponent, so only the
  // active player has any
  badge.style.display = !p.dead && (TB.isStock() || p.active) ? "" : "none";
  badge.querySelector(".nx_badge_value").textContent = p.value;
  badge.querySelector(".nx_badge_label").textContent = TB.isStock()
    ? p.value === 1
      ? "Stock"
      : "Stocks"
    : p.value === 1
      ? "Win"
      : "Wins";
  TB.setEliminated(cardEl, p.dead, animate);
  TB.setActive(cardEl, p.active && !p.dead, animate);
}

// The players on standby: character icon and tag, dimmed once the team is
// out without them playing
function updateStandby(team) {
  const standby = document.querySelector(`.nx_team.t${team.t} .nx_standby`);
  standby.style.display = team.limited ? "" : "none";
  if (!team.limited) return;
  const unused = team.onDeck.length > 0 && team.onDeck.every((p) => p.status === "unused");
  standby.querySelector(".nx_standby_label").textContent = unused ? "Didn't play" : "Standby";
  TB.setHtml(
    standby.querySelector(".nx_standby_list"),
    HD.html`${team.onDeck.map((p) => {
      const icon = TB.characterIcon(p.character);
      return HD.html`<div class="nx_chip${p.status === "unused" ? " unused" : ""}">${
        icon && HD.img(icon)
      }<span class="nx_chip_name">${TB.name(p)}</span></div>`;
    })}`,
  );
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["team_battle", "score", "game", "tournamentInfo", "commentary"],
  init() {
    HD.render(
      "#nexus",
      HD.html`
        <div class="nx_top">
          ${teamHeader(1)}
          <div class="nx_center">
            <div class="nx_diamond t1"><span class="nx_score"></span></div>
            <img class="nx_emblem" src="../logo.png" onerror="this.style.visibility='hidden'" />
            <div class="nx_diamond t2"><span class="nx_score"></span></div>
          </div>
          ${teamHeader(2)}
        </div>
        <div class="nx_body">
          ${teamColumn(1)}
          <div class="nx_vs">VS.</div>
          ${teamColumn(2)}
        </div>`,
    );
  },

  intro(tl) {
    const ease = "power3.out";
    tl.from(".nx_head.t1", { duration: 0.55, x: -120, autoAlpha: 0, ease }, 0)
      .from(".nx_head.t2", { duration: 0.55, x: 120, autoAlpha: 0, ease }, 0)
      .from(".nx_emblem", { duration: 0.5, scale: 0, autoAlpha: 0, ease: "back.out(2)" }, 0.2)
      .from(".nx_diamond", { duration: 0.4, scale: 0, autoAlpha: 0, stagger: 0.08, ease: "back.out(2)" }, 0.35)
      .from(".nx_vs", { duration: 0.45, scale: 2.5, autoAlpha: 0, ease: "power4.in" }, 0.4)
      .from(".nx_team.t1 .nx_card", { duration: 0.45, x: -80, autoAlpha: 0, stagger: 0.07, ease }, 0.3)
      .from(".nx_team.t2 .nx_card", { duration: 0.45, x: 80, autoAlpha: 0, stagger: 0.07, ease }, 0.3)
      .from(".nx_standby", { duration: 0.45, y: 40, autoAlpha: 0, ease }, 0.6);
  },

  update(s) {
    const teams = TB.teams(s.data);
    TB.applyColors(teams);

    // Cards again when a team's number of plays changes
    let rebuilt = false;
    for (const team of teams) {
      updateStandby(team);
      if (HD.build(`.nx_team.t${team.t} .nx_cards`, team.lineup.length, () => team.lineup.map(card))) rebuilt = true;
    }
    const animate = !s.first && !rebuilt;

    for (const team of teams) {
      const head = document.querySelector(`.nx_head.t${team.t}`);
      head.querySelector(".nx_name").textContent = team.displayName;
      TB.setHtml(head.querySelector(".nx_logo"), TB.logo(team));
      const big = head.querySelector(".nx_big");
      if (big.dataset.value !== String(team.big)) {
        big.dataset.value = team.big;
        big.textContent = twoDigits(team.big);
        if (animate) gsap.fromTo(big, { scale: 1.3 }, { scale: 1, duration: 0.45, ease: "back.out(3)" });
      }
      document.querySelector(`.nx_diamond.t${team.t} .nx_score`).textContent = team.score;

      $(`.nx_team.t${team.t} .nx_card`).each((i, cardEl) => {
        updateCard(cardEl, team.lineup[i], team, animate);
        TB.characterRender(s, cardEl.querySelector(".nx_render"), team.lineup[i], { custom_center: [0.5, 0.35] });
      });
    }
  },
});
