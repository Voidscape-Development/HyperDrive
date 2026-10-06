# HyperDrive web app

The pages HyperDrive serves for phones and second screens. It's a React app built
with [Vite](https://vite.dev/), using MUI, Redux Toolkit and socket.io.

| Route | Page | Source |
| - | - | - |
| `/stage-strike-app` | Stage strike for the players | [`src/StageStrikePage`](src/StageStrikePage) |
| `/character-select` | Character select for the players | [`src/CharacterSelectPage`](src/CharacterSelectPage) |
| `/scoreboard` | Remote scoreboard | [`src/ScoreboardPage`](src/ScoreboardPage) |

Any other path goes to `/stage-strike-app`.

HyperDrive serves the compiled app from `build/` on its web server (port 5500 by
default). The app gets its data from that server, partly through a socket.io connection
([`src/websocketConnection.ts`](src/websocketConnection.ts)) and partly through HTTP
endpoints, which are listed at `/api/docs`.

## Development

Use the Node.js LTS version, which is what CI builds with.

```sh
npm ci
npm run dev
```

1. Start HyperDrive (`uv run main.py` from the repository root).
2. Open the pages from the Vite dev server: `http://localhost:3000/stage-strike-app`,
   `/character-select` or `/scoreboard`.

The dev server reloads as you edit and forwards API, socket.io and asset requests to
HyperDrive (see `PROXIED_PATHS` in [`vite.config.js`](vite.config.js)). If you've changed
HyperDrive's web server port, set `TSH_PORT` in a `.env.local` file:

```sh
TSH_PORT=5600
```

When the app calls a new endpoint, add its path to `PROXIED_PATHS`.

## Building

```sh
npm run build
```

This writes the app to `build/`, where HyperDrive serves it from. `build/` is committed.
On every push to `main`, the "Build the application" workflow rebuilds it and commits the
result as "Update frontend". You only need to build locally to test your changes in
HyperDrive itself, or to run HyperDrive from source with them.

## Translations

The page text is in [`src/i18n/locales`](src/i18n/locales), one JSON file per language. To
add a language, add its file, then add it to both `resources` and `SUPPORTED_LANGUAGES`
in [`src/i18n/config.js`](src/i18n/config.js).

The character select and scoreboard pages use the language in the `?lng=` query
parameter, otherwise the browser's language, and fall back to English. The stage strike
page has its own language selector, saved in the browser. With "Auto" on, it switches to
each player's language during their strikes, based on their country (`COUNTRY_LANGUAGE`
in [`src/StageStrikePage/index.jsx`](src/StageStrikePage/index.jsx)).
