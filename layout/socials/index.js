// Socials lower third: a person's name and their social media accounts
// (socials), each with its platform's icon. The accounts take turns, or
// show side by side with mode "list". The player pages show a player on the
// scoreboard (team and player); commentators.html shows a card for each
// commentator.

// Platforms in the order they're shown; others are left out
const PLATFORMS = [
  "twitter",
  "bluesky",
  "twitch",
  "youtube",
  "tiktok",
  "instagram",
  "kick",
  "discord",
  "steam",
  "xbox",
];

// A person's accounts as [platform, handle], in the settings' order
const accounts = (person, settings) => {
  const socials = { ...(person.twitter && { twitter: person.twitter }), ...(person.socials || {}) };
  const order = (settings.platforms || PLATFORMS).filter((p) => PLATFORMS.includes(p));
  return order.filter((p) => socials[p]).map((p) => [p, socials[p]]);
};

const handle = (platform, text, settings) =>
  settings.twitter_at && platform === "twitter" && !String(text).startsWith("@") ? `@${text}` : text;

const chip = ([platform, text], settings) =>
  HD.html`<span class="social"><span class="icon" style="--icon: url('../icons/${platform}.svg')"></span>${handle(platform, text, settings)}</span>`;

const avatar = (person) => (person.avatar && HD.asset(person.avatar)) || person.online_avatar || null;

// The people shown, each with the selector of their card
const people = (s) => {
  if (s.settings.who === "commentators") {
    return Object.values(s.data.commentary || {})
      .filter((c) => c && c.name)
      .map((c, i) => ({ person: c, sel: `.card${i}`, color: "accent" }));
  }
  const team = s.settings.team === 2 ? 2 : 1;
  const person = _.get(s.score, ["team", team, "player", s.settings.player]) || {};
  return person.name ? [{ person, sel: ".card0", color: `p${team}` }] : [];
};

const cardHtml = (i) => HD.html`
  <div class="card card${i}">
    <div class="avatar"></div>
    <div class="info">
      <div class="name_row"><div class="name"></div><div class="pronoun"></div></div>
      <div class="socials"></div>
    </div>
  </div>`;

const showSocials = (s) => {
  for (const { person, sel } of people(s)) {
    const list = accounts(person, s.settings).map((a) => chip(a, s.settings));
    HD.set(`${sel} .socials`, s.settings.mode === "list" ? HD.html`${list}` : turns.pick(list));
  }
};
const turns = HD.turns(5, (s) => s.settings.mode !== "list" && showSocials(s));

HD.layout({
  subscribe: ["score", "commentary"],

  settings: {
    // "player" (team and player, on the scoreboard) or "commentators"
    who: "player",
    team: 1,
    player: 1,
    // "rotate" (one account at a time) or "list" (all of them)
    mode: "rotate",
    platforms: PLATFORMS,
    show_pronoun: true,
    show_avatar: true,
    // "@" before Twitter handles typed without it
    twitter_at: true,
  },

  init(settings) {
    $("body").addClass(`who_${settings.who} side_${settings.team === 2 ? 2 : 1} mode_${settings.mode}`);
  },

  intro(tl) {
    tl.from(".card", { autoAlpha: 0, x: -40, duration: 0.45, ease: "power3.out", stagger: 0.1 }, 0).from(
      ".card .info > *",
      { autoAlpha: 0, y: 12, duration: 0.3, ease: "power2.out", stagger: 0.06 },
      0.2,
    );
  },

  update(s) {
    if (s.settings.who !== "commentators") HD.teamColors(s);
    const list = people(s);
    HD.build(".cards", list.length, () => list.map((_p, i) => cardHtml(i)));

    for (const { person, sel, color } of list) {
      $(sel).addClass(`color_${color}`);
      HD.set(`${sel} .name`, HD.html`<span class="sponsor">${person.team}</span>${person.name}`);
      HD.set(`${sel} .pronoun`, s.settings.show_pronoun && person.pronoun);
      const picture = s.settings.show_avatar && avatar(person);
      $(`${sel} .avatar`).toggleClass("hidden", !picture);
      HD.set(`${sel} .avatar`, HD.img(picture));
    }
    showSocials(s);
  },
});
