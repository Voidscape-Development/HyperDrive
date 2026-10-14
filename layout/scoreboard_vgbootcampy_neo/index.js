// VGBootcamp neo scoreboard: each side's name with its bracket side, flag,
// sponsor and score on the team's color (with text colors that read on
// it). A player's Twitter and pronouns, and the match and best of, take
// turns every 9 seconds.

// Remembers which side came from winners, for its (WL) in a grand final
// reset. localStorage can be unavailable (some file:// setups).
const winnersSide = {
  get: () => {
    try {
      return localStorage.getItem("hd-neo-winners-side");
    } catch (e) {
      return null;
    }
  },
  set: (key) => {
    try {
      localStorage.setItem("hd-neo-winners-side", key);
    } catch (e) {}
  },
};

// Text colors that read on a team color, by its brightness: [score and
// Twitter, name, the name's background]
const DARK = "rgb(18, 18, 18, 0.8)";
const DARK_BG = "rgba(18, 18, 18, 0.8)";
const contrast = (intensity) =>
  intensity > 142
    ? [DARK, "white", DARK_BG]
    : intensity > 95
      ? ["white", "white", DARK_BG]
      : intensity <= 80
        ? ["white", DARK, "rgba(255, 255, 255, 0.8)"]
        : null; // In between: as they were

const rotate = (s) => {
  for (const t of s.teams) {
    const { player } = t;
    const shown = !s.isTeams && (player.twitter || player.pronoun);
    $(t.sel("&.twitter_container")).toggleClass("hidden", !shown).toggleClass("unhidden", !!shown);
    if (shown) {
      t.set(".twitter", turns.pick([HD.ui.chip("twitter", player.twitter, "@"), String(player.pronoun || "").toUpperCase()]));
    }
  }
  const text = turns.pick([s.score.match, s.score.best_of && s.score.best_of_text]);
  $(".tournament_container").toggleClass("hidden", !text).toggleClass("unhidden", !!text);
  if (text) s.set(".match", text);
};
const turns = HD.turns(9, rotate);

HD.layout({
  intro(tl) {
    tl.from(".logo", { duration: 0.5, autoAlpha: 0, ease: "power2.inOut" }, 0.5)
      .from(".anim_container_outer", { duration: 1, width: 168, ease: "power2.inOut" }, 1)
      .from(".p1.twitter_container", { duration: 0.75, x: -373, ease: "power4.Out" }, "<25%")
      .from(".p2.twitter_container", { duration: 0.75, x: 373, ease: "power4.Out" }, "<")
      .from(".tournament_container", { duration: 0.75, x: -326, ease: "power4.Out" }, "<")
      .from(".tournament_logo", { opacity: 0, duration: 0.5, ease: "power4.Out" }, "<");
  },

  update(s) {
    // Bracket sides: (L) in losers and (W) for its opponent; with both in
    // losers (a reset), (WL) for the side that came from winners
    const key = (t) => (s.isTeams ? t.name : `${t.player.team}|${t.player.name}`);
    const [a, b] = s.teams;
    let tags = ["", ""];
    if (a.team.losers && b.team.losers) {
      tags = [a, b].map((t) => (key(t) === winnersSide.get() ? "(WL)" : "(L)"));
    } else if (a.team.losers || b.team.losers) {
      tags = [a, b].map((t) => (t.team.losers ? "(L)" : "(W)"));
      const winners = a.team.losers ? b : a;
      if (s.isTeams ? winners.name : winners.player.name) winnersSide.set(key(winners));
    }

    for (const [i, t] of s.teams.entries()) {
      const { team, player } = t;
      if (!team.player || !team.player[1]) continue;
      const solo = s.isTeams ? {} : player;
      // Sponsors as "A B", not "A | B"
      const sponsor = String(player.team || "").replace(/\s*[|/\\]\s*/g, " ");

      t.set(
        "&.container .name",
        s.isTeams ? HD.text([t.name, tags[i]]) : HD.html`<span class="sponsor">${sponsor}</span>${player.name} ${tags[i]}`,
      );
      t.set(".score", team.score);
      // This layout has its own copy of the country flags, as .png
      t.set(
        "&.container .flagcountry",
        solo.country && solo.country.asset && HD.img(solo.country.asset.replace(/\.svg$/, ".png"), "class='flag'"),
      );
      t.set(
        ".sponsor_container",
        solo.sponsor_logo &&
          HD.html`<div class='sponsor_logo' style="background-image: url('${HD.asset(solo.sponsor_logo)}')"></div>`,
      );
    }
    HD.teamColors(s, ["score-bg-color"]);

    for (const { n } of s.teams) {
      const container = document.querySelector(`.p${n}.container`);
      const rgb = getComputedStyle(container).backgroundColor.match(/\d+/g);
      const colors = rgb && contrast(rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114);
      if (!colors) continue;
      const [text, name, nameBg] = colors;
      $(`.p${n}.container .score, .p${n} .twitter`).css("color", text);
      $(`.p${n}.twitter_container`).css("--twitter-logo", text);
      $(`.p${n}.container .name`).css("color", name);
      $(`.p${n}.container .inner_container`).css("background-color", nameBg);
    }

    rotate(s);
  },
});
