# Web pages

HyperDrive runs a web server, so a phone, a tablet or a second computer on the same network
can help run the stream. Open these at `http://<HyperDrive's address>:5500`:

| Page | What it does |
| - | - |
| `/scoreboard` | Remote scoreboard: scores, players, characters and sets |
| `/stage-strike-app` | Stage strike for the players (see [Stage strike](stage-strike.md)) |
| `/character-select` | Character select for the players |
| `/bracket-focus-app` | What the bracket focus layout zooms to (see [Bracket](bracket.md#bracket-focus)) |
| `/commentary-dashboard` | For the commentators: the players, their stats and what's up next (see [Commentary](commentary.md#commentary-dashboard)) |
| `/admin` | Player database editor (see [Player database](player-database.md)) |
| `/wiki` | This guide |
| `/api/docs` | Every endpoint of the web server, for developers |

## Finding HyperDrive's address

The Scoreboard and Stage tabs show the full links with the address filled in, e.g.
`http://192.168.1.20:5500/scoreboard`. Click one to open it, or type it on the other
device.

The device must be on the same network as HyperDrive's computer. If the page doesn't load,
see [Troubleshooting](troubleshooting.md#web-pages-dont-load-on-another-device).

## Pages for one scoreboard or one team

- Add `?scoreboard=2` to work on scoreboard 2. The stage strike, character select and
  commentary dashboard pages are then locked to it; without it, they let you pick a
  scoreboard and remember it.
- Add `&team=1` or `&team=2` to the stage strike page to give each team its own device.

## Changing the port

The port is 5500 unless you change it in
[Settings › General](hyperdrive://open/settings/general) (*Webserver Port*), which takes
effect when HyperDrive restarts. Use the new port in every link, in the
[Stream Deck](stream-deck.md) settings, and for layouts you load by URL.
