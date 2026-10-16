# Checks the "Track a stream or station" window: streams with what's on
# them now and next, stations with whether they're in use, the search, the
# selected one's sets, and starting to track one, now or from its next set.
# Run from the repository root: python test/test_select_station_window.py
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QEvent, QObject, Qt, QThreadPool, Signal
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)

# start.gg's set states
WAITING, IN_PROGRESS, CALLED = 1, 2, 6


def Queued(id, a, b, state=WAITING, match="Winners Semi-Final", station=-1):
    return {
        "id": id,
        "match": match,
        "phase": "Top 32",
        "state": state,
        "station": station,
        "team": {"1": {"teamName": a}, "2": {"teamName": b}},
    }


def Listed(id, a, b, state=WAITING, station=""):
    return {
        "id": id,
        "p1_name": a,
        "p2_name": b,
        "state": state,
        "station": station,
        "round_name": "Losers Round 3",
        "tournament_phase": "Top 32",
    }


STATIONS = [
    {"id": 11, "identifier": 2, "type": "station", "stream": "sidestage"},
    {"id": 10, "identifier": 1, "type": "station", "stream": "mainstage"},
    {"id": 13, "identifier": 10, "type": "station", "stream": ""},
    {"id": 12, "identifier": 4, "type": "station", "stream": ""},
    {"id": 1, "identifier": "mainstage", "type": "stream"},
    {"id": 2, "identifier": "sidestage", "type": "stream"},
]
QUEUES = {
    "mainstage": {
        "1": Queued(100, "Kaito", "Mira", IN_PROGRESS, station=1),
        "2": Queued(101, "Sable", "Oriel", station=1),
        "3": Queued(102, "Tamsin", "Quill", match="Winners Quarter-Final"),
    },
    "sidestage": {"1": Queued(103, "Halcyon", "Pell")},
}
SETS = [
    Listed(100, "Kaito", "Mira", IN_PROGRESS, station=1),
    Listed(200, "Rook", "Juno", CALLED, station=4),
    Listed(201, "Ash", "Lux", WAITING, station=4),
    Listed(202, "Corr", "Pim", IN_PROGRESS, station=4),
]


class Provider:
    def __init__(self):
        self.matchCalls = 0

    def GetStreamQueue(self, progress_callback=None, cancel_event=None):
        return QUEUES

    def GetMatches(self, getFinished=False, progress_callback=None, cancel_event=None):
        assert getFinished is False
        self.matchCalls += 1
        return SETS


class ManagerSignals(QObject):
    get_stations_finished = Signal(list)


class TournamentDataManager:
    instance = None

    def __init__(self):
        self.signals = ManagerSignals()
        self.threadPool = QThreadPool()
        self.provider = Provider()
        self.stations = STATIONS

    def GetProvider(self):
        return self.provider

    def LoadStations(self):
        self.signals.get_stations_finished.emit(list(self.stations))


# The real one loads the providers and the whole application with them
sys.modules["src.TournamentDataManager"] = types.SimpleNamespace(
    TournamentDataManager=TournamentDataManager
)
TournamentDataManager.instance = TournamentDataManager()

from src.SelectStationWindow import *
from src.SettingsManager import SettingsManager


# =====================================================
# STREAMS, STATIONS AND THEIR SETS
# =====================================================
def TestQueues():
    queue = {"2": "b", "10": "c", "1": "a"}
    assert QueueSets(queue) == ["a", "b", "c"]
    assert QueueSets(None) == []

    assert QueueFor({"identifier": "MainStage"}, QUEUES) is QUEUES["mainstage"]
    # parry.gg's slots share their stream's queue
    assert QueueFor({"identifier": "mainstage (Slot 2/2)"}, QUEUES) is QUEUES["mainstage"]
    assert QueueFor({"identifier": "main"}, QUEUES) is None

    now, following = StreamNowNext(QUEUES["mainstage"])
    assert now["id"] == 100 and following["id"] == 101
    # Nothing in progress: the first one is next
    now, following = StreamNowNext(QUEUES["sidestage"])
    assert now is None and following["id"] == 103
    assert StreamNowNext({}) == (None, None)

    assert SetTitle(QUEUES["mainstage"]["1"]) == "Kaito vs Mira"
    assert SetTitle(SETS[1]) == "Rook vs Juno"
    assert SetTitle({"team": {"1": {"player": {"1": {"mergedName": "A"}}}}}) == "A vs TBD"
    assert SetLine(QUEUES["mainstage"]["1"]) == "Kaito vs Mira · Winners Semi-Final · Top 32"


