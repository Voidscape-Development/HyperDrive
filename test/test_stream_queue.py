# Checks the stream queue model: start.gg's queues with the changes made by
# hand on top of them, and when their sets should start.
# Run from the repository root: python test/test_stream_queue.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.SetDurations import Durations, EstimateStarts, SetSeconds
from src.StreamQueue import *

MIN = 60


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


def TestDurations():
    sets = [
        {"startedAt": 0, "completedAt": 10 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 12 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 14 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 30 * MIN, "totalGames": 5},
        # Left out: a DQ, a set with no start, one reported hours later
        {"startedAt": 0, "completedAt": 5 * MIN, "totalGames": 3, "dq": True},
        {"startedAt": None, "completedAt": 5 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 10 * 60 * MIN, "totalGames": 3},
    ]
    durations = Durations(sets)
    assert sorted(durations[None]) == [10 * MIN, 12 * MIN, 14 * MIN, 30 * MIN]
    assert SetSeconds(durations, 3) == 12 * MIN
    # Not enough best of 5s yet: every set's
    assert SetSeconds(durations, 5) == 13 * MIN
    assert SetSeconds(durations) == 13 * MIN
    assert SetSeconds({}, 3) is None


def TestEstimateStarts():
    durations = {None: [10 * MIN] * 3, 3: [10 * MIN] * 3, 5: [20 * MIN] * 3}
    now = 100000
    sets = [
        # Started 4 minutes ago: 6 minutes left
        {"state": 2, "best_of": 3, "started_at": now - 4 * MIN},
        {"state": 1, "best_of": 3},
        {"state": 3, "best_of": 3},
        {"state": 1, "best_of": 5},
        {"state": 1, "best_of": 3},
    ]
    result = EstimateStarts(sets, durations, now)
    assert result[0] == (now - 4 * MIN, 0)
    assert result[1] == (now + 6 * MIN, 6)
    # Finished sets have no start time and take no time
    assert result[2] == (None, None)
    assert result[3] == (now + 16 * MIN, 16)
    assert result[4] == (now + 36 * MIN, 36)
    # Without data, nothing can be told
    assert EstimateStarts(sets[1:2], {}, now) == [(None, None)]


def TestEta():
    model = StreamQueueModel()
    model.SetProviderQueues(
        {"main": [{"id": 1, "state": 1, "best_of": 3}, {"id": 2, "state": 1, "best_of": 3}]}
    )
    durations = {None: [10 * MIN] * 3}
    exported = model.Export(onStream={"main": 1}, durations=durations, now=1000)
    main = exported["byName"]["main"]
    # The set on the stream's scoreboard is being played
    assert main[0]["eta_minutes"] == 0
    assert main[0]["state"] == 1
    assert main[1]["eta_minutes"] == 10
    assert exported["average_set_minutes"] == 10
    # Without durations, no times
    assert model.Export()["byName"]["main"][1]["eta"] is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
