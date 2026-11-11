# Checks TournamentDataManager's one way of asking the provider something
# off the GUI thread (Run), with the real thread pool:
# - the provider is asked off the GUI thread, inside RaiseProviderErrors; the
#   answer, the error and the progress come back on it
# - an answer for the event that was loaded before is dropped
# - with a key, the latest request wins, whichever answers first (two sets
#   loaded on a scoreboard: the last one asked for is the one shown)
# - a request that fails leaves what was shown (the tournament's data, the
#   phases), unless nothing of the event was shown yet
# and how an event is loaded (SetTournament):
# - making a provider asks nothing of the network, Connect does, off the GUI
#   thread
# - an event that can't be loaded says why (the key, the link, the network),
#   and can be loaded again
# Run from the repository root: python test/test_data_manager.py
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

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.GameAssetManager import GameAssetManager
from src.PlayerDB import PlayerDB
from src.SettingsManager import SettingsManager
from src.TournamentDataManager import TournamentDataManager
from src.TournamentDataProvider import Providers
from src.TournamentDataProvider.ParryGGDataProvider import ParryGGDataProvider
from src.TournamentDataProvider.ProviderErrors import (
    KIND_AUTH,
    KIND_NOT_FOUND,
    KIND_TRANSIENT,
    AuthError,
    NotFoundError,
    Raising,
    TransientError,
)
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider
from src.Workers import Worker

GUI_THREAD = threading.get_ident()
manager = TournamentDataManager.instance

# Nothing is saved, no game is loaded
settings = {}
SettingsManager.Get = staticmethod(lambda key, default=None: settings.get(key, default))
SettingsManager.Set = staticmethod(lambda key, value: settings.__setitem__(key, value))
PlayerDB.AddPlayers = staticmethod(lambda players, *args, **kwargs: None)


class FakeGames:
    def LoadGameAssets(self, game):
        pass

    def SetGameFromStartGGId(self, id):
        pass


GameAssetManager.instance = FakeGames()
errorsShown = []
manager.ShowTournamentError = lambda url, message, retry: errorsShown.append((url, message, retry))


def Wait(condition, secs=5):
    deadline = time.monotonic() + secs
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.002)
    return condition()


def Settle():
    """Lets what's running finish and what's queued arrive"""
    manager.threadPool.waitForDone(5000)
    for _ in range(5):
        app.processEvents()
        time.sleep(0.002)


class Provider(TournamentDataProvider):
    """Answers what it's told to, when it's told to"""

    NAME = "Fake"
    HOST = "fake.gg"
    GAME_ID_KIND = "startgg"
    made = []
    # What Connect and the others do for the providers made next: raise it
    connectError = None
    dataError = None

    def __init__(self, url, threadpool=None, dataManager=None, api_key=None, context=None):
        super().__init__(url, threadpool, dataManager, api_key)
        Provider.made.append(self)
        self.madeOn = threading.get_ident()
        self.connectedOn = None
        self.calls = []
        self.holds = {}

    def Hold(self, what):
        """The next answer for `what` waits until it's released"""
        self.holds[what] = threading.Event()
        return self.holds[what]

    def Answer(self, what, value):
        self.calls.append((what, threading.get_ident(), Raising()))
        hold = self.holds.pop(what, None)
        if hold is not None:
            hold.wait(5)
        if isinstance(value, Exception):
            raise value
        return value

    def Connect(self, progress_callback=None, cancel_event=None):
        self.connectedOn = threading.get_ident()
        if Provider.connectError:
            raise Provider.connectError
        self.url = self.url.replace("/short/", "/event/")
        return self.url

    def GetTournamentData(self, progress_callback=None, cancel_event=None):
        return self.Answer("tournament", Provider.dataError or {"tournamentName": self.url})

    def GetTournamentPhases(self, progress_callback=None, cancel_event=None):
        return self.Answer("phases", Provider.dataError or [{"id": 1, "name": "Bracket"}])

    def GetMatch(self, setId, progress_callback=None, cancel_event=None):
        return self.Answer(f"set {setId}", {"id": setId})

    def GetMatches(self, getFinished=False, progress_callback=None, cancel_event=None):
        if progress_callback:
            progress_callback(1, 2)
        return self.Answer("sets", Provider.dataError or [{"id": 1}])

    def GetLastSets(
        self, playerID, playerNumber, callback, progress_callback=None, cancel_event=None
    ):
        callback.emit(self.Answer("last sets", {"playerNumber": playerNumber, "last_sets": [1]}))


