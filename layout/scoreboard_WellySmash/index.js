// Welly's Smash scoreboard: each side's name, flags, Twitter,
// seed and score, the games won as bubbles between them, and the
// commentators on index_com.html
HD.layout({
  intro(tl) {
    tl.from(".mask", { width: 0, duration: 1, ease: "power2.inOut" }, 0).from(
      ".doubles .info",
      { opacity: 0, duration: 0.5, ease: "power2.inOut" },
      0.8,
    );
  },

  update(s) {
    const flag = (place) => place && place.asset && HD.html`<img class='flag' src='${HD.asset(place.asset)}' />`;
    const losers = (team) => team.losers && HD.html`<span class='losers'>L</span>`;

    for (const { n, team, player, name } of s.teams) {
      if (!player.name) continue;
      const sel = `.t${n}.p1`;
      // Doubles show the team's name, and none of the player's info
      const solo = s.isTeams ? {} : player;

      HD.set(
        `.t${n}.container .name`,
        s.isTeams
          ? HD.html`${name} ${losers(team)}`
          : HD.html`<span class="sponsor">${player.team}</span>${player.name} ${losers(team)}`,
      );
      HD.set(`${sel} .pronoun`, solo.pronoun);
      HD.set(`${sel} .flagcountry`, flag(solo.country));
      HD.set(`${sel} .flagstate`, flag(solo.state));
      HD.set(`${sel} .twitter`, HD.ui.chip("twitter", solo.twitter));
      HD.set(`${sel} .seed`, player.seed ? `Seed ${player.seed}` : "");
      HD.set(`${sel} .score`, team.score);
      HD.set(`.t${n} .doubles_score`, team.score);
      HD.set(`${sel} .sponsor-container`, solo.sponsor_logo && HD.ui.sponsorLogo(solo.sponsor_logo));
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".info.material_container .phase", HD.text([s.data.tournamentInfo.eventName, s.score.phase], " - "));
    s.set(".info.material_container .tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".singles .match", s.score.match);

    // A bubble per game of the best of: team 1's wins fill from the top,
    // team 2's from the bottom. Kept in place, so their colors transition.
    const bestOf = s.score.best_of || 0;
    const bubbles = document.querySelector(".score-bubbles-container");
    const middle = document.querySelector(".middle_container");
    if (bubbles && middle) {
      while (bubbles.children.length < bestOf) bubbles.appendChild(Object.assign(document.createElement("div"), { className: "score-bubble" }));
      while (bubbles.children.length > bestOf) bubbles.lastChild.remove();
      const [won1, won2] = s.teams.map((t) => t.team.score || 0);
      [...bubbles.children].forEach((bubble, i) => {
        bubble.classList.toggle("p1", i < won1);
        bubble.classList.toggle("p2", i >= bestOf - won2);
      });
      Object.assign(middle.style, bestOf ? { justifyContent: "unset", top: "10px" } : { justifyContent: "center", top: "0" });
    }

    HD.commentators(s, ".com_container", ["name", "pronoun"]);
  },
});
