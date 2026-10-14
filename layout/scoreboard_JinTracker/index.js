// Jin's tracker scoreboard: each side's name, chips (seed, Twitter,
// pronouns, location, flag), score and character art on the team's color
// (with text colors that read on it), and a box per game of the best of,
// colored by who won it. noCharacter.html has no character art.

// A team color's brightness band, for data-contrast (see index.css)
const contrast = (color) => {
  const rgb = String(color).match(/\d+/g);
  if (!rgb) return null;
  const intensity = rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114;
  return intensity > 142 ? "light" : intensity > 75 ? "mid" : "dark";
};

// Shows who won each game: the red (team 1) or blue (team 2) box over it
const colorGameBoxes = (s) => {
  for (let game = 1; game <= (s.score.best_of || 0); game += 1) {
    const winner = _.get(s.score, ["games", game, "winner"]);
    $(`.game${game}.p1_won`).toggleClass("unhidden", winner === 1);
    $(`.game${game}.p2_won`).toggleClass("unhidden", winner === 2);
  }
};

HD.layout({
  intro(tl) {
    HD.classIntro(tl);
  },

  update(s) {
    const characters = s.settings.characters !== false;

    for (const t of s.teams) {
      const { n, team, player } = t;
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && "(L)";

      t.set(
        "&.container .name",
        s.isTeams || !characters
          ? HD.text([s.isTeams ? t.name : player.name, losers])
          : HD.html`<span class="sponsor">${player.team}</span>${player.name} ${losers}`,
      );
      t.set("&.container .sponsor_icon", solo.sponsor_logo && HD.html`<div style="background-image: url('${HD.asset(solo.sponsor_logo)}')"></div>`);
      t.set(".flagcountry", solo.country && HD.img(HD.asset(solo.country.asset), "class='flag'"));
      t.set(".seed", solo.seed ? `SEED ${solo.seed}` : "");
      t.set(".pronoun", solo.pronoun);
      t.set(".flagstate", solo.state && solo.state.name && HD.html`<div class="location_logo symbol"></div>${solo.state.name}`);
      t.set(".twitter", solo.twitter && HD.html`<div class="twitter_logo symbol"></div>${solo.twitter}`);
      t.set(".score", team.score);

      // Character art (and its backdrop) in singles
      const character = _.get(player, "character.1.name");
      t.set("&.container .placeholder_container", !s.isTeams && character && HD.html`<div class='placeholder'></div>`);
      $(t.sel("&.character_container")).toggleClass("unhidden", !s.isTeams);
      $(t.sel("&.bg")).toggleClass("unhidden", !s.isTeams);
      if (characters && !s.isTeams) {
        s.characters(t.sel("&.character_container"), {
          source: ["score", s.n, "team", n],
          flip_x: n === 2,
          ...HD.slideToMiddle(n === 1 ? 1 : -1),
        });
      }
    }
    HD.teamColors(s, ["score-bg-color"]);

    // After the team colors are in
    for (const { n } of s.teams) {
      const band = contrast(getComputedStyle(document.querySelector(`.p${n} .score_container`)).backgroundColor);
      if (!band) continue;
      $(`.p${n}.container, .p${n}.chips, .p${n}.under_chips`).attr("data-contrast", band);
      // The light camera border reads on dark colors
      $(`.p${n}.light`).toggleClass("unhidden", !s.isTeams && band === "dark");
    }

    $(".tournament_logo").toggleClass("unhidden", !s.isTeams);
    s.set(".match", s.score.match);
    s.set(".phase", s.score.phase);
    gsap.to(".topleft_container", { duration: 0.5, opacity: s.score.match ? 1 : 0 });
    gsap.to(".topleft_container_small", { duration: 0.5, opacity: s.score.phase ? 1 : 0 });

    // A box per game of the best of, rebuilt when it changes
    const bestOf = s.score.best_of || 0;
    $(".score_boxes").first().toggleClass("unhidden", bestOf > 0);
    if (s.scoreChanged("best_of")) {
      const games = _.range(1, bestOf + 1);
      const row = (box) => HD.html`${games.map(box)}`;
      const after = () => colorGameBoxes(s);
      HD.set(".word.score_boxes", row((i) => HD.html`<div class="game${i} box">GAME ${i}</div>`), { after });
      HD.set(".red.score_boxes", row((i) => HD.html`<div class="game${i} box p1_won hidden"></div>`), { after });
      HD.set(".blue.score_boxes", row((i) => HD.html`<div class="game${i} box p2_won hidden"></div>`), { after });
      HD.set(".dark.score_boxes", row((i) => HD.html`<div class="game${i} box neither_won"></div>`), { after });
    }
    colorGameBoxes(s);
  },
});
