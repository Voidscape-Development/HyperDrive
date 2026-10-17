# Socials

Lower thirds with a person's name, pronouns and avatar, and their social
media accounts (`socials`, see
[`docs/layout-data.md`](../../docs/layout-data.md#socials-socials)), each with
its platform's icon from `layout/icons` in the card's color. The accounts take
turns every 5 seconds, or show side by side with `mode` `"list"`.

| Page | |
| - | - |
| `player1.html`, `player2.html` | A player on the scoreboard, at the bottom left or right, in their team color |
| `player1_list.html` | The same, with every account side by side |
| `commentators.html` | A card for each commentator, along the bottom center, in the accent color |

For doubles, pick the player with `?player=2`.

## Settings

Set them in this folder's `settings.json`, or in the page's URL
(`player1.html?mode=list`).

| Setting | Default | |
| - | - | - |
| `mode` | `"rotate"` | `"rotate"` (one account at a time) or `"list"` (all of them) |
| `platforms` | Every platform | The platforms shown, in order: `twitter`, `bluesky`, `twitch`, `youtube`, `tiktok`, `instagram`, `kick`, `discord`, `steam`, `xbox` |
| `team`, `player` | `1`, `1` | The player on the scoreboard, for the player pages |
| `show_pronoun`, `show_avatar` | `true` | |
| `twitter_at` | `true` | `@` before Twitter handles typed without one |
