// Simple scoreboard: a bar per player (two per team in doubles, under the
// team names) and the match info
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    const ease = "power2.inOut";
    tl.from(".container", { duration: 1, opacity: 0, x: -40, ease }, 0)
      .from(".twitter-container", { duration: 1, opacity: 0, x: 80, ease }, 0)
      .from(".mask", { width: 0, duration: 1, ease }, 0)
      .from(".doubles .info", { opacity: 0, duration: 0.5, ease }, 0.8);
  },

  update(s) {
    // Singles and doubles have their own bars: switch when it changes
    if (s.scoreChanged((score) => _.size(score.team[1].player))) {
      const [from, to] = s.isTeams ? [".singles", ".doubles"] : [".doubles", ".singles"];
      const ease = "power2.inOut";
      gsap
        .timeline()
        .fromTo(`body > ${from}`, { opacity: 1 }, { duration: 0.2, opacity: 0, ease })
        .fromTo(`body > ${to}`, { opacity: 0 }, { duration: 0.2, opacity: 1, ease });
    }

    const flag = (place) =>
      place &&
      place.asset &&
      HD.html`<div class='flagname'>${place.code}</div><img class='flag' src='${HD.asset(place.asset)}' />`;

    for (const { n, team, name } of s.teams) {
      HD.set(`.info.doubles.t${n} .team_name`, name + (team.losers ? " [L]" : ""));
      HD.set(`.t${n} .doubles_score`, team.score);

      Object.values(team.player).forEach((player, i) => {
        if (!player) return;
        const sel = `.t${n}.p${i + 1}`;
        HD.set(
          `${sel} .name`,
          HD.html`<span class="sponsor">${player.team}</span>${player.name}${!s.isTeams && team.losers && " [L]"}`,
        );
        HD.set(`${sel} .pronoun`, player.pronoun);
        HD.set(`${sel} .flagcountry`, flag(player.country));
        HD.set(`${sel} .flagstate`, flag(player.state));
        HD.set(`${sel} .twitter`, HD.ui.chip("twitter", player.twitter));
        HD.set(`${sel} .score`, s.isTeams ? "" : team.score);
        HD.set(`${sel} .sponsor-container`, HD.ui.sponsorLogo(player.sponsor_logo));
      });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".info.material_container .phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
    s.set(".info.material_container .tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".info.material_container .match", s.score.match);
  },
});
