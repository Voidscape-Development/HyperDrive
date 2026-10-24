# Adding layouts to OBS

Layouts are web pages in HyperDrive's `layout` folder. Each one shows part of what you set
in HyperDrive (a scoreboard, a bracket, a top 8…) and updates live.

## Add a layout

1. In OBS, add a **Browser** source to your scene.
2. Check **Local file** and pick the layout's `.html` file in `layout/`.
3. Set the width to **1920** and the height to **1080**.

Every layout is drawn for 1920x1080. Scale the source in OBS if your canvas is different.

## Layouts with options: use a URL

Some options go in the layout's URL, after a `?`. OBS's *Local file* mode can't add them,
so leave **Local file** unchecked and type a URL instead, served by HyperDrive's web server:

```
http://127.0.0.1:5500/layout/scoreboard_simple/index.html?scoreboardNumber=2
```

| Option | What it does |
| - | - |
| `?scoreboardNumber=2` | Shows scoreboard 2 instead of 1 (see [Scoreboard](scoreboard.md#several-scoreboards)) |
| `?display=main` | Puts the page in a display group, to hide it with the group (see [Display controls](display-controls.md)) |
| `?channel=TV 1` | Bracket layouts: shows a bracket channel other than the main one (see [Bracket](bracket.md#channels)) |

Join several with `&`: `?scoreboardNumber=2&display=side`. If you changed the web server's
port in [Settings › General](hyperdrive://open/settings/general), use it instead of 5500. If
OBS runs on another computer, use HyperDrive's computer's address instead of `127.0.0.1`.

## Which layout for what

| Folder | Shows |
| - | - |
| `scoreboard`, `scoreboard_*` | In-game scoreboards. `scoreboard/` has one per game (`sf6_offline.html`, `ssbultimate.html`…) |
| `scoreboard_4by3`, `scoreboard_4by3_oneside` | Scoreboards for 4:3 games such as Melee and Smash 64 |
| `scoreboard_team_versus`, `team_battle` | Doubles and crew battles (see [Crew/team battle](team-battle.md)) |
| `versus_screen*` | A versus screen between games |
| `player_presentation`, `character_gallery`, `character_line` | Player intros and characters |
| `commentators` | Commentator names and socials (see [Commentary](commentary.md)) |
| `socials` | Lower thirds with a player's or the commentators' social media accounts, taking turns |
| `stage_strike`, `stage_strike_display` | The stage strike as it happens (see [Stage strike](stage-strike.md)) |
| `ruleset` | The ruleset's stage list, also printable |
| `bracket`, `bracket_ultimate`, `bracket_focus` | Brackets, standings and a zooming bracket (see [Bracket](bracket.md)) |
| `top_8`, `top_8_single_elim`, `top_8 - StationSquare`, `top_n_list` | Final results (see [Player list](player-list.md)) |
| `stream_queue`, `stream_queue_simple` | Upcoming sets (see [Stream queue](stream-queue.md)) |
| `completed_sets` | Sets that just finished: a ticker, a list, a full-screen scrolling list (for a vertical stream or a venue screen) or cards, and an alert for upsets (`upset_alert.html`) |
| `game_log` | The set's games so far: stages, characters and who won each, as a strip, a column or a full screen recap |
| `last_sets`, `recent_sets`, `recent_sets_full`, `tournament_history` | Player stats: recent sets, head-to-head and past results |
| `tale_of_the_tape` | Both players' stats face to face before their set: seeds, head-to-head, finishes and last meetings |
| `starting_soon` | Starting soon and be right back screens: a countdown, the next sets on stream and the latest results |
| `map`, `map_world_fighters` | Where the players come from |

Each layout folder has a `_preview.png` next to every page, so you can see what it looks
like before adding it.

## Hiding and showing layouts

Use [Display controls](display-controls.md) to play a layout's hide and show animations
from HyperDrive or a Stream Deck, instead of toggling sources in OBS.

## Changing the look

Colors, fonts and animation options shared by the layouts are in
[Layout themes](layout-themes.md). To change a layout itself, see
[Making layouts](making-layouts.md).
