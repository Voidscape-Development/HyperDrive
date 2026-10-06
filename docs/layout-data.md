# Layout data: bracket, stream queue, games and layout themes

What TSH sends to the layouts (in `program_state`) for the bracket widget, the
Stream Queue widget, the scoreboard's Games tab and the layout theme in use.

## `bracket`

### `bracket.bracket`

The bracket of the phase selected in the bracket widget.

| Key | |
| - | - |
| `type` | `DOUBLE_ELIMINATION`, `SINGLE_ELIMINATION`, `ROUND_ROBIN` or `SWISS` |
| `name` | The phase's name |
| `fromStartgg` | Loaded from start.gg |
| `progressionsOut` | Players going on to another phase (no champion then) |
| `limitExportNumber` | Top N when "Only show the top" is on, otherwise `null` |
| `sides` | The bracket's columns, by side (see below) |
| `sets` | Every set shown, by id (see below) |
| `results` | Elimination: players by finishing order, `[{order, id, name}]`. With players going on, the players going on. |
| `standings` | Round robin and swiss: `[{rank, playerId, name, played, wins, draws, losses, points, gameWins, gameLosses, gameDiff, buchholz, byes}]` |
| `totalRounds` | Round robin and swiss |
| `byes` | Round robin and swiss: players sitting out, by round key: `{"pool:1": [{id, name}]}` |

`sides` has a key per side the bracket has: `winners`, `losers`,
`grand_final`, `third_place` and `pool` (round robin and swiss). Each is a
list of columns, left to right:

```json
{"key": "winners:2", "name": "Winners Semi-Final", "sets": ["m5", "m6"]}
```

`sets` are in order, top to bottom. Sets against a bye aren't sent (and
neither are columns left empty), so layouts don't have to hide them.

Each set in `sets`:

| Key | |
| - | - |
| `id`, `identifier` | The set's id and its letter (A, B...) |
| `side`, `column`, `row` | Where it is |
| `roundName` | Its round's name |
| `players` | Its two slots: `{id, seed, name, bye, pending, source, manual}`. `id` is the player's slot in `bracket.players.slot`. `source` says what a pending slot waits for, e.g. "Winner of C". `manual` is set when the player was put there by hand. |
| `score` | `[a, b]`; `-1` is a DQ |
| `completed` | |
| `winner` | `0` or `1` for the slot that won, `"draw"`, or `null` |
| `nextWin`, `nextLose` | Where the winner and the loser go: `{set, slot}`, or `null` |
| `loserPlacement` | Placement the loser gets if they lose their next set |
| `isGrandFinal`, `isReset`, `resetNeeded` | Grand final sets. A reset that isn't needed has `resetNeeded: false`. |
| `startggId` | The set's start.gg id, when loaded from start.gg |

### Helpers for layouts: `layout/include/bracket.js`

Load it after `globals.js` (`<script src="../include/bracket.js"></script>`)
for `TSHBracket`:

| | |
| - | - |
| `IsPool(bracket)` | Round robin or swiss |
| `Areas(bracket)` | Columns of the upper part (winners, grand finals) and lower part (losers) of an elimination bracket. The 3rd place match goes in the lower part, or after the final when there's no losers side. |
| `Signature(data)` | Changes only when the bracket has to be drawn again (not for scores or players) |
| `SetState(set, expand)` | `hidden`, `displayed` or `done` (shown with its line to the next set) |
| `Winner(set)`, `ScoreText(set, slot)` | |
| `StandingsHtml(data)` | A pool's standings, or an elimination bracket's results, as a table |
| `RenderPool(container, data)` | Draws a pool's rounds, for layouts without a pool view of their own |
| `ToRounds(bracket, players)` | The bracket in the older `rounds` shape (`{"1": {name, sets: {"0": {playerId, score, nextWin...}}}}`, losers rounds negative), with byes filled in, for layouts drawn around it |

