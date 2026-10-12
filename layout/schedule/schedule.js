// The event's schedule (schedule in the program state, from the Event Stats
// widget): its phases, or its waves with show: "waves" (waves.html), with
// their start times and whether they're done, live or upcoming. The
// tournament's logo comes from tournamentInfo.logo. See docs/layout-data.md.

const SC_DEFAULTS = {
  title: "SCHEDULE",
  // "phases" or "waves"
  show: "phases",
  display: {
    logo: true,
    date: true,
    state: true,
    // The next phase or wave, with how long until it starts
    next: true,
  },
  labels: {
    upcoming: "UPCOMING",
    active: "LIVE",
    completed: "DONE",
    next: "UP NEXT",
    wave: "Wave {0}",
    minutes: "in {0} min",
  },
};

function SCEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function SCValues(object) {
  return Object.entries(object || {})
    .filter(([key, value]) => value)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, value]) => value);
}

function SCFormat(label, value) {
  return String(label ?? "").replace("{0}", value ?? "");
}

function SCItemName(item, config) {
  if (item.identifier !== undefined) {
    const wave = SCFormat(config.labels.wave, item.identifier);
    return item.phases && item.phases.length ? `${wave} · ${item.phases.join(", ")}` : wave;
  }
  return item.name;
}

function SCRowHtml(item, config, nextItem) {
  const isNext =
    nextItem &&
    SCItemName(nextItem, config) == SCItemName(item, config) &&
    nextItem.start_at == item.start_at;
  const when = [config.display.date ? item.weekday : "", item.time].filter(Boolean).join(" ");
  const detail =
    item.pools && item.pools.length
      ? item.pools.join(" ")
      : item.groups > 1
        ? `${item.groups} pools`
        : "";
  return `
    <div class="sc-row sc-${SCEscape(item.state)} ${isNext ? "sc-is-next" : ""}">
      <span class="sc-time">${SCEscape(when || "—")}</span>
      <div class="sc-main">
        <span class="sc-name">${SCEscape(SCItemName(item, config))}</span>
        ${detail ? `<span class="sc-detail">${SCEscape(detail)}</span>` : ""}
      </div>
      ${
        config.display.state
          ? `<span class="sc-state">${SCEscape(config.labels[item.state] || item.state)}</span>`
          : ""
      }
    </div>`;
}

function SCHtml(schedule, state, config) {
  const items = SCValues(config.show == "waves" ? schedule.waves : schedule.phases);
  const logo = _.get(state, "tournamentInfo.logo");
  const name = _.get(state, "tournamentInfo.tournamentName");
  const nextItem = schedule.next;
  let next = "";
  if (config.display.next && nextItem) {
    const minutes =
      nextItem.minutes !== undefined && nextItem.minutes !== null
        ? `<span class="sc-next-in">${SCEscape(SCFormat(config.labels.minutes, nextItem.minutes))}</span>`
        : "";
    next = `
      <div class="sc-next">
        <span class="sc-next-label">${SCEscape(config.labels.next)}</span>
        <span class="sc-name">${SCEscape(SCItemName(nextItem, config))}</span>
        ${minutes}
      </div>`;
  }
  return `
    <div class="sc-header">
      ${config.display.logo && logo ? `<img class="sc-logo" src="${SCEscape(logo)}" />` : ""}
      <div class="sc-heading">
        <div class="sc-title">${SCEscape(config.title)}</div>
        ${name ? `<div class="sc-subtitle">${SCEscape(name)}</div>` : ""}
      </div>
    </div>
    ${next}
    <div class="sc-rows">${items.map((item) => SCRowHtml(item, config, nextItem)).join("")}</div>`;
}

LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  Update = async (event) => {
    const schedule = _.get(event.data, "schedule") || {};
    const changed =
      !event.oldData ||
      !_.isEqual(schedule, _.get(event.oldData, "schedule")) ||
      !_.isEqual(_.get(event.data, "tournamentInfo"), _.get(event.oldData, "tournamentInfo"));
    if (!changed) return;
    const config = _.defaultsDeep({}, hd_settings, SC_DEFAULTS);
    const items = config.show == "waves" ? schedule.waves : schedule.phases;
    $(".sc-container").html(SCHtml(schedule, event.data, config));
    $(".sc-container").toggleClass("sc-empty", _.isEmpty(items));
  };

  Start = async () => {
    gsap
      .timeline()
      .fromTo(".sc-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".sc-header, .sc-next", { y: -20, autoAlpha: 0, duration: 0.4, stagger: 0.1 }, 0)
      .from(".sc-row", { x: -20, autoAlpha: 0, duration: 0.3, stagger: 0.05 }, 0.15);
  };
});
