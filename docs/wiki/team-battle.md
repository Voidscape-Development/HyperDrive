# Crew/team battle

The [Crew/Team Battle](hyperdrive://open/team-battle) tab runs crew battles:
two teams of players, played one matchup at a time until a team runs out.

## Modes

| Mode | How it works |
| - | - |
| **Stock Pool** | Each player starts with a number of stocks (lives) and plays until they've lost them all, then the team's next player comes in. The team that runs out of stocks loses |
| **First To** | Each matchup is played to a number of game wins; the loser is out |

The starting stocks (Stock Pool) and games to win a matchup (First To) default to the values
in [Settings › General](hyperdrive://open/settings/general).

## Running a battle

1. Pick the **Mode**, and the number of **Players** and **Characters** per team.
2. Fill in each team's name and players (type a tag to fill in a player from your
   [Player database](player-database.md)).
3. During the battle, set each player's stocks or games won. The active player is marked
   **Active**, and players who are out **Eliminated**.

**Auto advance** makes a team's next player active when the active player is eliminated.
**Reset Player Mode Values** resets every player's stocks or wins, and **Reset Battle
Mode** resets the whole battle.

## Layouts

`layout/team_battle/` has an in-game scoreboard, a roster board and a versus screen for each
mode: `scoreboard_stock.html`, `roster_stock.html`, `versus_stock.html`, and the
`_first_to` versions.

The [Stream Deck plugin](stream-deck.md) has Team Battle Score, Player and Reset actions.
