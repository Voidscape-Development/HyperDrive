// Shared by the completed sets pages: the sets pulled with "Pull Latest
// Completed Sets" (completed_sets in the program state), most recent first.
// See docs/layout-data.md for what each set holds.
const CS = {
  SETTINGS: {
    // How many sets to show, at most (0 or less: all the app pulled, up to 10)
    sets_displayed: 10,
    // Sets the winner was expected to finish this many placement rounds
    // below the loser in are marked as upsets (0 turns the marker off)
    upset_threshold: 1,
    upset_label: "UPSET",
    title: "RECENT RESULTS",
    // card.html: seconds each set stays on screen
    card_interval: 6,
    // ticker.html: scrolling speed in pixels per second
    ticker_speed: 90,
    // scroll.html: scrolling speed in pixels per second
    scroll_speed: 60,
    display: {
      title: true,
      phase: true,
      round: true,
      seed: true,
      country_flag: true,
      state_flag: true,
      characters: true,
      upset: true,
      upset_factor: true,
    },
  },

  // -------------------------------------------------------------------
  // Sets

  // The values of an object keyed "1", "2"..., in order, without empty ones
  values: (object) =>
    Object.entries(object || {})
      .filter(([, value]) => value)
      .sort(([a], [b]) => a - b)
      .map(([, value]) => value),

  // The sets to show, most recent first
  sets(s) {
    const sets = CS.values(s.data.completed_sets);
    const count = Number(s.settings.sets_displayed);
    return count > 0 ? sets.slice(0, count) : sets;
  },

  // The sets changed, or the game (for their character icons)
  changed: (s) => s.changed("completed_sets") || s.changed("game.codename"),

  isUpset: (set, settings) =>
    Number(settings.upset_threshold) > 0 && Number(set.upset_factor) >= Number(settings.upset_threshold),

  // The title, and whether there's anything to show
  header(s, sets) {
    $(".cs-title")
      .text(s.settings.title)
      .toggle(s.settings.display.title !== false);
    $(".cs-container").toggleClass("cs-empty", sets.length === 0);
  },

  // -------------------------------------------------------------------
  // Markup

  flags(player, display) {
    const country = display.country_flag && _.get(player, "country.asset");
    const state = display.state_flag && _.get(player, "state.asset");
    return (
      (country || state) &&
      HD.html`<span class="cs-flags">${
        country && HD.html`<img class="cs-flag cs-country-flag" src="${HD.asset(country)}" />`
      }${state && HD.html`<img class="cs-flag cs-state-flag" src="${HD.asset(state)}" />`}</span>`
    );
  },

  // Stock icons of every character the player used, in order of first use.
  // None when the provider had no character data for the set.
  characters(player, display) {
    if (!display.characters) return "";
    const key = HD.assetSettings("stock_icon").asset_key || "base_files/icon";
    const icons = CS.values(player.characters)
      .filter((c) => c.assets && Object.keys(c.assets).length > 0)
      .map((c) => {
        const asset = HD.characterAsset(c, key);
        return (
          asset && asset.asset && HD.html`<img class="cs-character" src="${HD.asset(asset.asset)}" title="${c.name}" />`
        );
      })
      .filter(Boolean);
    return icons.length > 0 && HD.html`<span class="cs-characters">${icons}</span>`;
  },

  name: (player) =>
    HD.html`${player.sponsor && HD.html`<span class="cs-sponsor">${player.sponsor}</span>`}<span class="cs-tag">${player.gamertag}</span>`,

  // One side of a set, the winner or the loser: the player, or a team's
  // name with each player under it
  side(set, side, display) {
    const players = CS.values(set[`${side}_team`]);
    const seed = Number(set[`${side}_seed`]);
    const teams = players.length > 1;
    const player = players[0] || { gamertag: set[`${side}_team_name`] || "" };
    const score = Number(set[`${side}_score`]) < 0 ? "DQ" : set[`${side}_score`];

    const names = teams
      ? HD.html`
        <div class="cs-team-name"><span class="cs-tag">${set[`${side}_team_name`] || players.map((p) => p.gamertag).join(" / ")}</span></div>
        <div class="cs-members">${players.map(
          (p) => HD.html`
            <div class="cs-member">
              ${CS.flags(p, display)}
              <span class="cs-name">${CS.name(p)}</span>
              ${CS.characters(p, display)}
            </div>`,
        )}</div>`
      : HD.html`
        <div class="cs-player">
          ${CS.flags(player, display)}
          <span class="cs-name">${CS.name(player)}</span>
        </div>`;

    return HD.html`
      <div class="cs-side cs-${side} ${teams ? "cs-teams" : ""}">
        ${display.seed && seed > 0 && HD.html`<span class="cs-seed">${seed}</span>`}
        <div class="cs-names">${names}</div>
        ${!teams && CS.characters(player, display)}
        <span class="cs-score">${score}</span>
      </div>`;
  },

  // A set: its round (and upset marker), then the winner and the loser
  set(set, settings) {
    const display = settings.display;
    const phase = HD.text([set.phase_name, set.phase_id]);
    const upset = display.upset && CS.isUpset(set, settings);
    return HD.html`
      <div class="cs-set ${CS.isUpset(set, settings) ? "cs-is-upset" : ""}">
        <div class="cs-header">
          <div class="cs-round">${display.phase && phase && HD.html`<span class="cs-phase">${phase}</span>`}${
            display.round && set.round_name && HD.html`<span class="cs-round-name">${set.round_name}</span>`
          }</div>
          ${
            upset &&
            HD.html`<span class="cs-upset">${settings.upset_label}${
              display.upset_factor && HD.html`<span class="cs-upset-factor">${set.upset_factor}</span>`
            }</span>`
          }
        </div>
        ${CS.side(set, "winner", display)}
        ${CS.side(set, "loser", display)}
      </div>`;
  },
};