class Listener:
    """What the manager's signals said, in order"""

    def __init__(self):
        self.events = []
        self.threads = set()
        for name in [
            "tournament_data_updated",
            "tournament_phases_updated",
            "tournament_changed",
            "sets_data_updated",
            "provider_error",
            "tournament_error",
        ]:
            getattr(manager.signals, name).connect(self.Slot(name))

    def Slot(self, name):
        def slot(*args):
            self.threads.add(threading.get_ident())
            self.events.append((name, *args))

        # Kept, so it can be disconnected
        setattr(self, name, slot)
        return slot

    def Of(self, name):
        return [e[1:] for e in self.events if e[0] == name]

    def Stop(self):
        for name in list(vars(self)):
            signal = getattr(manager.signals, name, None)
            if signal is not None:
                signal.disconnect(getattr(self, name))


def Reset():
    Settle()
    Provider.made = []
    Provider.connectError = Provider.dataError = None
    errorsShown.clear()
    settings.clear()
    manager.provider = None
    manager.loadFailed = False
    Providers.PROVIDERS[:] = [Provider]


def Load(url="https://fake.gg/event/e"):
    listener = Listener()
    manager.SetTournament(url)
    Settle()
    return listener


# =====================================================
# RUN
# =====================================================
def TestRun():
    Reset()
    manager.provider = provider = Provider("https://fake.gg/event/e")
    seen = {}

    def fn(progress_callback=None, cancel_event=None):
        seen["thread"] = threading.get_ident()
        seen["raising"] = Raising()
        progress_callback(1, 3)
        return 42

    results, progress, finished = [], [], []
    before = Worker.offGuiThreadCreations
    manager.Run(
        fn,
        lambda value: results.append((value, threading.get_ident())),
        on_progress=lambda n, t: progress.append((n, t, threading.get_ident())),
        on_finished=lambda: finished.append(threading.get_ident()),
    )
    assert Wait(lambda: finished)
    assert seen["thread"] != GUI_THREAD and seen["raising"], seen
    assert results == [(42, GUI_THREAD)] and finished == [GUI_THREAD], (results, finished)
    assert progress == [(1, 3, GUI_THREAD)], progress

    # What it raises goes to on_error, on the GUI thread
    errors, finished = [], []

    def failing(progress_callback=None, cancel_event=None):
        raise TransientError("no network")

    manager.Run(
        failing,
        results.append,
        lambda error: errors.append((error.kind, threading.get_ident())),
        on_finished=lambda: finished.append(1),
    )
    assert Wait(lambda: finished)
    assert errors == [(KIND_TRANSIENT, GUI_THREAD)] and len(results) == 1

    # Asked from another thread: started from the GUI thread, never a Worker
    # made off it
    results, finished = [], []
    thread = threading.Thread(
        target=lambda: manager.Run(
            fn,
            lambda value: results.append((value, threading.get_ident())),
            on_finished=lambda: finished.append(1),
        )
    )
    thread.start()
    thread.join()
    assert Wait(lambda: finished)
    assert results == [(42, GUI_THREAD)], results
    assert Worker.offGuiThreadCreations == before, "a Worker was made off the GUI thread"
    assert provider is manager.provider


def TestAnotherEventLoadedMeanwhile():
    Reset()
    manager.provider = first = Provider("https://fake.gg/event/a")
    release = first.Hold("tournament")
    results, errors, finished = [], [], []

    def fetch(progress_callback=None, cancel_event=None):
        return first.GetTournamentData()

    manager.Run(fetch, results.append, errors.append, on_finished=lambda: finished.append(1))
    # Another event is loaded before the first one's data arrives
    manager.provider = Provider("https://fake.gg/event/b")
    release.set()
    assert Wait(lambda: finished), "on_finished is called all the same"
    assert results == [] and errors == [], "event a's data was shown for event b"

    # The same for an error
    first = manager.provider
    release = first.Hold("tournament")
    Provider.dataError = TransientError("no network")
    finished = []
    manager.Run(fetch, results.append, errors.append, on_finished=lambda: finished.append(1))
    manager.provider = Provider("https://fake.gg/event/c")
    release.set()
    assert Wait(lambda: finished)
    assert results == [] and errors == []

    # What a provider method emits to its callback too (players' stats)
    Provider.dataError = None

    class Callback(QObject):
        got = Signal(object)

    callback = Callback()
    emitted = []
    callback.got.connect(emitted.append)
    current = manager.provider
    manager.GetLastSets(callback.got, [5, 6], 1)
    Settle()
    assert emitted == [{"playerNumber": 1, "last_sets": [1]}], emitted
    release = current.Hold("last sets")
    manager.GetLastSets(callback.got, [5, 6], 2)
    manager.provider = Provider("https://fake.gg/event/d")
    release.set()
    Settle()
    assert len(emitted) == 1, emitted


