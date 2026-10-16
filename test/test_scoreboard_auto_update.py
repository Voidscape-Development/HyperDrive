# Checks how a scoreboard takes a new set (NewSetSelected): a set picked in
# the set list with "Keep scores updated" off, and a stream or station
# tracked from its next set, which leaves the set on it when tracking starts.
# Run from the repository root: python test/test_scoreboard_auto_update.py
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import src.ScoreboardWidget as scoreboardModule
from src.ScoreboardWidget import ScoreboardWidget
from src.TrackingBar import *

# What the scoreboard did: ("load", set id), ("start"|"stop", job), ("stopped",)
calls = []
scoreboardModule.Scheduler.instance = types.SimpleNamespace(
    Start=lambda job: calls.append(("start", job)),
    Stop=lambda job: calls.append(("stop", job)),
)
scoreboardModule.TournamentDataManager.instance = types.SimpleNamespace(
    GetMatch=lambda mainWindow, setId, **kwargs: calls.append(("load", setId))
)
scoreboardModule.SettingsManager.Get = staticmethod(lambda key, default=None: default)
scoreboardModule.StateManager.Set = staticmethod(lambda *args: None)
scoreboardModule.StateManager.Unset = staticmethod(lambda *args: None)


class Ignored:
    """Takes any call and does nothing"""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class Scoreboard:
    """Just what NewSetSelected uses of a scoreboard"""

    autoUpdateJob = "job"
    scoreboardNumber = 1
    playerWidgets = []
    gameReport = Ignored()
    signals = types.SimpleNamespace(NewSetLoaded=Ignored())
    RefreshTrackingBar = ScoreboardWidget.RefreshTrackingBar

    def __init__(self):
        self.lastSetSelected = None
        self.lastStationSelected = {"identifier": "main", "type": "stream"}
        self.waitForNextSet = False
        self.autoUpdateData = None
        self.trackedSet = None
        self.trackingBar = TrackingBar()

    def CommandClearAll(self, **kwargs):
        pass

    def ClearScore(self):
        pass

    def StopAutoUpdate(self, clear_variables=False):
        calls.append(("stopped",))

    def Select(self, data):
        ScoreboardWidget.NewSetSelected(self, data)


def Loaded():
    return [c[1] for c in calls if c[0] == "load"]


def TestWaitForNextSet():
    calls.clear()
    scoreboard = Scoreboard()
    scoreboard.waitForNextSet = True
    # The set on the stream when tracking starts isn't loaded, but it's
    # followed from then on
    scoreboard.Select({"id": 5, "auto_update": "stream"})
    assert Loaded() == [] and ("start", "job") in calls
    assert scoreboard.waitForNextSet is False
    scoreboard.Select({"id": 5, "auto_update": "stream"})
    assert Loaded() == []
    scoreboard.Select({"id": 6, "auto_update": "stream"})
    assert Loaded() == [6]

    # Nothing on it when tracking starts: its first set loads
    calls.clear()
    scoreboard = Scoreboard()
    scoreboard.waitForNextSet = True
    scoreboard.Select({"auto_update": "station"})
    scoreboard.Select({"id": 7, "auto_update": "station"})
    assert Loaded() == [7]

    # Not waiting: the set on it now loads
    calls.clear()
    scoreboard = Scoreboard()
    scoreboard.Select({"id": 5, "auto_update": "stream"})
    assert Loaded() == [5]


def TestKeepUpdated():
    # Off: the set loads, without updates, and the previous set's stop
    calls.clear()
    scoreboard = Scoreboard()
    scoreboard.Select({"id": 8, "auto_update": "set", "keep_updated": False})
    assert Loaded() == [8] and ("stopped",) in calls
    assert not any(c[0] == "start" for c in calls) and scoreboard.autoUpdateData is None

    # On: updated even with the setting off
    calls.clear()
    get = scoreboardModule.SettingsManager.Get
    scoreboardModule.SettingsManager.Get = staticmethod(
        lambda key, default=None: key == "general.disable_autoupdate" or default
    )
    try:
        scoreboard = Scoreboard()
        data = {"id": 9, "auto_update": "set", "keep_updated": True}
        scoreboard.Select(data)
        assert Loaded() == [9] and scoreboard.autoUpdateData is data
        assert ("stopped",) not in calls

        # Not said: the setting decides
        calls.clear()
        scoreboard = Scoreboard()
        scoreboard.Select({"id": 10, "auto_update": "set"})
        assert Loaded() == [10] and scoreboard.autoUpdateData is None
    finally:
        scoreboardModule.SettingsManager.Get = get


def Queued(id, a, b, state=1, match="Winners Semi-Final"):
    return {
        "id": id,
        "match": match,
        "phase": "Top 32",
        "state": state,
        "team": {"1": {"teamName": a}, "2": {"teamName": b}},
    }


