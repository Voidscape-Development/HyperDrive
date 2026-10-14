// 4:3 scoreboard: the teams in the side bars, a box per player with their
// info and character (the second box closes in singles). The cameras pages
// show character icons instead of art.
HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  intro(tl) {
    const vars = { duration: 1, ease: "power2.inOut" };
    // One-side pages bring both sides in from the right
    const oneSide = document.body.classList.contains("one-side-layout");
    tl.from(".left .container:not(.cameras)", { ...vars, x: oneSide ? "+100%" : "-100%" }, 0)
      .from(".right .container:not(.cameras)", { ...vars, x: "+100%" }, 0)
      .from(".score", { ...vars, autoAlpha: 0 }, 0)
      .from(".left .character_container:not(.cameras)", { ...vars, x: "+50%" }, 0)
      .from(".right .character_container:not(.cameras)", { ...vars, x: oneSide ? "+50%" : "-50%" }, 0)
      .from(".container.top", { ...vars, y: "-100%" }, 0)
      .from(".container.bottom", { ...vars, y: "+100%" }, 0);
  },

  update(s) {
    const cameras = $(".cameras").length > 0;

    for (const { n, team } of s.teams) {
      const side = `.t${n}`;
      HD.set(`${side} .score`, team.score);
      // The second player's box closes in singles
      gsap.to(`${side} .p2.container`, {
        height: _.size(team.player) === 1 ? 0 : "420px",
        duration: s.first ? 0 : 1,
      });

      Object.values(team.player).forEach((player, i) => {
        if (!player) return;
        const sel = `${side} .p${i + 1}`;
        HD.set(`${sel} .name`, HD.html`<span class="sponsor">${player.team}</span>${player.name}`);
        HD.set(`${sel} .pronoun`, player.pronoun);
        HD.set(`${sel} .seed`, player.seed ? `Seed ${player.seed}` : "");
        HD.set(`${sel} .flagcountry`, HD.ui.flag(player.country, "flagname"));
        HD.set(`${sel} .flagstate`, HD.ui.flag(player.state, "flagname"));
        HD.set(`${sel} .twitter`, HD.ui.chip("twitter", player.twitter));
        HD.set(
          `${sel} .sponsor_logo`,
          HD.html`<div class='sponsor_logo' style="background-image: url('${HD.asset(player.sponsor_logo)}')"></div>`,
        );
        s.characters(`${sel}.container .character_container`, {
          source: ["score", s.n, "team", n, "player", i + 1],
          ...(cameras
            ? { asset_key: ["base_files/icon"], scale_fill_x: true, scale_fill_y: true, custom_zoom: 1 }
            : { flip_x: n === 2 }),
        });
      });
    }
    HD.teamColors(s, ["score-bg-color"]);

    s.set(".info.container.top", HD.text([s.data.tournamentInfo.tournamentName, s.score.phase], " | "));
    s.set(".match", HD.text([s.score.match, s.score.best_of_text], " | "));
  },
});
