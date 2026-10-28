# Checks values set with StateManager.Set(..., replace=True), which skip
# DeepDiff: the deltas sent to the layouts turn the old state into the new
# one, and the exported files end up the same as a fresh export of the state.
# Run from the repository root: python test/test_state_replace.py
import copy
import os
import sys
import tempfile
import types

os.environ.setdefault("QT_API", "PyQt6")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

import src.StateManager as stateManagerModule
from src.StateManager import StateManager

stateManagerModule.SettingsManager.Get = staticmethod(lambda key, default=None: default)

deltas = []
StateManager.signals.state_updated.connect(lambda message: deltas.extend(message["delta"]))
StateManager.signals.state_big_change.connect(lambda: deltas.append("big"))


def Apply(data, delta):
    """applyDeltas() of layout/include/globals.js"""
    current = data
    for key in delta["path"][:-1]:
        current = current.setdefault(key, {})
    if delta["action"] == "dictionary_item_removed":
        current.pop(delta["path"][-1], None)
    else:
        current[delta["path"][-1]] = delta["value"]


def Files(folder):
    """{path: content} of the exported files"""
    result = {}
    for root, _, files in os.walk(folder):
        for name in files:
            if name.startswith("program_state.json"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as file:
                result[os.path.relpath(path, folder)] = file.read()
    return result


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
    folder = tempfile.mkdtemp()
    os.chdir(folder)
    os.makedirs("out")
    StateManager.state = {}
    StateManager.lastSavedState = {}
    StateManager.changedPaths = []
    StateManager.replacedPaths = set()
    deltas.clear()


def Check(old):
    applied = copy.deepcopy(old)
    for delta in deltas:
        assert delta != "big", deltas
        Apply(applied, delta)
    assert applied == StateManager.state, (applied, StateManager.state)
    assert StateManager.lastSavedState == StateManager.state

    exported = Files("out")
    # CreateFilesDict writes to ./out: compare with a folder of its own
    os.makedirs("fresh/out")
    os.chdir("fresh")
    for key, value in StateManager.state.items():
        StateManager.CreateFilesDict(key, value)
    fresh = Files("out")
    assert exported == fresh, (exported, fresh)


def Swap(parentToo=False):
    Reset()
    with StateManager.SaveBlock():
        StateManager.Set("score.1.last_sets.1", Stats(1, 5))
        StateManager.Set("score.1.last_sets.2", Stats(2, 3))
        StateManager.Set("score.1.last_sets.3", {"x": {"y": 1}})
        StateManager.Set("score.1.name", "a")
    old = copy.deepcopy(StateManager.state)
    deltas.clear()

    with StateManager.SaveBlock():
        stats1 = StateManager.Get("score.1.last_sets.1")
        stats2 = StateManager.Get("score.1.last_sets.2")
        StateManager.Set("score.1.last_sets.1", stats2, replace=True)
        StateManager.Set("score.1.last_sets.2", stats1, replace=True)
        # A dict becoming a value (whose old files the diff's export leaves
        # behind, so only when replaced), and an unchanged one
        if not parentToo:
            StateManager.Set("score.1.last_sets.3", {"x": 2}, replace=True)
        StateManager.Set("score.1.unchanged", {"z": 1})
        StateManager.Set("score.1.name", "b")
        if parentToo:
            StateManager.Set("score.1.last_sets", dict(StateManager.Get("score.1.last_sets")))
    return old


def TestReplace():
    old = Swap()
    replaced = {tuple(d["path"]) for d in deltas if d["action"] == "values_changed"}
    assert ("score", "1", "last_sets", "1") in replaced, deltas
    assert ("score", "1", "last_sets", "2") in replaced, deltas
    Check(old)


def TestReplaceUnderChangedParent():
    # The parent was set too: the diff takes the replaced values
    old = Swap(parentToo=True)
    Check(old)


def TestReplaceSameValue():
    Reset()
    StateManager.Set("score.1.last_sets.1", Stats(1, 2))
    deltas.clear()
    StateManager.Set("score.1.last_sets.1", Stats(1, 2), replace=True)
    assert deltas == [], deltas


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
