// Top 8 from the player list, shared by layout/top_8, top_8_single_elim and
// the MTF variant: the winner big, then 2nd-4th, then the rest (or all the
// same size with the same_size page option), each with their placement,
// name, flags, sponsor, record and character art on a backdrop in its
// colors. settings.json's top_1 / top_4 / top_8 / same_size set the art.
//
// MTF pages (body.mtf) also have a header (tournament, date, entrants),
// take the scoreboard's team colors and have no color backdrops.
(() => {
  const mtf = () => document.body.classList.contains("mtf");

  const slotCard = (slot, i, placement) => {
    const player = Object.values(slot.player)[0] || {};
    return HD.html`
      <div class="slot slot${i + 1}">
        <div class="p1 player container">
          <div class="score">${placement}</div>
          <div class="record-chip"></div>
          <div class="footer">
            <div class="name_twitter">
              <div class="name"></div>
              <div class="team_members"></div>
              <div class="twitter"></div>
            </div>
            <div class="sponsor_icon"></div>
          </div>
          <div class="flags">
            <div class="flagcountry"></div>
            ${player.state && player.state.asset && HD.html`<div class="flagstate"></div>`}
          </div>
          <div class="character_container"></div>
        </div>
      </div>`;
  };

  // Code, then the flag as a background
  const flag = (place) =>
    place &&
    place.asset &&
    HD.html`<div class='flagname'>${place.code}</div><div class='flag' style="background-image: url('${HD.asset(place.asset)}')"></div>`;

  // A diagonal gradient in the art's colors behind it: palette colors
  // [a, b] at opacities [x, y]
  function colorBackdrop(container, colors, alphas) {
    const paint = (target, img) => {
      const apply = () => {
        try {
          const palette = new ColorThief().getPalette(img, 5);
          if (!palette || palette.length === 0) return;
          const [c1, c2] = colors.map((i) => palette[i] || palette[palette.length - 1]);
          $(target).css("background", `linear-gradient(135deg, rgba(${c1}, ${alphas[0]}) 0%, rgba(${c2}, ${alphas[1]}) 100%)`);
        } catch (e) {
          console.log("No colors from the character art:", e);
        }
      };
      if (img.complete) apply();
      else img.onload = apply;
    };
    const characters = container.find(".hd_character");
    // Several characters with dividers: each its own
    if (characters.length > 1) {
      characters.each((_i, el) => {
        const img = $(el).find("img.hd-img").get(0);
        if (img) paint(el, img);
      });
    } else {
      const img = container.find("img.hd-img").get(0);
      if (img) paint(container, img);
    }
  }

  // placements: what each slot shows, by its order
  HD.layouts.top8 = (placements) => ({
    intro(tl) {
      tl.from(".container", { duration: 1, width: 0, ease: "power2.inOut" }, 0);
      if (mtf()) tl.from(".mtf_header", { duration: 0.6, autoAlpha: 0, y: -20, ease: "power2.out" }, 0);
    },

    update(s) {
      if (mtf()) {
        HD.teamColors(s, ["score-bg-color"]);
        const info = s.data.tournamentInfo;
        s.set(".mtf_header .tournament_name", info.tournamentName);
        s.set(".mtf_header .event_date", info.eventStartAt || info.startAt);
        s.set(".mtf_header .entrants", info.numEntrants ? `${info.numEntrants} Entrants` : "");
      }
      if (!s.changed("player_list")) return;

      const slots = Object.entries(_.get(s.data, "player_list.slot") || {});
      const sameSize = !!s.settings.equal_sizes;
      // The winner, 2nd to 4th and the rest in containers of their own
      const groups = { top1: [], top4: [], top8: [] };
      slots.forEach(([, slot], i) => {
        const group = sameSize ? "top8" : i === 0 ? "top1" : i < 4 ? "top4" : "top8";
        groups[group].push(slotCard(slot, i, placements[i]));
      });
      for (const [group, cards] of Object.entries(groups)) HD.render(`.${group}_container`, cards);

      const isTeams = slots.length > 0 && _.size(slots[0][1].player) > 1;
      const instant = { duration: 0 };
      for (const [key, slot] of slots) {
        const card = `.slot${key} .p1.container`;
        const settingsPath = sameSize ? "same_size" : key == 1 ? "top_1" : key <= 4 ? "top_4" : "top_8";
        const art = s.characters(`${card} .character_container`, {
          source: ["player_list", "slot", key],
          load_settings_path: settingsPath,
          slice_character: isTeams ? [0, 1] : undefined,
        });
        if (!mtf()) {
          // Teams: lighter, from the art's less dominant colors
          art.then(() =>
            colorBackdrop($(`${card} .character_container`), isTeams ? [2, 3] : [0, 1], isTeams ? [0.6, 0.3] : [0.85, 0.6]),
          );
        }

        if (isTeams) {
          // The team's name with its players under it, or their names
          const names = HD.playerNames(slot);
          HD.set(`${card} .name`, slot.name || names);
          if (slot.name) HD.set(`${card} .team_members`, names);
          continue;
        }
        const player = slot.player[1];
        if (!player) continue;
        HD.set(
          `${card} .name`,
          mtf()
            ? HD.html`${player.team && HD.html`<span class="sponsor">${player.team}</span>`} ${player.name}`
            : HD.html`<span class="sponsor">${player.team}</span> ${player.name}`,
          instant,
        );
        HD.set(`${card} .flagcountry`, flag(player.country), instant);
        HD.set(`${card} .flagstate`, flag(player.state), instant);
        HD.set(
          `${card} .sponsor_icon`,
          player.sponsor_logo
            ? HD.html`<div style="background-image: url('${HD.asset(player.sponsor_logo)}')"></div>`
            : HD.html`<div></div>`,
          instant,
        );
        HD.set(`${card} .twitter`, HD.ui.chip("twitter", player.twitter), instant);
        HD.set(`${card} .record-chip`, player.wins != null && player.losses != null ? `${player.wins}W - ${player.losses}L` : "", instant);
      }
    },
  });
})();
