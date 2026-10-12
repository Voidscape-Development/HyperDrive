# The main window

HyperDrive's window has a bar at the top and a set of tabs (*widgets*) below it.

## The top bar

| Control | What it does |
| - | - |
| **Set tournament** | Loads a tournament from start.gg or parry.gg (see [Tournaments](tournaments.md)) |
| **Select event** | Switches to another event of the same tournament |
| **Repull entrants** | Pulls the event's players again, for those who registered after it was loaded |
| ✕ | Unloads the tournament |
| **Pull Latest Completed Sets from StartGG** | Pulls the sets that just finished, for the `completed_sets` layouts. **Auto pull** does it periodically |
| Game dropdown | The game being played. It sets the characters, stages and icons. ⟳ reloads its assets |
| **Modded content** | Shown for games with modded characters: includes them |
| **Number of Scoreboards** | How many scoreboards to run, for several streams or stations (see [Scoreboard](scoreboard.md#several-scoreboards)) |
| **Modify Tab Name** | Renames a scoreboard's tab |
| ☰ | The menu (see below) |

## The widgets

Each widget is a tab. Drag a tab out to make it a separate window, or next to another to see
both at once. HyperDrive remembers where you put them.

| Widget | Read |
| - | - |
| [Scoreboard Manager](hyperdrive://open/scoreboard) | [Scoreboard](scoreboard.md) |
| [Stage](hyperdrive://open/stage-strike) | [Stage strike](stage-strike.md) |
| [Commentary](hyperdrive://open/commentary) | [Commentary](commentary.md) |
| [Tournament Info](hyperdrive://open/tournament-info) | [Tournament info](tournament-info.md) |
| [Player List](hyperdrive://open/player-list) | [Player list](player-list.md) |
| [Bracket](hyperdrive://open/bracket) | [Bracket](bracket.md) |
| [Stream Queue](hyperdrive://open/stream-queue) | [Stream queue](stream-queue.md) |
| [Display Controls](hyperdrive://open/display-controls) | [Display controls](display-controls.md) |
| [Crew/Team Battle](hyperdrive://open/team-battle) | [Crew/team battle](team-battle.md) |

Closed a widget by mistake? Bring it back from ☰ › **Toggle widgets**.

## The menu (☰)

| Item | What it does |
| - | - |
| **Always on top** | Keeps HyperDrive above other windows |
| **Download assets** | Character and stage icons for your games (see [Game assets](game-assets.md)) |
| **Player database** | Your saved players (see [Player database](player-database.md)) |
| **Seed editor** | Seeds set by hand (see [Player database](player-database.md#seeds)) |
| **Toggle widgets** | Shows or hides each widget |
| **Layout themes** | Colors, fonts and options shared by the layouts (see [Layout themes](layout-themes.md)) |
| **Migrate Layout** | Updates the JavaScript of a custom layout made before HyperDrive had several scoreboards |
| **Program Language** | HyperDrive's language (needs a restart) |
| **Game Asset Language** | The language of character and stage names |
| **Tournament term language** | The language of round names such as *Winners Finals* |
| **Help** | This guide, bug reports and the asset database |
| **Settings** | See [Settings](settings.md) |
| **About** | The version, and links to the source code and releases |
