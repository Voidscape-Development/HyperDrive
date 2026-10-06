# Checks what the bracket focus layout zooms to (bracket.focus): sets and
# rounds picked by hand, a player's run, the set on a scoreboard and the
# round tour, from the sample bracket the layout previews use.
# Run from the repository root: python test/test_bracket_focus.py
import json
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package
helpers = types.ModuleType("src.Helpers")
helpers.__path__ = [os.path.abspath("src/Helpers")]
sys.modules["src.Helpers"] = helpers

from src.Helpers.TSHBracketFocusHelper import *

with open("scripts/previews/sample_state.json", encoding="utf-8") as f:
    SAMPLE = json.load(f)
BRACKET = SAMPLE["bracket"]["bracket"]


def Team(*names, teamName=""):
    return {
        "teamName": teamName,
        "player": {str(i + 1): {"name": n, "mergedName": n} for i, n in enumerate(names)},
    }


def TestNormalize():
    assert NormalizeRequest(None) == {"mode": MODE_ALL}
    assert NormalizeRequest({"mode": "nope", "sets": ["m1"]}) == {"mode": MODE_ALL}
    assert NormalizeRequest({"mode": "sets", "sets": ["m1", None, ""]}) == {
        "mode": MODE_SETS,
        "sets": ["m1"],
        "rounds": [],
    }
    assert NormalizeRequest({"mode": "player", "player": "3"})["player"] == 3
    assert NormalizeRequest({"mode": "player", "player": "x"})["player"] is None
    assert NormalizeRequest({"mode": "follow", "scoreboard": "0"})["scoreboard"] == 1
    assert NormalizeRequest({"mode": "tour", "interval": 1})["interval"] == MIN_INTERVAL
    assert NormalizeRequest({"mode": "tour", "interval": None})["interval"] == DEFAULT_INTERVAL


def TestChannelNames():
    assert NormalizeChannelName("  Losers   cam ") == "Losers cam"
    # Dots would split the state key
    assert NormalizeChannelName("stream.2") == "stream 2"
    assert NormalizeChannelName(" . ") == ""
    assert NormalizeChannelName(None) == ""
    assert len(NormalizeChannelName("x" * 100)) == MAX_CHANNEL_NAME


def TestAll():
    focus = Resolve(BRACKET, {"mode": "all"})
    assert focus["sets"] == [] and focus["rounds"] == [] and focus["label"] == ""
    # Nothing loaded yet
    assert Resolve({}, {"mode": "rounds", "rounds": ["winners:1"]})["sets"] == []


def TestSetsAndRounds():
    focus = Resolve(BRACKET, {"mode": "sets", "sets": ["m9", "gone", "m1"]})
    # Sets that aren't in the bracket are left out, the rest in its order
    assert focus["sets"] == ["m1", "m9"], focus
    assert focus["label"] == ""

    focus = Resolve(BRACKET, {"mode": "sets", "sets": ["m1"]})
    assert focus["label"] == BRACKET["sets"]["m1"]["roundName"]

    focus = Resolve(BRACKET, {"mode": "rounds", "rounds": ["winners:3", "winners:4"]})
    assert focus["sets"] == ["m13", "m14", "m15"], focus
    assert focus["rounds"] == ["winners:3", "winners:4"]
    assert focus["label"] == "Winners Semi-Final, Winners Final"

    # Rounds and sets together
    focus = Resolve(BRACKET, {"mode": "sets", "sets": ["m1"], "rounds": ["winners:4"]})
    assert focus["sets"] == ["m1", "m15"], focus
    assert focus["rounds"] == ["winners:4"]
    # Not named after the round: there's more in focus
    assert focus["label"] == ""


def TestPlayer():
    focus = Resolve(BRACKET, {"mode": "player", "player": 1})
    # Every set of the player, winners side first
    assert focus["sets"][0] == "m1"
    for id in focus["sets"]:
        assert any(p.get("id") == 1 for p in BRACKET["sets"][id]["players"])
    assert focus["label"] == "Azure"
    assert Resolve(BRACKET, {"mode": "player", "player": 999})["sets"] == []


def TestFollow():
    sets = BRACKET["sets"]
    # By the players' names, either way round: the unfinished set first
    score = {"team": {"1": Team("Kestrel"), "2": Team("Azure")}}
    id = FollowSet(BRACKET, score)
    assert id is not None
    names = {p["name"] for p in sets[id]["players"]}
    assert names == {"Azure", "Kestrel"}, names
    unfinished = [
        s
        for s in sets.values()
        if {p["name"] for p in s["players"]} == names and not s["completed"]
    ]
    if unfinished:
        assert not sets[id]["completed"]

    # Names are compared without case and extra spaces
    assert FollowSet(BRACKET, {"team": {"1": Team(" azure "), "2": Team("KESTREL")}}) == id

    # By start.gg set id first
    bracket = json.loads(json.dumps(BRACKET))
    bracket["sets"]["m1"]["startggId"] = 12345
    assert FollowSet(bracket, {"set_id": "12345", "team": score["team"]}) == "m1"

    # Not in the bracket
    assert FollowSet(BRACKET, {"team": {"1": Team("Nobody"), "2": Team("Azure")}}) is None
    assert FollowSet(BRACKET, {}) is None

    focus = Resolve(BRACKET, {"mode": "follow", "scoreboard": 1}, score)
    assert focus["sets"] == [id] and focus["scoreboard"] == 1
    assert Resolve(BRACKET, {"mode": "follow"}, {})["sets"] == []


def TestTour():
    steps = TourSteps(BRACKET)
    # The whole bracket, then each round: winners, losers, grand finals
    assert steps[0]["sets"] == []
    keys = [s["rounds"][0] for s in steps[1:]]
    assert keys[0] == "winners:1"
    assert keys.index("losers:1") > keys.index("winners:4")
    assert keys[-1].startswith("grand_final")

    focus = Resolve(BRACKET, {"mode": "tour"}, step=1)
    assert focus["rounds"] == ["winners:1"] and focus["steps"] == len(steps)
    # Goes round
    assert Resolve(BRACKET, {"mode": "tour"}, step=len(steps))["step"] == 0


def TestNextRound():
    assert NextRound(BRACKET, {"sets": []}) == {"mode": MODE_ROUNDS, "rounds": ["winners:1"]}
    assert NextRound(BRACKET, {"sets": []}, -1)["rounds"] == ["grand_final:2"]
    assert NextRound(BRACKET, {"rounds": ["winners:1"]})["rounds"] == ["winners:2"]
    assert NextRound(BRACKET, {"rounds": ["winners:1"]}, -1)["rounds"] == ["grand_final:2"]
    # From a set, the round after its own
    assert NextRound(BRACKET, {"sets": ["m13"]})["rounds"] == ["winners:4"]
    assert NextRound({}, {}) == {"mode": MODE_ALL}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
