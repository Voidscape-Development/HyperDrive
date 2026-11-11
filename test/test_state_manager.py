# Checks what StateManager sends and exports as the state changes: after any
# sequence of Set() and Unset() (random ones too, from several threads too)
# the deltas applied the way each client applies them give the state, the
# files of out/ are the ones a fresh export of the state would make, and
# program_state.json has the state. Also the save blocks and their watchdog,
# the scheduled saves, and that a failed export doesn't stop the next ones.
# Run from the repository root: python test/test_state_manager.py
import copy
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.abspath("test"))
from loguru import logger
from state_harness import (
    CheckExport,
    Files,
    Replica,
    ResetState,
    RunTests,
    SavedJson,
    Wire,
)

import src.StateManager as stateManagerModule
from src.SettingsManager import SettingsManager
from src.StateManager import StateManager

SettingsManager.SaveSettings = lambda: None
# The errors these tests cause are logged
logger.remove()

replica = Replica()
Set, Unset, Get = StateManager.Set, StateManager.Unset, StateManager.Get


def Reset():
    ResetState()
    SettingsManager.settings = {}
    replica.Reset()
    for name, content in [("img.png", b"png 1"), ("img2.png", b"png 2"), ("doc.txt", b"doc")]:
        with open(name, "wb") as file:
            file.write(content)


def Check():
    replica.Check()
    CheckExport()


def Sent():
    """The deltas sent since the last call, without their values."""
    sent = [
        "big" if m == "big" else [(".".join(map(str, d["path"])), d["action"]) for d in m]
        for m in replica.messages
    ]
    replica.messages.clear()
    return sent


ADDED, CHANGED, REMOVED = "dictionary_item_added", "values_changed", "dictionary_item_removed"


# =====================================================
# WHAT'S SENT AND EXPORTED
# =====================================================
def TestDeltas():
    Reset()
    Set("score.1.team.1.name", "A")
    # A whole message per save, with a number, and nothing but what the clients read
    assert replica.messages == [
        [{"path": ["score"], "action": ADDED, "value": {"1": {"team": {"1": {"name": "A"}}}}}]
    ], replica.messages
    Sent()
    Set("score.1.team.1.name", "B")
    assert Sent() == [[("score.1.team.1.name", CHANGED)]]
    Set("score.1.team.1.name", "B")
    assert Sent() == []
    Set("score.1.team.1", {"name": "B", "score": 0})
    assert Sent() == [[("score.1.team.1.score", ADDED)]]
    Unset("score.1.team.1.name")
    assert replica.messages == [[{"path": ["score", "1", "team", "1", "name"], "action": REMOVED}]]
    assert Sent() and Get("score.1.team.1") == {"score": 0}
    # Unset() of what isn't there makes the dicts on its way, as it always did
    Unset("score.2.team.1.name")
    assert Sent() == [[("score.2", ADDED)]]
    assert Get("score.2") == {"team": {"1": {}}}
    Unset("score.2.team.1.name")
    assert Sent() == []
    # The values sent are copies: the state may change before they're encoded
    Set("list", [{"a": 1}])
    assert replica.messages[0][0]["value"] == [{"a": 1}]
    assert replica.messages[0][0]["value"] is not Get("list")
    assert replica.messages[0][0]["value"][0] is not Get("list")[0]
    Check()


def TestTypes():
    Reset()
    Set("a.v", 1)
    Sent()
    for value in [1.0, True, 1, "1", [1], [1.0], [True], (False,), {"k": 1}, {"k": True}, None, 0]:
        Set("a.v", value)
        assert len(Sent()) == 1, value
        assert type(replica.states[0]["a"]["v"]) is type(Wire(value))
        Check()
    assert Files() == {"a/v.txt": b"0"}
    # The same to a client, so nothing is sent
    Set("a.v", [1, 2])
    Sent()
    Set("a.v", (1, 2))
    assert Sent() == []
    Check()


