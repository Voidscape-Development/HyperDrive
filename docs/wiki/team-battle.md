# Crew/team battle

The [Crew/Team Battle](hyperdrive://open/team-battle) tab runs crew battles:
two teams of players, played one matchup at a time until a team runs out.

## Modes

| Mode | How it works |
| - | - |
| **Stock Pool** | Each player starts with a number of stocks (lives) and plays until they've lost them all, then the team's next player comes in. The team that runs out of stocks loses |
| **First To** | Each matchup is played to a number of game wins; the loser is out |
| **Stock Pool (Limited Plays)**, **First To (Limited Plays)** | The same, with only some of each team's players playing: see [Players on deck](#players-on-deck) |

The starting stocks (Stock Pool) and games to win a matchup (First To) default to the values
in [Settings › Crew battles](hyperdrive://open/settings/crew-battles).

## Running a battle

1. Pick the **Mode**, and the number of **Players** and **Characters** per team.
2. Fill in each team's name and players (type a tag to fill in a player from your
   [Player database](player-database.md)).
3. During the battle, set each player's stocks or games won. The active player is marked
   **Active**, and players who are out **Eliminated**.

**Auto advance** makes a team's next player active when the active player is eliminated.
After a reset, nobody is playing until each team picks their player (in the Limited Plays
modes, **First player starts** makes each team's first player active instead).
**Reset Player Mode Values** resets every player's stocks or wins, and **Reset Battle
Mode** resets the whole battle.

## Players on deck

A team can bring more players than get to play: for example, a crew of 7 where only 4
play. Pick a **Limited Plays** mode, set **Players** to the size of the crews (7) and
**Plays** to how many of them play (4). Plays starts one under Players, can't be more than
Players, and stays where you set it when Players changes. The **Plays** and **First player
starts** options only show in the Limited Plays modes.

In the Limited Plays modes:

- There are no starters. Players who haven't played are **On deck**, and when the playing
  player is eliminated, the team picks who's next from them: tick that player's **Active**
  box (or use the Stream Deck's Team Battle Player action). Nobody comes in on their own,
  even with Auto advance on.
- A team is out once Plays of its players are eliminated. The players who never got to
  play show **Didn't play**.
- The team's stocks are the stocks of the players who can still play: the one playing, and
  a full set for each play left.
- Undoing the last stock (or game) of a player who was replaced brings them back in.

On the layouts, the roster board shows a card per play, filled as players come in, and the
players on deck in an **On Deck** strip below (dimmed once the team is out). The versus
screen and the scoreboard's roster show a slot per play, without the players on deck.

## Layouts

`layout/team_battle/` has an in-game scoreboard, a roster board and a versus screen for each
mode: `scoreboard_stock.html`, `roster_stock.html`, `versus_stock.html`, and the
`_first_to` versions.

`layout/Nexus - Teams Overview/` (`stock.html` and `first_to.html`) is an overview of
both teams: each team's logo, name and stocks (or players) left, the team scores around the
tournament logo, a card per play with the player's character and stocks or wins (crossed
out once eliminated, empty until a player comes in), and the players on deck in a
**Standby** box below.

`layout/Nexus - Battle/` (`stock.html` and `first_to.html`) is the in-game overlay to go with
it. At the top: each team's logo, stocks (or players) left and short name (the **Short name** typed next to
the team's name, else the name, or its initials when it's longer than 8 characters:
"University of South Carolina Upstate" is USCU), the team scores around the tournament logo, and a slot per play under
each team, slashed once its player is out and lit while they play. At the bottom right: the
player playing for each team, with their character and stocks or games won, or *Picking…*
while the team picks who's next. `stock_wings.html` and `first_to_wings.html` have each
team's player on a wing above the bar, out on its side, instead of at the bottom right.

The [Stream Deck plugin](stream-deck.md) has Team Battle Score, Player and Reset actions.
