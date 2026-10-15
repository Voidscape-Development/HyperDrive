# Checks fetching players' mains and the event's entrants in the background:
# - PlayerMains (prefetch for the entrants, and a queue for players loaded
#   without them): what it skips, saving in batches, stopping when the event
#   or the game changes
# - TournamentDataManager.LoadEntrants and EnrichPlayer: the manager, not the
#   provider, saves players and starts the background fetching, and only for
#   providers with SUPPORTS_MAINS_PREFETCH (start.gg, not parry.gg)
# - start.gg's MainsKey, IsMainsCached, FetchMains and EnrichPlayerData
# Run from the repository root: python test/test_player_mains.py
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

from qtpy.QtWidgets import QApplication

app = QApplication(sys.argv)

from src import PlayerMains as PlayerMainsModule
from src.GameAssetManager import GameAssetManager
from src.PlayerDB import PlayerDB
from src.PlayerMains import PlayerMains
from src.TournamentDataManager import TournamentDataManager
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider

PlayerMains.INTERVAL_SECS = 0


# =====================================================
# STAND-INS
# =====================================================
class Saved:
    """The player database: what was added, and the mains it already has"""

    def __init__(self, database=None):
        self.added = []
        self.threads = []
        PlayerDB.database = database or {}
        PlayerDB.AddPlayers = staticmethod(self.Add)

    def Add(self, players, *args, **kwargs):
        self.added.append(list(players))
        self.threads.append(threading.current_thread() is threading.main_thread())


def SetGame(codename="ssbu", startggId=1386):
    GameAssetManager.instance = types.SimpleNamespace(
        selectedGame={"codename": codename, "smashgg_game_id": startggId}
    )


def Player(tag, slug=None, prefix=None):
    return {"gamerTag": tag, "prefix": prefix, "startgg_user_slug": slug}


class FakeProvider(TournamentDataProvider):
    """Mains by player slug: {slug: mains}, None for a failed request"""

    NAME = "Fake"
    SUPPORTS_MAINS_PREFETCH = True

    def __init__(self, mains=None, entrants=()):
        super().__init__("https://fake.gg/e", None, None)
        self.mains = mains or {}
        self.entrants = list(entrants)
        self.cache = {}
        self.fetched = []
        self.enriched = []

    def MainsKey(self, player):
        return player.get("startgg_user_slug")

    def IsMainsCached(self, key):
        return key in self.cache

    def FetchMains(self, key):
        self.fetched.append(key)
        mains = self.mains.get(key)
        if mains is not None:
            self.cache[key] = mains
        return mains

    def FetchEntrants(self, progress_callback=None, cancel_event=None):
        return self.entrants

    def EnrichPlayerData(self, playerData, blocking=True):
        self.enriched.append((playerData.get("gamerTag"), blocking))
        return playerData


class NoPrefetch(FakeProvider):
    """Like parry.gg: mains only through EnrichPlayerData"""

    SUPPORTS_MAINS_PREFETCH = False


def WaitFor(condition, timeout=5):
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.01)


# =====================================================
# PREFETCH
# =====================================================
def TestPrewarm():
    SetGame()
    saved = Saved({"Saved": {"mains": {"ssbu": [["Mario"]]}}})
    provider = FakeProvider(
        {"a": {"ssbu": [["Fox"]]}, "b": {}, "c": None, "d": {"ssbu": [["Ness"]]}}
    )
    provider.cache["cached"] = {"ssbu": [["Kirby"]]}
    players = [
        Player("A", "a"),
        Player("NoSlug"),
        Player("Cached", "cached"),
        Player("Saved", "saved"),
        Player("B", "b"),
        Player("C", "c"),
        Player("D", "d", prefix="T"),
    ]
    PlayerMains(provider, lambda: True, lambda: None)._Prewarm(players)

    # Asked only for who isn't known: no key, cached or saved are skipped
    assert provider.fetched == ["a", "b", "c", "d"], provider.fetched
    # Found mains are saved; no mains ({}) and failures (None) aren't
    assert saved.added == [
        [
            {"prefix": None, "gamerTag": "A", "mains": {"ssbu": [["Fox"]]}},
            {"prefix": "T", "gamerTag": "D", "mains": {"ssbu": [["Ness"]]}},
        ]
    ], saved.added
    # A failure isn't cached, so it's asked again later
    assert "c" not in provider.cache and "b" in provider.cache


def TestPrewarmSavesInBatches():
    SetGame()
    saved = Saved()
    provider = FakeProvider({str(i): {"ssbu": [["Fox"]]} for i in range(5)})
    mains = PlayerMains(provider, lambda: True, lambda: None)
    mains.PREWARM_BATCH = 2
    mains._Prewarm([Player(f"P{i}", str(i)) for i in range(5)])
    assert [len(batch) for batch in saved.added] == [2, 2, 1], saved.added


def TestPrewarmStops():
    # When another event is loaded
    SetGame()
    Saved()
    provider = FakeProvider({"a": {}, "b": {}, "c": {}})
    current = [True]

    def fetch(key):
        current[0] = False
        return FakeProvider.FetchMains(provider, key)

    provider.FetchMains = fetch
    PlayerMains(provider, lambda: current[0], lambda: None)._Prewarm(
        [Player("A", "a"), Player("B", "b"), Player("C", "c")]
    )
    assert provider.fetched == ["a"], provider.fetched

    # When another game is picked
    SetGame()
    provider = FakeProvider({"a": {}, "b": {}})

    def fetchThenSwitch(key):
        SetGame("ssbm", 1)
        return FakeProvider.FetchMains(provider, key)

    provider.FetchMains = fetchThenSwitch
    PlayerMains(provider, lambda: True, lambda: None)._Prewarm([Player("A", "a"), Player("B", "b")])
    assert provider.fetched == ["a"], provider.fetched


