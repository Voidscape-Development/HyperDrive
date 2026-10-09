<p align="center">
  <img src="assets/icons/icon.svg" width="128" alt="HyperDrive logo">
</p>

# HyperDrive

A stream helper for fighting game tournaments!

HyperDrive loads sets, players and brackets from your tournament and sends them to
HTML overlays that you add to OBS or any other streaming software as browser sources.

- **Tournament data** from start.gg, plus parry.gg in beta.
- **Scoreboards** for players, teams and commentators, with a stream queue, a bracket
  view and player stats such as recent sets and head-to-head.
- **Crew/team battles** (Stock Pool or First To), with an in-game scoreboard, a roster
  board and a versus screen in [`layout/team_battle`](layout/team_battle).
- **More than 40 layouts** in [`layout/`](layout): scoreboards, brackets, top 8s, versus
  screens, stream queues and maps. They share theme options that you can change from the app.
- **A local player database** that you can edit in the app or from a browser.
- **Player media:** avatars, sponsor logos, team logos and custom player data (a bio, a
  stats file, an image) managed from the Player Database window, or by dropping files in
  `user_data`. The layouts get changes live
  (see [`docs/layout-data.md`](docs/layout-data.md#custom-player-data-custom)).
- **Web pages for your phone or a second screen:** a remote scoreboard, stage strike and
  character select, served by HyperDrive itself.

To show a layout in OBS, add a Browser source with *Local file* checked, pick the
layout's `.html` file in [`layout/`](layout) and set the size to 1920x1080.

## Download (Windows)

1. Download `HyperDrive-windows.zip` from the
   [releases page](https://github.com/Voidscape-Development/HyperDrive/releases).
   The [`latest-build`](https://github.com/Voidscape-Development/HyperDrive/releases/tag/latest-build)
   prerelease is rebuilt on every change to `main`, if you want the newest version.
2. Extract the zip and run `HyperDrive.exe`.

To update, extract the new zip and copy your old `user_data` folder over the new one.
It holds your settings, player database, game assets and logos. HyperDrive doesn't
check for updates yet.

On Linux and macOS, run HyperDrive [from source](#running-from-source).

## Web pages

HyperDrive runs a web server on port 5500, which you can change in the settings. Open
these from any device on the same network at `http://<HyperDrive's address>:5500`:

| Page | What it does |
| - | - |
| `/scoreboard` | Remote scoreboard: scores, players, characters and sets |
| `/stage-strike-app` | Stage strike for the players |
| `/character-select` | Character select for the players |
| `/bracket-focus-app` | What the bracket focus layout zooms to: sets, rounds, a player's run, the set on stream or a tour of the rounds |
| `/admin` | Player database editor |
| `/api/docs` | The web server's endpoints |

## Display Controls

The Display Controls window turns layouts on and off: off plays the layout's hide
animation (its show animation backwards, unless the layout has its own), on plays its show
animation again. What's off stays off when HyperDrive restarts or OBS reloads the source.

- **By layout folder**: every page in `layout/<folder>/` (e.g. `scoreboard`).
- **By group**: add `?display=<group>` (or several, `?display=main,top8`) to a layout's URL
  in OBS, and that page is also turned off with its group. Groups show up in the window
  once a page using them is open, or can be added there by hand.

A page is shown while its folder and all of its groups are on. *Show all* and *Hide all*
turn everything on or off.

The [Stream Deck plugin](#stream-deck-plugin) has a Display Controls action that lights up
while its layout is shown. For other tools (Stream Deck's *Website* or *API Ninja* actions,
Bitfocus Companion), right click an entry to copy its links, or use these (`<action>` is `show`, `hide` or `toggle`):

| Link | |
| - | - |
| `/display/folder/<folder>/<action>` | A layout folder |
| `/display/group/<group>/<action>` | A group |
| `/display/all/<action>` | Everything (`toggle` hides everything if all is shown, otherwise shows everything) |
| `/display/folder/<folder>`, `/display/group/<group>` | `{"kind", "name", "shown"}`, e.g. to light a button |
| `/display/state` | Every folder and group: `{"shown", "folders": {name: shown}, "groups": {...}}` |

Over socket.io, emit `display` with `{"folder" or "group": <name>, "action": <action>}`
(or `{"all": true, "action": ...}`). `display_state` answers the state, and is also sent to
every client whenever something is turned on or off.

## Stream Deck plugin

The HyperDrive plugin for Stream Deck runs HyperDrive from its keys, and they show what's
happening live: the score and team color on a score key, whether a layout is shown, the
active player of a crew battle.

1. Download `HyperDrive.streamDeckPlugin` from the
   [releases page](https://github.com/Voidscape-Development/HyperDrive/releases) (the
   [`latest-build`](https://github.com/Voidscape-Development/HyperDrive/releases/tag/latest-build)
   prerelease has the newest one) and open it to install it.
2. Drag a HyperDrive action onto a key. If HyperDrive runs on another PC, type its address
   (and its port, if you changed it from 5500) at the bottom of the action's settings. Every
   action uses the same address, and the settings say whether it's connected.

It needs Stream Deck 7.1 or newer, on Windows 10 or macOS 12 and up. Keys whose HyperDrive
can't be reached are dimmed with a red badge, and pressing one shows an alert, as does an
action HyperDrive refuses (e.g. nothing to undo).

| Action | Key | Dial (Stream Deck +) |
| - | - | - |
| Team Score | Adds a point (or takes one), holding does the opposite. Shows the team, its score and color | Turn: change the score. Push: swap the teams. Touch: add a point |
| Swap Teams | Swaps the scoreboard's teams | |
| Reset Scoreboard | The scores, the match, the players or everything. Held, so it isn't pressed by mistake | |
| Team Color | Sets a team's color, lit while the team has it | |
| Load Set | The next set of the stream queue (shown on the key), the set on stream, or the set selector | |
| Display Controls | Toggles, shows or hides a layout folder, a group or everything. Lit while shown | Turn: pick the layout. Push or touch: show/hide it |
| Team Battle Score | A team scores (Stock Pool: the other team loses a stock), holding undoes it. Shows the active player | Turn: score or undo. Push or touch: next player |
| Team Battle Player | Makes the next player, or a given one, active | |
| Team Battle Reset | Every player's stocks, or the whole battle. Held | |
| Stage Strike | Undo, redo, restart (held), or the winner of rock-paper-scissors or of the game | |
| Bracket Focus | The whole bracket, next/previous round, the set on a scoreboard, a tour or a player's run, on any focus channel | Turn: next/previous round. Push: follow the scoreboard's set. Touch: whole bracket |

The actions with scoreboards have a scoreboard setting, so one profile can run several
streams. The plugin's code is in [`streamdeck/`](streamdeck).

## Player database

Players are saved in `user_data/players.db`. You can edit them in the Player DB window,
or from a browser at `/admin`. The first time this version runs, it imports any existing
`local_players.json` and renames that file to `local_players.json.bak`. The Player DB
window can still import and export the JSON format.

## Running from source

HyperDrive uses [uv](https://docs.astral.sh/uv/), which installs Python 3.14 and the
dependencies locked in `uv.lock` (the Windows executable is built with Python 3.10, so the
code has to stay compatible with it; `ruff check` flags syntax 3.10 doesn't have):

```sh
uv run main.py
```

`HyperDrive.sh` (Linux and macOS) and `HyperDrive.bat` (Windows) do the same.

The stage strike, character select and remote scoreboard pages are a separate Vite
app in [`stage_strike_app/`](stage_strike_app). Its build is committed, so you only need to
rebuild it if you change it:

```sh
cd stage_strike_app
npm ci
npm run build
```

## Development

```sh
uv run ruff check .    # lint
uv run ruff format .   # format
```

The tests in [`test/`](test) are standalone scripts. Run them from the repository root:

```sh
uv run python test/test_stream_queue.py
```

To work on layouts:

- [`layout/README.md`](layout/README.md) explains how to test layouts in a browser.
- [`docs/layout-data.md`](docs/layout-data.md) describes the data HyperDrive sends to them.

GitHub Actions does the rest:

- `build_app.yml` builds the Windows zip and publishes it as `latest-build`.
- `build_release.yml` turns that build into a versioned release.
- `lint.yml` runs Ruff.
- `update_previews.yml` renders the layout preview images.
- `update_countries.yml` refreshes `assets/countries.json` every week.

## Credits

- Country flags from [hampusborgos/country-flags](https://github.com/hampusborgos/country-flags),
  which are public domain. See [`assets/country_flag/README.md`](assets/country_flag/README.md).

## License

HyperDrive is released under the MIT License. See [`LICENSE`](LICENSE).
