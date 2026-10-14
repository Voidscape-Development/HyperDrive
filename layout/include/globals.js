// HyperDrive layout runtime.
//
// A layout page loads this file in <head> and its own script at the end of
// <body>, which describes the layout with HD.layout({...}) (see
// docs/layouts.md). The runtime does the rest: it loads the libraries and
// settings, follows the program state, calls update() with what changed,
// plays the intro and hides the layout for Display Controls.
//
// Classic scripts on purpose: OBS and the previews open layouts from
// file://, where ES modules don't load.
"use strict";

const HD = (window.HD = {});

// Layouts several folders share (include/scoreboard.js...)
HD.layouts = {};

(() => {
  // Libraries, then the runtime's own parts that use them. Downloaded in
  // parallel; async = false still runs them in this order.
  const SCRIPTS = [
    "jquery-3.7.1.min.js",
    "gsap.min.js",
    "lodash.min.js",
    "jquery.waitforimages.min.js",
    "color-thief.min.js",
    "socket.io.min.js",
    "render.js",
    "characters.js",
  ];
  const INCLUDE = document.currentScript.src.replace(/[^/]*$/, "");

  const libraries = Promise.all(
    SCRIPTS.map(
      (name) =>
        new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = INCLUDE + name;
          script.async = false;
          script.onload = resolve;
          script.onerror = () => reject(new Error(`Couldn't load ${script.src}`));
          document.head.appendChild(script);
        }),
    ),
  );

  // Hidden until the first state is shown and the intro starts
  document.documentElement.classList.add("hd-loading");
  const style = document.createElement("style");
  style.textContent = "html.hd-loading body { opacity: 0; }";
  document.head.appendChild(style);

  // ---------------------------------------------------------------------
  // Page options: URL params (?scoreboardNumber=2&channel=TV 1) and
  // HD.page({...}) from the page's inline script. They win over every other
  // setting.

  // "true", "false" and numbers as such; the rest as typed
  const parseParam = (v) =>
    v === "true" ? true : v === "false" ? false : v !== "" && isFinite(v) ? Number(v) : v;

  const pageOptions = {};
  for (const [k, v] of new URLSearchParams(location.search)) pageOptions[k] = parseParam(v);

  // For pages sharing a layout's script: HD.page({ team: 1, player: 2 })
  HD.page = (options) => Object.assign(pageOptions, options);

  // ---------------------------------------------------------------------
  // State

  const EMPTY = Object.freeze({});
  let def = null; // The layout, from HD.layout()
  let current = EMPTY; // Latest state received
  let applied = EMPTY; // State the last update() ran with
  let fileSettings = {}; // settings.json: global under local
  let devMode = false; // State comes from the dev harness, not HyperDrive

  // Animation speed from the layout theme (1 = normal)
  let animationScale = 1;

  HD.state = () => current;

  // Which scoreboard the layout shows
  HD.scoreboardNumber = () => pageOptions.scoreboardNumber || 1;

  // ---------------------------------------------------------------------
  // Settings: the layout's defaults, under /layout/settings.json, under its
  // folder's settings.json, under the theme's values for it, under the
  // page's options

  // def.theme maps settings to theme fields: { "display.eta":
  // ["stream_queue", "eta_display", default, (value) => setting] }. A theme
  // value only counts when it isn't its default, so the default theme
  // leaves settings.json as it is.
  function themeSettings(data) {
    const out = {};
    for (const [path, [section, field, fallback, convert]] of Object.entries(def.theme || {})) {
      const value = _.get(data, ["layout_theme", "values", section, field], fallback);
      if (!_.isEqual(value, fallback)) _.set(out, path, convert ? convert(value) : value);
    }
    return out;
  }

  const resolveSettings = (data) =>
    _.merge({}, def.settings, fileSettings, themeSettings(data), pageOptions);

  async function loadSettings() {
    const load = (url) =>
      $.ajax({ dataType: "json", url, cache: false }).catch(() => {
        console.log(`No ${url}`);
        return {};
      });
    const [global, local] = await Promise.all([load("../settings.json"), load("./settings.json")]);
    fileSettings = _.merge({}, global, local);
  }

  HD.settings = {};

  // ---------------------------------------------------------------------
  // Change tracking. Deltas keep the parts of the state they don't change
  // (same objects), so most checks end at ===.

  // path: a lodash path ("score.1.team") or a function of the state
  function read(state, path) {
    if (typeof path !== "function") return _.get(state, path);
    try {
      return path(state);
    } catch (e) {
      return undefined; // A part missing from the old state
    }
  }

  function changed(data, old, path) {
    const a = read(data, path);
    const b = read(old, path);
    return a !== b && !_.isEqual(a, b);
  }

  // ---------------------------------------------------------------------
  // What update() gets: the state, what changed, and shortcuts to the
  // scoreboard the layout shows

  function teamView(score, t) {
    const team = _.get(score, ["team", t]) || {};
    const sel = `.p${t}`;
    return {
      n: t,
      team,
      players: HD.players(team),
      player: _.get(team, "player.1") || {},
      name: HD.teamName(team),
      // Selector under the team's .p1/.p2: "& .x" or ".x" for ".p1 .x",
      // "&.x" for ".p1.x"
      sel: (s = "") => (s.includes("&") ? s.replace(/&/g, sel) : `${sel} ${s}`.trim()),
      set(s, content, options) {
        return HD.set(this.sel(s), content, options);
      },
    };
  }

  function scope(data, old) {
    const n = HD.scoreboardNumber();
    const score = _.get(data, ["score", n]) || {};
    const pending = [];
    const s = {
      data,
      old,
      first: old === EMPTY,
      n,
      score,
      settings: HD.settings,
      teams: [1, 2].map((t) => teamView(score, t)),
      changed: (path) => changed(data, old, path),
      // Same as changed(), in the scoreboard: "team.1.color" or a function
      scoreChanged: (path) =>
        changed(data, old, typeof path === "function" ? (d) => path(d.score[n]) : ["score", n, ..._.toPath(path)]),
      set: (...args) => HD.set(...args),
      // Work the first show waits for (e.g. images loading)
      wait: (promise) => (pending.push(promise), promise),
      pending,
      // Character art, see characters.js
      characters: (target, options) => s.wait(HD.characters(target, options, s)),
    };
    s.isTeams = s.teams[0].players.length > 1;
    return s;
  }

  HD.scope = () => scope(applied, applied);

  // Runs fn(scope) every so many seconds, for content that takes turns.
  // Call it from init(), so it isn't started again with each show.
  HD.every = (seconds, fn) => setInterval(() => applied !== EMPTY && fn(HD.scope()), seconds * 1000);

  // ---------------------------------------------------------------------
  // Updates: one at a time, with the latest state. States arriving while
  // one runs are folded into the next run, compared against what the
  // layout last showed.

  let running = false;
  let dirty = false;

  async function schedule() {
    dirty = true;
    if (running || !def || !booted) return;
    running = true;
    try {
      while (dirty) {
        dirty = false;
        const data = current;
        const old = applied;
        applied = data;
        await runUpdate(data, old);
      }
    } finally {
      running = false;
    }
  }

  async function runUpdate(data, old) {
    const themeChanged = applyTheme(data, old);
    if (themeChanged || old === EMPTY) HD.settings = resolveSettings(data);

    const s = scope(data, old);
    try {
      if (def.update) await def.update(s);
    } catch (e) {
      console.error(e);
    }

    if (!display.started) {
      await Promise.allSettled(s.pending);
      await firstShow();
    } else {
      applyDisplay(data);
    }
  }

  function receive(state) {
    current = state;
    console.log(state);
    schedule();
  }

  // ---------------------------------------------------------------------
  // Lifecycle: the layout's intro (a GSAP timeline) plays when it's shown,
  // and runs backwards to hide it, unless it has an outro

  let intro = null;

  // Once the images and fonts are in, so nothing pops in during the intro
  async function firstShow() {
    await document.fonts.ready;
    await new Promise((resolve) =>
      requestAnimationFrame(() =>
        $(document).waitForImages(() => {
          display.started = true;
          gsap.globalTimeline.timeScale(animationScale);
          // Turned off in Display Controls: stays hidden until turned on
          if (!displayVisible(applied)) {
            display.shown = false;
            gsap.set("body", { autoAlpha: 0 });
          } else {
            show();
          }
          resolve();
        }),
      ),
    );
  }

  function show() {
    document.documentElement.classList.remove("hd-loading");
    console.log("Start()");
    return runStart();
  }

  async function runStart() {
    const s = HD.scope();
    // From the end, so a new intro animates from where things rest
    if (intro) intro.progress(1).kill();
    intro = null;
    if (def.intro) {
      intro = gsap.timeline();
      def.intro(intro, s);
    }
    if (def.start) await def.start(s);
  }

  // Resolves when a timeline has run backwards to its start
  const reverse = (timeline) =>
    new Promise((resolve) => {
      if (timeline.time() === 0) return resolve();
      timeline.eventCallback("onReverseComplete", resolve);
      timeline.reverse();
    });

  async function hide() {
    if (def.outro) {
      await def.outro(HD.scope());
    } else if (intro && intro.time() > 0) {
      // At most as long as the intro could take, in case it's killed
      await Promise.race([
        reverse(intro),
        new Promise((r) => setTimeout(r, (intro.time() / animationScale) * 1000 + 500)),
      ]);
    }
  }

  // ---------------------------------------------------------------------
  // Display Controls (the Display Controls window, or /display/... links
  // for a Stream Deck) show and hide layouts by folder, and by group: the
  // groups in ?display=<group>[,<group>...]. A layout is shown while its
  // folder and all of its groups are on.

  const display = {
    folder: (() => {
      const folder = location.pathname.split("/").filter(Boolean).slice(-2)[0] || "";
      try {
        return decodeURIComponent(folder);
      } catch (e) {
        return folder;
      }
    })(),
    groups: String(pageOptions.display || "")
      .split(",")
      .map((g) => g.trim().replace(/\s+/g, " ").toLowerCase().slice(0, 40).trim())
      .filter(Boolean),
    started: false, // Shown the first time
    shown: true, // On screen, or going to be
    sequence: 0, // Changes each show or hide, so an interrupted one stops
  };

  function displayVisible(data) {
    const d = data && data.display;
    if (!d) return true;
    if ((d.folders || {})[display.folder] === false) return false;
    return display.groups.every((g) => (d.groups || {})[g] !== false);
  }

  async function applyDisplay(data) {
    const visible = displayVisible(data);
    if (!display.started || visible === display.shown) return;
    display.shown = visible;
    const sequence = ++display.sequence;
    gsap.killTweensOf("body");
    console.log(`Display: ${visible ? "show" : "hide"}`);

    if (visible) {
      gsap.set("body", { autoAlpha: 1 });
      await show();
      return;
    }
    await hide();
    // Shown again meanwhile
    if (sequence !== display.sequence) return;
    // Whatever wasn't part of the animation goes too
    gsap.to("body", { autoAlpha: 0, duration: intro || def.outro ? 0.15 : 0.3 });
  }

  // OBS showing the source again (or the tab, in a browser): fresh state,
  // intro again
  function onBecameActive(callback) {
    if (window.obsstudio) {
      window.addEventListener("obsSourceActiveChanged", (e) => e.detail.active && callback());
    } else {
      document.addEventListener("visibilitychange", () => !document.hidden && callback());
    }
  }

  // ---------------------------------------------------------------------
  // Layout theme (data.layout_theme): display options as body classes,
  // colors and fonts as main.css's custom properties, the animation speed.
  // The properties go in a stylesheet, not on :root's style, so colors a
  // layout sets itself (e.g. a scoreboard's team colors) still win.

  // Font stack a theme font goes in front of (same as main.css's --font)
  const FONT_FALLBACK =
    '"SairaCondensed", "NotoSans", "NotoSansJP", "NotoSansSC", "NotoSansTC", "NotoSansKR", sans-serif';

  // Body classes for the theme's display options: [class, section, field,
  // value that adds the class]
  const THEME_CLASSES = [
    ["hd-hide-pronouns", "chip", "pronouns_display", false],
    ["hd-hide-seed", "chip", "seed_display", false],
    ["hd-hide-social", "chip", "social_media_display", false],
    ["hd-hide-country-flag", "chip", "country_flag_display", false],
    ["hd-hide-state-flag", "chip", "state_flag_display", false],
    ["hd-hide-avatar", "chip", "avatar_display", false],
    ["hd-hide-losers", "chip", "losers_display", false],
    ["hd-no-text-outline", "general", "text_outline", false],
    ["hd-bracket-hide-avatar", "bracket", "avatar_display", false],
    ["hd-bracket-hide-character", "bracket", "character_display", false],
    ["hd-bracket-hide-country-flag", "bracket", "country_flag_display", false],
    ["hd-bracket-hide-state-flag", "bracket", "state_flag_display", false],
    ["hd-bracket-hide-seed", "bracket", "seed_display", false],
    ["hd-bracket-hide-round-names", "bracket", "round_names_display", false],
    ["hd-bracket-show-identifier", "bracket", "identifier_display", true],
    ["hd-bracket-hide-pending", "bracket", "pending_display", false],
    ["hd-bracket-no-dim-losers", "bracket", "dim_losers", false],
    ["hd-bracket-hide-focus-label", "bracket", "focus_label_display", false],
    ["hd-standings-hide-game-diff", "standings", "game_diff_display", false],
    ["hd-standings-hide-points", "standings", "points_display", false],
    ["hd-standings-show-buchholz", "standings", "buchholz_display", true],
    ["hd-strike-hide-names", "stage_strike", "stage_names_display", false],
    ["hd-strike-hide-striker", "stage_strike", "striker_display", false],
  ];

  // main.css's properties, from the theme's, with "Use this theme's colors"
  const THEME_COLORS = {
    "--text-color": "--general-text-color",
    "--bg-fill": "--general-background",
    "--border-radius": "--general-border-radius",
    "--border-radius-chip": "--general-chip-radius",
    "--accent-color": "--general-primary-color",
    "--accent-secondary-color": "--general-secondary-color",
    "--p1-score-bg-color": "--teams-team1-color",
    "--p2-score-bg-color": "--teams-team2-color",
    "--p1-score-color": "--teams-team1-score-color",
    "--p2-score-color": "--teams-team2-score-color",
    "--chip-color": "--chip-text-color",
    "--chip-bg": "--chip-background",
    "--bracket-score-bg": "--bracket-score-background",
    "--bracket-sponsor-bg": "--bracket-sponsor-background",
    "--bracket-winner-color": "--bracket-winner-color",
    "--bracket-line-color": "--bracket-lines-color",
    "--strike-striked-color": "--stage-strike-striked-color",
    "--strike-selected-color": "--stage-strike-selected-color",
  };

  // A theme color (#rrggbb or Qt's #aarrggbb) as CSS
  function cssColor(color) {
    const m = /^#([0-9a-f]{2})([0-9a-f]{6})$/i.exec(color || "");
    if (!m) return color;
    const rgb = m[2].match(/../g).map((h) => parseInt(h, 16));
    return `rgba(${rgb.join(", ")}, ${Math.round((parseInt(m[1], 16) / 255) * 1000) / 1000})`;
  }

  // Returns whether the theme changed
  function applyTheme(data, old) {
    const theme = _.get(data, "layout_theme");
    const oldTheme = _.get(old, "layout_theme");
    if (!theme || !theme.values) return false;
    if (old !== EMPTY && (theme === oldTheme || _.isEqual(theme, oldTheme))) return false;

    const get = (section, field, fallback) => _.get(theme.values, [section, field], fallback);
    const body = document.body.classList;
    for (const [cls, section, field, when] of THEME_CLASSES) {
      body.toggle(cls, get(section, field) === when);
    }
    const colors = get("general", "apply_colors", false) === true;
    // Layouts with a palette of their own switch to the theme's under it
    body.toggle("hd-theme-colors", colors);
    const textCase = get("general", "text_case", "layout");
    body.toggle("hd-text-upper", textCase === "uppercase");
    body.toggle("hd-text-none", textCase === "none");

    // Every theme value as --<section>-<field>, for layouts that want them
    const css = theme.css || {};
    const props = { ...css };
    const font = get("general", "font_family", "");
    if (font) props["--font"] = `"${String(font).replace(/["\\]/g, "")}", ${FONT_FALLBACK}`;
    if (colors) {
      for (const [prop, from] of Object.entries(THEME_COLORS)) props[prop] = css[from];
      const bg = get("general", "background");
      props["--bg-color"] = bg && bg.color ? cssColor(bg.color) : null;
      if (get("versus", "custom_sponsor_colors", false)) {
        props["--p1-sponsor-color"] = css["--versus-team1-sponsor-color"];
        props["--p2-sponsor-color"] = css["--versus-team2-sponsor-color"];
      }
    }

    let sheet = document.getElementById("hd-layout-theme");
    if (!sheet) {
      sheet = document.createElement("style");
      sheet.id = "hd-layout-theme";
      document.head.appendChild(sheet);
    }
    sheet.textContent = `:root {\n${Object.entries(props)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => `  ${k}: ${v};\n`)
      .join("")}}\n`;

    const speed = Number(get("animation", "speed", 100)) || 100;
    animationScale = get("animation", "enabled", true) === false ? 1000 : speed / 100;
    // Stays 0 until the layout is first shown
    if (display.started) gsap.globalTimeline.timeScale(animationScale);

    document.dispatchEvent(new CustomEvent("hd_theme", { detail: theme }));
    return true;
  }

  // A theme value, e.g. HD.theme("bracket", "seed_display", true)
  HD.theme = (section, field, fallback) =>
    _.get(current, ["layout_theme", "values", section, field], fallback);

  // Colors from the tournament logo, with "automatic_theme" in settings.json
  function logoColors() {
    const img = new Image();
    img.src = "../logo.png";
    img.onload = () => {
      const [bg, accent] = new ColorThief().getPalette(img, 2);
      const contrast = (c) => ((c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000 > 125 ? "0,0,0" : "255,255,255");
      const props = {
        "--text-color": `rgb(${contrast(bg)})`,
        "--bg-color": `rgb(${bg})`,
        "--p1-score-color": `rgb(${contrast(accent)})`,
        "--p2-score-color": `rgb(${contrast(accent)})`,
      };
      for (const p of ["p1", "p2"]) {
        props[`--${p}-score-bg-color`] = props[`--${p}-sponsor-color`] = `rgb(${accent})`;
      }
      for (const [k, v] of Object.entries(props)) document.documentElement.style.setProperty(k, v);
    };
  }

  // ---------------------------------------------------------------------
  // Transport: the HyperDrive web server's socket (full states, then
  // deltas), or program_state.json polled when opened from a file

  let fetching = false;

  async function poll() {
    if (fetching || devMode) return;
    fetching = true;
    try {
      const state = await $.ajax({ dataType: "json", url: "../../out/program_state.json", cache: false });
      // Overlapping or older responses never put an older state back
      if (!(state.timestamp <= current.timestamp)) receive(state);
    } catch (e) {
      console.log(e);
    } finally {
      fetching = false;
    }
  }

  let polling = null;
  const startPolling = () => {
    if (polling === null) polling = setInterval(poll, 64);
  };

  function connectSocket() {
    const socket = io(`${location.protocol}//${location.host}/`, {
      transports: ["websocket", "webtransport"],
      timeout: 500,
      reconnectionDelay: 500,
      reconnectionDelayMax: 1500,
    });
    let deltaIndex = -1;
    let resyncing = false; // A full state was requested and hasn't come

    socket.on("connect", () => {
      console.log("socket.io connected");
      // So Display Controls lists this layout's groups
      if (display.groups.length > 0) socket.emit("display_register", { groups: display.groups });
    });
    // The web server may be fine with only the socket down (or HyperDrive
    // closed): the file meanwhile
    socket.on("disconnect", poll);
    socket.io.on("reconnect_attempt", poll);
    socket.io.on("reconnect_failed", startPolling);
    socket.on("error", console.log);

    socket.on("program_state", (message) => {
      if (devMode) return;
      resyncing = false;
      deltaIndex = message.delta_index;
      receive(message.state);
    });

    socket.on("program_state_update", (message) => {
      if (devMode || resyncing) return;
      const index = message.delta_index;
      // Deltas are numbered one by one: an older one, or a gap, means the
      // state here is off. Ask for the whole state, once: the server sends
      // it to every layout.
      if (index < deltaIndex || (deltaIndex >= 0 && index > deltaIndex + 1)) {
        console.log(`Delta ${index} after ${deltaIndex}: resyncing`);
        resyncing = true;
        socket.emit("program_state", {});
        return;
      }
      deltaIndex = index;
      receive(applyDeltas(current, message.delta));
    });
  }

  // The state with the deltas applied, leaving the state as it was: only
  // the objects on the changed paths are copied, the rest is shared
  function applyDeltas(state, deltas) {
    const root = { ...state };
    const copied = new Set([root]);
    const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
    for (const { path, action, value } of deltas) {
      let node = root;
      for (const key of path.slice(0, -1)) {
        let next = node[key];
        if (!own(node, key) || next === null || typeof next !== "object") {
          next = {};
        } else if (!copied.has(next)) {
          next = Array.isArray(next) ? next.slice() : { ...next };
        }
        copied.add(next);
        node[key] = next;
        node = next;
      }
      const last = path[path.length - 1];
      if (action === "dictionary_item_removed") delete node[last];
      else node[last] = value;
    }
    return root;
  }
  HD.applyDeltas = applyDeltas;

  // The dev harness (layout/dev.html) sends states to the layout it shows
  window.addEventListener("message", (e) => {
    if (e.source !== window.parent || !e.data || e.data.type !== "hd_state") return;
    devMode = true;
    receive(e.data.state);
  });

  // ---------------------------------------------------------------------
  // Boot

  let booted = false;

  // def: { settings, theme, intro(tl, s), outro(s), start(s), update(s) }
  HD.layout = async (layout) => {
    if (def) throw new Error("HD.layout() called twice");
    def = layout;

    await libraries;
    await new Promise((resolve) => $(resolve));
    gsap.config({ nullTargetWarn: false, trialWarn: false });
    // Frozen until the first show, so nothing plays before the intro
    gsap.globalTimeline.timeScale(0);
    await loadSettings();
    HD.settings = resolveSettings(current);
    if (HD.settings.automatic_theme) logoColors();
    if (def.init) await def.init(HD.settings);

    booted = true;
    console.log("== Init complete ==");

    onBecameActive(async () => {
      await poll();
      // Turned off in Display Controls: stays hidden
      if (display.started && display.shown) runStart();
    });

    if (location.protocol === "file:" || location.host === "absolute") startPolling();
    else connectSocket();
    if (current !== EMPTY) schedule();
  };
})();
