# Player list

The [Player List](hyperdrive://open/player-list) tab holds a list of players for the
`top_8`, `top_8_single_elim` and `top_n_list` layouts: final standings, a top 8 graphic, or
any list of players.

## Filling it in

- **Load tournament standings** fills it with the event's final standings from start.gg.
- Or fill it by hand: each slot works like a [scoreboard](scoreboard.md) player card.

| Option | What it does |
| - | - |
| **Number of slots** | How many places, e.g. 8 for a top 8 |
| **Players per slot** | 2 for a doubles top 8 |
| **Characters per player** | How many characters each player shows |
| **Show scores** | Adds a score to each slot |

## Results text

**Generate Descriptive Text for Results** writes the results as text, e.g. to post on
social media. The **Simple** template is ready to use; you can also edit the **Header**,
**Each placement**, **Each player** and **Footer** templates.

In a template, `{name}` is replaced by the value. A part in `[[ ]]` is only shown when every
value in it is filled in, e.g. `[[ ({twitter})]]`. **Copy text** copies the result, and
**Reset templates** goes back to the defaults.
