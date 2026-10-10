// ticker.html: the sets scroll by in a bar, over and over
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  let scroll = null;

  CSOnChange(async (sets, config) => {
    $(".cs-title").html(CSEscape(config.title)).toggle(config.display.title !== false);
    $(".cs-container").toggleClass("cs-empty", sets.length == 0);

    if (scroll) scroll.kill();
    scroll = null;
    const run = `<div class="cs-run" style="display: flex">${sets
      .map((set) => CSSetHtml(set, config))
      .join("")}</div>`;
    const track = $(".cs-track");
    track.html(run);
    if (sets.length == 0) return;

    // Wait for the flags and icons, which give the sets their width
    await new Promise((resolve) => track.waitForImages(resolve));

    // Enough copies to fill the bar while the first one scrolls out
    const width = track.children().first().outerWidth();
    const copies = Math.ceil($(".cs-viewport").width() / Math.max(width, 1)) + 1;
    track.html(run.repeat(copies));

    gsap.set(track, { x: 0 });
    scroll = gsap.to(track, {
      x: -width,
      duration: width / Math.max(Number(config.ticker_speed) || 90, 1),
      ease: "none",
      repeat: -1,
    });
  });

  Start = async () => {
    gsap
      .timeline()
      .fromTo(
        ".cs-container",
        { autoAlpha: 0, y: 64 },
        { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" },
      );
  };
});
