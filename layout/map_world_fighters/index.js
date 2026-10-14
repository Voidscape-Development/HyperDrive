// The players on a world map (map.svg, in the Mollweide projection), with
// their flag, country and state
const crs = new L.Proj.CRS("ESRI:53009", "+proj=moll +lon_0=0 +x_0=0 +y_0=0 +a=6371000 +b=6371000 +units=m +no_defs", {
  resolutions: [65536, 32768, 16384, 8192, 4096, 2048],
});

const map = L.map("map", { center: [0, 0], zoom: 1, minZoom: 0, crs, zoomSnap: 0, zoomControl: false });
L.Proj.imageOverlay("./map.svg", L.bounds([-18019909.21, -9009954.61], [18019909.21, 9009954.61])).addTo(map);
map.fitBounds([
  [0, 180],
  [0, -180],
]);

HD.layout(
  HD.layouts.map(map, {
    icons: [24, 64],
    iconClass: "blink",
    offset: 12,
    fly: false,
    line: { color: "lightblue", dashArray: "5,14", weight: 8 },
    tooltip: (p) => HD.html`
      <div style="display: flex; flex-direction: column; align-items: center;">
        <div class="player_name">${p.name}</div>
        ${p.country.asset && HD.html`<div class="flag" style="background-image: url('${HD.asset(p.country.asset)}')"></div>`}
        <div class="player_country">${p.country.name}</div>
        <div class="player_state">${p.state.name}</div>
      </div>`,
  }),
);
