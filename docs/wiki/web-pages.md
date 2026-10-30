# Web pages

HyperDrive runs a web server, so a phone, a tablet or a second computer on the same network
can help run the stream. Open these at `http://<HyperDrive's address>:5500`:

| Page | What it does |
| - | - |
| `/` | The dashboard: everything HyperDrive does, from a browser (see below) |
| `/scoreboard` | The dashboard's scoreboard on its own, full screen |
| `/stage-strike-app` | Stage strike for the players (see [Stage strike](stage-strike.md)) |
| `/character-select` | Character select for the players |
| `/bracket-focus-app` | What the bracket focus layout zooms to (see [Bracket](bracket.md#bracket-focus)) |
| `/commentary-dashboard` | For the commentators: the players, their stats and what's up next (see [Commentary](commentary.md#commentary-dashboard)) |
| `/report` | A reporting station: players send their sets' results (see [Web reporting](web-reporting.md)) |
| `/report-admin`, `/report-approval` | Reporting sets to start.gg, and approving the players' results (see [Web reporting](web-reporting.md)) |
| `/admin` | Player database editor (see [Player database](player-database.md)) |
| `/wiki` | This guide |
| `/api/docs` | Every endpoint of the web server, for developers |

## The dashboard

`http://<HyperDrive's address>:5500` opens the dashboard, which runs the event from a
laptop, a tablet or a phone. It looks like HyperDrive, in the theme picked in
[Settings › Appearance](hyperdrive://open/settings/appearance).

The sidebar on the left has:

- **Event**: the tournament (click it to switch events, repull the entrants, load another
  tournament or unload it), the game, and the completed sets (**Auto pull** and ⟳ to pull
  now). Changes show up in HyperDrive right away.
- **Overview**: the set on stream with its score, what's up next, which layouts are shown,
  the latest results, the commentators and the tournament.
- A section for each of HyperDrive's tabs: Scoreboard, Stage strike, Character select,
  Commentary, Display Controls, Crew/Team Battle, Stream Queue, Bracket, Bracket focus, Player
  List and Tournament Info.
- **start.gg reporting**: Reporting, Approval and Player reporting (see
  [Web reporting](web-reporting.md)).

The eye next to a section hides it in this browser only, e.g. so a commentator's tablet
shows just Commentary. **Ctrl+B** collapses the sidebar to icons. On a phone, ☰ opens it.

The **Scoreboard** section has a tab per scoreboard: double-click a tab to rename it,
**+ Scoreboard** adds one and **−** removes the last. Q and P add a point to the left and
right team (Shift takes one away), and S swaps them.

Some things stay in HyperDrive itself: building brackets by hand, editing rulesets,
players' media files, and workspaces.

### Locking the dashboard

Anyone on your network can open the dashboard. To lock it, set a **Web dashboard PIN** in
[Settings › Web pages & PIN](hyperdrive://open/settings/web-pages): each browser then asks for it
once and remembers it, until the PIN changes or someone clicks the lock at the bottom of
the sidebar. After five wrong PINs, a device has to wait 30 seconds.

The PIN locks the dashboard, `/scoreboard`, `/report-admin` and `/report-approval`. The
players' pages (stage strike, character select, and `/report`, which has its own PIN), the
commentary dashboard and the links a [Stream Deck](stream-deck.md) or other tools use
([Remote control](remote-control.md)) stay open, so they keep working.

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
[Settings › Web pages & PIN](hyperdrive://open/settings/web-pages) (*Web server port*), which takes
effect when HyperDrive restarts. Use the new port in every link, in the
[Stream Deck](stream-deck.md) settings, and for layouts you load by URL.
