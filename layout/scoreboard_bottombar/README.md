# Bottom bar scoreboard

A full-width bar along the bottom of the screen (1920x140):

- The tournament's logo, name, phase and best of, and the match
- Each side's sponsor and name, location flag and score, in the team colors
- Their character art meeting at a VS in the middle
- A clock with the time zone

Under each name the location stays, and the handle, pronouns and seed take
turns every 6 seconds. In doubles the team's name shows, with its players
under it when it has a name. When a score changes it pops.

## Settings

Set them in this folder's `settings.json`, or in the page's URL
(`index.html?show_clock=false&clock_24h=true`).

| Setting | Default | |
| - | - | - |
| `show_clock` | `true` | Show the clock |
| `clock_24h` | `false` | 24-hour clock (`15:42`) instead of `03:42pm` |
| `clock_timezone` | `""` | An IANA time zone, e.g. `America/New_York`. Empty uses the computer's |
| `set_length` | `"best_of"` | `"best_of"` (Best of 3) or `"first_to"` (First to 2) |
| `location_flag` | `"auto"` | `"auto"` (the state's, else the country's), `"state"`, `"country"` or `"both"` |
| `show_twitter`, `show_pronoun`, `show_seed` | `true` | What takes turns under the name. The layout theme's display options hide them too |
| `use_tournament_logo` | `true` | The start.gg tournament's logo when it has one, else `layout/logo.png` |

The layout theme's colors, font and animation speed apply as in the other
layouts.
