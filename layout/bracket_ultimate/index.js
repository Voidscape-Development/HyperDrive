// Smash Ultimate-style bracket: the players' slots along the edges, winners
// at the top and losers at the bottom, and each player's icon travelling
// along the bracket's lines to the furthest round they reached (lit while
// they're in, darkened once they're out). Round robin and swiss pools show
// their rounds and standings instead.
// Page option online_picture: players' online avatars on their icons
// instead of their character.
const MIDDLE_SPACE = 100;

// What's drawn: the bracket in rounds (1, 2... winners, then the grand
// final and its reset; -1, -2... losers), its players, and per icon its
// path timeline (labels start, round_<n>) and its "out" timeline
let bracket = {};
let players = {};
let allWinners = false;
let iconsW = [];
let iconsL = [];
let loseW = [];
let loseL = [];
let lastSignature = null;
let firstUpdate = true;

const roundsWhere = (test) => Object.fromEntries(Object.entries(bracket).filter(([key]) => test(parseInt(key))));
const roundNumbers = () => Object.keys(bracket).map((r) => parseInt(r));
const center = (el) => [el.offset().left + el.outerWidth() / 2, el.offset().top + el.outerHeight() / 2];
const spacer = (cls) => HD.html`<div class="${cls}" style="width: 32px; height: 32px; align-self: center;"></div>`;

// The same next power of 2 the bracket was drawn for (8 players: 16)
function nextPow2(v) {
  let p = 2;
  while ((v >>= 1)) p <<= 1;
  return p;
}

// Line colors, from the layout theme when it sets them
const lineColor = (color) =>
  color == "gray"
    ? "var(--bracket-line-color, gray)"
    : color == "yellow"
      ? "var(--bracket-winner-color, yellow)"
      : color;

// A line through the points
const line = (cls, points, color, hidden = false) =>
  HD.html`<path class="${cls}" d="M${points
    .map((p) => p.join(" "))
    .join(" L")}" fill="none" stroke-width="8" stroke-linecap="square" style="stroke: ${lineColor(color)};${
    hidden ? " opacity: 0;" : ""
  }" />`;

// A bracket line: across, then down or up to the next set
const bracketLine = (cls, [a, b], color, hidden) => line(cls, [a, [b[0], a[1]], b], color, hidden);

// A line drawing itself
function animateLine(element) {
  const path = element.get(0);
  if (!path) return null;
  const length = path.getTotalLength();
  return gsap.from(path, {
    duration: 0.4,
    "stroke-dashoffset": length,
    "stroke-dasharray": length,
    "stroke-linecap": "butt",
    opacity: 0,
    onUpdate() {
      const progress = (this.progress() * 100) >> 0;
      const now = path.getTotalLength();
      gsap.set(path, {
        "stroke-dashoffset": (now / 100) * (100 - progress),
        "stroke-dasharray": now,
        "stroke-linecap": progress ? "square" : "butt",
        opacity: progress ? 1 : 0,
      });
    },
  });
}

// Darkens elements, for when a player is out
const darken = (tl, el) => tl.fromTo(el, { filter: "brightness(1)" }, { duration: 0.5, filter: "brightness(0.7)" }, 0);

const iconHtml = (id) => HD.html`
  <div class="bracket_icon bracket_icon_p${id}">
    <div class="icon_name_arrow">
      <div class="icon_name"></div>
      <div class="icon_arrow_border"></div>
      <div class="icon_arrow"></div>
    </div>
    <div class="icon_image"></div>
  </div>`;

