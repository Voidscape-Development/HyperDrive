// What the event's completed sets add up to (event_stats in the program
// state, from the Event Stats widget): the characters and stages played, the
// biggest upsets and the players doing better or worse than their seed. Each
// page shows one of them, by the class of its body. See docs/layout-data.md.

const ES_DEFAULTS = {
  characters_displayed: 10,
  stages_displayed: 6,
  upsets_displayed: 6,
  performers_displayed: 5,
  titles: {
    characters: "MOST PLAYED",
    stages: "STAGES",
    upsets: "BIGGEST UPSETS",
    overperformers: "OVERPERFORMING",
    underperformers: "UNDERPERFORMING",
  },
  display: {
    title: true,
    // The number of sets and games under the title
    summary: true,
    win_rate: true,
    seed: true,
    // Seed Performance Rating of over- and underperformers
    spr: true,
    upset_factor: true,
  },
};

// Settings the layout theme's "Event stats" section can change
const ES_THEME = [
  ["characters_displayed", "event_stats", "characters_count", 10],
  ["stages_displayed", "event_stats", "stages_count", 6],
  ["upsets_displayed", "event_stats", "upsets_count", 6],
  ["performers_displayed", "event_stats", "performers_count", 5],
  ["display.summary", "event_stats", "summary_display", true],
  ["display.win_rate", "event_stats", "win_rate_display", true],
  ["display.seed", "event_stats", "seed_display", true],
  ["display.upset_factor", "event_stats", "upset_factor_display", true],
  ["display.spr", "event_stats", "spr_display", true],
];

function ESConfig() {
  return ThemeSettings(_.defaultsDeep({}, hd_settings, ES_DEFAULTS), ES_THEME);
}

function ESEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function ESSrc(path) {
  return path ? `../../${String(path).replace(/^\.\//, "")}` : null;
}

function ESValues(object, count) {
  const values = Object.entries(object || {})
    .filter(([key, value]) => value)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, value]) => value);
  return Number(count) > 0 ? values.slice(0, Number(count)) : values;
}

function ESPage() {
  return ["characters", "stages", "upsets", "performers"].find((page) =>
    document.body.classList.contains(`es-${page}`),
  );
}

function ESTitleHtml(title, stats, config) {
  if (config.display.title === false) return "";
  const summary =
    config.display.summary && stats.sets
      ? `<span class="es-summary">${ESEscape(stats.sets)} sets · ${ESEscape(stats.games)} games</span>`
      : "";
  return `<div class="es-title"><span>${ESEscape(title)}</span>${summary}</div>`;
}

function ESCharacterIcon(character) {
  if (!character || !character.assets || Object.keys(character.assets).length == 0) return "";
  const key = ResolveAssetSetting("stock_icon").asset_key || "base_files/icon";
  const asset = GetCharacterAsset(key, character);
  if (!asset || !asset.asset) return "";
  return `<img class="es-icon" src="${ESEscape(ESSrc(asset.asset))}" />`;
}

// A bar filled to `percent`
function ESBarHtml(percent) {
  const width = Math.max(0, Math.min(100, Number(percent) || 0));
  return `<div class="es-bar"><div class="es-bar-fill" style="width: ${width}%"></div></div>`;
}

function ESCharactersHtml(stats, config) {
  const characters = ESValues(stats.characters, config.characters_displayed);
  const most = Math.max(1, ...characters.map((c) => Number(c.games) || 0));
  const rows = characters
    .map(
      (c, i) => `
      <div class="es-row">
        <span class="es-rank">${i + 1}</span>
        ${ESCharacterIcon(c)}
        <div class="es-main">
          <div class="es-line">
            <span class="es-name">${ESEscape(c.name)}</span>
            <span class="es-value">${ESEscape(c.games)} <small>games · ${ESEscape(c.play_rate)}%</small></span>
          </div>
          ${ESBarHtml((100 * c.games) / most)}
        </div>
        ${
          config.display.win_rate
            ? `<span class="es-chip" title="Games won">${ESEscape(c.win_rate)}% <small>WR</small></span>`
            : ""
        }
      </div>`,
    )
    .join("");
  return ESTitleHtml(config.titles.characters, stats, config) + `<div class="es-rows">${rows}</div>`;
}

function ESStagesHtml(stats, config) {
  const stages = ESValues(stats.stages, config.stages_displayed);
  const most = Math.max(1, ...stages.map((s) => Number(s.games) || 0));
  const cards = stages
    .map(
      (s) => `
      <div class="es-stage">
        <div class="es-stage-image" ${
          s.path ? `style="background-image: url('${ESEscape(ESSrc(s.path))}')"` : ""
        }></div>
        <div class="es-line">
          <span class="es-name">${ESEscape(s.name)}</span>
          <span class="es-value">${ESEscape(s.play_rate)}%</span>
        </div>
        ${ESBarHtml((100 * s.games) / most)}
      </div>`,
    )
    .join("");
  return ESTitleHtml(config.titles.stages, stats, config) + `<div class="es-stages">${cards}</div>`;
}

