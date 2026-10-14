// list.html and column.html: every set at once, under a title
const showSets = () => gsap.from(".cs-set", { y: 16, autoAlpha: 0, duration: 0.35, stagger: 0.05, ease: "power2.out" });

HD.layout({
  subscribe: ["completed_sets", "score", "game", "tournamentInfo", "commentary"],
  settings: CS.SETTINGS,

  intro(tl) {
    tl.fromTo(".cs-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".cs-title", { x: -30, autoAlpha: 0, duration: 0.4, ease: "power2.out" }, 0)
      .add(showSets(), 0.1);
  },

  update(s) {
    if (!CS.changed(s)) return;
    const sets = CS.sets(s);
    CS.header(s, sets);
    HD.render(
      ".cs-sets",
      sets.map((set) => CS.set(set, s.settings)),
    );
    if (HD.shown()) showSets();
  },
});