# =====================================================
# QUEUE
# =====================================================
def TestQueue():
    SetGame()
    saved = Saved({"Saved": {"mains": {"ssbu": [["Mario"]]}}})
    provider = FakeProvider({"a": {"ssbu": [["Fox"]]}, "b": {}})
    provider.cache["cached"] = {}
    updates = []
    mains = PlayerMains(provider, lambda: True, lambda: updates.append(1))

    gate = threading.Event()
    realFetch = provider.FetchMains

    def slowFetch(key):
        gate.wait(5)
        return realFetch(key)

    provider.FetchMains = slowFetch
    for player in [
        Player("A", "a"),
        Player("A", "a"),  # already queued
        Player("NoSlug"),
        Player("Cached", "cached"),
        Player("Saved", "saved"),
        Player("B", "b"),
    ]:
        mains.Queue(player)
    queued = [key for key, _ in mains.queue]
    gate.set()
    WaitFor(lambda: mains.queueThread is None and not mains.queue)

    # The thread may have taken A already; nothing else was queued, and A once
    assert queued in (["a", "b"], ["b"]), queued
    assert provider.fetched == ["a", "b"], provider.fetched
    assert saved.added == [[{"prefix": None, "gamerTag": "A", "mains": {"ssbu": [["Fox"]]}}]]
    assert updates, "no update signal"
    assert not mains.queued


# =====================================================
# THE MANAGER
# =====================================================
class SyncPool:
    """Runs workers in a thread, like the app's pool, and waits for them"""

    def start(self, worker):
        thread = threading.Thread(target=worker.run)
        thread.start()
        thread.join()


def Manager(provider):
    manager = TournamentDataManager.instance
    manager.provider = provider
    manager.threadPool = SyncPool()
    manager._mains = None
    return manager


def TestLoadEntrants():
    SetGame()
    players = [Player("A", "a"), Player("B", "b")]
    for providerClass, prefetch in [(FakeProvider, True), (NoPrefetch, False)]:
        saved = Saved()
        provider = providerClass({"a": {"ssbu": [["Fox"]]}}, entrants=players)
        prewarmed = []
        PlayerMainsModule.PlayerMains.Prewarm = lambda self, p: prewarmed.append(list(p))
        try:
            Manager(provider).LoadEntrants()
        finally:
            del PlayerMainsModule.PlayerMains.Prewarm
        # The manager saves them, off the UI thread
        assert saved.added == [players] and saved.threads == [False], (
            providerClass,
            saved.added,
        )
        assert prewarmed == ([players] if prefetch else []), (providerClass, prewarmed)


def TestEnrichPlayer():
    SetGame()
    Saved()
    for providerClass, queues in [(FakeProvider, True), (NoPrefetch, False)]:
        provider = providerClass({"a": {}})
        manager = Manager(provider)
        queued = []
        PlayerMainsModule.PlayerMains.Queue = lambda self, p: queued.append(p["gamerTag"])
        try:
            manager.EnrichPlayer(Player("A", "a"), blocking=True)
            manager.EnrichPlayer(Player("B", "b"), blocking=False)
            manager.EnrichPlayer({**Player("C", "c"), "mains": {"ssbu": []}}, blocking=False)
        finally:
            del PlayerMainsModule.PlayerMains.Queue
        assert provider.enriched == [("A", True), ("B", False), ("C", False)], provider.enriched
        # Only a non-blocking load still without mains is fetched in the
        # background, and only with SUPPORTS_MAINS_PREFETCH
        assert queued == (["B"] if queues else []), (providerClass, queued)


# =====================================================
# START.GG'S MAINS
# =====================================================
def TestStartGGMains():
    SetGame()
    provider = StartGGDataProvider("https://www.start.gg/tournament/t/event/e", None, None)
    answers = {"u1": {"ssbu": [["Fox"]]}, "u2": None}
    asked = []

    def fetch(slug, videogameId):
        asked.append((slug, videogameId))
        return answers.get(slug)

    provider._FetchUserMains = fetch
    one, two = Player("One", "user/u1"), Player("Two", "user/u2")
    one["startgg_user_slug"], two["startgg_user_slug"] = "u1", "u2"

    assert provider.MainsKey(one) == ("u1", 1386)
    assert provider.MainsKey(Player("NoSlug")) is None
    # Without blocking, nothing is fetched
    assert "mains" not in provider.EnrichPlayerData(dict(one), blocking=False) and not asked
    # Blocking: fetched, cached, and not asked again
    assert provider.EnrichPlayerData(dict(one), blocking=True)["mains"] == answers["u1"]
    assert provider.EnrichPlayerData(dict(one), blocking=False)["mains"] == answers["u1"]
    assert provider.GetCachedMains(one) == answers["u1"] and asked == [("u1", 1386)]
    # A failed request isn't cached
    assert provider.FetchMains(("u2", 1386)) is None
    assert not provider.IsMainsCached(("u2", 1386))
    provider.FetchMains(("u2", 1386))
    assert asked.count(("u2", 1386)) == 2, asked


if __name__ == "__main__":
    for test in [
        TestPrewarm,
        TestPrewarmSavesInBatches,
        TestPrewarmStops,
        TestQueue,
        TestLoadEntrants,
        TestEnrichPlayer,
        TestStartGGMains,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All player mains checks passed")
