# Checks how the completed sets pulled from start.gg / parry.gg are finished
# for the completed_sets layouts: upset factors, flags and characters.
# Run from the repository root: python test/test_completed_sets.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.Helpers.CompletedSetsHelper import AddCharacterKey, FinishSets, UpsetFactor
from src.Helpers.SeedPerformance import DOUBLE_ELIMINATION, SINGLE_ELIMINATION


def TestUpsetFactor():
    # The better seed winning isn't an upset
    assert UpsetFactor(DOUBLE_ELIMINATION, 1, 4) == 0
    assert UpsetFactor(DOUBLE_ELIMINATION, 3, 3) == 0
    # Seeds expected to finish in the same placement: no upset
    assert UpsetFactor(DOUBLE_ELIMINATION, 16, 13) == 0
    assert UpsetFactor(DOUBLE_ELIMINATION, 9, 8) == 1
    assert UpsetFactor(DOUBLE_ELIMINATION, 11, 6) == 2
    # Single elimination counts fewer rounds
    assert UpsetFactor(SINGLE_ELIMINATION, 11, 6) == 1
    # Round robin, swiss and unknown types count as double elimination
    assert UpsetFactor("ROUND_ROBIN", 11, 6) == 2
    assert UpsetFactor(None, 11, 6) == 2
    # Seeds can come in as strings; unknown seeds aren't upsets
    assert UpsetFactor(DOUBLE_ELIMINATION, "11", "6") == 2
    assert UpsetFactor(DOUBLE_ELIMINATION, 0, 6) == 0
    assert UpsetFactor(DOUBLE_ELIMINATION, None, 6) == 0


def TestAddCharacterKey():
    keys = []
    for key in ["Fox", "Falco", "Fox", None, "Marth"]:
        AddCharacterKey(keys, key)
    assert keys == ["Fox", "Falco", "Marth"]


def TestFinishSets():
    locations = []

    def location(prefix, gamertag, country_code, state_code):
        locations.append((prefix, gamertag, country_code, state_code))
        if country_code:
            return {"code": country_code}, {"code": state_code} if state_code else {}
        # Not in the provider: what the local player database would have
        return ({"code": "JP"}, {}) if gamertag == "Local" else ({}, {})

    def character(key):
        return {"en_name": key} if key != "Unknown" else None

    sets = FinishSets(
        [
            {
                "winner_seed": 11,
                "loser_seed": 6,
                "winner_team": {
                    1: {
                        "sponsor": "HD",
                        "gamertag": "Azure",
                        "country_code": "BR",
                        "state_code": "SP",
                        "character_keys": ["Palutena", "Unknown", "Sonic"],
                    }
                },
                "loser_team": {
                    1: {"sponsor": "", "gamertag": "Local", "character_keys": []},
                    2: {"sponsor": "", "gamertag": "Nobody"},
                },
            }
        ],
        location,
        character,
    )

    s = sets[0]
    assert s["upset_factor"] == 2
    assert s["bracket_type"] == DOUBLE_ELIMINATION

    winner = s["winner_team"][1]
    assert winner["country"] == {"code": "BR"}
    assert winner["state"] == {"code": "SP"}
    # Characters the game doesn't have are left out, the others numbered in order
    assert winner["characters"] == {"1": {"en_name": "Palutena"}, "2": {"en_name": "Sonic"}}
    # The raw fields are only for building these
    for key in ("country_code", "state_code", "character_keys"):
        assert key not in winner

    assert s["loser_team"][1]["country"] == {"code": "JP"}
    assert s["loser_team"][2] == {
        "sponsor": "",
        "gamertag": "Nobody",
        "country": {},
        "state": {},
        "characters": {},
    }
    assert locations[0] == ("HD", "Azure", "BR", "SP")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
