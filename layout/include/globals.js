// Global variable containing current data red from out/program_state.json
var data = {};

// Global variable containing previous data red from out/program_state.json
// Used for comparing what changed since last update
var oldData = {};

// Global variable that tracks the max delta index that has been applied.
// Used as a failsafe to prevent stale state-changes from being processed.
var maxAppliedDeltaIdx = -1;

// Global variable containing settings red from settings.json
// The settings under /layout/settings.json (global) are merged with /layout/<directory>/settings.json (local),
// where the local settings have priority over global ones
var hd_settings = {};
// The settings the page's window.settings sets, which win over the layout theme
var hd_page_settings = {};

// This is called once after initialization. Layouts should reimplement this function.
var Start = async () => {
  console.log("Start(): Implement me");
};

// Display Controls turning this layout off plays Hide(). Layouts can
// reimplement it with their own hide animation; by default the layout's show
// animation (what Start() played) runs backwards. Turning it back on plays
// Start() again.
var Hide = null;

// This is called each time data changes. Layouts should reimplement this function.
var Update = async (event) => {
  console.log("Update(): Implement me");
};

// Animation speed from the layout theme (1 = normal)
var hd_animation_scale = 1;

// Wrapper for the update call
async function UpdateWrapper(event) {
  ApplyLayoutTheme(event.data, event.oldData);

  await Update(event);

  // If initialization wasn't done yet, call Start()
  // We use gsap.globalTimeline.timeScale as 0 for animation to not play before this
  if (gsap.globalTimeline.timeScale() == 0) {
    gsap.globalTimeline.timeScale(hd_animation_scale);
    window.requestAnimationFrame(() => {
      $(document).waitForImages(() => {
        hd_display.started = true;
        // Turned off in Display Controls: stays hidden until turned on
        if (!HDDisplayVisible(data)) {
          hd_display.shown = false;
          gsap.set("body", { autoAlpha: 0 });
          return;
        }
        $("body").fadeTo(1, 1, () => {
          console.log("Start()");
          HDRunStart();
        });
      });
    });
  } else {
    HDApplyDisplay(event.data);
  }
}

// Display Controls (the Display Controls window, or /display/... links for a
// Stream Deck) show and hide layouts by folder, and by group: the groups in
// ?display=<group>[,<group>...]. A layout is shown while its folder and all
// of its groups are on.
var hd_display = {
  // The layout's folder, as in layout/<folder>/<page>.html
  folder: (() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    try {
      return decodeURIComponent(parts[parts.length - 2] || "");
    } catch (e) {
      return parts[parts.length - 2] || "";
    }
  })(),
  groups: (new URLSearchParams(window.location.search).get("display") || "")
    .split(",")
    .map((g) => g.trim().replace(/\s+/g, " ").toLowerCase().slice(0, 40).trim())
    .filter(Boolean),
  // Start() was called the first time
  started: false,
  // Whether it's on screen (or going to be)
  shown: true,
  // The timelines Start() played, run backwards to hide
  animations: [],
  // Changes each show or hide, so one that's interrupted stops there
  sequence: 0,
};

function HDDisplayVisible(data) {
  const display = data && data.display;
  if (!display) return true;
  if ((display.folders || {})[hd_display.folder] === false) return false;
  return hd_display.groups.every((g) => (display.groups || {})[g] !== false);
}

// Calls Start(), keeping the timelines it played to run them backwards for
// the hide animation
async function HDRunStart() {
  const before = gsap.globalTimeline.time();
  await Start();
  // Started (or restarted) by Start() and not done yet. Done timelines
  // aren't in the global timeline anymore.
  hd_display.animations = gsap.globalTimeline
    .getChildren(false, false, true)
    .filter(
      (t) =>
        !t.paused() &&
        t.progress() < 1 &&
        t.duration() > 0 &&
        t.startTime() >= before &&
        t.repeat() !== -1,
    );
}

function HDApplyDisplay(data) {
  if (!hd_display.started) return;
  const visible = HDDisplayVisible(data);
  if (visible === hd_display.shown) return;
  if (visible) {
    HDDisplayShow();
  } else {
    HDDisplayHide();
  }
}

async function HDDisplayShow() {
  hd_display.shown = true;
  hd_display.sequence += 1;
  console.log("Display: show");
  gsap.killTweensOf("body");
  // Back to the end, so Start() restarting them plays the whole animation
  hd_display.animations.forEach((t) => t.progress(1));
  if (hd_display.animations.length > 0 || Hide) {
    gsap.set("body", { autoAlpha: 1 });
  } else {
    // No show animation to play: fades in
    gsap.fromTo("body", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 });
  }
  await HDRunStart();
}

