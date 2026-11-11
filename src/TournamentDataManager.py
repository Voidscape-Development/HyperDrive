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
from .TournamentDataProvider.ProviderErrors import (
    KIND_AUTH,
    KIND_NOT_FOUND,
    KIND_RATE_LIMITED,
    KIND_TRANSIENT,
    ProviderError,
    RaiseProviderErrors,
)
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
    # Background loading started and finished (StartWithActivity), for the
    # command bar's activity strip
    activity_started = Signal(str)
    activity_finished = Signal(str)
    # A request to the provider failed: what was asked for ("connect",
    # "tournament", "sets"...), the kind of error (ProviderErrors.KINDS) and
    # its message. What was shown before is kept.
    provider_error = Signal(str, str, str)
    # The event couldn't be loaded at all: its link, the kind of error, and
    # a message for the user
    tournament_error = Signal(str, str, str)


class _Captured:
    """Takes what a provider method emits to its callback, for it to be
    passed on from the GUI thread once it's known to still be wanted"""

    def __init__(self):
        self.values = []

    def emit(self, value):
        self.values.append(value)


class TournamentDataManager(QObject):
    instance: "TournamentDataManager" = None

    # Calls a function on the GUI thread (Run asked for from another thread)
    _callOnGuiThread = Signal(object)

    def __init__(self) -> None:
        super().__init__(None)
        self.provider: TournamentDataProvider = None
        # Run's bookkeeping: the last request of each key, and its worker
        self._sequence = {}
        self._keyWorkers = {}
        # What was loaded of the provider's event so far ("tournament",
        # "phases"), to tell a refresh that failed (what's shown is kept)
        # from a first load that did (there's nothing to keep)
        self._loaded = set()
        # The event couldn't be loaded: loading its link again tries again
        self.loadFailed = False
        self._errorBox = None
        self._callOnGuiThread.connect(self._CallOnGuiThread)
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

    def StartWithActivity(self, worker, activity):
        """Runs the worker, shown on the command bar's activity strip until
        it's done"""
        self.signals.activity_started.emit(activity)
        worker.signals.finished.connect(lambda: self.signals.activity_finished.emit(activity))
        self.threadPool.start(worker)

    # =====================================================
    # REQUESTS
    # =====================================================
    def Run(
        self,
        fn,
        on_result=None,
        on_error=None,
        key=None,
        on_finished=None,
        on_progress=None,
        activity=None,
    ):
        """The one way to ask the provider something off the GUI thread.

        fn(progress_callback=, cancel_event=) runs in the thread pool,
        inside RaiseProviderErrors: provider methods raise a ProviderError
        there instead of returning something empty. on_result(what fn
        returned), on_error(the exception) and on_progress(n, total) are
        called on the GUI thread, and only while the answer is still wanted:
        - the provider is still the one it was asked of (another event
          wasn't loaded meanwhile)
        - with a key ("sets", "match:1"...), no later request was made with
          the same key: the latest wins, whichever answers first. The
          earlier one is told to stop (its cancel_event).
        on_finished() is always called, once, after them. activity shows on
        the command bar's activity strip meanwhile.

        Can be called from any thread: the request then starts from the GUI
        thread. Returns the worker, None when called from another thread."""
        if not self.thread().isCurrentThread():
            self._callOnGuiThread.emit(
                lambda: self.Run(fn, on_result, on_error, key, on_finished, on_progress, activity)
            )
            return None

        provider = self.provider
        sequence = None
        if key is not None:
            sequence = self._sequence[key] = self._sequence.get(key, 0) + 1
            previous = self._keyWorkers.get(key)
            if previous is not None:
                previous.cancel()

        def wanted():
            if self.provider is not provider:
                return False
            return key is None or self._sequence.get(key) == sequence

        def call(progress_callback=None, cancel_event=None):
            with RaiseProviderErrors():
                return fn(progress_callback=progress_callback, cancel_event=cancel_event)

        def result(value):
            if not wanted():
                logger.debug(f"Dropped the answer to an outdated request ({key or fn})")
            elif on_result:
                on_result(value)

        def error(info):
            # (type, exception, traceback), already logged by the worker
            if wanted() and on_error:
                on_error(info[1])

        def progress(n, total):
            if wanted():
                on_progress(n, total)

        def finished():
            if key is not None and self._keyWorkers.get(key) is worker:
                del self._keyWorkers[key]
            if activity:
                self.signals.activity_finished.emit(activity)
            if on_finished:
                on_finished()

        worker = Worker(call)
        worker.signals.result.connect(result)
        worker.signals.error.connect(error)
        if on_progress:
            worker.signals.progress.connect(progress)
        worker.signals.finished.connect(finished)
        if key is not None:
            self._keyWorkers[key] = worker
        if activity:
            self.signals.activity_started.emit(activity)
        self.threadPool.start(worker)
        return worker

    def _CallOnGuiThread(self, fn):
        fn()

    def ReportError(self, what, error):
        """A request failed: says so (signals.provider_error). What was
        shown before it stays."""
        kind = error.kind if isinstance(error, ProviderError) else KIND_TRANSIENT
        logger.error(f"{what}: {kind} error: {error}")
        self.signals.provider_error.emit(what, kind, str(error))

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
        # Loading the same link again does nothing, unless it failed to
        # load: then it's tried again
        if self.provider and self.provider.url == url and not self.loadFailed:
            return

        # Made here, on the GUI thread: making a provider asks nothing of
        # the network. Connect does, off this thread.
        provider = self.CreateProvider(url)
        TournamentDataManager.instance.provider = provider
        self._loaded = set()
        self.loadFailed = False
        self._sequence = {}

        SettingsManager.Set("TOURNAMENT_URL", url)

        if provider is None:
            self.NoTournament()
            return

        def connected(realUrl):
            # A short or admin link became its event's link
            SettingsManager.Set("TOURNAMENT_URL", provider.url)

            self.GetTournamentData(initialLoading=initialLoading)
            self.GetTournamentPhases()

            self.LoadEntrants()
            TournamentDataManager.instance.signals.tournament_changed.emit()

        def failed(error):
            # Like a link without a provider, and loading it again tries
            # again (there's no provider with its url to stop it)
            TournamentDataManager.instance.provider = None
            self.NoTournament()
            self.TournamentFailed(provider, url, error, initialLoading)

        self.Run(provider.Connect, connected, failed, activity="connect")

    def NoTournament(self):
        """No event is loaded: nothing of the last one is left showing"""
        TournamentDataManager.instance.signals.tournament_data_updated.emit({})
        TournamentDataManager.instance.signals.tournament_phases_updated.emit([])
        TournamentDataManager.instance.signals.tournament_changed.emit()
        GameAssetManager.instance.LoadGameAssets(0)

    def ErrorMessage(self, providerClass, error):
        """What to tell the user about an event that couldn't be loaded"""
        kind = error.kind if isinstance(error, ProviderError) else KIND_TRANSIENT
        site = getattr(providerClass, "HOST", None) or getattr(providerClass, "NAME", "")
        if kind == KIND_AUTH:
            if getattr(providerClass, "API_KEY_SETTING", None):
                text = QApplication.translate(
                    "app", "The {0} API key was refused. Check it in Settings > API Keys."
                )
            else:
                text = QApplication.translate("app", "{0} refused the request.")
        elif kind == KIND_NOT_FOUND:
            text = QApplication.translate("app", "This event wasn't found on {0}. Check its link.")
        elif kind == KIND_RATE_LIMITED:
            text = QApplication.translate(
                "app", "{0} is getting too many requests. Try again in a moment."
            )
        else:
            text = QApplication.translate(
                "app", "{0} couldn't be reached. Check your connection and try again."
            )
        return text.format(site)

    def TournamentFailed(self, provider, url, error, initialLoading=False):
        """The event couldn't be loaded: says why (signals.tournament_error,
        and a message unless the app is starting), and lets it be tried
        again"""
        self.loadFailed = True
        kind = error.kind if isinstance(error, ProviderError) else KIND_TRANSIENT
        message = self.ErrorMessage(type(provider), error)
        logger.error(f"Couldn't load {url}: {kind} error: {error}")
        self.signals.provider_error.emit("connect", kind, str(error))
        self.signals.tournament_error.emit(url, kind, message)
        if not initialLoading:
            retry = kind in (KIND_TRANSIENT, KIND_RATE_LIMITED)
            self.ShowTournamentError(url, message, retry)

    def ShowTournamentError(self, url, message, retry):
        """A message that doesn't hold up the app, with a button to try
        again when that might work"""
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(QApplication.translate("app", "Error"))
        box.setText(QApplication.translate("app", "The tournament couldn't be loaded."))
        box.setInformativeText(message + "\n" + url)
        buttons = QMessageBox.StandardButton.Close
        if retry:
            buttons |= QMessageBox.StandardButton.Retry
        box.setStandardButtons(buttons)
        box.setModal(False)

        def clicked(button):
            if box.standardButton(button) == QMessageBox.StandardButton.Retry:
                self.SetTournament(url)

        box.buttonClicked.connect(clicked)
        # Kept, or it'd be collected (and closed) right away
        self._errorBox = box
        box.show()

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
        if provider is None:
            return

        def fetch(progress_callback=None, cancel_event=None):
            provider.videogameFound = None
            data = provider.GetTournamentData()
            return data, provider.videogameFound

        def loaded(result):
            tournamentData, videogame = result
            self._loaded.add("tournament")
            # The event's game first, as the layouts' game comes with it
            if videogame:
                self.signals.game_changed.emit(videogame)
            tournamentData = dict(tournamentData or {})
            tournamentData.update({"initial_load": initialLoading})
            TournamentDataManager.instance.signals.tournament_data_updated.emit(tournamentData)

        def failed(error):
            if "tournament" in self._loaded:
                # A refresh: the tournament's data shown is kept
                self.ReportError("tournament", error)
                return
            # Nothing of this event was shown yet
            TournamentDataManager.instance.signals.tournament_data_updated.emit(
                {"initial_load": initialLoading}
            )
            self.TournamentFailed(provider, provider.url, error, initialLoading)

        self.Run(fetch, loaded, failed, key="tournament", activity="tournament")

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
            # In the worker: saving many players takes a while, and the
            # player database can be used from any thread
            if players:
                PlayerDB.AddPlayers(players)
            # The entrants query doesn't carry each player's last set (that
            # blew start.gg's complexity cap), so mains are filled in the
            # background instead of the scoreboard fetching them one by one.
            # Not for an event that isn't the one loaded anymore.
            if players and self.provider is provider:
                mains = self.MainsFor(provider)
                if mains is not None:
                    mains.Prewarm(players)
            return players

        def loaded(players):
            self.signals.entrants_updated.emit()

        self.Run(
            load,
            loaded,
            lambda error: self.ReportError("entrants", error),
            key="entrants",
            activity="entrants",
        )

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
        provider = self.provider
        if provider is None:
            return

        def loaded(tournamentPhases):
            self._loaded.add("phases")
            TournamentDataManager.instance.signals.tournament_phases_updated.emit(
                tournamentPhases or []
            )

        def failed(error):
            self.ReportError("phases", error)
            # The phases shown are kept, unless they're another event's
            if "phases" not in self._loaded:
                TournamentDataManager.instance.signals.tournament_phases_updated.emit([])

        self.Run(provider.GetTournamentPhases, loaded, failed, key="phases", activity="phases")

    def GetTournamentPhaseGroup(self, id):
        provider = self.provider
        if provider is None:
            return

        def fetch(progress_callback=None, cancel_event=None):
            return provider.GetTournamentPhaseGroup(
                id, progress_callback=progress_callback, cancel_event=cancel_event
            )

        def loaded(phaseGroupData):
            # Which phase group this is, so its sets can be refreshed later
            if phaseGroupData:
                phaseGroupData.update({"phaseGroupId": id})
            TournamentDataManager.instance.signals.tournament_phasegroup_updated.emit(
                phaseGroupData
            )

        # When it fails, the bracket shown is left as it is
        self.Run(
            fetch,
            loaded,
            lambda error: self.ReportError("phase_group", error),
            key=f"phase_group:{id}",
        )

    def GetTournamentPhaseGroupSets(self, id, onFinished=None):
        provider = self.provider
        if provider is None:
            if onFinished:
                onFinished()
            return

        def fetch(progress_callback=None, cancel_event=None):
            return provider.GetTournamentPhaseGroupSets(
                id, progress_callback=progress_callback, cancel_event=cancel_event
            )

        def loaded(setsData):
            TournamentDataManager.instance.signals.tournament_phasegroup_sets_updated.emit(
                {"phaseGroupId": id, "data": setsData or {}}
            )

        self.Run(
            fetch,
            loaded,
            lambda error: self.ReportError("phase_group_sets", error),
            key=f"phase_group_sets:{id}",
            on_finished=onFinished,
        )

    # =====================================================
    # SETS
    # =====================================================
    def LoadSets(self, showFinished):
        provider = self.provider
        if provider is None:
            self.signals.sets_data_updated.emit({"progress": 0, "totalPages": 0, "sets": []})
            return

        def fetch(progress_callback=None, cancel_event=None):
            return provider.GetMatches(
                getFinished=showFinished,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )

        def loaded(data):
            self.signals.get_sets_finished.emit(data)
            self.signals.sets_data_updated.emit({"progress": 0, "totalPages": 0, "sets": data})

        def progress(n, t):
            logger.info(f"SetDataUpdated: {n}/{t}")
            self.signals.sets_data_updated.emit({"progress": n, "totalPages": t, "sets": []})

        def failed(error):
            self.ReportError("sets", error)
            # The list stops loading, and says it has no sets because it
            # couldn't get them
            self.signals.sets_data_updated.emit(
                {"progress": 0, "totalPages": 0, "sets": [], "error": str(error)}
            )

        # A list asked for again replaces the one being loaded (Run tells
        # the earlier request to stop, and drops its answer)
        self.setLoadingWorker = self.Run(fetch, loaded, failed, key="sets", on_progress=progress)

    def GetMatch(self, mainWindow, setId, overwrite=True, no_mains=False, on_finished=None):
        provider = self.provider
        if provider is None:
            if on_finished:
                on_finished()
            return

        def fetch(progress_callback=None, cancel_event=None):
            return provider.GetMatch(
                setId, progress_callback=progress_callback, cancel_event=cancel_event
            )

        def loaded(data):
            # Nothing came (the set isn't there): the scoreboard is left as is
            if not data:
                return
            data.update({"overwrite": overwrite, "no_mains": no_mains})
            mainWindow.signals.UpdateSetData.emit(data)

        # One set at a time for each scoreboard: when two are asked for, the
        # last one asked for is loaded, not the slowest to answer
        number = getattr(mainWindow, "scoreboardNumber", id(mainWindow))
        self.Run(
            fetch,
            loaded,
            lambda error: self.ReportError("set", error),
            key=f"set:{number}",
            on_finished=on_finished,
        )

    # =====================================================
    # STREAMS AND STATIONS
    # =====================================================
    def LoadStations(self):
        provider = self.provider
        if provider is None:
            self.signals.get_stations_finished.emit([])
            return

        def loaded(data):
            logger.info(data)
            self.signals.get_stations_finished.emit(data)

        def failed(error):
            self.ReportError("stations", error)
            # Whoever asked stops waiting for them
            self.signals.get_stations_finished.emit([])

        self.Run(provider.GetStations, loaded, failed, key="stations")

    def LoadStationSets(self, mainWindow, on_finished=None):
        """Loads the set on the scoreboard's stream or station (NewSetSelected)
        and, when its queue changed, the sets after it (StationSetsLoaded)"""
        provider = self.provider
        if not mainWindow.lastStationSelected or provider is None:
            if on_finished:
                on_finished()
            return

        # What the worker needs of the scoreboard is read here, on the GUI
        # thread: the station, and the queue it already has
        station = dict(mainWindow.lastStationSelected)
        queueCache = mainWindow.stationQueueCache
        known = type(queueCache)()
        known.UpdateQueue(list(queueCache.queue))

        def fetch(progress_callback=None, cancel_event=None):
            return TournamentDataManager.FetchStationSets(provider, station, known)

        # When it fails (a ProviderError), the set on the scoreboard and its
        # queue are left as they are: nothing says the stream has no set
        number = getattr(mainWindow, "scoreboardNumber", id(mainWindow))
        self.Run(
            fetch,
            lambda result: self.StationSetsFetched(mainWindow, provider, station, result),
            lambda error: self.ReportError("station_sets", error),
            key=f"station_sets:{number}",
            on_finished=on_finished,
        )

    @staticmethod
    def FetchStationSets(provider, station, known):
        """Runs in a worker thread, and touches nothing of the GUI: the set
        on the station now, its sets' ids, and the sets after the first one
        when they aren't the ones known already (None when they are, or when
        they couldn't be fetched)"""
        stationSet = None

        if station.get("type") == "stream":
            # Pass the full station dict so providers that need extra context
            # (e.g. parry's per-capacity slot index) can read it. Providers that
            # only care about the identifier string accept either form.
            stationSet = provider.GetStreamMatchId(station)

        # Populate the upcoming-matches queue for both stream and station
        # selections. Providers that don't have a queue for the given id
        # return [] (e.g. start.gg returns [] when called with a stream id).
        stationSets = provider.GetStationMatchsId(station.get("id"))

        queue = None
        if stationSets:
            # Station mode: use queue head as the active set when no
            # stream-mode set was loaded above.
            if stationSet is None:
                stationSet = stationSets[0]

            if not known.CheckQueue(stationSets):
                # Fetched here, in the same worker: a worker made in this
                # thread would never deliver its result. Omits the first one
                # (loaded through NewSetSelected).
                try:
                    queue = provider.GetFutureMatchesList(stationSets[1:], None, None)
                except Exception as e:
                    # The set still loads; its queue is tried again next time
                    logger.error(f"{e.__class__.__name__}: {e}")

        return {"set": stationSet, "ids": stationSets, "queue": queue}

    def StationSetsFetched(self, mainWindow, provider, station, result):
        """On the GUI thread, with what FetchStationSets returned"""
        # Another event, or another stream or station, was picked meanwhile
        if provider is not self.provider or mainWindow.lastStationSelected != station:
            return

        if result.get("queue") is not None:
            # Only once its sets were fetched, so a failed fetch is tried
            # again at the next update
            mainWindow.stationQueueCache.UpdateQueue(result.get("ids"))

        stationSet = result.get("set") or {}
        stationSet["auto_update"] = station.get("type")
        mainWindow.signals.NewSetSelected.emit(stationSet)

        if result.get("queue") is not None:
            mainWindow.signals.StationSetsLoaded.emit(result.get("queue"))

    # =====================================================
    # SET HISTORY
    # =====================================================
    def RunEmitting(self, call, callback):
        """Runs a provider method that emits its result to a callback
        (call(callback, progress_callback, cancel_event) calls it). What it
        emits is passed on to callback from the GUI thread, unless another
        event was loaded meanwhile."""
        if self.provider is None:
            return

        def fetch(progress_callback=None, cancel_event=None):
            captured = _Captured()
            call(captured, progress_callback, cancel_event)
            return captured.values

        def loaded(values):
            for value in values:
                callback.emit(value)

        self.Run(fetch, loaded)

    def GetRecentSets(self, callback, id1, id2, videogame):
        provider = self.provider
        requestTime = time.time_ns()
        self.RunEmitting(
            lambda captured, progress_callback, cancel_event: provider.GetRecentSets(
                id1=id1,
                id2=id2,
                videogame=videogame,
                callback=captured,
                requestTime=requestTime,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            ),
            callback,
        )

    def GetLastSets(self, callback, playerId, playerNumber):
        provider = self.provider
        self.RunEmitting(
            lambda captured, progress_callback, cancel_event: provider.GetLastSets(
                playerID=playerId[0],
                playerNumber=playerNumber,
                callback=captured,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            ),
            callback,
        )

    def GetPlayerHistoryStandings(self, callback, playerId, playerNumber, gameType):
        provider = self.provider
        self.RunEmitting(
            lambda captured, progress_callback, cancel_event: provider.GetPlayerHistoryStandings(
                playerID=playerId[0],
                playerNumber=playerNumber,
                gameType=gameType,
                callback=captured,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            ),
            callback,
        )

    def GetCompletedSets(self, on_finished=None):
        provider = self.provider
        if provider is None:
            if on_finished:
                on_finished()
            return

        def loaded(completedSets):
            TournamentDataManager.instance.signals.completed_sets_updated.emit(completedSets)

        # When it fails, the completed sets shown are kept
        self.Run(
            provider.GetCompletedSets,
            loaded,
            lambda error: self.ReportError("completed_sets", error),
            key="completed_sets",
            on_finished=on_finished,
            activity="completed_sets",
        )

    # =====================================================
    # STANDINGS
    # =====================================================
    def GetStandings(self, playerNumber, callback, on_progress=None, on_finished=None):
        provider = self.provider
        if provider is None:
            if on_finished:
                on_finished()
            return

        def fetch(progress_callback=None, cancel_event=None):
            return provider.GetStandings(
                playerNumber, progress_callback=progress_callback, cancel_event=cancel_event
            )

        # When it fails, nothing is passed on: the standings that would come
        # out of the placements that did load would be wrong
        self.Run(
            fetch,
            lambda data: callback.emit(data),
            lambda error: self.ReportError("standings", error),
            on_finished=on_finished,
            on_progress=on_progress,
        )


TournamentDataManager.instance = TournamentDataManager()