// The rounds, slots and icons
function buildStructure() {
  const winnersRounds = roundsWhere((r) => r > 0);
  const losersRounds = roundsWhere((r) => r < 0);
  const [firstWinners] = Object.values(winnersRounds);
  const slotPlayer = (cls, i, id, p, extra = "") => HD.html`
    <div class="${cls} slot_${i + 1} p_${id} slot_p_${p} player container">${extra}</div>`;

  // Winners: the first row has the players' slots
  HD.render(".winners_container", [
    HD.html`<div class="round round_base_w">${Object.values(firstWinners.sets).map((set, i) =>
      set.playerId.map((id, p) =>
        slotPlayer(
          "slot_full",
          i,
          id,
          p,
          HD.html`
            <div class="icon avatar"></div>
            <div class="icon online_avatar"></div>
            <div class="name_twitter"><div class="name"></div></div>
            <div class="sponsor_icon"></div>
            <div class="flags"><div class="flagcountry"></div><div class="flagstate"></div></div>
            <div class="character_container"></div>`,
        ),
      ),
    )}</div>`,
    Object.entries(winnersRounds)
      .slice(0, -2)
      .map(
        ([key, round]) =>
          HD.html`<div class="round round_${key}"><div class="round_name"></div>${Object.values(round.sets).map(
            (_s, i) => spacer(`slot_${i + 1}`),
          )}</div>`,
      ),
  ]);

  // Losers: every other round has players coming from winners
  allWinners = true; // Players coming from another phase aren't exported any more
  HD.render(".losers_container", [
    Object.entries(losersRounds)
      .reverse()
      .map(
        ([key, round], r) =>
          HD.html`<div class="round round_${key}"><div class="round_name"></div>${Object.values(round.sets).map(
            (_s, i) =>
              r % 2 == 1
                ? HD.html`
                <div class="slot_hanging slot_hanging_${i + 1} p_0 slot_p_0 player container">
                  <div class="character_container"></div>
                  <div class="name"></div>
                </div>
                ${spacer(`slot_sibling_${i + 1}`)}${spacer(`slot_${i + 1}`)}${spacer(`slot_sibling_${i + 1}`)}`
                : spacer(`slot_${i + 1}`),
          )}</div>`,
      ),
    // The last row has every player
    Object.values(losersRounds)
      .slice(0, 1)
      .map(
        (round) =>
          HD.html`<div class="round round_base_l ${!allWinners && "complete"}">${Object.values(round.sets).map(
            (set, i) =>
              set.playerId.map(
                (id, p) =>
                  HD.html`${spacer(`slot_sibling_${i + 1}`)}${slotPlayer(
                    "slot_hanging",
                    i,
                    id,
                    p,
                    HD.html`
                <div class="character_container"></div>
                <div class="name"></div>
                ${
                  !allWinners &&
                  HD.html`
                  <div class="sponsor_icon"></div>
                  <div class="flags"><div class="flagcountry"></div><div class="flagstate"></div></div>
                  <div class="icon avatar"></div>
                  <div class="icon online_avatar"></div>`
                }`,
                  )}`,
              ),
          )}</div>`,
      ),
  ]);

  // The grand final in the middle
  HD.render(
    ".center_container",
    HD.html`<div class="round round_${Object.keys(winnersRounds).reverse()[1]}"><div class="round_name"></div>${spacer("slot_1")}</div>`,
  );

  // An icon per player on the winners side; on the losers side, one per
  // slot of a power of 2 bracket
  HD.render(".winners_icons", Object.keys(players).map(iconHtml));
  HD.render(
    ".losers_icons",
    _.range(nextPow2(_.size(players))).map((t) => iconHtml(t + 1)),
  );
}

