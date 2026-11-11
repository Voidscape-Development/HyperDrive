# Shared by the tests of StateManager: how the clients apply the state
# deltas they're sent, a client replica fed by StateManager's
# signals, and what's needed to check the files exported to out/.
import json
import os
import shutil
import sys
import tempfile
import types

os.environ.setdefault("QT_API", "PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = os.path.abspath(".")
sys.path.insert(0, REPO)
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.join(REPO, "src")]
sys.modules["src"] = package

# StateManager writes ./out and SettingsManager ./user_data: not the repository's
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data")

import orjson
from qtpy.QtCore import Qt

from src.StateManager import StateManager

sys.path.insert(0, os.path.join(REPO, "test"))
from state_protocol import apply_deltas

# The only actions the clients are sent. They all remove the key at the path
# for REMOVED and set the value at the path for anything else.
ACTIONS = {"dictionary_item_added", "values_changed", "dictionary_item_removed"}
REMOVED = "dictionary_item_removed"


def Wire(value):
    """value as a client gets it: encoded the way the web server does
    (SocketioJson in src/WebServer.py) and decoded from JSON."""
    return json.loads(orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS))


def _Key(key):
    # JavaScript's object keys are strings: o[1] is o["1"]
    return key if isinstance(key, str) else str(key)


def ApplyShared(state, delta):
    """applyDeltas() of layout/include/state_client.js, which the layouts,
    the web app and the Stream Deck plugin all run: its Python port, held to
    the same fixture as the JavaScript by test_state_protocol.py. It raises
    on a delta the clients would answer by fetching the whole state."""
    applied = apply_deltas(state, [delta])
    state.clear()
    state.update(applied)


def ApplyStrict(state, delta):
    """What every client does when nothing unusual is asked of it: the
    deltas never go through a missing key or a value that isn't an object,
    never remove a missing key and never go into a list."""
    assert set(delta) <= {"path", "action", "value"}, delta
    assert delta["action"] in ACTIONS, delta
    assert len(delta["path"]) > 0, delta
    assert ("value" in delta) == (delta["action"] != REMOVED), delta
    node = state
    for key in delta["path"][:-1]:
        node = node[_Key(key)]
        assert isinstance(node, dict), delta
    last = _Key(delta["path"][-1])
    if delta["action"] == REMOVED:
        del node[last]
    else:
        assert (last in node) == (delta["action"] == "values_changed"), delta
        node[last] = delta["value"]


CLIENTS = [ApplyShared, ApplyStrict]


class Replica:
    """The state as each kind of client has it, from what StateManager's
    signals send: deltas (state_updated), or a note to fetch the whole state
    (state_big_change), numbered one by one."""

    def __init__(self):
        self.messages = []  # The deltas sent, and "big" for whole states
        # True while the messages don't reach the clients (the web server
        # can't encode them), which then have to fetch the whole state
        self.lost = False
        self.deltaIndex = StateManager.deltaIndex
        self.Resync()
        # Direct: called by the thread that saves, as it saves. Qt would
        # otherwise queue what other threads send for this thread's event
        # loop, which gets to it after what this thread sent meanwhile.
        direct = Qt.ConnectionType.DirectConnection
        StateManager.signals.state_updated.connect(self.OnUpdate, direct)
        StateManager.signals.state_big_change.connect(self.OnBigChange, direct)

    def Resync(self):
        self.states = [Wire(StateManager.state) for _ in CLIENTS]

    def Reset(self):
        self.messages.clear()
        self.deltaIndex = StateManager.deltaIndex
        self.Resync()

    def OnUpdate(self, message):
        assert set(message) == {"delta_index", "delta"}, message
        assert message["delta_index"] == self.deltaIndex + 1, (message, self.deltaIndex)
        assert message["delta_index"] == StateManager.deltaIndex
        assert 0 < len(message["delta"]) <= StateManager.MAX_DELTA, len(message["delta"])
        self.deltaIndex = message["delta_index"]
        self.messages.append(message["delta"])
        if self.lost:
            return
        for apply, state in zip(CLIENTS, self.states):
            # Each client decodes its own
            for delta in Wire(message)["delta"]:
                apply(state, delta)

    def OnBigChange(self):
        # The web server sends {"state": ..., "delta_index": ...} to everyone
        assert StateManager.deltaIndex >= self.deltaIndex
        self.deltaIndex = StateManager.deltaIndex
        self.messages.append("big")
        self.Resync()

    def Check(self):
        """Every client has the state, and so has everything saved."""
        expected = Wire(StateManager.state)
        for apply, state in zip(CLIENTS, self.states):
            assert state == expected, (apply.__name__, state, expected)
        assert self.deltaIndex == StateManager.deltaIndex
        assert Wire(StateManager.lastSavedState) == expected, (
            StateManager.lastSavedState,
            StateManager.state,
        )
        assert StateManager.changedPaths == []


def Files(folder="out"):
    """{path: content} of the exported files"""
    result = {}
    for root, _, files in os.walk(folder):
        for name in files:
            if name.startswith("program_state.json"):
                continue
            path = os.path.join(root, name)
            with open(path, "rb") as file:
                result[os.path.relpath(path, folder).replace(os.sep, "/")] = file.read()
    return result


def FreshFiles():
    """The files an export of the whole state to an empty out/ makes."""
    os.rename("out", "out.kept")
    try:
        os.makedirs("out")
        for key, value in StateManager.state.items():
            StateManager.CreateFilesDict(str(key).replace("/", "_"), value)
        return Files()
    finally:
        shutil.rmtree("out")
        os.rename("out.kept", "out")


def SavedJson():
    with open("out/program_state.json", "rb") as file:
        state = json.loads(file.read())
    state.pop("timestamp", None)
    return state


def CheckExport():
    """out/ has the files of the state, no more and no less, and
    program_state.json has the state."""
    exported, fresh = Files(), FreshFiles()
    assert exported == fresh, (
        {k: v for k, v in exported.items() if fresh.get(k) != v},
        {k: v for k, v in fresh.items() if exported.get(k) != v},
    )
    assert SavedJson() == Wire(StateManager.state)


def ResetState():
    """An empty state in an empty folder."""
    os.chdir(tempfile.mkdtemp())
    os.makedirs("out")
    os.makedirs("user_data")
    with StateManager.lock:
        StateManager.state = {}
        StateManager.lastSavedState = {}
        StateManager.changedPaths = []
        StateManager.saveBlocked = 0
        StateManager.saveBlockedSince = None
        StateManager.savePending = False


def RunTests(namespace):
    tests = [v for k, v in list(namespace.items()) if k.startswith("Test") and callable(v)]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