def TestNone():
    # None is sent like any value (null) and has no file
    Reset()
    Set("a", {"x": 1, "n": None, "d": {"k": None, "j": 2}})
    assert Files() == {"a/x.txt": b"1", "a/d/j.txt": b"2"}
    Set("a.x", None)
    assert replica.messages[-1] == [{"path": ["a", "x"], "action": CHANGED, "value": None}]
    assert Files() == {"a/d/j.txt": b"2"}
    assert SavedJson()["a"] == {"x": None, "n": None, "d": {"k": None, "j": 2}}
    Sent()
    Set("a.x", None)
    assert Sent() == []
    Set("a.n", "text")
    Set("a.new", None)
    Set("a.d", None)
    assert Sent() == [[("a.n", CHANGED)], [("a.new", ADDED)], [("a.d", CHANGED)]]
    assert Files() == {"a/n.txt": b"text"}
    for state in replica.states:
        assert state == {"a": {"x": None, "n": "text", "new": None, "d": None}}
    Unset("a.new")
    assert Sent() == [[("a.new", REMOVED)]]
    # Set() through None (or anything that isn't a dict) makes it a dict, as
    # the layouts do when they're sent a.d.k
    Set("a.d.k", 3)
    Set("a.n.k.j", 4)
    assert Sent() == [[("a.d", CHANGED)], [("a.n", CHANGED)]]
    assert Get("a") == {"x": None, "n": {"k": {"j": 4}}, "d": {"k": 3}}
    assert Files() == {"a/d/k.txt": b"3", "a/n/k/j.txt": b"4"}
    # Unset() through it leaves it alone
    Set("a.n", "text")
    Sent()
    Unset("a.n.k.j")
    Unset("a.x.k")
    assert Sent() == [] and Get("a.n") == "text" and Get("a.x") is None
    Check()


def TestFiles():
    Reset()
    Set("p", {"name": "A", "avatar": "./img.png", "missing": "./missing.png", "n": 5})
    Set("p.site", "http://example.com/page")
    assert Files() == {
        "p/name.txt": b"A",
        "p/avatar.png": b"png 1",
        "p/n.txt": b"5",
        "p/site.txt": b"http://example.com/page",
    }
    # A text becoming a file and back, a file becoming another
    Set("p.name", "./doc.txt")
    Set("p.avatar", "./img2.png")
    Set("p.missing", "./img.png")
    Set("p.site", "text")
    assert Files() == {
        "p/name.txt": b"doc",
        "p/avatar.png": b"png 2",
        "p/missing.png": b"png 1",
        "p/n.txt": b"5",
        "p/site.txt": b"text",
    }
    Set("p.avatar", "plain")
    Set("p.missing", "./missing.png")
    Unset("p.site")
    assert Files() == {"p/name.txt": b"doc", "p/avatar.txt": b"plain", "p/n.txt": b"5"}

    # A dict becoming a value, a value becoming a dict, a list
    Set("p", "gone")
    assert Files() == {"p.txt": b"gone"}
    Set("p", {"a/b": {"c": [1, {"d": None}]}, 5: "int"})
    assert Files() == {"p/a_b/c.txt": b"[1, {'d': None}]", "p/5.txt": b"int"}
    Set("p", {"a/b": {"c": [1, {"d": 2}]}})
    assert Files() == {"p/a_b/c.txt": b"[1, {'d': 2}]"}
    Unset("p")
    assert Files() == {}
    Check()

    # Keys that are sent and saved, but have no files
    assert StateManager.EXPORT_EXCLUDED_PREFIXES == (("game", "stages"),)
    Set("game", {"name": "G", "stages": {"bf": {"name": "BF"}}, "stagesx": 1})
    Set("game.stages.fd.name", "FD")
    assert Sent()[-1] == [("game.stages.fd", ADDED)]
    assert Files() == {"game/name.txt": b"G", "game/stagesx.txt": b"1"}
    Unset("game.stages.bf")
    Set("game.stages", 5)
    Unset("game")
    assert Files() == {}
    Check()

    # Files aren't exported with the setting off; the rest is
    Set("a", 1)
    SettingsManager.settings = {"general": {"disable_export": True}}
    Set("a", 2)
    assert Files() == {"a.txt": b"1"}
    replica.Check()
    assert SavedJson() == {"a": 2}


def TestBigChange():
    Reset()
    index = StateManager.deltaIndex
    with StateManager.SaveBlock():
        for i in range(StateManager.MAX_DELTA):
            Set(f"k{i}", i)
    assert len(replica.messages) == 1 and len(replica.messages[0]) == StateManager.MAX_DELTA
    assert StateManager.deltaIndex == index + 1
    Check()

    # One more than a delta takes, with no dict to send in their place:
    # the clients are told to take the whole state
    Sent()
    with StateManager.SaveBlock():
        for i in range(StateManager.MAX_DELTA + 1):
            Set(f"k{i}", -i - 1)
    assert Sent() == ["big"]
    assert StateManager.deltaIndex == index + 2
    Check()

    # In a dict: the dict is sent, to the clients that subscribed to it
    with StateManager.SaveBlock():
        for i in range(StateManager.MAX_DELTA + 1):
            Set(f"bracket.sets.{i}.score", i)
        Set("other", 1)
    assert Sent() == [[("bracket", ADDED), ("other", ADDED)]]
    with StateManager.SaveBlock():
        for i in range(StateManager.MAX_DELTA + 1):
            Set(f"bracket.sets.{i}.score", -i - 1)
        Set("bracket.name", "B")
    assert Sent() == [[("bracket.sets", CHANGED), ("bracket.name", ADDED)]]
    assert StateManager.deltaIndex == index + 4
    Check()