// The gray lines from each set to the next, and over them the yellow ones
// (hidden until drawn) a player's icon follows: .line_r_<round> from a
// set in <round>, .line_base_r_<round> from the players' slots
function drawLines() {
  const winnersRounds = roundsWhere((r) => r > 0);
  const losersRounds = roundsWhere((r) => r < 0);
  const losersCount = Object.keys(losersRounds).length;
  const count = _.size(players);
  const gray = [];
  const yellow = [];
  // The yellow line split in two: across ("base") then to the set ("win")
  const winLine = (cls, [a, b]) => {
    yellow.push(bracketLine(`${cls} base`, [a, [b[0], a[1]]], "yellow", true));
    yellow.push(bracketLine(`${cls} win`, [[b[0], a[1]], b], "yellow", true));
  };

  for (const [key, round] of Object.entries(bracket)) {
    const r = parseInt(key);
    const area = r < 0 ? "losers_container" : "winners_container";
    // Rounds where the losers' sets take a player from winners
    const fedFromWinners = (r % 2 == -1 && losersCount % 2 == 0) || (r % 2 == 0 && losersCount % 2 == 1);

    Object.values(round.sets).forEach((set, i) => {
      if (!set.nextWin || set.playerId[0] > count || set.playerId[1] > count) return;
      const slot = $(`.${area} .round_${key} .slot_${i + 1}`);
      if (!slot.offset()) return;
      let target = $(`.${area} .round_${set.nextWin[0]} .slot_${set.nextWin[1] + 1}`);
      if (!target.get(0)) target = $(".center_container .slot_1");

      // From the players' slots
      if (key == "1" || key == "-1") {
        const base = key == "1" ? "round_base_w" : "round_base_l";
        [0, 1].forEach((p) => {
          const points = [center($(`.${area} .${base} .slot_${i + 1}.slot_p_${p}`)), center(slot)];
          const cls = `${area} line_base_r_${key} s_${i + 1} p_${p}`;
          gray.push(bracketLine(cls, points, "gray"));
          yellow.push(line(`${cls} base`, [points[0], [points[1][0], points[0][1]]], "yellow", true));
          yellow.push(line(`${cls} win`, [[points[1][0], points[0][1]], points[1]], "yellow", true));
        });
      }
      if (!target.offset()) return;

      if (r > 0) {
        const points = [center(slot), center(target)];
        // The last round's lines don't merge: room between them
        if (r == parseInt(Object.keys(winnersRounds).reverse()[2])) points[1][0] -= MIDDLE_SPACE;
        gray.push(bracketLine(`${area} line_r_${key} s_${i + 1}`, points, "gray"));
        winLine(`${area} line_r_${r + 1} s_${i + 1}`, points);
        return;
      }

      // Losers: the player coming from winners hangs above the set
      const hanging = $(`.${area} .round_${key} .slot_hanging_${i + 1}`);
      if (fedFromWinners && hanging.offset()) {
        const points = [center(hanging), center(target)];
        gray.push(bracketLine(`${area} line_r_${key} s_${i + 1}`, points, "gray"));
        winLine(`${area} line_r_${r - 1} s_${i + 1} p_0`, points);
      }
      const points = [center(slot), center(target)];
      if (r == parseInt(Object.keys(losersRounds).reverse()[0])) points[1][0] += MIDDLE_SPACE;
      gray.push(bracketLine(`${area} line_r_${key} s_${i + 1}`, points, "gray"));
      // The next round has as many sets (the player goes to slot 1, slot 0
      // being the one from winners) or half as many (slots alternate)
      const next = fedFromWinners ? i + 1 : Math.floor(i / 2) + 1;
      const p = fedFromWinners ? 1 : i % 2;
      winLine(`${area} line_r_${r - 1} s_${next} p_${p}`, points);
    });
  }
  HD.render(".lines.base", gray);
  HD.render(".lines.win", yellow);
}

// Where a losers icon (one per slot) first appears: [round, set, slot]
function losersEntries(onlyWinnersFeeds) {
  const losersRounds = roundsWhere((r) => r < 0);
  const gfReset = Math.max(...roundNumbers());
  const entries = [];
  if (Object.keys(losersRounds).length % 2 == 0 && !allWinners) {
    Object.values(bracket["-1"].sets).forEach((_s, i) => entries.push([-1, i, 0], [-1, i, 1]));
  }
  for (const [key, round] of Object.entries(bracket)) {
    if (onlyWinnersFeeds ? parseInt(key) < 0 : parseInt(key) < 0 && parseInt(key) != gfReset - 1) continue;
    Object.values(round.sets).forEach(
      (set) => set.nextLose && entries.push([set.nextLose[0], set.nextLose[1], set.loseSlot]),
    );
  }
  return entries;
}