def TestTrackingBarText():
    assert TrackingTitle(MODE_STREAM, "main") == "Tracking stream main"
    assert TrackingTitle(MODE_STATION, 4) == "Tracking station 4"
    assert TrackingTitle(MODE_SET) == "Keeping this set updated"
    assert CountdownText(8200) == "checks again in 9s"
    assert CountdownText(0) == "checks again in 0s"
    assert CountdownText(None) == "checking now..."

    queue = [Queued(1, "A", "B", state=3), Queued(2, "C", "D"), Queued(3, "E", "F")]
    # Past the set on the scoreboard and finished sets
    assert NextQueued(queue, None)["id"] == 2
    assert NextQueued(queue, 2)["id"] == 3
    assert NextQueued(queue, "2")["id"] == 3
    assert NextQueued([Queued(2, "C", "D")], 2) is None
    assert NextQueued([], None) is None

    queues = {"Main": queue}
    assert QueueOf(MODE_STREAM, "main", queues, {}) is queue
    assert QueueOf(MODE_STREAM, "main (Slot 1/2)", queues, {}) is queue
    assert QueueOf(MODE_STREAM, "side", queues, {}) == []
    assert [s["id"] for s in QueueOf(MODE_STATION, 4, {}, {"2": queue[2], "1": queue[1]})] == [
        2,
        3,
    ]
    assert QueueOf(MODE_SET, "", queues, {"1": queue[1]}) == []


def TestTrackingBar():
    get = scoreboardModule.StateManager.state
    scoreboardModule.StateManager.state = {
        "stream_queue": {
            "byName": {
                "main": [
                    Queued(5, "Kaito", "Mira", state=2),
                    Queued(6, "Sable", "Oriel"),
                ]
            }
        },
        "score": {"1": {"station_queue": {"1": Queued(9, "Rook", "Juno")}}},
    }
    try:
        calls.clear()
        scoreboard = Scoreboard()
        bar = scoreboard.trackingBar
        scoreboard.Select({"id": 5, "auto_update": "stream", **Queued(5, "Kaito", "Mira")})
        assert not bar.isHidden() and bar.titleLabel.text() == "Tracking stream main"
        assert bar.nowLabel.text() == "Kaito vs Mira · Winners Semi-Final · Top 32"
        # Next: past the set on the scoreboard
        assert bar.nextLabel.text() == "Sable vs Oriel · Winners Semi-Final · Top 32"
        assert not bar.nextLabel.isHidden()

        # Waiting: the stream's set now isn't the scoreboard's
        scoreboard = Scoreboard()
        scoreboard.waitForNextSet = True
        scoreboard.Select({"id": 5, "auto_update": "stream"})
        assert scoreboard.trackingBar.nowLabel.text() == "Waiting for the next set"
        assert scoreboard.trackingBar.nextLabel.text().startswith("Sable vs Oriel")

        # A station's next comes from its queue
        scoreboard = Scoreboard()
        scoreboard.lastStationSelected = {"identifier": 4, "type": "station"}
        scoreboard.Select({"id": 8, "auto_update": "station", **Queued(8, "Ash", "Lux")})
        bar = scoreboard.trackingBar
        assert bar.titleLabel.text() == "Tracking station 4"
        assert bar.nextLabel.text().startswith("Rook vs Juno")

        # A set: no next
        scoreboard = Scoreboard()
        scoreboard.Select(
            {
                "id": 10,
                "auto_update": "set",
                "p1_name": "Pell",
                "p2_name": "Halcyon",
                "round_name": "Grand Final",
            }
        )
        bar = scoreboard.trackingBar
        assert bar.titleLabel.text() == "Keeping this set updated"
        assert bar.nowLabel.text() == "Pell vs Halcyon · Grand Final"
        assert bar.nextLabel.isHidden() and bar.nextName.isHidden()

        # The bracket's data for the set, once loaded, is what's shown; not
        # another set's
        loaded = types.SimpleNamespace(
            lastSetSelected=10,
            trackedSet=None,
            RefreshTrackingBar=lambda: None,
            ChangeSetData=lambda data: None,
            gameReport=types.SimpleNamespace(
                HoldProviderResults=lambda: False, ApplySetData=lambda data: None
            ),
        )
        full = {"id": 10, "p1_name": "Pell", "p2_name": "Halcyon", "round_name": "Grand Final"}
        ScoreboardWidget.UpdateSetData(loaded, full)
        assert loaded.trackedSet is full
        ScoreboardWidget.UpdateSetData(loaded, {"id": 11, "p1_name": "Other"})
        assert loaded.trackedSet is full

        # Turned off for a set: no bar
        scoreboard = Scoreboard()
        scoreboard.Select({"id": 12, "auto_update": "set", "keep_updated": False})
        assert scoreboard.trackingBar.isHidden()
    finally:
        scoreboardModule.StateManager.state = get


if __name__ == "__main__":
    for test in [TestWaitForNextSet, TestKeepUpdated, TestTrackingBarText, TestTrackingBar]:
        test()
        print(f"{test.__name__}: OK")
    print("All scoreboard auto update checks passed")
