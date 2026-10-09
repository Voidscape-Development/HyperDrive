# HyperDrive Stream Deck plugin

A Stream Deck plugin for HyperDrive, built with Elgato's
[Stream Deck SDK](https://docs.elgato.com/streamdeck/sdk/introduction/getting-started) (Node.js
and TypeScript). See the main [README](../README.md#stream-deck-plugin) for what it does.

## How it works

The plugin keeps one connection to HyperDrive's web server (port 5500 by default):

- **State**: socket.io, like the layouts. HyperDrive sends the whole program state when the
  plugin connects (`program_state`), then the changes (`program_state_update`), which are
  applied as in `layout/include/globals.js`. A missed change makes it ask for the whole state
  again. Every key and dial is redrawn from the state when it changes.
- **Commands**: the web server's links (`/scoreboard1-team1-scoreup`,
  `/display/folder/<folder>/toggle`...), whose answer tells a refused command apart, so the
  key shows an alert. They're all in [`src/hyperdrive/commands.ts`](src/hyperdrive/commands.ts).

The keys and touch strips are SVG drawn by the plugin ([`src/render`](src/render)), from what
[`src/views.ts`](src/views.ts) makes of the action's settings and the state.

| | |
| - | - |
| `src/plugin.ts` | Registers the actions and connects to HyperDrive with the address in the plugin's global settings |
| `src/actions/` | The actions. `base.ts` has what they share: drawing, holding a key, alerts, the property inspectors' lists |
| `src/hyperdrive/` | The connection, the state and what's read from it, the links |
| `com.voidscape.hyperdrive.sdPlugin/` | The plugin as installed: `manifest.json`, `en.json`, the property inspectors in `ui/` (with [sdpi-components](https://sdpi-components.dev) v4), the dial layout, images. `bin/` is built |
| `scripts/generate-images.ts` | Writes the action list icons and the keys' first images |

## Developing

Needs Node.js 24.

```sh
cd streamdeck
npm install
npm run check      # typecheck, tests, build and validate
npm run pack       # dist/com.voidscape.hyperdrive.streamDeckPlugin
```

To work on it with Stream Deck installed, link the plugin folder once and rebuild on changes
(Stream Deck restarts the plugin after each build):

```sh
npx streamdeck link com.voidscape.hyperdrive.sdPlugin
npm run watch
```

The plugin's log is in `com.voidscape.hyperdrive.sdPlugin/logs/`. To debug it with an
inspector, add `"Debug": "enabled"` to `Nodejs` in `manifest.json` (not in a release).

After changing an icon in `src/render/icons.ts`, run `npm run images`.

[`build_streamdeck.yml`](../.github/workflows/build_streamdeck.yml) checks and packs the plugin
for pull requests and pushes to main, where it adds `HyperDrive.streamDeckPlugin` to the
`latest-build` release. Bump `Version` in `manifest.json` for a new version of the plugin.

## Translations

The plugin's text (action names, what the keys show) is in
`com.voidscape.hyperdrive.sdPlugin/en.json`, the property inspectors' in `ui/locales.js`. To
add a language Stream Deck supports (`de`, `es`, `fr`, `ja`, `ko`, `zh_CN`, `zh_TW`), copy
`en.json` to `<language>.json` and translate it, and add the language to `ui/locales.js`.