`layout/include/bracket.css` has the pool view, the standings table and the
layout theme's bracket options.

`layout/bracket/standings.html` shows only the standings.

### `bracket.focus`

What the bracket focus layout (`layout/bracket_focus`) zooms to, set from
the bracket widget's "Layout focus" bar, hotkeys or the `/bracket-focus-app`
web page. There's one per focus channel, by name: `{"main": {...}, "Losers
cam": {...}}`. `main` is always there; more are added in the bracket widget,
so layouts in different sources can show different things. Each layout shows
one, picked with `?channel=<name>` in its URL (`main` without it). The
bracket widget, and the hotkeys, act on the channel picked in the widget.

Each channel's focus:

| Key | |
| - | - |
| `mode` | `all`, `sets` / `rounds` (picked by hand), `player` (a player's run), `follow` (the set on a scoreboard) or `tour` (the whole bracket, then each round in turn) |
| `sets` | Ids of the sets in focus, in the bracket's order. Empty: the whole bracket. |
| `rounds` | Keys of the rounds in focus (`winners:2`...) |
| `label` | What's in focus, e.g. the round's or the player's name |
| `player` | `player`: the player's slot in `bracket.players.slot` |
| `scoreboard` | `follow`: the scoreboard followed. Its set is the one with its start.gg set id, or between its two teams. |
| `interval`, `step`, `steps` | `tour`: seconds per step, the step shown and how many there are |

The same can be set from the web server, on the channel in `?channel=<name>`
(`main` without it; 404 `NO_CHANNEL` for one that doesn't exist): `GET
/bracket-focus` answers what's in focus, the channels and the rounds, sets
and players there are to pick from, `POST /bracket-focus` takes `{mode, sets,
rounds, player, scoreboard, interval}` or `{"move": 1}` (`-1`) for the next
(previous) round. As links, e.g. for a Stream Deck: `/bracket-focus/all`,
`/bracket-focus/next-round`, `/bracket-focus/previous-round`,
`/bracket-focus/follow?scoreboard=<n>`, `/bracket-focus/tour?interval=<seconds>`
and `/bracket-focus/player?id=<slot>`, with `&channel=<name>` for a channel
other than `main`.

The layout draws the bracket once at full size and moves and scales it to
the sets in focus, outlining them and dimming the rest. `no_title.html` has
no title bar; add `?ignore_focus=1` to its URL for a source that always shows
the whole bracket, `?max_zoom=<percent>` to change how big it draws a set.

### `bracket.phases`

Every phase of the bracket widget: `[{id, name, type, current}]`.

### `bracket.players`, `bracket.phase`, `bracket.phaseGroup`

The player list (unchanged), and the start.gg phase and phase group names.

## `stream_queue`

| Key | |
| - | - |
| `streams` | Every stream, in the widget's order: `[{name, manual, scoreboard, sets}]`. `scoreboard` is the scoreboard number showing the stream's sets, or `null`. |
| `byName` | The same sets, by stream name |
| `lastUpdated` | When start.gg's queues were last pulled (seconds since the epoch) |
| `currentStream` | The Twitch username set in TSH |

Each set has start.gg's set data (`id`, `match`, `phase`, `best_of`,
`best_of_text`, `state`, `station`, `team: {"1": {teamName, losers, seed,
player: {"1": {...}}}, "2": {...}}`), plus:

| Key | |
| - | - |
| `queueKey` | The set's key in the queue |
| `source` | `startgg` (in start.gg's queue), `added` (a start.gg set added by hand) or `custom` (typed in by hand) |
| `position` | 1 for the next set |
| `onStream` | It's the set on the stream's scoreboard |

`score.N.station_queue` (sets of the station tracked by scoreboard N) is
unchanged.

## `score.N.games`

The games of the set on scoreboard N, by game number:

| Key | |
| - | - |
| `game` | Game number |
| `winner` | `1` or `2` for the team that won, `0` for a draw, `null` if not played yet |
| `stage`, `stageData` | The stage's codename and its data (as in `game.stages`) |
| `characters` | Characters by team: `{"1": ["Mario"], "2": ["Fox"]}`, by player |
| `current` | It's the game being played |

## `score.N.report`

Reporting the set to start.gg: `{setId, status, message, liveUpdates}`.
`status` is `idle`, `pending`, `sending`, `synced` (games sent), `reported`,
`retrying` or `error` (`message` says why).

## `score.N.stage_strike.characterLock`

The character select page (`/character-select?scoreboard=N`, and `&team=1`
or `&team=2` for one team's page) lets each team pick its characters once per
score: `{score: [team 1, team 2], locked: {"1": bool, "2": bool}}`. A team's
picks reach the scoreboard once the other team sent theirs. The stage strike
page shows the same character select when there's no ruleset.

Picks are sent to `POST /character_select_report?scoreboard=N[&team=T]` with
`{"characters": {team: {player: [[character, skin], ...]}}}`; it answers 409
`ALREADY_PICKED` until the score changes.

## `layout_theme`

The theme picked in Layout themes:

| Key | |
| - | - |
| `name` | |
| `values` | Every field, by section: `{general: {primary_color, ...}, chip: {...}, ...}` (see `LayoutThemeSchema()` in `src/LayoutOptions/TSHLayoutThemes.py`) |
| `css` | The values as CSS custom properties: `{"--general-primary-color": "#d02670", ...}` |
| `stylesheet` | The same as a `:root { ... }` stylesheet |

Layouts don't need to read it: `ApplyLayoutTheme()` in `globals.js` applies
it before each `Update()`:

- Every `css` property is set on `:root`, along with `--font` when the theme
  has a font.
- With "Use this theme's colors in layouts" (`general.apply_colors`) on, it
  also sets `main.css`'s own properties (`--text-color`, `--bg-color`,
  `--bg-fill` (the background, gradient included), `--border-radius`,
  `--border-radius-chip`, `--accent-color`, `--accent-secondary-color`,
  `--p1/p2-score-bg-color`, `--p1/p2-score-color`, and
  `--p1/p2-sponsor-color` with custom sponsor colors), plus `--chip-color`,
  `--chip-bg`, `--bracket-score-bg`, `--bracket-sponsor-bg`,
  `--bracket-winner-color`, `--bracket-line-color`, `--strike-striked-color`
  and `--strike-selected-color`, and adds `tsh-theme-colors` to `<body>`.
  These go in a stylesheet, so a color a layout sets on `:root` itself
  (e.g. a scoreboard's team colors) wins.
- Display options add classes to `<body>`, only for values that change what
  layouts show. `main.css` and `include/bracket.css` hide by them:
  `tsh-hide-pronouns`, `tsh-hide-seed`, `tsh-hide-social`,
  `tsh-hide-country-flag`, `tsh-hide-state-flag`, `tsh-hide-avatar`,
  `tsh-hide-losers`, `tsh-no-text-outline`, `tsh-text-upper`, `tsh-text-none`,
  `tsh-bracket-hide-avatar`, `tsh-bracket-hide-character`,
  `tsh-bracket-hide-country-flag`, `tsh-bracket-hide-state-flag`,
  `tsh-bracket-hide-seed`, `tsh-bracket-hide-round-names`,
  `tsh-bracket-show-identifier`, `tsh-bracket-hide-pending`,
  `tsh-bracket-no-dim-losers`, `tsh-bracket-hide-focus-label`,
  `tsh-standings-hide-game-diff`,
  `tsh-standings-hide-points`, `tsh-standings-show-buchholz`,
  `tsh-strike-hide-names` and `tsh-strike-hide-striker`.
- The animation speed is set on GSAP's global timeline (off: 1000x).

A `tsh_theme` event is sent on `document` after it's applied, and
`ThemeValue(section, field, fallback)` reads a value.
