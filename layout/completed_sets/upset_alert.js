// upset_alert.html: an alert that drops in when a set pulled with "Pull
// Latest Completed Sets" is an upset (upset_factor at least
// upset_threshold), and leaves after alert_seconds. Sets already there when
// the page loads (or in the first pull after it) aren't announced, unless
// show_latest shows the latest upset among them. Several new upsets take
// turns.

// What tells two sets apart: their players, round and score
const setKey = (set) =>
  JSON.stringify([
    CS.values(set.winner_team).map((p) => p.gamertag),
    CS.values(set.loser_team).map((p) => p.gamertag),
    set.phase_name,
    set.phase_id,
    set.round_name,
    set.winner_score,
    set.loser_score,
  ]);

const seen = new Set();
const pending = [];
let showing = false;

// A side's name: a doubles team's name, else its player's sponsor and tag
const sideName = (set, side) => {
  const players = CS.values(set[`${side}_team`]);
  if (players.length > 1) {
    return HD.html`<span class="cs-tag">${set[`${side}_team_name`] || players.map((p) => p.gamertag).join(" / ")}</span>`;
  }
  return CS.name(players[0] || { gamertag: set[`${side}_team_name`] || "" });
};

const side = (set, side, display) => {
  const players = CS.values(set[`${side}_team`]);
  const player = players.length === 1 ? players[0] : null;
  const seed = Number(set[`${side}_seed`]);
  return HD.html`
    <div class="ua-side ua-${side}">
      ${display.seed && seed > 0 && HD.html`<span class="ua-seed">${seed}</span>`}
      ${player && CS.flags(player, display)}
      <span class="ua-name">${sideName(set, side)}</span>
      ${player && CS.characters(player, display)}
    </div>`;
};

const alertHtml = (set, settings) => {
  const display = settings.display;
  const score = (s) => (Number(set[`${s}_score`]) < 0 ? "DQ" : set[`${s}_score`]);
  const round = HD.text([HD.text([set.phase_name, set.phase_id]), set.round_name], " · ");
  return HD.html`
    <div class="ua-alert">
      <div class="ua-label">${settings.upset_label}</div>
      <div class="ua-body">
        <div class="ua-matchup">
          ${side(set, "winner", display)}
          <span class="ua-score">${score("winner")}<span class="ua-dash">–</span>${score("loser")}</span>
          ${side(set, "loser", display)}
        </div>
        <div class="ua-footer">
          ${display.round && round && HD.html`<span class="ua-round">${round}</span>`}
          ${
            display.upset_factor &&
            HD.html`<span class="ua-factor">${settings.upset_factor_label} <b>${set.upset_factor}</b></span>`
          }
        </div>
      </div>
    </div>`;
};

// Shows the next upset waiting, if none is on screen
const showNext = (settings) => {
  if (showing || pending.length === 0) return;
  showing = true;
  const slot = $(".ua-slot");
  slot.html(String(alertHtml(pending.shift(), settings)));
  const alert = slot.children();
  const seconds = Math.max(Number(settings.alert_seconds) || 8, 1);
  gsap
    .timeline()
    .fromTo(alert, { autoAlpha: 0, y: -60 }, { autoAlpha: 1, y: 0, duration: 0.45, ease: "back.out(1.6)" })
    .from(alert.find(".ua-label"), { scale: 1.6, duration: 0.4, ease: "back.out(3)" }, "<0.15")
    .from(alert.find(".ua-matchup > *"), { autoAlpha: 0, x: -20, duration: 0.3, stagger: 0.08 }, "<0.1")
    .from(alert.find(".ua-footer"), { autoAlpha: 0, duration: 0.3 }, "<0.2");
  // A timeout rather than a GSAP delayed call, as in card.js
  setTimeout(() => {
    gsap.to(alert, {
      autoAlpha: 0,
      y: -60,
      duration: 0.35,
      ease: "power2.in",
      onComplete: () => {
        alert.remove();
        showing = false;
        showNext(settings);
      },
    });
  }, seconds * 1000);
};

HD.layout({
  subscribe: ["completed_sets", "score", "game", "tournamentInfo", "commentary"],
  settings: {
    ...CS.SETTINGS,
    // Seconds each alert stays on screen
    alert_seconds: 8,
    // Show the latest upset already pulled when the page loads (to try
    // the alert out)
    show_latest: false,
    upset_factor_label: "Upset factor",
  },

  intro(tl) {
    tl.fromTo(".ua-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 });
  },

  update(s) {
    if (!CS.changed(s)) return;
    const sets = CS.values(s.data.completed_sets);
    // The newest first: announce the oldest new upset first
    const fresh = sets.filter((set) => !seen.has(setKey(set))).reverse();
    // Nothing was there before: these are past sets, not new ones
    const past = seen.size === 0;
    for (const set of sets) seen.add(setKey(set));

    if (past) {
      const latest = s.settings.show_latest && sets.find((set) => CS.isUpset(set, s.settings));
      if (latest) pending.push(latest);
    } else {
      pending.push(...fresh.filter((set) => CS.isUpset(set, s.settings)));
    }
    showNext(s.settings);
  },
});
