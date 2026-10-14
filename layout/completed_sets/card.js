// card.html: one set at a time, going through them every card_interval
// seconds
let sets = [];
let index = 0;
let timer = null;

// Slides the current set in, the previous one out
const showSet = (s, animate) => {
  const slot = $(".cs-slot");
  const old = slot.children();
  const card = $(String(CS.set(sets[index], s.settings)));
  slot.append(card);
  if (!animate) return old.remove();
  gsap.to(old, { x: -30, autoAlpha: 0, duration: 0.3, ease: "power2.in", onComplete: () => old.remove() });
  gsap.from(card, { x: 30, autoAlpha: 0, duration: 0.35, delay: 0.2, ease: "power2.out" });
};

// A timeout rather than a GSAP delayed call: turning animations off in the
// layout theme speeds those up
const next = (s) => {
  clearTimeout(timer);
  if (sets.length < 2) return;
  timer = setTimeout(() => {
    index = (index + 1) % sets.length;
    showSet(s, true);
    next(s);
  }, Math.max(Number(s.settings.card_interval) || 6, 1) * 1000);
};

HD.layout({
  settings: CS.SETTINGS,

  intro(tl) {
    tl.fromTo(".cs-container", { autoAlpha: 0, y: 20 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" });
  },

  update(s) {
    if (!CS.changed(s)) return;
    sets = CS.sets(s);
    index = 0;
    CS.header(s, sets);
    if (sets.length === 0) {
      clearTimeout(timer);
      $(".cs-slot").empty();
      return;
    }
    showSet(s, HD.shown());
    next(s);
  },
});
