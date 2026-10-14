// A team's characters, or one player's (page options team and player), one
// at a time: they crossfade every 3 seconds, with which one it is ("2/3")
let shown = 0;

const showCharacter = (fade) => {
  const characters = $(".hd_character").toArray();
  if (characters.length === 0) return;
  shown %= characters.length;
  gsap.to(characters, { autoAlpha: (i) => (i === shown ? 1 : 0), duration: fade ? 1 : 0 });
  $(".index_display")
    .text(`${shown + 1}/${characters.length}`)
    .css("opacity", characters.length < 2 ? 0 : 1);
};

HD.every(3, () => {
  shown += 1;
  showCharacter(true);
});

HD.layout({
  subscribe: ["score", "game", "tournamentInfo", "commentary"],
  async update(s) {
    const { team, player } = s.settings;
    // They come in hidden: showCharacter() shows one
    await s.characters(".container", {
      source: ["score", s.n, "team", team, ...(player != null ? ["player", player] : [])],
      out: { autoAlpha: 0, duration: 0 },
      in: { autoAlpha: 0, duration: 0 },
    });
    showCharacter(false);
  },
});
