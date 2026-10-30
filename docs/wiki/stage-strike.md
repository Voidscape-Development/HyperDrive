# Stage strike

HyperDrive can run stage striking for games with stages, such as Smash: the players strike
and pick stages on a phone or tablet, the result shows on stream, and the game's winner can
be reported from the same page.

## 1. Set up a ruleset

Open the [Stage](hyperdrive://open/stage-strike) tab. Pick a ruleset in the **Ruleset**
dropdown (start.gg's rulesets for the game, and the ones you saved), or make your own:

| | What it means |
| - | - |
| **Name** | The ruleset's name in the dropdown |
| **Stages** | Click a stage to change it: *not used* → *neutral* (stages for game 1) → *counterpick* (extra stages for the following games). Right-click one to pick what it is. **Search stages** and **In ruleset** narrow the list |
| **Game 1 striking** | Who strikes how many stages in game 1. Player A wins rock-paper-scissors and strikes first, then the players take turns. **+ Add a step** adds a turn |
| **Bans after each game** | How many stages the winner of a game bans for the next one: **Same every set**, or **Depends on best-of** (e.g. 3 bans in a best of 3, 2 in a best of 5) |
| **Stage clause** | *No DSR*, *DSR* (a stage already played in the set can't be picked again) or *MDSR* (the player picking can't pick a stage they already won on) |

The squares under **Game 1 striking** show the neutral stages being struck, and the stage
left to play. If the strikes don't match the neutral stages, it says how many to add or take
away, and the badge at the top of the tab says the ruleset has an issue to fix.

Click **Save new** (or **Update**) to keep it. **Unsaved changes** shows when you changed
the ruleset since; **Revert** goes back to the selected ruleset.

### Rulesets for several scoreboards

**Applies to** picks what you're editing: the ruleset shared by **All scoreboards**,
or one scoreboard's. Check **Use its own ruleset** to give a scoreboard a ruleset of its own,
e.g. a side stream running another game.

## 2. Open the stage strike page

The Stage tab's **Stage strike page** shows the link to open on a phone or tablet on the same
network, with a button to copy it:

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

After each game, the page asks for the next game's characters. Turn this off in
[Settings › Scoreboard](hyperdrive://open/settings/scoreboard) (*Ask for the next game's
characters after each game*); the **Characters** button still
opens it.

A link with `?scoreboard=<n>`, like the one in the Stage tab, only works on that
scoreboard: the page doesn't offer the others.

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
(*Players can change the score*, under *Stage striking app*).

**Restart stage strike**, in the Stage tab, starts the strike over for the scoreboard
you're editing. You can also do it from a [Stream Deck](stream-deck.md).
