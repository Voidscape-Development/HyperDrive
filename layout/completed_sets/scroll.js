// scroll.html: a full-screen column of sets scrolling up, over and over.
// Fits any page size, a portrait one (1080x1920) included.
let scroll = null;

HD.layout({
  subscribe: ["completed_sets", "score", "game", "tournamentInfo", "commentary"],
  settings: CS.SETTINGS,

  intro(tl) {
    tl.fromTo(".cs-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".cs-title", { y: -30, autoAlpha: 0, duration: 0.4, ease: "power2.out" }, 0)
      .from(".cs-viewport", { y: 40, autoAlpha: 0, duration: 0.5, ease: "power2.out" }, 0.1);
  },

  async update(s) {
    if (!CS.changed(s)) return;
    const sets = CS.sets(s);
    CS.header(s, sets);

    if (scroll) scroll.kill();
    scroll = null;
    const run = HD.html`<div class="cs-run">${sets.map((set) => CS.set(set, s.settings))}</div>`;
    const track = $(".cs-track");
    HD.render(track, run);
    gsap.set(track, { y: 0 });
    if (sets.length === 0) return;

    // The flags and icons give the sets their height
    await HD.imagesLoaded(track);

    // The sets fit between the fades: no need to scroll
    const height = track.children().first().outerHeight();
    const viewport = $(".cs-viewport").height();
    const fade = parseFloat(getComputedStyle($(".cs-viewport")[0]).getPropertyValue("--cs-fade")) || 0;
    if (height <= viewport - 2 * fade) return;

    // Enough copies to fill the page while the first one scrolls out
    const copies = Math.ceil(viewport / Math.max(height, 1)) + 1;
    HD.render(track, Array(copies).fill(run));

    scroll = gsap.to(track, {
      y: -height,
      duration: height / Math.max(Number(s.settings.scroll_speed) || 60, 1),
      ease: "none",
      repeat: -1,
    });
  },
});
