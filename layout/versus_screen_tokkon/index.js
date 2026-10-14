// The standard versus screen, with each player's controller
HD.layout({
  ...HD.layouts.versus,
  update(s) {
    HD.layouts.versus.update(s);
    if (!s.isTeams) s.teams.forEach(VS.controller);
  },
});
