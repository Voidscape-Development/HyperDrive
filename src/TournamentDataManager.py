import threading
import time

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameAssetManager import GameAssetManager
from .Helpers.VersionHelper import get_supported_providers
from .PlayerDB import PlayerDB
from .PlayerMains import PlayerMains
from .SelectEventWindow import SelectEventWindow
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TournamentDataProvider.Providers import ProviderClassFor
from .TournamentDataProvider.TournamentDataProvider import TournamentDataProvider
from .TournamentDataProvider.TournamentEventLookup import ParseTournamentLink
from .Workers import Worker


class TournamentDataManagerSignals(QObject):
    tournament_changed = Signal()
    entrants_updated = Signal()
    tournament_data_updated = Signal(dict)
    completed_sets_updated = Signal(list)
    twitch_username_updated = Signal()
    get_sets_finished = Signal(list)
    get_stations_finished = Signal(list)
    tournament_phases_updated = Signal(list)
    tournament_phasegroup_updated = Signal(dict)
    tournament_phasegroup_sets_updated = Signal(dict)
    game_changed = Signal(int)
    sets_data_updated = Signal(dict)
    tournament_url_update = Signal(str)
    # Mains requested by a non-blocking EnrichPlayerData arrived
    player_mains_updated = Signal()


class TournamentDataManager(QObject):
    instance: "TournamentDataManager" = None

    def __init__(self) -> None:
        super().__init__(None)
        self.provider: TournamentDataProvider = None
        self.signals: TournamentDataManagerSignals = TournamentDataManagerSignals()
        self.entrantsModel: QStandardItemModel = None
        self.threadPool = QThreadPool()

        self.signals.game_changed.connect(self.GameChanged)
        self.signals.tournament_url_update.connect(self.SetTournamentSignal)

        GameAssetManager.instance.signals.onLoadAssets.connect(self.SetGameFromProvider)

        self.setLoadingWorker = None
        # Background mains fetching for the provider, see MainsFor
        self._mains = None
        self._mainsLock = threading.Lock()

    # =====================================================
    # SETUP
    # =====================================================
    def UiMounted(self):
        if SettingsManager.Get("TOURNAMENT_URL"):
            TournamentDataManager.instance.SetTournament(
                SettingsManager.Get("TOURNAMENT_URL"), initialLoading=True
            )
            TournamentDataManager.instance.signals.twitch_username_updated.emit()

    def GetProvider(self):
        return self.provider

    def GameChanged(self, videogame):
        StateManager.Set("provider_videogame", {"id": videogame})
        self.SetGameFromProvider()

    def SetGameFromProvider(self):

        if not self.provider or not self.provider.videogame:
            return

        # The provider's videogame ids are start.gg's or IGDB's
        setGame = {
            "startgg": GameAssetManager.instance.SetGameFromStartGGId,
            "igdb": GameAssetManager.instance.SetGameFromIGDBId,
        }.get(self.provider.GAME_ID_KIND)
        if setGame:
            setGame(self.provider.videogame)
        else:
            logger.error("Unsupported provider...")

    # =====================================================
    # TOURNAMENT
    # =====================================================
    def CreateProvider(self, url):
        """A provider for the event link, None if there's none for it or it
        can't be made (its API key isn't set)"""
        providerClass = ProviderClassFor(url)
        if providerClass is None:
            logger.error("Unsupported provider...")
            return None

        apiKey = None
        if providerClass.API_KEY_SETTING:
            apiKey = SettingsManager.Get(providerClass.API_KEY_SETTING)
            if not apiKey:
                logger.error(f"{providerClass.NAME} API key not set")
                self.ShowApiKeyMissing(providerClass)
                return None

        try:
            return providerClass(url, self.threadPool, self, apiKey)
        except Exception as e:
            logger.error(f"Failed to initialize {providerClass.NAME} provider: {e}")
            return None

    def ShowApiKeyMissing(self, providerClass):
        url = providerClass.API_KEY_URL
        messagebox = QMessageBox()
        messagebox.setWindowTitle(QApplication.translate("app", "Error"))
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setText(
            QApplication.translate("app", providerClass.API_KEY_MISSING)
            + "<br><br>"
            + QApplication.translate("app", "API keys can be created at: ")
            + f'<a href="{url}">{url.split("://")[-1]}</a>'
        )
        messagebox.exec()

    @Slot(str, bool)
    @Slot(str)
    def SetTournament(self, url, initialLoading=False):
        if self.provider and self.provider.url == url:
            return

        TournamentDataManager.instance.provider = self.CreateProvider(url)
        if self.provider is not None:
            # A start.gg admin link becomes its event's link
            url = self.provider.GetRealEventURL(url)

        SettingsManager.Set("TOURNAMENT_URL", url)

        if self.provider is not None:
            self.GetTournamentData(initialLoading=initialLoading)
            self.GetTournamentPhases()

            self.LoadEntrants()
            TournamentDataManager.instance.signals.tournament_changed.emit()
        else:
            TournamentDataManager.instance.signals.tournament_data_updated.emit({})
            TournamentDataManager.instance.signals.tournament_phases_updated.emit([])
            TournamentDataManager.instance.signals.tournament_changed.emit()
            GameAssetManager.instance.LoadGameAssets(0)

    def SetTournamentSignal(self, url, initialLoading=False):
        # An event loaded from the web server (/load-tournament), like one
        # loaded here
        self.SetTournament(url, initialLoading)

    def SetStartggEventSlug(self, mainWindow):
        inp = QDialog(mainWindow)

        layout = QVBoxLayout()
        inp.setLayout(layout)

        inp.layout().addWidget(
            QLabel(
                QApplication.translate("app", "Paste the tournament URL.")
                + "\n"
                + QApplication.translate(
                    "app",
                    "A tournament link, start.gg short link or tournament slug lets you pick one of its events. Its other events are listed in the tournament's menu in the top bar, to switch to one later.",
                )
                + "\n"
                + QApplication.translate("app", "Supported providers:")
                + " "
                + ", ".join(get_supported_providers())
            )
        )

        lineEdit = QLineEdit()
        okButton = QPushButton(QApplication.translate("app", "OK"))

        def validateText():
            okButton.setDisabled(ParseTournamentLink(lineEdit.text()) is None)

        lineEdit.textEdited.connect(validateText)

        inp.layout().addWidget(lineEdit)

        okButton.clicked.connect(inp.accept)
        okButton.setDisabled(True)
        inp.layout().addWidget(okButton)

        inp.setWindowTitle(QApplication.translate("app", "Set tournament URL"))
        inp.resize(600, 10)

        if inp.exec_() == QDialog.Accepted:
            # An event link opens its tournament, with that event selected
            self.ShowEventPicker(mainWindow, ParseTournamentLink(lineEdit.text()))

        inp.deleteLater()

    def SelectEvent(self, mainWindow):
        # Picks another event of the loaded event's tournament. The provider's
        # URL is used as TOURNAMENT_URL is cleared when an event fails to load.
        url = self.provider.url if self.provider else SettingsManager.Get("TOURNAMENT_URL")
        parsed = ParseTournamentLink(url)
        if parsed is None:
            logger.error("No tournament is loaded to select an event from")
            return
        self.ShowEventPicker(mainWindow, parsed)

    def ShowEventPicker(self, mainWindow, parsed):
        def loadEvent(url):
            SettingsManager.Set("TOURNAMENT_URL", url)
            TournamentDataManager.instance.SetTournament(SettingsManager.Get("TOURNAMENT_URL"))

        SelectEventWindow(mainWindow, self.threadPool, loadEvent).Load(
            parsed, SettingsManager.Get("api_keys.parrygg")
        )

    def SetTwitchUsername(self, window):
        input_dialog = QInputDialog(window)
        input_dialog.setWindowTitle(QApplication.translate("app", "Set Twitch username"))
        input_dialog.setLabelText(QApplication.translate("app", "Twitch Username:") + " ")
        input_dialog.setCancelButtonText(QApplication.translate("app", "Cancel"))
        input_dialog.setOkButtonText(QApplication.translate("app", "OK"))

        if input_dialog.exec_() == QDialog.Accepted:
            SettingsManager.Set("twitch_username", input_dialog.textValue())

    def GetTournamentData(self, initialLoading=False):
        provider = self.provider

        def fetch(progress_callback=None, cancel_event=None):
            provider.videogameFound = None
            data = provider.GetTournamentData()
            return data, provider.videogameFound

        def loaded(result):
            tournamentData, videogame = result
            # The event's game first, as the layouts' game comes with it
            if videogame:
                self.signals.game_changed.emit(videogame)
            tournamentData.update({"initial_load": initialLoading})
            TournamentDataManager.instance.signals.tournament_data_updated.emit(tournamentData)

        worker = Worker(fetch)
        worker.signals.result.connect(loaded)
        self.threadPool.start(worker)

    def RepullEntrants(self):
        # For entrants who registered after the event was loaded. Players
        # already pulled are updated, not removed.
        self.LoadEntrants()

    # =====================================================
    # ENTRANTS AND PLAYERS
    # =====================================================
    def LoadEntrants(self):
        """Adds the event's entrants to the player database, in the
        background, then fetches their mains ahead of time"""
        provider = self.provider
        if provider is None:
            return

        def load(progress_callback=None, cancel_event=None):
            players = provider.FetchEntrants(progress_callback, cancel_event)
            PlayerDB.AddPlayers(players)
            # The entrants query doesn't carry each player's last set (that
            # blew start.gg's complexity cap), so mains are filled in the
            # background instead of the scoreboard fetching them one by one
            mains = self.MainsFor(provider)
            if mains is not None and players:
                mains.Prewarm(players)

        self.threadPool.start(Worker(load))

    def MainsFor(self, provider):
        """The background mains fetching for the provider, None if it has
        none (SUPPORTS_MAINS_PREFETCH)"""
        if not provider.SUPPORTS_MAINS_PREFETCH:
            return None
        with self._mainsLock:
            if self._mains is None or self._mains.provider is not provider:
                self._mains = PlayerMains(
                    provider,
                    isCurrent=lambda: self.provider is provider,
                    onUpdated=self.signals.player_mains_updated.emit,
                )
            return self._mains

    def EnrichPlayer(self, playerData, blocking=True):
        """Fills in what the provider can add to a player loaded on a
        scoreboard (their mains). Without blocking, only what it already
        has: the rest is fetched in the background, and
        signals.player_mains_updated says when it's there."""
        provider = self.provider
        if provider is None:
            return playerData
        playerData = provider.EnrichPlayerData(playerData, blocking=blocking) or playerData
        if not blocking and not playerData.get("mains"):
            mains = self.MainsFor(provider)
            if mains is not None:
                mains.Queue(playerData)
        return playerData

    # =====================================================
    # PHASES AND BRACKETS
    # =====================================================
    def GetTournamentPhases(self):
        worker = Worker(self.provider.GetTournamentPhases)
        worker.signals.result.connect(
            lambda tournamentPhases: [
                TournamentDataManager.instance.signals.tournament_phases_updated.emit(
                    tournamentPhases
                )
            ]
        )
        self.threadPool.start(worker)

    def GetTournamentPhaseGroup(self, id):
        worker = Worker(self.provider.GetTournamentPhaseGroup, **{"id": id})
        worker.signals.result.connect(
            lambda phaseGroupData: [
                # Which phase group this is, so its sets can be refreshed later
                phaseGroupData.update({"phaseGroupId": id}) if phaseGroupData else None,
                TournamentDataManager.instance.signals.tournament_phasegroup_updated.emit(
                    phaseGroupData
                ),
            ]
        )
        self.threadPool.start(worker)

    def GetTournamentPhaseGroupSets(self, id, onFinished=None):
        worker = Worker(self.provider.GetTournamentPhaseGroupSets, **{"id": id})
        worker.signals.result.connect(
            lambda setsData: [
                TournamentDataManager.instance.signals.tournament_phasegroup_sets_updated.emit(
                    {"phaseGroupId": id, "data": setsData or {}}
                )
            ]
        )
        if onFinished:
            worker.signals.finished.connect(onFinished)
        self.threadPool.start(worker)

    # =====================================================
    # SETS
    # =====================================================
    def LoadSets(self, showFinished):
        if self.setLoadingWorker:
            # If there was a previous set loading worker,
            # block its signals
            self.setLoadingWorker.cancel()
            self.setLoadingWorker.signals.blockSignals(True)

        worker = Worker(self.provider.GetMatches, **{"getFinished": showFinished})
        worker.signals.result.connect(
            lambda data: [
                # logger.info(data),
                self.signals.get_sets_finished.emit(data),
                self.signals.sets_data_updated.emit({"progress": 0, "totalPages": 0, "sets": data}),
            ]
        )
        worker.signals.progress.connect(
            lambda n, t: [
                logger.info(f"SetDataUpdated: {n}/{t}"),
                self.signals.sets_data_updated.emit({"progress": n, "totalPages": t, "sets": []}),
            ]
        )
        self.setLoadingWorker = worker
        self.threadPool.start(worker)

    def GetMatch(self, mainWindow, setId, overwrite=True, no_mains=False, on_finished=None):
        if self.provider is None:
            if on_finished:
                on_finished()
            return
        worker = Worker(self.provider.GetMatch, **{"setId": setId})
        worker.signals.result.connect(
            lambda data: [
                data.update({"overwrite": overwrite, "no_mains": no_mains}),
                mainWindow.signals.UpdateSetData.emit(data),
            ]
        )
        if on_finished:
            worker.signals.finished.connect(on_finished)
        self.threadPool.start(worker)

    # =====================================================
    # STREAMS AND STATIONS
    # =====================================================
    def LoadStations(self):
        worker = Worker(self.provider.GetStations)
        worker.signals.result.connect(
            lambda data: [logger.info(data), self.signals.get_stations_finished.emit(data)]
        )
        self.threadPool.start(worker)

    def LoadStationSets(self, mainWindow, on_finished=None):
        if mainWindow.lastStationSelected:
            worker = Worker(
                TournamentDataManager.instance.LoadStationSetsDo, **{"mainWindow": mainWindow}
            )
            if on_finished:
                worker.signals.finished.connect(on_finished)
            self.threadPool.start(worker)
        elif on_finished:
            on_finished()

    def LoadStationSetsDo(self, mainWindow, progress_callback=None, cancel_event=None):
        stationSet = None

        if mainWindow.lastStationSelected.get("type") == "stream":
            # Pass the full station dict so providers that need extra context
            # (e.g. parry's per-capacity slot index) can read it. Providers that
            # only care about the identifier string accept either form.
            stationSet = TournamentDataManager.instance.provider.GetStreamMatchId(
                mainWindow.lastStationSelected
            )

        # Populate the upcoming-matches queue for both stream and station
        # selections. Providers that don't have a queue for the given id
        # return [] (e.g. start.gg returns [] when called with a stream id).
        stationSets = TournamentDataManager.instance.provider.GetStationMatchsId(
            mainWindow.lastStationSelected.get("id")
        )

        if stationSets is not None and len(stationSets) > 0:
            # Station mode: use queue head as the active set when no
            # stream-mode set was loaded above.
            if stationSet is None:
                stationSet = stationSets[0]

            queueCache = mainWindow.stationQueueCache
            logger.info(queueCache.queue)
            logger.info(stationSets)
            if queueCache and not queueCache.CheckQueue(stationSets):
                queueCache.UpdateQueue(stationSets)

                TournamentDataManager.instance.GetStationMatches(stationSets, mainWindow)

        if not stationSet:
            stationSet = {}

        stationSet["auto_update"] = mainWindow.lastStationSelected.get("type")

        mainWindow.signals.NewSetSelected.emit(stationSet)

    # omits the first one (loaded through NewSetSelected)
    def GetStationMatches(self, matchesId, mainWindow):
        matchesId = matchesId[1:]

        worker = Worker(self.provider.GetFutureMatchesList, **{"setsId": matchesId})
        worker.signals.result.connect(lambda sets: mainWindow.signals.StationSetsLoaded.emit(sets))
        self.threadPool.start(worker)

    # =====================================================
    # SET HISTORY
    # =====================================================
    def GetRecentSets(self, callback, id1, id2, videogame):
        worker = Worker(
            self.provider.GetRecentSets,
            **{
                "id1": id1,
                "id2": id2,
                "callback": callback,
                "requestTime": time.time_ns(),
                "videogame": videogame,
            },
        )
        self.threadPool.start(worker)

    def GetLastSets(self, callback, playerId, playerNumber):
        worker = Worker(
            self.provider.GetLastSets,
            **{"playerID": playerId[0], "playerNumber": playerNumber, "callback": callback},
        )
        self.threadPool.start(worker)

    def GetPlayerHistoryStandings(self, callback, playerId, playerNumber, gameType):
        worker = Worker(
            self.provider.GetPlayerHistoryStandings,
            **{
                "playerID": playerId[0],
                "playerNumber": playerNumber,
                "gameType": gameType,
                "callback": callback,
            },
        )
        self.threadPool.start(worker)

    def GetCompletedSets(self, on_finished=None):
        worker = Worker(self.provider.GetCompletedSets)
        worker.signals.result.connect(
            lambda completedSets: [
                TournamentDataManager.instance.signals.completed_sets_updated.emit(completedSets)
            ]
        )
        if on_finished:
            worker.signals.finished.connect(on_finished)
        self.threadPool.start(worker)

    # =====================================================
    # STANDINGS
    # =====================================================
    def GetStandings(self, playerNumber, callback, on_progress=None, on_finished=None):
        worker = Worker(self.provider.GetStandings, **{"playerNumber": playerNumber})
        worker.signals.result.connect(lambda data: [callback.emit(data)])
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        self.threadPool.start(worker)


TournamentDataManager.instance = TournamentDataManager()
