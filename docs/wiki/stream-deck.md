# Stream Deck

The HyperDrive plugin for Stream Deck runs HyperDrive from its keys, and they show what's
happening live: the score and team color on a score key, whether a layout is shown, the
active player of a crew battle.

It needs Stream Deck 7.1 or newer, on Windows 10 or macOS 12 and up.

## Installing it

1. Download `HyperDrive.streamDeckPlugin` from the
   [releases page](https://github.com/Voidscape-Development/HyperDrive/releases) and open
   it.
2. Drag a HyperDrive action onto a key.
3. If HyperDrive runs on another computer, type its address (and its port, if you changed
   it from 5500) at the bottom of the action's settings. Every action uses the same
   address, and the settings say whether it's connected.

Keys whose HyperDrive can't be reached are dimmed with a red badge, and pressing one shows
an alert, as does an action HyperDrive refuses (e.g. nothing to undo).

## Actions

| Action | Key | Dial (Stream Deck +) |
| - | - | - |
| Team Score | Add or Remove: adds a point, or takes one. Shows the team, its score and color | Turn: change the score. Push: swap the teams. Touch: add (or take) a point |
| Swap Teams | Swaps the scoreboard's teams | |
| Reset Scoreboard | The scores, the match, the players or everything. Held, so it isn't pressed by mistake | |
| Team Color | Sets a team's color, lit while the team has it | |
| Load Set | The next set of the stream queue (shown on the key), the set on stream, or the set selector | |
| Display Controls | Toggles, shows or hides a layout folder, a group or everything. Lit while shown | Turn: pick the layout. Push or touch: show/hide it |
| Team Battle Score | A team scores (Stock Pool: the other team loses a stock), or undoes a point. Shows the active player, *Pick a player* while the team has to pick who plays, or *Team out* | Turn: score or undo. Push or touch: next player |
| Team Battle Player | Makes the next player, or a given one, active. A given player's key shows their stocks or wins, *Out*, and when only some of the players play, *On deck* or *Didn't play* | |
| Team Battle Reset | Every player's stocks, or the whole battle. Held | |
| Stage Strike | Undo, redo, restart (held), or the winner of rock-paper-scissors or of the game | |
| Bracket Focus | The whole bracket, next/previous round, the set on a scoreboard, a tour, a player's run, or which phase a focus channel shows | Turn: next/previous round. Push: follow the scoreboard's set. Touch: whole bracket |

The actions with scoreboards have a scoreboard setting, so one profile can run several
streams.

## Other controllers

Bitfocus Companion, Stream Deck's *Website* action and similar tools can call HyperDrive's
links directly. See [Display controls](display-controls.md#controlling-it-from-other-tools)
and [Remote control](remote-control.md).
