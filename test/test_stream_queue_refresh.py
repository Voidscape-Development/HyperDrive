# Checks how the stream queue takes what the provider answers
# (StreamQueueWidget.RunRefresh): an update that fails keeps the queues shown
# and when they were last updated, and says they're stale; an update that
# says there's nothing queued empties them; an answer for the event that was
# loaded before is dropped.
# Run from the repository root: python test/test_stream_queue_refresh.py
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

import src.StreamQueueWidget as module
from src.StreamQueue import StreamQueueModel
from src.StreamQueueWidget import StreamQueueWidget
from src.TournamentDataManager import TournamentDataManager
from src.TournamentDataProvider.ProviderErrors import Failed, TransientError
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider


class SyncPool:
    def start(self, worker):
        worker.run()


manager = TournamentDataManager.instance
manager.threadPool = SyncPool()


def Set(id):
    return {"id": id, "state": 1, "match": f"Set {id}", "team": {}}


class Provider(TournamentDataProvider):
    def __init__(self):
        super().__init__("https://fake.gg/e", None, None)
        # What GetStreamQueue answers: the queues, or an error
        self.queues = {"main": {"1": Set(1), "2": Set(2)}}

    def GetStreamQueue(self, progress_callback=None, cancel_event=None):
        if isinstance(self.queues, Exception):
            # Like the real providers: raised when asked to, else {}
            return Failed(self.queues, {})
        return self.queues

    def GetFutureMatch(self, matchId, progress_callback=None, cancel_event=None):
        return {}


class Widget:
    """What RunRefresh, Fetched and FetchFailed use of the widget"""

    RunRefresh = StreamQueueWidget.RunRefresh
    Fetched = StreamQueueWidget.Fetched
    FetchFailed = StreamQueueWidget.FetchFailed

    def __init__(self):
        self.model = StreamQueueModel()
        self.durations = {}
        self.durationsUpdated = 10**12
        self.lastError = None
        self.changed = 0
        self.exported = 0

    def Changed(self, save=True):
        self.changed += 1

    def Export(self):
        self.exported += 1

    def UpdateStatus(self):
        pass


def Refresh(widget):
    done = []
    widget.RunRefresh(lambda: done.append(1))
    assert done == [1], "the update never finished"


def Keys(widget, name="main"):
    return [e["key"] for e in widget.model.Queue(name)]


def TestRefresh():
    manager.provider = provider = Provider()
    widget = Widget()

    Refresh(widget)
    assert Keys(widget) == ["set:1", "set:2"] and widget.lastError is None
    updated = widget.model.lastUpdated
    assert updated is not None

    # The update fails: the queues stay, and so does when they were updated
    provider.queues = TransientError("no network")
    module.time.sleep(0.01)
    Refresh(widget)
    assert Keys(widget) == ["set:1", "set:2"], "a failed update emptied the queue"
    assert widget.model.lastUpdated == updated, "a failed update counted as an update"
    assert widget.lastError == "no network" and widget.exported == 1

    # It works again
    provider.queues = {"main": {"1": Set(2), "2": Set(3)}}
    Refresh(widget)
    assert Keys(widget) == ["set:2", "set:3"] and widget.lastError is None
    assert widget.model.lastUpdated > updated

    # Nothing queued anymore is an answer: the queue empties
    provider.queues = {}
    Refresh(widget)
    assert Keys(widget) == [] and widget.lastError is None

    # No event: done right away
    manager.provider = None
    Refresh(widget)


def TestAnotherEvent():
    """An answer for the event loaded before isn't this event's queue"""
    manager.provider = first = Provider()
    widget = Widget()
    Refresh(widget)

    class Loading(Provider):
        def GetStreamQueue(self, progress_callback=None, cancel_event=None):
            # Another event is loaded while this one's queue is fetched
            manager.provider = Provider()
            return {"main": {"1": Set(9)}}

    manager.provider = Loading()
    Refresh(widget)
    assert Keys(widget) == ["set:1", "set:2"], Keys(widget)
    assert first is not manager.provider


if __name__ == "__main__":
    TestRefresh()
    TestAnotherEvent()
    print("OK")
