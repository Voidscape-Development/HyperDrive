// The shared scoreboard, plus the phase on its own
HD.layout({
  ...HD.layouts.scoreboard,
  update(s) {
    HD.layouts.scoreboard.update(s);
    s.set(".phase_name", s.score.phase);
  },
});
