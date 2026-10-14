// Helpers for layouts showing the bracket widget's export, bracket.bracket
// (see docs/layout-data.md): its sides, columns and sets, the standings of
// round robin and swiss pools, the older "rounds" shape some layouts
// were drawn around, and the bracket a focus channel shows. Load after globals.js:
//   <script src="../include/bracket.js"></script>
// The *Html helpers return HD.html (names escaped), for HD.set() or HD.render().
var HDBracket = {
  POOL_TYPES: ["ROUND_ROBIN", "SWISS"],

  // Value standing for a bye in the rounds shape (any id past the players)
  BYE_ID: 99999,

  // A focus channel's name as the app keeps it: no dots or extra spaces.
  // Empty if there's none.
  ChannelName(name) {
    return String(name || "")
      .replace(/\./g, " ")
      .split(/\s+/)
      .filter((w) => w)
      .join(" ")
      .slice(0, 40)
      .trim();
  },

  // The data with a channel's bracket (bracket.channels.<channel>: the
  // phase it shows, with its top N) in place of the main channel's:
  // bracket.bracket, bracket.players, bracket.phase and bracket.phaseGroup.
  // bracket.playersPath is where its players are in the state, for
  // CharacterDisplay's source. A channel that isn't there shows nothing.
  ForChannel(data, channel) {
    if (!data || !data.bracket) return data;
    const exported = _.get(data, ["bracket", "channels", channel]);
    if (!exported) {
      if (channel != "main" || data.bracket.channels) {
        return { ...data, bracket: { ...data.bracket, bracket: {}, players: {}, playersPath: "bracket.players" } };
      }
      // Sent before channels existed
      return { ...data, bracket: { ...data.bracket, playersPath: "bracket.players" } };
    }
    return {
      ...data,
      bracket: {
        ...data.bracket,
        bracket: exported.bracket || {},
        players: _.get(data, exported.playersPath) || {},
        phase: exported.phase || "",
        phaseGroup: exported.phaseGroup || "",
        playersPath: exported.playersPath,
      },
    };
  },

  IsPool(bracket) {
    return HDBracket.POOL_TYPES.includes(_.get(bracket, "type"));
  },

  Columns(bracket, side) {
    return _.get(bracket, ["sides", side], []) || [];
  },

  // The columns of the upper and lower parts of an elimination bracket:
  // winners then grand finals (and a 3rd place match, when there's no
  // losers side) on top, losers below
  Areas(bracket) {
    const losers = HDBracket.Columns(bracket, "losers").map((c) => ({ ...c, side: "losers" }));
    const third = HDBracket.Columns(bracket, "third_place").map((c) => ({ ...c, side: "third_place" }));
    const upper = []
      .concat(HDBracket.Columns(bracket, "winners").map((c) => ({ ...c, side: "winners" })))
      .concat(HDBracket.Columns(bracket, "grand_final").map((c) => ({ ...c, side: "grand_final" })));
    if (losers.length == 0) return { upper: upper.concat(third), lower: [] };
    return { upper, lower: losers.concat(third) };
  },

  // Changes when what's drawn has to be rebuilt (not for scores or players)
  Signature(data) {
    const bracket = _.get(data, "bracket.bracket", {});
    return JSON.stringify([
      bracket.type,
      bracket.name,
      bracket.progressionsOut,
      bracket.limitExportNumber,
      _.mapValues(bracket.sides || {}, (columns) => columns.map((c) => [c.key, c.sets])),
      Object.values(bracket.sets || {}).map((s) => [s.id, s.resetNeeded]),
      Object.keys(_.get(data, "bracket.players.slot", {})).length,
      _.get(data, "bracket.phase"),
      _.get(data, "bracket.phaseGroup"),
    ]);
  },

  // hidden: not shown. displayed: shown. done: shown, and its line to the
  // next set drawn. With expand, every set that can be is shown.
  SetState(set, expand) {
    if (!set) return "hidden";
    if (set.isReset && set.resetNeeded === false) return "hidden";
    const known = set.players.filter((p) => p.id).length;
    if (expand) return "done";
    if (known == 0) return "hidden";
    return set.completed ? "done" : "displayed";
  },

  // 0 or 1 for the slot that won, "draw", or null
  Winner(set) {
    if (!set) return null;
    if (set.winner === 0 || set.winner === 1 || set.winner === "draw") return set.winner;
    return null;
  },

  ScoreText(set, slot) {
    const score = set.score ? set.score[slot] : null;
    if (score == null) return "";
    if (score == -1) return "DQ";
    const started = set.completed || set.score.some((s) => s > 0);
    return started ? String(score) : "";
  },

  // A team's display name: its player (with sponsor), its name, or its
  // players' names
  TeamName(team) {
    if (!team) return "";
    const players = Object.values(team.player || {}).filter((p) => p && p.name);
    if (players.length == 1) return HD.html`<span class="sponsor">${players[0].team}</span> ${players[0].name}`;
    return team.name || players.map((p) => p.name).join(" / ");
  },

  // The bracket in the shape older layouts were made for:
  // {"<round>": {name, sets: {"<i>": {playerId, score, completed, nextWin,
  // winSlot, nextLose, loseSlot, playerName}}}}. Winners rounds are 1, 2...
  // then the grand final and its reset; losers rounds are -1, -2... Sets
  // are filled in with byes up to full columns (rows are kept), so the
  // bracket keeps its shape.
  ToRounds(bracket, players) {
    const rounds = {};
    const where = {}; // set id: [roundKey, index]
    const winners = HDBracket.Columns(bracket, "winners");
    const grandFinal = HDBracket.Columns(bracket, "grand_final");
    const losers = HDBracket.Columns(bracket, "losers");
    const sets = bracket.sets || {};

    const add = (columns, keyOf) => {
      columns.forEach((column, c) => {
        const key = keyOf(c);
        const rows = column.sets.map((id) => (sets[id] ? sets[id].row : 0));
        rounds[key] = { name: column.name, sets: {}, size: Math.max(column.sets.length, Math.max(-1, ...rows) + 1) };
        column.sets.forEach((id) => {
          const set = sets[id];
          if (!set) return;
          where[id] = [key, set.row];
        });
      });
    };
    add(winners, (c) => String(c + 1));
    add(grandFinal, (c) => String(winners.length + c + 1));
    add(losers, (c) => String(-(c + 1)));

    // Winners columns double going back, so a bracket of byes keeps its shape
    for (let c = winners.length - 2; c >= 0; c -= 1) {
      const next = rounds[String(c + 2)];
      if (next) rounds[String(c + 1)].size = Math.max(rounds[String(c + 1)].size, next.size * 2);
    }

    const playerId = (p) => (p.id ? p.id : p.bye ? HDBracket.BYE_ID : -2);
    const nameOf = (id) => {
      const team = players ? players[id] : null;
      if (!team) return "";
      return Object.values(team.player || {})
        .map((p) => p && p.name)
        .filter((n) => n)
        .join(" / ");
    };

    Object.entries(rounds).forEach(([key, round]) => {
      for (let i = 0; i < round.size; i += 1) {
        round.sets[i] = null;
      }
    });

    Object.values(sets).forEach((set) => {
      const at = where[set.id];
      if (!at) return;
      const next = (link) => (link && where[link.set] ? [parseInt(where[link.set][0]), where[link.set][1]] : null);
      const ids = set.players.map(playerId);
      rounds[at[0]].sets[at[1]] = {
        playerId: ids,
        score: (set.score || [0, 0]).slice(),
        completed: !!set.completed,
        nextWin: next(set.nextWin),
        winSlot: set.nextWin ? set.nextWin.slot : null,
        nextLose: next(set.nextLose),
        loseSlot: set.nextLose ? set.nextLose.slot : null,
        playerName: ids.map(nameOf),
        id: set.id,
      };
    });

    // Rows with no set had a bye: its player is the one waiting in the
    // next column, where the set's winner would have gone
    Object.entries(rounds).forEach(([key, round]) => {
      const k = parseInt(key);
      Object.keys(round.sets).forEach((i) => {
        if (round.sets[i]) return;
        i = parseInt(i);
        let player = -1;
        let nextWin = null;
        if (k > 0 && rounds[String(k + 1)] && k < winners.length) {
          nextWin = [k + 1, i >> 1];
          const target = rounds[String(k + 1)].sets[i >> 1];
          if (target && target.playerId[i % 2] > 0 && target.playerId[i % 2] != HDBracket.BYE_ID) {
            player = target.playerId[i % 2];
          }
        }
        round.sets[i] = {
          playerId: [player, HDBracket.BYE_ID],
          score: [0, 0],
          completed: player > 0,
          nextWin,
          winSlot: nextWin ? i % 2 : null,
          nextLose: null,
          loseSlot: null,
          playerName: [nameOf(player), ""],
          bye: true,
        };
      });
      delete round.size;
    });

    return rounds;
  },

  // The pool's standings, or an elimination bracket's results, as a table
  StandingsHtml(data) {
    const bracket = _.get(data, "bracket.bracket", {});
    const players = _.get(data, "bracket.players.slot", {});
    const highlight = HD.theme("standings", "highlight_top", 0);
    const pool = HDBracket.IsPool(bracket);
    const swiss = bracket.type == "SWISS";
    const name = (id, fallback) => {
      const team = players[id];
      return HD.html`<td class="st_name">${HDBracket.FlagHtml(team)}<span>${team ? HDBracket.TeamName(team) : fallback}</span></td>`;
    };
    const top = (place) => (highlight && place <= highlight ? "top" : "");

    if (!pool) {
      return HD.html`<table class="standings_table elimination">
        <thead><tr><th class="st_rank">#</th><th class="st_name">Player</th></tr></thead>
        <tbody>${(bracket.results || []).map(
          (row) =>
            HD.html`<tr class="${top(row.order)}" data-player="${row.id}"><td class="st_rank">${row.order}</td>${name(row.id, row.name)}</tr>`,
        )}</tbody></table>`;
    }
    const draws = (bracket.standings || []).some((r) => r.draws);
    return HD.html`<table class="standings_table pool">
      <thead><tr>
        <th class="st_rank">#</th>
        <th class="st_name">Player</th>
        <th class="st_record">W-L${draws && "-D"}</th>
        <th class="st_points">Pts</th>
        <th class="st_game_diff">+/-</th>
        ${swiss && HD.html`<th class="st_buchholz">Bh</th>`}
      </tr></thead>
      <tbody>${(bracket.standings || []).map(
        (row) => HD.html`<tr class="${top(row.rank)}" data-player="${row.playerId}">
          <td class="st_rank">${row.rank}</td>
          ${name(row.playerId, row.name)}
          <td class="st_record">${row.wins}-${row.losses}${row.draws ? `-${row.draws}` : ""}</td>
          <td class="st_points">${row.points}</td>
          <td class="st_game_diff">${row.gameDiff > 0 ? "+" : ""}${row.gameDiff}</td>
          ${swiss && HD.html`<td class="st_buchholz">${row.buchholz}</td>`}
        </tr>`,
      )}</tbody></table>`;
  },

  // A pool's players in seed order: [{id, seed, name}]
  PoolPlayers(bracket) {
    const found = {};
    const add = (id, seed, name) => {
      if (!id) return;
      const known = found[id] || { id, seed: null, name: "" };
      if (seed != null && known.seed == null) known.seed = seed;
      if (name && !known.name) known.name = name;
      found[id] = known;
    };
    Object.values(bracket.sets || {}).forEach((set) =>
      (set.players || []).forEach((p) => p && add(p.id, p.seed, p.name)),
    );
    (bracket.standings || []).forEach((row) => add(row.playerId, null, row.name));
    return Object.values(found).sort(
      (a, b) =>
        (a.seed == null ? Infinity : a.seed) - (b.seed == null ? Infinity : b.seed) ||
        String(a.id).localeCompare(String(b.id)),
    );
  },

  // A round robin grid: each player is a row and a column, the cell where
  // two players meet holds their set's score from the row player's side, and
  // the cells where a player meets themselves are blank
  GridHtml(data) {
    const bracket = _.get(data, "bracket.bracket", {});
    const players = _.get(data, "bracket.players.slot", {});
    const list = HDBracket.PoolPlayers(bracket);

    // "a|b": [set, slot of a]; a later set between the same two players wins
    const meetings = {};
    Object.values(bracket.sets || {}).forEach((set) => {
      const [a, b] = (set.players || []).map((p) => p && p.id);
      if (!a || !b) return;
      meetings[`${a}|${b}`] = [set, 0];
      meetings[`${b}|${a}`] = [set, 1];
    });

    const name = (p) => (players[p.id] ? HDBracket.TeamName(players[p.id]) : p.name);
    // The cell where row meets col
    const cell = (row, col) => {
      if (row.id == col.id) return HD.html`<td class="rr_cell rr_self"></td>`;
      const meeting = meetings[`${row.id}|${col.id}`];
      if (!meeting) return HD.html`<td class="rr_cell rr_none"></td>`;
      const [set, slot] = meeting;
      const mine = HDBracket.ScoreText(set, slot);
      const theirs = HDBracket.ScoreText(set, 1 - slot);
      const winner = HDBracket.Winner(set);
      const result = winner === "draw" ? "draw" : winner === slot ? "won" : winner === 1 - slot ? "lost" : "";
      const played = mine !== "" || theirs !== "";
      return HD.html`<td class="rr_cell rr_set ${result} ${set.completed ? "completed" : ""}" data-set="${set.id}">${
        played && HD.html`${mine || 0}<span class="rr_dash">-</span>${theirs || 0}`
      }</td>`;
    };

    return HD.html`<table class="rr_grid" style="--rr-count: ${list.length}">
      <thead><tr><th class="rr_corner"></th>${list.map(
        (p) => HD.html`<th class="rr_col_name" data-player="${p.id}"><span>${name(p)}</span></th>`,
      )}</tr></thead>
      <tbody>${list.map(
        (row) =>
          HD.html`<tr data-player="${row.id}"><th class="rr_row_name">${HDBracket.FlagHtml(players[row.id])}<span>${name(row)}</span></th>${list.map(
            (col) => cell(row, col),
          )}</tr>`,
      )}</tbody></table>`;
  },

  // A singles player's country and state flags
  FlagHtml(team) {
    const player = team ? Object.values(team.player || {})[0] : null;
    if (!player || Object.keys(team.player || {}).length != 1) return "";
    return HD.html`${HD.img(HD.asset(_.get(player, "country.asset")), "class='flag flagcountry'")}${HD.img(
      HD.asset(_.get(player, "state.asset")),
      "class='flag flagstate'",
    )}`;
  },

  // Draws a round robin / swiss pool's rounds in container: a column per
  // round, each set its two players and scores. For layouts without a pool
  // view of their own; rebuilt only when the pool's shape changes.
  RenderPool(container, data) {
    const bracket = _.get(data, "bracket.bracket", {});
    const sets = bracket.sets || {};
    const players = _.get(data, "bracket.players.slot", {});
    const columns = HDBracket.Columns(bracket, "pool");
    const byes = HDBracket.ByesText(bracket);
    const shape = JSON.stringify(columns.map((c) => [c.key, c.sets]));

    const built = HD.build(container, shape, () =>
      columns.map(
        (column) => HD.html`<div class="pool_round" data-round="${column.key}">
          <div class="round_name"><div class="text"></div></div>
          ${column.sets.map(
            (id) =>
              HD.html`<div class="pool_set" data-set="${id}">${[0, 1].map(
                (slot) =>
                  HD.html`<div class="pool_player slot_p_${slot}"><div class="name"></div><div class="score"></div></div>`,
              )}</div>`,
          )}
          <div class="byes"><div class="text"></div></div>
        </div>`,
      ),
    );
    if (built) gsap.from(container.find(".pool_set"), { autoAlpha: 0, x: -30, stagger: 0.02, duration: 0.3 });

    const biggest = Math.max(1, ...columns.map((c) => c.sets.length));
    container.css("--pool-set-height", Math.max(28, Math.min(64, (container.height() - 60) / biggest - 8)) + "px");

    for (const column of columns) {
      const round = container.find(`.pool_round[data-round="${CSS.escape(column.key)}"]`);
      HD.set(round.find(".round_name"), column.name);
      HD.set(round.find(".byes"), byes[column.key] ? `Bye: ${byes[column.key]}` : "");
      for (const id of column.sets) {
        const set = sets[id];
        const element = round.find(`.pool_set[data-set="${CSS.escape(id)}"]`);
        if (!set || !element.get(0)) continue;
        const winner = HDBracket.Winner(set);
        for (const slot of [0, 1]) {
          const p = set.players[slot];
          const row = element.find(`.slot_p_${slot}`);
          const team = p && p.id ? players[p.id] : null;
          HD.set(
            row.find(".name"),
            team
              ? HDBracket.TeamName(team)
              : p && p.pending && p.source && HD.html`<span class="pending_source">${p.source}</span>`,
          );
          HD.set(row.find(".score"), HDBracket.ScoreText(set, slot));
          row.toggleClass("won", winner === slot).toggleClass("lost", winner === 1 - slot);
          row.addClass("player");
        }
      }
    }
  },

  // A set's player slot (0 or 1), for UpdateSet() to fill
  PlayerSlotHtml: (slot) => HD.html`
    <div class="slot_p_${slot} player container" data-slot="${slot}">
      <div class="icon avatar"></div>
      <div class="icon online_avatar"></div>
      <div class="seed"></div>
      <div class="name_twitter"><div class="name"></div></div>
      <div class="sponsor_icon"></div>
      <div class="flags"><div class="flagcountry"></div><div class="flagstate"></div></div>
      <div class="character_container"></div>
      <div class="score"></div>
    </div>`,

  // Fills a set's element (made with PlayerSlotHtml()): its identifier, and
  // each slot's player (or where they come from), score and result
  UpdateSet(s, element, set, data) {
    const players = _.get(data, "bracket.players.slot", {});
    const winner = HDBracket.Winner(set);
    HD.set(element.find(".set_identifier"), set.identifier);

    [0, 1].forEach((n) => {
      const row = element.find(`.slot_p_${n}`);
      const slot = set.players[n];
      const team = slot && slot.id ? players[slot.id] : null;
      HD.set(row.find(".score"), HDBracket.ScoreText(set, n));
      row
        .toggleClass("won", winner === n)
        .toggleClass("lost", winner === 1 - n)
        .toggleClass("draw", winner === "draw");
      row.toggleClass("pending", !!(slot && slot.pending)).toggleClass("empty", !team);

      const singles = team && _.size(team.player) === 1;
      const player = (singles && team.player[1]) || {};
      const asset = (path) => HD.asset(_.get(player, path));
      HD.set(
        row.find(".name"),
        team
          ? HDBracket.TeamName(team)
          : slot && slot.pending && slot.source && HD.html`<span class="pending_source">${slot.source}</span>`,
      );
      HD.set(row.find(".seed"), team && slot.seed ? String(slot.seed) : "");
      HD.set(row.find(".flagcountry"), HD.img(asset("country.asset"), "class='flag'"));
      HD.set(row.find(".flagstate"), HD.img(asset("state.asset"), "class='flag'"));
      HD.set(row.find(".sponsor_icon"), HD.img(asset("sponsor_logo"), "class='sponsor_icon'"));
      HD.set(row.find(".avatar"), HD.img(asset("avatar"), "class='avatar'"));
      HD.set(row.find(".online_avatar"), HD.img(player.online_avatar, "class='online_avatar'"));
      if (!team) {
        HD.set(row.find(".character_container"), "");
        return;
      }
      s.characters(row.find(".character_container"), {
        source: `${data.bracket.playersPath || "bracket.players"}.slot.${slot.id}`,
        slice_character: singles ? undefined : [0, 1],
      });
    });
  },

  // Who sits out each pool round: {"pool:1": "A, B"}
  ByesText(bracket) {
    const byes = {};
    Object.entries(bracket.byes || {}).forEach(([key, list]) => {
      byes[key] = (list || [])
        .map((p) => p.name)
        .filter((n) => n)
        .join(", ");
    });
    return byes;
  },
};