// Each icon's path along the bracket, as a timeline with a label per round
function buildIconTimelines() {
  const winnersRounds = roundsWhere((r) => r > 0);
  const losersRounds = roundsWhere((r) => r < 0);
  const lastWinners = Object.keys(winnersRounds).reverse()[1];
  iconsW = [];
  loseW = [];
  iconsL = [];
  loseL = [];

  // Winners: from the player's slot, round after round
  for (const teamId of Object.keys(players)) {
    const icon = $(`.winners_icons .bracket_icon_p${teamId}`);
    const path = gsap.timeline({ paused: true });
    const out = darken(gsap.timeline({ paused: true }), icon);
    let prev = null;

    for (const [key, round] of Object.entries(winnersRounds).slice(0, -1)) {
      Object.values(round.sets).forEach((set, i) =>
        set.playerId.forEach((id, slot) => {
          const here =
            (key == "1" && id == teamId) ||
            (prev && prev.nextWin && prev.nextWin[0] == parseInt(key) && prev.nextWin[1] == i && slot == prev.winSlot);
          if (!here) return;
          prev = set;
          const winLine = (cls, part) => animateLine($(`.lines.win .winners_container.${cls}.${part}`));

          if (key == "1") {
            const start = $(`.round_base_w .slot_${i + 1}.slot_p_${slot}`);
            darken(out, start);
            if (start.offset()) {
              path.set(icon, {
                x: start.offset().left + start.outerWidth() - icon.outerWidth() / 4,
                y: start.offset().top + start.outerHeight() / 2 - icon.outerHeight() / 2,
              });
              path.addLabel("start");
            }
            path.add(winLine(`line_base_r_${key}.s_${i + 1}.p_${slot}`, "base"), ">");
          }

          const target = $(`.round_${key} .slot_${i + 1}`);
          path.add(winLine(`line_r_${key}.s_${2 * i + 1 + slot}`, "base"), ">");
          if (!target.offset()) return;
          const x = key != lastWinners ? target.offset().left : target.offset().left - MIDDLE_SPACE;
          path.to(icon, { x, duration: 0.4 }, "<");
          path.addLabel(`round_${key}`, "<+=0.4");
          // Then, if they won
          path.add(
            key == "1"
              ? winLine(`line_base_r_${key}.s_${i + 1}.p_${slot}`, "win")
              : winLine(`line_r_${key}.s_${2 * i + 1 + slot}`, "win"),
            ">",
          );
          path.to(icon, { x, y: target.offset().top, duration: 0.4 }, "<");
        }),
      );
    }
    iconsW.push(path);
    loseW.push(out);
  }

  // Losers: one icon per slot, from where it enters, to the grand final
  const entries = losersEntries(true);
  const numbers = roundNumbers();
  const gfReset = Math.max(...numbers);
  const lastLosers = Math.min(...numbers);

  _.range(nextPow2(_.size(players))).forEach((t) => {
    const icon = $(`.losers_icons .bracket_icon_p${t + 1}`);
    const path = gsap.timeline({ paused: true });
    const out = darken(gsap.timeline({ paused: true }), icon);
    const losersLine = (cls, part) => animateLine($(`.lines.win .losers_container.${cls}${part ? `.${part}` : ""}`));
    const placeAt = (el) => {
      if (!el.offset()) return;
      gsap.set(icon, {
        x: el.offset().left - (icon.outerWidth() * 3) / 4,
        y: el.offset().top + el.outerHeight() / 2 - icon.outerHeight() / 2,
      });
      darken(out, el);
    };
    let prev = null;
    let found = false;

    for (const [key, round] of Object.entries(losersRounds)) {
      Object.values(round.sets).forEach((set, i) =>
        set.playerId.forEach((_id, slot) => {
          const entry = entries[t];
          const here =
            (prev &&
              prev.nextWin &&
              prev.nextWin[0] == parseInt(key) &&
              prev.nextWin[1] == i &&
              slot == prev.winSlot) ||
            (entry && parseInt(key) == entry[0] && i == entry[1] && slot == entry[2] && !found);
          if (!here) return;
          prev = set;

          if (key == "-1") {
            placeAt($(`.round_base_l .slot_${i + 1}.slot_p_${slot}`));
            path.add(losersLine(`line_base_r_${key}.s_${i + 1}.p_${slot}`, "base"), "<");
          } else if (!found) {
            placeAt($(`.round_${parseInt(key) + 1} .slot_hanging_${i + 1}`));
            path.addLabel("start");
            path.add(losersLine(`line_r_${parseInt(key)}.s_${i + 1}.p_${slot}`, "base"), "<");
          }

          const target = $(`.round_${key} .slot_${i + 1}`);
          path.add(losersLine(`line_r_${key}.s_${i + 1}.p_${slot}`, "base"), ">");
          if (target.offset()) {
            path.to(icon, { x: target.offset().left, duration: 0.4 }, "<");
            path.addLabel(`round_${key}`);
            // Then, if they won
            path.add(
              key == "-1"
                ? losersLine(`line_base_r_-1.s_${i + 1}.p_${slot}`, "win")
                : losersLine(`line_r_${key}.s_${i + 1}.p_${slot}`, "win"),
              ">",
            );
            path.to(icon, { x: target.offset().left, y: target.offset().top, duration: 0.4 }, "<");
          }
          found = true;
        }),
      );
    }

    // Into the grand final
    const gf = $(`.round_${gfReset - 1} .slot_1`);
    path.add(losersLine(`line_r_${lastLosers - 1}.s_1`, "base"), ">");
    if (gf.get(0)) path.to(icon, { x: gf.offset().left + MIDDLE_SPACE, duration: 0.4 }, "<");
    path.addLabel(`round_${lastLosers - 1}`);
    path.add(losersLine(`line_r_${lastLosers - 1}.s_1`, "win"), ">");
    if (gf.get(0)) path.to(icon, { x: gf.offset().left + MIDDLE_SPACE, y: gf.offset().top, duration: 0.4 }, "<");

    iconsL.push(path);
    loseL.push(out);
  });
}

