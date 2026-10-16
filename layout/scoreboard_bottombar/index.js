// Bottom bar scoreboard: a bar along the bottom of the screen with each
// side's name and info at its ends, then their character art and score, and
// the tournament's logo and a clock between the scores. A pill above it has
// the tournament's name, and a thinner bar under it the phase, match and best
// of. Under each name the handle, pronouns and seed take turns.

// The handle, pronouns and seed, the ones shown, as turns pick them
const rotating = (s, player) => {
  const hidden = (what) => $("body").hasClass(`hd-hide-${what}`);
  return [
    s.settings.show_twitter && !hidden("social") && HD.ui.chip("twitter", player.twitter),
    s.settings.show_pronoun && !hidden("pronouns") && HD.ui.chip("pronoun", player.pronoun),
    s.settings.show_seed && !hidden("seed") && player.seed ? HD.ui.chip("seed", player.seed, "Seed ") : "",
  ];
};

const rotate = (s) => {
  if (s.isTeams) return;
  for (const t of s.teams) t.set(".rotating", turns.pick(rotating(s, t.player)));
};
const turns = HD.turns(6, rotate);

// The state's flag, else the country's (or as location_flag says)
const placeFlags = (s, player) => {
  const which = s.settings.location_flag;
  if (which === "country") return HD.ui.flag(player.country);
  if (which === "state") return HD.ui.flag(player.state);
  if (which === "both") return HD.html`${HD.ui.flag(player.country)}${HD.ui.flag(player.state)}`;
  return HD.ui.flag(player.state && player.state.asset ? player.state : player.country);
};

// The time and time zone, in clock_timezone (or the computer's)
const clock = (settings) => {
  if (!settings.show_clock) return;
  const options = { hour: "2-digit", minute: "2-digit", hour12: !settings.clock_24h, timeZoneName: "short" };
  let parts;
  try {
    parts = new Intl.DateTimeFormat("en-US", {
      ...options,
      timeZone: settings.clock_timezone || undefined,
    }).formatToParts(new Date());
  } catch {
    parts = new Intl.DateTimeFormat("en-US", options).formatToParts(new Date());
  }
  const part = (type) => (parts.find((p) => p.type === type) || {}).value || "";
  const time = `${part("hour")}:${part("minute")}${part("dayPeriod").toLowerCase()}`;
  HD.set(".clock", HD.html`${time}<span class="zone">${part("timeZoneName")}</span>`, { duration: 0.2 });
};

// Which character each side shows when it takes turns
const shown = { 1: 0, 2: 0 };

const showCharacter = (n, fade) => {
  const characters = $(`.p${n} .character_container.cycle .hd_character`).toArray();
  if (characters.length === 0) return;
  shown[n] %= characters.length;
  gsap.to(characters, { autoAlpha: (i) => (i === shown[n] ? 1 : 0), duration: fade ? 0.6 : 0, overwrite: true });
};

HD.layout({
  subscribe: ["score", "game", "tournamentInfo"],

  settings: {
    show_clock: true,
    clock_24h: false,
    // An IANA time zone ("America/New_York"); empty for the computer's
    clock_timezone: "",
    // "best_of" (Best of 3) or "first_to" (First to 2)
    set_length: "best_of",
    // "auto" (the state's, else the country's), "state", "country" or "both"
    location_flag: "auto",
    show_twitter: true,
    show_pronoun: true,
    show_seed: true,
    // The start.gg tournament's logo when it has one, else layout/logo.png
    use_tournament_logo: true,
    // A player's characters take turns every this many seconds; 0 shows
    // them side by side
    character_cycle_seconds: 4,
    // How the bar under it arranges the phase, match and best of: "chips"
    // (a centered chip each), "spread" (phase left, match centered, best of
    // right) or "center" (one centered line)
    info_layout: "chips",
  },

  init(settings) {
    $("body").toggleClass("no_clock", !settings.show_clock).addClass(`info_${settings.info_layout}`);
    clock(settings);
    setInterval(() => clock(settings), 1000);
    if (settings.character_cycle_seconds > 0) {
      HD.every(settings.character_cycle_seconds, () => {
        for (const n of [1, 2]) {
          shown[n] += 1;
          showCharacter(n, true);
        }
      });
    }
  },

  intro(tl) {
    const vars = { duration: 0.35, ease: "power2.out", autoAlpha: 0 };
    tl.from(".bar, .subbar", { yPercent: 110, autoAlpha: 0, duration: 0.5, ease: "power3.out", stagger: 0.05 }, 0)
      .from(".p1.player", { ...vars, x: -40 }, 0.35)
      .from(".p2.player", { ...vars, x: 40 }, "<")
      .from(".center", { autoAlpha: 0, scale: 0.6, duration: 0.35, ease: "back.out(2)" }, "<0.05")
      .from(".pill", { ...vars, y: 20 }, "<0.1")
      .from(".subbar > div", { ...vars, y: -10, stagger: 0.06 }, "<");
  },

  update(s) {
    for (const t of s.teams) {
      const { team, player } = t;
      const losers = team.losers && HD.html`<span class='losers'>L</span>`;

      // Doubles show the team (or its players' names), and its players
      // under it when it has a name
      if (s.isTeams) {
        t.set(".name", HD.html`${t.name}${losers}`);
        t.set(".location", "");
        t.set(".rotating", team.teamName && HD.playerNames(team));
      } else {
        t.set(".name", HD.ui.name(player, team));
        t.set(".location", placeFlags(s, player));
      }

      const pop = !s.first && s.scoreChanged(`team.${t.n}.score`);
      t.set(".score", team.score, {
        after: () =>
          pop && gsap.fromTo(t.sel(".score .text"), { scale: 1.45 }, { scale: 1, duration: 0.4, ease: "back.out(3)" }),
      });

      // A player with several characters shows them one at a time, stacked
      // in the same place; doubles show each player's first side by side
      const container = t.sel(".character_container");
      const count = Object.values(player.character || {}).filter((c) => c && c.codename && _.size(c.assets)).length;
      const cycle = !s.isTeams && count > 1 && s.settings.character_cycle_seconds > 0;
      $(container).toggleClass("cycle", cycle);
      const slide = HD.slideToMiddle(t.n === 1 ? 1 : -1);
      s.characters(container, {
        source: ["score", s.n, "team", t.n],
        slice_character: s.isTeams ? [0, 1] : undefined,
        flip_x: t.n === 2,
        ...slide,
        // They come in hidden, then showCharacter() shows one
        ...(cycle && {
          in: {
            autoAlpha: 0,
            duration: 0,
            onComplete: () => {
              shown[t.n] = 0;
              showCharacter(t.n, true);
            },
          },
        }),
      });
    }
    HD.teamColors(s);
    rotate(s);

    const info = s.data.tournamentInfo || {};
    const logo = (s.settings.use_tournament_logo && info.logo) || "../logo.png";
    s.set(".logo", HD.img(logo));
    s.set(".tournament_name", info.tournamentName);
    const length = s.settings.set_length === "first_to" ? s.score.first_to_text : s.score.best_of_text;
    s.set(".phase", s.score.phase || info.eventName);
    s.set(".match", s.score.match);
    s.set(".best_of", length);
  },
});
