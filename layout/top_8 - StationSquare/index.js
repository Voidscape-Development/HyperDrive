// Station Square top 8: the winner's character art in a gold circle with
// their name on a banner, and the next seven in rows on the right (their
// placement on a medal colored tab, flag, sponsor and name, the characters
// they played and their record). The tournament's name and date, its
// start.gg link, its logo and the event's name around them.
//
// Each page calls stationSquareTop8() with its placements.
// settings.json's winner / icon set the art.
// series_logo.png in this folder is the right orb's logo.

// "AUG 7 2026", from the date HyperDrive sends (localized), else as it is
function eventDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (isNaN(date)) return String(value).toUpperCase();
  const month = date.toLocaleString("en-US", { month: "short" }).toUpperCase();
  return `${month} ${date.getDate()} ${date.getFullYear()}`;
}

// The slot's players, without empty ones
const slotPlayers = (slot) => Object.values((slot && slot.player) || {}).filter((p) => p && p.name);

// The characters' icons, from the icon asset settings
function characterIcons(players) {
  const key = HD.assetSettings("icon").asset_key || "base_files/icon";
  return players.flatMap((p) =>
    Object.values(p.character || {})
      .filter((c) => c && c.assets && c.assets[key])
      .map((c) => HD.html`<div class="icon">${HD.img(HD.asset(c.assets[key].asset))}</div>`),
  );
}

// A country or state flag, without its code
const flagImage = (place) => place && HD.img(HD.asset(place.asset));

const placementClass = (placement) => (placement === 2 ? "silver" : placement === 3 ? "bronze" : "");

const rowMarkup = (placement, i) => HD.html`
  <div class="row row${i + 1} ${placementClass(placement)}">
    <div class="placement"><div class="number">${placement}</div></div>
    <div class="row_body">
      <div class="flags">
        <div class="flagcountry"></div>
        <div class="flagstate"></div>
      </div>
      <div class="names">
        <div class="name"></div>
        <div class="team_members"></div>
      </div>
      <div class="extras">
        <div class="icons"></div>
        <div class="record"></div>
      </div>
    </div>
  </div>`;

function stationSquareTop8(placements) {
  return {
    subscribe: ["player_list", "game", "tournamentInfo"],

    intro(tl) {
      tl.from(".ss_title", { autoAlpha: 0, x: -60, duration: 0.5, ease: "power2.out" }, 0);
      tl.from([".ss_link", ".ss_date"], { autoAlpha: 0, y: -30, duration: 0.5, ease: "power2.out" }, 0.1);
      tl.from(".winner", { autoAlpha: 0, scale: 0.6, duration: 0.7, ease: "back.out(1.4)" }, 0.2);
      tl.from(".rows_panel", { autoAlpha: 0, duration: 0.4 }, 0.3);
      tl.from(".row", { autoAlpha: 0, x: 120, duration: 0.4, stagger: 0.08, ease: "power2.out" }, 0.4);
      tl.from(".ss_bottom", { autoAlpha: 0, y: 80, duration: 0.5, ease: "power2.out" }, 0.6);
    },

    update(s) {
      const info = s.data.tournamentInfo || {};
      s.set(".ss_title", info.tournamentName);
      s.set(".ss_date", eventDate(info.eventStartAt || info.startAt));
      s.set(".ss_link .slug", info.shortLink ? `/${info.shortLink}` : "");
      gsap.set(".ss_link", { display: info.shortLink ? "" : "none" });
      s.set(".ss_bottom .event", info.eventName ? `${info.eventName} Top Finalists` : "Top Finalists");
      // The tournament's logo, else start.gg's
      $(".tournament_logo").css("--logo", `url("${info.logo || "../icons/startgg.svg"}")`);

      if (!s.changed("player_list") && !s.changed("game")) return;
      const slots = Object.entries(_.get(s.data, "player_list.slot") || {});
      const [winner, ...rest] = slots;
      const rows = rest.slice(0, placements.length - 1);
      HD.build(".rows", rows.length, () => rows.map((_slot, i) => rowMarkup(placements[i + 1], i)));

      const instant = { duration: 0 };
      if (winner) {
        const [key, slot] = winner;
        const players = slotPlayers(slot);
        const isTeams = players.length > 1;
        s.set(".winner .name", slot.name || HD.playerNames(slot) || "", instant);
        s.characters(".winner .character_container", {
          source: ["player_list", "slot", key],
          load_settings_path: "winner",
          slice_character: isTeams ? [0, 1] : undefined,
        });
      }

      rows.forEach(([, slot], i) => {
        const row = `.row${i + 1}`;
        const players = slotPlayers(slot);
        const isTeams = players.length > 1;
        const player = players[0] || {};
        if (isTeams) {
          // The team's name with its players under it, or their names
          s.set(`${row} .name`, slot.name || HD.playerNames(slot), instant);
          s.set(`${row} .team_members`, slot.name ? HD.playerNames(slot) : "", instant);
        } else {
          s.set(
            `${row} .name`,
            HD.html`${player.team && HD.html`<span class="sponsor">${player.team}</span>`}${player.name || ""}`,
            instant,
          );
          s.set(`${row} .team_members`, "", instant);
        }
        $(row).toggleClass("teams", isTeams && !!slot.name);
        s.set(`${row} .flagcountry`, !isTeams && flagImage(player.country), instant);
        s.set(`${row} .flagstate`, !isTeams && flagImage(player.state), instant);
        HD.render(`${row} .icons`, characterIcons(players));
        s.set(
          `${row} .record`,
          !isTeams && player.wins != null && player.losses != null ? `${player.wins}W - ${player.losses}L` : "",
          instant,
        );
      });
    },
  };
}
