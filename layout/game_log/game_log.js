// Game log: the games of the set on the scoreboard (score.N.games, from the
// Games window), one card each: its stage, both sides' characters, who won
// and the score after it. The game being played is marked, and the games
// left to play are outlined. Pages pick a view: "strip" (a row), "column"
// or "recap" (full screen, with each character's record in the set).

// The games in order, without the ones left over once the set is decided
const gameList = (score, settings) => {
  const games = Object.values((score && score.games) || {})
    .filter(Boolean)
    .sort((a, b) => a.game - b.game);
  if (!settings.hide_after_decided || games.length === 0) return games;
  const needed = Math.ceil((Number(score.best_of) || games.length) / 2);
  const decided = games.findIndex((g) => g.scoreAfter && Math.max(g.scoreAfter[1], g.scoreAfter[2]) >= needed);
  return decided < 0 ? games : games.slice(0, decided + 1);
};

const played = (game) => game.winner !== null && game.winner !== undefined;

// A character's image under key (the stock icon, or the full art)
const characterImage = (character, key) => {
  if (!character || !_.size(character.assets)) return null;
  const asset = HD.characterAsset(character, key);
  return asset && asset.asset ? asset : null;
};

const iconKey = () => HD.assetSettings("stock_icon").asset_key || "base_files/icon";

// A team's characters in a game: their stock icons
const icons = (game, team) =>
  (_.get(game, ["characterData", team]) || []).map((c) => {
    const asset = characterImage(c, iconKey());
    return asset
      ? HD.html`<img class="icon" src="${HD.asset(asset.asset)}" title="${c.display_name || c.name}" />`
      : HD.html`<div class="icon icon_empty"></div>`;
  });

// A team's characters in a game: their full art, framed around their eyes
const portraits = (game, team) =>
  (_.get(game, ["characterData", team]) || []).map((c) => {
    const asset = characterImage(c, ["full", "portrait"]);
    if (!asset) return HD.html`<div class="portrait portrait_empty"></div>`;
    const size = asset.image_size || {};
    const eyes = asset.eyesight || {};
    const at = (axis) => (size[axis] && eyes[axis] ? `${Math.round((eyes[axis] / size[axis]) * 100)}%` : "50%");
    return HD.html`<div class="portrait" style="background-image: url('${HD.asset(asset.asset)}'); background-position: ${at("x")} ${at("y")}"></div>`;
  });

const stageName = (game) => game.stageData && (game.stageData.display_name || game.stageData.name);

const stageImage = (game) =>
  game.stageData && game.stageData.path
    ? HD.html`<div class="stage" style="background-image: url('${HD.asset(game.stageData.path)}')"></div>`
    : HD.html`<div class="stage stage_empty"></div>`;

// What a game's card is: won by a team, a draw, being played or to play
const state = (game) => {
  if (game.winner === 1 || game.winner === 2) return `won won_${game.winner}`;
  if (game.winner === 0) return "draw";
  return game.current ? "current" : "upcoming";
};

const scoreAfter = (game) => game.scoreAfter && `${game.scoreAfter[1]}–${game.scoreAfter[2]}`;

const label = (game, settings) => {
  if (game.winner === 0) return settings.draw_label;
  if (game.current && !played(game)) return settings.current_label;
  return scoreAfter(game);
};

// A game's card in the strip and the column
const card = (game, s) => HD.html`
  <div class="game ${state(game)}">
    ${stageImage(game)}
    <div class="number">${s.settings.game_label} ${game.game}</div>
    <div class="sides">
      <div class="side t1">${icons(game, 1)}</div>
      <div class="side t2">${icons(game, 2)}</div>
    </div>
    <div class="result">${label(game, s.settings)}</div>
  </div>`;

