# Making layouts

A layout is an HTML page in `layout/<folder>/` that shows HyperDrive's data. The easiest way
to start is to copy a layout close to what you want, e.g. `layout/scoreboard_simple/`, and
change it.

## How a layout gets its data

Layouts include `layout/include/globals.js` and call `LoadEverything()`. It connects to
HyperDrive's web server with socket.io and calls the functions your page defines:

- `Update(event)`: each time something changes. `event.data` is everything HyperDrive sends
  (the *program state*), `event.oldData` what it was before, to animate only what changed.
- `Start()`: once, after the first update: the layout's show animation.
- `Hide()` (optional): the hide animation for [display controls](display-controls.md). By
  default the show animation plays backwards.

If the web server can't be reached, `globals.js` falls back to reading
`out/program_state.json`, which HyperDrive also writes.

`layout/include/` also has the libraries the layouts use: gsap for animations, jQuery and
lodash, and helpers such as `bracket.js` for brackets.

## What's in the data

The full reference is
[docs/layout-data.md](https://github.com/Voidscape-Development/HyperDrive/blob/main/docs/layout-data.md)
in HyperDrive's repository. The main parts:

| Key | |
| - | - |
| `score.N` | Scoreboard N: its teams, players, characters, score, phase, match, best of, games and stage strike |
| `commentary` | The commentators |
| `tournamentInfo` | The [tournament info](tournament-info.md), logo and banner |
| `player_list` | The [player list](player-list.md) (top 8s) |
| `bracket` | The [bracket](bracket.md): channels, phases, sets, standings and focus |
| `stream_queue` | The [stream queue](stream-queue.md) |
| `completed_sets` | Recent results |
| `team_battle` | The [crew battle](team-battle.md) |
| `layout_theme` | The [layout theme](layout-themes.md) in use, with CSS custom properties |
| `display` | What [display controls](display-controls.md) have turned off |

To see the real data, open `http://127.0.0.1:5500/program-state` in a browser.

## URL options

Anything after `?` in the layout's URL becomes a global variable in the page:
`?scoreboardNumber=2` sets `window.scoreboardNumber` (1 by default). `?display=` is handled
by `globals.js`, and `?channel=` by `bracket.js`.

## Testing a layout in a browser

Opening a layout from disk in Chrome needs a flag:

1. Start Chrome with `--allow-file-access-from-files`.
2. Open the layout's `.html` file and press F12.
3. Turn on the device toolbar and set the size to 1920x1080.

Or open it through the web server, which needs no flag:
`http://127.0.0.1:5500/layout/<folder>/<page>.html`.

## Theme colors

Use the CSS custom properties of `layout_theme` instead of fixed colors, so your layout
follows the user's [layout theme](layout-themes.md).

## Preview images

Each page's `<page>_preview.png` is rendered by a GitHub Action when a layout changes on
`main`, from the sample data in `scripts/previews`.
