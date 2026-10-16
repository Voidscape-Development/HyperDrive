# Checks how a scoreboard takes a new set (NewSetSelected): a set picked in
# the set list with "Keep scores updated" off, and a stream or station
# tracked from its next set, which leaves the set on it when tracking starts,
# the tracking bar, and a tracked stream's next set loading after a
# countdown that can be held.
# Run from the repository root: python test/test_scoreboard_auto_update.py
import os
import sys
import time
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

from qtpy.QtCore import QTimer
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
# Nothing is saved or exported
scoreboardModule.StateManager.BlockSaving = staticmethod(lambda: None)
scoreboardModule.StateManager.ReleaseSaving = staticmethod(lambda: None)


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
    WaitToSwitch = ScoreboardWidget.WaitToSwitch
    ShowNextSet = ScoreboardWidget.ShowNextSet
    LoadNextSet = ScoreboardWidget.LoadNextSet
    HoldNextSet = ScoreboardWidget.HoldNextSet
    ClearNextSet = ScoreboardWidget.ClearNextSet
    NewSetSelected = ScoreboardWidget.NewSetSelected

    def __init__(self):
        self.lastSetSelected = None
        self.lastStationSelected = {"identifier": "main", "type": "stream"}
        self.waitForNextSet = False
        self.autoUpdateData = None
        self.trackedSet = None
        self.trackingBar = TrackingBar()
        self.nextSet = None
        self.nextSetHeld = False
        self.nextSetTimer = QTimer()
        self.nextSetTimer.setSingleShot(True)
        self.nextSetTimer.timeout.connect(self.LoadNextSet)

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


def Tracking(delay=None):
    """A scoreboard tracking stream "main", its set 5 loaded."""
    settings = {} if delay is None else {"general.tracking_next_set_delay": delay}
    scoreboardModule.SettingsManager.Get = staticmethod(
        lambda key, default=None: settings.get(key, default)
    )
    scoreboard = Scoreboard()
    scoreboard.Select({"id": 5, "auto_update": "stream", **Queued(5, "Kaito", "Mira")})
    calls.clear()
    return scoreboard


def Next(id, a="Sable", b="Oriel"):
    return {"id": id, "auto_update": "stream", **Queued(id, a, b)}


def TestNextSetCountdown():
    get = scoreboardModule.SettingsManager.Get
    try:
        scoreboard = Tracking()
        notice = scoreboard.trackingBar.notice
        # The next set waits, the set on the scoreboard stays
        scoreboard.Select(Next(6))
        assert Loaded() == [] and scoreboard.lastSetSelected == 5
        assert not notice.isHidden() and not scoreboard.trackingBar.holdButton.isHidden()
        assert scoreboard.trackingBar.noticeLabel.text() == "Next set: Sable vs Oriel loads in 5s."
        assert scoreboard.nextSetTimer.isActive()
        # Seen again on the next check: the countdown goes on
        remaining = scoreboard.nextSetTimer.remainingTime()
        scoreboard.Select(Next(6))
        assert Loaded() == [] and scoreboard.nextSetTimer.remainingTime() <= remaining

        scoreboard.LoadNextSet()
        assert Loaded() == [6] and scoreboard.lastSetSelected == 6
        assert notice.isHidden() and not scoreboard.nextSetTimer.isActive()
        # Loaded: the next check doesn't count it as new
        calls.clear()
        scoreboard.Select(Next(6))
        assert Loaded() == [] and notice.isHidden()

        # Held: it waits until loaded by hand, even if another comes up
        scoreboard.Select(Next(7, "Rook", "Juno"))
        scoreboard.HoldNextSet()
        assert not scoreboard.nextSetTimer.isActive()
        assert scoreboard.trackingBar.holdButton.isHidden()
        assert "is held" in scoreboard.trackingBar.noticeLabel.text()
        scoreboard.Select(Next(7, "Rook", "Juno"))
        scoreboard.Select(Next(8, "Ash", "Lux"))
        assert Loaded() == [] and scoreboard.nextSetHeld
        assert not scoreboard.nextSetTimer.isActive()
        assert "Ash vs Lux" in scoreboard.trackingBar.noticeLabel.text()
        scoreboard.LoadNextSet()
        assert Loaded() == [8] and not scoreboard.nextSetHeld

        # The set on the scoreboard back on top: nothing to switch to
        scoreboard.Select(Next(9))
        assert not notice.isHidden()
        scoreboard.Select(Next(8))
        assert notice.isHidden() and Loaded() == [8]

        # A set picked by hand: no switch waits any more
        scoreboard.Select(Next(9))
        scoreboard.Select({"id": 20, "auto_update": "set", "p1_name": "A", "p2_name": "B"})
        assert notice.isHidden() and scoreboard.nextSet is None and Loaded() == [8, 20]
    finally:
        scoreboardModule.SettingsManager.Get = get


def TestNextSetLoadsAfterTheDelay():
    get = scoreboardModule.SettingsManager.Get
    try:
        # The countdown runs out
        scoreboard = Tracking(delay=0.1)
        scoreboard.Select(Next(6))
        assert Loaded() == []
        deadline = time.monotonic() + 3
        while not Loaded() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert Loaded() == [6] and scoreboard.trackingBar.notice.isHidden()

        # 0: at once
        scoreboard = Tracking(delay=0)
        scoreboard.Select(Next(6))
        assert Loaded() == [6] and scoreboard.trackingBar.notice.isHidden()

        # The first set of a stream loads at once
        scoreboard = Tracking()
        scoreboard.trackedSet = None
        scoreboard.Select(Next(6))
        assert Loaded() == [6]
    finally:
        scoreboardModule.SettingsManager.Get = get


if __name__ == "__main__":
    for test in [
        TestWaitForNextSet,
        TestKeepUpdated,
        TestTrackingBarText,
        TestTrackingBar,
        TestNextSetCountdown,
        TestNextSetLoadsAfterTheDelay,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All scoreboard auto update checks passed")
