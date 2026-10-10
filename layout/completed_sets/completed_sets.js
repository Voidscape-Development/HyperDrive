// Shared by the completed sets pages: the sets pulled with "Pull Latest
// Completed Sets" (completed_sets in the program state), most recent first.
// See docs/layout-data.md for what each set holds.

const CS_DEFAULTS = {
  // How many sets to show, at most (0 or less: all the app pulled, up to 10)
  sets_displayed: 10,
  // Sets the winner was expected to finish this many placement rounds below
  // the loser in are marked as upsets (0 turns the marker off)
  upset_threshold: 1,
  upset_label: "UPSET",
  title: "RECENT RESULTS",
  // card.html: seconds each set stays on screen
  card_interval: 6,
  // ticker.html: scrolling speed in pixels per second
  ticker_speed: 90,
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
};

function CSConfig() {
  return _.defaultsDeep({}, hd_settings, CS_DEFAULTS);
}

function CSEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function CSSrc(path) {
  return path ? `../../${String(path).replace(/^\.\//, "")}` : null;
}

function CSValues(object) {
  return Object.entries(object || {})
    .filter(([key, value]) => value)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, value]) => value);
}

// The sets to show, most recent first
function CSSets(config) {
  const sets = CSValues(_.get(data, "completed_sets"));
  const count = Number(config.sets_displayed);
  return count > 0 ? sets.slice(0, count) : sets;
}

function CSIsUpset(set, config) {
  const threshold = Number(config.upset_threshold);
  return threshold > 0 && Number(set.upset_factor) >= threshold;
}

function CSScore(score) {
  return Number(score) < 0 ? "DQ" : CSEscape(score);
}

function CSFlagsHtml(player, config) {
  let html = "";
  const country = _.get(player, "country.asset");
  const state = _.get(player, "state.asset");
  if (config.display.country_flag && country) {
    html += `<img class="cs-flag cs-country-flag" src="${CSEscape(CSSrc(country))}" />`;
  }
  if (config.display.state_flag && state) {
    html += `<img class="cs-flag cs-state-flag" src="${CSEscape(CSSrc(state))}" />`;
  }
  return html ? `<span class="cs-flags">${html}</span>` : "";
}

// Stock icons of every character the player used, in order of first use.
// None when the provider had no character data for the set.
function CSCharactersHtml(player, config) {
  if (!config.display.characters) return "";
  const key = ResolveAssetSetting("stock_icon").asset_key || "base_files/icon";
  const icons = CSValues(player.characters)
    .filter((c) => c.assets && Object.keys(c.assets).length > 0)
    .map((c) => {
      const asset = GetCharacterAsset(key, c);
      if (!asset || !asset.asset) return "";
      return `<img class="cs-character" src="${CSEscape(CSSrc(asset.asset))}" title="${CSEscape(c.name)}" />`;
    })
    .join("");
  return icons ? `<span class="cs-characters">${icons}</span>` : "";
}

function CSPlayerNameHtml(player) {
  const sponsor = player.sponsor
    ? `<span class="cs-sponsor">${CSEscape(player.sponsor)}</span>`
    : "";
  return `${sponsor}<span class="cs-tag">${CSEscape(player.gamertag)}</span>`;
}

// One side of a set: the winner or the loser. Singles show the player;
// teams show the team name, with each player underneath.
function CSSideHtml(set, side, config) {
  const players = CSValues(set[`${side}_team`]);
  const seed = Number(set[`${side}_seed`]);
  const seedHtml =
    config.display.seed && seed > 0 ? `<span class="cs-seed">${seed}</span>` : "";

  let names;
  let characters = "";
  if (players.length > 1) {
    const teamName =
      set[`${side}_team_name`] || players.map((p) => p.gamertag).join(" / ");
    const members = players
      .map(
        (p) => `
          <div class="cs-member">
            ${CSFlagsHtml(p, config)}
            <span class="cs-name">${CSPlayerNameHtml(p)}</span>
            ${CSCharactersHtml(p, config)}
          </div>`,
      )
      .join("");
    names = `
      <div class="cs-team-name"><span class="cs-tag">${CSEscape(teamName)}</span></div>
      <div class="cs-members">${members}</div>`;
  } else {
    const player = players[0] || { gamertag: set[`${side}_team_name`] || "" };
    names = `
      <div class="cs-player">
        ${CSFlagsHtml(player, config)}
        <span class="cs-name">${CSPlayerNameHtml(player)}</span>
      </div>`;
    characters = CSCharactersHtml(player, config);
  }

  return `
    <div class="cs-side cs-${side} ${players.length > 1 ? "cs-teams" : ""}">
      ${seedHtml}
      <div class="cs-names">${names}</div>
      ${characters}
      <span class="cs-score">${CSScore(set[`${side}_score`])}</span>
    </div>`;
}

function CSRoundHtml(set, config) {
  const phase = [set.phase_name, set.phase_id].filter(Boolean).join(" ");
  const parts = [];
  if (config.display.phase && phase) {
    parts.push(`<span class="cs-phase">${CSEscape(phase)}</span>`);
  }
  if (config.display.round && set.round_name) {
    parts.push(`<span class="cs-round-name">${CSEscape(set.round_name)}</span>`);
  }
  return `<div class="cs-round">${parts.join("")}</div>`;
}

function CSUpsetHtml(set, config) {
  if (!config.display.upset || !CSIsUpset(set, config)) return "";
  const factor = config.display.upset_factor
    ? `<span class="cs-upset-factor">${CSEscape(set.upset_factor)}</span>`
    : "";
  return `<span class="cs-upset">${CSEscape(config.upset_label)}${factor}</span>`;
}

// A set: its round, then the winner and the loser
function CSSetHtml(set, config) {
  return `
    <div class="cs-set ${CSIsUpset(set, config) ? "cs-is-upset" : ""}">
      <div class="cs-header">
        ${CSRoundHtml(set, config)}
        ${CSUpsetHtml(set, config)}
      </div>
      ${CSSideHtml(set, "winner", config)}
      ${CSSideHtml(set, "loser", config)}
    </div>`;
}

// Calls render(sets, config) with the sets to show, first and then each
// time they (or the game, for its character icons) change
function CSOnChange(render) {
  Update = async (event) => {
    const changed =
      !event.oldData ||
      !_.isEqual(_.get(event.data, "completed_sets"), _.get(event.oldData, "completed_sets")) ||
      _.get(event.data, "game.codename") != _.get(event.oldData, "game.codename");
    if (changed) {
      const config = CSConfig();
      await render(CSSets(config), config);
    }
  };
}
