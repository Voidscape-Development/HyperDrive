# Tournaments

HyperDrive pulls tournament data from **start.gg** and **parry.gg**. Loading an event
fills in the scoreboard's sets, the players and their seeds, the bracket and the stream
queue.

## Loading an event

1. Click [Load tournament](hyperdrive://open/set-tournament) in the top bar.
2. Paste one of:
   - the tournament's link, e.g. `https://www.start.gg/tournament/genesis-x`
   - an event's link (that event is selected for you)
   - a start.gg short link
   - the tournament's slug, e.g. `genesis-x`
3. Pick the event in the list. You can filter it, and it shows each event's game, entrants,
   dates and whether it's online or offline.

The game is selected from the event. The top bar then shows the tournament and event; click
it for **Repull entrants**, **Load a different tournament…** and **Unload tournament**, with
the tournament's events listed below them: click one to switch to it.

### parry.gg

parry.gg needs an API key: create one at parry.gg/api-keys and paste it in
[Settings › API keys](hyperdrive://open/settings/api-keys). Some features (the stream queue,
reporting) are start.gg only.

## Players who registered late

The players are pulled when the event is loaded. **Repull entrants**, in the tournament's
menu in the top bar, pulls them again, for the ones who registered after. Players already pulled are updated, not removed.

## Completed sets

**Completed sets** in the top bar pulls the sets that just finished, for the
`completed_sets` layouts (a ticker, a list, a scrolling list or cards of recent results). ⟳ next to it pulls
them now. Click it and check **Auto pull** to pull them periodically; the interval is in
[Settings › General](hyperdrive://open/settings/general). The bar shows when the next pull
is.

## Using the data

| To… | Use |
| - | - |
| Put a set on the scoreboard | **Load set from …** on the [Scoreboard](scoreboard.md) |
| Follow a stream or a station | **Track sets from a stream or station** on the [Scoreboard](scoreboard.md) |
| Load the next streamed set automatically | [Stream queue](stream-queue.md) |
| Show the bracket | [Bracket](bracket.md) |
| Show the final standings (top 8) | [Player list](player-list.md) |
| Show the tournament's name, logo and date | [Tournament info](tournament-info.md) |
| Report results back to start.gg | [Games and reporting](games-and-reporting.md) |

## Without a tournament

Everything works by hand too: type players on the scoreboard, build a bracket in the
[Bracket](bracket.md) tab, and seed players in the [Seed editor](player-database.md#seeds).
