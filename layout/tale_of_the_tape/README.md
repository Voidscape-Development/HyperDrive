# Tale of the tape

A full screen for before a set, the two sides face to face: their character
art, names, flags, real names, pronouns and bio (custom data, see
[`docs/layout-data.md`](../../docs/layout-data.md#custom-player-data-custom))
at the edges, and between them a row per number, the better one highlighted:

| Row | From |
| - | - |
| `seed` | The players' seeds |
| `head_to_head` | Their sets against each other (the same as `recent_sets`) |
| `best_finish` | Their best placement among their last tournaments (as `tournament_history`) |
| `recent_finishes` | Their last three placements |
| `event_record` | Their sets won and lost in this event (as `last_sets`) |

Rows with nothing on either side are left out. Under them are their last
meetings. The stats are fetched when a set is loaded on the scoreboard.

## Settings

Set them in this folder's `settings.json`, or in the page's URL.

| Setting | Default | |
| - | - | - |
| `title` | `"Tale of the tape"` | |
| `rows` | All of the above | The rows, in order |
| `custom_rows` | `[]` | More rows from the players' custom data: `[{"label": "Mains", "key": "mains"}]` shows each player's `mains.txt` |
| `highlight_better` | `true` | Highlight the better value of each row |
| `bio_key` | `"bio"` | The custom field under each name (`""` for none) |
| `meetings_displayed`, `meetings_title` | `3`, `"Last meetings"` | |
