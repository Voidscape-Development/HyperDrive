# Checks the "Load a set" window: sets grouped by status, the search and
# filters, keeping a set selected, fetching the completed sets only when
# they're asked for, and loading the selected set.
# Run from the repository root: python test/test_select_set_window.py
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

from qtpy.QtCore import QEvent, QObject, Qt, Signal
from qtpy.QtGui import QKeyEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)


class ManagerSignals(QObject):
    sets_data_updated = Signal(dict)


class TournamentDataManager:
    instance = None

    def __init__(self):
        self.signals = ManagerSignals()
        self.setLoadingWorker = None
        self.fetches = []

    def LoadSets(self, showFinished):
        self.fetches.append(showFinished)


# The real one loads the providers and the whole application with them
sys.modules["src.TournamentDataManager"] = types.SimpleNamespace(
    TournamentDataManager=TournamentDataManager
)
TournamentDataManager.instance = TournamentDataManager()

from src.SelectSetWindow import *
from src.SettingsManager import SettingsManager

# start.gg's set states
WAITING, IN_PROGRESS, DONE, CALLED = 1, 2, 3, 6


def Set(id, p1, p2, state=WAITING, **fields):
    s = {
        "id": id,
        "p1_name": p1,
        "p2_name": p2,
        "state": state,
        "round_name": "Winners Semi-Final",
        "tournament_phase": "Top 32",
        "stream": "",
        "station": "",
        "team1score": 0,
        "team2score": 0,
        "entrants": [[], []],
    }
    s.update(fields)
    return s


SETS = [
    Set(1, "Halcyon", "Pell", p1_seed=1, p2_seed=4, round_name="Winners Quarter-Final"),
    Set(2, "Kaito", "Mira", IN_PROGRESS, stream="https://twitch.tv/mainstage", station=1),
    Set(3, "Sable", "Oriel", CALLED, stream="https://twitch.tv/mainstage", station=1),
    Set(4, "Rook", "", round_name="Losers Round 3", station=4, tournament_phase="Top 8"),
    Set(5, "Tamsin", "Quill", DONE, team1score=3, team2score=1, station=10),
    Set(
        6,
        "Team Vale",
        "Ninefold",
        CALLED,
        station=6,
        entrants=[
            [{"gamerTag": "Ash"}, {"gamerTag": "Pim"}],
            [{"gamerTag": "Corr"}, {"gamerTag": "Lux"}],
        ],
    ),
]


def Ids(groups):
    return [(status, [s["id"] for s in sets]) for status, sets in groups]


# =====================================================
# SETS
# =====================================================
def TestSetFields():
    assert [SetStatus(s) for s in SETS] == [
        STATUS_UPCOMING,
        STATUS_IN_PROGRESS,
        STATUS_CALLED,
        STATUS_UPCOMING,
        STATUS_COMPLETED,
        STATUS_CALLED,
    ]
    # Ready and queued sets haven't started either
    assert SetStatus({"state": 4}) == SetStatus({"state": 7}) == SetStatus({}) == STATUS_UPCOMING

    assert StreamName("https://twitch.tv/mainstage") == "mainstage"
    assert StreamName("https://youtube.com/@channel/") == "@channel"
    assert StreamName("twitch.tv/side") == "side"
    assert StreamName(None) == StreamName("") == ""
    # parry.gg's YouTube streams
    assert StreamName("https://www.youtube.com/@channel/live") == "@channel"
    # The provider's name for it first: a YouTube channel's address has its id
    youtube = "https://youtube.com/channel/UCiHOK00jVASaoM7WPgi-hyg"
    assert SetStreamName({"stream": youtube, "stream_name": "Smash Club"}) == "Smash Club"
    assert SetStreamName({"stream": "https://twitch.tv/mainstage"}) == "mainstage"
    assert SetStreamName({}) == ""

    assert StreamPlatform("https://twitch.tv/mainstage") == "twitch"
    assert StreamPlatform("https://www.youtube.com/@channel/live") == "youtube"
    assert StreamPlatform("youtu.be/x") == "youtube"
    assert StreamPlatform("https://kick.com/side") == "kick"
    assert StreamPlatform("https://nottwitch.tv/x") is None
    assert StreamPlatform("mainstage") is None and StreamPlatform(None) is None

    assert StationText({"station": 4}) == "4"
    assert StationText({"station": ""}) == StationText({"station": -1}) == StationText({}) == ""

    assert TeamMembers(SETS[5]) == ["Ash, Pim", "Corr, Lux"]
    assert TeamMembers(SETS[0]) == ["", ""]
    assert HasEmptySlot(SETS[3]) and not HasEmptySlot(SETS[0])
    assert ScoreText(SETS[4]) == "3–1" and ScoreText(SETS[0]) == ""


