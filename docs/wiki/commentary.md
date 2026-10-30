# Commentary

The [Commentary](hyperdrive://open/commentary) tab holds the commentators shown by the
`commentators` layouts.

- **Number of commentators**: how many cards to show.
- **Characters per player**: for commentators who are also players and want their mains
  shown.
- Each card works like a [scoreboard](scoreboard.md) player card: type a tag and pick the
  person in the popup to fill in their real name, pronouns and socials from your
  [Player database](player-database.md). **Save new player** adds a commentator to it.
- The 👁 menu hides fields you don't use, and **Compact player cards** shows only the
  tag, sponsor and characters (each card's arrow still shows the rest). Its default is
  set in [Settings › Player cards](hyperdrive://open/settings/display-options).

## Commentary dashboard

A page for the commentators to keep open on a laptop, a tablet or a second screen while
they talk: open `http://<HyperDrive's address>:5500/commentary-dashboard` (the
Commentary tab has the link). It follows the scoreboard live and shows:

- **The players**: tag, sponsor, real name, pronouns, where they're from, seed, socials
  and characters, with their notes: *Additional information* from the
  [Player database](player-database.md) and their custom data (a bio, a stats file...,
  see [Player database](player-database.md)).
- **Their stats**, for 1v1 sets from start.gg or parry.gg: their head-to-head, their sets
  in this event and their results at past events, with how they did against their seed.
  *Refresh stats* asks for them again.
- **The set**: the score, the upset it would be, each game's stage, characters and
  winner, and what's at stake: where the winner and the loser go in the bracket, and the
  placement the loser gets. That needs the event's bracket loaded in the
  [Bracket](bracket.md) window.
- **Up next**: the sets of the [Stream queue](stream-queue.md), with when they should
  start. Click one to see its players, with their stats.
- **Recent results**: the event's last completed sets, upsets marked.

It only shows what's in HyperDrive: nothing on it can change the stream. With several
scoreboards, pick one at the top, or add `?scoreboard=2` to the link to lock it to one.

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