// A team's name: the player's (with sponsor), or the team's, or its
// players' with slashes
function teamName(team, sponsor) {
  const list = Object.values(team.player || {});
  if (list.length === 1) {
    const player = list[0];
    return HD.html`<span><span class="sponsor">${sponsor && player && player.team}</span> ${player ? player.name : "---"}</span>`;
  }
  return (
    team.name ||
    HD.join(
      list.filter((p) => p && p.name).map((p) => p.name),
      HD.html`<div>/</div>`,
    )
  );
}

// The players in their slots
function updatePlayers(s) {
  for (const [key, round] of Object.entries(bracket)) {
    const r = parseInt(key);
    if (r > 1) continue;
    Object.values(round.sets).forEach((set, i) =>
      set.playerId.forEach((pid, p) => {
        const sel =
          r > 0
            ? `.round_base_w .slot_${i + 1}.slot_p_${p}`
            : key == "-1"
              ? `.round_base_l .slot_${i + 1}.slot_p_${p}`
              : `.round_${r + 1} .slot_hanging_${i + 1}.slot_p_${p}`;
        const element = $(sel);
        if (!element.get(0)) return;
        const field = (f) => element.find(f);
        const team = players[pid];

        // A bye, or a slot still waiting for its player
        if (!team) {
          for (const f of [
            ".name",
            ".flagcountry",
            ".flagstate",
            ".character_container",
            ".sponsor_icon",
            ".avatar",
            ".online_avatar",
            ".twitter",
          ]) {
            HD.set(field(f), "");
          }
          return;
        }

        const singles = _.size(team.player) === 1;
        const player = (singles && team.player[1]) || {};
        HD.set(field(".name"), teamName(team, r > 0 || (!allWinners && key == "-1")));
        HD.set(field(".flagcountry"), HD.img(HD.asset(_.get(player, "country.asset")), "class='flag'"));
        HD.set(field(".flagstate"), HD.img(HD.asset(_.get(player, "state.asset")), "class='flag'"));
        s.characters(field(".character_container"), { source: ["bracket", "players", "slot", pid] });
        HD.set(field(".sponsor_icon"), HD.img(HD.asset(player.sponsor_logo)));
        HD.set(field(".avatar"), HD.img(HD.asset(player.avatar)));
        HD.set(field(".online_avatar"), HD.img(player.online_avatar));
        HD.set(field(".twitter"), HD.ui.chip("twitter", player.twitter));
        HD.set(field(".sponsor-container"), HD.ui.sponsorLogo(player.sponsor_logo));
      }),
    );
  }
}