function ESEntrantHtml(entrant, config) {
  const players = ESValues(entrant.players);
  let name = ESEscape(entrant.name);
  if (players.length == 1) {
    const p = players[0];
    name =
      (p.sponsor ? `<span class="es-sponsor">${ESEscape(p.sponsor)}</span>` : "") +
      `<span class="es-tag">${ESEscape(p.gamertag)}</span>`;
  }
  const seed =
    config.display.seed && entrant.seed
      ? `<span class="es-seed" title="Seed">${ESEscape(entrant.seed)}</span>`
      : "";
  return `<span class="es-entrant">${seed}<span class="es-name">${name}</span></span>`;
}

function ESUpsetsHtml(stats, config) {
  const upsets = ESValues(stats.upsets, config.upsets_displayed);
  const rows = upsets
    .map(
      (u) => `
      <div class="es-upset">
        <div class="es-upset-round">
          <span>${ESEscape([u.phase_name, u.phase_id].filter(Boolean).join(" "))}</span>
          <span>${ESEscape(u.round_name)}</span>
          ${
            config.display.upset_factor
              ? `<span class="es-chip es-accent" title="Upset factor">UF ${ESEscape(u.upset_factor)}</span>`
              : ""
          }
        </div>
        <div class="es-upset-line es-winner">
          ${ESEntrantHtml(u.winner, config)}
          <span class="es-score">${ESEscape(u.winner_score)}</span>
        </div>
        <div class="es-upset-line es-loser">
          ${ESEntrantHtml(u.loser, config)}
          <span class="es-score">${ESEscape(u.loser_score)}</span>
        </div>
      </div>`,
    )
    .join("");
  return ESTitleHtml(config.titles.upsets, stats, config) + `<div class="es-upsets">${rows}</div>`;
}

function ESPerformerRows(list, config) {
  return list
    .map(
      (p) => `
      <div class="es-row">
        <span class="es-rank">${ESEscape(p.placement)}</span>
        <div class="es-main">${ESEntrantHtml(p, config)}</div>
        ${
          config.display.spr
            ? `<span class="es-chip ${p.spr > 0 ? "es-good" : "es-bad"}" title="Seed Performance Rating">${
                p.spr > 0 ? "+" : ""
              }${ESEscape(p.spr)}</span>`
            : ""
        }
      </div>`,
    )
    .join("");
}

function ESPerformersHtml(stats, config) {
  const over = ESValues(stats.overperformers, config.performers_displayed);
  const under = ESValues(stats.underperformers, config.performers_displayed);
  const column = (title, list) =>
    list.length
      ? `<div class="es-column">
          <div class="es-subtitle">${ESEscape(title)}</div>
          <div class="es-rows">${ESPerformerRows(list, config)}</div>
        </div>`
      : "";
  return (
    ESTitleHtml("", stats, { ...config, display: { ...config.display, title: false } }) +
    `<div class="es-columns">${column(config.titles.overperformers, over)}${column(
      config.titles.underperformers,
      under,
    )}</div>`
  );
}

function ESHasData(stats, page) {
  if (page == "characters") return !_.isEmpty(stats.characters);
  if (page == "stages") return !_.isEmpty(stats.stages);
  if (page == "upsets") return !_.isEmpty(stats.upsets);
  return !_.isEmpty(stats.overperformers) || !_.isEmpty(stats.underperformers);
}

LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });
  const page = ESPage();
  const render = {
    characters: ESCharactersHtml,
    stages: ESStagesHtml,
    upsets: ESUpsetsHtml,
    performers: ESPerformersHtml,
  }[page];

  function ShowRows() {
    return gsap.from(".es-row, .es-stage, .es-upset", {
      y: 14,
      autoAlpha: 0,
      duration: 0.3,
      stagger: 0.04,
      ease: "power2.out",
    });
  }

  Update = async (event) => {
    const stats = _.get(event.data, "event_stats") || {};
    const changed =
      !event.oldData ||
      !_.isEqual(stats, _.get(event.oldData, "event_stats")) ||
      _.get(event.data, "game.codename") != _.get(event.oldData, "game.codename") ||
      !_.isEqual(
        _.get(event.data, "layout_theme.values.event_stats"),
        _.get(event.oldData, "layout_theme.values.event_stats"),
      );
    if (!changed) return;
    const config = ESConfig();
    $(".es-container").html(render(stats, config));
    $(".es-container").toggleClass("es-empty", !ESHasData(stats, page));
    if (hd_display.started && hd_display.shown) ShowRows();
  };

  Start = async () => {
    gsap
      .timeline()
      .fromTo(".es-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".es-title, .es-subtitle", { x: -30, autoAlpha: 0, duration: 0.4 }, 0)
      .add(ShowRows(), 0.1);
  };
});
