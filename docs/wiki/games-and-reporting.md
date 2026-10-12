# Games and reporting

Each scoreboard has a **Games** window with the set's games: who won each one, on which
stage, with which characters. Open it by clicking the game squares under the score on the
[Scoreboard](scoreboard.md).

The score and the games follow each other: raising a team's score gives it the next game,
and setting a game's winner changes the score. The characters on the scoreboard are filled
in for each game as it's won.

## Editing games

- Each row is a game: click a team's button to make it the game's winner, and pick the
  stage and the characters.
- On the scoreboard, right-click a game square to set its winner without opening the
  window.
- **Clear games** empties every game's result, stage and characters.

Layouts get the games in `score.N.games` (see [Making layouts](making-layouts.md)).

## Reporting the set to start.gg

HyperDrive can report the set, with its games, characters and stages, to start.gg. This
needs a start.gg API token from an account that's an **admin of the tournament**:

1. On start.gg, open **Developer Settings** and create a token.
2. Paste it in [Settings › API Keys](hyperdrive://open/settings/api-keys), under
   *start.gg (reporting sets)*.
3. In the Games window, click **Check token** to make sure it works.

Then, with a set loaded from start.gg:

| Button | What it does |
| - | - |
| **Report set to start.gg** | Sends the result and the games, ending the set |
| **Send games now** | Sends the games so far without ending the set |
| **Reset on start.gg** | Resets the set on start.gg so it can be reported again. Sets that depend on it are reset too. The games here are kept |

The window says why reporting isn't possible yet, e.g. when the set's bracket hasn't
started on start.gg.

## Reporting settings

In [Settings › start.gg Reporting](hyperdrive://open/settings/startgg-reporting):

- **Send each game to start.gg as it's played**: viewers can follow the set on start.gg.
  Otherwise the games are sent when the set is reported.
- **Mark sets as in progress on start.gg when they're loaded on a scoreboard**.
- **Ask before reporting a set**.

> The token is saved in plain text in `user_data/settings.json`. Don't share that file.
