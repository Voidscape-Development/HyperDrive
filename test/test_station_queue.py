# Checks how a scoreboard's stream or station queue is loaded
# (TournamentDataManager.LoadStationSets), with the real thread pool:
# - the sets after the first one reach the scoreboard (StationSetsLoaded).
#   They used to be fetched by a worker made inside another worker's thread,
#   whose result never arrived.
# - the scoreboard's state (the station picked, its queue cache) is only
#   read and changed on the GUI thread
# - a result for a station that isn't the one picked anymore is dropped
# - Worker says so when it's made outside the GUI thread
# Run from the repository root: python test/test_station_queue.py
import os
import sys
import threading
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

from qtpy.QtCore import QObject, QThread, Signal
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.ScoreboardWidget import QueueSetsCache
from src.TournamentDataManager import TournamentDataManager
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider
from src.Workers import Worker

GUI_THREAD = threading.get_ident()


def Set(id, state=1):
    return {"id": id, "state": state, "slots": [{"entrant": {"id": 1}}, {"entrant": {"id": 2}}]}


class Provider(TournamentDataProvider):
    def __init__(self, sets):
        super().__init__("https://fake.gg/e", None, None)
        self.sets = sets
        self.asked = []
        self.threads = set()
        self.delay = 0

    def GetStreamMatchId(self, station):
        self.threads.add(threading.get_ident())
        return None

    def GetStationMatchsId(self, stationId):
        self.threads.add(threading.get_ident())
        time.sleep(self.delay)
        return [dict(s) for s in self.sets]

    def GetFutureMatchesList(self, setsId, progress_callback=None, cancel_event=None):
        self.threads.add(threading.get_ident())
        self.asked.append([s["id"] for s in setsId])
        return {str(i + 1): {"id": s["id"]} for i, s in enumerate(setsId)}


class Signals(QObject):
    NewSetSelected = Signal(object)
    StationSetsLoaded = Signal(object)


class Scoreboard:
    """What LoadStationSets uses of a scoreboard"""

    def __init__(self):
        self.signals = Signals()
        self.lastStationSelected = {"id": 7, "type": "station", "identifier": "7"}
        self.stationQueueCache = QueueSetsCache()
        self.selected = []
        self.queues = []
        self.threads = set()
        self.signals.NewSetSelected.connect(self.Selected)
        self.signals.StationSetsLoaded.connect(self.Loaded)

    def Selected(self, data):
        self.threads.add(threading.get_ident())
        self.selected.append(data)

    def Loaded(self, data):
        self.threads.add(threading.get_ident())
        self.queues.append(data)


def Wait(condition, secs=5):
    deadline = time.monotonic() + secs
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    return condition()


def Load(manager, scoreboard):
    finished = []
    manager.LoadStationSets(scoreboard, on_finished=lambda: finished.append(1))
    assert Wait(lambda: finished), "LoadStationSets never finished"
    # Whatever else was queued behind it
    for _ in range(5):
        app.processEvents()


def TestQueueLoads():
    manager = TournamentDataManager.instance
    provider = Provider([Set(1), Set(2), Set(3)])
    manager.provider = provider
    scoreboard = Scoreboard()
    before = Worker.offGuiThreadCreations

    Load(manager, scoreboard)

    # The first set is loaded, the others are its queue
    assert [s.get("id") for s in scoreboard.selected] == [1], scoreboard.selected
    assert scoreboard.selected[0]["auto_update"] == "station"
    assert scoreboard.queues == [{"1": {"id": 2}, "2": {"id": 3}}], scoreboard.queues
    assert provider.asked == [[2, 3]]
    assert [s["id"] for s in scoreboard.stationQueueCache.queue] == [1, 2, 3]

    # The provider was asked off the GUI thread, the scoreboard told on it
    assert GUI_THREAD not in provider.threads, "the provider was asked on the GUI thread"
    assert scoreboard.threads == {GUI_THREAD}, "the scoreboard was told off the GUI thread"
    assert Worker.offGuiThreadCreations == before, "a Worker was made off the GUI thread"

    # The same queue again: the set is loaded, its queue isn't fetched again
    Load(manager, scoreboard)
    assert len(scoreboard.selected) == 2 and len(scoreboard.queues) == 1
    assert provider.asked == [[2, 3]]

    # The queue changed: fetched again
    provider.sets = [Set(2), Set(3)]
    Load(manager, scoreboard)
    assert scoreboard.queues[-1] == {"1": {"id": 3}}, scoreboard.queues
    assert [s.get("id") for s in scoreboard.selected] == [1, 1, 2]


def TestFailedQueueIsTriedAgain():
    manager = TournamentDataManager.instance
    provider = Provider([Set(1), Set(2)])
    manager.provider = provider
    scoreboard = Scoreboard()

    def fails(setsId, progress_callback=None, cancel_event=None):
        raise RuntimeError("no network")

    working = provider.GetFutureMatchesList
    provider.GetFutureMatchesList = fails
    Load(manager, scoreboard)
    # The set still loads; the queue isn't taken as known
    assert [s.get("id") for s in scoreboard.selected] == [1]
    assert scoreboard.queues == [] and scoreboard.stationQueueCache.queue == []

    provider.GetFutureMatchesList = working
    Load(manager, scoreboard)
    assert scoreboard.queues == [{"1": {"id": 2}}], scoreboard.queues


def TestStaleResultsAreDropped():
    manager = TournamentDataManager.instance
    provider = Provider([Set(1), Set(2)])
    provider.delay = 0.2
    manager.provider = provider
    scoreboard = Scoreboard()

    # Another station is picked while the first one's sets are fetched
    finished = []
    manager.LoadStationSets(scoreboard, on_finished=lambda: finished.append(1))
    scoreboard.lastStationSelected = {"id": 8, "type": "station", "identifier": "8"}
    assert Wait(lambda: finished)
    app.processEvents()
    assert scoreboard.selected == [] and scoreboard.queues == []
    assert scoreboard.stationQueueCache.queue == []

    # Another event is loaded meanwhile
    scoreboard = Scoreboard()
    finished = []
    manager.LoadStationSets(scoreboard, on_finished=lambda: finished.append(1))
    manager.provider = Provider([])
    assert Wait(lambda: finished)
    app.processEvents()
    assert scoreboard.selected == [] and scoreboard.queues == []

    # No station, or no event: done right away
    scoreboard.lastStationSelected = None
    finished = []
    manager.LoadStationSets(scoreboard, on_finished=lambda: finished.append(1))
    assert finished == [1]


def TestWorkerOffTheGuiThread():
    """A worker made in a thread without an event loop can't deliver its
    signals: it says so"""
    before = Worker.offGuiThreadCreations
    made = []

    class Thread(QThread):
        def run(self):
            made.append(Worker(lambda progress_callback=None, cancel_event=None: 1))

    thread = Thread()
    thread.start()
    thread.wait()
    assert made[0].createdOffGuiThread
    assert Worker.offGuiThreadCreations == before + 1

    worker = Worker(lambda progress_callback=None, cancel_event=None: 1)
    assert not worker.createdOffGuiThread
    assert Worker.offGuiThreadCreations == before + 1


if __name__ == "__main__":
    TestQueueLoads()
    TestFailedQueueIsTriedAgain()
    TestStaleResultsAreDropped()
    TestWorkerOffTheGuiThread()
    print("OK")
