// Nexus - Battle: the in-game overlay for a Crew/Team Battle, in the style of
// Nexus - Teams Overview. At the top, each team's logo, stocks (or players)
// left and short name, the team scores around the tournament logo, and a
// track of the team's plays under it (used ones slashed, the one playing
// lit). At the bottom right, the matchup: each team's player playing, with
// their character and stocks or games won. Uses the Team Battle layouts'
// team_battle.js.

// ---------------------------------------------------------------------
// Markup

const topSide = (t) => HD.html`
  <div class="nb_side t${t}">
    <div class="nb_logo logo"></div>
    <div class="nb_count">
      <div class="nb_big"></div>
      <div class="nb_short"></div>
    </div>
  </div>`;

const matchRow = (t) => HD.html`
  <div class="nb_row t${t}">
    <div class="nb_row_inner">
      <div class="nb_tag"></div>
      <div class="nb_stocks pips"></div>
      <div class="nb_char"><img /></div>
    </div>
    <div class="sweep"></div>
  </div>`;

// ---------------------------------------------------------------------
// Teams

// "06": the big numbers have two digits
const twoDigits = (n) => String(n).padStart(2, "0");

// Words left out of a team's initials
const MINOR_WORDS = new Set(["of", "the", "and", "at", "de", "&", "-"]);

// A short name for the team under its number: the name when it's short,
// else its initials ("University of South Carolina Upstate": "USCU")
function shortName(name) {
  const trimmed = name.trim();
  if (trimmed.length <= 8) return trimmed;
  const words = trimmed.split(/\s+/).filter((w) => !MINOR_WORDS.has(w.toLowerCase()));
  if (words.length < 2) return trimmed;
  return words
    .map((w) => Array.from(w)[0])
    .join("")
    .toUpperCase()
    .slice(0, 6);
}

// A slot per play (or per player when everyone plays): slashed once its
// player is out, lit while they play
function updateTrack(team) {
  const track = document.querySelector(`.nb_track.t${team.t}`);
  HD.build(track, team.lineup.length, () => team.lineup.map(() => HD.html`<div class="nb_slot"></div>`));
  track.querySelectorAll(".nb_slot").forEach((slot, i) => {
    const p = team.lineup[i];
    slot.classList.toggle("out", !!p && p.dead);
    slot.classList.toggle("playing", !!p && p.active && !p.dead);
  });
}

// Which player each team's row shows, to slide the next one in
const shownKeys = {};

function updateRow(team, animate) {
  const row = document.querySelector(`.nb_row.t${team.t}`);
  // The player playing, none while the team picks who's next
  const p = team.active && !team.active.dead ? team.active : null;
  const swapped = shownKeys[team.t] !== (p ? p.key : null);
  shownKeys[team.t] = p ? p.key : null;

  // Out once every player is out or didn't get to play
  const out = team.players.length > 0 && team.players.every((pl) => pl.dead || pl.status === "unused");
  row.classList.toggle("picking", !p);
  HD.set(row.querySelector(".nb_tag"), p ? TB.name(p) : out ? "Team out" : "Picking…");
  TB.setImage(row.querySelector(".nb_char img"), p && TB.characterIcon(p.character), "visibility");
  const stocks = row.querySelector(".nb_stocks");
  if (p) TB.updatePips(stocks, p, team, animate && !swapped);
  else TB.setHtml(stocks, "");

  if (animate && swapped) {
    // The next player comes in
    gsap.fromTo(
      row.querySelector(".nb_row_inner"),
      { x: 60, autoAlpha: 0 },
      { x: 0, autoAlpha: 1, duration: 0.45, ease: "power3.out", overwrite: true },
    );
    if (p) TB.sweep(row.querySelector(".sweep"), 0.15);
  }
}

// ---------------------------------------------------------------------
// The layout

HD.layout({
  subscribe: ["team_battle", "score", "game", "tournamentInfo", "commentary"],
  init() {
    HD.render(
      "#battle",
      HD.html`
        <div class="nb_top">
          <div class="nb_bar">
            ${topSide(1)}
            <div class="nb_center">
              <div class="nb_diamond t1"><span class="nb_score"></span></div>
              <img class="nb_emblem" src="../logo.png" onerror="this.style.visibility='hidden'" />
              <div class="nb_diamond t2"><span class="nb_score"></span></div>
            </div>
            ${topSide(2)}
          </div>
          <div class="nb_tracks"><div class="nb_track t1"></div><div class="nb_track t2"></div></div>
        </div>
        <div class="nb_match">${matchRow(1)}${matchRow(2)}</div>`,
    );
  },

  intro(tl) {
    const ease = "power3.out";
    tl.from(".nb_bar", { duration: 0.5, y: -110, ease }, 0)
      .from(".nb_emblem", { duration: 0.45, scale: 0, ease: "back.out(2)" }, 0.3)
      .from(".nb_diamond", { duration: 0.4, scale: 0, stagger: 0.08, ease: "back.out(2)" }, 0.4)
      .from(".nb_slot", { duration: 0.3, scale: 0, autoAlpha: 0, stagger: 0.03, ease: "back.out(2)" }, 0.55)
      .from(".nb_row", { duration: 0.5, x: 340, stagger: 0.1, ease }, 0.3);
  },

  update(s) {
    const teams = TB.teams(s.data);
    const animate = !s.first;
    TB.applyColors(teams);

    for (const team of teams) {
      const side = document.querySelector(`.nb_side.t${team.t}`);
      TB.setHtml(side.querySelector(".nb_logo"), TB.logo(team));
      HD.set(side.querySelector(".nb_short"), shortName(team.displayName));
      const big = side.querySelector(".nb_big");
      if (big.dataset.value !== String(team.big)) {
        big.dataset.value = team.big;
        big.textContent = twoDigits(team.big);
        if (animate) gsap.fromTo(big, { scale: 1.35 }, { scale: 1, duration: 0.45, ease: "back.out(3)" });
      }
      document.querySelector(`.nb_diamond.t${team.t} .nb_score`).textContent = team.score;
      updateTrack(team);
      updateRow(team, animate);
    }
  },
});
