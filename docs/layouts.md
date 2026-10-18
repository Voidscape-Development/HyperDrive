# Writing layouts

A layout is a folder in `layout/` with HTML pages, a stylesheet and a script.
The runtime in `layout/include/` does the plumbing: it loads the libraries and
settings, follows the program state ([layout-data.md](layout-data.md)), calls
the layout with what changed, plays its intro, and hides it for Display
Controls. The layout says what to show.

## A page

```html
<!doctype html>
<html>
  <head>
    <meta charset="UTF-8" />
    <script src="../include/globals.js"></script>
    <link rel="stylesheet" href="../include/main.css" />
    <link rel="stylesheet" href="./index.css" />
  </head>
  <body>
    <div class="p1 container"><div class="name"></div><div class="score"></div></div>
    <div class="p2 container"><div class="name"></div><div class="score"></div></div>
    <script>
      HD.page({ size: "mini" }); // Options for this page (optional)
    </script>
    <script src="index.js"></script>
  </body>
</html>
```

Pages are classic scripts, not modules: OBS opens them from `file://`, where
modules don't load. Everything is on the global `HD`.

`globals.js` loads jQuery (`$`), GSAP, lodash (`_`) and the rest of the
runtime asynchronously. A layout's script can call `HD.layout()`, `HD.page()`,
`HD.every()` and `HD.turns()` straight away, and the rest from inside its
functions.

## The layout

```js
HD.layout({
  // The parts of the state it reads: only those are sent
  subscribe: ["score", "game", "tournamentInfo"],

  // Defaults, under settings.json and the page's options
  settings: { show_score: true },

  intro(tl, s) {
    tl.from(".container", { autoAlpha: 0, x: -50, duration: 0.5 });
  },

  update(s) {
    for (const t of s.teams) {
      t.set(".name", HD.ui.name(t.player, t.team));
      t.set(".score", s.settings.show_score ? t.team.score : "");
    }
  },
});
```

| | |
| - | - |
| `subscribe` | The state's top-level keys the layout reads (see below). Without it, it gets everything. |
| `settings` | Default settings |
| `theme` | Settings the layout theme can change: `{ "setting.path": [section, field, theme default, (value) => setting] }` |
| `plugins` | GSAP plugins it uses, loaded from `include/gsap/` and registered before `init()`: `["SplitText", "Flip"]`. List a plugin after the ones it needs (`CustomEase` before `CustomBounce`). |
| `init(settings)` | Once, before the first state: loading files, starting timers |
| `update(s)` | With each state. One runs at a time; states that arrive meanwhile are folded into the next. |
| `intro(tl, s)` | Adds the show animation to a GSAP timeline, built again each time the layout is shown |
| `outro(s)` | Hides the layout; without it, the intro plays backwards |
| `start(s)` | After the intro is built, each time the layout is shown |

The first show waits for `update()`, the fonts and the images, so nothing
pops in during the intro.

### Subscriptions

With `subscribe`, the web server sends the layout only those parts of the
state (plus `layout_theme` and `display`, which the runtime uses), in the
whole state and in each update. A scoreboard doesn't need the bracket, the
stream queue or the completed sets, which are the biggest parts. The runtime
cuts the state down the same way when it reads `program_state.json` or gets
it from the dev harness, so a key missing from the list shows up in the
previews and the layout check too.

Character art needs `game` (the asset settings), and `HD.stage()` needs
`game` and `score`.

### Settings

From lowest to highest: the layout's `settings`, `layout/settings.json`, the
folder's `settings.json`, the layout theme (through `theme`), then page
options: `HD.page({...})` and the page's URL parameters (`?size=mini`;
`true`, `false` and numbers are converted). `s.settings` has the result.

### The scope: `s`

| | |
| - | - |
| `s.data`, `s.old` | The state, and the one the previous `update()` ran with (`{}` the first time) |
| `s.first` | The first `update()` |
| `s.changed(path)` | Whether a part of the state changed: a lodash path (`"commentary"`) or a function of the state |
| `s.scoreChanged(path)` | The same, inside this scoreboard: `"team.1.color"` |
| `s.n`, `s.score` | The scoreboard number (`?scoreboardNumber=`, default 1) and its data |
| `s.teams` | Both sides, `[t1, t2]` (see below) |
| `s.isTeams` | Doubles (more than one player a team) |
| `s.settings` | The settings |
| `s.set(...)` | `HD.set()` |
| `s.characters(target, options)` | Character art (see below) |
| `s.wait(promise)` | Makes the first show wait for it |

Each `t` in `s.teams`: `t.n` (1 or 2), `t.team`, `t.players`, `t.player` (the
first), `t.name` (the team's name, or its players'), and `t.set(selector,
content)`, which looks inside the side's `.p1`/`.p2`. `t.sel()` gives that
selector: `t.sel(".name")` is `".p1 .name"`, `t.sel("&.container")` is
`".p1.container"`.

