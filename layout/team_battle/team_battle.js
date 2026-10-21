// Shared by the Team Battle layouts, which show the Crew/Team Battle window's
// data (team_battle in docs/layout-data.md). Each page sets its mode,
// HD.page({ mode: "STOCK_POOL" }) or "FIRST_TO":
// - Stock Pool: a player's number is their stocks left, the team's is the
//   stocks the whole team has left.
// - First To: a player's number is the games they won against the current
//   opponent, the team's is how many of their players are still in.
const TB = {
  DEFAULT_COLORS: { 1: "#fe3636", 2: "#2e89ff" },

  // -------------------------------------------------------------------
  // Teams and players

  isStock: () => HD.settings.mode !== "FIRST_TO",

  firstCharacter: (player) =>
    Object.values(_.get(player, "character", {})).find(
      (c) => c && c.codename && c.assets && Object.keys(c.assets).length > 0,
    ),

  // The character's stock icon (settings.json "stock_icon" picks the asset)
  characterIcon(character) {
    if (!character) return null;
    const asset = HD.characterAsset(character, HD.assetSettings("stock_icon").asset_key || "base_files/icon");
    return asset ? HD.asset(asset.asset) : null;
  },

  avatar: (player) => HD.asset(player.avatar) || player.online_avatar || null,

  // A team, with its players in order and the numbers the layouts show.
  // When only some of the players play (team_battle.plays under the number
  // of players), lineup is a slot per play, with the players who played in
  // the order they came in and null for the ones left, and onDeck the
  // others. Otherwise lineup is every player and onDeck is empty.
  team(data, t) {
    const tb = data.team_battle || {};
    const team = _.get(tb, ["team", t]) || {};
    const players = Object.entries(team.player || {})
      .filter(([, p]) => p)
      .sort(([a], [b]) => a - b)
      .map(([key, p]) => {
        const active = team.active_player != null ? String(team.active_player) === key : !!p.active;
        return {
          key,
          data: p,
          path: ["team_battle", "team", t, "player", key],
          name: p.name || "",
          sponsor: p.team || "",
          value: Math.max(Number(p.dynamic_spinner) || 0, 0),
          dead: !!p.dead,
          active,
          // "playing", "out", "on_deck" or "unused" (the team is out without them playing)
          status: p.status || (p.dead ? "out" : active ? "playing" : "on_deck"),
          playOrder: Number(p.play_order) || null,
          character: TB.firstCharacter(p),
        };
      });
    // Players can be given more stocks than the others in the app
    const max = Math.max(Number(tb.battle_value) || 0, ...players.map((p) => p.value), 1);

    const plays = Math.min(Number(tb.plays) || players.length, players.length);
    const limited = plays < players.length;
    const left = Math.max(plays - players.filter((p) => p.dead).length, 0);
    // The stocks of the players who can still play: the ones who played
    // first, then the ones on deck
    const stocks = _.sortBy(
      players.filter((p) => !p.dead),
      (p) => p.playOrder == null,
    )
      .slice(0, left)
      .reduce((sum, p) => sum + p.value, 0);

    let lineup = players;
    let onDeck = [];
    if (limited) {
      const played = _.sortBy(
        players.filter((p) => p.playOrder != null || p.active || p.dead),
        (p) => (p.playOrder == null ? Infinity : p.playOrder),
      );
      lineup = _.range(Math.max(plays, played.length)).map((i) => played[i] || null);
      onDeck = players.filter((p) => !played.includes(p));
    }

    return {
      t,
      name: team.sponsor || "",
      displayName: team.sponsor || `Team ${t}`,
      color: team.color || TB.DEFAULT_COLORS[t],
      logo: HD.asset(team.logo),
      players,
      lineup,
      onDeck,
      limited,
      max,
      score: Number(tb[`team${t}_total-score`]) || 0,
      active: players.find((p) => p.active) || null,
      big: TB.isStock() ? stocks : left,
      bigLabel: TB.isStock() ? "Stocks" : "Left",
    };
  },

  teams: (data) => [TB.team(data, 1), TB.team(data, 2)],

  // -------------------------------------------------------------------
  // Colors and text

  // Team colors as --t1-color and --t2-color
  applyColors(teams) {
    const root = document.documentElement.style;
    for (const team of teams) {
      if (HD.settings.forceDefaultScoreColors) root.removeProperty(`--t${team.t}-color`);
      else root.setProperty(`--t${team.t}-color`, team.color);
    }
  },

  // "Phase · Match", from the Crew/Team Battle window
  phaseMatch: (data) => HD.text([_.get(data, "team_battle.phase"), _.get(data, "team_battle.match")], " · "),

  // What every player starts with, e.g. "3 Stocks each" or "First to 2"
  ruleText(teams) {
    const max = Math.max(teams[0].max, teams[1].max);
    return TB.isStock() ? `${max} ${max === 1 ? "Stock" : "Stocks"} each` : `First to ${max}`;
  },

  // -------------------------------------------------------------------
  // Markup

  // A pip per stock (Stock Pool, with the character's stock icon) or per
  // game to win (First To). Lit: stocks left, or games won.
  pips(player, team) {
    const icon = TB.isStock() ? TB.characterIcon(player.character) : null;
    return _.range(team.max).map(
      (i) =>
        HD.html`<span class="pip ${i < player.value ? "lit" : "spent"}${icon ? " icon" : ""}">${icon && HD.img(icon)}</span>`,
    );
  },

  // Sponsor and tag
  name: (player) =>
    HD.html`${player.sponsor && HD.html`<span class="sponsor">${player.sponsor}</span>`}<span class="tag">${player.name}</span>`,

  // Flag and pronouns
  chips(player) {
    const p = player.data;
    return HD.html`${
      p.country &&
      p.country.asset &&
      HD.html`<span class="chip flag"><img class="flagcountry" src="${HD.asset(p.country.asset)}" />${p.country.code}</span>`
    }${p.pronoun && HD.html`<span class="chip pronoun">${p.pronoun}</span>`}`;
  },

  // The team's logo, or its initial when there's none
  logo: (team) =>
    team.logo
      ? HD.html`<img class="logo_img" src="${team.logo}" />`
      : HD.html`<span class="logo_initial">${Array.from(team.displayName.trim())[0] || "?"}</span>`,

  // Sets an element's markup only when it changed, so images don't load
  // again. Returns whether it did.
  setHtml: (element, html) => HD.build(element, String(html), html),

  // An image's src, hidden without one
  setImage(img, src, hide = "display") {
    if (src) {
      if (img.getAttribute("src") !== src) img.setAttribute("src", src);
      img.style[hide] = "";
    } else {
      img.removeAttribute("src");
      img.style[hide] = hide === "display" ? "none" : "hidden";
    }
  },

  // -------------------------------------------------------------------
  // Animations for changes (not on the first update)

  // A number ticking up or down to its new value, with a pop
  animateNumber(element, value, animate) {
    if (!element) return;
    const old = Number(element.dataset.value);
    element.dataset.value = value;
    if (!animate || isNaN(old) || old === value) {
      element.textContent = value;
      return;
    }
    const counter = { v: old };
    gsap.to(counter, {
      v: value,
      duration: 0.4,
      ease: "power1.out",
      overwrite: true,
      onUpdate: () => (element.textContent = Math.round(counter.v)),
    });
    gsap.fromTo(
      element,
      { scale: 1.45, filter: "brightness(2)" },
      { scale: 1, filter: "brightness(1)", duration: 0.6, ease: "back.out(3)", overwrite: "auto" },
    );
  },

  // A player's pips, the ones that changed flashing
  updatePips(element, player, team, animate) {
    const before = [...element.querySelectorAll(".pip")].map((p) => p.classList.contains("lit"));
    if (!TB.setHtml(element, HD.html`${TB.pips(player, team)}`) || !animate) return;
    element.querySelectorAll(".pip").forEach((pip, i) => {
      const lit = pip.classList.contains("lit");
      if (i >= before.length || before[i] === lit) return;
      if (lit) {
        gsap.fromTo(pip, { scale: 2, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.45, ease: "back.out(2.5)" });
      } else {
        gsap.fromTo(
          pip,
          { scale: 1.6, filter: "brightness(3)" },
          { scale: 1, filter: "brightness(1)", duration: 0.5, ease: "power2.out" },
        );
      }
    });
  },

  // Eliminated: the red X slams onto the card and the card shakes
  setEliminated(card, dead, animate) {
    const was = card.classList.contains("dead");
    card.classList.toggle("dead", dead);
    const x = card.querySelector(".x_mark");
    if (!x) return;
    if (!animate || was === dead) {
      gsap.set(x, { autoAlpha: dead ? 1 : 0, scale: 1, rotate: 0 });
    } else if (dead) {
      gsap.fromTo(
        x,
        { autoAlpha: 0, scale: 3, rotate: -25 },
        { autoAlpha: 1, scale: 1, rotate: 0, duration: 0.3, ease: "power4.in", overwrite: true },
      );
      gsap.fromTo(
        card,
        { x: 0 },
        { keyframes: { x: [0, -10, 9, -6, 4, 0] }, duration: 0.35, delay: 0.28, ease: "none", clearProps: "x" },
      );
    } else {
      gsap.to(x, { autoAlpha: 0, scale: 0.6, duration: 0.3, ease: "power2.in", overwrite: true });
    }
  },

  // A light sweeping across an element's .sweep, which stays inside it
  sweep(sweep, delay = 0) {
    if (!sweep) return;
    gsap.fromTo(
      sweep,
      { autoAlpha: 1, backgroundPosition: "100% 0" },
      {
        backgroundPosition: "0% 0",
        duration: 0.7,
        delay,
        ease: "power2.inOut",
        overwrite: true,
        onComplete: () => gsap.set(sweep, { autoAlpha: 0 }),
      },
    );
  },

  // Active: highlighted, with a sweep across the card when it becomes active
  setActive(card, active, animate) {
    const was = card.classList.contains("active");
    card.classList.toggle("active", active);
    if (!animate || was || !active) return;
    TB.sweep(card.querySelector(".sweep"));
    gsap.fromTo(card, { scale: 1.06 }, { scale: 1, duration: 0.5, ease: "back.out(2)", clearProps: "scale" });
  },

  // A card's character render, none for an empty lineup slot
  characterRender: (s, element, player, options = {}) =>
    s.characters(element, {
      source: player ? player.path : ["team_battle", "no_player"],
      load_settings_path: "render",
      slice_character: [0, 1],
      ...options,
    }),

  // The team's header: name, logo, big number and score
  updateHeader(team, { name, logo, big, bigLabel, score }, animate) {
    HD.set(name, team.displayName);
    TB.setHtml(logo, TB.logo(team));
    TB.animateNumber(big, team.big, animate);
    bigLabel.textContent = team.bigLabel;
    TB.animateNumber(score, team.score, animate);
  },
};
