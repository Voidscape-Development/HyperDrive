# Player list

The [Player List](hyperdrive://open/player-list) tab holds a list of players for the
`top_8`, `top_8_single_elim`, `top_8 - StationSquare` and `top_n_list` layouts: final
standings, a top 8 graphic, or any list of players.

`top_8 - StationSquare` shows the winner's character art in a circle and the next seven
in rows with their flags, characters and record (`index.html` for double elimination,
`index_single_elim.html` for single). Its bottom bar has the start.gg tournament's logo
on the left; put your series' logo in its folder as `series_logo.png` for the right.

## Filling it in

- **Load tournament standings** fills it with the event's final standings from start.gg.
- Or fill it by hand: each slot works like a [scoreboard](scoreboard.md) player card.

| Option | What it does |
| - | - |
| **Number of slots** | How many places, e.g. 8 for a top 8 |
| **Players per slot** | 2 for a doubles top 8 |
| **Characters per player** | How many characters each player shows |
| **Show scores** | Adds a score to each slot, beside its team name |
| **Start slots collapsed** | Slots open collapsed to their title. Off: they open as you left them |
| **Compact players** | Folds every player's details away, keeping their tag, sponsor and characters |
| **Collapse all** / **Expand all** | Collapses every slot to its title, or shows every slot's players |

## Collapsing slots

The arrow at the start of a slot collapses it to its title: its place, team name and score,
which you can still edit. A slot with no team name shows its players' tags in grey. Each
player's own arrow folds away their details. HyperDrive remembers which slots and players
are folded for next time.

## Results text

**Generate Descriptive Text for Results** writes the results as text, e.g. to post on
social media. The **Simple** template is ready to use; you can also edit the **Header**,
**Each placement**, **Each player** and **Footer** templates.

In a template, `{name}` is replaced by the value. A part in `[[ ]]` is only shown when every
value in it is filled in, e.g. `[[ ({twitter})]]`. **Copy text** copies the result, and
**Reset templates** goes back to the defaults.
