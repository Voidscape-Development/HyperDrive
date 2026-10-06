<p align="center">
  <img src="assets/icons/icon.svg" width="128" alt="HyperDrive logo">
</p>

# HyperDrive

A stream helper for fighting game tournaments!

HyperDrive is based on [TournamentStreamHelper](https://github.com/joaorb64/TournamentStreamHelper)
(TSH). It loads sets, players and brackets from your tournament and sends them to
HTML overlays that you add to OBS or any other streaming software as browser sources.

- **Tournament data** from start.gg, plus parry.gg in beta.
- **Scoreboards** for players, teams and commentators, with a stream queue, a bracket
  view and player stats such as recent sets and head-to-head.
- **More than 40 layouts** in [`layout/`](layout): scoreboards, brackets, top 8s, versus
  screens, stream queues and maps. They share theme options that you can change from the app.
- **A local player database** that you can edit in the app or from a browser.
- **Web pages for your phone or a second screen:** a remote scoreboard, stage strike and
  character select, served by HyperDrive itself.

For setting up layouts in OBS and general usage, see the
[TSH wiki](https://github.com/joaorb64/TournamentStreamHelper/wiki). Most of it applies
to HyperDrive.

## Download (Windows)

1. Download `HyperDrive-windows.zip` from the
   [releases page](https://github.com/Voidscape-Development/TSH-HyperDrive/releases).
   The [`latest-build`](https://github.com/Voidscape-Development/TSH-HyperDrive/releases/tag/latest-build)
   prerelease is rebuilt on every change to `main`, if you want the newest version.
2. Extract the zip and run `HyperDrive.exe`.

To update, extract the new zip and copy your old `user_data` folder over the new one.
It holds your settings, player database, game assets and logos. HyperDrive doesn't
check for updates yet.

On Linux and macOS, run HyperDrive [from source](#running-from-source).

## Web pages

HyperDrive runs a web server on port 5500, which you can change in the settings. Open
these from any device on the same network at `http://<HyperDrive's address>:5500`:

| Page | What it does |
| - | - |
| `/scoreboard` | Remote scoreboard: scores, players, characters and sets |
| `/stage-strike-app` | Stage strike for the players |
| `/character-select` | Character select for the players |
| `/bracket-focus-app` | What the bracket focus layout zooms to: sets, rounds, a player's run, the set on stream or a tour of the rounds |
| `/admin` | Player database editor |
| `/api/docs` | The web server's endpoints |

## Player database

Players are saved in `user_data/players.db`. You can edit them in the Player DB window,
or from a browser at `/admin`. The first time this version runs, it imports any existing
`local_players.json` and renames that file to `local_players.json.bak`. The Player DB
window can still import and export the JSON format.

## Running from source

HyperDrive uses [uv](https://docs.astral.sh/uv/), which installs Python 3.14 and the
dependencies locked in `uv.lock`:

```sh
uv run main.py
```

`TSH.sh` (Linux and macOS) and `TSH_bat.bat` (Windows) do the same.

The stage strike, character select and remote scoreboard pages are a separate Vite
app in [`stage_strike_app/`](stage_strike_app). Its build is committed, so you only need to
rebuild it if you change it:

```sh
cd stage_strike_app
npm ci
npm run build
```

## Development

```sh
uv run ruff check .    # lint
uv run ruff format .   # format
```

The tests in [`test/`](test) are standalone scripts. Run them from the repository root:

```sh
uv run python test/test_stream_queue.py
```

To work on layouts:

- [`layout/README.md`](layout/README.md) explains how to test layouts in a browser.
- [`docs/layout-data.md`](docs/layout-data.md) describes the data HyperDrive sends to them.

GitHub Actions does the rest:

- `build_app.yml` builds the Windows zip and publishes it as `latest-build`.
- `build_release.yml` turns that build into a versioned release.
- `lint.yml` runs Ruff.
- `update_previews.yml` renders the layout preview images.
- `update_countries.yml` refreshes `assets/countries.json` every week.

## Credits

- [TournamentStreamHelper](https://github.com/joaorb64/TournamentStreamHelper) by
  João Ribeiro Bezerra and its contributors. HyperDrive is MIT licensed, like TSH; see
  [`LICENSE`](LICENSE).
- Country flags from [hampusborgos/country-flags](https://github.com/hampusborgos/country-flags),
  which are public domain. See [`assets/country_flag/README.md`](assets/country_flag/README.md).
- Support the original TSH on its
  [Discord](https://discord.gg/X9Sp2FkcHF) and [Ko-fi](https://ko-fi.com/W7W22YK26).
