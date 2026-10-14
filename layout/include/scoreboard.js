// The scoreboard layouts share: each side's name, score, character icon and
// chips (seed, Twitter, pronouns, flags), or a doubles team's name and its
// players. Pages load it before their script, which runs
// HD.layout(HD.layouts.scoreboard) or builds on it.
HD.layouts.scoreboard = {
  intro(tl) {
    HD.classIntro(tl);
    // The logo snaps from slightly oversized, drawing the eye to the center
    tl.from(".logo.fade", { scale: 1.28, duration: 0.22, ease: "power3.out", transformOrigin: "center center" }, 0);
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      // Doubles show the team (or its players' names) instead of a player
      const solo = s.isTeams ? {} : player;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;

      t.set(".name", s.isTeams ? HD.html`${t.name}${losers}` : HD.ui.name(player, team));
      t.set(".flagcountry", HD.ui.flag(solo.country));
      t.set(".flagstate", HD.ui.flag(solo.state));
      t.set(".sponsor_icon", HD.img(HD.asset(solo.sponsor_logo)));
      t.set(".avatar", HD.img(HD.asset(solo.avatar)));
      t.set(".online_avatar", HD.img(solo.online_avatar));
      t.set(".pronoun", HD.ui.chip("pronoun", solo.pronoun));
      t.set(".seed", HD.ui.chip("seed", solo.seed, "Seed "));
      t.set(".twitter", s.isTeams ? team.teamName && HD.playerNames(team) : HD.ui.chip("twitter", player.twitter));
      t.set(".score", team.score);
      t.set(
        ".sponsor-container",
        !s.isTeams &&
          HD.html`<div class='sponsor-logo' style="background-image: url('${HD.asset(player.sponsor_logo)}')"></div>`,
      );
      s.characters(t.sel(".character_container"), {
        asset_key: "base_files/icon",
        source: ["score", s.n, "team", t.n],
        slice_character: s.isTeams ? [0, 1] : undefined,
        scale_fill_x: true,
        scale_fill_y: true,
        custom_zoom: 1,
      });

      // SF6 online hides the chips when there's nothing in them
      if (!s.isTeams && $(".sf6.online").length > 0) {
        gsap.to(t.sel("&.chips"), { autoAlpha: player.twitter || player.pronoun ? 1 : 0 });
      }
    }
    HD.teamColors(s);

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".event_name", s.data.tournamentInfo.eventName);
    s.set(".match", s.score.match);
    s.set(".phase", HD.text([s.score.phase, s.score.best_of_text], " - "));
  },
};
