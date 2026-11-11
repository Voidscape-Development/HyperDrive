# Checks big values set with StateManager.Set(), with and without
# replace=True (which used to skip a slow diff, and is only kept for its
# callers): the deltas sent to the layouts turn the old state into the new
# one, and the exported files end up the same as a fresh export of the state.
# Run from the repository root: python test/test_state_replace.py
import copy
import os
import sys

sys.path.insert(0, os.path.abspath("test"))
from state_harness import CheckExport, Replica, ResetState, RunTests

from src.StateManager import StateManager

replica = Replica()


def Stats(side, count):
    return {
        str(i): {
            "round_name": f"Round {i}",
            "player_name": f"P{side}",
            "player_score": i if side == 1 else 3,
            "player_char": {"name": f"C{i + side}", "skin": {"color": side}},
        }
        for i in range(1, count + 1)
    }


def Reset():
    ResetState()
    replica.Reset()


def Check():
    assert "big" not in replica.messages, replica.messages
    replica.Check()
    CheckExport()


def Paths():
    return [delta["path"] for message in replica.messages for delta in message]


def Swap(replace, parentToo=False, count=5):
    Reset()
    with StateManager.SaveBlock():
        StateManager.Set("score.1.last_sets.1", Stats(1, count))
        StateManager.Set("score.1.last_sets.2", Stats(2, 3))
        StateManager.Set("score.1.last_sets.3", {"x": {"y": 1}})
        StateManager.Set("score.1.name", "a")
    replica.messages.clear()

    with StateManager.SaveBlock():
        stats1 = StateManager.Get("score.1.last_sets.1")
        stats2 = StateManager.Get("score.1.last_sets.2")
        StateManager.Set("score.1.last_sets.1", stats2, replace=replace)
        StateManager.Set("score.1.last_sets.2", stats1, replace=replace)
        # A dict becoming a value (whose old files have to go), and an
        # unchanged one
        if not parentToo:
            StateManager.Set("score.1.last_sets.3", {"x": 2}, replace=replace)
        StateManager.Set("score.1.unchanged", {"z": 1})
        StateManager.Set("score.1.name", "b")
        if parentToo:
            StateManager.Set("score.1.last_sets", dict(StateManager.Get("score.1.last_sets")))


def TestSwap():
    for replace in (True, False):
        Swap(replace)
        # One message, with only what changed
        assert len(replica.messages) == 1, replica.messages
        assert ["score", "1", "last_sets", "1", "1", "round_name"] not in Paths()
        assert ["score", "1", "last_sets", "1", "1", "player_name"] in Paths()
        assert ["score", "1", "last_sets", "1", "4"] in Paths()
        assert ["score", "1", "last_sets", "3", "x"] in Paths()
        Check()


def TestSwapUnderChangedParent():
    for replace in (True, False):
        Swap(replace, parentToo=True)
        assert len(replica.messages) == 1, replica.messages
        Check()


def TestSwapBig():
    # Too many changes for a delta: the dicts that hold them are sent whole,
    # instead of the whole state to every layout
    for replace in (True, False):
        Swap(replace, count=200)
        assert len(replica.messages) == 1, replica.messages
        assert ["score", "1", "last_sets", "1"] in Paths(), Paths()
        assert ["score", "1", "last_sets", "2"] in Paths(), Paths()
        assert ["score", "1", "name"] in Paths(), Paths()
        Check()


def TestSmallChange():
    # Only a little of it changed: only that is sent
    for replace in (True, False):
        Reset()
        StateManager.Set("score.1.last_sets.1", Stats(1, 5))
        replica.messages.clear()
        stats = copy.deepcopy(StateManager.Get("score.1.last_sets.1"))
        stats["3"]["round_name"] = "Grand Final"
        StateManager.Set("score.1.last_sets.1", stats, replace=replace)
        assert Paths() == [["score", "1", "last_sets", "1", "3", "round_name"]], Paths()
        Check()


def TestSameValue():
    for replace in (True, False):
        Reset()
        StateManager.Set("score.1.last_sets.1", Stats(1, 2))
        replica.messages.clear()
        StateManager.Set("score.1.last_sets.1", Stats(1, 2), replace=replace)
        assert replica.messages == [], replica.messages
        Check()


if __name__ == "__main__":
    RunTests(globals())
