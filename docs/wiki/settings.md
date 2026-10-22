# Settings

Open ☰ › [Settings](hyperdrive://open/settings). Each page is listed on the left; click a
link below to open it directly.

## [General](hyperdrive://open/settings/general)

| Setting | |
| - | - |
| Webserver Port | The port of HyperDrive's [web pages](web-pages.md) (5500). Takes effect on restart |
| Web dashboard PIN | Locks the [web dashboard](web-pages.md#locking-the-dashboard) behind a PIN. Empty: no PIN |
| Enable profanity filter | Masks offensive words in the tags, sponsors, names and handles of players loaded from a tournament |
| Completed sets auto pull interval | How often **Auto pull** pulls completed sets |
| Bracket auto update interval | How often the [bracket](bracket.md)'s **Auto update** runs |
| Export custom player data | Sends players' [custom data](player-database.md#player-media) to the layouts |
| Crew/Team Battle starting stocks / games to win | Defaults for [crew battles](team-battle.md) |

## [Appearance](hyperdrive://open/settings/appearance)

HyperDrive's own look: **Dark**, **Light** or **Follow system**, the **Accent color**, the
**UI scale** (on restart), and custom themes with your own colors, corner roundness, spacing
and font. Also the **Default team colors** of the scoreboard.

Ready-made themes are listed under the first three: **Midnight**, **Graphite** and **OLED
Black** (dark), **Synthwave** and **Forest** (colorful dark), **Paper** and **Soft Blue**
(light), and **High Contrast Dark** and **High Contrast Light**. They come with their own
accent and can't be changed: pick one and click **New custom theme…** to make your own from it.

## [Scoreboard](hyperdrive://open/settings/scoreboard)

How the [scoreboard](scoreboard.md) follows start.gg: score control from the stage strike
page, whether that page asks for each game's characters, automatic set and score updating
and its interval, keeping your characters when a set loads, and using your local player
database for player info.

## [State Manager](hyperdrive://open/settings/state-manager)

For troubleshooting: logs every change of the data sent to layouts, and can turn off writing
it to the `out/` folder.

## [Default Display Options](hyperdrive://open/settings/display-options)

Which fields player cards show by default (real name, socials, seed, birthday, location,
characters, pronouns, additional information), and compact cards for players and
commentators.

## [Character Select](hyperdrive://open/settings/character-select)

Whether the character grid shows the player's mains and recent picks on top.

## [Match & Phase Names](hyperdrive://open/settings/match-names)

Rename the match and phase names in the scoreboard's dropdowns and in sets loaded from
start.gg, e.g. *Grand Finals* to *GF*, and add extra names. `{0}` is replaced with a number
or letter, like the round number.

## [Pronouns](hyperdrive://open/settings/pronouns)

The pronouns offered in a player's pronouns field. Pronouns of players you save are added
automatically.

## [API Keys](hyperdrive://open/settings/api-keys)

| Key | Needed for |
| - | - |
| ParryGG | Loading parry.gg tournaments |
| start.gg (reporting sets) | [Reporting sets](games-and-reporting.md), calling sets and assigning streams. From an admin of the tournament |
| Twitch (predictions) | [Twitch predictions](twitch-predictions.md) |

Keys are stored in plain text in `user_data/settings.json`. Don't share that file.

## [start.gg Reporting](hyperdrive://open/settings/startgg-reporting)

See [Games and reporting](games-and-reporting.md#reporting-settings).

## [Twitch Predictions](hyperdrive://open/settings/twitch-predictions)

See [Twitch predictions](twitch-predictions.md).

## Languages

HyperDrive's language, the game assets' language and the tournament terms' language are in
the ☰ menu, not in the settings.
