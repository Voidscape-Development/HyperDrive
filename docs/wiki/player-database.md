# Player database

HyperDrive keeps the players you save in a local database (`user_data/players.db`), so
their real name, pronouns, location, socials and mains are filled in whenever you type their
tag, with or without a tournament loaded.

Open it from ☰ › [Player database](hyperdrive://open/player-database). It has five tabs.

## Players

Search, add, edit and delete players.

- **New player** adds one; select a player to edit their sponsor, tag, real name,
  pronouns, socials, country, state and custom text, then **Save** (or **Revert**).
- **Characters**: the player's mains for the selected game. **Add character** adds one.
- **Import JSON** / **Export JSON** read and write the `local_players.json` format of older
  versions, e.g. to share a database.

Players are also saved from the scoreboard with **Save new player** / **Update player** on a
player card. To keep the database from being changed by sets you load, check *Do not
override existing values in the local player database* in
[Settings › Scoreboard](hyperdrive://open/settings/scoreboard).

The database can also be edited from a browser at `http://<address>:5500/admin`.

## Seeds

Open it directly from ☰ › [Seed editor](hyperdrive://open/seed-editor).

Seeds come with the entrants when an event is loaded. Seeds set here replace them on the
scoreboards, and are kept until a different event is loaded. With no event loaded, players
can be seeded by hand.

- Type a **Player tag** and a **Seed**, then **Set seed**.
- **Use imported seed** drops the seeds set by hand for the selected players; **Clear seeds
  set by hand** drops them all.

## Player media

A player's **avatar**, **sponsor logos** and **custom data**: pick a player on the left, or
type a sponsor and tag for someone who isn't in the database.

- **Avatar**: drop an image, or **Choose image…**.
- **Custom data**: any files for the layouts, e.g. `bio.txt`, a stats `.json` or an image.
  Each file reaches the layouts by its name: `bio.txt` becomes `custom.bio`. **New text…**
  writes one here; **Add files…** copies files in; **Open folder** opens the player's folder.

Changes show up on stream within a second. The scoreboard's **Media…** button opens this tab
for a player.

Custom data can be turned off in
[Settings › General](hyperdrive://open/settings/general) (*Export custom player data*). The
layout side is described in `docs/layout-data.md`, under *Custom player data*.

## Logos

- **Sponsor logos**: a player gets the logo of the sponsor typed for them, e.g. `HD`. With
  more than one sponsor (`HD | GG`), the logo of all of them if there is one, otherwise each
  one's.
- **Team logos**: a team on the scoreboard gets the logo named after its team name.

Drop images on either tab to add them.

## Where the files are

Everything is in `user_data/`, which you can also edit by hand:

| Folder | |
| - | - |
| `user_data/players.db` | The player database |
| `user_data/player_avatar/` | Avatars |
| `user_data/sponsor_logo/` | Sponsor logos |
| `user_data/team_logo/` | Team logos |
| `user_data/custom_player_export/` | Custom data, a folder per player |

Copy `user_data/` to keep your players when you update HyperDrive (see
[Troubleshooting](troubleshooting.md#updating-hyperdrive)).