## Showing things

Content is **text** unless it's marked as HTML, so names and tags can't break
the page:

```js
HD.set(".name", player.name); // Text
HD.set(".name", HD.html`<span class="sponsor">${player.team}</span>${player.name}`); // HTML, values escaped
HD.set(".logo", HD.img(HD.asset(player.sponsor_logo))); // An image, or nothing
```

- `HD.html` is a template whose values are escaped. `null`, `undefined` and
  `false` show nothing, and arrays are joined, so `${cond && HD.html`...`}` and
  `${list.map(...)}` work. **A number `0` shows as "0"**: use
  `${seed ? ... : ""}` for numbers.
- `HD.raw(html)` is trusted HTML; `HD.join(items, separator)` joins the
  non-empty ones.
- `HD.set(target, content, options)` puts content in a `.text` child,
  fades it when it changes, and squeezes it to fit (or shrinks the font with
  `.font-scale-fit`). It does nothing when the content is the same.
  Options: `duration`, `in`, `out` (GSAP vars), `after()`, `force`.
- `HD.render(target, content)` puts structure (rows, iframes) straight in.
  `HD.build(target, key, content)` does it only when `key` changed, so the rows
  stay and `HD.set()` can fade what's in them. It returns whether it built.

### Shared pieces

| | |
| - | - |
| `HD.asset(path)` | A path from the state as a URL |
| `HD.players(team)`, `HD.playerNames(team)`, `HD.teamName(team)` | |
| `HD.text(parts, separator)` | Joins the non-empty parts |
| `HD.stage(data, score)` | The stage picked |
| `HD.custom(p, key)`, `HD.customFile(p, key)` | A player's custom fields |
| `HD.ordinal(n)` | `1st`, `2nd`... |
| `HD.ui.name(player, team)` | Sponsor, name and the losers badge |
| `HD.ui.flag(place, codeClass)` | A country or state flag with its code |
| `HD.ui.chip(kind, text)` | An icon and text, e.g. `HD.ui.chip("twitter", handle)` |
| `HD.ui.sponsorLogo(path)`, `HD.ui.variant(variant)` | |
| `HD.commentators(s, container, fields)` | The commentators |
| `HD.teamColors(s, props)` | The scoreboard's team colors as `--p1-...` properties |
| `HD.classIntro(tl)` | An intro from classes: `.fade`, `.fade_down`/`_up`/`_left`/`_right`, `*_stagger`, `*_stagger_reverse` |
| `HD.theme(section, field, fallback)` | A layout theme value |
| `HD.every(seconds, fn)`, `HD.turns(seconds, render)` | Content that takes turns (`turns.pick(items)`) |
| `HD.restart()`, `HD.shown()` | Play the intro again; whether the layout is on screen |

### Character art

```js
s.characters(t.sel(".character"), {
  source: ["score", s.n, "team", t.n], // The team or player in the state
  ...HD.slideToMiddle(t.n === 1 ? 1 : -1), // Or in / out GSAP vars
});
```

Options: `asset_key`, `custom_zoom`, `custom_center`, `use_dividers`,
`scale_based_on_parent`, `scale_fill_x`/`_y`, `flip_x`, `slice_character`
(`[from, to]` of each player's), and `load_settings_path` (the section of
`settings.json` with the game's asset settings).

### Shared layouts

Layouts that several folders use live in `include/` and register on
`HD.layouts`, and pages use them directly or extend them:

```js
HD.layout(HD.layouts.versus); // include/versus.js
HD.layout({ ...HD.layouts.scoreboard, intro(tl) { ... } });
```

`scoreboard.js`, `versus.js` (also `VS`, its building blocks), `top8.js`,
`stream_queue.js`, `stage_strike_display.js`, `multicam.js`, `map.js` and
`bracket.js` (`HDBracket`, see [layout-data.md](layout-data.md#helpers-for-layouts-layoutincludebracketjs)).

## Developing

- **Dev harness**: with HyperDrive running, open
  `http://localhost:5500/layout/dev.html`. Pick a page, then use HyperDrive's
  live state or a fixture you can edit and send (Ctrl+Enter). It can also
  turn a state into doubles and hide the layout as Display Controls would.
- **Editor types**: `layout/jsconfig.json` and `include/hd.d.ts` give
  editors completion and docs for `HD`.
- **Previews and checks**: `scripts/previews/render_previews.py` renders
  pages. On pull requests, the "Layout check" workflow renders the layouts a
  change touches before and after. It fails on page errors, and lists the
  pages that look different, with images, in the run's summary and its
  `layout-diff` artifact. To do the same locally:

  ```sh
  python scripts/previews/render_previews.py layout/scoreboard --out /tmp/after --strict
  # ...same with the base branch checked out, into /tmp/before, then:
  python scripts/previews/compare_previews.py /tmp/before /tmp/after --diff /tmp/diff
  ```
