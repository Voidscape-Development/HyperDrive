// The players on a map, shared by layout/map and map_world_fighters: a
// marker at each one's state (or country), the lines between them, and
// the distance and estimated ping (pings.json: servers and the pings
// between them) between the farthest apart.
//
// Page options: country_only (markers at countries), no_hud (no ping and
// distance). A player without a location gets a question mark.
//
// HD.layouts.map(map, options), map a Leaflet map. options: icons ([known,
// unknown] sizes), iconClass, offset (tooltip distance), tooltip(player)
// (HTML), line (polyline options), fly (zoom to the players, the lines
// once there)
(() => {
  // -------------------------------------------------------------------
  // Distances and pings

  const radians = (deg) => (deg * Math.PI) / 180;

  // Great circle distance
  function distanceKm([lat1, lon1], [lat2, lon2]) {
    const a =
      Math.sin(radians(lat2 - lat1) / 2) ** 2 +
      Math.cos(radians(lat1)) * Math.cos(radians(lat2)) * Math.sin(radians(lon2 - lon1) / 2) ** 2;
    return 2 * Math.asin(Math.sqrt(a)) * 6371;
  }

  // The ping server nearest to a position
  const closestServer = (servers, [lat, lng]) =>
    _.minBy(servers, (s) => Math.hypot(parseFloat(s.latitude) - lat, parseFloat(s.longitude) - lng));

  const pairs = (list) => list.flatMap((a, i) => list.slice(i + 1).map((b) => [a, b]));

  // -------------------------------------------------------------------
  // Players and the HUD

  // Where a player is: [lat, lng], and whether it's known
  function locate(player, countryOnly) {
    const place = player.state.latitude != null && !countryOnly ? player.state : player.country;
    const pos = [parseFloat(place.latitude), parseFloat(place.longitude)];
    const known = !pos.some(Number.isNaN);
    return { player, pos: known ? pos : [0, 0], known, area: known && (!player.state.latitude || countryOnly) };
  }

  // The HUD: the distance and estimated ping between the farthest apart
  function hud(spots, servers) {
    if (spots.some((s) => !s.known)) {
      $("#ping").text("ESTIMATED PING: ???");
      $("#distance").text("DISTANCE: ???");
      return;
    }
    const nearest = spots.map((s) => closestServer(servers, s.pos));
    const ping = _.max(pairs(nearest).map(([a, b]) => (a === b ? 0 : Math.max(a.pings[b.id], b.pings[a.id])))) || 0;
    $("#ping").text(`ESTIMATED PING: ${ping < 20 ? "< 20" : ping.toFixed(2)} ms`);

    const km = _.max(pairs(spots).map(([a, b]) => distanceKm(a.pos, b.pos))) || 0;
    const distance = km < 100 ? "< 100 Km / < 62 mi" : `${km.toFixed(2)} Km / ${(km * 0.621371).toFixed(2)} mi`;
    $("#distance").text(`${spots.length === 2 ? "DISTANCE" : "MAX DISTANCE"}: ${distance}`);
  }

  // -------------------------------------------------------------------
  // The layout

  HD.layouts.map = (
    map,
    { icons = [12, 32], iconClass = "", offset = 8, tooltip = (p) => HD.html`${p.name}`, line, fly = true },
  ) => {
    let servers = [];
    let layers = [];
    const add = (layer) => (layers.push(layer.addTo(map)), layer);

    return {
      subscribe: ["score"],
      settings: { country_only: false, no_hud: false },

      async init() {
        servers = await $.ajax({ dataType: "json", url: "./pings.json", cache: false });
      },

      update(s) {
        if (!s.scoreChanged((score) => [score.team[1].player, score.team[2].player])) return;
        layers.forEach((layer) => layer.remove());
        layers = [];

        const spots = s.teams
          .flatMap((t) => Object.values(t.team.player || {}))
          .filter((p) => p && p.name)
          .map((p) => locate(p, s.settings.country_only));

        const directions = ["top", "bottom", "left", "right"];
        spots.forEach((spot, i) => {
          // Tooltips of players at the same spot go different ways
          const same = spots.slice(0, i).filter((other) => _.isEqual(other.pos, spot.pos)).length;
          const direction = directions[same % directions.length];
          const distance = spot.known ? offset : offset * 2;
          const size = icons[spot.known ? 0 : 1];
          add(
            L.marker(spot.pos, {
              icon: L.icon({
                iconUrl: spot.known ? "./marker.svg" : "./questionmark.svg",
                iconSize: [size, size],
                iconAnchor: [size / 2, size / 2],
                className: iconClass,
              }),
            }),
          )
            .bindTooltip(String(tooltip(spot.player)), {
              direction,
              className: "leaflet-tooltip-own",
              offset: { top: [0, -distance], bottom: [0, distance], left: [-distance, 0], right: [distance, 0] }[
                direction
              ],
            })
            .openTooltip();
          // A pulsing ring where only the country (or nothing) is known
          if (!spot.known || spot.area) {
            add(
              L.marker(spot.pos, {
                icon: L.divIcon({
                  html: `<div class="gps_ring ${spot.known ? "" : "gps_ring_big"}"></div>`,
                  className: "css-icon",
                  iconAnchor: [64, 64],
                }),
              }),
            );
          }
        });

        if (s.settings.no_hud) {
          $(".overlay").css("height", 0);
        } else {
          hud(spots, servers);
          gsap.to(".overlay-element", { duration: 1, autoAlpha: 1 });
        }

        const lines = () => add(L.polyline(pairs(spots.filter((x) => x.known).map((x) => x.pos)), line));
        if (!fly) return lines();

        // Zoom to the players, with room around the unknown ones
        let bounds = L.latLngBounds(spots.map((x) => x.pos));
        for (const spot of spots) if (!spot.known) bounds = bounds.extend(L.latLng(spot.pos).toBounds(2000000));
        map.once("moveend", lines);
        map.flyToBounds(bounds, {
          paddingTopLeft: [30, 30 + $(".overlay").outerHeight()],
          paddingBottomRight: [30, 30],
          duration: 1.2,
          easeLinearity: 0.000001,
        });
      },
    };
  };
})();
