# Starting soon

A full screen for before the stream (`index.html`) and its breaks
(`brb.html`):

- The start.gg tournament's banner, blurred and shaded, as the background
  (a gradient of the theme's colors without one)
- The tournament's logo (or `layout/logo.png`), name and event
- The title ("Starting soon", "Be right back") and a countdown
- Up next: the next sets on stream from the Stream Queue window, with when
  each should start
- The latest results scrolling along the bottom (Pull Latest Completed Sets),
  with upsets marked

The countdown goes to `countdown_to` (a time today), else for
`countdown_minutes` from when the source loads, else to when the first set in
the stream queue should start. Without any of them it's hidden.

## Settings

Set them in this folder's `settings.json`, or in the page's URL
(`index.html?countdown_to=19:30`).

| Setting | Default | |
| - | - | - |
| `title` | `"Starting soon"` | `brb.html` sets `"Be right back"` |
| `subtitle` | `""` | Shown after the event's name |
| `countdown_to` | `""` | A time today, `"19:30"` |
| `countdown_minutes` | `0` | Minutes from when the source loads |
| `countdown_from_queue` | `true` | Count down to the first queued set's start |
| `countdown_label`, `countdown_done` | `"Starting in"`, `"Any moment now"` | |
| `stream` | `""` | The stream whose queue shows. Empty: the stream linked to the scoreboard, else the first with sets |
| `sets_displayed` | `3` | Sets in Up next |
| `up_next_title`, `now_label` | `"Up next"`, `"Now"` | |
| `eta_format` | `"minutes"` | `"minutes"` (~16 min) or `"time"` (7:42 PM) |
| `clock_24h` | `false` | For `eta_format` `"time"` |
| `show_results`, `results_title`, `ticker_speed` | `true`, `"Results"`, `80` | The results along the bottom; the speed in pixels per second |
| `upset_threshold`, `upset_label` | `1`, `"Upset"` | Results whose upset factor is at least this are marked |
| `show_banner`, `use_tournament_logo` | `true` | The start.gg tournament's banner and logo |
