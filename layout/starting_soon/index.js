// Starting soon (and be right back): a full screen for before the stream
// and its breaks. The tournament's logo and name over its banner, a title
// and a countdown, the next sets on stream with when they should start
// (stream_queue), and the latest results scrolling along the bottom
// (completed_sets).

// -------------------------------------------------------------------
// Up next

// The queue shown: the stream in settings.stream, the one linked to the
// scoreboard, else the first with sets
const queue = (s) => {
  const streams = _.get(s.data, "stream_queue.streams") || [];
  const named = (name) => streams.find((st) => String(st.name).toLowerCase() === String(name).toLowerCase());
  const stream =
    (s.settings.stream && named(s.settings.stream)) ||
    streams.find((st) => String(st.scoreboard) === String(s.n)) ||
    streams.find((st) => _.size(st.sets) > 0);
  return Object.values((stream && stream.sets) || {}).filter((set) => set && set.team);
};

// A side of a queued set: its flag and name (a doubles team's name)
const side = (team) => {
  if (!team) return HD.html`<span class="tbd">TBD</span>`;
  const players = HD.players(team);
  const player = players[0] || {};
  if (players.length > 1) return HD.html`<span class="tag">${team.teamName || HD.playerNames(team)}</span>`;
  return HD.html`${_.get(player, "country.asset") && HD.img(HD.asset(player.country.asset), "class='flag'")}<span class="sponsor">${player.team}</span><span class="tag">${player.name}</span>`;
};

const eta = (set, settings) => {
  if (set.eta_minutes === 0) return settings.now_label;
  if (!(set.eta_minutes > 0)) return "";
  if (settings.eta_format === "time" && set.eta) return clockTime(new Date(set.eta * 1000), settings);
  return `~${set.eta_minutes} min`;
};

const setRow = (set, settings) => HD.html`
  <div class="set">
    <div class="set_info">
      <div class="round">${HD.text([set.phase, set.match], " · ")}</div>
      <div class="eta">${eta(set, settings)}</div>
    </div>
    <div class="matchup">
      <div class="side t1">${side(set.team[1])}</div>
      <div class="vs">vs</div>
      <div class="side t2">${side(set.team[2])}</div>
    </div>
  </div>`;

// -------------------------------------------------------------------
// Results

const result = (set, settings) => {
  const name = (side) => {
    const players = Object.values(set[`${side}_team`] || {}).filter(Boolean);
    return set[`${side}_team_name`] || players.map((p) => p.gamertag).join(" / ");
  };
  const score = (side) => (Number(set[`${side}_score`]) < 0 ? "DQ" : set[`${side}_score`]);
  const upset = Number(settings.upset_threshold) > 0 && Number(set.upset_factor) >= Number(settings.upset_threshold);
  return HD.html`
    <span class="result">
      ${upset && HD.html`<span class="upset">${settings.upset_label}</span>`}
      <span class="winner">${name("winner")}</span>
      <span class="result_score">${score("winner")}–${score("loser")}</span>
      <span class="loser">${name("loser")}</span>
      <span class="result_round">${set.round_name}</span>
    </span>`;
};

const results = (s) =>
  Object.entries(s.data.completed_sets || {})
    .filter(([, set]) => set)
    .sort(([a], [b]) => a - b)
    .map(([, set]) => set);

// Scrolls the results right to left, without end: the list is there twice
const scroll = (speed) => {
  const track = $(".ticker_track");
  gsap.killTweensOf(track);
  gsap.set(track, { x: 0 });
  const width = track[0].scrollWidth / 2;
  if (width > 0)
    gsap.to(track, { x: -width, duration: width / Math.max(Number(speed) || 80, 1), ease: "none", repeat: -1 });
};

// -------------------------------------------------------------------
// Countdown

function clockTime(date, settings) {
  return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: !settings.clock_24h });
}

