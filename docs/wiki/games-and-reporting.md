# Games and reporting

Each scoreboard keeps track of the set's games: who won each one and with which
characters (and on which stage, for games with stages). Under the score on the
[Scoreboard](scoreboard.md) there's a square per game, and a **Games** button.

The score and the games follow each other: raising a team's score gives it the next game,
and setting a game's winner changes the score. The characters on the scoreboard are filled
in for each game as it's won.

## Editing games

- **Click a game square** to open that game: click a team to make it the winner (or
  press **1** or **2**), and change the characters. The arrows, or **←** and **→**, go
  to the other games. The game being played shows the characters on the scoreboard in
  italics until it's won.
- **Click Games** to see every game at once, with the score after each one. The game
  being played is highlighted, and games the set won't need are greyed out. **1** and
  **2** pick the winner of the game being played.
- **Right-click a game square** to set its winner without opening anything.
- Clicking a character opens the character grid.
- **☰ › Clear games**, in the Games pop-up, empties every game's result, stage and
  characters.

Stages are set by [stage strike](stage-strike.md), or in a game's pop-up for games with
stages.

Layouts get the games in `score.N.games` (see [Making layouts](making-layouts.md)).

## Reporting the set to start.gg

HyperDrive can report the set, with its games, characters and stages, to start.gg. This
needs a start.gg API token from an account that's an **admin of the tournament**:

1. On start.gg, open **Developer Settings** and create a token.
2. Paste it in [Settings › API Keys](hyperdrive://open/settings/api-keys), under
   *start.gg (reporting sets)*.
3. Click **Games**, then **☰ › Check start.gg token** to make sure it works.

Then, with a set loaded from start.gg:

- When a game's winner takes the set, its pop-up offers to **Report to start.gg**.
- The Games pop-up's button says what it reports, e.g. **Report 3–1 · Tweek wins**
  (**Ctrl+Enter**). It's greyed out until the set is won, and says why reporting isn't
  possible yet when you point at it, e.g. when the set's bracket hasn't started on
  start.gg.
- Its **☰** menu has the rest:

| Item | What it does |
| - | - |
| **Send games now** | Sends the games so far without ending the set (when games aren't sent as they're played) |
| **Retry** | Sends the last request to start.gg again, after an error |
| **Check start.gg token** | Checks the token in Settings works |
| **Reset set on start.gg** | Resets the set on start.gg so it can be reported again. Sets that depend on it are reset too. The games here are kept |

Without a token, or without a set from start.gg, nothing about start.gg is shown.

## Reporting settings

In [Settings › start.gg Reporting](hyperdrive://open/settings/startgg-reporting):

- **Send each game to start.gg as it's played**: viewers can follow the set on start.gg.
  Otherwise the games are sent when the set is reported.
- **Mark sets as in progress on start.gg when they're loaded on a scoreboard**.
- **Ask before reporting a set**.

> The token is saved in plain text in `user_data/settings.json`. Don't share that file.
