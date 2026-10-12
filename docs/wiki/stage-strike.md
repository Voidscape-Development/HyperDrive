# Stage strike

HyperDrive can run stage striking for games with stages, such as Smash: the players strike
and pick stages on a phone or tablet, the result shows on stream, and the game's winner can
be reported from the same page.

## 1. Set up a ruleset

Open the [Stage](hyperdrive://open/stage-strike) tab. Pick a ruleset in the **Ruleset**
dropdown (start.gg's rulesets for the game, and the ones you saved), or make your own:

| Field | What it means |
| - | - |
| **Ruleset Name** | Its name in the dropdown |
| **Neutral stages** | Stages for game 1 |
| **Counterpick stages** | Extra stages for the following games |
| **Strike order** | Who strikes how many stages in game 1, e.g. `1,2,1` |
| **Fixed ban count** | How many stages the winner of a game bans afterwards |
| **Ban count by max games** | A different ban count by best of, e.g. `3:3,5:2` (3 bans in a best of 3, 2 in a best of 5) |
| **DSR** | *No DSR*, *DSR* (a stage already played in the set can't be picked again) or *MDSR* (the player picking can't pick a stage they already won on) |

Drag stages from **All stages** into the neutral and counterpick lists. The **Validation**
line tells you if the ruleset makes sense, e.g. if the strike order doesn't match the number
of neutral stages. Click **Save new** (or **Update**) to keep it.

### Rulesets for several scoreboards

**Edit ruleset for** picks what you're editing: the ruleset shared by **All scoreboards**,
or one scoreboard's. Check **Use its own ruleset** to give a scoreboard a ruleset of its own,
e.g. a side stream running another game.

## 2. Open the stage strike page

The Stage tab shows the link to open on a phone or tablet on the same network:

```
http://<HyperDrive's address>:5500/stage-strike-app?scoreboard=1
```

The players play rock-paper-scissors, strike and pick stages on it. After each game they
pick the winner, and the next game's strike starts. The page has **Undo**, **Redo**,
**Restart** and **Gentleman's** (agree on a stage).

Add `&team=1` or `&team=2` to the link to give each team its own device: a team can only
strike on its turn, and the other team confirms a game's winner.

The link **for character selection only** (`/character-select`) lets players pick their
characters without striking stages.

## 3. Show it on stream

Add one of these layouts in OBS (see [Adding layouts to OBS](obs-setup.md)):

- `stage_strike/`: the strike as it happens. `index_autohide.html` hides itself once a
  stage is picked.
- `stage_strike_display/`: the strike in different shapes (a column, a bar, minimal…).
- `ruleset/`: the ruleset's stage list. `index_for_printing.html` is for printing at the
  stations.

## Scores from the stage strike page

When a game's winner is picked on the stage strike page, the scoreboard's score goes up.
Turn this off in [Settings › Scoreboard](hyperdrive://open/settings/scoreboard)
(*Enable score control from the stage striking app*).

**Restart stage strike**, in the Stage tab, starts the strike over for the scoreboard
you're editing. You can also do it from a [Stream Deck](stream-deck.md).
