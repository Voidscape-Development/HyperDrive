# Tournaments

HyperDrive pulls tournament data from **start.gg**, and from **parry.gg** in beta. Loading
an event fills in the scoreboard's sets, the players and their seeds, the bracket, the
stream queue and the event stats.

## Loading an event

1. Click [Set tournament](hyperdrive://open/set-tournament) in the top bar.
2. Paste one of:
   - the tournament's link, e.g. `https://www.start.gg/tournament/genesis-x`
   - an event's link (that event is selected for you)
   - a start.gg short link
   - the tournament's slug, e.g. `genesis-x`
3. Pick the event in the list. You can filter it, and it shows each event's game, entrants,
   dates and whether it's online or offline.

The game is selected from the event. **Select event** switches to another event of the same
tournament later, and ✕ unloads it.

### parry.gg

parry.gg needs an API key: create one at parry.gg/api-keys and paste it in
[Settings › API Keys](hyperdrive://open/settings/api-keys). Some features (event stats, the
stream queue, reporting) are start.gg only.

## Players who registered late

The players are pulled when the event is loaded. **Repull entrants** pulls them again, for
the ones who registered after. Players already pulled are updated, not removed.

## Completed sets

**Pull Latest Completed Sets from StartGG** pulls the sets that just finished, for the
`completed_sets` layouts (a ticker, a list or cards of recent results). Check **Auto pull**
to pull them periodically; the interval is in
[Settings › General](hyperdrive://open/settings/general).

## Using the data

| To… | Use |
| - | - |
| Put a set on the scoreboard | **Load set from …** on the [Scoreboard](scoreboard.md) |
| Follow a stream or a station | **Track sets from a stream or station** on the [Scoreboard](scoreboard.md) |
| Load the next streamed set automatically | [Stream queue](stream-queue.md) |
| Show the bracket | [Bracket](bracket.md) |
| Show the final standings (top 8) | [Player list](player-list.md) |
| Show stats, the schedule and a league | [Event stats](event-stats.md) |
| Show the tournament's name, logo and date | [Tournament info](tournament-info.md) |
| Report results back to start.gg | [Games and reporting](games-and-reporting.md) |

## Without a tournament

Everything works by hand too: type players on the scoreboard, build a bracket in the
[Bracket](bracket.md) tab, and seed players in the [Seed editor](player-database.md#seeds).
