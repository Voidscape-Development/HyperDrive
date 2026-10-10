// list.html and column.html: every set at once, under a title
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  function ShowSets() {
    return gsap.from(".cs-set", {
      y: 16,
      autoAlpha: 0,
      duration: 0.35,
      stagger: 0.05,
      ease: "power2.out",
    });
  }

  CSOnChange(async (sets, config) => {
    $(".cs-title").html(CSEscape(config.title)).toggle(config.display.title !== false);
    $(".cs-sets").html(sets.map((set) => CSSetHtml(set, config)).join(""));
    $(".cs-container").toggleClass("cs-empty", sets.length == 0);
    if (hd_display.started && hd_display.shown) ShowSets();
  });

  Start = async () => {
    gsap
      .timeline()
      .fromTo(".cs-container", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 })
      .from(".cs-title", { x: -30, autoAlpha: 0, duration: 0.4, ease: "power2.out" }, 0)
      .add(ShowSets(), 0.1);
  };
});
