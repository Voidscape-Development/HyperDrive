# Scoreboard

The [Scoreboard Manager](hyperdrive://open/scoreboard) tab is where you run the set on
stream: the players, their characters, the score, the phase and the match. Everything you
change shows up on the layouts right away.

## The score area

| Control | What it does |
| - | - |
| **Phase** | Where in the event the set is, e.g. *Pool A*, *Bracket*, *Top 8* |
| **Match** | The round, e.g. *Winners Finals*, *Losers Semis* |
| **Best of** | How many games the set lasts |
| **Score** | Each team's score. Use the arrows, or type it |
| **Swap teams** | Switches the left and right teams |
| **Reset score** | Sets both scores to 0 |
| **Clear all** | Clears the players, scores, phase and match, and unlinks the loaded set |

The squares under the score are the set's games: click one to open it, right-click it to
set who won it. **Games** shows every game at once (see
[Games and reporting](games-and-reporting.md)).

The phase and match dropdowns list the usual names. You can rename them, or add your own,
in [Settings › Match & Phase Names](hyperdrive://open/settings/match-names).

## Teams and players

Each side has a **Team** column:

- **Team name**: for doubles or crews. Its logo is the one named after it in
  [Player database › Team logos](player-database.md#logos).
- **Losers**: check it when the team comes from the losers side, to show *[L]* on the
  layouts in a grand final.
- The **color** button: the team's color on the layouts. The defaults are in
  [Settings › Appearance](hyperdrive://open/settings/appearance).

Each player card has the sponsor, tag, real name, pronouns, location, socials, seed and
characters. Type a tag and pick the player in the popup to fill in the rest from the
tournament's entrants or your [Player database](player-database.md).

On each card:

- **Save new player** / **Update player** saves the card to the player database.
- **Media…** opens the player's avatar, sponsor logos and custom data.
- **Clear** empties the card.
- **Show details** / **Hide details** shows the fields hidden by compact cards.
- Drag a card by its grip to reorder the players or move one to the other team.

## What's on the cards

Above the teams:

- **Characters per player**: how many characters each player can pick (e.g. 2 for a
  team game or a secondary).
- **Players per team**: 1 for singles, 2 for doubles, and so on.
- The 👁 menu hides fields you don't use (real name, socials, seed, birthday, location,
  characters, pronouns, additional information), and **Compact player cards** shows only
  the tag, sponsor and characters. The defaults are in
  [Settings › Default Display Options](hyperdrive://open/settings/display-options).

## Loading a set from your tournament

With a [tournament](tournaments.md) loaded:

- **Load set from …** lists the event's sets. Double-click one to load its players,
  characters, phase, match and best of. **Show completed sets** includes sets that are
  over.
- **Track sets from a stream or station** follows a start.gg stream or station: whenever
  its set changes, the new set is loaded.

After loading, the scoreboard keeps itself up to date from start.gg (the score and the
characters reported there). The **Auto update** line under the buttons shows the countdown
to the next update; ✕ stops it. You can turn this off, or change how often it updates, in
[Settings › Scoreboard](hyperdrive://open/settings/scoreboard).

To load the next set automatically when a set ends, use the [Stream queue](stream-queue.md).

## Several scoreboards

For several streams (or a stream plus a station), click **+ Scoreboard** at the right of
the Scoreboard Manager's tabs. Each scoreboard gets its own tab: double-click a tab to rename
it. **−** removes the last scoreboard.

Layouts show scoreboard 1. To show another one, add `?scoreboardNumber=2` to the layout's
URL (see [Adding layouts to OBS](obs-setup.md#layouts-with-options-use-a-url)).

## Editing the scoreboard from a phone

The link under the buttons, `http://<address>:5500/scoreboard`, opens a remote scoreboard in
any browser on your network: handy for a producer, or a second screen. See
[Web pages](web-pages.md).

- Tap a side to give it a point. Each side has **−** below it to take one away, and every
  score change shows a toast with **Undo**.
- The line above the score says where the set stands (game 4, match point, final game).
  Once a side wins, **Load next set** takes you to the list of sets.
- The person button below a side opens its players: tag (pick one from the player
  database to fill in the rest), sponsor, characters and costumes, plus the side's name
  and color.
- On a phone, **Live** and **Up next** at the bottom switch between the score and the
  sets. On a wider screen the sets are always on the right, and the keyboard works too:
  **Q** / **P** add a point to the left / right side, **Shift+Q** / **Shift+P** take one
  away and **S** swaps the sides.

## Related settings

In [Settings › Scoreboard](hyperdrive://open/settings/scoreboard):

- **Enable score control from the stage striking app**: players report game winners from
  the [stage strike](stage-strike.md) page.
- **Disable automatic set updating** / **Disable automatic score updating**: stop the
  start.gg updates.
- **Do not update character data when a set is loaded**: keeps the characters you set.
- **Use the local player database for player info when loading sets**: takes socials,
  pronouns and location from your player database instead of start.gg.
