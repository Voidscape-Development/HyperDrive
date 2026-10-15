# Checks how a tournament data provider is picked and what each declares:
# - Providers.ProviderClassFor finds the provider for an event link
# - every provider says what it is (host, game ids, icon, button text with
#   its translations) and what it can do (SUPPORTS_* flags)
# - loading an event here (SetTournament) and from the web server
#   (SetTournamentSignal) make the same provider, with its API key
# Run from the repository root: python test/test_providers.py
import html
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

from qtpy.QtWidgets import QApplication

app = QApplication(sys.argv)

from src.GameAssetManager import GameAssetManager
from src.SettingsManager import SettingsManager
from src.TournamentDataManager import TournamentDataManager
from src.TournamentDataProvider import Providers
from src.TournamentDataProvider.ParryGGDataProvider import ParryGGDataProvider
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider

FLAGS = [
    "SUPPORTS_BRACKETS",
    "SUPPORTS_STATS",
    "SUPPORTS_COMPLETED_SETS",
    "SUPPORTS_SET_ACTIONS",
]


# =====================================================
# PICKING A PROVIDER
# =====================================================
def TestProviderClassFor():
    cases = {
        "https://www.start.gg/tournament/t/event/e": StartGGDataProvider,
        "https://start.gg/admin/tournament/t/brackets/123": StartGGDataProvider,
        "https://parry.gg/t/e": ParryGGDataProvider,
        "https://challonge.com/t": None,
        "": None,
        None: None,
    }
    for url, expected in cases.items():
        got = Providers.ProviderClassFor(url)
        assert got is expected, f"{url!r}: {got}, expected {expected}"


# =====================================================
# WHAT EACH PROVIDER DECLARES
# =====================================================
def TestDeclarations():
    with open("src/i18n/HyperDrive_en.ts", encoding="utf-8") as f:
        translations = f.read()

    for provider in Providers.PROVIDERS:
        name = provider.__name__
        assert provider.NAME and provider.HOST, name
        assert provider.GAME_ID_KIND in ("startgg", "igdb"), name
        assert os.path.exists(provider.ICON), f"{name}: no {provider.ICON}"
        # Translated strings are found by lupdate through QT_TRANSLATE_NOOP
        for text in [provider.COMPLETED_SETS_BUTTON, provider.API_KEY_MISSING]:
            if text:
                source = f"<source>{html.escape(text, quote=False)}</source>"
                assert source in translations, f"{name}: {text!r}"
        if provider.API_KEY_SETTING:
            assert provider.API_KEY_MISSING and provider.API_KEY_URL, name
        for flag in FLAGS:
            assert isinstance(getattr(provider, flag), bool), f"{name}.{flag}"
        assert provider.HOST not in [p.HOST for p in Providers.PROVIDERS if p is not provider], (
            f"{name}: host shared"
        )

    # What each can do today
    assert [f for f in FLAGS if getattr(StartGGDataProvider, f)] == FLAGS
    assert [f for f in FLAGS if getattr(ParryGGDataProvider, f)] == [
        "SUPPORTS_STATS",
        "SUPPORTS_COMPLETED_SETS",
    ]
    for flag in FLAGS:
        assert getattr(TournamentDataProvider, flag) is False, flag

    # parry.gg names its rounds with start.gg's TranslateRoundName
    from src.TournamentDataProvider import StartGGConvert

    assert StartGGDataProvider.TranslateRoundName is StartGGConvert.TranslateRoundName

    # provider.name, which the logs and players' data use, comes from NAME
    assert StartGGDataProvider("https://www.start.gg/t", None, None).name == "StartGG"


# =====================================================
# LOADING AN EVENT
# =====================================================
class SyncPool:
    def start(self, worker):
        worker.run()