// Resolves when a timeline has run backwards to its start
function HDReverse(timeline) {
  return new Promise((resolve) => {
    if (timeline.time() === 0) return resolve();
    const previous = timeline.eventCallback("onReverseComplete");
    timeline.eventCallback("onReverseComplete", function () {
      timeline.eventCallback("onReverseComplete", previous || null);
      if (previous) previous.apply(this, arguments);
      resolve();
    });
    timeline.reverse();
  });
}

async function HDDisplayHide() {
  hd_display.shown = false;
  const sequence = ++hd_display.sequence;
  console.log("Display: hide");
  gsap.killTweensOf("body");

  const animations = hd_display.animations.filter((t) => t.time() > 0);
  if (Hide) {
    await Hide();
  } else if (animations.length > 0) {
    // At most as long as the show animation could take, in case one of
    // them doesn't finish (killed by the layout)
    const longest = Math.max(...animations.map((t) => t.time())) / hd_animation_scale;
    await Promise.race([
      Promise.all(animations.map(HDReverse)),
      new Promise((r) => setTimeout(r, longest * 1000 + 500)),
    ]);
  }

  // Shown again meanwhile
  if (sequence !== hd_display.sequence) return;
  // Whatever wasn't part of the animation goes too
  gsap.to("body", {
    autoAlpha: 0,
    duration: Hide || animations.length > 0 ? 0.15 : 0.3,
  });
}

// Makes newData the current program state and dispatches "hd_update"
function DispatchUpdate(newData) {
  oldData = data;
  data = newData;

  let event = new CustomEvent("hd_update");
  event.data = data;
  event.oldData = oldData;

  console.log(data);
  document.dispatchEvent(event);
}

// Whether a program_state.json request is in flight
var hd_fetching = false;

// Gets current program state,
// Dispatch "hd_update" event if data has changed
// This function is called in a high frequency
async function UpdateData() {
  // The poll interval is shorter than a slow request: overlapping ones could
  // resolve out of order and put an older state back
  if (hd_fetching) return;
  hd_fetching = true;
  try {
    const newData = await getData();
    if (newData.timestamp <= data.timestamp) return;
    DispatchUpdate(newData);
  } catch (e) {
    console.log(e);
  } finally {
    hd_fetching = false;
  }
}

// Polls program_state.json (file:// layouts, or the websocket gave up)
var hd_polling = null;
function StartPolling() {
  if (hd_polling === null) hd_polling = setInterval(UpdateData, 64);
}

// Gets current program state using SocketIO,
// Dispatch "hd_update" event if data has changed
// This function is called in a high frequency.
// Similar to UpdateData() except for SocketIO support
// which requires being on HTTP/HTTPS
async function UpdateData_SocketIO() {
  try {
    // Connect to Socket.io. Valid: websocket, webtransport, polling
    // Python threading with Qt is weird so put in polling method if
    // really absolutely necessary.
    const socket = io(
      window.location.protocol + "//" + window.location.host + "/",
      {
        transports: ["websocket", "webtransport"],
        timeout: 500,
        reconnectionDelay: 500,
        reconnectionDelayMax: 1500,
      },
    );

    socket.on("connect", () => {
      console.log("socket.io connected");
      // So Display Controls lists this layout's groups
      if (hd_display.groups.length > 0) {
        socket.emit("display_register", { groups: hd_display.groups });
      }
    });

    socket.on("disconnect", () => {
      // call program_state.json initially in case it's a
      // websocket issue and not with web server being gone
      // e.g. HyperDrive being closed
      console.log("socket.io disconnected");
      UpdateData();
    });

    socket.io.on("reconnect", () => {
      console.log("socket.io reconnected");
    });

    socket.io.on("reconnect_attempt", (attempt_number) => {
      // every 1-2 seconds, it will attempt to reconnect to
      // the websocket. before that happens, call UpdateData
      // in case it's an issue with the websocket and not
      // with the web server being gone
      UpdateData();
    });

    socket.io.on("reconnect_failed", () => {
      // reconnect_failed, if max retries are reached,
      // will fall back to file loading program_state.json
      StartPolling();
    });

    socket.on("error", (err) => {
      console.log(err);
    });

    // A full state was requested and hasn't arrived yet
    let resyncing = false;

    socket.on("program_state", (message) => {
      resyncing = false;
      // Fine to reset the max applied index here, since we know that we've
      // received a complete valid state for a point in time.
      maxAppliedDeltaIdx = message["delta_index"];
      DispatchUpdate(message["state"]);
    });

    socket.on("program_state_update", (message) => {
      // Deltas until the full state arrives build on the state that failed
      if (resyncing) return;
      try {
        console.log("Handling state delta: ", message);
        HandleHDStateUpdateMessage(message);
      } catch (e) {
        console.log(e);
        // We failed to handle the program state, so request a new update.
        // The server sends it to every layout: ask once.
        resyncing = true;
        socket.emit("program_state", {});
      }
    });
  } catch (e) {
    console.log(e);
  }
}

