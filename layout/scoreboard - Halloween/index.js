// The shared scoreboard, plus each side's full character art behind its
// bar on pages that have .hw_art (SSBU): halloween.css makes it a
// black-to-red duotone
HD.layout({
  ...HD.layouts.scoreboard,
  update(s) {
    HD.layouts.scoreboard.update(s);
    for (const t of s.teams) {
      s.characters(t.sel(".hw_art"), {
        asset_key: "full",
        source: ["score", s.n, "team", t.n],
        slice_character: s.isTeams ? [0, 1] : undefined,
        // Facing the score, inside the art's soft edges
        custom_center: t.n === 1 ? [0.6, 0.4] : [0.4, 0.4],
        scale_fill_x: true,
        scale_fill_y: true,
        custom_zoom: 1,
      });
    }
  },
});