def TestGroupSets():
    # In progress first, then called, then upcoming; in the provider's order
    assert Ids(GroupSets(SETS)) == [
        (STATUS_IN_PROGRESS, [2]),
        (STATUS_CALLED, [3, 6]),
        (STATUS_UPCOMING, [1, 4]),
    ]
    assert Ids(GroupSets(SETS, show=SHOW_IN_PROGRESS)) == [(STATUS_IN_PROGRESS, [2])]
    assert Ids(GroupSets(SETS, show=SHOW_COMPLETED)) == [(STATUS_COMPLETED, [5])]
    assert [status for status, _ in GroupSets(SETS, show=SHOW_ALL)] == STATUS_ORDER

    # Every word has to match, in any field
    assert Ids(GroupSets(SETS, text="kaito")) == [(STATUS_IN_PROGRESS, [2])]
    assert Ids(GroupSets(SETS, text="mainstage sable")) == [(STATUS_CALLED, [3])]
    assert Ids(GroupSets(SETS, text="LUX")) == [(STATUS_CALLED, [6])]
    assert Ids(GroupSets(SETS, text="losers")) == [(STATUS_UPCOMING, [4])]
    assert GroupSets(SETS, text="nobody") == []

    assert Ids(GroupSets(SETS, hideEmptySlots=True))[-1] == (STATUS_UPCOMING, [1])
    assert Ids(GroupSets(SETS, stream="mainstage")) == [
        (STATUS_IN_PROGRESS, [2]),
        (STATUS_CALLED, [3]),
    ]
    assert Ids(GroupSets(SETS, station="4")) == [(STATUS_UPCOMING, [4])]
    assert Ids(GroupSets(SETS, phase="Top 8")) == [(STATUS_UPCOMING, [4])]


def TestFilterOptions():
    streams, stations, phases = FilterOptions(SETS)
    assert streams == ["mainstage"]
    # By number, not as text
    assert stations == ["1", "4", "6", "10"]
    assert phases == ["Top 32", "Top 8"]


# =====================================================
# WINDOW
# =====================================================
class Scoreboard(QWidget):
    class Signals(QObject):
        NewSetSelected = Signal(object)

    def __init__(self):
        super().__init__()
        self.signals = Scoreboard.Signals()
        self.loaded = []
        self.signals.NewSetSelected.connect(self.loaded.append)


def Settle():
    for _ in range(5):
        app.processEvents()


def Open():
    manager = TournamentDataManager.instance
    manager.fetches.clear()
    scoreboard = Scoreboard()
    window = SelectSetWindow(scoreboard)
    window.LoadSets()
    window.show()
    Settle()
    return scoreboard, window


def Finish(window, sets):
    TournamentDataManager.instance.signals.sets_data_updated.emit(
        {"progress": 0, "totalPages": 0, "sets": sets}
    )
    Settle()


def Rows(window):
    rows = []
    for row in range(window.model.rowCount()):
        index = window.model.index(row, 0)
        header = index.data(ROLE_HEADER)
        rows.append(header if header is not None else index.data(ROLE_SET)["id"])
    return rows


def Press(widget, key):
    event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)
    Settle()


def TestFetching():
    scoreboard, window = Open()
    manager = TournamentDataManager.instance
    # Not finished sets only, until the completed ones are asked for
    assert manager.fetches == [False]
    assert window.progressBar.isVisible() and not window.details.loadButton.isEnabled()

    manager.signals.sets_data_updated.emit({"progress": 2, "totalPages": 5, "sets": []})
    Settle()
    assert window.progressBar.maximum() == 5 and window.progressBar.value() == 2

    Finish(window, [s for s in SETS if s["state"] != DONE])
    assert not window.progressBar.isVisible()
    assert Rows(window) == [
        (STATUS_IN_PROGRESS, 1),
        2,
        (STATUS_CALLED, 2),
        3,
        6,
        (STATUS_UPCOMING, 2),
        1,
        4,
    ]
    assert window.countLabel.text() == "Showing 5 of 5 sets"

    # Completed: they're fetched, once
    window.showButtons.buttons()[2].click()
    Settle()
    assert manager.fetches == [False, True]
    Finish(window, SETS)
    assert Rows(window) == [(STATUS_COMPLETED, 1), 5]
    window.showButtons.buttons()[3].click()
    window.showButtons.buttons()[0].click()
    Settle()
    assert manager.fetches == [False, True]
    assert 5 not in Rows(window)
    window.close()


