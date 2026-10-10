"""Finishes the sets the data providers return for completed_sets.

The providers give each player of a set's winner_team/loser_team their raw
"country_code", "state_code" and "character_keys" (the keys of the characters
they played, in order of first use). Finish() turns those into what the
layouts use: country/state dicts with flag assets (from the local player
database when the provider has no location) and character dicts with assets,
and adds each set's upset_factor."""

import os

from .SeedPerformance import DOUBLE_ELIMINATION, SINGLE_ELIMINATION, PlacementRounds


def UpsetFactor(bracket_type, winner_seed, loser_seed):
    """Placement rounds the winner was expected to finish below the loser
    (0 when the better or an equal seed won, or the seeds are unknown).
    Like the SPR, types the math doesn't cover (round robin, swiss) count as
    double elimination."""
    try:
        winner_seed = int(winner_seed)
        loser_seed = int(loser_seed)
    except (TypeError, ValueError):
        return 0
    if winner_seed <= 0 or loser_seed <= 0 or winner_seed <= loser_seed:
        return 0
    if bracket_type != SINGLE_ELIMINATION:
        bracket_type = DOUBLE_ELIMINATION
    return max(
        0, PlacementRounds(bracket_type, winner_seed) - PlacementRounds(bracket_type, loser_seed)
    )


def AddCharacterKey(keys, key):
    """Adds a character key to a player's list, keeping first-use order."""
    if key and key not in keys:
        keys.append(key)


def FinishPlayer(player, location, character):
    """location(prefix, gamertag, country_code, state_code) returns the
    player's (country, state) dicts, character(key) a character dict or None."""
    country, state = location(
        player.get("sponsor"),
        player.get("gamertag"),
        player.pop("country_code", None),
        player.pop("state_code", None),
    )
    player["country"] = country or {}
    player["state"] = state or {}

    characters = {}
    for key in player.pop("character_keys", None) or []:
        data = character(key)
        if data:
            characters[str(len(characters) + 1)] = data
    player["characters"] = characters
    return player


def FinishSets(sets, location, character):
    for set in sets:
        set["bracket_type"] = set.get("bracket_type") or DOUBLE_ELIMINATION
        set["upset_factor"] = UpsetFactor(
            set["bracket_type"], set.get("winner_seed"), set.get("loser_seed")
        )
        for side in ("winner_team", "loser_team"):
            for player in (set.get(side) or {}).values():
                FinishPlayer(player, location, character)
    return sets


def Location(prefix, gamertag, country_code, state_code):
    """The provider's location, or the local player database's when the
    provider has no country for the player."""
    from ..PlayerDB import PlayerDB
    from ..PlayerDBModels import MakeTag
    from .CountryHelper import CountryHelper

    if not country_code:
        saved = PlayerDB.GetPlayer(MakeTag(prefix, gamertag)) or {}
        country_code = saved.get("country_code")
        state_code = saved.get("state_code")

    if not country_code:
        return {}, {}

    country = CountryHelper.GetBasicCountryInfo(country_code)
    state = {}
    states = (CountryHelper.countries.get(country_code) or {}).get("states") or {}
    if state_code and state_code in states:
        state = dict(states[state_code])
        # Windows can't have a file named CON.png
        path = f"./assets/state_flag/{country_code}/{'_CON' if state_code == 'CON' else state_code}.png"
        state["asset"] = path if os.path.exists(path) else None
    return country, state


def Character(key):
    from ..GameAssetManager import GameAssetManager

    info = (GameAssetManager.instance.characters or {}).get(key)
    if not info:
        return None
    codename = info.get("codename", key)
    return {
        "name": info.get("display_name", codename),
        "en_name": key,
        "codename": codename,
        "assets": GameAssetManager.instance.GetCharacterAssets(codename, 0),
    }


def Finish(sets):
    return FinishSets(sets, Location, Character)