def TestUnchangedAndUntracked():
    Reset()
    Set("a.b", 1)
    saved = os.path.getmtime("out/program_state.json")
    Sent()
    # Nothing changed: nothing is sent or written
    os.utime("out/program_state.json", (saved - 10, saved - 10))
    Set("a.b", 1)
    StateManager.SaveState()
    with StateManager.SaveBlock():
        pass
    assert Sent() == []
    assert os.path.getmtime("out/program_state.json") == saved - 10

    # A change made without Set() is found by a save with nothing set
    StateManager.state["a"]["c"] = {"d": True}
    StateManager.SaveState()
    assert Sent() == [[("a.c", ADDED)]]
    Check()

    # Values orjson and msgpack don't take are exported as text
    replica.lost = True
    Set("odd", {"set": {1}, "big": 2**70, "object": Ellipsis})
    assert SavedJson()["odd"] == {"set": "{1}", "big": 2**70, "object": "Ellipsis"}
    assert Files()["odd/big.txt"] == str(2**70).encode()
    Set("odd.set", {1})
    Set("odd.set", {2})
    assert Sent() == [[("odd", ADDED)], [("odd.set", CHANGED)]]
    Unset("odd")
    replica.lost = False
    replica.Resync()
    Set("after", 1)
    Check()
    assert Get("after") == 1 and SavedJson()["after"] == 1
    assert Files()["after.txt"] == b"1"


def TestRandom(iterations=400, seed=0, files=True):
    random.seed(seed)
    keys = ["a", "b", "c", "1", "x y", "q'uote", "sl/ash"]
    scalars = [None, None, 0, 1, 1.0, True, False, "", "text", "more", 2.5, float("nan")]
    scalars += ["./img.png", "./img2.png", "./missing.png", "./doc.txt", "http://example.com/page"]

    def Value(depth=0):
        r = random.random()
        if depth < 3 and r < 0.4:
            value = {random.choice(keys): Value(depth + 1) for _ in range(random.randint(0, 4))}
            if random.random() < 0.15:
                value[5] = Value(depth + 1)
            return value
        if r < 0.5:
            return [Value(depth + 1) for _ in range(random.randint(0, 3))]
        if r < 0.53:
            return (1, Value(depth + 1))
        return random.choice(scalars)

    def Change():
        top = random.choice(["score", "game", "game.stages", "bracket", "x"])
        key = ".".join([top] + [random.choice(keys) for _ in range(random.randint(0, 3))])
        current = Get(key)
        r = random.random()
        if r < 0.3 and isinstance(current, dict) and current:
            # The same dict with a few changes, like most Set() calls
            value = copy.deepcopy(current)
            for _ in range(random.randint(0, 3)):
                k = random.choice(list(value.keys()) + keys)
                m = random.random()
                if m < 0.5:
                    value[k] = Value(2)
                elif m < 0.7:
                    value.pop(k, None)
            Set(key, value, replace=random.random() < 0.3)
        elif r < 0.4:
            Set(key, copy.deepcopy(current))
        elif r < 0.5 and isinstance(current, dict):
            # Changed in place then set
            current[random.choice(keys)] = Value(2)
            Set(key, current)
        elif r < 0.85:
            Set(key, Value(1), replace=random.random() < 0.3)
        else:
            Unset(key)

    Reset()
    limit = StateManager.MAX_DELTA
    sent = set()
    try:
        for i in range(iterations):
            if i % 100 == 0:
                Reset()
                SettingsManager.settings = {"general": {"disable_export": not files}}
            # With few changes to a delta, whole dicts and states are sent too
            StateManager.MAX_DELTA = random.choice([limit, 2, 5])
            if random.random() < 0.5:
                Change()
            else:
                with StateManager.SaveBlock():
                    for _ in range(random.randint(0, 12)):
                        Change()
                        if random.random() < 0.1:
                            with StateManager.SaveBlock():
                                Change()
            sent.update("big" if m == "big" else "delta" for m in replica.messages)
            replica.messages.clear()
            if files:
                Check()
            else:
                replica.Check()
                assert Files() == {}
                assert SavedJson() == Wire(StateManager.state)
    finally:
        StateManager.MAX_DELTA = limit
    assert sent == {"big", "delta"}


def TestRandomWithoutFiles():
    # Only the delta is looked for then
    TestRandom(seed=1, files=False)


