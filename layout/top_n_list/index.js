// The player list (Top N): a row per slot with its placement, the players'
// names, Twitter, flags, sponsor, avatar and character
// Double elimination placements by rank: 1, 2, 3, 4, 5, 5, 7, 7, 9 (x4),
// 13 (x4), 17 (x8), 25 (x8)...
const placements = (count) => {
  const list = [1, 2, 3, 4];
  for (let size = 2; list.length < count; size *= 2) {
    for (let half = 0; half < 2; half += 1) list.push(...Array(size).fill(list.length + 1));
  }
  return list;
};

const slotRow = ([key, slot], i, ranks) => HD.html`
  <div class="slot slot${i + 1}">${Object.values(slot.player).map(
    (player, p) => HD.html`
      <div class="p${p + 1} player container">
        <div class="score">${ranks[key - 1]}</div>
        <div class="icon avatar"></div>
        <div class="icon online_avatar"></div>
        <div class="name_twitter"><div class="name"></div><div class="twitter"></div></div>
        <div class="sponsor_icon"></div>
        <div class="flags">
          <div class="flagcountry"></div>
          ${player && player.state && player.state.asset && HD.html`<div class="flagstate"></div>`}
        </div>
        <div class="character_container"></div>
      </div>`,
  )}</div>`;

HD.layout({
  intro(tl) {
    $(".slot").each((i, el) => tl.from(el, { x: -100, autoAlpha: 0, duration: 0.4 }, 0.5 + 0.3 * i));
  },

  update(s) {
    if (!s.changed("player_list")) return;
    const slots = Object.entries(_.get(s.data, "player_list.slot") || {});
    const ranks = placements(slots.length);
    HD.render(".players_container", slots.map((slot, i) => slotRow(slot, i, ranks)));

    const instant = { duration: 0 };
    slots.forEach(([key, slot], i) => {
      Object.values(slot.player).forEach((player, p) => {
        if (!player) return;
        const sel = `.slot${i + 1} .p${p + 1}.container`;
        HD.set(`${sel} .name`, HD.html`<span><span class="sponsor">${player.team}</span> ${player.name}</span>`, instant);
        HD.set(`${sel} .flagcountry`, HD.ui.flag(player.country, "flagname"), instant);
        HD.set(`${sel} .flagstate`, HD.ui.flag(player.state, "flagname"), instant);
        HD.set(`${sel} .sponsor_icon`, HD.img(HD.asset(player.sponsor_logo)), instant);
        HD.set(`${sel} .avatar`, HD.img(HD.asset(player.avatar)), instant);
        HD.set(`${sel} .online_avatar`, player.online_avatar ? HD.img(player.online_avatar) : HD.html`<div></div>`, instant);
        HD.set(`${sel} .twitter`, HD.ui.chip("twitter", player.twitter), instant);
        s.characters(`${sel} .character_container`, { source: ["player_list", "slot", key], scale_based_on_parent: true });
      });
    });

    // A new list slides in again
    if (!s.first) HD.restart();
  },
});
