// card.html: one set at a time, going through them every card_interval
// seconds
LoadEverything().then(() => {
  gsap.config({ nullTargetWarn: false, trialWarn: false });

  let sets = [];
  let config = null;
  let index = 0;
  let timer = null;

  function Show(first) {
    const slot = $(".cs-slot");
    const old = slot.children();
    const card = $(CSSetHtml(sets[index], config));
    slot.append(card);

    if (first) {
      old.remove();
      return;
    }
    gsap.to(old, {
      x: -30,
      autoAlpha: 0,
      duration: 0.3,
      ease: "power2.in",
      onComplete: () => old.remove(),
    });
    gsap.from(card, { x: 30, autoAlpha: 0, duration: 0.35, delay: 0.2, ease: "power2.out" });
  }

  // Not a gsap delayed call: turning animations off in the layout theme
  // speeds those up
  function Next() {
    clearTimeout(timer);
    if (sets.length < 2) return;
    timer = setTimeout(
      () => {
        index = (index + 1) % sets.length;
        Show(false);
        Next();
      },
      Math.max(Number(config.card_interval) || 6, 1) * 1000,
    );
  }

  CSOnChange(async (newSets, newConfig) => {
    sets = newSets;
    config = newConfig;
    index = 0;
    $(".cs-title").html(CSEscape(config.title)).toggle(config.display.title !== false);
    $(".cs-container").toggleClass("cs-empty", sets.length == 0);
    if (sets.length == 0) {
      clearTimeout(timer);
      $(".cs-slot").empty();
      return;
    }
    Show(!(hd_display.started && hd_display.shown));
    Next();
  });

  Start = async () => {
    gsap
      .timeline()
      .fromTo(
        ".cs-container",
        { autoAlpha: 0, y: 20 },
        { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" },
      );
  };
});
