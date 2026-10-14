// The player list: a block per slot with its name and its players (name,
// Twitter, flags, sponsor, avatar, character)
const flag = (place) => place && place.asset && HD.html`<div class='flag' style="background-image: url('${HD.asset(place.asset)}')"></div>`;
const background = (src) => src && HD.html`<div style="background-image: url('${src}')"></div>`;

HD.layout({
  intro(tl) {
    tl.from(".container", { duration: 1, width: 0, ease: "power2.inOut" }, 0);
  },

  update(s) {
    if (s.changed("player_list")) {
      const slots = Object.entries(_.get(s.data, "player_list.slot") || {});
      HD.render(
        ".players_container",
        slots.map(
          ([, slot], i) => HD.html`
            <div class="slot slot${i + 1}">
              <div class="container title"></div>
              ${Object.values(slot.player).map(
                (_p, p) => HD.html`
                  <div class="p${p + 1} player container">
                    <div class="icon avatar"></div>
                    <div class="icon online_avatar"></div>
                    <div class="flagcountry"></div>
                    <div class="flagstate"></div>
                    <div class="sponsor_icon"></div>
                    <div class="name_twitter"><div class="name"></div><div class="twitter"></div></div>
                    <div class="filler"></div>
                    <div class="character_container"></div>
                  </div>`,
              )}
            </div>`,
        ),
      );

      const instant = { duration: 0 };
      slots.forEach(([key, slot], i) => {
        HD.set(`.slot${i + 1} .title`, slot.name);
        Object.values(slot.player).forEach((player, p) => {
          if (!player) return;
          const sel = `.slot${i + 1} .p${p + 1}.container`;
          HD.set(`${sel} .name`, HD.html`<span><span class="sponsor">${player.team}</span> ${player.name}</span>`, instant);
          HD.set(`${sel} .flagcountry`, flag(player.country), instant);
          HD.set(`${sel} .flagstate`, flag(player.state), instant);
          HD.set(`${sel} .sponsor_icon`, background(HD.asset(player.sponsor_logo)), instant);
          HD.set(`${sel} .avatar`, background(HD.asset(player.avatar)), instant);
          HD.set(`${sel} .online_avatar`, background(player.online_avatar), instant);
          HD.set(`${sel} .twitter`, HD.ui.chip("twitter", player.twitter), instant);
          s.characters(`${sel} .character_container`, {
            source: ["player_list", "slot", key, "player", p + 1],
            custom_center: [0.5, 0.5],
            scale_based_on_parent: true,
          });
        });
      });
    }

    // Empty fields take no room
    $(".container div:has(>.text:empty)").css({ "margin-left": "0", "margin-right": "0" });
    $(".container div:not(:has(>.text:empty))").css({ "margin-left": "", "margin-right": "" });
  },
});
