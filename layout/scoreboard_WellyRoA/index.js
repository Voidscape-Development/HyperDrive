// Welly's Rivals of Aether scoreboard: each side's name (uppercase), flags,
// Twitter, seed, score and character, and the match info
HD.layout({
  intro(tl) {
    tl.from(".mask", { width: 0, duration: 1, ease: "power2.inOut" }, 0).from(
      ".doubles .info",
      { opacity: 0, duration: 0.5, ease: "power2.inOut" },
      0.8,
    );
  },

  update(s) {
    for (const { n, team, player, name } of s.teams) {
      if (!team.player || !team.player[1]) continue;
      const sel = `.t${n}.p1`;
      // Doubles show the team's name, and none of the player's info
      const solo = s.isTeams ? {} : player;
      const upper = (text) => String(text || "").toUpperCase();
      const flag = (place) => place && place.asset && HD.html`<img class='flag' src='${HD.asset(place.asset)}' />`;

      HD.set(
        `.t${n}.container .name`,
        s.isTeams
          ? HD.text([upper(name), team.losers && "(L)"])
          : HD.html`<span class="sponsor">${upper(player.team)}</span>${upper(player.name)} ${team.losers && "(L)"}`,
      );
      HD.set(`${sel} .pronoun`, solo.pronoun);
      HD.set(`${sel} .flagcountry`, flag(solo.country));
      HD.set(`${sel} .flagstate`, flag(solo.state));
      HD.set(`${sel} .twitter`, HD.ui.chip("twitter", solo.twitter));
      HD.set(`${sel} .seed`, player.seed ? `Seed ${player.seed}` : "");
      HD.set(`${sel} .score`, team.score);
      HD.set(`.t${n} .doubles_score`, team.score);
      HD.set(`${sel} .sponsor-container`, solo.sponsor_logo && HD.ui.sponsorLogo(solo.sponsor_logo));

      s.characters(`.p${n}.character`, { source: ["score", s.n, "team", n], ...HD.slideToMiddle(n === 1 ? 1 : -1) });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".info.material_container .phase", HD.text([s.data.tournamentInfo.eventName, s.score.phase], " - "));
    s.set(".info.material_container .tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".singles .match", s.score.match);
    s.set(".singles .best_of", s.score.best_of_text);
  },
});
