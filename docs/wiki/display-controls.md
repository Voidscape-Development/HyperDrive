# Display controls

The [Display Controls](hyperdrive://open/display-controls) tab turns layouts on and off.
Off plays the layout's hide animation (its show animation backwards, unless the layout has
its own), on plays its show animation again. What's off stays off when HyperDrive restarts
or OBS reloads the source.

It's an alternative to hiding sources in OBS: the layout animates out instead of
disappearing.

## Layouts and groups

- **Layouts**: every page in a layout folder (e.g. `scoreboard`) is turned on and off
  together. **Look for new layout folders** refreshes the list.
- **Groups**: add `?display=<group>` (or several, `?display=main,top8`) to a layout's URL in
  OBS, and that page is also turned off with its group. Groups show up once a page using
  them is open, or add one with **New group** › **Add group**.

A page is shown while its folder and all of its groups are on. Checked means shown.
**Show all** and **Hide all** turn everything on or off. **Filter** narrows the lists.

## Controlling it from other tools

The [Stream Deck plugin](stream-deck.md) has a Display Controls action that lights up while
its layout is shown.

For other tools (Stream Deck's *Website* or *API Ninja* actions, Bitfocus Companion…),
right-click an entry and **Copy toggle link**, **Copy show link** or **Copy hide link**. The
links are:

| Link | |
| - | - |
| `/display/folder/<folder>/<action>` | A layout folder |
| `/display/group/<group>/<action>` | A group |
| `/display/all/<action>` | Everything |
| `/display/folder/<folder>`, `/display/group/<group>` | Whether it's shown, e.g. to light a button |
| `/display/state` | Every folder and group |

`<action>` is `show`, `hide` or `toggle`. See [Remote control](remote-control.md) for the
socket.io events.
