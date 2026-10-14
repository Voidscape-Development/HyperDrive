// The stream queue, shared by layout/stream_queue and stream_queue_simple:
// the next sets on stream (from the Stream Queue widget), each with both
// sides' names, flags, avatars, Twitter, pronouns and seeds, the phase,
// match and when it should start.
//
// Which queue: settings.stream ("all" for every stream) unless
// force_multistream; otherwise the scoreboard's station (or its station
// queue, with auto_update "station"), the stream linked to the scoreboard,
// settings.default_stream, or every stream.
(() => {
  // The queues to show, { all (every stream), queues: [[stream name,
  // queue]] }, the name null for a station's queue
  function streamQueues(s) {
    const c = s.settings;
    const byName = _.get(s.data, "stream_queue.byName") || s.data.streamQueue || {};
    // A stream's queue, its name in any case
    const named = (name) => {
      const key = Object.keys(byName).find((k) => k.toLowerCase() === String(name).toLowerCase());
      return key ? [[key, byName[key]]] : [];
    };

    const pick = () => {
      if (c.stream && !c.force_multistream) return c.stream === "all" ? null : named(c.stream);
      if (s.score.station) {
        return s.score.auto_update === "station" ? [[null, s.score.station_queue || {}]] : named(s.score.station);
      }
      // The stream linked to this scoreboard in the Stream Queue widget
      const linked = (_.get(s.data, "stream_queue.streams") || []).find((st) => String(st.scoreboard) === String(s.n));
      if (linked) return named(linked.name);
      return c.default_stream ? named(c.default_stream) : null;
    };
    const queues = pick();
    return queues ? { all: false, queues } : { all: true, queues: Object.entries(byName) };
  }

  const isTeams = (set) => set.team[1] && _.size(set.team[1].player) > 1;

  // A queue's sets the settings show
  function visibleSets(queue, c) {
    const count = c.sets_displayed < 0 ? Infinity : c.sets_displayed;
    return Object.values(queue || {})
      .slice(c.display_first_set ? 0 : 1)
      .filter(
        (set) =>
          set.team &&
          !(c.minimum_determined_players > 0 && !set.team[c.minimum_determined_players]) &&
          !(c.currentEventOnly && !set.isCurrentEvent) &&
          (c.station == -1 || c.station == set.station),
      )
      .slice(0, count);
  }

  // A set: both sides around the VS, the phase, match and station
  const setRow = (c, set, i) => {
    const side = (t) => {
      const team = set.team[t];
      if (!team) return HD.html`<div class="p${t} tbd_container"><div class="TBD">TBD</div></div>`;
      const teams = isTeams(set);
      const player = team.player[1] || {};
      const country = player.country || {};
      const state = player.state || {};
      return HD.html`
        <div class="p${t} team">
          ${!teams && c.display.avatar && HD.html`<div class="p${t}_avatar avatar_container">${player.online_avatar && HD.img(player.online_avatar, "class='avatar'")}</div>`}
          <div class="flags">${
            !teams &&
            HD.html`${c.display.country_flag && HD.img(HD.asset(country.asset), "class='flag'")}${
              c.display.state_flag && HD.img(HD.asset(state.asset), "class='flag'")
            }`
          }</div>
          <div class="name">
            <div class="tag"></div>
            <div class="extra">
              ${player.twitter && HD.html`<div class="twitter"></div>`}
              ${player.pronoun && HD.html`<div class="pronoun"><div class="text">${teams ? "" : player.pronoun}</div></div>`}
              ${player.seed ? HD.html`<div class="seed"><div class="text">Seed ${player.seed}</div></div>` : ""}
            </div>
          </div>
        </div>`;
    };
    return HD.html`
      <div class="set${i} set">
        ${side(1)}
        <div class="vs_container">
          <div class="vs vs_${c.display.station ? "small" : "big"}">VS</div>
          ${c.display.station && set.station && set.station != -1 && HD.html`<div class="station"></div>`}
          <div class="phase"></div>
          <div class="match"></div>
        </div>
        ${side(2)}
      </div>`;
  };

  HD.layouts.streamQueue = {
    // streamQueue: older HyperDrive versions' name for stream_queue
    subscribe: ["stream_queue", "streamQueue", "score", "game", "tournamentInfo", "commentary"],

    settings: {
      stream: "",
      default_stream: "",
      force_multistream: false,
      // Sets shown per stream (-1: all), and whether the one on stream is
      sets_displayed: -1,
      display_first_set: true,
      station: -1,
      currentEventOnly: false,
      // Sets with fewer players known than this aren't shown
      minimum_determined_players: 1,
      display: {
        station: false,
        country_flag: true,
        state_flag: true,
        avatar: true,
        // Each stream's name over its sets: true, false or "multistream" (only
        // with every stream shown)
        stream_name: "multistream",
        eta: true,
      },
    },

    // The layout theme's "Stream queue" section
    theme: {
      sets_displayed: ["stream_queue", "sets_count", 0],
      display_first_set: ["stream_queue", "first_set_display", true],
      "display.eta": ["stream_queue", "eta_display", true],
      "display.station": ["stream_queue", "station_display", false],
      "display.avatar": ["stream_queue", "avatar_display", true],
    },

    intro(tl) {
      $(".set").each((i, el) => tl.from(el, { x: -100, autoAlpha: 0, duration: 0.3 }, 0.2 + 0.2 * i));
      tl.from(".message", { autoAlpha: 0, duration: 0.3 }, 0.3 + 0.2 * $(".set").length);
    },

    update(s) {
      const c = s.settings;
      // [stream name or null, its sets] for each queue to show
      const { all, queues: found } = streamQueues(s);
      const queues = found.map(([name, queue]) => [name, visibleSets(queue, c)]);
      const showNames = c.display.stream_name === true || (c.display.stream_name === "multistream" && all);
      const built = HD.build(".stream_queue_content", [queues, c], () => {
        let n = 0; // Sets are numbered across the streams
        return queues.map(([name, sets]) => [
          name &&
            showNames &&
            HD.html`<div class="message"><img class="twitch_logo" src="./twitch.svg"></img>/${name}</div>`,
          sets.map((set) => setRow(c, set, n++)),
        ]);
      });

      let n = 0;
      for (const [, sets] of queues) {
        for (const set of sets) {
          const row = `.stream_queue_content .set${n}`;
          const eta = c.display.eta && set.eta_minutes > 0 ? `~${set.eta_minutes} min` : "";
          HD.set(`${row} .match`, HD.text([set.match, eta], " · "));
          HD.set(`${row} .phase`, set.phase);
          HD.set(`${row} .station`, `Station ${set.station}`);
          for (const t of [1, 2]) {
            const team = set.team[t];
            if (!team) continue;
            const player = team.player[1] || {};
            const teams = isTeams(set);
            HD.set(
              `${row} .p${t} .tag`,
              teams
                ? team.teamName || team.name
                : HD.html`<span class="sponsor">${player.team}</span> ${player.name} ${team.losers && HD.html`<span class='losers'>L</span>`}`,
            );
            HD.set(`${row} .p${t} .twitter`, !teams && HD.ui.chip("twitter", player.twitter));
          }
          n += 1;
        }
      }

      // A new queue slides in
      if (built && !s.first) HD.restart();
    },
  };
})();
