# Tournament info

The [Tournament Info](hyperdrive://open/tournament-info) tab holds what the layouts show
about the event itself:

| Field | |
| - | - |
| **Tournament Name**, **Event Name** | Shown on scoreboards, brackets and top 8s |
| **Dates** | When it starts and ends |
| **Entrants** | How many entrants |
| **Location** | Where: the venue's address |
| **City, State** | Just the city and state (e.g. *Springfield, IL*), for layouts that don't show the whole address. Filled in from the tournament; layouts get it as `tournamentInfo.cityState` |
| **Short Link** | e.g. the start.gg short link for viewers. The button at its end copies it |
| **Logo** | The tile next to the names. Its buttons load an image of yours, download the tournament's from start.gg, or go back to the default. You can also drop an image on it |
| **Banner** | The tournament's banner from start.gg, for layouts that show one. The button next to it removes it, **Restore** brings it back |

The top of the tab says where the info comes from. **Load from start.gg** (or parry.gg) fills
it all in from the loaded [tournament](tournaments.md). It's filled in when an event is loaded,
and you can change anything afterwards: a field you changed says **Edited**, and its
**Revert** button gives it the tournament's value back. **Clear all** empties it.

On the side, **On stream** gives a rough idea of how layouts use these fields, and
**Sent to layouts** lists what they get (`tournamentInfo.*`), changed fields marked with a dot.

The tournament's logo and banner from start.gg are sent to the layouts as
`tournamentInfo.logo` and `tournamentInfo.banner`.
