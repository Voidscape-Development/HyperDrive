# Bottom bar scoreboard

A scoreboard along the bottom of the screen, top to bottom:

- A pill with the tournament's name
- The bar: each side's name and info at its ends, then their character art and
  score, with the tournament's logo and a clock (with the time zone) between
  the scores
- A thinner bar with the phase, match and best of

`index.html` spans the full width, its bars resting on the bottom edge.
`inset.html` floats 24px above and in from the edges, with rounded corners.

Under each name the location stays, and the handle, pronouns and seed take
turns every 6 seconds. In doubles the team's name shows, with its players
under it when it has a name. A player with several characters shows them
one at a time, crossfading every 4 seconds; in doubles each player's first
character shows side by side. When a score changes it pops.

## Settings

Set them in this folder's `settings.json`, or in the page's URL
(`index.html?show_clock=false&clock_24h=true`).

| Setting | Default | |
| - | - | - |
| `info_layout` | `"spread"` | The bottom bar: `"spread"` (phase left, match centered, best of right), `"center"` (one centered line) or `"chips"` (a centered chip each) |
| `show_clock` | `true` | Show the clock under the logo |
| `clock_24h` | `false` | 24-hour clock (`15:42`) instead of `03:42pm` |
| `clock_timezone` | `""` | An IANA time zone, e.g. `America/New_York`. Empty uses the computer's |
| `set_length` | `"best_of"` | `"best_of"` (Best of 3) or `"first_to"` (First to 2) |
| `location_flag` | `"auto"` | `"auto"` (the state's, else the country's), `"state"`, `"country"` or `"both"` |
| `show_twitter`, `show_pronoun`, `show_seed` | `true` | What takes turns under the name. The layout theme's display options hide them too |
| `character_cycle_seconds` | `4` | How long each of a player's characters shows. `0` shows them side by side |
| `use_tournament_logo` | `true` | The start.gg tournament's logo when it has one, else `layout/logo.png` |

The layout theme's colors, font and animation speed apply as in the other
layouts.
