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
    timerLayout = Ignored()
    labelAutoUpdate = Ignored()
    gameReport = Ignored()
    signals = types.SimpleNamespace(NewSetLoaded=Ignored())

    def __init__(self):
        self.lastSetSelected = None
        self.lastStationSelected = {"identifier": "main", "type": "stream"}
        self.waitForNextSet = False
        self.autoUpdateData = None

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


if __name__ == "__main__":
    for test in [TestWaitForNextSet, TestKeepUpdated]:
        test()
        print(f"{test.__name__}: OK")
    print("All scoreboard auto update checks passed")
