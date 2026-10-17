// Tale of the tape: the two sides before their set, face to face. Each
// side's character art, name and bio (custom bio) at its edge, and between
// them their numbers side by side: seed, head-to-head, best and latest
// finishes (history_sets), their sets in the event (last_sets) and any
// custom fields. The better number of each row is highlighted. Under them,
// their last meetings (recent_sets).

// A side's tournaments, most recent first
const history = (s, n) => Object.values(_.get(s.score, ["history_sets", n]) || {}).filter(Boolean);

// A side's sets in the event
const eventSets = (s, n) => Object.values(_.get(s.score, ["last_sets", n]) || {}).filter(Boolean);

// The sets between the two, most recent first ([team 1's score, team 2's],
// winner 0 for team 1)
const meetings = (s) => _.get(s.score, "recent_sets.sets") || [];

const placing = (t) =>
  t && t.placement && HD.html`${t.placement}<span class="ordinal">${HD.ordinal(t.placement)}</span>`;

// Each row: its label and, for each side, the value shown and the number
// it's compared by (lower or higher is better)
const ROWS = {
  seed: {
    label: "Seed",
    lower: true,
    value: (s, t) => t.player.seed || null,
  },
  head_to_head: {
    label: "Head-to-head",
    value: (s, t) => (meetings(s).length ? meetings(s).filter((m) => m.winner === t.n - 1).length : null),
  },
  best_finish: {
    label: "Best recent finish",
    lower: true,
    value: (s, t) => {
      const best = _.minBy(
        history(s, t.n).filter((h) => h.placement),
        "placement",
      );
      return best ? [HD.html`${placing(best)}<span class="of">/${best.entrants}</span>`, best.placement] : null;
    },
  },
  recent_finishes: {
    label: "Latest finishes",
    value: (s, t) => {
      const latest = history(s, t.n)
        .filter((h) => h.placement)
        .slice(0, 3);
      return latest.length ? [HD.join(latest.map(placing), HD.html`<span class="dot">·</span>`), null] : null;
    },
  },
  event_record: {
    label: "Sets in this event",
    value: (s, t) => {
      const sets = eventSets(s, t.n);
      if (!sets.length) return null;
      const won = sets.filter((set) => Number(set.player_score) > Number(set.oponent_score)).length;
      return [`${won}–${sets.length - won}`, won - (sets.length - won)];
    },
  },
};

// A row's value for a side as [shown, compared by]
const rowValue = (row, s, t) => {
  const value = row.value(s, t);
  if (value === null || value === undefined || value === "") return [null, null];
  return Array.isArray(value) ? value : [value, Number(value)];
};

// The rows the settings show, with the custom fields after them
const rows = (s) => [
  ...s.settings.rows.filter((key) => ROWS[key]).map((key) => ({ key, ...ROWS[key] })),
  ...(s.settings.custom_rows || []).map((c) => ({
    key: `custom_${c.key}`,
    label: c.label,
    value: (_s, t) => HD.custom(t.player, c.key),
  })),
];

const meetingRow = (m) => {
  const won = m.winner === 0 ? 1 : 2;
  const date =
    m.timestamp && new Date(m.timestamp * 1000).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  return HD.html`
    <div class="meeting won_${won}">
      <span class="meeting_score"><span class="s1">${m.score[0]}</span>–<span class="s2">${m.score[1]}</span></span>
      <span class="meeting_event">${m.tournament}</span>
      <span class="meeting_round">${HD.text([m.round, date], " · ")}</span>
    </div>`;
};

HD.layout({
  subscribe: ["score", "game", "tournamentInfo"],

  settings: {
    title: "Tale of the tape",
    // The rows, in order: seed, head_to_head, best_finish,
    // recent_finishes and event_record
    rows: ["seed", "head_to_head", "best_finish", "recent_finishes", "event_record"],
    // More rows from the players' custom data: [{ "label": "Mains",
    // "key": "mains" }] shows custom/mains.txt
    custom_rows: [],
    // Highlight the better value of each row
    highlight_better: true,
    // The custom field shown under each name ("" for none)
    bio_key: "bio",
    // Their last meetings, at most this many (0 for none)
    meetings_displayed: 3,
    meetings_title: "Last meetings",
  },

  intro(tl) {
    tl.from(".header > *", { autoAlpha: 0, y: -20, duration: 0.4, ease: "power2.out", stagger: 0.06 }, 0)
      .from(".p1.side", { autoAlpha: 0, x: -80, duration: 0.55, ease: "power3.out" }, 0.1)
      .from(".p2.side", { autoAlpha: 0, x: 80, duration: 0.55, ease: "power3.out" }, "<")
      .from(".row", { autoAlpha: 0, scaleX: 0.85, duration: 0.3, ease: "power2.out", stagger: 0.07 }, 0.35)
      .from(".meetings", { autoAlpha: 0, y: 20, duration: 0.35, ease: "power2.out" }, "<0.2");
  },

  update(s) {
    const c = s.settings;
    HD.teamColors(s);

    const info = s.data.tournamentInfo || {};
    s.set(".title", c.title);
    s.set(".round", HD.text([info.tournamentName, s.score.phase, s.score.match, s.score.best_of_text], " · "));

    for (const t of s.teams) {
      t.set(".name", s.isTeams ? t.name : HD.ui.name(t.player, t.team));
      t.set(
        ".details",
        s.isTeams
          ? t.team.teamName && HD.playerNames(t.team)
          : HD.join(
              [HD.ui.flag(t.player.country), t.player.real_name, t.player.pronoun],
              HD.html`<span class="dot">·</span>`,
            ),
      );
      const bio = c.bio_key && !s.isTeams && HD.custom(t.player, c.bio_key);
      t.set(".bio", typeof bio === "string" ? bio : "");
      s.characters(t.sel(".character"), {
        source: ["score", s.n, "team", t.n],
        flip_x: t.n === 2,
        ...HD.slideToMiddle(t.n === 1 ? 1 : -1),
      });
    }

    // The rows with something on either side
    const shown = rows(s)
      .map((row) => ({ row, values: s.teams.map((t) => rowValue(row, s, t)) }))
      .filter(({ values }) => values.some(([v]) => v !== null));
    HD.build(
      ".rows",
      shown.map(({ row }) => row.key),
      () =>
        shown.map(
          ({ row }) => HD.html`
          <div class="row row_${row.key}">
            <div class="value v1"></div>
            <div class="label"></div>
            <div class="value v2"></div>
          </div>`,
        ),
    );
    for (const { row, values } of shown) {
      const sel = `.row_${row.key}`;
      const [a, b] = values.map(([, n]) => n);
      const comparable = c.highlight_better && Number.isFinite(a) && Number.isFinite(b) && a !== b;
      const better = comparable && ((row.lower ? a < b : a > b) ? 1 : 2);
      values.forEach(([shown], i) => {
        $(`${sel} .v${i + 1}`).toggleClass("better", better === i + 1);
        HD.set(`${sel} .v${i + 1}`, shown === null ? "–" : shown);
      });
      HD.set(`${sel} .label`, row.label);
    }

    const list = meetings(s).slice(0, Math.max(Number(c.meetings_displayed) || 0, 0));
    $(".meetings").toggleClass("hidden", list.length === 0);
    s.set(".meetings_title", c.meetings_title);
    HD.build(".meeting_list", list, () => list.map(meetingRow));
  },
});