// An icon's picture: the character's icon, or the online avatar
function iconImage(s, element, teamId, player) {
  if (s.settings.online_picture) {
    HD.set(
      element.find(".icon_image"),
      player && player.online_avatar && HD.img(player.online_avatar, "class='floating_online_avatar'"),
    );
    return;
  }
  s.characters(element.find(".icon_image"), {
    load_settings_path: "icon",
    slice_character: [0, 1],
    source: ["bracket", "players", "slot", teamId],
    scale_fill_x: true,
    scale_fill_y: true,
    custom_zoom: 1,
  });
}

// Did the team lose this set?
const lostSet = (set, teamId, orTied) =>
  set.completed &&
  [0, 1].some(
    (n) => set.playerId[n] == teamId && (orTied ? set.score[n] <= set.score[1 - n] : set.score[n] < set.score[1 - n]),
  );

// The icons: names, pictures, and their paths played to how far each
// player got
function updateIcons(s) {
  const numbers = roundNumbers();
  const gfReset = Math.max(...numbers);
  const lastLosers = Math.min(...numbers);

  // Winners: as far as the player keeps showing up, until they lose
  Object.entries(players).forEach(([teamId, team], t) => {
    const element = $(`.winners_icons .bracket_icon_p${teamId}`);
    HD.set(element.find(".icon_name"), _.size(team.player) === 1 ? _.get(team, "player.1.name", "") : teamName(team));
    iconImage(s, element, teamId, Object.values(team.player)[0]);

    let lastRound = 0;
    let lost = false;
    for (const [key, round] of Object.entries(bracket)) {
      if (parseInt(key) < 0 || lost) continue;
      Object.values(round.sets).forEach((set) => {
        if (parseInt(key) > parseInt(lastRound) && set.playerId.some((id) => id == parseInt(teamId))) {
          lastRound = key;
          if (lostSet(set, teamId)) lost = true;
        }
      });
    }
    if (lost) loseW[t].play();
    else loseW[t].reverse();
    iconsW[t].tweenTo(lastRound >= 1 ? `round_${lastRound}` : "start", {
      delay: firstUpdate && lastRound >= 1 ? 0.6 : 0,
    });
  });

  // Losers: players get the icon of the slot they entered losers through
  const entries = losersEntries(false);
  const used = [];
  for (const [teamId, team] of Object.entries(players)) {
    let lastRound = 0;
    let firstRound = 0;
    let lastSet = null;
    let icon = null;

    for (const [key, round] of Object.entries(bracket)) {
      if (parseInt(key) > 0 && parseInt(key) < gfReset - 1) continue;
      Object.values(round.sets).forEach((set, i) => {
        if (!(parseInt(key) < parseInt(lastRound) && set.playerId.some((id) => id == teamId))) return;
        lastRound = key;
        lastSet = set;
        if (!firstRound) firstRound = key;
        if (icon != null) return;
        const at = entries.findIndex(
          ([r, setIndex, slot]) => parseInt(key) == r && i == setIndex && set.playerId[slot] == teamId,
        );
        if (at !== -1) icon = at;
      });
    }
    if (lastRound == 0 || icon === null || !iconsL[icon]) continue;
    used.push(icon);

    if (lastSet && lostSet(lastSet, teamId, true)) loseL[icon].play();
    else loseL[icon].reverse();
    // In the grand final
    if (lastRound == lastLosers && bracket[gfReset - 1].sets[0].playerId[1] == teamId) lastRound = lastLosers - 1;
    const label = `round_${lastRound}`;
    iconsL[icon].tweenTo(label in iconsL[icon].labels ? label : "start", {
      delay: firstUpdate && label in iconsL[icon].labels ? 0.6 * -firstRound : 0,
    });

    const element = $(`.losers_icons .bracket_icon_p${icon + 1}`);
    HD.set(element.find(".icon_name"), HD.html`<span>${_.get(team, "player.1.name", "")}</span>`);
    gsap.to(element, { autoAlpha: 1 });
    iconImage(s, element, teamId, team.player[1]);
  }

  // The icons nobody took go back to the start, hidden
  iconsL.forEach((anim, i) => {
    if (used.includes(i)) return;
    anim.tweenTo(0, { duration: firstUpdate ? 0 : undefined });
    const element = $(`.losers_icons .bracket_icon_p${i + 1}`);
    HD.set(element.find(".icon_name"), "---");
    gsap.to(element, { autoAlpha: 0, duration: firstUpdate ? 0 : undefined });
  });
}

