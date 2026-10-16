# Bracket

The [Bracket](hyperdrive://open/bracket) tab shows brackets on stream: start.gg phase
groups, or brackets you build yourself. It supports double elimination, single elimination,
round robin and swiss.

## The layout of the tab

- **The header** shows the [channel](#channels) tabs, the channel's phase as its title (click it
  to show another phase), the people button for the phases and players window, and on the right
  the **start.gg** button: where the bracket comes from, and loading it.
- **The bar under it** is what goes on stream: the channel's **Top** N and the
  [focus](#bracket-focus).
- **Over the bracket**, bottom right: **Update sets** and **Auto update** (once a start.gg
  phase group is loaded), then zoom out, zoom in and **Fit**. Bottom left, when sets have
  players placed by hand: **Clear manual changes**.

## Loading a bracket from start.gg

With a [tournament](tournaments.md) loaded, click the **start.gg** button in the header:

1. Pick the **Phase** and the **Phase Group** (e.g. *Top 8*).
2. Click **Load**. The group's players and sets are loaded, and shown on this channel.
   Loading it again reloads it.

Once it's loaded, **Update sets** in the bracket's bottom right corner updates the results
without reloading the players. **Auto update**, next to it, does it periodically as the
bracket progresses, and counts down to the next update; the interval is in
[Settings › General](hyperdrive://open/settings/general).

Results come from start.gg. Changes you make here only change what's shown on stream.

## Building a bracket by hand

Click the people button (or the phase title, then **Phases and players...**) to open the phases and players
window, then **New phase**:

| Option | What it does |
| - | - |
| **Name**, **Type** | The phase's name, and double elimination, single elimination, round robin or swiss |
| **Starting in losers** | How many of the last seeds start on the losers side |
| **Grand final reset**, **3rd place match** | Extra sets |
| **Players going on** | How many players go on to another phase instead of playing to a champion |
| **Seeds** | The players, in seed order. ▲ ▼ move them |
| **Take from phases…** | Seeds this phase with the top players of other phases (e.g. pools), spread out so players from the same pool don't meet early |
| **Player list order** | Seeds it with the player list, in its order |
| **Rebuild bracket** | Builds the bracket again from the seeds, clearing its results |
| **Pair next round** (swiss) | Pairs the next round from the standings, avoiding rematches |

**Players** edits the player list. Double-click a set in the bracket to enter its score.

## What goes on stream

- **Top**: only sends the sets of players who can still finish in the top N, e.g. a top 8
  out of a bigger bracket.
- **Clear manual changes** (over the bracket, when there are some): puts back the players
  the bracket gives each set, undoing players placed by hand.
- **Fit** zooms the view to the whole bracket.

## Channels

Each tab of the bracket is a *channel*: it shows one phase on its own, e.g. a pool bracket
on one screen and top 8 on another. **+** adds a channel; right-click a tab to rename or
remove it. With more channels than fit, the tabs scroll and a ▾ button lists them all.

Layouts show the `main` channel. Add `?channel=<name>` to a layout's URL to show another one.

## Bracket focus

`layout/bracket_focus` zooms to part of the bracket and follows the action. **Focus** picks
what it shows, one mode at a time; the setting of the mode in use shows next to it. What the
layout shows now is on the right of the bar.

| Mode | What it does |
| - | - |
| **Whole** | Shows everything |
| **Selected** | Zooms to the sets and rounds you Ctrl+click, and highlights them. **Unselect** clears them |
| **Round** | Zooms to a round; ◀ ▶ step through the rounds |
| **Player** | Zooms to every set of the player you pick |
| **Follow** | Keeps zooming to the set on a **Scoreboard** |
| **Tour** | Shows the whole bracket, then each round in turn, over and over, **Each step** seconds; ◀ ▶ skip steps |

The focus can also be driven from a phone at `/bracket-focus-app` (see
[Web pages](web-pages.md)) or a [Stream Deck](stream-deck.md).

## Layouts

| Layout | Shows |
| - | - |
| `bracket/index.html`, `index_expanded.html` | The bracket |
| `bracket/winners_only.html`, `losers_only.html` | One side |
| `bracket/round_robin.html`, `standings.html` | Round robin and swiss |
| `bracket_ultimate/` | A bracket with character art |
| `bracket_focus/` | The zooming bracket |

The bracket's colors and options are in [Layout themes](layout-themes.md), under Bracket and
Standings.
