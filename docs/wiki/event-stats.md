# Event stats

The [Event Stats](hyperdrive://open/event-stats) tab pulls, for a start.gg event:

- **What its completed sets add up to**: the most played characters (with win rates), the
  stages, the biggest upsets, and the players placing furthest above or below their seed.
- **Its schedule**: the phases and waves with their start times.
- **A league's standings**, for events that are part of a circuit.

## Updating

The first update of an event pulls every completed set, which takes a few minutes at a
major. Later updates only pull the new sets.

- **Update now** updates immediately; **Update every** updates periodically.
- **Pull all sets again** forgets the sets already pulled, e.g. after sets were reset on
  start.gg.

The tab shows a summary: the number of sets and games, how long a set takes, the most played
character and the biggest upset.

## League

start.gg rarely links events to their league, so paste the league's start.gg link in
**League**.

## Layouts

| Layout | Shows |
| - | - |
| `event_stats/characters.html` | The most played characters |
| `event_stats/stages.html` | The most played stages |
| `event_stats/upsets.html` | The biggest upsets |
| `event_stats/performers.html` | Players doing better or worse than their seed |
| `schedule/index.html`, `schedule/waves.html` | The schedule |
| `league_standings/index.html` | The league's standings |

How many characters, upsets or players they show, and what's displayed, is in
[Layout themes](layout-themes.md), under Event stats, Schedule and League standings.
