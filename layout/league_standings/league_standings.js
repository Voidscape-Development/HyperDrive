// The standings of the league (circuit) the event is part of, or the one set
// in the Event Stats widget: league in the program state. Players on the
// scoreboard (?scoreboardNumber=N, 1 by default) are highlighted. See
// docs/layout-data.md.

const LS_DEFAULTS = {
  players_displayed: 16,
  display: {
    logo: true,
    sponsor: true,
    // Highlights the players on the scoreboard
    on_stream: true,
  },
  labels: {
    points: "PTS",
    players: "{0} players",
  },
};

function LSEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function LSValues(object, count) {
  const values = Object.entries(object || {})
    .filter(([key, value]) => value)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, value]) => value);
  return Number(count) > 0 ? values.slice(0, Number(count)) : values;
}

// Gamertags of the players on the scoreboard, lowercase
function LSOnStream(state) {
  const teams = _.get(state, `score.${window.scoreboardNumber}.team`) || {};
  const names = [];
  Object.values(teams).forEach((team) =>
    Object.values((team && team.player) || {}).forEach((p) => {
      if (p && p.name) names.push(String(p.name).toLowerCase());
    }),
  );
  return names;
}

function LSHtml(league, state, config) {
  const onStream = config.display.on_stream ? LSOnStream(state) : [];
  const logo =
    config.display.logo && league.logo ? `<img class="ls-logo" src="${LSEscape(league.logo)}" />` : "";
  const standings = LSValues(league.standings, config.players_displayed);
  const rows = standings
    .map((p) => {
      const sponsor =
        config.display.sponsor && p.sponsor
          ? `<span class="ls-sponsor">${LSEscape(p.sponsor)}</span>`
          : "";
      const highlighted = onStream.includes(String(p.gamertag || "").toLowerCase());
      return `
        <div class="ls-row ${highlighted ? "ls-on-stream" : ""}">
          <span class="ls-rank">${LSEscape(p.placement)}</span>
          <span class="ls-name">${sponsor}<span class="ls-tag">${LSEscape(p.gamertag)}</span></span>
          <span class="ls-points">${LSEscape(p.points)} <small>${LSEscape(config.labels.points)}</small></span>
        </div>`;
    })
    .join("");
  return `
    <div class="ls-header">
      ${logo}
      <div class="ls-heading">
        <div class="ls-title">${LSEscape(league.name)}</div>
        <div class="ls-subtitle">${LSEscape(String(config.labels.players).replace("{0}", league.players ?? ""))}</div>
      </div>
    </div>
    <div class="ls-rows" style="grid-template-rows: repeat(${Math.max(1, Math.ceil(standings.length / 2))}, auto)">${rows}</div>`;
}

LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  function ShowRows() {
    return gsap.from(".ls-row", { x: -20, autoAlpha: 0, duration: 0.3, stagger: 0.03 });
  }

  Update = async (event) => {
    const league = _.get(event.data, "league") || {};
    const changed =
      !event.oldData ||
      !_.isEqual(league, _.get(event.oldData, "league")) ||
      !_.isEqual(LSOnStream(event.data), LSOnStream(event.oldData));
    if (!changed) return;
    const config = _.defaultsDeep({}, hd_settings, LS_DEFAULTS);
    $(".ls-container").html(LSHtml(league, event.data, config));
    $(".ls-container").toggleClass("ls-empty", _.isEmpty(league.standings));
  };

  Start = async () => {
    gsap
      .timeline()
      .fromTo(".ls-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".ls-header", { y: -20, autoAlpha: 0, duration: 0.4 }, 0)
      .add(ShowRows(), 0.1);
  };
});
