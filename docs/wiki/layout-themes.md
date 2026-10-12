# Layout themes

A layout theme is the colors, fonts and display options the layouts share, so you can change
the look of every layout at once without editing them, and switch or share whole looks.

Open it from ☰ › [Layout themes](hyperdrive://open/layout-themes).

## Making your own theme

The built-in **Default** theme can't be changed. Click **New theme…** to start a theme from
the one in use, then change anything: changes are saved and sent to the layouts as you make
them, so you can watch them in OBS.

| Section | What it changes |
| - | - |
| General | Whether layouts use the theme's colors at all, the primary, secondary and text colors, the background (a color or a gradient), the font, the text case, the text outline and corner roundness |
| Animations | Whether changes animate, and how fast |
| Teams | Each team's color and score text color |
| Player chips | What the boxes with a player's name show (pronouns, seed, socials, flags, avatar, the losers [L] badge) and their colors |
| Bracket, Standings | What the bracket layouts show: avatars, characters, flags, seeds, round names, set letters |
| Stage strike, Stream queue | Those layouts' options |
| Event stats, Schedule, League standings | How many characters, upsets or players to show, and what's displayed |
| Versus | Custom sponsor colors on versus screens |

**Layout default** (e.g. for the font or text case) means each layout keeps its own.

## Sharing themes

- **Export…** saves the theme in use to a file.
- **Import…** loads a theme someone shared.
- **Rename…** and **Delete** manage your themes.

Themes are saved in `user_data/layout_themes.json`.

## For layout makers

The theme in use is sent to the layouts as `layout_theme`, with ready-to-use CSS custom
properties. See [Making layouts](making-layouts.md).

> Looking for the colors of HyperDrive's own window? That's
> [Settings › Appearance](hyperdrive://open/settings/appearance).
