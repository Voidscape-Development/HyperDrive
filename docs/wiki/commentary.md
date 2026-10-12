# Commentary

The [Commentary](hyperdrive://open/commentary) tab holds the commentators shown by the
`commentators` layouts.

- **Number of commentators**: how many cards to show.
- **Characters per player**: for commentators who are also players and want their mains
  shown.
- Each card works like a [scoreboard](scoreboard.md) player card: type a tag and pick the
  person in the popup to fill in their real name, pronouns and socials from your
  [Player database](player-database.md). **Save new player** adds a commentator to it.
- The 👁 menu hides fields you don't use.

## Layouts

`layout/commentators/` has three pages:

| Page | Shows |
| - | - |
| `tag.html` | The tags |
| `tag_twitter.html` | The tags and their Twitter/X handles |
| `tag_name_twitter.html` | The tags, real names and handles |

Add the one you want in OBS (see [Adding layouts to OBS](obs-setup.md)).

## From other tools

The commentators can be read and updated over HTTP, e.g. by a producer tool:
`GET /get-comms` returns them, and `POST /update-commentary-<n>` updates commentator `n`.
See [Remote control](remote-control.md).
