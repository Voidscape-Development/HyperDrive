# Checks the stream queue model: start.gg's queues with the changes made by
# hand on top of them.
# Run from the repository root: python test/test_stream_queue.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.TSHStreamQueue import *


def Set(id, state=1):
    return {"id": id, "state": state, "match": f"Set {id}", "team": {}}


def Keys(model, name):
    return [e["key"] for e in model.Queue(name)]


def TestProviderQueues():
    model = StreamQueueModel()
    model.SetProviderQueues({"main": {"1": Set(1), "2": Set(2)}, "side": [Set(3)]})
    assert [s.name for s in model.streams] == ["main", "side"]
    assert Keys(model, "main") == ["set:1", "set:2"]
    assert Keys(model, "MAIN") == ["set:1", "set:2"]

    # Removed streams don't come back, unless added again by hand
    model.RemoveStream("side")
    model.SetProviderQueues({"main": [Set(1)], "side": [Set(3)]})
    assert [s.name for s in model.streams] == ["main"]
    model.AddStream("side")
    assert Keys(model, "side") == ["set:3"]

    model.autoAddStreams = False
    model.SetProviderQueues({"main": [Set(1)], "new": [Set(4)]})
    assert model.GetStream("new") is None


def TestEditing():
    model = StreamQueueModel()
    model.SetProviderQueues({"main": [Set(1), Set(2), Set(3)]})

    model.Move("main", "set:3", -2)
    assert Keys(model, "main") == ["set:3", "set:1", "set:2"]

    model.Remove("main", "set:1")
    assert Keys(model, "main") == ["set:3", "set:2"]

    added = model.AddStartggSet("main", 9, Set(9), index=1)
    assert Keys(model, "main") == ["set:3", "set:9", "set:2"]
    custom = model.AddCustomSet("main", "Team A", "Team B", match="Exhibition")
    assert Keys(model, "main")[-1] == custom
    assert model.Queue("main")[-1]["set"]["team"]["2"]["teamName"] == "Team B"

    # start.gg's queue changes: new sets go after the ones placed by hand,
    # finished ones leave
    model.SetProviderQueues({"main": [Set(2), Set(3), Set(4)]})
    assert Keys(model, "main") == ["set:3", "set:9", "set:2", custom, "set:4"], Keys(model, "main")

    # Added start.gg sets are refreshed and leave once finished
    assert model.AddedSetIds() == ["9"]
    model.SetAddedSetData({"9": Set(9, STATE_COMPLETED)})
    assert "set:9" not in Keys(model, "main")

    model.Remove("main", custom)
    model.ResetOrder("main")
    assert Keys(model, "main") == ["set:2", "set:3", "set:4"]


def TestNextAndFinished():
    model = StreamQueueModel()
    model.SetProviderQueues({"main": [Set(1), Set(2)]})
    config = model.GetStream("main")
    config.scoreboard = 1
    assert model.StreamOfScoreboard(1) is config
    assert model.NextEntry("main")["key"] == "set:1"
    assert model.NextEntry("main", currentSetId=1)["key"] == "set:2"

    model.AddStartggSet("main", 5, Set(5))
    model.SetFinished(5)
    assert "set:5" not in Keys(model, "main")


def TestSaveAndExport():
    model = StreamQueueModel()
    model.SetProviderQueues({"main": [Set(1), Set(2)]})
    model.AddStream("offline")
    model.AddCustomSet("offline", "A", "B")
    model.Move("main", "set:2", -1)
    model.afterSet = AFTER_SET_LOAD_NEXT

    copy = StreamQueueModel.FromDict(model.ToDict())
    copy.SetProviderQueues({"main": [Set(1), Set(2)]})
    assert Keys(copy, "main") == ["set:2", "set:1"]
    assert copy.afterSet == AFTER_SET_LOAD_NEXT
    assert len(copy.Queue("offline")) == 1

    exported = copy.Export(onStream={"main": 2})
    main = exported["byName"]["main"]
    assert [s["position"] for s in main] == [1, 2]
    assert main[0]["onStream"] and not main[1]["onStream"]
    assert exported["streams"][1]["manual"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