// Fits the sets in the height there is
function resize() {
  const biggest = Math.max(...Object.values(bracket).map((r) => _.size(r.sets)));
  const room = $(".winners_container").height() - 92;
  let size = 32;
  while (biggest * (2 * size + 2) > room && size > 1) size -= 1;
  const root = $(":root");
  root.css("--player-height", size);
  root.css("--name-size", Math.min(size * 0.7, 16));
  root.css("--score-size", size * 0.7);
  root.css("--flag-height", size * 0.6);
}

HD.layout({
  subscribe: ["bracket", "score", "game", "tournamentInfo", "commentary"],
  update(s) {
    if (!s.changed("bracket")) return;
    const data = s.data;
    if (!_.get(data, "bracket.bracket.sides")) {
      lastSignature = null;
      return;
    }
    const info = (parts) => HD.text(parts, " / ");

    // Round robin and swiss: their rounds and standings
    const pool = HDBracket.IsPool(data.bracket.bracket);
    $("body").toggleClass("pool_view", pool);
    $(".standings_container").toggleClass("hidden", !pool);
    if (pool) {
      lastSignature = null;
      HDBracket.RenderPool($(".pool_container"), data);
      HD.render(".standings_container .standings", HDBracket.StandingsHtml(data));
      s.set(".header .title", data.tournamentInfo.tournamentName);
      s.set(".info_content", info([data.bracket.phase || data.bracket.bracket.name, data.bracket.phaseGroup]));
      return;
    }
    HD.render($(".pool_container").removeData("hd-build"), "");

    bracket = HDBracket.ToRounds(data.bracket.bracket, data.bracket.players.slot);
    players = data.bracket.players.slot;
    resize();

    const signature = HDBracket.Signature(data);
    if (signature != lastSignature) {
      lastSignature = signature;
      buildStructure();
      drawLines();
      buildIconTimelines();
    }

    // Losers round names as initials: "Losers Round 1" -> "LR1"
    for (const [key, round] of Object.entries(bracket)) {
      const name =
        parseInt(key) < 0
          ? round.name
              .split(/ |-/)
              .map((n) => n[0])
              .join("")
          : round.name;
      HD.set(`.round_${parseInt(key)} .round_name`, name);
    }
    updatePlayers(s);
    updateIcons(s);

    s.set(".header .title", data.tournamentInfo.tournamentName);
    s.set(
      ".info_content",
      info([
        data.bracket.phase,
        data.bracket.phaseGroup,
        data.tournamentInfo.numEntrants && `${data.tournamentInfo.numEntrants} Players`,
      ]),
    );
    firstUpdate = false;
  },
});
