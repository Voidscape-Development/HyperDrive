# Remote control

Everything HyperDrive's [web pages](web-pages.md) and the [Stream Deck plugin](stream-deck.md)
do goes through its web server, so other tools can do it too: Bitfocus Companion, Stream
Deck's *Website* or *API Ninja* actions, a producer's script, a bot.

The full list of endpoints, with their parameters, is at
`http://<HyperDrive's address>:5500/api/docs`.

## Simple links

These are GET requests, so they work from any "open a website" button. `N` is the
scoreboard's number and `T` the team (1 or 2).

| Link | What it does |
| - | - |
| `/scoreboardN-teamT-scoreup`, `/scoreboardN-teamT-scoredown` | Adds or takes a point |
| `/scoreboardN-teamT-color-<color>` | Sets a team's color, as hex without the `#`, e.g. `-color-fe3636` |
| `/scoreboardN-swap-teams` | Swaps the teams |
| `/scoreboardN-reset-scores`, `-reset-match`, `-reset-players`, `-clear-all` | Resets part of the scoreboard |
| `/scoreboardN-load-set?set=<id>` | Loads a set |
| `/scoreboardN-get` | The scoreboard's data |
| `/scoreboardN-stats-refresh` | Gets the players' stats again: head-to-head, last sets, past events and upset factor |
| `/stream-queue/load-next?stream=<name>` | Loads a stream's next set into its scoreboard |
| `/display/...` | Shows or hides layouts (see [Display controls](display-controls.md)) |
| `/team-battle-teamT-scoreup`, `/team-battle-teamT-next-player` | Crew battles |
| `/program-state` | Everything HyperDrive sends to the layouts, as JSON |
| `/layouts` | The layout pages: `{"layouts": [{"folder", "pages": [{"name", "path", "preview"}]}]}`, where `path` and `preview` (the page's `_preview.png`, or `null`) go after the server's address |

## socket.io

Layouts and HyperDrive's own pages use socket.io on the same port. After connecting, the
server sends `program_state` (everything) and then `program_state_update` (only what
changed) on each change.

Clients can emit the same actions as the links, with JSON: e.g. `team_scoreup` with
`{"scoreboardNumber": 1, "team": 1}`, `swap_teams`, `load_set`, `display`,
`bracket_focus`, `stage_strike_undo`. Each is answered with an event of the same name.

## Layout data

What's in the program state, key by key, is described in `docs/layout-data.md` in
HyperDrive's repository. See [Making layouts](making-layouts.md).

> The web server has no password: anyone on your network can use it. Don't expose port
> 5500 to the internet.