// Load libraries sequentially (to respect dependencies)
// Then call InitAll
async function LoadEverything() {
  let libPath = "../include/";
  let scripts = [
    "jquery-3.7.1.min.js",
    "gsap.min.js",
    "he.js",
    "lodash.min.js",
    "jquery.waitforimages.min.js",
    "color-thief.min.js",
    "assetUtils.js",
    "socket.io.min.js",
  ];

  let urlParams = new URLSearchParams(window.location.search);
  window.scoreboardNumber = 1;

  /*
    Read URL params (<url>?var=val&var2=val2...)
    Options:
      scoreboardNumber
  */
  for (let [k, v] of urlParams.entries()) {
    // A param named like a function (?Update=...) would break the layout
    if (typeof window[k] === "function") continue;
    window[k] = v;
  }

  // Downloaded in parallel; async = false still runs them in this order
  await Promise.all(
    scripts.map((script) => {
      const src = libPath + script;
      return new Promise((resolve, reject) => {
        const scriptElement = document.createElement("script");
        scriptElement.src = src;
        scriptElement.async = false;
        scriptElement.onload = () => {
          console.log(`Loaded script: ${src}`);
          resolve();
        };
        scriptElement.onerror = (error) => {
          console.error(`Error loading script: ${src}`, error);
          reject(error);
        };
        document.head.appendChild(scriptElement);
      });
    }),
  );

  console.log("== Loading complete ==");

  await InitAll();
}

// Initialize libraries
async function InitAll() {
  await LoadSettings();

  if (hd_settings.automatic_theme) {
    GetLogoColors();
  }

  await new Promise((resolve) => $(resolve));

  console.log("== Init complete ==");
  // After LoadEverything().then(), so layouts can listen to it there
  setTimeout(() => document.dispatchEvent(new CustomEvent("hd_init")));

  // Before any data comes in: a first update dispatched without a listener
  // would be lost, and polling only dispatches again once the state changes
  document.addEventListener("hd_update", UpdateWrapper);
  gsap.globalTimeline.timeScale(0);

  // Set up listener to regrab data and rerun intro animations on OBS scene switch
  initOnBrowserActive(
    () => {
      // hide function - nothing right now
      console.log("Hidden");
    },
    () => {
      UpdateData().then(() => {
        // Turned off in Display Controls: stays hidden
        if (hd_display.shown) HDRunStart();
      });
    },
  );

  // Both deliver their first state asynchronously, after the layout's
  // LoadEverything().then() has set Start() and Update()
  if (
    window.location.protocol === "file:" ||
    window.location.host === "absolute"
  ) {
    StartPolling();
  } else {
    await UpdateData_SocketIO();
  }
}

// Font stack a theme font is put in front of (same as main.css's --font)
const HD_FONT_FALLBACK =
  '"SairaCondensed", "NotoSans", "NotoSansJP", "NotoSansSC", "NotoSansTC", "NotoSansKR", sans-serif';