def TestLatestWins():
    Reset()
    manager.provider = provider = Provider("https://fake.gg/event/e")
    results, finished, cancelled = [], [], {}

    def Fetch(name, hold):
        def fetch(progress_callback=None, cancel_event=None):
            hold.wait(5)
            cancelled[name] = cancel_event.is_set()
            return name

        return fetch

    slow, fast = threading.Event(), threading.Event()
    manager.Run(
        Fetch("first", slow), results.append, key="k", on_finished=lambda: finished.append(1)
    )
    manager.Run(
        Fetch("second", fast), results.append, key="k", on_finished=lambda: finished.append(2)
    )
    # Another key isn't concerned
    manager.Run(
        Fetch("other", fast), results.append, key="o", on_finished=lambda: finished.append(3)
    )
    # The second answers first, the first one after it
    fast.set()
    assert Wait(lambda: len(finished) == 2)
    slow.set()
    assert Wait(lambda: len(finished) == 3)
    assert sorted(results) == ["other", "second"], results
    assert cancelled == {"first": True, "second": False, "other": False}, cancelled

    # Two sets loaded on a scoreboard, the first one slower than the second
    class Signals(QObject):
        UpdateSetData = Signal(object)

    class Scoreboard:
        scoreboardNumber = 1

        def __init__(self):
            self.signals = Signals()
            self.loaded = []
            self.signals.UpdateSetData.connect(self.loaded.append)

    scoreboard, other = Scoreboard(), Scoreboard()
    other.scoreboardNumber = 2
    release = provider.Hold("set 100")
    done = []
    manager.GetMatch(scoreboard, 100, on_finished=lambda: done.append(100))
    manager.GetMatch(scoreboard, 200, on_finished=lambda: done.append(200))
    manager.GetMatch(other, 300, on_finished=lambda: done.append(300))
    assert Wait(lambda: 200 in done and 300 in done)
    release.set()
    assert Wait(lambda: len(done) == 3)
    Settle()
    assert [d["id"] for d in scoreboard.loaded] == [200], scoreboard.loaded
    assert scoreboard.loaded[0]["overwrite"] is True
    assert [d["id"] for d in other.loaded] == [300], "another scoreboard's set"


# =====================================================
# LOADING AN EVENT
# =====================================================
def TestConnect():
    Reset()
    listener = Load("https://fake.gg/short/e")
    provider = Provider.made[0]
    assert manager.provider is provider and len(Provider.made) == 1
    # Made on the GUI thread, connected off it
    assert provider.madeOn == GUI_THREAD and provider.connectedOn not in (None, GUI_THREAD)
    # The link the provider resolves is the one kept
    assert provider.url == settings["TOURNAMENT_URL"] == "https://fake.gg/event/e"
    assert listener.Of("tournament_data_updated")[0][0]["tournamentName"] == provider.url
    assert listener.Of("tournament_phases_updated") == [([{"id": 1, "name": "Bracket"}],)]
    assert len(listener.Of("tournament_changed")) == 1 and not listener.Of("tournament_error")
    assert listener.threads == {GUI_THREAD}
    # Everything was asked off the GUI thread, raising its errors
    assert all(thread != GUI_THREAD and raising for _, thread, raising in provider.calls)
    listener.Stop()

    # The same link again: nothing to do
    listener = Load("https://fake.gg/event/e")
    assert len(Provider.made) == 1 and listener.events == []
    listener.Stop()


