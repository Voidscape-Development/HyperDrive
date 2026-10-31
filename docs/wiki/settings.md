# Settings

Open ☰ › [Settings](hyperdrive://open/settings). The pages are listed on the left in four
groups; click a link below to open one directly. **Search settings** at the top (Ctrl+F)
finds any setting by its name or description and takes you to it.

Changes are saved as you make them. A dot before a setting means it isn't at its default;
the ↶ button next to it puts the default back. Settings marked **Restart** take effect when
HyperDrive restarts: a banner offers to restart it for you.

## HyperDrive

### [General](hyperdrive://open/settings/general)

| Setting | |
| - | - |
| Profanity filter | Masks offensive words in the tags, sponsors, names and handles of players loaded from a tournament |
| Pull completed sets every | How often **Auto pull** pulls completed sets |
| Update the bracket every | How often the [bracket](bracket.md)'s **Auto update** runs |

### [Appearance](hyperdrive://open/settings/appearance)

HyperDrive's own look. Pick a theme from the cards: **Dark**, **Light**, **Follow system**,
then the ready-made themes, **Midnight**, **Graphite** and **OLED Black** (dark),
**Synthwave** and **Forest** (colorful dark), **Paper** and **Soft Blue** (light), and **High
Contrast Dark** and **High Contrast Light**, then your own themes.

- **Accent color** (Dark, Light and Follow system): pick one of the swatches or any color.
- **Interface size** (on restart).
- **New from current** makes your own theme from the one in use, with your own colors,
  corner roundness, spacing and font. Right-click your theme's card to rename or delete it.
  **Import…** and **Export…** share themes as files.
- **Team colors for new sets**: the scoreboard's starting team colors.

### [Web pages & PIN](hyperdrive://open/settings/web-pages)

| Setting | |
| - | - |
| Web server port | The port of HyperDrive's [web pages](web-pages.md) (5500). Takes effect on restart |
| Web dashboard PIN | Locks the [web dashboard](web-pages.md#locking-the-dashboard) behind a PIN. Empty: no PIN |

## On stream

### [Scoreboard](hyperdrive://open/settings/scoreboard)

How the [scoreboard](scoreboard.md) follows start.gg: automatic set and score updates and how
often they run, filling in characters when a set loads, the wait before a tracked stream's
next set, what players can do from the stage strike page, and using your local player
database for player info.

### [Player cards](hyperdrive://open/settings/display-options)

Which fields new player cards show (real name, socials, seed, birthday, location,
characters, pronouns, additional information), and compact cards for players and
commentators.

### [Character select](hyperdrive://open/settings/character-select)

Whether the character grid shows the player's mains and recent picks on top.

### [Crew battles](hyperdrive://open/settings/crew-battles)

The starting stocks (Stock Pool) and games to win a matchup (First To) of new
[crew battles](team-battle.md).

### [Match & phase names](hyperdrive://open/settings/match-names)

Rename the match and phase names in the scoreboard's dropdowns and in sets loaded from
start.gg, e.g. *Grand Finals* to *GF*, and add extra names. `{0}` is replaced with a number
or letter, like the round number.

### [Pronouns](hyperdrive://open/settings/pronouns)

The pronouns offered in a player's pronouns field. Pronouns of players you save are added
automatically.

## Connections

### [API keys](hyperdrive://open/settings/api-keys)

| Key | Needed for |
| - | - |
| parry.gg | Loading parry.gg tournaments |
| start.gg token | [Reporting sets](games-and-reporting.md), calling sets and assigning streams. From an admin of the tournament |

Each shows **Set** or **Not set**; the eye button shows what you typed. Keys are stored in
plain text in `user_data/settings.json`. Don't share that file.

### [start.gg reporting](hyperdrive://open/settings/startgg-reporting)

See [Games and reporting](games-and-reporting.md#reporting-settings).

### [Web reporting](hyperdrive://open/settings/web-reporting)

See [Web reporting](web-reporting.md#settings).

## Advanced

### [Data & file export](hyperdrive://open/settings/data)

| Setting | |
| - | - |
| Send custom player data to the layouts | Sends players' [custom data](player-database.md#player-media) to the layouts |
| Write the layouts' data to the out folder | For other software that reads HyperDrive's files |
| Log every change of the layouts' data | For troubleshooting |

## Languages

HyperDrive's language, the game assets' language and the tournament terms' language are in
the ☰ menu, not in the settings.