def TestThreads():
    # Set() and Unset() from several threads, each saving as it goes
    Reset()
    errors = []

    def Work(seed):
        rng = random.Random(seed)
        try:
            for _ in range(150):
                key = ".".join(rng.choice("abc") for _ in range(rng.randint(1, 3)))
                r = rng.random()
                if r < 0.6:
                    Set(f"shared.{key}", rng.choice([1, "v", None, {"k": rng.random()}, [1]]))
                elif r < 0.8:
                    Unset(f"shared.{key}")
                else:
                    with StateManager.SaveBlock():
                        Set(f"shared.{key}", {"a": {"b": seed}})
                        Set(f"own.{seed}.count", rng.random())
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=Work, args=(seed,)) for seed in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [], errors
    assert StateManager.saveBlocked == 0
    Check()


# =====================================================
# SAVE BLOCKS
# =====================================================
def TestSaveBlocks():
    Reset()
    with StateManager.SaveBlock():
        Set("a", 1)
        with StateManager.SaveBlock():
            Set("b", 2)
        Set("a", 3)
        assert Sent() == [] and not os.path.exists("out/program_state.json")
    # Everything set in the block, in one message
    assert Sent() == [[("a", ADDED), ("b", ADDED)]]
    Check()

    # The block is released when what's in it fails
    try:
        with StateManager.SaveBlock():
            Set("c", 1)
            raise ValueError("failed")
    except ValueError:
        pass
    assert StateManager.saveBlocked == 0 and Sent() == [[("c", ADDED)]]

    # One release too many doesn't leave saving off
    StateManager.ReleaseSaving()
    assert StateManager.saveBlocked == 0
    Set("d", 1)
    assert Sent() == [[("d", ADDED)]]

    # A save asked for while another thread holds a block waits for it
    StateManager.BlockSaving()
    Set("e", 1)
    thread = threading.Thread(target=StateManager.SaveState)
    thread.start()
    thread.join()
    assert Sent() == []
    StateManager.ReleaseSaving()
    assert Sent() == [[("e", ADDED)]]
    Check()


def TestWatchdog():
    Reset()
    StateManager.BlockSaving()
    Set("a", 1)
    assert Sent() == [] and StateManager.saveBlocked == 1
    # The block was never released: the next change saves anyway
    StateManager.saveBlockedSince = time.time() - StateManager.DEFAULT_BLOCK_WATCHDOG_SECONDS - 1
    Set("b", 1)
    assert Sent() == [[("a", ADDED), ("b", ADDED)]]
    assert StateManager.saveBlocked == 0 and StateManager.saveBlockedSince is None
    Set("c", 1)
    assert Sent() == [[("c", ADDED)]]

    # Blocks that are meant to last aren't watched, nor any with the setting at 0
    StateManager.BlockSaving(watchdog=False)
    assert StateManager.saveBlockedSince is None
    Set("d", 1)
    assert Sent() == [] and StateManager.saveBlocked == 1
    StateManager.ReleaseSaving()
    SettingsManager.settings = {"general": {"statemanager_block_timeout": 0}}
    StateManager.BlockSaving()
    StateManager.saveBlockedSince = time.time() - 1000
    Set("e", 1)
    assert Sent() == [[("d", ADDED)]] and StateManager.saveBlocked == 1
    StateManager.ReleaseSaving()
    assert Sent() == [[("e", ADDED)]]
    Check()