def TestSelection():
    scoreboard, window = Open()
    Finish(window, SETS)

    # The first set is selected and shown
    assert window.SelectedSet()["id"] == 2
    assert window.details.sides[0]["name"].text() == "Kaito"
    # The stream's name, its address in the tooltip
    assert window.details.factValues["stream"].text() == "mainstage"
    assert window.details.factValues["stream"].toolTip() == "https://twitch.tv/mainstage"
    assert window.details.loadButton.isEnabled()

    # Up and down skip the headers, from the search bar too
    Press(window.searchBar, Qt.Key.Key_Down)
    assert window.SelectedSet()["id"] == 3
    Press(window.setList, Qt.Key.Key_Down)
    Press(window.setList, Qt.Key.Key_Down)
    assert window.SelectedSet()["id"] == 1
    Press(window.setList, Qt.Key.Key_Up)
    Press(window.setList, Qt.Key.Key_Up)
    assert window.SelectedSet()["id"] == 3

    # The selection stays while it's still listed
    window.searchBar.setText("mainstage")
    Settle()
    assert window.SelectedSet()["id"] == 3
    window.searchBar.setText("pell")
    Settle()
    assert window.SelectedSet()["id"] == 1

    # Nothing matches: nothing to load
    window.searchBar.setText("nobody")
    Settle()
    assert window.SelectedSet() is None and window.emptyLabel.isVisible()
    assert not window.details.loadButton.isEnabled()
    Press(window.searchBar, Qt.Key.Key_Return)
    assert scoreboard.loaded == [] and window.isVisible()

    window.searchBar.setText("")
    window.hideEmptySlots.setChecked(True)
    Settle()
    assert 4 not in Rows(window)

    # The filters list what the sets have, and keep what was picked
    window.stationFilter.setCurrentIndex(window.stationFilter.findData("6"))
    Settle()
    assert Rows(window) == [(STATUS_CALLED, 1), 6]
    assert window.details.sides[1]["members"].text() == "Corr, Lux"
    Finish(window, SETS)
    assert window.stationFilter.currentData() == "6"
    window.close()


def TestClickShowsSet():
    scoreboard, window = Open()
    # All of them, the completed ones too
    window.showButtons.buttons()[3].click()
    Settle()
    Finish(window, SETS)
    for row in range(window.model.rowCount()):
        index = window.model.index(row, 0)
        s = index.data(ROLE_SET)
        if s is None:
            continue
        # A click moves the current index before it selects the row
        QTest.mouseClick(
            window.setList.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            window.setList.visualRect(index).center(),
        )
        Settle()
        assert window.SelectedSet()["id"] == s["id"]
        assert not window.details.empty.isVisible()
        assert window.details.sides[0]["name"].text() == s["p1_name"]
        assert window.details.factValues["status"].text() == StatusNames()[SetStatus(s)]
    # The last one is the completed set, with its score
    assert window.SelectedSet()["id"] == 5
    assert [side["score"].text() for side in window.details.sides] == ["3", "1"]
    window.close()


def TestLoading():
    scoreboard, window = Open()
    Finish(window, SETS)
    window.searchBar.setText("sable")
    Settle()
    Press(window.searchBar, Qt.Key.Key_Return)
    assert [s["id"] for s in scoreboard.loaded] == [3]
    assert scoreboard.loaded[0]["auto_update"] == "set"
    # The listed set isn't changed
    assert "auto_update" not in SETS[2]
    assert not window.isVisible()

    # Opening it again fetches the sets again
    window.LoadSets()
    window.show()
    Settle()
    Finish(window, SETS)
    window.details.loadButton.click()
    Settle()
    assert [s["id"] for s in scoreboard.loaded] == [3, 3]
    window.close()


def TestKeepUpdated():
    settings = {}
    get = SettingsManager.Get
    SettingsManager.Get = staticmethod(lambda key, default=None: settings.get(key, default))
    try:
        # Starts as the setting says, each time the window opens
        scoreboard, window = Open()
        Finish(window, SETS)
        assert window.details.keepUpdated.isChecked()
        window.details.loadButton.click()
        Settle()
        assert scoreboard.loaded[-1]["keep_updated"] is True

        settings["general.disable_autoupdate"] = True
        window.LoadSets()
        window.show()
        Settle()
        assert not window.details.keepUpdated.isChecked()
        # Changed for one set only
        window.details.keepUpdated.setChecked(True)
        Finish(window, SETS)
        window.details.loadButton.click()
        Settle()
        assert scoreboard.loaded[-1]["keep_updated"] is True
        window.LoadSets()
        window.show()
        Settle()
        assert not window.details.keepUpdated.isChecked()
        Finish(window, SETS)
        window.details.loadButton.click()
        Settle()
        assert scoreboard.loaded[-1]["keep_updated"] is False
    finally:
        SettingsManager.Get = get


if __name__ == "__main__":
    for test in [
        TestSetFields,
        TestGroupSets,
        TestFilterOptions,
        TestFetching,
        TestSelection,
        TestClickShowsSet,
        TestLoading,
        TestKeepUpdated,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All select set window checks passed")