class FakeProvider(TournamentDataProvider):
    """Records how it was made, and asks nothing of the network"""

    made = []

    def __init__(self, url, threadpool, dataManager, api_key=None):
        super().__init__(url, threadpool, dataManager, api_key)
        FakeProvider.made.append((type(self).__name__, url, api_key))
        self.videogame = 1386

    def GetRealEventURL(self, url):
        self.url = url.replace("/short/", "/event/")
        return self.url

    # The game GetTournamentData finds, None for none
    game = None

    def GetTournamentData(self, progress_callback=None, cancel_event=None):
        if FakeProvider.game:
            self.videogame = self.videogameFound = FakeProvider.game
        return {"tournamentName": "T"}

    def GetTournamentPhases(self, progress_callback=None, cancel_event=None):
        return []


class FakeNoKey(FakeProvider):
    NAME = "FakeNoKey"
    HOST = "nokey.gg"
    GAME_ID_KIND = "startgg"


class FakeWithKey(FakeProvider):
    NAME = "FakeWithKey"
    HOST = "withkey.gg"
    API_KEY_SETTING = "api_keys.withkey"
    API_KEY_MISSING = "No key"
    API_KEY_URL = "https://withkey.gg/keys"
    GAME_ID_KIND = "igdb"


class FakeGames:
    def __init__(self):
        self.calls = []

    def SetGameFromStartGGId(self, id):
        self.calls.append(("startgg", id))

    def SetGameFromIGDBId(self, id):
        self.calls.append(("igdb", id))

    def LoadGameAssets(self, game):
        self.calls.append(("load", game))


def LoadEvent(load, url, settings):
    """Loads an event with load ("here" or "remote") and returns the
    manager, the providers made, the missing key messages and the games set"""
    manager = TournamentDataManager.instance
    manager.provider = None
    manager.threadPool = SyncPool()
    FakeProvider.made = []
    missing = []
    manager.ShowApiKeyMissing = lambda providerClass: missing.append(providerClass.NAME)
    SettingsManager.Get = staticmethod(lambda key, default=None: settings.get(key, default))
    SettingsManager.Set = staticmethod(lambda key, value: settings.__setitem__(key, value))
    games = FakeGames()
    GameAssetManager.instance = games

    if load == "here":
        manager.SetTournament(url)
    else:
        manager.SetTournamentSignal(url)
    return manager, FakeProvider.made, missing, games


def TestLoadingAnEvent():
    Providers.PROVIDERS[:] = [FakeNoKey, FakeWithKey]
    try:
        for load in ["here", "remote"]:
            # Its key reaches the provider, from either path
            settings = {"api_keys.withkey": "secret"}
            manager, made, missing, games = LoadEvent(load, "https://withkey.gg/e", settings)
            assert made == [("FakeWithKey", "https://withkey.gg/e", "secret")], (load, made)
            assert isinstance(manager.provider, FakeWithKey) and not missing, load
            assert settings["TOURNAMENT_URL"] == "https://withkey.gg/e", load

            # Without its key: no provider, and the message says why
            settings = {}
            manager, made, missing, games = LoadEvent(load, "https://withkey.gg/e", settings)
            assert manager.provider is None and made == [] and missing == ["FakeWithKey"], load
            assert games.calls == [("load", 0)], (load, games.calls)

            # The link the provider resolves is the one kept
            settings = {}
            manager, made, missing, games = LoadEvent(load, "https://nokey.gg/short/e", settings)
            assert made == [("FakeNoKey", "https://nokey.gg/short/e", None)], (load, made)
            assert settings["TOURNAMENT_URL"] == "https://nokey.gg/event/e", load
            assert manager.provider.url == "https://nokey.gg/event/e", load

            # No provider for the link
            settings = {}
            manager, made, missing, games = LoadEvent(load, "https://challonge.com/t", settings)
            assert manager.provider is None and made == [] and not missing, load
    finally:
        Providers.PROVIDERS[:] = [StartGGDataProvider, ParryGGDataProvider]