// A game's card in the recap: the stage's picture and name, both sides'
// art, and the score after it
const recapCard = (game, s) => HD.html`
  <div class="game ${state(game)}">
    <div class="stage_box">
      ${stageImage(game)}
      <div class="number">${s.settings.game_label} ${game.game}</div>
      ${s.settings.show_stage_name && stageName(game) && HD.html`<div class="stage_name">${stageName(game)}</div>`}
    </div>
    <div class="sides">
      <div class="side t1">${portraits(game, 1)}</div>
      <div class="side t2">${portraits(game, 2)}</div>
    </div>
    <div class="result">${label(game, s.settings) || ""}</div>
  </div>`;

// Each character a team played, with the games they won and lost with it
const records = (games, team) => {
  const byName = new Map();
  for (const game of games.filter(played)) {
    for (const c of _.get(game, ["characterData", team]) || []) {
      if (!c || !c.codename) continue;
      const record = byName.get(c.codename) || { character: c, won: 0, lost: 0 };
      if (game.winner === team) record.won += 1;
      else if (game.winner !== 0) record.lost += 1;
      byName.set(c.codename, record);
    }
  }
  return [...byName.values()];
};

const recordRow = ({ character, won, lost }) => {
  const asset = characterImage(character, iconKey());
  return HD.html`
    <div class="record">
      ${asset && HD.html`<img class="icon" src="${HD.asset(asset.asset)}" />`}
      <span class="record_name">${character.display_name || character.name}</span>
      <span class="record_score">${won}–${lost}</span>
    </div>`;
};

HD.layout({
  subscribe: ["score", "game", "tournamentInfo"],

  settings: {
    // "strip", "column" or "recap"; each page sets its own
    view: "strip",
    // Leave out the games after the one that decided the set
    hide_after_decided: true,
    // Outline the games left to play (strip and column)
    show_upcoming: true,
    show_stage_name: true,
    game_label: "Game",
    current_label: "Now",
    draw_label: "Draw",
    // recap: each character's games won and lost in the set
    show_records: true,
  },

  init(settings) {
    $("body").addClass(`view_${settings.view}`).toggleClass("no_upcoming", !settings.show_upcoming);
  },

  intro(tl) {
    tl.from(".header > *", { autoAlpha: 0, y: -20, duration: 0.35, ease: "power2.out", stagger: 0.05 }, 0)
      .from(".game", { autoAlpha: 0, y: 20, duration: 0.3, ease: "power2.out", stagger: 0.07 }, 0.1)
      .from(".records > *", { autoAlpha: 0, y: 20, duration: 0.3, ease: "power2.out", stagger: 0.1 }, "<0.2");
  },

  update(s) {
    HD.teamColors(s);
    const games = gameList(s.score, s.settings);
    const recap = s.settings.view === "recap";

    // The cards again when a game changed; a game just won pops
    const before = _.keyBy(gameList(_.get(s.old, ["score", s.n]), s.settings), "game");
    const built = HD.build(".games", [games, _.get(s.data, "game.codename")], () =>
      games.map((g) => (recap ? recapCard(g, s) : card(g, s))),
    );
    $(".games").toggleClass("empty", games.length === 0);
    if (built && !s.first) {
      games.forEach((g, i) => {
        if (played(g) && !played(before[g.game] || {})) {
          gsap.from($(".games .game").eq(i), { scale: 1.15, duration: 0.45, ease: "back.out(3)" });
        }
      });
    }

    if (!recap) return;

    const info = s.data.tournamentInfo || {};
    s.set(".tournament_name", info.tournamentName);
    s.set(".round", HD.text([s.score.phase, s.score.match, s.score.best_of_text], " · "));
    for (const t of s.teams) {
      t.set(".name", s.isTeams ? t.name : HD.ui.name(t.player, t.team));
      t.set(".score", t.team.score);
      if (s.settings.show_records) {
        HD.build(t.sel("&.records"), [records(games, t.n), _.get(s.data, "game.codename")], () =>
          records(games, t.n).map(recordRow),
        );
      }
    }
    $(".records").toggle(s.settings.show_records);
  },
});
