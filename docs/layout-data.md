# Layout data: bracket, stream queue, completed sets, games, team battle, socials, custom player data, layout themes and display controls

What HyperDrive sends to the layouts (in `program_state`) for the bracket widget, the
Stream Queue widget, the completed sets, the scoreboard's Games window, the Crew/Team Battle window, the
players' socials and custom data, and the layout theme in use.

A socket.io client gets the whole state when it connects (`program_state`:
`{state, delta_index}`), then changes (`program_state_update`:
`{delta_index, delta}`, numbered one by one). A client that only needs some
of it connects with `auth: {state_keys: ["score", "game"]}` and gets only
those top-level keys, in both. Its updates keep their numbers, with an empty
`delta` when none of its keys changed. Layouts do this with `subscribe` (see
[layouts.md](layouts.md#subscriptions)).

## `bracket`

The bracket widget's phases are a pool: phases built in it and start.gg
phase groups loaded into it (each loaded group is a phase; loading it again
reloads it). What goes on stream is set by channels, a tab each in the
widget: each channel shows one phase of the pool, with its own "only show
the top N", its own focus (`bracket.focus`) and, in the widget, its own
view and selection. Several channels can show the same phase; they share
its data. `main` is always there, and layouts without `?channel=` show it.

### `bracket.channels`

Each channel's bracket, by name: `{"main": {...}, "TV 1": {...}}`.

| Key | |
| - | - |
| `bracket` | Its phase's bracket, with its top N: as `bracket.bracket` below |
| `phase`, `phaseGroup` | The start.gg phase and phase group names, or the phase's name and `""` for a phase built in the widget |
| `phaseId` | The phase's id in `bracket.phases` |
| `playersPath` | Where its player list is in the state (`bracket.rosters.<key>`) |

`HDBracket.ForChannel(data, channel)` in `layout/include/bracket.js` puts a
channel's bracket in place of `bracket.bracket`, `bracket.players`,
`bracket.phase` and `bracket.phaseGroup`, so a layout can show any channel.
`layout/bracket_focus` and the `layout/bracket` pages take `?channel=<name>`.

### `bracket.rosters`

The player lists: `local` for the phases built in the widget, and one per
start.gg phase group loaded, by its id. Each as `bracket.players`.

### `bracket.bracket`

The main channel's bracket (also in `bracket.channels.main.bracket`).

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
for `HDBracket`:

| | |
| - | - |
| `IsPool(bracket)` | Round robin or swiss |
| `Areas(bracket)` | Columns of the upper part (winners, grand finals) and lower part (losers) of an elimination bracket. The 3rd place match goes in the lower part, or after the final when there's no losers side. |
| `Signature(data)` | Changes only when the bracket has to be drawn again (not for scores or players) |
| `SetState(set, expand)` | `hidden`, `displayed` or `done` (shown with its line to the next set) |
| `Winner(set)`, `ScoreText(set, slot)` | |
| `StandingsHtml(data)` | A pool's standings, or an elimination bracket's results, as a table |
| `GridHtml(data)` | A pool as a round robin grid of who played who, players in seed order |
| `RenderPool(container, data)` | Draws a pool's rounds, for layouts without a pool view of their own |
| `PlayerSlotHtml(slot)`, `UpdateSet(s, element, set, data)` | A set's two player rows, and filling them in (names, flags, avatars, characters) |
| `ToRounds(bracket, players)` | The bracket in the older `rounds` shape (`{"1": {name, sets: {"0": {playerId, score, nextWin...}}}}`, losers rounds negative), with byes filled in, for layouts drawn around it |

`layout/include/bracket.css` has the pool view, the standings table and the
layout theme's bracket options.

`layout/bracket/standings.html` shows only the standings, and
`layout/bracket/round_robin.html` a round robin / swiss pool as a grid: a
row and a column per player, the score where two players meet (from the
row player's side) and a blank cell where a player meets themselves.

### `bracket.focus`

What the bracket focus layout (`layout/bracket_focus`) zooms to, per channel
(see `bracket` above), set from the bracket widget's "Layout focus" bar,
the `/bracket-focus-app` web page or a Stream Deck: `{"main": {...}, "TV 1":
{...}}`. Each layout shows one, picked with `?channel=<name>` in its URL
(`main` without it).

Each channel's focus:

| Key | |
| - | - |
| `mode` | `all`, `sets` / `rounds` (picked by hand), `player` (a player's run), `follow` (the set on a scoreboard) or `tour` (the whole bracket, then each round in turn) |
| `sets` | Ids of the sets in focus, in the bracket's order. Empty: the whole bracket. |
| `rounds` | Keys of the rounds in focus (`winners:2`...) |
| `label` | What's in focus, e.g. the round's or the player's name |
| `player` | `player`: the player's slot in the channel's player list |
| `scoreboard` | `follow`: the scoreboard followed. Its set is the one with its start.gg set id, or between its two teams. |
| `interval`, `step`, `steps` | `tour`: seconds per step, the step shown and how many there are |
| `phase` | Id of the phase the channel shows, in `bracket.phases` |

The same can be set from the web server, on the channel in `?channel=<name>`
(`main` without it; 404 `NO_CHANNEL` for one that doesn't exist): `GET
/bracket-focus` answers what's in focus, the channels and the rounds, sets
and players there are to pick from, `POST /bracket-focus` takes `{mode, sets,
rounds, player, scoreboard, interval}`, `{"move": 1}` (`-1`) for the next
(previous) round, or `{"phase": <id>}` for the phase it shows (the `GET`
answer's `phases` lists them, `[{value, label, section}]`, section `local`
or `startgg`; 404 `NO_PHASE` for one that isn't there). As links, e.g. for a Stream Deck: `/bracket-focus/all`,
`/bracket-focus/next-round`, `/bracket-focus/previous-round`,
`/bracket-focus/follow?scoreboard=<n>`, `/bracket-focus/tour?interval=<seconds>`
`/bracket-focus/player?id=<slot>` and `/bracket-focus/phase?phase=<id>`, with `&channel=<name>` for a channel
other than `main`.

The layout draws the bracket once at full size and moves and scales it to
the sets in focus, outlining them and dimming the rest. `no_title.html` has
no title bar; add `?ignore_focus=1` to its URL for a source that always shows
the whole bracket, `?max_zoom=<percent>` to change how big it draws a set.

### `bracket.phases`

Every phase of the pool: `[{id, name, type, source, phaseGroupId, channels,
current}]`. `source` is `local` (built in the widget) or `startgg`,
`channels` the channels showing it, `current` whether the main channel does.

### `bracket.players`, `bracket.phase`, `bracket.phaseGroup`

The main channel's player list, and its phase and phase group names (as in
`bracket.channels`).

## `stream_queue`

| Key | |
| - | - |
| `streams` | Every stream, in the widget's order: `[{name, manual, scoreboard, sets}]`. `scoreboard` is the scoreboard number showing the stream's sets, or `null`. |
| `byName` | The same sets, by stream name |
| `lastUpdated` | When start.gg's queues were last pulled (seconds since the epoch) |
| `currentStream` | The Twitch username set in HyperDrive |
| `average_set_minutes` | How long the event's last sets took (the median), or `null` before it's known |

Each set has start.gg's set data (`id`, `match`, `phase`, `best_of`,
`best_of_text`, `state`, `station`, `team: {"1": {teamName, losers, seed,
player: {"1": {...}}}, "2": {...}}`), plus:

| Key | |
| - | - |
| `queueKey` | The set's key in the queue |
| `source` | `startgg` (in start.gg's queue), `added` (a start.gg set added by hand) or `custom` (typed in by hand) |
| `position` | 1 for the next set |
| `onStream` | It's the set on the stream's scoreboard |
| `eta` | When the set should start (seconds since the epoch), with each set ahead of it taking as long as the event's last sets did (of the same length, best of 3 or 5, once there are a few of those). In-progress sets (or the one on the stream's scoreboard) count for what's left of them. `null` while it isn't known |
| `eta_minutes` | The same, in minutes from now: `0` for a set being played |
| `started_at` | When start.gg says the set started, or `null` |

Its players (`team.T.player.P`) have their start.gg or parry.gg `id`, as the scoreboard's
players do, which the commentary dashboard uses to look up their stats
(`POST /commentary-preview` with `{"teams": [[player...], [player...]]}`).

`score.N.station_queue` (sets of the station tracked by scoreboard N) is
unchanged.

## `completed_sets`

The event's last 10 completed sets, from "Pull Latest Completed Sets"
(start.gg or parry.gg), most recent first, keyed `"1"`, `"2"`... Shown by
`layout/completed_sets/` (`list.html`, `ticker.html`, `scroll.html`, `card.html` and
`column.html`, and `upset_alert.html` for new upsets; see its `settings.json`).

| Key | |
| - | - |
| `phase_name`, `phase_id` | The phase, and its pool (e.g. `B2`) when it has several |
| `round_name` | |
| `winner_score`, `loser_score` | `-1` is a DQ |
| `winner_seed`, `loser_seed` | Seeds in the event |
| `winner_team`, `loser_team` | The players, by number: `{sponsor, gamertag, country, state, characters}` |
| `winner_team_name`, `loser_team_name` | The entrant's name (a doubles team's name) |
| `bracket_type` | The phase's: `DOUBLE_ELIMINATION`, `SINGLE_ELIMINATION`... |
| `upset_factor` | Placement rounds the winner was expected to finish below the loser, `0` when it isn't an upset |

`country` and `state` are like the scoreboard players' (with `asset`, the
flag), from the player's start.gg / parry.gg profile, or the local player
database when the profile has no location. `characters` are the characters
the player used in the set, in the order they first picked them
(`{"1": {name, en_name, codename, assets}}`), empty when the provider has no
character data for the set.

## `tournamentInfo.logo`, `tournamentInfo.banner`

The URLs of the start.gg tournament's square logo and wide banner, `""` when
it has none, for layouts to brand themselves with.

## `twitch_prediction`

The Twitch prediction of the stream's scoreboard (see the README), `{}` when
there's none: `{id, setId, title, names: {"1", "2"}, outcomes: {"1", "2"},
status, winner}`. `status` is `ACTIVE`, `LOCKED`, `RESOLVED` or `CANCELED`,
`winner` the team that won once it's resolved.

## `score.N.games`

The games of the set on scoreboard N, by game number:

| Key | |
| - | - |
| `game` | Game number |
| `winner` | `1` or `2` for the team that won, `0` for a draw, `null` if not played yet |
| `stage`, `stageData` | The stage's codename and its data (as in `game.stages`) |
| `characters` | Characters by team: `{"1": ["Mario"], "2": ["Fox"]}`, by player |
| `characterData` | The same characters with their data, as in a player's `character`: `{name, en_name, display_name, codename, assets}`. `assets` are the default skin's images (the games don't keep skins). `null` for a player without one |
| `scoreAfter` | The set's score once this game was played: `{"1": 1, "2": 0}`. Draws don't count. `null` for a game not played yet |
| `current` | It's the game being played |

The teams are the scoreboard's sides: when they're swapped, `winner`, the
characters and `scoreAfter` follow the teams. Their colors are in
`score.N.team.T.color`, and the best of in `score.N.best_of`.

[`layout/game_log`](../layout/game_log) shows them: a card per game with its
stage, characters, winner and score after it.

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

## `team_battle`

The Crew/Team Battle window:

| Key | |
| - | - |
| `battle_mode` | `STOCK_POOL` or `FIRST_TO` |
| `battle_value` | The stocks every player starts with (Stock Pool), or the games to win (First To) |
| `plays` | How many of each team's players play. Under the number of players, the others wait on deck until their team picks them |
| `phase`, `match` | |
| `team.T` | `{sponsor, short_name, color, logo, sponsor_logo, active_player, plays_left, player}`: `sponsor` is the team's name, `short_name` the short name typed for it (or empty), `logo` its logo from `user_data/team_logo/` (or `null`), `active_player` the number of the player playing, `plays_left` how many more of its players can play (the one playing included) |
| `team.T.player.P` | A player, as on the scoreboard, plus `dynamic_spinner` (their stocks left, or games won against the current opponent), `active`, `dead` (eliminated), `status` (`playing`, `out`, `on_deck`, or `unused` when their team is out without them playing) and `play_order` (their place in the order the team's players came in, `null` before they play) |
| `team1_spinner-total`, `team2_spinner-total` | Every player's `dynamic_spinner`, added up. With fewer `plays` than players, only the players who can still play count |
| `team1_total-score`, `team2_total-score` | The team scores set in the window |

The layouts in [`layout/team_battle`](../layout/team_battle) show it: a scoreboard
for in game, a roster board and a versus screen, each in a Stock Pool
(`*_stock.html`) and a First To (`*_first_to.html`) version.

## Socials: `socials`

A player's or commentator's social media accounts, as `{platform: handle}`,
for example `{"twitter": "beast", "twitch": "beasttv"}`. It's in the
scoreboard's players, the commentators, the player lists, team battle players
and the stream queue's players, next to `twitter`, which is unchanged
(`socials.twitter` is the same handle). Platforms with no account are left
out, so check one with `player.socials?.twitch`.
[`layout/socials`](../layout/socials) shows them, a player's or the
commentators', with their icons.

start.gg's linked accounts fill `twitter`, `twitch`, `discord` and `xbox`
(the API has no others). The *+* button next to a player's Twitter field adds
the rest by hand: `bluesky`, `youtube`, `instagram`, `tiktok`, `kick` and
`steam`. Those are saved in the player database and kept when start.gg data
is loaded again. Handles are as typed, a leading `@` included.

Each platform has an icon in [`layout/icons`](../layout/icons), named after
its key (`twitter.svg`, `twitch.svg`, `youtube.svg`...). `twitter.svg` is the
original Twitter bird (it used to be the X logo). They're one color
(`currentColor`), so they take the text color of the element they're in. The
Xbox icon is a generic gamepad. The brand glyphs come from
[Simple Icons](https://simpleicons.org) (CC0); the brands' trademarks still
apply.

## Custom player data: `custom`

Any data a tournament wants on stream for a player or commentator, without a
field for it in HyperDrive: a bio, a stats card, a walkout video. Each person
can have a folder in `user_data/custom_player_export/` named after their tag,
or their sponsor and tag (`GG Kestrel`), in any case; the tag's own folder
wins when there are both. Characters that can't be in file names
(`,/|;:<>\?*`) are replaced by `_`, as for avatars.

Every file in it is sent in the person's `custom`, by its name without the
extension (dots in the name become `_`):

| File | Value |
| - | - |
| `.txt` | Its text, without the newline at its end |
| `.md`, `.html`, `.csv`, `.xml` | Its text |
| `.json` | What it holds (an object, a list...). Its text if it isn't valid JSON. |
| Anything else | Its path, e.g. `./user_data/custom_player_export/Azure/card.png` |

```json
"custom": {
  "bio": "Two-time HyperDrive Invitational champion",
  "stats": {"wins": 12, "mains": ["mario"]},
  "card": "./user_data/custom_player_export/Azure/card.png"
}
```

`custom` is in the scoreboard's players (`score.N.team.T.player.P`), the
commentators (`commentary.N`), the player lists (`player_list.slot.N.player.P`
and `bracket.players.slot.N.player.P`) and team battle players. People
without a folder, or with an empty one, have no `custom`.

The files can be managed in the app, in the Player Database window's *Player
media* tab (also opened by the *Media...* button of a player or commentator),
which also sets avatars. Its *Sponsor logos* and *Team logos* tabs manage
`user_data/sponsor_logo/` and `user_data/team_logo/`.

HyperDrive checks the folders every second, so changes to the files reach the
layouts while the person is on stream; so do a player's `avatar`, `sponsor_logo`
and `sponsor_logos`. A file replaced by another with the same name keeps the
same path, so a layout showing it doesn't load it again. Turn custom data off
with *Export custom player data* in Settings > General.

A player's `avatar` is `user_data/player_avatar/<sponsor> <tag>.png`, or
`<tag>.png` when there's none with their sponsor, so it stays when their
sponsor changes. Avatars set in the app are saved as the tag alone.

`sponsor_logos` has the logo of each of a player's sponsors (`HD | GG`:
`{"1": ".../HD.png", "2": ".../GG.png"}`) when there's no logo for all of them
together, which is then `sponsor_logo`.

In layouts (see [layouts.md](layouts.md)):

| | |
| - | - |
| `HD.custom(player, key, fallback = null)` | `player.custom[key]`, or `fallback` |
| `HD.customFile(player, key, fallback = null)` | The `src` of the image or video in the file named `key`, or `fallback` |

```js
t.set(".bio", HD.custom(t.player, "bio", ""));
t.set(".card", HD.img(HD.customFile(t.player, "card")));
```

`player_presentation` shows `bio` under the player's name.

## `layout_theme`

The theme picked in Layout themes:

| Key | |
| - | - |
| `name` | |
| `values` | Every field, by section: `{general: {primary_color, ...}, chip: {...}, ...}` (see `LayoutThemeSchema()` in `src/LayoutOptions/LayoutThemes.py`) |
| `css` | The values as CSS custom properties: `{"--general-primary-color": "#ffb800", ...}` |
| `stylesheet` | The same as a `:root { ... }` stylesheet |

Layouts don't need to read it: the runtime (`globals.js`) applies it before
each `update()`:

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
  and `--strike-selected-color`, and adds `hd-theme-colors` to `<body>`.
  These go in a stylesheet, so a color a layout sets on `:root` itself
  (e.g. a scoreboard's team colors) wins.
- Display options add classes to `<body>`, only for values that change what
  layouts show. `main.css` and `include/bracket.css` hide by them:
  `hd-hide-pronouns`, `hd-hide-seed`, `hd-hide-social`,
  `hd-hide-country-flag`, `hd-hide-state-flag`, `hd-hide-avatar`,
  `hd-hide-losers`, `hd-no-text-outline`, `hd-text-upper`, `hd-text-none`,
  `hd-bracket-hide-avatar`, `hd-bracket-hide-character`,
  `hd-bracket-hide-country-flag`, `hd-bracket-hide-state-flag`,
  `hd-bracket-hide-seed`, `hd-bracket-hide-round-names`,
  `hd-bracket-show-identifier`, `hd-bracket-hide-pending`,
  `hd-bracket-no-dim-losers`, `hd-bracket-hide-focus-label`,
  `hd-standings-hide-game-diff`,
  `hd-standings-hide-points`, `hd-standings-show-buchholz`,
  `hd-strike-hide-names` and `hd-strike-hide-striker`.
- The animation speed is set on GSAP's global timeline (off: 1000x).

A `hd_theme` event is sent on `document` after it's applied, and
`HD.theme(section, field, fallback)` reads a value.

A layout whose settings the theme can change maps them in its `theme`:
`{ "setting.path": [section, field, theme default, (value) => setting] }`.
A theme value only counts when it isn't its field's default (so the default
theme keeps the layout's `settings.json`), and page options still win. The
stream queue layouts (`stream_queue` section) read theirs this way.

## `display`

What the Display Controls window (and its `/display/...` links, see the
README) has turned on and off:

```json
{"folders": {"scoreboard": true, "commentators": false}, "groups": {"main": true}}
```

`globals.js` does the work, so layouts don't have to: a page is shown while
its folder (the folder its page is in) is on and so is every group in its
`?display=<group>[,<group>...]` (lowercase). When it's turned off, the
layout's intro plays backwards (or its `outro`), then the page fades out;
when it's turned back on, the intro plays again. One that's off when it
loads stays hidden, without playing it, and so does one that's off when OBS
shows its source.

To hide it another way than the intro backwards, a layout has an `outro`:

```js
HD.layout({
  outro: () => gsap.to(".container", { y: -100, autoAlpha: 0, duration: 0.4 }),
  // ...
});
```
