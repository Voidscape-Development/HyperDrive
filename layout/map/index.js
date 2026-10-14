// The players on an OpenStreetMap map (colorize it with a filter, see
// https://github.com/xtk93x/Leaflet.TileLayer.ColorFilter)
const map = L.map("map", { zoomControl: false }).setView([0, 0], 3);

L.tileLayer
  .colorFilter("http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 4,
    zoomSnap: 0,
    zoomControl: false,
    id: "osm.streets",
    filter: [],
  })
  .addTo(map);

HD.layout(HD.layouts.map(map, { line: { color: "blue", dashArray: "5,10" } }));