def TestStations():
    # In progress first, then called
    assert [s["id"] for s in StationSets(4, SETS)] == [202, 200, 201]
    assert StationUse("4", SETS) == (USE_IN_USE, SETS[3])
    assert StationUse("1", SETS)[0] == USE_IN_USE
    assert StationUse("2", SETS) == (USE_FREE, None)
    assert StationUse("4", [SETS[1], SETS[2]]) == (USE_CALLED, SETS[1])
    # Not checked yet
    assert StationUse("4", None) == (None, None)

    assert StationsOnStream("MainStage", STATIONS) == ["1"]
    assert StationsOnStream("other", STATIONS) == []
    # By number
    assert [StationNumber(e) for e in SortedStations(STATIONS)] == ["1", "2", "4", "10"]


# =====================================================
# WINDOW
# =====================================================
class Scoreboard(QWidget):
    class Signals(QObject):
        StationSelected = Signal(object)

    def __init__(self):
        super().__init__()
        self.signals = Scoreboard.Signals()
        self.tracked = []
        self.signals.StationSelected.connect(self.tracked.append)


def Settle():
    for _ in range(3):
        TournamentDataManager.instance.threadPool.waitForDone()
        for _ in range(5):
            app.processEvents()


def Open():
    scoreboard = Scoreboard()
    window = SelectStationWindow(scoreboard)
    window.LoadStations()
    window.show()
    Settle()
    return scoreboard, window


def Cards(grid):
    return [grid.model().index(row, 0).data(ROLE_CARD) for row in range(grid.model().rowCount())]


def Press(widget, key):
    QApplication.sendEvent(
        widget, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    )
    Settle()


def TestCards():
    scoreboard, window = Open()
    assert not window.progressBar.isVisible()

    streams = Cards(window.streamGrid)
    assert [c["title"] for c in streams] == ["mainstage", "sidestage"]
    assert streams[0]["badge"] == "3 queued"
    assert streams[0]["subtitle"] == "uses Station 1"
    assert streams[0]["lines"] == [
        ("Now", "Kaito vs Mira · Winners Semi-Final · Top 32", True),
        ("Next", "Sable vs Oriel · Winners Semi-Final · Top 32", False),
    ]
    assert streams[1]["lines"][0] == ("Now", "Nothing on stream", False)

    stations = Cards(window.stationGrid)
    assert [c["number"] for c in stations] == ["1", "2", "4", "10"]
    assert [c["use"] for c in stations] == [USE_IN_USE, USE_FREE, USE_IN_USE, USE_FREE]
    assert stations[2]["set"] == "Corr vs Pim" and stations[2]["where"] == "Off stream"
    assert stations[1]["set"] == "No set" and stations[1]["where"] == "On sidestage"
    assert window.showButtonsByKey[SHOW_STATIONS].text() == "Stations · 4"

    # The first card is selected, with its queue
    assert window.SelectedEntry()["identifier"] == "mainstage"
    assert [r.findChildren(QLabel)[0].text() for r in window.details.queueRows] == [
        "NOW",
        "NEXT",
        "3",
    ]
    assert window.details.startButton.text() == "Start tracking mainstage"
    window.close()


def TestOtherScoreboards():
    # Every scoreboard has a window; one loading doesn't make the others fetch
    manager = TournamentDataManager.instance
    manager.provider.matchCalls = 0
    other = SelectStationWindow(Scoreboard())
    scoreboard, window = Open()
    assert manager.provider.matchCalls == 1
    assert other.entries == [] and not other.loadingSets
    window.close()


