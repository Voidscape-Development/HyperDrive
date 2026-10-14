// Every scoreboard at once: the folder's ssbultimate.html for each one, in
// iframes scaled into a grid, under the tournament's name. For the
// scoreboard folders' multicam.html, with their multicam.css.

// The scoreboards' numbers: score also holds the ruleset and bracket type
const multicamBoards = (data) => Object.keys(data.score || {}).filter((k) => /^\d+$/.test(k));

HD.layouts.multicam = {
  subscribe: ["score", "tournamentInfo"],

  update(s) {
    const boards = multicamBoards(s.data);
    const container = $(".multicam_container");

    if (s.changed(multicamBoards) || container.is(":empty")) {
      HD.render(
        container,
        boards.map(
          (n) =>
            HD.html`<div class="wrap"><iframe src="./ssbultimate.html?scoreboardNumber=${n}&mini=true"></iframe></div>`,
        ),
      );
      // Each scoreboard restyled for the grid
      container.find("iframe").on("load", (e) => {
        $(e.target).contents().find("head").append('<link rel="stylesheet" href="./multicam.css" />');
      });

      const columns = Math.ceil(Math.sqrt(boards.length));
      const gap = parseFloat(container.css("column-gap")) || 0;
      // The container's side padding again as a margin around the grid
      const margin = parseFloat(container.css("padding-left")) + parseFloat(container.css("padding-right"));
      const width = container.width() - margin - (columns - 1) * gap;
      const scale = width / 1920 / columns;
      container.find("iframe").css("transform", `scale(${scale})`);
      container.find(".wrap").css({ width: `${width / columns}px`, height: `${scale * 1080}px` });
    }

    const name = s.data.tournamentInfo.tournamentName;
    s.set(".tournament_name", name && HD.html`<span class="faded">${name}</span><span class="divider">/</span>`);
    s.set(".event_name", s.data.tournamentInfo.eventName);
  },
};
