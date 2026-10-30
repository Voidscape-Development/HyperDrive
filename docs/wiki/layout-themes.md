# Layout themes

A layout theme is the colors, fonts and display options the layouts share, so you can change
the look of every layout at once without editing them, and switch or share whole looks.

Open it from ☰ › [Layout themes](hyperdrive://open/layout-themes). Your themes and the
built-in ones are listed on the left; click one to use it. The theme's options are in the
middle, in sections, and a **Preview** on the right draws a scoreboard, bracket, stage
strike, stream queue, standings or versus screen in the theme as you change it (click a
small one under it to see it big). It's an approximation: your layouts in OBS update live too.

## Built-in themes

**Default** leaves every layout looking as it was made. The others give all the layouts a
shared look to get started quickly:

| Theme | Look |
| - | - |
| Esports Neon | Dark purple with neon cyan and magenta, gradients, square corners, UPPERCASE, quick animations |
| Clean Minimal | Slate and soft indigo, rounded corners, no text outline, text as typed, calmer animations |
| Classic Broadcast | Navy and gold, a TV sports look in Roboto Condensed and UPPERCASE |
| Daytime | Light backgrounds with dark text and blue highlights, rounded corners |

They only change colors, fonts, corners and animations, never what the layouts show
(avatars, seeds, pronouns, flags...), so switching between them never hides anything.

## Making your own theme

Built-in themes stay as they are: change any option of one and HyperDrive makes it your own
copy (e.g. *Esports Neon (custom)*) and switches to it, with **Undo** to go back. **Customize
a copy** does the same without changing anything, and **+** or **Duplicate** start a new
theme from the one in use. Changes are saved and sent to the layouts as you make them, so you
can watch them in OBS.

**Use this theme's colors, fonts and corners in layouts**, at the top, decides whether the
layouts take the theme's colors at all. While it's off, the options that need it are dimmed
and each layout keeps its own look; what's shown and the animations still apply.

**Find an option in any section** (Ctrl+F) leaves only the options that match. A dot before
an option means it isn't at its default; ↶ next to it puts the default back.

| Section | What it changes |
| - | - |
| General | The primary, secondary and text colors, the background (a color or a gradient), the font, the text case, the text outline and corner roundness |
| Animations | Whether changes animate, and how fast |
| Teams | Each team's color and score text color |
| Player chips | What the boxes with a player's name show (pronouns, seed, socials, flags, avatar, the losers [L] badge) and their colors |
| Bracket, Standings | What the bracket layouts show: avatars, characters, flags, seeds, round names, set letters, and the bracket focus layout's highlight, dimming, zoom and caption. The **Focus glow** table turns the outline and glow around the sets in focus on or off for each focus mode (Ctrl+click selection, round mode, winners/losers side, player's run, followed set, tour), and its **Color** is the **Focus highlight** or that mode's **Own color** |
| Stage strike, Stream queue | Those layouts' options |
| Versus | Custom sponsor colors on versus screens |

**Layout default** (e.g. for the font or text case) means each layout keeps its own.

A background that can be a gradient (**Gradient** checked) takes a second color, a direction
and a **%**: where the two colors meet, from the first color's side. 50% is an even blend;
lower keeps the first color close to its side, higher spreads it further across.

## Sharing themes

- **Export…** saves the theme in use to a file.
- **Import…** loads a theme someone shared.
- ✎ next to the name renames your theme, and ⊗ deletes it. Right-click a theme in the list
  for the same.

Themes are saved in `user_data/layout_themes.json`.

## For layout makers

The theme in use is sent to the layouts as `layout_theme`, with ready-to-use CSS custom
properties. See [Making layouts](making-layouts.md).

> Looking for the colors of HyperDrive's own window? That's
> [Settings › Appearance](hyperdrive://open/settings/appearance).