def TestNoStations():
    # parry.gg: streams only, so the set list isn't fetched
    manager = TournamentDataManager.instance
    manager.stations = [e for e in STATIONS if e["type"] == "stream"]
    manager.provider.matchCalls = 0
    try:
        scoreboard, window = Open()
        assert manager.provider.matchCalls == 0
        assert not window.stationGrid.isVisible() and not window.stationsTitle.isVisible()
        window.close()

        manager.stations = []
        scoreboard, window = Open()
        assert window.emptyLabel.isVisible()
        assert window.emptyLabel.text() == "This event has no streams or stations."
        assert not window.details.startButton.isVisible()
        window.close()
    finally:
        manager.stations = STATIONS


def TestSearchAndSelection():
    scoreboard, window = Open()

    # Players on a station find it
    window.searchBar.setText("juno")
    Settle()
    assert Cards(window.streamGrid) == []
    assert [c["number"] for c in Cards(window.stationGrid)] == ["4"]
    assert window.SelectedEntry()["identifier"] == 4
    assert [r.findChildren(QLabel)[0].text() for r in window.details.queueRows] == [
        "NOW",
        "CALLED",
        "NEXT",
    ]
    # The stream's rows shown before are gone at once
    assert len(window.details.findChildren(QFrame, "queueRow")) == 3

    window.searchBar.setText("")
    Settle()
    # The selection stays while it's listed
    assert window.SelectedEntry()["identifier"] == 4

    # One card selected across both grids
    window.streamGrid.setCurrentIndex(window.streamGrid.model().index(1, 0))
    Settle()
    assert window.SelectedEntry()["identifier"] == "sidestage"
    assert not window.stationGrid.selectionModel().hasSelection()

    window.showButtonsByKey[SHOW_STATIONS].click()
    Settle()
    assert Cards(window.streamGrid) == []
    assert window.SelectedEntry()["identifier"] == 1

    window.searchBar.setText("nothing like it")
    Settle()
    assert window.SelectedEntry() is None and not window.details.startButton.isEnabled()
    Press(window.searchBar, Qt.Key.Key_Return)
    assert scoreboard.tracked == []
    window.close()


def TestTracking():
    settings = {}
    get = SettingsManager.Get
    SettingsManager.Get = staticmethod(lambda key, default=None: settings.get(key, default))
    try:
        scoreboard, window = Open()
        assert not window.details.startGroup.isHidden()
        assert window.details.loadNow.isChecked()
        Press(window.searchBar, Qt.Key.Key_Return)
        assert [s["identifier"] for s in scoreboard.tracked] == ["mainstage"]
        assert scoreboard.tracked[0]["wait_for_next"] is False
        assert not window.isVisible()
        # The listed station isn't changed
        assert "wait_for_next" not in STATIONS[4]

        # From the next set; reset each time the window opens
        window.LoadStations()
        window.show()
        Settle()
        window.details.waitForNext.setChecked(True)
        window.details.startButton.click()
        Settle()
        assert scoreboard.tracked[-1]["wait_for_next"] is True
        window.LoadStations()
        window.show()
        Settle()
        assert window.details.loadNow.isChecked()

        # Without auto update, only the set on it now loads
        settings["general.disable_autoupdate"] = True
        window.close()
        window.show()
        Settle()
        assert window.details.startGroup.isHidden()
        assert not window.details.noAutoUpdate.isHidden()
        window.details.waitForNext.setChecked(True)
        window.StartTracking()
        assert scoreboard.tracked[-1]["wait_for_next"] is False
    finally:
        SettingsManager.Get = get


if __name__ == "__main__":
    for test in [
        TestQueues,
        TestStations,
        TestCards,
        TestOtherScoreboards,
        TestNoStations,
        TestSearchAndSelection,
        TestTracking,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All select station window checks passed")
