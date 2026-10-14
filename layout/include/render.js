// Rendering: safe HTML templates, HD.set() to change what an element
// shows (with a fade), text fitting, and helpers for the state's shapes.
"use strict";

(() => {
  // -------------------------------------------------------------------
  // HTML. Values from the state (names, sponsors, handles...) are text:
  // HD.html`<b>${name}</b>` escapes them. Markup is only what the
  // template itself has, nested HD.html results, or HD.raw().

  class Html {
    constructor(html) {
      this.html = html;
    }
    toString() {
      return this.html;
    }
  }

  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  HD.escape = (text) => String(text).replace(/[&<>"']/g, (c) => ESCAPES[c]);

  // null, undefined and false render nothing, so ${cond && html`...`} works
  function render(value) {
    if (value == null || value === false) return "";
    if (value instanceof Html) return value.html;
    if (Array.isArray(value)) return value.map(render).join("");
    return HD.escape(value);
  }

  HD.html = (strings, ...values) =>
    new Html(strings.reduce((out, s, i) => out + render(values[i - 1]) + s));

  // Trusted markup, e.g. from a file the tournament wrote
  HD.raw = (html) => new Html(html == null ? "" : String(html));

  // Several pieces with a separator between the non-empty ones
  HD.join = (items, separator = "") =>
    new Html(items.map(render).filter(Boolean).join(render(separator)));

  // -------------------------------------------------------------------
  // HD.set(target, content, options): shows content in the target(s), in
  // a .text child (which main.css and the layouts style), fitted to the
  // target's width. Plain values are text. A change fades the old content
  // out and the new in; the same content again does nothing.
  //
  // options: { duration, in, out (GSAP vars), after() (runs once the new
  // content is in), force (even if unchanged) }

  // What each element last got, to skip unchanged content without reading
  // the DOM back
  const shown = new WeakMap();

  HD.set = async (target, content, options = {}) => {
    const el = target instanceof $ ? target : $(target);
    if (el.length === 0) return;
    const html = render(content);
    const { duration = 0.5, after } = options;
    const animIn = { autoAlpha: 1, duration, stagger: 0.1, ...options.in };
    const animOut = { autoAlpha: 0, duration, stagger: 0.1, overwrite: true, ...options.out };

    const first = el.find(".text").length === 0;
    if (first) {
      // Some text, so fonts start loading before sizes are measured
      el.html("<div class='text' style='opacity: 0;'>&nbsp;</div>");
    } else if (!options.force && el.toArray().every((e) => shown.get(e) === html)) {
      return;
    }
    el.each((_, e) => shown.set(e, html));

    await document.fonts.ready;
    const text = () => el.find(".text");

    const swap = () => {
      text().html(html);
      const empty = html.trim().length === 0;
      text().toggleClass("text_empty", empty);
      el.toggleClass("text_empty", empty);
      HD.fit(el);
      if (after) after();

      if (document.hidden) {
        gsap.killTweensOf(text());
        text().css({ opacity: 1, visibility: "inherit" });
      } else if (first) {
        gsap.set(text(), animIn);
      } else {
        gsap.fromTo(text(), { ...animOut, onComplete: null }, animIn);
      }
    };

    if (document.hidden) return swap();
    const vars = { ...animOut, onComplete: swap };
    // The first time there's nothing to fade out
    await (first ? gsap.set(text(), vars) : gsap.to(text(), vars));
  };

  // Structure (a list's rows, iframes...) put straight in the target(s),
  // without HD.set()'s fade and .text
  HD.render = (target, content) => $(target).html(render(content));

  // HD.render() only when key (anything JSON-able: the players, the
  // stages...) changed since the last build, so the rows stay and what
  // HD.set() puts in them can fade. content may be a function, called
  // only then. Returns whether it built.
  HD.build = (target, key, content) => {
    const el = $(target);
    const signature = JSON.stringify(key === undefined ? null : key);
    if (el.length === 0 || el.data("hd-build") === signature) return false;
    el.data("hd-build", signature);
    HD.render(el, typeof content === "function" ? content() : content);
    return true;
  };

  // An image, or nothing without a src
  HD.img = (src, attrs = "") => src && HD.html`<img src="${src}" ${HD.raw(attrs)} />`;

  // -------------------------------------------------------------------
  // Fitting: text wider than its element is squeezed (scaleX), or with
  // .font-scale-fit on the element, made smaller. Done again when the
  // element is resized.

  const fitObserver = new ResizeObserver((entries) => {
    for (const entry of entries) HD.fit($(entry.target));
  });

  HD.fit = (target) =>
    document.fonts.ready.then(() => {
      target.each((_, element) => {
        const el = $(element);
        if (!el.hasClass("hd-fit-content")) {
          el.addClass("hd-fit-content");
          fitObserver.observe(element);
        }
        const text = el.find(".text")[0];
        if (!text) return;
        text.style.transform = "";
        text.style.fontSize = "";

        const width = el.width();
        if (text.scrollWidth <= width) return;

        if (!el.hasClass("font-scale-fit")) {
          text.style.transform = `scaleX(${width / text.scrollWidth})`;
          return;
        }
        // Each step is a layout: jump to the size that fits if the width
        // scales with it, then step down for what doesn't (padding...)
        let size = parseFloat(getComputedStyle(text).fontSize);
        size = Math.max(1, Math.floor(((size * width) / text.scrollWidth) * 10) / 10);
        text.style.fontSize = `${size}px`;
        while (text.scrollWidth > width && size > 1) {
          size = Math.max(1, size - 0.1);
          text.style.fontSize = `${size}px`;
        }
      });
    });

  // -------------------------------------------------------------------
  // The state's shapes

  // A path from the state (an image, a flag...) as the layout's src
  HD.asset = (path) => (path ? `../../${path}` : "");

  // A team's players, in order, without empty slots
  HD.players = (team) => Object.values((team && team.player) || {}).filter(Boolean);

  // The players' names: "A / B"
  HD.playerNames = (team, separator = " / ") =>
    HD.players(team)
      .map((p) => p.name)
      .filter(Boolean)
      .join(separator);

  // A team's name, or its players' names without one
  HD.teamName = (team) => (team && team.teamName) || HD.playerNames(team);

  // The non-empty values (not null, "" or false), joined:
  // HD.text([phase, bestOf], " - ")
  HD.text = (parts, separator = " ") =>
    parts.filter((p) => p != null && p !== "" && p !== false).join(separator);

  // A number's ordinal suffix: 1 -> "st", 12 -> "th", 22 -> "nd"
  const SUFFIXES = ["th", "st", "nd", "rd"];
  HD.ordinal = (n) => {
    const v = n % 100;
    return SUFFIXES[(v - 20) % 10] || SUFFIXES[v] || "th";
  };

  // The stage picked on a scoreboard, with its data
  HD.stage = (data, score) => {
    const strike = (score && score.stage_strike) || {};
    return (
      strike.selectedStageData ||
      (strike.selectedStage ? _.get(data, ["game", "stages", strike.selectedStage]) : null)
    );
  };

  // A person's custom data (user_data/custom_player_export/<name>/<key>.*):
  // a text file's text, a .json file's value, or fallback
  HD.custom = (person, key, fallback = null) => _.get(person, ["custom", key], fallback);

  // The src of a person's custom image or video, or fallback
  HD.customFile = (person, key, fallback = null) => {
    const path = HD.custom(person, key);
    return typeof path === "string" && path.startsWith("./user_data/") ? `../../${path}` : fallback;
  };

  // -------------------------------------------------------------------
  // Pieces most layouts show, as main.css styles them

  HD.ui = {
    // A flag with its code: country or state ({asset, code})
    flag: (place, codeClass) =>
      place &&
      place.asset &&
      HD.html`<img class='flag' src='${HD.asset(place.asset)}' /><div${
        codeClass && HD.html` class="${codeClass}"`
      }>${place.code}</div>`,

    // Icon + text chips, e.g. HD.ui.chip("twitter", handle): the icon is
    // a .twitter_logo span
    chip: (kind, text, prefix = "", icon = `${kind}_logo`) =>
      text ? HD.html`<span class="${icon}"></span>${prefix}${text}` : "",

    // Sponsor and name, and the losers badge: the scoreboards' name
    name: (player, team) =>
      HD.html`<span class="sponsor">${player.team}</span>${player.name}${
        team && team.losers && HD.html`<span class='losers'>L</span>`
      }`,

    // The sponsor's logo as a background (styled as .sponsor-logo)
    sponsorLogo: (path) =>
      HD.html`<div class='sponsor-logo' style="background-image: url('${HD.asset(path)}')"></div>`,

    // A character's skin: its icon and name
    variant(variant) {
      if (!variant) return "";
      const size = variant.image_size || { x: 32, y: 32 };
      return HD.html`${
        variant.icon_path &&
        HD.html`<img src="${HD.asset(variant.icon_path)}" class="variant_icon" width="${(size.x * 32) / size.y}" height="32"/>`
      }${variant.display_name && HD.html`<span class="variant_name">${variant.display_name}</span>`}`;
    },
  };

  // The intro most layouts share, from classes on their elements:
  // - .fade fades in
  // - .fade_down, .fade_up, .fade_left, .fade_right also slide in that way
  // - *_stagger (and *_stagger2...) fade in one after the other, last
  //   first; *_stagger_reverse first first. Each parent's are a group.
  // Elements left empty (.text_empty) don't take part.
  HD.classIntro = (tl, { duration = 0.2, distance = 20, each = 0.05 } = {}) => {
    const ease = "power2.out";
    tl.from(".fade", { duration, autoAlpha: 0, ease }, 0);
    const slides = { down: { y: -distance }, up: { y: distance }, left: { x: distance }, right: { x: -distance } };
    for (const [way, offset] of Object.entries(slides)) {
      tl.from(`.fade_${way}`, { duration, autoAlpha: 0, ease, ...offset }, 0);
    }

    // parent -> stagger class -> its elements there
    const groups = new Map();
    for (const el of document.querySelectorAll("[class*='_stagger']:not(.text_empty)")) {
      const cls = [...el.classList].find((c) => /_stagger(\d*|_reverse)$/.test(c));
      if (!cls) continue;
      if (!groups.has(el.parentElement)) groups.set(el.parentElement, new Map());
      const byClass = groups.get(el.parentElement);
      byClass.set(cls, [...(byClass.get(cls) || []), el]);
    }
    for (const byClass of groups.values()) {
      for (const [cls, els] of byClass) {
        const from = cls.endsWith("_reverse") ? "start" : "end";
        tl.from(els, { autoAlpha: 0, duration, stagger: { each, from } }, 0);
      }
    }
  };

  // The commentators (data.commentary) in a container: a
  // .commentator_container.commentator<i> each, with a div per field.
  // Fields are shown as `show` has them (or the defaults below); ones
  // without a name are hidden.
  const COMMENTATOR_FIELDS = {
    name: (c) =>
      HD.html`<span class="mic_icon"></span><span class="team">${c.team && HD.html`${c.team}&nbsp;`}</span>${c.name}`,
    pronoun: (c) => c.pronoun,
    real_name: (c) => c.real_name,
    twitter: (c) => HD.ui.chip("twitter", c.twitter),
  };

  HD.commentators = (s, container, fields = ["name", "pronoun", "real_name", "twitter"], show = {}) => {
    const list = Object.values(s.data.commentary || {});
    if (s.changed((d) => _.size(d.commentary)) || $(container).is(":empty")) {
      HD.render(
        container,
        list.map(
          (_c, i) =>
            HD.html`<div class="commentator_container commentator${i}">${fields.map(
              (f) => HD.html`<div class="${f}"></div>`,
            )}</div>`,
        ),
      );
    }
    list.forEach((c, i) => {
      const sel = `${container} .commentator${i}`;
      $(sel).css("display", c.name ? "" : "none");
      if (c.name) for (const f of fields) HD.set(`${sel} .${f}`, (show[f] || COMMENTATOR_FIELDS[f])(c));
    });
  };

  // The team colors set on the scoreboard as the score's (and sponsor's)
  // background, unless forceDefaultScoreColors is set
  HD.teamColors = (s, props = ["score-bg-color", "sponsor-color"]) => {
    if (s.settings.forceDefaultScoreColors) return;
    for (const { n, team } of s.teams) {
      if (!team.color) continue;
      for (const prop of props) document.documentElement.style.setProperty(`--p${n}-${prop}`, team.color);
    }
  };
})();
