# Web reporting

HyperDrive can run your event's reporting from a browser. Admins report sets to start.gg
right away. Players report their own sets at a **reporting station**, and an admin
approves each result before it's reported. It works with start.gg events, using the
start.gg API token from
[Settings › API Keys](hyperdrive://open/settings/api-keys) (from an account that's an
admin of the tournament, as for [reporting from the scoreboard](games-and-reporting.md)).

There are three pages. Each one is in the [dashboard](web-pages.md#the-dashboard)'s
sidebar, under *start.gg reporting*, and also has its own address:

| Page | Address | For |
| - | - | - |
| Reporting | `/report-admin` | Admins: every set, reported or changed right away |
| Approval | `/report-approval` | Admins: the results players sent, to approve or reject |
| Player reporting | `/report` | Players, at a reporting station |

## Reporting (admins)

Every set of the loaded event, as start.gg has it. **List** shows them in rows, with
filters by state (*Not completed* by default), phase and station, and a search by player
or set code (e.g. `A1 C`, the pool and the set's letter). **Stations** shows a card per
start.gg station with the set it's playing and the next ones, and the sets ready to play
that don't have a station.

Each set has a button for its next step: **Call**, **Start** (mark it in progress), or
**Report**. Its **⋯** menu has everything else:

| Action | What it does on start.gg |
| - | - |
| Mark as called / Mark as in progress | Changes the set's state |
| Report or update score… | Opens the set's games (as start.gg has them) to change: who won each game, and the characters and stages if you want. **Report** ends the set, **Send as update** only sends the games so far |
| Report a DQ… | The other player wins, without games |
| Assign to a station… / Assign to a stream… | Moves the set there |
| Reset on start.gg… | Clears the set's result and games. Sets that depend on it are reset too |

Changes are sent right away, without asking first. Only resetting asks, and so does
reporting a set that's already completed, since that resets it first.

The sets are fetched from start.gg every 30 seconds while a page is open (all of them every
10 minutes, and in between only the ones that changed), or now with **Update from
start.gg**.

## Approval (admins)

Results sent from reporting stations wait here, oldest first. The sidebar shows how many
are waiting, and the dashboard says when a new one arrives. Each result shows its score,
games, the station it came from, and when.

- **Approve and report** reports it to start.gg.
- **Edit…** changes the games first, e.g. a wrong character, then approves.
- **Reject** drops it. A reason is optional and kept in the log.

A result is marked when something changed since it was sent:

- **Another result was sent for this set**: approving one drops the others.
- **Already completed on start.gg**: approving it resets the set first, after asking.
- **The set's players changed on start.gg**: it can only be rejected.

**Done** lists the results approved or rejected, and **Log** lists everything reported from
the web pages, by whom (with the device's address) and whether start.gg accepted it.

Results and the log are kept in `user_data/web_reporting.json`, so they're still there
after HyperDrive restarts.

## Player reporting (reporting stations)

Put a tablet or a laptop at the TO desk or by the setups, and open
`http://<HyperDrive's address>:5500/report`. Players find their set by typing their name or
the set's code, or pick it from the sets being played. They then set who won each game (or
tap the final score), optionally with characters and stages, and send it. Only sets with
both players known and not completed yet are shown.

Results sent from a station are never reported to start.gg before an admin approves them.

The ⚙ at the top sets the station up, in that browser:

- **Name**: shown to the admins with each result, e.g. *TO desk*.
- **start.gg station number**: that station's sets are shown first.

A link sets it up too: `/report?station=5&name=Setup%205`.

## Settings

In [Settings › Web Reporting](hyperdrive://open/settings/web-reporting):

| Setting | |
| - | - |
| Accept results from player reporting stations | Off: `/report` sends nothing |
| Reporting station PIN | Asked once by each station's browser, then remembered. Empty: no PIN |
| Get the sets from start.gg every (seconds) | While a reporting page is open. At least 10 |

The admin pages use the dashboard's PIN from
[Settings › General](hyperdrive://open/settings/general). Without one, anyone on your
network can open them. Set a dashboard PIN when players can reach HyperDrive's address. The
station PIN only lets a device send results for approval.
