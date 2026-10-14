// Pokkén versus screen: the standard one with its own intro (the logo
// moves up, a two-stage VS), art sliding in from the edges, and the phase
// and best of on one line
const base = VS.layout({
  slide: (way) => ({
    out: { x: `${-way * 100}%`, stagger: 0.2 },
    in: { x: 0, duration: 1, ease: "expo.out", autoAlpha: 1, stagger: 0.2 },
  }),
  stage: { from: 2, duration: 0.8 },
  teamName: (t) => HD.html`<span><div>${t.name}</div></span>`,
});

HD.layout({
  ...base,

  intro(tl) {
    const fade = (duration) => ({ duration, opacity: 0, ease: "power2.inOut" });
    tl.to(".logo", { duration: 0.8, top: 160, scale: 0.4 }, 0)
      .from(".tournament", fade(0.6), 0.2)
      .from(".match", fade(0.6), 0.4)
      .from(".phase_best_of", fade(0.6), 0.6)
      .from(".score_container", fade(0.8), 0)
      .from(".best_of.container", fade(0.8), 0)
      .from(".vs1", { duration: 0.1, opacity: 0, scale: 10, ease: "in" }, 1.2)
      .from(".vs2", { duration: 0.01, opacity: 0 }, 1.3)
      .to(".vs2", { opacity: 0, scale: 2, ease: "power2.out" }, 1.31)
      .from(".p1.container", { duration: 1, x: -200, ease: "out" }, 0)
      .from(".p2.container", { duration: 1, x: 200, ease: "out" }, 0);
  },

  update(s) {
    base.update(s);
    s.set(".phase_best_of", HD.text([s.score.phase, s.score.best_of_text], " | "));
  },
});