# =====================================================
# FAILURES
# =====================================================
def TestExportFailures():
    Reset()
    Set("a", {"x": 1, "y": 1})

    # A value whose file can't be written: the others are, it's sent, and
    # the next saves go on
    create = StateManager.CreateFilesDict

    def FailingCreate(path, value):
        if path == "a/x":
            raise OSError("can't write that")
        create(path, value)

    StateManager.CreateFilesDict = FailingCreate
    try:
        Set("a", {"x": 2, "y": 2, "z": 2})
    finally:
        StateManager.CreateFilesDict = create
    assert Sent()[-1] == [("a.x", CHANGED), ("a.y", CHANGED), ("a.z", ADDED)]
    assert Files() == {"a/x.txt": b"1", "a/y.txt": b"2", "a/z.txt": b"2"}
    replica.Check()
    assert SavedJson() == {"a": {"x": 2, "y": 2, "z": 2}}
    Set("a.x", 3)
    Check()

    # program_state.json can't be written
    replace = os.replace
    os.replace = lambda *args: (_ for _ in ()).throw(OSError("disk full"))
    try:
        Set("a.x", 4)
    finally:
        os.replace = replace
    assert Sent() == [[("a.x", CHANGED)], [("a.x", CHANGED)]]
    assert SavedJson()["a"]["x"] == 3 and Files()["a/x.txt"] == b"4"
    # Windows refuses to replace a file that's open: written in place
    os.replace = lambda *args: (_ for _ in ()).throw(PermissionError("in use"))
    try:
        Set("a.x", 5)
    finally:
        os.replace = replace
    assert not os.path.exists("out/program_state.json.tmp")
    Check()

    # The comparison itself fails: everything is sent and saved again
    diff = stateManagerModule.DiffStates
    stateManagerModule.DiffStates = lambda *args: 1 / 0
    try:
        Sent()
        Set("b", 1)
    finally:
        stateManagerModule.DiffStates = diff
    assert Sent() == ["big"]
    replica.Check()
    assert SavedJson() == Wire(StateManager.state)
    Set("b", 2)
    assert Sent() == [[("b", CHANGED)]]
    assert Files()["b.txt"] == b"2"

    # A delta that can't be made: the whole state instead
    clones = stateManagerModule.deep_clones
    stateManagerModule.deep_clones = lambda *args: 1 / 0
    try:
        Set("c", {"k": 1})
    finally:
        stateManagerModule.deep_clones = clones
    assert Sent() == ["big"]
    Set("c.k", 2)
    assert Sent() == [[("c.k", CHANGED)]]
    Check()


def TestLoadState():
    Reset()
    Set("a", {"x": 1})
    with open("out/program_state.json", "wb") as file:
        file.write(b'{"a": {"x": 2}, "notes": "old", "timestamp": 12.5}')
    Sent()
    StateManager.LoadState()
    assert StateManager.load_error is None
    assert StateManager.state == {"a": {"x": 2}} == StateManager.lastSavedState
    assert StateManager.state["a"] is not StateManager.lastSavedState["a"]
    assert Sent() == ["big"]
    Set("a.x", 3)
    assert Sent() == [[("a.x", CHANGED)]]
    replica.Check()
    assert SavedJson() == {"a": {"x": 3}}

    # No file: the state stays
    os.remove("out/program_state.json")
    StateManager.LoadState()
    assert StateManager.load_error is None and StateManager.state == {"a": {"x": 3}}

    for broken in [b'{"a": {"x"', b"", b"[1]"]:
        with open("out/program_state.json", "wb") as file:
            file.write(broken)
        StateManager.LoadState()
        assert StateManager.load_error.startswith("./out/program_state.json\n\n")
        assert StateManager.state == {}
        # What the clients and out/ had is gone
        assert Sent() == [[("a", REMOVED)]]
        Check()
        Set("a.x", 4)
        assert Sent() == [[("a", ADDED)]]
        Check()

    # Even when the state can't be saved until later
    with open("out/program_state.json", "wb") as file:
        file.write(b"{")
    with StateManager.SaveBlock():
        StateManager.LoadState()
        Set("b", 1)
    assert Sent() == [[("a", REMOVED), ("b", ADDED)]]
    Check()
    StateManager.load_error = None


# =====================================================
# SCHEDULED SAVES
# =====================================================
def TestDebounce():
    # Last: from here on there's an application, whose event loop the saves wait for
    from qtpy.QtCore import QCoreApplication

    Reset()
    app = QCoreApplication.instance() or QCoreApplication([])

    def Wait(done, timeout=5):
        end = time.time() + timeout
        while not done() and time.time() < end:
            app.processEvents()
            time.sleep(0.005)
        assert done()

    # Changes made together are saved once, a moment later
    for i in range(5):
        Set(f"a.{i}", i)
    assert replica.messages == [] and StateManager.savePending
    Wait(lambda: replica.messages)
    assert Sent() == [[("a", ADDED)]]
    assert not StateManager.savePending
    Check()

    # A save asked for right away takes them with it
    Set("b", 1)
    StateManager.FlushPendingSave()
    assert Sent() == [[("b", ADDED)]]
    app.processEvents()
    time.sleep(StateManager.SAVE_DEBOUNCE_MS / 1000 * 2)
    app.processEvents()
    assert Sent() == []

    # A block's release saves at once
    with StateManager.SaveBlock():
        Set("c", 1)
    assert Sent() == [[("c", ADDED)]]

    # From another thread, the save is scheduled on the application's
    thread = threading.Thread(target=lambda: [Set(f"d.{i}", i) for i in range(5)])
    thread.start()
    thread.join()
    assert replica.messages == [] and StateManager.savePending
    Wait(lambda: replica.messages)
    assert Sent() == [[("d", ADDED)]]
    Check()


if __name__ == "__main__":
    RunTests(globals())
