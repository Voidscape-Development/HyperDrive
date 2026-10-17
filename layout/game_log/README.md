# Game log

The games of the set on the scoreboard, from the scoreboard's Games window
(`score.N.games`): a card per game with its stage, both sides' characters,
who won (in their team color along the bottom, the loser's characters faded)
and the score after it. The game being played is outlined in the accent
color, and the games left to play are outlined. A game just won pops.

| Page | |
| - | - |
| `strip.html` | A row of cards at the bottom center |
| `column.html` | A column of cards at the left |
| `recap.html` | Full screen, between games: the names and score, a big card per game with the stage's picture and the characters' art, and each character's games won and lost in the set |

Stages and characters show once they're set in the Games window (or reported
from the stage strike and character select pages).

## Settings

Set them in this folder's `settings.json`, or in the page's URL
(`strip.html?show_upcoming=false`).

| Setting | Default | |
| - | - | - |
| `hide_after_decided` | `true` | Leave out the games after the one that decided the set |
| `show_upcoming` | `true` | Outline the games left to play (strip and column) |
| `show_stage_name` | `true` | The stage's name on the recap's cards |
| `game_label`, `current_label`, `draw_label` | `"Game"`, `"Now"`, `"Draw"` | |
| `show_records` | `true` | The recap's records of each character |
| `stock_icon.<game>.asset_key` | `"base_files/icon"` | The characters' icons |