def TestConnectErrors():
    for error, kind, retry, text in [
        (AuthError("bad key"), KIND_AUTH, False, "refused"),
        (NotFoundError("no event"), KIND_NOT_FOUND, False, "wasn't found on fake.gg"),
        (TransientError("no network"), KIND_TRANSIENT, True, "couldn't be reached"),
        # Anything else counts as worth trying again
        (RuntimeError("bug"), KIND_TRANSIENT, True, "couldn't be reached"),
    ]:
        Reset()
        Provider.connectError = error
        listener = Load()
        url = "https://fake.gg/event/e"
        # No provider, nothing of the previous event left, and why
        assert manager.provider is None, kind
        assert listener.Of("tournament_data_updated") == [({},)], listener.events
        assert listener.Of("tournament_phases_updated") == [([],)]
        assert len(listener.Of("tournament_changed")) == 1
        failed = listener.Of("tournament_error")
        assert len(failed) == 1 and failed[0][:2] == (url, kind), failed
        assert text in failed[0][2], failed[0][2]
        assert errorsShown == [(url, failed[0][2], retry)], errorsShown
        assert listener.Of("provider_error")[0][:2] == ("connect", kind)
        # The link is kept, to be tried at the next start too
        assert settings["TOURNAMENT_URL"] == url
        listener.Stop()

        # Loading the same link again tries again
        Provider.connectError = None
        listener = Load()
        assert manager.provider is Provider.made[-1] and len(Provider.made) == 2, kind
        assert not listener.Of("tournament_error")
        assert listener.Of("tournament_data_updated")[0][0]["tournamentName"] == url
        listener.Stop()

    # When the app starts, no message: the error is only signaled
    Reset()
    Provider.connectError = TransientError("no network")
    listener = Listener()
    manager.SetTournament("https://fake.gg/event/e", initialLoading=True)
    Settle()
    assert len(listener.Of("tournament_error")) == 1 and errorsShown == []
    listener.Stop()


def TestDataErrors():
    # The event's data can't be loaded: the event isn't there
    Reset()
    Provider.dataError = NotFoundError("no event")
    listener = Load()
    assert manager.provider is not None
    assert listener.Of("tournament_data_updated") == [({"initial_load": False},)]
    assert listener.Of("tournament_phases_updated") == [([],)], "another event's phases stay"
    assert [e[:2] for e in listener.Of("tournament_error")] == [
        ("https://fake.gg/event/e", KIND_NOT_FOUND)
    ]
    listener.Stop()
    # Loading it again tries again
    Provider.dataError = None
    listener = Load()
    assert len(Provider.made) == 2 and not listener.Of("tournament_error")
    assert listener.Of("tournament_data_updated")[0][0]["tournamentName"]
    listener.Stop()

    # Loaded, then a refresh fails: what's shown is kept
    Provider.dataError = TransientError("no network")
    errorsShown.clear()
    listener = Listener()
    manager.GetTournamentData()
    manager.GetTournamentPhases()
    Settle()
    assert not listener.Of("tournament_data_updated"), "the tournament's data was blanked"
    assert not listener.Of("tournament_phases_updated"), "the phases were emptied"
    assert not listener.Of("tournament_error") and errorsShown == []
    assert sorted(e[:2] for e in listener.Of("provider_error")) == [
        ("phases", KIND_TRANSIENT),
        ("tournament", KIND_TRANSIENT),
    ]

    # The set list says it couldn't load, instead of showing no sets
    manager.LoadSets(False)
    Settle()
    assert listener.Of("sets_data_updated")[-1][0]["error"] == "no network"
    Provider.dataError = None
    listener.events.clear()
    manager.LoadSets(False)
    Settle()
    updates = [e[0] for e in listener.Of("sets_data_updated")]
    assert updates[0] == {"progress": 1, "totalPages": 2, "sets": []}, updates
    assert updates[-1] == {"progress": 0, "totalPages": 0, "sets": [{"id": 1}]}, updates
    listener.Stop()


def TestProvidersAskNothingWhenMade():
    """Making a provider (on the GUI thread) sends nothing: no request, no
    gRPC call"""
    import grpc

    from src.TournamentDataProvider import StartGGClient

    def NoNetwork(*args, **kwargs):
        raise AssertionError("the network was used to make a provider")

    realChannel, realRequest = grpc.secure_channel, StartGGClient._session.request
    grpc.secure_channel = NoNetwork
    StartGGClient._session.request = NoNetwork
    try:
        parry = ParryGGDataProvider(
            "https://parry.gg/my-tournament/_manage/my-event", None, None, "k"
        )
        assert (parry.tournament_slug, parry.event_slug) == ("my-tournament", "my-event")
        assert parry.event_id is None and parry.metadata == [("x-api-key", "k")]
        StartGGDataProvider("https://www.start.gg/tournament/t/event/e", None, None)
        StartGGDataProvider("https://www.start.gg/admin/tournament/t/brackets/123", None, None)
    finally:
        grpc.secure_channel, StartGGClient._session.request = realChannel, realRequest
        parry.channel = None


if __name__ == "__main__":
    for test in [
        TestRun,
        TestAnotherEventLoadedMeanwhile,
        TestLatestWins,
        TestConnect,
        TestConnectErrors,
        TestDataErrors,
        TestProvidersAskNothingWhenMade,
    ]:
        test()
        print(f"{test.__name__}: OK")
    Reset()
    Providers.PROVIDERS[:] = [StartGGDataProvider, ParryGGDataProvider]
    print("All data manager checks passed")
