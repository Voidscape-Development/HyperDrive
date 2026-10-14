// Team versus scoreboard: each team's identity and score, its players as
// cards (name, chips, avatar, character icons) and the stages played down
// the middle. settings.json's main_icon, secondary_icon and tertiary_icon
// pick the icons; a card only has the ones with an asset_key.

// A card's character icon slots: [setting, icon class, label class]
const SLOTS = [
  ["main_icon", "main_icon_bg", "char_name"],
  ["secondary_icon", "secondary_icon_bg", "char_meta"],
  ["tertiary_icon", "tertiary_icon_bg", "char_meta"],
];

const playerCard = (slots) => HD.html`
  <div class="player container">
    <div class="name">
      <div class="name_row"><div class="team_name"></div><div class="sponsor_icon"></div></div>
      <div class="player_chips"></div>
    </div>
    <div class="char_icons">
      ${slots.map(
        ([, icon, label], i) =>
          HD.html`<div class="char_slot${i === 0 ? " main_slot" : ""}"><div class="char_icon_bg ${icon}"></div><div class="char_label ${label}"></div></div>`,
      )}
    </div>
    <img class="player_avatar" />
  </div>`;

const stageRow = ([game, stage]) => HD.html`
  <div class="stage_row${!stage.codename && " empty"}" data-game="${game}">
    <div class="win_indicator t1${stage.tie ? " tie" : !!stage.t1_win && " won"}">${stage.tie && "="}</div>
    <div class="stage_content">
      <div class="stage_icon" style="${stage.path && `background-image: url("${HD.asset(stage.path.replace(/^\.\//, ""))}")`}"></div>
      <div class="stage_name">${stage.display_name || stage.name || stage.codename}</div>
    </div>
    <div class="win_indicator t2${stage.tie ? " tie" : !!stage.t2_win && " won"}">${stage.tie && "="}</div>
  </div>`;

HD.layout({
  intro(tl) {
    const ease = "power2.out";
    const cards = (side) => [...document.querySelectorAll(`.${side} .player.container`)];
    const [t1, t2] = [cards("t1"), cards("t2")];
    const all = [...t1, ...t2];
    const inCards = (sel) => all.map((c) => c.querySelector(sel)).filter(Boolean);
    const stagger = 0.1;
    const playersEnd = 0.2 + (Math.max(t1.length, t2.length, 1) - 1) * stagger + 0.7;

    tl.from("#header", { duration: 0.4, autoAlpha: 0, ease }, 0);
    for (const [side, way] of [["t1", -1], ["t2", 1]]) {
      tl.from(`.${side}.score_side .team_logo`, { duration: 0.5, x: 40 * way, autoAlpha: 0, ease }, 0.1)
        .from(`.${side}.score_side .team_identity`, { duration: 0.5, x: 30 * way, autoAlpha: 0, ease }, 0.15)
        .from(`.${side}.score_side .score`, { duration: 0.6, scale: 1.4, autoAlpha: 0, ease: "back.out(1.4)" }, 0.2);
      const sideCards = side === "t1" ? t1 : t2;
      tl.from(sideCards, { duration: 0.7, x: 120 * way, autoAlpha: 0, stagger, ease }, 0.2).from(
        sideCards.map((c) => c.querySelector(".player_avatar")),
        { duration: 0.8, x: 180 * way, autoAlpha: 0, stagger, ease },
        0.35,
      );
    }
    tl.from(inCards(".name"), { duration: 0.4, autoAlpha: 0, stagger: 0.04, ease }, 0.45)
      .from(inCards(".char_icons"), { duration: 0.4, autoAlpha: 0, stagger: 0.04, ease }, 0.45)
      .from("#center_strip", { duration: 0.4, autoAlpha: 0, ease }, playersEnd);
    // Then the stages, one by one
    document.querySelectorAll(".stage_row").forEach((row, i) => {
      const at = playersEnd + 0.2 + i * 0.3;
      tl.from(row.querySelector(".stage_content"), { duration: 0.35, autoAlpha: 0, y: 10, ease }, at).from(
        row.querySelectorAll(".win_indicator"),
        { duration: 0.25, autoAlpha: 0, scale: 0.5, ease: "back.out(1.7)" },
        at + 0.22,
      );
    });
  },

  update(s) {
    const stages = Object.entries(s.score.stages || {})
      .filter(([, stage]) => stage)
      .sort(([a], [b]) => a - b);
    HD.build("#stage_list", stages, () => stages.map(stageRow));

    s.set(".tournament_name", s.data.tournamentInfo.tournamentName);
    s.set(".event_name", s.data.tournamentInfo.eventName);
    s.set(".ca_phase", s.score.phase);
    s.set(".ca_match", s.score.match);
    s.set(".ca_best_of", s.score.best_of_text);

    // The icon slots with an asset_key for this game
    const game = _.get(s.data, "game.codename", "default");
    const assetKey = (setting) =>
      _.get(s.settings, [setting, game, "asset_key"]) || _.get(s.settings, [setting, "default", "asset_key"]) || "";
    const slots = SLOTS.filter(([setting], i) => i === 0 || assetKey(setting));

    for (const { n, team } of s.teams) {
      const side = `.score_side.t${n}`;
      HD.set(`${side} .score`, team.score || 0);
      HD.set(`${side} .score_team_name`, team.teamName);
      $(`${side} .losers_badge`).toggleClass("visible", !!team.losers);
      $(`${side} .team_logo`).attr("src", HD.asset(team.logo)).css("display", team.logo ? "" : "none");

      const players = Object.entries(team.player || {})
        .filter(([, p]) => p && p.name)
        .sort(([a], [b]) => a - b);
      const area = `.team.t${n} .players_area`;
      HD.build(area, [players.map(([key]) => key), slots], () => players.map(() => playerCard(slots)));

      $(area)
        .children()
        .each((i, el) => {
          const [key, player] = players[i];
          const card = $(el);
          const location = player.country && player.country.code && HD.text([player.country.code, player.state && player.state.code], "/");
          const chip = (icon, text) => text ? HD.html`<div class="chip"><span class="${icon}"></span>${text}</div>` : "";

          HD.set(card.find(".team_name"), HD.html`${player.team && HD.html`<span class="sponsor">${player.team}</span>`}${player.name}`);
          // One row, so fitting scales the chips together
          HD.set(
            card.find(".player_chips"),
            HD.html`${chip("seed_logo", player.seed ? `Seed ${player.seed}` : "")}${chip("twitter_logo", player.twitter)}${chip(
              "pronoun_logo",
              player.pronoun,
            )}${chip("location_icon", location)}`,
          );
          HD.set(card.find(".sponsor_icon"), HD.img(HD.asset(player.sponsor_logo)));
          // The local avatar over the online one
          const avatar = HD.asset(player.avatar) || player.online_avatar;
          card.find(".player_avatar").attr("src", avatar || "").css("display", avatar ? "" : "none");

          const character = Object.values(player.character || {})[0] || {};
          slots.forEach(([setting, icon, label], j) => {
            s.characters(card.find(`.${icon}`), {
              source: ["score", s.n, "team", n, "player", key],
              load_settings_path: setting,
              slice_character: [0, 1],
              scale_fill_x: true,
              custom_zoom: 1,
            });
            HD.set(
              card.find(".char_slot").eq(j).find(`.${label}`),
              j === 0 ? character.display_name : _.get(character, ["assets", assetKey(setting), "metadata", "0", "value"]),
            );
          });
        });
    }
    HD.teamColors(s, ["score-bg-color"]);
  },
});
