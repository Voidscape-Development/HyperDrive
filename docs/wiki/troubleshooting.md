# Troubleshooting

## A layout shows nothing in OBS

- Check the source's size is **1920x1080**.
- Make sure HyperDrive is running: layouts get their data from it.
- Right-click the source › **Refresh cache of current page**, or **Interact** and press F5.
- A layout loaded by URL (`http://127.0.0.1:5500/…`) needs the right port, if you changed it
  in [Settings › General](hyperdrive://open/settings/general).
- Check it isn't hidden by [Display controls](display-controls.md).
- A scoreboard layout shows scoreboard 1 unless its URL has `?scoreboardNumber=`.

## Characters or stages are missing

Download the game's assets: [Download assets](hyperdrive://open/download-assets). If they're
still missing after updating, they may not be in the asset database yet (see
[Game assets](game-assets.md)).

## Web pages don't load on another device

- Use the address shown in the Scoreboard or Stage tab, not `127.0.0.1` (which means "this
  device").
- The device must be on the same network. Guest Wi-Fi networks often keep devices apart.
- Windows may ask to let HyperDrive through the firewall the first time it runs: allow it on
  private networks. If you dismissed it, allow `HyperDrive.exe` in *Windows Defender Firewall
  › Allow an app through firewall*.
- Another program may be using port 5500: change the port in
  [Settings › General](hyperdrive://open/settings/general) and restart HyperDrive.

## The tournament doesn't load

- Check the link: it should be a start.gg tournament or event link, a short link, or a slug.
- parry.gg needs an API key in [Settings › API Keys](hyperdrive://open/settings/api-keys).
- start.gg may be down or limiting requests: wait a minute and try again.

## Reporting to start.gg fails

In the Games window, click **Check token**. The token must belong to an account that's an
admin of the tournament, and the set's bracket must have started. See
[Games and reporting](games-and-reporting.md).

## "Invalid JSON file" at startup

`user_data/settings.json` or `out/program_state.json` was damaged, e.g. by a crash while
saving. HyperDrive says which one. Fix the file in a text editor, or delete it to start over
(deleting `settings.json` resets your settings and API keys).

## Updating HyperDrive

HyperDrive doesn't update itself yet. To update:

1. Download the new `HyperDrive-windows.zip` from the
   [releases page](https://github.com/Voidscape-Development/HyperDrive/releases).
2. Extract it to a new folder.
3. Copy your old `user_data` folder over the new one: it holds your settings, player
   database, game assets and logos.

Your version is in ☰ › [About](hyperdrive://open/about).

## Logs and reporting a bug

HyperDrive writes logs to the `logs/` folder next to it: `hyperdrive.log`,
`hyperdrive-error.log`, and `hyperdrive-crash.log` after a crash.

To report a bug, use ☰ › **Report a bug**, say what you did and what happened, and
attach the logs. Remove anything private from them first.