// When the countdown ends (ms since the epoch), or null for none:
// countdown_to ("19:30" today), countdown_minutes from when the page
// loaded, else the first queued set's start
const loaded = Date.now();
const countdownEnd = (s) => {
  const c = s.settings;
  const at = /^(\d{1,2}):(\d{2})$/.exec(String(c.countdown_to || "").trim());
  if (at) {
    const end = new Date();
    end.setHours(Number(at[1]), Number(at[2]), 0, 0);
    return end.getTime();
  }
  if (Number(c.countdown_minutes) > 0) return loaded + Number(c.countdown_minutes) * 60000;
  if (c.countdown_from_queue) {
    const next = queue(s).find((set) => set.eta);
    if (next) return next.eta * 1000;
  }
  return null;
};

const pad = (n) => String(n).padStart(2, "0");

const countdown = (s) => {
  const end = countdownEnd(s);
  $(".countdown_box").toggleClass("hidden", end === null);
  if (end === null) return;
  const left = Math.max(0, Math.ceil((end - Date.now()) / 1000));
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const time = h > 0 ? `${h}:${pad(m)}:${pad(left % 60)}` : `${pad(m)}:${pad(left % 60)}`;
  $(".countdown_label").text(left > 0 ? s.settings.countdown_label : "");
  $(".countdown").text(left > 0 ? time : s.settings.countdown_done);
};

HD.layout({
  subscribe: ["stream_queue", "completed_sets", "score", "game", "tournamentInfo"],

  settings: {
    title: "Starting soon",
    subtitle: "",
    // The countdown: to a time today ("19:30"), for some minutes from
    // when the source loads, or to the first queued set's start
    countdown_to: "",
    countdown_minutes: 0,
    countdown_from_queue: true,
    countdown_label: "Starting in",
    countdown_done: "Any moment now",
    clock_24h: false,
    // Up next: the stream's queue ("" for the one linked to the
    // scoreboard, else the first with sets)
    stream: "",
    sets_displayed: 3,
    up_next_title: "Up next",
    now_label: "Now",
    // "minutes" (~16 min) or "time" (7:42 PM)
    eta_format: "minutes",
    // The results along the bottom
    show_results: true,
    results_title: "Results",
    ticker_speed: 80,
    upset_threshold: 1,
    upset_label: "Upset",
    // The start.gg tournament's banner and logo when it has them
    show_banner: true,
    use_tournament_logo: true,
  },

  init() {
    HD.every(1, countdown);
  },

  intro(tl) {
    tl.from(".background", { autoAlpha: 0, duration: 0.6 }, 0)
      .from(".brand > *", { autoAlpha: 0, x: -40, duration: 0.45, ease: "power3.out", stagger: 0.08 }, 0.2)
      .from(".up_next", { autoAlpha: 0, x: 60, duration: 0.5, ease: "power3.out" }, 0.35)
      .from(".set", { autoAlpha: 0, y: 20, duration: 0.35, ease: "power2.out", stagger: 0.1 }, "<0.2")
      .from(".ticker", { yPercent: 100, duration: 0.5, ease: "power3.out" }, 0.5);
  },

  update(s) {
    const c = s.settings;
    const info = s.data.tournamentInfo || {};

    const banner = c.show_banner && info.banner;
    $(".background").css("background-image", banner ? `url("${banner}")` : "");
    $("body").toggleClass("has_banner", Boolean(banner));
    s.set(".logo", HD.img((c.use_tournament_logo && info.logo) || "../logo.png"));
    s.set(".tournament_name", info.tournamentName);
    s.set(".event_name", HD.text([info.eventName, c.subtitle], " · "));
    s.set(".title", c.title);

    const sets = queue(s).slice(0, Math.max(Number(c.sets_displayed) || 0, 0));
    s.set(".up_next_title", c.up_next_title);
    HD.build(".sets", [sets, c.eta_format], () => sets.map((set) => setRow(set, c)));
    $(".up_next").toggleClass("hidden", sets.length === 0);

    const list = c.show_results ? results(s) : [];
    $(".ticker").toggleClass("hidden", list.length === 0);
    s.set(".ticker_title", c.results_title);
    const items = list.map((set) => result(set, c));
    if (HD.build(".ticker_track", items, () => [items, items])) scroll(c.ticker_speed);

    countdown(s);
  },
});