def TestGameFromProvider():
    Providers.PROVIDERS[:] = [FakeNoKey, FakeWithKey]
    try:
        for url, kind in [("https://nokey.gg/e", "startgg"), ("https://withkey.gg/e", "igdb")]:
            manager, made, missing, games = LoadEvent("here", url, {"api_keys.withkey": "k"})
            games.calls.clear()
            manager.SetGameFromProvider()
            assert games.calls == [(kind, 1386)], (url, games.calls)
    finally:
        Providers.PROVIDERS[:] = [StartGGDataProvider, ParryGGDataProvider]


def TestGameChanged():
    """The manager says the event's game changed, before its data"""
    Providers.PROVIDERS[:] = [FakeNoKey, FakeWithKey]
    manager = TournamentDataManager.instance
    events = []

    def onGame(game):
        events.append(("game", game))

    def onData(data):
        events.append(("data", data.get("tournamentName")))

    manager.signals.game_changed.connect(onGame)
    manager.signals.tournament_data_updated.connect(onData)
    try:
        for game, expected in [(1386, [("game", 1386), ("data", "T")]), (None, [("data", "T")])]:
            FakeProvider.game = game
            LoadEvent("here", "https://nokey.gg/e", {})
            events.clear()
            manager.GetTournamentData()
            assert events == expected, (game, events)
    finally:
        FakeProvider.game = None
        manager.signals.game_changed.disconnect(onGame)
        manager.signals.tournament_data_updated.disconnect(onData)
        Providers.PROVIDERS[:] = [StartGGDataProvider, ParryGGDataProvider]


def TestGetMatchDoesNotWaitForASlowApi():
    """start.gg's GetMatch asks both its APIs at once; one too slow is
    left out rather than waited for"""
    provider = StartGGDataProvider("https://www.start.gg/tournament/t/event/e", None, None)
    provider._request_timeout_secs = 0.3

    def slow(setId, progress_callback, cancel_event):
        time.sleep(2)
        return {"from": "old"}

    provider._GetMatchTasks = slow
    provider._GetMatchNewApi = lambda setId, progress_callback, cancel_event: {"id": setId}
    start = time.monotonic()
    result = provider.GetMatch("123")
    took = time.monotonic() - start
    assert took < 1.5, f"waited {took:.1f}s for the slow API"
    assert result.get("id") == "123" and "from" not in result, result


def TestAppContext():
    """The app's context is its game, setting and player database"""
    from src.PlayerDB import PlayerDB
    from src.TournamentDataProvider.ProviderContext import AppContext

    context = AppContext()
    games = FakeGames()
    GameAssetManager.instance = games
    assert context.games is games

    settings = {"general.local_player_data": True}
    SettingsManager.Get = staticmethod(lambda key, default=None: settings.get(key, default))
    assert context.UseLocalPlayerData() is True
    settings.clear()
    assert context.UseLocalPlayerData() is False

    saved = []
    getPlayer, addPlayers = PlayerDB.GetPlayer, PlayerDB.AddPlayers
    PlayerDB.GetPlayer = staticmethod(lambda tag: {"gamerTag": tag})
    PlayerDB.AddPlayers = staticmethod(lambda players, *a, **k: saved.extend(players))
    try:
        assert context.GetSavedPlayer("T") == {"gamerTag": "T"}
        context.SavePlayers([{"gamerTag": "A"}])
        assert saved == [{"gamerTag": "A"}]
    finally:
        PlayerDB.GetPlayer, PlayerDB.AddPlayers = getPlayer, addPlayers

    # Providers get it unless they're given another
    assert isinstance(StartGGDataProvider("https://www.start.gg/t", None, None).context, AppContext)
    other = AppContext()
    assert StartGGDataProvider("https://www.start.gg/t", None, None, context=other).context is other


if __name__ == "__main__":
    for test in [
        TestProviderClassFor,
        TestDeclarations,
        TestLoadingAnEvent,
        TestGameFromProvider,
        TestGameChanged,
        TestGetMatchDoesNotWaitForASlowApi,
        TestAppContext,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All provider checks passed")
