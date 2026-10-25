# Getting started

This page takes you from a fresh install to a working scoreboard on stream. It takes about
five minutes. You can come back to it any time from ☰ › **Guide**.

## 1. Pick your game

At the top of the main window, choose your game in the game dropdown. You can type to
filter the list.

If your game isn't listed, or it has no character icons, download its assets: open
[Download assets](hyperdrive://open/download-assets), search for the game, tick the asset
packs you want and click **Download**. See [Game assets](game-assets.md) for more.

## 2. Load your tournament (optional)

HyperDrive works without a tournament: you can type players and scores by hand. Loading
one from start.gg (or parry.gg) fills in players, sets, seeds and brackets for you.

1. Click [Set tournament](hyperdrive://open/set-tournament).
2. Paste the tournament's link, a start.gg short link or its slug, and click **OK**.
3. Pick the event (e.g. *Ultimate Singles*) in the list.

The game is picked for you from the event. See [Tournaments](tournaments.md) for the
details.

## 3. Add a scoreboard to OBS

1. In OBS, add a **Browser** source.
2. Check **Local file** and pick a layout's `.html` file, e.g.
   `layout/scoreboard_simple/index.html` in HyperDrive's folder.
3. Set the width to **1920** and the height to **1080**.

The layout updates live as you change things in HyperDrive. See
[Adding layouts to OBS](obs-setup.md) for the full list of layouts and the options they
take.

## 4. Run a set

Open the [Scoreboard](hyperdrive://open/scoreboard) tab.

- With a tournament loaded, click **Load set from …** and double-click a set. Its players,
  characters, phase and match name are filled in.
- Without one, type the players' tags, pick their characters and set the phase and match.
- Change the score with the arrows next to each team's score. **Swap teams** switches the
  sides.

That's it: the layout in OBS shows everything as you type it.

## Where to go next

- Load the next set on stream automatically with the [Stream queue](stream-queue.md).
- Let the players strike stages from their phones: [Stage strike](stage-strike.md).
- Add commentators: [Commentary](commentary.md).
- Make the layouts match your brand: [Layout themes](layout-themes.md).
- Control everything from a Stream Deck: [Stream Deck](stream-deck.md).

> Tip: everything you set in HyperDrive is saved. Closing and reopening it keeps your
> scoreboard, settings and player database.
