// ticker.html: the sets scroll by in a bar, over and over
let scroll = null;

HD.layout({
  settings: CS.SETTINGS,

  intro(tl) {
    tl.fromTo(".cs-container", { autoAlpha: 0, y: 64 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" });
  },

  async update(s) {
    if (!CS.changed(s)) return;
    const sets = CS.sets(s);
    CS.header(s, sets);

    if (scroll) scroll.kill();
    scroll = null;
    const run = HD.html`<div class="cs-run" style="display: flex">${sets.map((set) => CS.set(set, s.settings))}</div>`;
    const track = $(".cs-track");
    HD.render(track, run);
    if (sets.length === 0) return;

    // The flags and icons give the sets their width
    await new Promise((resolve) => track.waitForImages(resolve));

    // Enough copies to fill the bar while the first one scrolls out
    const width = track.children().first().outerWidth();
    const copies = Math.ceil($(".cs-viewport").width() / Math.max(width, 1)) + 1;
    HD.render(track, Array(copies).fill(run));

    gsap.set(track, { x: 0 });
    scroll = gsap.to(track, {
      x: -width,
      duration: width / Math.max(Number(s.settings.ticker_speed) || 90, 1),
      ease: "none",
      repeat: -1,
    });
  },
});