// Body classes for the theme's display options: [class, section, field, value
// that adds the class]. main.css and the layouts hide or show things by them.
const HD_THEME_CLASSES = [
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

// Applies the layout theme HyperDrive exports (data.layout_theme): display options as
// body classes, colors and fonts as main.css's custom properties, and the
// animation speed. Called before each Update(); does nothing if the theme
// didn't change. The properties go in a stylesheet, not on :root's style, so
// colors a layout sets itself (e.g. the scoreboard's team colors) still win.
function ApplyLayoutTheme(data, oldData) {
  const theme = _.get(data, "layout_theme");
  if (!theme || !theme.values) return;
  const oldTheme = _.get(oldData, "layout_theme");
  if (
    document.getElementById("hd-layout-theme") &&
    // Deltas keep unchanged parts of the state: same object, no stringify
    (theme === oldTheme || JSON.stringify(theme) == JSON.stringify(oldTheme))
  )
    return;

  const v = theme.values;
  const get = (section, field, fallback) => _.get(v, [section, field], fallback);

  for (const [cls, section, field, when] of HD_THEME_CLASSES) {
    document.body.classList.toggle(cls, get(section, field) === when);
  }
  // Layouts with a palette of their own switch to the theme's under this class
  document.body.classList.toggle("hd-theme-colors", get("general", "apply_colors", false) === true);
  const textCase = get("general", "text_case", "layout");
  document.body.classList.toggle("hd-text-upper", textCase == "uppercase");
  document.body.classList.toggle("hd-text-none", textCase == "none");

  // Every theme value as --<section>-<field>, for layouts that want them
  const props = Object.assign({}, theme.css || {});

  const font = get("general", "font_family", "");
  if (font) {
    props["--font"] = `"${String(font).replace(/["\\]/g, "")}", ${HD_FONT_FALLBACK}`;
  }

  const css = theme.css || {};
  if (get("general", "apply_colors", false)) {
    const solid = (fill) => (fill && fill.color ? CssColor(fill.color) : null);
    Object.assign(props, {
      "--text-color": css["--general-text-color"],
      "--bg-color": solid(get("general", "background")),
      "--bg-fill": css["--general-background"],
      "--border-radius": css["--general-border-radius"],
      "--border-radius-chip": css["--general-chip-radius"],
      "--accent-color": css["--general-primary-color"],
      "--accent-secondary-color": css["--general-secondary-color"],
      "--p1-score-bg-color": css["--teams-team1-color"],
      "--p2-score-bg-color": css["--teams-team2-color"],
      "--p1-score-color": css["--teams-team1-score-color"],
      "--p2-score-color": css["--teams-team2-score-color"],
      "--chip-color": css["--chip-text-color"],
      "--chip-bg": css["--chip-background"],
      "--bracket-score-bg": css["--bracket-score-background"],
      "--bracket-sponsor-bg": css["--bracket-sponsor-background"],
      "--bracket-winner-color": css["--bracket-winner-color"],
      "--bracket-line-color": css["--bracket-lines-color"],
      "--strike-striked-color": css["--stage-strike-striked-color"],
      "--strike-selected-color": css["--stage-strike-selected-color"],
    });
    if (get("versus", "custom_sponsor_colors", false)) {
      props["--p1-sponsor-color"] = css["--versus-team1-sponsor-color"];
      props["--p2-sponsor-color"] = css["--versus-team2-sponsor-color"];
    }
  }

  let style = document.getElementById("hd-layout-theme");
  if (!style) {
    style = document.createElement("style");
    style.id = "hd-layout-theme";
    document.head.appendChild(style);
  }
  style.textContent =
    ":root {\n" +
    Object.entries(props)
      .filter(([k, value]) => value != null && value !== "")
      .map(([k, value]) => `  ${k}: ${value};\n`)
      .join("") +
    "}\n";

  const speed = Number(get("animation", "speed", 100)) || 100;
  hd_animation_scale = get("animation", "enabled", true) === false ? 1000 : speed / 100;
  // 0 means the layout hasn't started yet (see UpdateWrapper)
  if (gsap.globalTimeline.timeScale() != 0) {
    gsap.globalTimeline.timeScale(hd_animation_scale);
  }

  document.dispatchEvent(new CustomEvent("hd_theme", { detail: theme }));
}

// A theme color (#rrggbb or Qt's #aarrggbb) as CSS
function CssColor(color) {
  const m = /^#([0-9a-f]{2})([0-9a-f]{6})$/i.exec(color || "");
  if (!m) return color;
  const alpha = parseInt(m[1], 16) / 255;
  const rgb = m[2].match(/../g).map((h) => parseInt(h, 16));
  return `rgba(${rgb.join(", ")}, ${Math.round(alpha * 1000) / 1000})`;
}

// A layout theme value, e.g. ThemeValue("bracket", "seed_display", true)
function ThemeValue(section, field, fallback) {
  return _.get(data, ["layout_theme", "values", section, field], fallback);
}

// A layout's settings with the layout theme's on top: overrides is
// [[setting path, section, field, theme default, (value) => setting value]],
// e.g. [["display.eta", "stream_queue", "eta_display", true]]. A theme value
// only counts when it's not its default, so the default theme leaves the
// layout's settings.json as it is. The page's own window.settings still wins.
function ThemeSettings(settings, overrides) {
  const theme = {};
  for (const [path, section, field, fallback, convert] of overrides) {
    const value = ThemeValue(section, field, fallback);
    if (!_.isEqual(value, fallback)) _.set(theme, path, convert ? convert(value) : value);
  }
  return _.merge({}, settings, theme, hd_page_settings);
}

// A player's or commentator's custom data, from the file named key in their
// folder in user_data/custom_player_export/, e.g. CustomData(player, "bio").
// Text files give their text, .json files what they hold; fallback when the
// person has no such file. See docs/layout-data.md.
function CustomData(player, key, fallback = null) {
  return _.get(player, ["custom", key], fallback);
}

// The src of a custom image or video of a player, e.g.
// CustomFile(player, "card"), or fallback when they have none
function CustomFile(player, key, fallback = null) {
  const path = CustomData(player, key);
  return typeof path === "string" && path.startsWith("./user_data/")
    ? `../../${path}`
    : fallback;
}

// Read program_state.json
function getData() {
  return $.ajax({
    dataType: "json",
    url: "../../out/program_state.json",
    cache: false,
  });
}

// Loads settings.json from /layout/ and /layout/<folder>/
// /layout/<folder>/settings.json (local) has priority over /layout/settings.json (global)
async function LoadSettings() {
  const load = async (url, name) => {
    try {
      return await $.ajax({ dataType: "json", url: url, cache: false });
    } catch (e) {
      console.log(`Could not load ${name} settings.json`);
      console.log(e);
      return {};
    }
  };
  const [global_settings, file_settings] = await Promise.all([
    load("../settings.json", "global"),
    load("./settings.json", "local"),
  ]);

  // What the page itself sets, before window.settings becomes all of them
  hd_page_settings = _.cloneDeep(window.settings || {});

  hd_settings = _.defaultsDeep(
    window.settings,
    file_settings,
    global_settings,
  );
}

// Registers element for content fitting inside div if the div is resized
function RegisterFit(element) {
  if (!$(element).hasClass("hd-fit-content")) {
    if ($(element).get(0)) {
      $(element).addClass("hd-fit-content");
      divResizeObserver.observe($(element).get(0));
    }
  }
}

// Scale content to fit div
function FitText(target) {
  document.fonts.ready.then(() => {
    if (target == null) return;
    if (target.css("font-size") == null) return;
    if (target.css("width") == null) return;

    let textElement = target.find(".text");
    const text = textElement[0];
    RegisterFit(target);
    if (!text) return;

    if (textElement.text().trim().toLowerCase() == "undefined") {
      textElement.html("");
    }

    textElement.css({ transform: "", "font-size": "" });

    const targetWidth = target.width();
    if (text.scrollWidth <= targetWidth) return;

    if (target.hasClass("font-scale-fit")) {
      // Each step is a layout: jump to the size that fits if the width
      // scales with it, then step down for what doesn't (padding, etc.)
      let fontSize = parseFloat(window.getComputedStyle(text).fontSize);
      fontSize = Math.max(
        1,
        Math.floor(((fontSize * targetWidth) / text.scrollWidth) * 10) / 10,
      );
      textElement.css("font-size", fontSize + "px");

      while (text.scrollWidth > targetWidth && fontSize > 1) {
        fontSize = Math.max(1, fontSize - 0.1);
        textElement.css("font-size", fontSize + "px");
      }
    } else {
      textElement.css("transform", "scaleX(" + targetWidth / text.scrollWidth + ")");
    }
  });
}

// Sets an element's inner HTML
// Sequence: runs anim_out > changes content > runs anim_in
// Uses FitText to scale div contents to fit
async function SetInnerHtml(element, html, settings = {}) {
  // Extract settings
  let { force, fadeTime = 0.5, middleFunction } = settings;

  if (element == null) return;
  if (force === false) return;

  // Fade out/in animations
  let anim_in = {
    autoAlpha: 1,
    duration: fadeTime,
    stagger: 0.1,
    ...settings.anim_in,
  };
  let anim_out = {
    autoAlpha: 0,
    duration: fadeTime,
    stagger: 0.1,
    overwrite: true,
    ...settings.anim_out,
  };

  html = html == null ? "" : String(html);

  let firstRun = element.find(".text").length === 0;

  // First run, no need for smooth fade out
  if (firstRun) {
    // Put any text inside the div just so the font loading is triggered
    element.html("<div class='text' style='opacity: 0;'>&nbsp;</div>");
    force = true;
  }

  // Wait for font to load before calculating sizes
  await document.fonts.ready;

  // Normalize the new HTML by parsing it like the DOM did the current one,
  // which already comes out serialized
  const temp = document.createElement("div");
  temp.innerHTML = html;
  const currentText = element.find(".text").html();
  const newText = temp.innerHTML;

  if (force === true || currentText !== newText) {
    const updateElement = (element, html, firstRun) => {
      element.find(".text").html(html);

      if (html.trim().length === 0) {
        element.find(".text").addClass("text_empty");
        element.addClass("text_empty");
      } else {
        element.find(".text").removeClass("text_empty");
        element.removeClass("text_empty");
      }

      FitText(element);

      if (middleFunction) {
        middleFunction();
      }

      if (document.hidden) {
        gsap.killTweensOf(element.find(".text"));
        element.find(".text").css({ opacity: 1, visibility: "inherit" });
        return;
      }

      if (firstRun) {
        gsap.set(element.find(".text"), anim_in);
      } else {
        anim_out.onComplete = null;
        gsap.fromTo(element.find(".text"), anim_out, anim_in);
      }
    };

    if (document.hidden) {
      updateElement(element, html, firstRun);
      return;
    }

    if (!firstRun) {
      anim_out.onComplete = () => updateElement(element, html, firstRun);
      await gsap.to(element.find(".text"), anim_out);
    } else {
      anim_out.onComplete = () => updateElement(element, html, firstRun);
      await gsap.set(element.find(".text"), anim_out);
    }
  }
}

const degrees_to_radians = (deg) => (deg * Math.PI) / 180.0;

// Given a number of characters, returns an array os positions (0-1) for their eyesights
// Used for "smart" positioning of multiple characters in a container without dividers
function GenerateMulticharacterPositions(
  character_number,
  center = [0.5, 0.5],
  radius = 0.3,
) {
  let positions = [];

  // For 1 character, just center it
  if (character_number == 1) radius = 0;

  let angle_rad = degrees_to_radians(90);

  if (character_number == 2) angle_rad = degrees_to_radians(45);

  let pendulum = 1;

  for (let i = 0; i < character_number; i += 1) {
    let j = i;
    if (i > 1) {
      if (i % 2 == 0) {
        pendulum *= -1;
      } else {
        pendulum *= -1;
        pendulum += 1;
      }
      j = pendulum;
    }
    const angle = angle_rad + degrees_to_radians(360 / character_number) * j;
    const pos = [
      center[0] + Math.cos(angle) * radius,
      center[1] + Math.sin(angle) * radius,
    ];
    positions.push(pos);
  }

  return positions;
}

// Use a HTML canvas to resize an image
// Only needed when downscaling images, to avoid bad image quality
// Detect div size changes for character images
var imageResizeObserver = new ResizeObserver((entries) => {
  for (const entry of entries) {
    CenterImageDo($(entry.target));
  }
});

// Detect div size changes for text elements
var divResizeObserver = new ResizeObserver((entries) => {
  for (const entry of entries) {
    FitText($(entry.target));
  }
});

// Prepare element for character image display
// Call function to center image
async function CenterImage(element, assetData, options = {}) {
  try {
    options = _.defaultsDeep(options, {
      custom_zoom: 1,
      custom_center: [0.5, 0.5],
      scale_based_on_parent: false,
      scale_fill_x: false,
      scale_fill_y: false,
    });

    if (!assetData) return;

    options.asset_data = assetData;

    $(element).data(options);

    await CenterImageDo($(element)).then(() => {
      if (!$(element).hasClass("hd-center-image")) {
        $(element).addClass("hd-center-image");
        imageResizeObserver.observe($(element).get(0));
      }
    });
  } catch (e) {
    console.log(e);
  }
}

// If the character asset is a video, this is called for setting its content
async function CenterVideo(element, assetData, options = {}) {
  function loadImage() {
    return new Promise((resolve) => {
      var video = $("<video />", {
        src: "../../" + assetData.asset,
        muted: true,
        autoplay: true,
      });

      $(element).css({
        position: "relative",
      });

      video.css({
        height: "100%",
        "min-width": 0,
        "min-height": 0,
        position: "absolute",
      });

      // Autoplay needs the property, not only the attribute
      video[0].muted = true;

      video.appendTo($(element)).unwrap();

      // Resolves even if the video can't load or play, so callers go on
      video.on("error", () => resolve());
      video.on("loadedmetadata", () => {
        video[0].play().catch(console.log).finally(resolve);
      });

      video[0].load();
    });
  }

  await loadImage();
}

// Center character images based on settings (div data)
async function CenterImageDo(element) {
  try {
    let data = $(element).data();

    let assetData = data.asset_data;
    let customZoom = data.custom_zoom;
    let customCenter = data.custom_center;
    let scale_based_on_parent = data.scale_based_on_parent;
    let scale_fill_x = data.scale_fill_x;
    let scale_fill_y = data.scale_fill_y;

    let customElement = null;

    if (scale_based_on_parent) {
      customElement = element.parent().parent();
    }

    // $(element).data() is live: keep what this call was for
    const requestedAsset = assetData;

    if (typeof assetData == "string") {
      assetData = JSON.parse(assetData);
    }
    if (!assetData) return;

    function loadImage() {
      return new Promise((resolve) => {
        const img = new Image();
        // A missing file would otherwise leave CenterImage() pending forever
        img.onerror = () => resolve();
        img.onload = () => {
          // Another asset was set while this one loaded
          if ($(element).data("asset_data") !== requestedAsset) return resolve();

          let eyesight = assetData.eyesight;

          if (!eyesight) {
            eyesight = {
              x: img.naturalWidth / 2,
              y: img.naturalHeight / 2,
            };
          }

          if (!customElement) customElement = element;

          const containerWidth = $(customElement).innerWidth();
          const containerHeight = $(customElement).innerHeight();

          let proportional_zoom = 1;
          if (assetData.average_size) {
            proportional_zoom = 0;
            proportional_zoom = Math.max(
              proportional_zoom,
              (containerWidth / assetData.average_size.x) * 1.2,
            );
            proportional_zoom = Math.max(
              proportional_zoom,
              (containerHeight / assetData.average_size.y) * 1.2,
            );
          }

          // For cropped assets, zoom to fill
          // Calculate max zoom
          const zoom_x = containerWidth / img.naturalWidth;
          const zoom_y = containerHeight / img.naturalHeight;

          let minZoom = 1;

          let rescalingFactor = 1;

          if (assetData.rescaling_factor)
            rescalingFactor = assetData.rescaling_factor;

          let uncropped_edge = assetData.uncropped_edge;

          if (
            !uncropped_edge ||
            uncropped_edge == "undefined" ||
            uncropped_edge.length == 0
          ) {
            if (zoom_x > zoom_y) {
              minZoom = zoom_x * rescalingFactor;
            } else {
              minZoom = zoom_y * rescalingFactor;
            }
          } else {
            if (
              uncropped_edge.includes("u") &&
              uncropped_edge.includes("d") &&
              uncropped_edge.includes("l") &&
              uncropped_edge.includes("r")
            ) {
              minZoom = customZoom * proportional_zoom * rescalingFactor;
            } else if (
              !uncropped_edge.includes("l") &&
              !uncropped_edge.includes("r")
            ) {
              minZoom = zoom_x * rescalingFactor;
            } else if (
              !uncropped_edge.includes("u") &&
              !uncropped_edge.includes("d")
            ) {
              minZoom = zoom_y * rescalingFactor;
            } else {
              minZoom = customZoom * proportional_zoom * rescalingFactor;
            }
          }

          if (scale_fill_x && !scale_fill_y) {
            minZoom = zoom_x;
          } else if (scale_fill_y && !scale_fill_x) {
            minZoom = zoom_y;
          } else if (scale_fill_x && scale_fill_y) {
            minZoom = Math.max(zoom_x, zoom_y);
          }

          const zoom = Math.max(minZoom, customZoom * minZoom);

          // Centering
          let xx = 0;
          let yy = 0;

          if (!customCenter) {
            xx = -eyesight.x * zoom + $(element).innerWidth() / 2;
          } else {
            xx =
              -eyesight.x * zoom + $(element).innerWidth() * customCenter[0];
          }

          let maxMoveX = $(element).innerWidth() - img.naturalWidth * zoom;

          if (!uncropped_edge || !uncropped_edge.includes("l")) {
            if (xx > 0) xx = 0;
          } else {
            if (xx > containerWidth * 0.1) xx = containerWidth * 0.1;
          }
          if (!uncropped_edge || !uncropped_edge.includes("r")) {
            if (xx < maxMoveX) xx = maxMoveX;
          } else {
            if (xx < maxMoveX - containerWidth * 0.1)
              xx = maxMoveX - containerWidth * 0.1;
          }

          if (!customCenter) {
            yy = -eyesight.y * zoom + $(element).innerHeight() / 2;
          } else {
            yy =
              -eyesight.y * zoom + $(element).innerHeight() * customCenter[1];
          }

          let maxMoveY = $(element).innerHeight() - img.naturalHeight * zoom;

          if (!uncropped_edge || !uncropped_edge.includes("u")) {
            if (yy > 0) yy = 0;
          } else {
            if (yy > containerHeight * 0.1) yy = containerHeight * 0.1;
          }
          if (!uncropped_edge || !uncropped_edge.includes("d")) {
            if (yy < maxMoveY) yy = maxMoveY;
          } else {
            if (yy < maxMoveY - containerHeight * 0.1)
              yy = maxMoveY - containerHeight * 0.1;
          }

          if (data.use_dividers === false) {
            $(element).parent().css("position", "absolute");
          }

          if (data.z_index) {
            $(element).parent().css("z-index", data.z_index);
          } else {
            $(element).parent().css("z-index", 0);
          }

          $(element).css({ position: "relative" });
          $(element).find("img.hd-img").remove();
          // The image already loaded, rather than a new one for the same src
          const $img = $(img).addClass("hd-img").css({
            position: "absolute",
            left: `${xx}px`,
            top: `${yy}px`,
            width: `${img.naturalWidth * zoom}px`,
            height: `${img.naturalHeight * zoom}px`,
          });
          $(element).append($img);

          resolve();
        };
        img.src = "../../" + assetData.asset;
      });
    }

    await loadImage();
  } catch (e) {
    console.log(e);
  }
}

async function FindImages(folder = "") {
  let flag = true;
  let counter = 1;
  const files = [];

  while (flag) {
    const filename = `${folder}/${counter}.png`;
    try {
      await $.get(filename);
      files.push(filename);
      counter += 1;
    } catch (e) {
      flag = false;
    }
  }

  return files;
}

function powerOf2(v) {
  return v && !(v & (v - 1));
}

function nextPow2(v) {
  var p = 2;
  while ((v >>= 1)) {
    p <<= 1;
  }
  return p;
}

/**
 * Stores content to be added to the DOM with SetInnerHtml later
 */
class ContentResolver {
  constructor() {
    this.list = [];
  }

  add(selector, value) {
    this.list.push({ s: selector, v: value });
    return "";
  }

  resolve() {
    for (let element of this.list) {
      SetInnerHtml($(element.s), element.v);
    }
  }
}

function HandleHDStateUpdateMessage(message) {
  const deltaIdx = message["delta_index"];
  const deltas = message["delta"];

  if (deltaIdx < maxAppliedDeltaIdx) {
    throw Error(
      `Received out of order delta ${deltaIdx} (applied: ${maxAppliedDeltaIdx})`,
    );
  }
  // The server numbers deltas one by one: a gap means one was missed and the
  // state would silently stay wrong
  if (maxAppliedDeltaIdx >= 0 && deltaIdx > maxAppliedDeltaIdx + 1) {
    throw Error(
      `Missed deltas before ${deltaIdx} (applied: ${maxAppliedDeltaIdx})`,
    );
  }

  // it's fine if this doesn't fire because we threw an exception, because
  // that means state wasn't applied and we've requested new program state.
  DispatchUpdate(applyDeltas(data, deltas));
  maxAppliedDeltaIdx = deltaIdx;
}

function HDHasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

/**
 * Takes a single delta operation and applies it to data, copying the objects
 * along its path that aren't in copied yet (and adding the copies to it).
 *
 * @param {Object} data
 * @param {Delta} delta
 * @param {Set<Object>} copied
 */
function applyDelta(data, delta, copied) {
  const pathPieces = delta.path;
  /** @type {DeltaOpType} */ const deltaOp = delta.action;
  const newValue = delta.value;
  const lastPiece = pathPieces[pathPieces.length - 1];

  let currentData = data;
  for (let i = 0; i < pathPieces.length - 1; i += 1) {
    const key = pathPieces[i];
    let next = currentData[key];
    if (!HDHasOwn(currentData, key)) {
      next = {};
      copied.add(next);
    } else if (next !== null && typeof next === "object" && !copied.has(next)) {
      next = Array.isArray(next) ? next.slice() : { ...next };
      copied.add(next);
    }
    currentData[key] = next;
    currentData = next;
  }

  if (deltaOp === "dictionary_item_removed") {
    if (HDHasOwn(currentData, lastPiece)) {
      delete currentData[lastPiece];
    } else {
      console.warn(`Couldn't find data to delete for path: ${pathPieces}`);
    }
  } else {
    currentData[lastPiece] = newValue;
  }
}

/**
 * Returns data with the deltas applied, leaving data as it was: only the
 * objects on the changed paths are copied, the rest is shared with it.
 * Much cheaper than deep-cloning the whole state for oldData each time.
 *
 * @param {Object} data
 * @param {Delta[]} deltas python deep-diff delta object.
 */
function applyDeltas(data, deltas) {
  const result = { ...data };
  const copied = new Set([result]);
  for (let delta of deltas) {
    applyDelta(result, delta, copied);
  }

  return result;
}

// taken from https://github.com/Readek/RoA-Stream-Tool/blob/master/Stream%20Tool/Resources/Scripts/Utils/On%20Transition%20Event.mjs

/**
 * Starts an event listener fired every time browser becomes "active"
 * @param {() => {void}} hide - hideElements() function
 * @param {() => {void}} show - showElements() function
 */
function initOnBrowserActive(hide, show) {
  // if browser is on OBS
  if (window.obsstudio) {
    // every time the browser source becomes active
    window.addEventListener("obsSourceActiveChanged", (event) => {
      if (event.detail.active) {
        // when its show time
        show();
      } else {
        // when browser goes to the backstage
        hide();
      }
    });
  } else {
    // this is here for regular browsers for better developer experiece
    // this will trigger every time the browser goes out of view (or back to view)
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        // if lights go out
        hide();
      } else {
        // when the user comes back
        show();
      }
    });
  }
}

/** Determines if the browser view is currently active/visible */
function isBrowserActive() {
  if (window.obsstudio) {
    return true; // theres no way to get active state without the event listener :(
  } else {
    // visibilityState is a string: "hidden" would be truthy too
    return document.visibilityState === "visible";
  }
}
