#!/usr/bin/env python3
import atexit
import contextlib
import faulthandler
import os
import shutil
import sys
import time
import traceback
import unicodedata
import zipfile
from pathlib import Path

import orjson
import qtpy
import requests
from loguru import logger
from packaging.version import InvalidVersion, parse
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers import QtHelper
from .Helpers.DirHelper import ResolvePath
from .Helpers.DynamicExport import DynamicExport
from .Helpers.LocaleHelper import LocaleHelper
from .Helpers.VersionHelper import PROJECT_URL, REPOSITORY, get_program_version, get_versions

crashpath = Path("./logs/hyperdrive-crash.log").resolve()
Path.mkdir(crashpath.parent, exist_ok=True)
crashlog = crashpath.open(mode="w")
faulthandler.enable(crashlog)

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

if parse(qtpy.QT_VERSION).major == 6:
    QImageReader.setAllocationLimit(0)

# The UI scale has to be set before the application is created
from .Theme import ApplyUIScale, Theme, ThemedIcon

ApplyUIScale()

App = QApplication(sys.argv)
QtHelper.init_gui_executor()  # guaranteed to be the main thread.

fmt = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
    + "| <level>{level}</level> | "
    + "<yellow>{file}</yellow>:<blue>{function}</blue>:<cyan>{line}</cyan> "
    + "- <level>{message}</level>"
)

if sys.stdout != None:
    config = {
        "handlers": [
            {"sink": sys.stdout, "format": fmt, "level": "DEBUG"},
        ],
    }
    logger.configure(**config)
else:
    # Handle all uncaught exceptions and forward to loguru
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # loguru ignores logging's exc_info, so pass the exception this way
        # or the traceback never reaches the log
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Uncaught exception")

    sys.excepthook = handle_exception

    class LoggerWriter:
        def __init__(self, writer):
            self._writer = writer
            self._msg = ""

        def write(self, message):
            self._msg = self._msg + message
            while "\n" in self._msg:
                pos = self._msg.find("\n")
                self._writer(self._msg[:pos])
                self._msg = self._msg[pos + 1 :]

        def flush(self):
            if self._msg != "":
                self._writer(self._msg)
                self._msg = ""

    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)

logger.add(
    "./logs/hyperdrive.log",
    format="[{time:YYYY-MM-DD HH:mm:ss}] - {level} - {file}:{function}:{line} | {message}",
    encoding="utf-8",
    level="INFO",
    rotation="20 MB",
)

logger.add(
    "./logs/hyperdrive-error.log",
    format="[{time:YYYY-MM-DD HH:mm:ss}] - {level} - {file}:{function}:{line} | {message}",
    encoding="utf-8",
    level="ERROR",
    rotation="20 MB",
)

try:
    # Setting the icon for individual windows doesn't work on mac (and perhaps linux? unknown)
    App.setWindowIcon(QIcon("assets/icons/icon.png"))
except:
    logger.opt(exception=True).warning("Could not set window icon for QApplication.")


logger.critical("=== HyperDrive IS STARTING ===")

logger.info("QApplication successfully initialized")

from contextlib import contextmanager


@contextmanager
def catchtime(msg=""):
    from time import perf_counter

    start = perf_counter()
    yield lambda: perf_counter() - start
    logger.info(f"{msg} Time: {perf_counter() - start:.3f} seconds")


# autopep8: off
from src.AboutWidget import AboutWidget
from src.AssetDownloader import AssetDownloader
from src.CommandBar import (
    STATUS_BUSY,
    STATUS_OFF,
    STATUS_OK,
    BarButton,
    CommandBar,
    ContextChip,
    StatusPill,
    Workspaces,
)
from src.WebServer import WebServer

from .AlertNotification import AlertNotification
from .BracketWidget import BracketWidget
from .CommentaryWidget import CommentaryWidget
from .DisplayControls import DisplayControls, DisplayControlsWidget
from .GameAssetManager import GameAssetManager
from .Helpers.CountryHelper import CountryHelper
from .LayoutOptions.LayoutThemes import LayoutThemes
from .LayoutOptions.LayoutThemeWindow import LayoutThemeWindow
from .PlayerDB import PlayerDB
from .PlayerDBWindow import PlayerDBWindow
from .PlayerListWidget import PlayerListWidget
from .Scheduler import (
    COMPLETED_SETS_DEFAULT_INTERVAL_SECS,
    COMPLETED_SETS_MIN_INTERVAL_SECS,
    Scheduler,
)
from .ScoreboardManager import ScoreboardManager
from .ScoreboardStageWidget import ScoreboardStageWidget
from .SeedManager import SeedManager
from .Settings.SettingsWindow import SettingsWindow
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .StreamQueueWidget import StreamQueueWidget
from .TeamBattleWidget import TeamBattleWidget
from .TournamentDataManager import TournamentDataManager
from .TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from .TournamentDataProvider.TournamentEventLookup import (
    FetchTournamentEvents,
    IsSameEvent,
    ParseTournamentLink,
)
from .TournamentInfoWidget import TournamentInfoWidget
from .TwitchPredictions import TwitchPredictionsHook
from .Wiki import GETTING_STARTED_PAGE, Wiki
from .WikiWindow import WikiWindow
from .Workers import *

# autopep8: on


def RemoveObsoleteFiles():
    """Deletes files that earlier versions downloaded and HyperDrive no longer uses"""
    for path in ["./assets/countries+states+cities.json", "./assets/countries_cache.json"]:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            logger.opt(exception=True).warning(f"Could not remove {path}")
    shutil.rmtree("./assets/controller", ignore_errors=True)


def generate_restart_messagebox(main_txt):
    messagebox = QMessageBox()
    messagebox.setWindowTitle(QApplication.translate("app", "Warning"))
    messagebox.setText(
        main_txt + "\n" + QApplication.translate("app", "The program will now close.")
    )
    messagebox.finished.connect(QApplication.exit)
    return messagebox


def UpdateProcedure():
    """
    Update Procedure -- backup layouts, register extraction on program close
    """

    try:
        # Backup layouts
        os.rename("./layout", f"./layout_backup_{str(time.time())}")

        # Register update extraction on program close
        atexit.register(ExtractUpdate)

        messagebox = generate_restart_messagebox(
            QApplication.translate(
                "app", "Update download complete. The program will extract the update upon closing."
            )
            + "\n\n"
            + QApplication.translate(
                "app",
                "Please ensure the layout folder or its contents aren't open in another application before closing this window.",
            )
            + "\n"
        )

        messagebox.exec()
    except Exception as e:
        # Layout folder backups failed
        logger.error(traceback.format_exc())

        buttonReply = QDialog()
        buttonReply.setWindowTitle(QApplication.translate("app", "Warning"))
        vbox = QVBoxLayout()
        buttonReply.setLayout(vbox)

        buttonReply.layout().addWidget(
            QLabel(QApplication.translate("updater", "Error while backing up the layout folder:"))
        )
        buttonReply.layout().addWidget(QLabel(str(e)))

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)

        btRetry = QPushButton(QApplication.translate("updater", "Retry"))
        hbox.addWidget(btRetry)
        btCancel = QPushButton(QApplication.translate("updater", "Cancel"))
        hbox.addWidget(btCancel)

        btRetry.clicked.connect(lambda: [buttonReply.close(), UpdateProcedure()])

        btCancel.clicked.connect(lambda: buttonReply.close())

        buttonReply.exec()


def ExtractUpdate():
    try:
        updateLog = []
        with zipfile.ZipFile("update.zip", "r") as z:
            # backup exe
            os.rename("./HyperDrive.exe", "./HyperDrive_old.exe")

            for filename in z.namelist():
                if "/" in filename:
                    fullname = filename.split("/", 1)[1]
                    if fullname.endswith("/"):
                        updateLog.append(f"Create directory {fullname}")
                        try:
                            os.makedirs(os.path.dirname(fullname), exist_ok=True)
                        except Exception:
                            updateLog.append(
                                f"Failed to create {filename} - {traceback.format_exc()}"
                            )
                    else:
                        updateLog.append(f"Extract {filename} -> {fullname}")
                        try:
                            z.extract(filename, path=os.path.dirname(fullname))
                        except Exception:
                            updateLog.append(
                                f"Failed to extract {filename} - {traceback.format_exc()}"
                            )

            try:
                with open("assets/update_log.txt", "w") as f:
                    f.writelines(updateLog)
            except:
                logger.error(traceback.format_exc())

        os.remove("update.zip")
    except Exception as e:
        logger.error(traceback.format_exc())


# The most scoreboards that can run at once
MAX_SCOREBOARDS = 10


def remove_accents_lower(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


class TabCorner(QWidget):
    """A tab widget's corner as tall as its tab bar, which is all the room
    the tab widget gives it: taller and it's cut off."""

    def __init__(self, tabBar):
        super().__init__()
        self.tabBar = tabBar

    def sizeHint(self):
        return QSize(super().sizeHint().width(), max(0, self.tabBar.sizeHint().height() - 2))

    def minimumSizeHint(self):
        return self.sizeHint()


class WindowSignals(QObject):
    StopTimer = Signal()
    ExportStageStrike = Signal(object)
    DetectGame = Signal(int)
    SetupAutocomplete = Signal()
    UiMounted = Signal()
    GameChanged = Signal()


class Window(QMainWindow):
    signals = WindowSignals()

    def __init__(self, loop=None):
        super().__init__()

        StateManager.loop = loop

        # Startup is expected to hold the block for a long time, so it opts out
        # of the stuck-block watchdog.
        with StateManager.SaveBlock(watchdog=False):
            self.SetupUi()

        StateManager.Unset("completed_sets")

    # =====================================================
    # SETUP
    # =====================================================
    def SetupUi(self):
        LocaleHelper.LoadLocale()
        LocaleHelper.LoadRoundNames()
        Theme.Apply()

        self.signals = WindowSignals()

        # splash.png is drawn at twice its 540x220 size, scaled down to the
        # screen's pixel ratio so it stays sharp on high DPI screens
        ratio = App.primaryScreen().devicePixelRatio()
        splashPixmap = QPixmap("assets/icons/splash.png").scaledToWidth(
            round(540 * ratio), Qt.TransformationMode.SmoothTransformation
        )
        splashPixmap.setDevicePixelRatio(ratio)
        splash = QSplashScreen(splashPixmap)
        splash.show()

        time.sleep(0.1)

        App.processEvents()

        self.programState = {}
        self.savedProgramState = {}
        self.programStateDiff = {}

        self.setWindowIcon(QIcon("assets/icons/icon.png"))

        os.makedirs("out", exist_ok=True)
        os.makedirs("./user_data/games", exist_ok=True)

        with contextlib.suppress(FileNotFoundError):
            os.remove("./HyperDrive_old.exe")

        self.font_small = QFont("./assets/font/RobotoCondensed.ttf", pointSize=8)

        self.threadpool = QThreadPool()
        self.saveMutex = QMutex()

        self.player_layouts = []

        self.allplayers = None
        self.local_players = None

        RemoveObsoleteFiles()
        CountryHelper.LoadCountries()

        self.setGeometry(300, 300, 800, 100)
        self.setWindowTitle("HyperDrive v" + get_program_version())

        self.setDockOptions(QMainWindow.DockOption.AllowTabbedDocks)

        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)

        # Layout base com status no topo
        central_widget = QWidget()
        pre_base_layout = QVBoxLayout()
        central_widget.setLayout(pre_base_layout)
        self.setCentralWidget(central_widget)
        central_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.dockWidgets = []

        bracket = BracketWidget()
        bracket.setWindowIcon(ThemedIcon("assets/icons/info.svg"))
        bracket.setObjectName(QApplication.translate("app", "Bracket"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bracket)
        self.dockWidgets.append(bracket)

        tournamentInfo = TournamentInfoWidget()
        tournamentInfo.setWindowIcon(ThemedIcon("assets/icons/info.svg"))
        tournamentInfo.setObjectName(QApplication.translate("app", "Tournament Info"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, tournamentInfo)
        self.dockWidgets.append(tournamentInfo)

        teamBattle = TeamBattleWidget()
        teamBattle.setWindowIcon(ThemedIcon("assets/icons/info.svg"))
        teamBattle.setObjectName(QApplication.translate("app", "Crew/Team Battle"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, teamBattle)
        self.dockWidgets.append(teamBattle)

        self.scoreboard = ScoreboardManager.instance
        self.scoreboard.setWindowIcon(ThemedIcon("assets/icons/list.svg"))
        self.scoreboard.setObjectName(QApplication.translate("app", "Scoreboard Manager"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.scoreboard)
        self.dockWidgets.append(self.scoreboard)
        ScoreboardManager.instance.setWindowTitle(
            QApplication.translate("app", "Scoreboard Manager")
        )

        self.stageWidget = ScoreboardStageWidget()
        self.stageWidget.setObjectName(QApplication.translate("app", "Stage"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.stageWidget)
        self.dockWidgets.append(self.stageWidget)

        streamQueue = StreamQueueWidget()
        streamQueue.setWindowIcon(ThemedIcon("assets/icons/list.svg"))
        streamQueue.setObjectName(QApplication.translate("app", "Stream Queue"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, streamQueue)
        self.dockWidgets.append(streamQueue)

        # Twitch predictions for the set on stream (off until enabled in the settings)
        TwitchPredictionsHook()

        commentary = CommentaryWidget()
        commentary.setWindowIcon(ThemedIcon("assets/icons/mic.svg"))
        commentary.setObjectName(QApplication.translate("app", "Commentary"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, commentary)
        self.dockWidgets.append(commentary)

        DisplayControls()
        displayControls = DisplayControlsWidget()
        displayControls.setWindowIcon(ThemedIcon("assets/icons/eye.svg"))
        displayControls.setObjectName(QApplication.translate("app", "Display Controls"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, displayControls)
        self.dockWidgets.append(displayControls)

        self.webserver = WebServer(
            parent=self, stageWidget=self.stageWidget, commentaryWidget=commentary
        )
        self.webserver.start()
        DisplayControls.signals.changed.connect(WebServer.ws_broadcast_display_state)
        self.signals.GameChanged.connect(self.webserver.ws_program_state)
        self.signals.GameChanged.connect(self.webserver.ws_get_characters)
        # Sends each scoreboard's stage strike to the stage strike app
        self.stageWidget.signals.strike_state_updated.connect(
            lambda number: WebServer.ws_ruleset({"scoreboardNumber": number})
        )

        playerList = PlayerListWidget()
        playerList.setWindowIcon(ThemedIcon("assets/icons/list.svg"))
        playerList.setObjectName(QApplication.translate("app", "Player List"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, playerList)
        self.dockWidgets.append(playerList)

        self.tabifyDockWidget(self.scoreboard, self.stageWidget)
        self.tabifyDockWidget(self.scoreboard, commentary)
        self.tabifyDockWidget(self.scoreboard, tournamentInfo)
        self.tabifyDockWidget(self.scoreboard, teamBattle)
        self.tabifyDockWidget(self.scoreboard, playerList)
        self.tabifyDockWidget(self.scoreboard, bracket)
        self.tabifyDockWidget(self.scoreboard, streamQueue)
        self.tabifyDockWidget(self.scoreboard, displayControls)
        self.scoreboard.raise_()

        # The command bar: what's loaded (tournament, game), the completed
        # sets' status and the window's own controls
        pre_base_layout.setContentsMargins(0, 0, 0, 0)
        self.commandBar = CommandBar()
        pre_base_layout.addWidget(self.commandBar)
        TournamentDataManager.instance.signals.activity_started.connect(
            self.commandBar.activity.Start
        )
        TournamentDataManager.instance.signals.activity_finished.connect(
            self.commandBar.activity.Finish
        )

        logo = QLabel()
        logo.setPixmap(QIcon("assets/icons/icon.svg").pixmap(28, 28))
        logo.setToolTip("HyperDrive")
        self.commandBar.AddWidget(logo)

        # Without a tournament the chip is a button that loads one; with one
        # it opens the tournament's actions
        self.tournamentChip = self.commandBar.AddWidget(ContextChip())
        self.tournamentChip.clicked.connect(
            lambda: (
                TournamentDataManager.instance.SetStartggEventSlug(self)
                if TournamentDataManager.instance.provider is None
                else None
            )
        )
        self.tournamentMenu = QMenu(self.tournamentChip)
        self.tournamentMenu.setToolTipsVisible(True)

        # For entrants who registered after the event was loaded
        self.repullEntrantsAction = self.tournamentMenu.addAction(
            ThemedIcon("./assets/icons/people.svg"),
            QApplication.translate("app", "Repull entrants"),
        )
        self.repullEntrantsAction.setToolTip(
            QApplication.translate(
                "app",
                "Pull the event's entrants again, to get players who registered after it was loaded",
            )
        )
        self.repullEntrantsAction.triggered.connect(
            lambda: TournamentDataManager.instance.RepullEntrants()
        )

        action = self.tournamentMenu.addAction(
            QApplication.translate("app", "Load a different tournament...")
        )
        action.triggered.connect(lambda: TournamentDataManager.instance.SetStartggEventSlug(self))
        action = self.tournamentMenu.addAction(
            ThemedIcon("./assets/icons/cancel.svg"),
            QApplication.translate("app", "Unload tournament"),
        )
        action.triggered.connect(lambda: TournamentDataManager.instance.SetTournament(None))

        # Below, the tournament's events, to switch to another one. Fetched
        # once per tournament (FillEventsMenu).
        self.tournamentMenu.addSeparator()
        self.eventsHeader = self.tournamentMenu.addAction(
            QApplication.translate("app", "Events in this tournament")
        )
        self.eventsHeader.setEnabled(False)
        self.eventActions = QActionGroup(self.tournamentMenu)
        self.eventActions.setExclusive(True)
        # (slug, events) of the tournament they were fetched for
        self.tournamentEvents = None
        TournamentDataManager.instance.signals.tournament_changed.connect(self.LoadTournamentEvents)

        TournamentDataManager.instance.signals.tournament_data_updated.connect(
            self.UpdateTournamentChip
        )

        # The game select and its options, added below once they're set up
        self.gameSlot = self.commandBar.AddLayout(QHBoxLayout())
        self.gameSlot.setSpacing(2)

        self.commandBar.AddStretch()

        # Completed Sets Feature
        self.completedSetsPill = self.commandBar.AddWidget(
            StatusPill(QApplication.translate("app", "Completed sets"))
        )
        self.completedSetsPill.setToolTip(
            QApplication.translate(
                "app", "The latest completed sets, for the completed_sets layouts"
            )
        )
        completedSetsMenu = QMenu(self.completedSetsPill)
        completedSetsMenu.setToolTipsVisible(True)
        self.completedSetsPill.setMenu(completedSetsMenu)

        self.autoPullCompletedSetsAction = completedSetsMenu.addAction(
            QApplication.translate("app", "Auto pull")
        )
        self.autoPullCompletedSetsAction.setCheckable(True)
        self.autoPullCompletedSetsAction.setToolTip(
            QApplication.translate(
                "app",
                "Pull the latest completed sets periodically. The interval can be changed in Settings > General.",
            )
        )

        # Manual pulls go through the scheduler too, so they can't overlap
        # an automatic one and they push the next automatic one back
        self.pullCompletedSetsAction = completedSetsMenu.addAction(
            QApplication.translate("app", "Pull Latest Completed Sets from StartGG")
        )
        self.pullCompletedSetsAction.triggered.connect(
            lambda: Scheduler.instance.TriggerNow("completed_sets")
        )
        self.btPullCompletedSets = self.commandBar.AddWidget(
            BarButton(
                ThemedIcon("./assets/icons/refresh.svg"),
                QApplication.translate("app", "Pull Latest Completed Sets from StartGG"),
            )
        )
        self.btPullCompletedSets.clicked.connect(
            lambda: Scheduler.instance.TriggerNow("completed_sets")
        )

        Scheduler.instance.Register(
            "completed_sets",
            self.PullCompletedSets,
            SettingsManager.Get(
                "general.completed_sets_pull_interval", COMPLETED_SETS_DEFAULT_INTERVAL_SECS
            )
            * 1000,
            COMPLETED_SETS_MIN_INTERVAL_SECS * 1000,
        )
        Scheduler.instance.signals.job_state_changed.connect(
            lambda name: self.UpdateCompletedSetsTimer() if name == "completed_sets" else None
        )
        Scheduler.instance.signals.tick.connect(self.UpdateCompletedSetsTimer)

        # No tournament is loaded yet, so the first pull happens when it is
        autoPull = SettingsManager.Get("general.completed_sets_auto_pull", False)
        self.autoPullCompletedSetsAction.setChecked(autoPull)
        if autoPull:
            Scheduler.instance.Start("completed_sets")
        self.autoPullCompletedSetsAction.toggled.connect(self.ToggleCompletedSetsAutoPull)

        # Keeps the players' avatars, sponsor logos and custom data up to
        # date as their files change
        DynamicExport.Start()

        TournamentDataManager.instance.signals.tournament_changed.connect(self.UpdateLastSetsButton)
        TournamentDataManager.instance.signals.tournament_changed.connect(
            self.UpdateTournamentButtons
        )
        TournamentDataManager.instance.signals.tournament_changed.connect(
            self.CompletedSetsTournamentChanged
        )
        # Seeds set by hand are for one event
        TournamentDataManager.instance.signals.tournament_changed.connect(
            lambda: SeedManager.EventLoaded(
                SettingsManager.Get("TOURNAMENT_URL")
                if TournamentDataManager.instance.provider
                else None
            )
        )
        TournamentDataManager.instance.signals.completed_sets_updated.connect(
            self.LoadCompletedSetsClicked
        )

        self.UpdateLastSetsButton()
        self.UpdateTournamentButtons()
        self.LoadTournamentEvents()
        self.UpdateCompletedSetsTimer()

        self.commandBar.AddSeparator()

        # Named arrangements of the widgets
        self.qtSettings = QSettings("Voidscape Development", "HyperDrive")
        self.workspaces = Workspaces(self, self.qtSettings)
        self.workspaceBt = self.commandBar.AddWidget(
            BarButton(
                ThemedIcon("assets/icons/workspace.svg"),
                QApplication.translate("app", "Workspace"),
            )
        )
        workspaceMenu = QMenu(self.workspaceBt)
        workspaceMenu.aboutToShow.connect(lambda: self.workspaces.FillMenu(workspaceMenu))
        self.workspaceBt.setMenu(workspaceMenu)
        self.workspaces.changed.connect(self.UpdateWorkspaceButton)
        self.UpdateWorkspaceButton()

        # Shows or hides each widget
        self.widgetsBt = self.commandBar.AddWidget(
            BarButton(
                ThemedIcon("assets/icons/widgets.svg"), QApplication.translate("app", "Widgets")
            )
        )
        widgetsMenu = QMenu(self.widgetsBt)
        self.widgetsBt.setMenu(widgetsMenu)
        for dock in [
            self.scoreboard,
            self.stageWidget,
            commentary,
            tournamentInfo,
            teamBattle,
            playerList,
            bracket,
            streamQueue,
            displayControls,
        ]:
            widgetsMenu.addAction(dock.toggleViewAction())
            dock.toggleViewAction().toggled.connect(self.UpdateWidgetsButton)
        self.UpdateWidgetsButton()

        self.playerDBBt = self.commandBar.AddWidget(
            BarButton(
                ThemedIcon("assets/icons/db.svg"),
                QApplication.translate("app", "Player database"),
            )
        )
        self.playerDBBt.clicked.connect(lambda: self.playerDBWindow.Open(0))

        # Settings
        menu_margin = " " * 6
        self.optionsBt = self.commandBar.AddWidget(
            BarButton(ThemedIcon("assets/icons/menu.svg"), QApplication.translate("app", "Menu"))
        )
        menu = QMenu()
        self.optionsBt.setMenu(menu)

        # The in-app guide, docs/wiki, first so it's easy to find. English
        # pages stand in for the ones not translated to the program's language.
        Wiki.Load(LocaleHelper.programLocale)
        self.wikiWindow = WikiWindow(self)
        action = menu.addAction(QApplication.translate("app", "Guide"))
        action.setIcon(ThemedIcon("assets/icons/book.svg"))
        action.triggered.connect(lambda: self.wikiWindow.Open())

        menu.addSeparator()

        action = menu.addAction(QApplication.translate("app", "Always on top"))
        action.setCheckable(True)
        action.toggled.connect(self.ToggleAlwaysOnTop)
        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Check for updates"))
        self.updateAction = action
        action.setIcon(ThemedIcon("assets/icons/undo.svg"))
        action.triggered.connect(self.CheckForUpdates)
        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Download assets"))
        action.setIcon(ThemedIcon("assets/icons/download.svg"))
        action.triggered.connect(lambda: AssetDownloader.instance.DownloadAssets(self))
        self.downloadAssetsAction = action

        self.playerDBWindow = PlayerDBWindow(self)
        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Player database"))
        action.setIcon(ThemedIcon("assets/icons/db.svg"))
        action.triggered.connect(lambda: self.playerDBWindow.Open(0))
        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Seed editor"))
        action.setIcon(ThemedIcon("assets/icons/list.svg"))
        action.triggered.connect(lambda: self.playerDBWindow.Open(1))

        self.optionsBt.menu().addSeparator()

        # The theme in use goes to the state as layout_theme for the layouts
        LayoutThemes.Load()
        LayoutThemes.ExportToState()
        self.layoutThemes = None

        action = self.optionsBt.menu().addAction(
            QApplication.translate("layout_themes", "Layout themes")
        )
        action.setIcon(ThemedIcon("assets/icons/settings.svg"))
        action.triggered.connect(self.OpenLayoutThemes)

        self.optionsBt.menu().addSeparator()

        languageSelect = QMenu(
            QApplication.translate("app", "Program Language") + menu_margin, self.optionsBt.menu()
        )
        self.optionsBt.menu().addMenu(languageSelect)

        languageSelectGroup = QActionGroup(languageSelect)
        languageSelectGroup.setExclusive(True)

        program_language_messagebox = generate_restart_messagebox(
            QApplication.translate("app", "Program language changed successfully.")
        )

        action = languageSelect.addAction(QApplication.translate("app", "System language"))
        languageSelectGroup.addAction(action)
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(
            lambda x=None: [
                SettingsManager.Set("program_language", "default"),
                program_language_messagebox.exec(),
            ]
        )

        for code, language in LocaleHelper.languages.items():
            action = languageSelect.addAction(f"{language[0]} / {language[1]}")
            action.setCheckable(True)
            languageSelectGroup.addAction(action)
            action.triggered.connect(
                lambda x=None, c=code: [
                    SettingsManager.Set("program_language", c),
                    program_language_messagebox.exec(),
                ]
            )
            if SettingsManager.Get("program_language") == code:
                action.setChecked(True)

        languageSelect = QMenu(
            QApplication.translate("app", "Game Asset Language") + menu_margin,
            self.optionsBt.menu(),
        )
        self.optionsBt.menu().addMenu(languageSelect)

        languageSelectGroup = QActionGroup(languageSelect)
        languageSelectGroup.setExclusive(True)

        game_asset_language_messagebox = generate_restart_messagebox(
            QApplication.translate("app", "Game Asset Language changed successfully.")
        )

        action = languageSelect.addAction(QApplication.translate("app", "Same as program language"))
        languageSelectGroup.addAction(action)
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(
            lambda x=None: [
                SettingsManager.Set("game_asset_language", "default"),
                game_asset_language_messagebox.exec(),
            ]
        )

        for code, language in LocaleHelper.languages.items():
            action = languageSelect.addAction(f"{language[0]} / {language[1]}")
            action.setCheckable(True)
            languageSelectGroup.addAction(action)
            action.triggered.connect(
                lambda x=None, c=code: [
                    SettingsManager.Set("game_asset_language", c),
                    game_asset_language_messagebox.exec(),
                ]
            )
            if SettingsManager.Get("game_asset_language") == code:
                action.setChecked(True)

        languageSelect = QMenu(
            QApplication.translate("app", "Tournament term language") + menu_margin,
            self.optionsBt.menu(),
        )
        self.optionsBt.menu().addMenu(languageSelect)

        languageSelectGroup = QActionGroup(languageSelect)
        languageSelectGroup.setExclusive(True)

        fg_language_messagebox = generate_restart_messagebox(
            QApplication.translate("app", "Tournament term language changed successfully.")
        )

        action = languageSelect.addAction(QApplication.translate("app", "Same as program language"))
        languageSelectGroup.addAction(action)
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(
            lambda x=None: [
                SettingsManager.Set("fg_term_language", "default"),
                fg_language_messagebox.exec(),
            ]
        )

        for code, language in LocaleHelper.languages.items():
            action = languageSelect.addAction(f"{language[0]} / {language[1]}")
            action.setCheckable(True)
            languageSelectGroup.addAction(action)
            action.triggered.connect(
                lambda x=None, c=code: [
                    SettingsManager.Set("fg_term_language", c),
                    fg_language_messagebox.exec(),
                ]
            )
            if SettingsManager.Get("fg_term_language") == code:
                action.setChecked(True)

        self.optionsBt.menu().addSeparator()

        # Links opened in the web browser
        help_messagebox = QMessageBox()
        help_messagebox.setWindowTitle(QApplication.translate("app", "Warning"))
        help_messagebox.setText(
            QApplication.translate(
                "app", "A new window has been opened in your default webbrowser."
            )
        )

        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Report a bug"))
        issues_url = f"{PROJECT_URL}/issues"
        action.triggered.connect(
            lambda x=None: [QDesktopServices.openUrl(QUrl(issues_url)), help_messagebox.exec()]
        )

        action = self.optionsBt.menu().addAction(
            QApplication.translate("app", "Contribute to the Asset Database")
        )
        asset_url = "https://github.com/joaorb64/StreamHelperAssets/"
        action.triggered.connect(
            lambda x=None: [QDesktopServices.openUrl(QUrl(asset_url)), help_messagebox.exec()]
        )

        self.optionsBt.menu().addSeparator()

        self.settingsWindow = SettingsWindow(self)

        action = self.optionsBt.menu().addAction(QApplication.translate("Settings", "Settings"))
        action.setIcon(ThemedIcon("assets/icons/settings.svg"))
        action.triggered.connect(lambda: self.settingsWindow.Open())

        self.aboutWidget = AboutWidget()
        action = self.optionsBt.menu().addAction(QApplication.translate("About", "About"))
        action.setIcon(ThemedIcon("assets/icons/info.svg"))
        action.triggered.connect(lambda: self.aboutWidget.show())

        self.RegisterGuideLinks(
            {
                "scoreboard": self.scoreboard,
                "stage-strike": self.stageWidget,
                "commentary": commentary,
                "tournament-info": tournamentInfo,
                "team-battle": teamBattle,
                "player-list": playerList,
                "bracket": bracket,
                "stream-queue": streamQueue,
                "display-controls": displayControls,
            }
        )

        # Game Select
        self.gameSelect = QComboBox()
        self.gameSelect.setEditable(True)
        self.gameSelect.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.gameSelect.completer().setCompletionMode(QCompleter.PopupCompletion)
        proxyModel = QSortFilterProxyModel()
        proxyModel.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxyModel.setSourceModel(self.gameSelect.model())
        self.gameSelect.model().setParent(proxyModel)
        self.gameSelect.setModel(proxyModel)
        self.gameSelect.setFont(self.font_small)
        self.gameSelect.activated.connect(
            lambda x: GameAssetManager.instance.LoadGameAssets(self.gameSelect.currentData())
        )
        GameAssetManager.instance.signals.onLoad.connect(self.SetGame)
        GameAssetManager.instance.signals.onLoadAssets.connect(self.ReloadGames)
        GameAssetManager.instance.signals.onLoad.connect(AssetDownloader.instance.CheckAssetUpdates)
        GameAssetManager.instance.signals.json_error.connect(
            lambda title, msg: QMessageBox.critical(self, title, msg)
        )
        AssetDownloader.instance.signals.AssetUpdates.connect(self.OnAssetUpdates)
        TournamentDataManager.instance.signals.tournament_changed.connect(self.SetGame)
        TournamentDataManager.instance.signals.tournament_url_update.connect(self.Signal_GameChange)

        # The game's options: reload its assets, modded content, download
        # assets
        self.gameOptionsBt = BarButton(
            ThemedIcon("assets/icons/chevron_down.svg"),
            QApplication.translate("app", "Game options"),
        )
        gameMenu = QMenu(self.gameOptionsBt)
        self.gameOptionsBt.setMenu(gameMenu)

        self.gameReloadAction = gameMenu.addAction(
            ThemedIcon("assets/icons/refresh.svg"),
            QApplication.translate("app", "Reload game assets"),
        )

        # Modded content UI: only for games with modded characters
        self.moddedContentCheck = gameMenu.addAction(
            QApplication.translate("app", "Modded content")
        )
        self.moddedContentCheck.setCheckable(True)
        self.moddedContentCheck.setVisible(False)
        self.moddedContentCheck.setChecked(False)

        action = gameMenu.addAction(
            ThemedIcon("assets/icons/download.svg"),
            QApplication.translate("app", "Download assets"),
        )
        action.triggered.connect(lambda: AssetDownloader.instance.DownloadAssets(self))

        def _on_game_load():
            self.moddedContentCheck.setVisible(GameAssetManager.instance.has_modded_content)
            # Block toggled so setting the action programmatically doesn't trigger a reload
            with QSignalBlocker(self.moddedContentCheck):
                self.moddedContentCheck.setChecked(
                    StateManager.Get("game").get("mods_active", False)
                )

        GameAssetManager.instance.signals.onLoad.connect(_on_game_load)

        GameAssetManager.instance.signals.onLoad.connect(
            lambda x=None: [
                self.moddedContentCheck.setVisible(GameAssetManager.instance.has_modded_content),
                self.moddedContentCheck.setChecked(
                    StateManager.Get("game").get("mods_active", False)
                ),
            ]
        )

        self.moddedContentCheck.toggled.connect(
            lambda x=None: [
                print("Checked: " + str(self.moddedContentCheck.isChecked())),
                GameAssetManager.instance.LoadGameAssets(
                    self.gameSelect.currentData(),
                    mods_active=self.moddedContentCheck.isChecked(),
                    mods_reload_mode=True,
                ),
            ]
        )

        self.gameSelect.activated.connect(lambda x=None: self.moddedContentCheck.setChecked(False))
        TournamentDataManager.instance.signals.tournament_changed.connect(
            lambda x=None: self.moddedContentCheck.setChecked(False)
        )

        self.gameReloadAction.triggered.connect(
            lambda: GameAssetManager.instance.LoadGameAssets(
                self.gameSelect.currentData(),
                mods_active=self.moddedContentCheck.isChecked(),
                mods_reload_mode=True,
            )
        )

        self.gameSelect.setMinimumContentsLength(16)
        self.gameSlot.addWidget(self.gameSelect)
        self.gameSlot.addWidget(self.gameOptionsBt)

        ScoreboardManager.instance.UpdateAmount(1)
        self.SetupScoreboardTabs()

        self.CheckForUpdates(True)
        self.ReloadGames()

        # Reset to default arrangement goes back to this
        self.workspaces.SetDefault(self.saveState())

        if self.qtSettings.value("geometry"):
            self.restoreGeometry(self.qtSettings.value("geometry"))

        if self.qtSettings.value("windowState"):
            self.restoreState(self.qtSettings.value("windowState"))

        # finish() waits up to a second for the window to be on screen, so
        # the window has to be shown first or every launch waits that long
        self.show()
        splash.finish(self)

        for path_error in [SettingsManager.load_error, StateManager.load_error]:
            if path_error:
                QMessageBox.critical(
                    self,
                    QApplication.translate("app", "Invalid JSON file"),
                    path_error,
                )

        if CountryHelper.countryModel is None:
            CountryHelper.LoadCountries()
        self.settingsWindow.UiMounted()
        # self.layoutOptions.UiMounted()
        TournamentDataManager.instance.UiMounted()
        GameAssetManager.instance.UiMounted()
        AlertNotification.instance.UiMounted()
        AssetDownloader.instance.UiMounted()
        PlayerDB.signals.db_updated.connect(self.webserver.ws_playerdb)
        PlayerDB.LoadDB()

        if SettingsManager.first_launch:
            self.wikiWindow.Open(GETTING_STARTED_PAGE)

    def RegisterGuideLinks(self, docks):
        """What the guide's hyperdrive://open/<target> links open"""

        def ShowDock(dock):
            dock.show()
            dock.raise_()

        for target, dock in docks.items():
            WikiWindow.RegisterAppLink(target, lambda d=dock: ShowDock(d))

        # settings/<page> opens a page of the settings, e.g. settings/api-keys
        WikiWindow.RegisterAppLink("settings", lambda page=None: self.settingsWindow.Open(page))
        WikiWindow.RegisterAppLink("player-database", lambda: self.playerDBWindow.Open(0))
        WikiWindow.RegisterAppLink("seed-editor", lambda: self.playerDBWindow.Open(1))
        WikiWindow.RegisterAppLink("layout-themes", self.OpenLayoutThemes)
        WikiWindow.RegisterAppLink(
            "download-assets", lambda: AssetDownloader.instance.DownloadAssets(self)
        )
        WikiWindow.RegisterAppLink(
            "set-tournament",
            lambda: TournamentDataManager.instance.SetStartggEventSlug(self),
        )
        WikiWindow.RegisterAppLink("about", lambda: self.aboutWidget.show())

    # =====================================================
    # GAMES
    # =====================================================
    def SetGame(self, mods_active=False):
        index = next(
            (
                i
                for i in range(self.gameSelect.model().rowCount())
                if self.gameSelect.itemText(i) == GameAssetManager.instance.selectedGame.get("name")
                or self.gameSelect.itemText(i)
                == GameAssetManager.instance.selectedGame.get("codename")
            ),
            None,
        )
        if index is not None:
            self.gameSelect.setCurrentIndex(index)
            # The start of a name too long to fit, not its end
            self.gameSelect.lineEdit().setCursorPosition(0)
            self.signals.GameChanged.emit()

    def Signal_GameChange(self, url):
        if url == "":
            self.gameSelect.setCurrentIndex(0)
            GameAssetManager.instance.selectedGame = {}

    def ReloadGames(self):
        logger.info("Reload games")
        with StateManager.SaveBlock():
            self.gameSelect.setModel(QStandardItemModel())
            self.gameSelect.addItem("", 0)
            for i, game in enumerate(GameAssetManager.instance.games.items()):
                logo_path = game[1].get("logo_path")
                if logo_path:
                    icon = QIcon(
                        QPixmap(
                            QImage(logo_path).scaled(
                                64,
                                64,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    )
                else:
                    icon = QIcon()
                if game[1].get("name"):
                    self.gameSelect.addItem(icon, game[1].get("name"), i + 1)
                else:
                    self.gameSelect.addItem(icon, game[0], i + 1)
            self.gameSelect.setIconSize(QSize(64, 64))
            self.gameSelect.setFixedHeight(32)
            view = QListView()
            view.setIconSize(QSize(64, 64))
            view.setStyleSheet("QListView::item { height: 32px; }")
            self.gameSelect.setView(view)
            self.gameSelect.model().sort(0)
            self.FitGameSelect()
            self.SetGame()

    def FitGameSelect(self):
        """Wide enough for the longest game name next to its logo, so names
        like Super Smash Bros. Ultimate aren't cut off"""
        metrics = self.gameSelect.fontMetrics()
        longest = max(
            (
                metrics.horizontalAdvance(self.gameSelect.itemText(i))
                for i in range(self.gameSelect.count())
            ),
            default=0,
        )
        # The logo, the arrow and the field's padding
        width = longest + self.gameSelect.iconSize().width() + 60
        self.gameSelect.setMinimumWidth(min(width, 360))

    def DetectGameFromId(self, id):
        def detect_smashgg_id_match(games, game, id):
            result = str(games[game].get("smashgg_game_id", "")) == str(id)
            if not result:
                alternates = games[game].get("alternate_versions")
                alternates_ids = []
                for alternate in alternates:
                    if alternate.get("smashgg_game_id"):
                        alternates_ids.append(str(alternate.get("smashgg_game_id")))
                result = str(id) in alternates_ids
            return result

        game = next(
            (
                i + 1
                for i, game in enumerate(self.games)
                if detect_smashgg_id_match(self.games, game, id)
            ),
            None,
        )

        if game is not None and self.gameSelect.currentIndex() != game:
            self.gameSelect.setCurrentIndex(game)
            self.LoadGameAssets(game)

    # =====================================================
    # COMPLETED SETS
    # =====================================================
    def _CompletedSetsProvider(self):
        return TournamentDataManager.instance.provider if TournamentDataManager.instance else None

    def _CompletedSetsSupported(self):
        provider = self._CompletedSetsProvider()
        return provider is not None and provider.SUPPORTS_COMPLETED_SETS

    def PullCompletedSets(self, done):
        if not self._CompletedSetsSupported():
            done()
            return
        TournamentDataManager.instance.GetCompletedSets(on_finished=done)

    def ToggleCompletedSetsAutoPull(self, enabled):
        SettingsManager.Set("general.completed_sets_auto_pull", enabled)
        if enabled:
            Scheduler.instance.Start("completed_sets", run_now=True)
        else:
            Scheduler.instance.Stop("completed_sets")

    def CompletedSetsTournamentChanged(self):
        if Scheduler.instance.IsEnabled("completed_sets"):
            Scheduler.instance.TriggerNow("completed_sets")

    def UpdateCompletedSetsTimer(self):
        scheduler = Scheduler.instance
        pill = self.completedSetsPill
        if scheduler.IsRunning("completed_sets"):
            pill.SetStatus(STATUS_BUSY, QApplication.translate("app", "Pulling..."))
        elif not scheduler.IsEnabled("completed_sets"):
            pill.SetStatus(STATUS_OFF, QApplication.translate("app", "Auto pull off"))
        elif not self._CompletedSetsSupported():
            pill.SetStatus(STATUS_OFF, QApplication.translate("app", "Waiting for a tournament"))
        else:
            remaining = scheduler.RemainingMs("completed_sets")
            if remaining is not None:
                pill.SetStatus(
                    STATUS_OK,
                    QApplication.translate("app", "Next pull in {0}s").format(
                        round(remaining / 1000)
                    ),
                )

    def LoadCompletedSetsClicked(self, data):
        StateManager.Set(
            "completed_sets", {index + 1: set for index, set in enumerate(data)}, replace=True
        )

    # =====================================================
    # TOURNAMENT BUTTONS
    # =====================================================
    def UpdateLastSetsButton(self):
        supported = self._CompletedSetsSupported()
        self.btPullCompletedSets.setEnabled(supported)
        self.pullCompletedSetsAction.setEnabled(supported)

        # start.gg's text and icon until an event is loaded
        provider = self._CompletedSetsProvider()
        if provider is None or not provider.COMPLETED_SETS_BUTTON:
            provider = StartGGDataProvider
        text = QApplication.translate("app", provider.COMPLETED_SETS_BUTTON)
        self.btPullCompletedSets.setToolTip(text)
        self.pullCompletedSetsAction.setText(text)
        self.pullCompletedSetsAction.setIcon(
            ThemedIcon(provider.ICON) if provider.ICON_THEMED else QIcon(provider.ICON)
        )

    def UpdateTournamentButtons(self):
        # Without an event the chip loads one; with one it opens its actions
        provider = TournamentDataManager.instance.provider
        chip = self.tournamentChip
        chip.setMenu(None if provider is None else self.tournamentMenu)
        chip.SetPrimary(provider is None)
        if provider is None:
            chip.SetIcon(QIcon())
            chip.SetCaption("")
            chip.SetTitle(QApplication.translate("app", "Load tournament"))
        else:
            chip.SetIcon(
                ThemedIcon(provider.ICON) if provider.ICON_THEMED else QIcon(provider.ICON)
            )
            # The event's link until its names arrive, which they may not
            # if pulling them fails
            chip.SetCaption(
                (provider.HOST or "") + " · " + QApplication.translate("app", "Loading...")
            )
            chip.SetTitle(provider.url or "")

    def UpdateTournamentChip(self, data):
        provider = TournamentDataManager.instance.provider
        if provider is None or not data:
            return
        title = " › ".join(
            name for name in [data.get("tournamentName"), data.get("eventName")] if name
        )
        self.tournamentChip.SetTitle(title or provider.url)
        caption = provider.HOST or ""
        if data.get("numEntrants"):
            caption += " · " + QApplication.translate("app", "{0} entrants").format(
                data.get("numEntrants")
            )
        self.tournamentChip.SetCaption(caption)

    def LoadTournamentEvents(self):
        # The loaded tournament's events, for the bottom of its menu. Another
        # event of the same tournament keeps the ones already fetched.
        provider = TournamentDataManager.instance.provider
        parsed = ParseTournamentLink(provider.url) if provider and provider.url else None
        if parsed is None:
            self.tournamentEvents = None
            self.FillEventsMenu(None)
            return
        slug = (parsed.get("provider"), parsed.get("slug"))
        if self.tournamentEvents and self.tournamentEvents[0] == slug:
            self.FillEventsMenu(self.tournamentEvents[1])
            return

        self.tournamentEvents = None
        self.FillEventsMenu(None)

        def loaded(result):
            # Not if another tournament was loaded meanwhile
            if TournamentDataManager.instance.provider is not provider:
                return
            self.tournamentEvents = (slug, result.get("events", []))
            self.FillEventsMenu(self.tournamentEvents[1])

        def failed(error):
            if TournamentDataManager.instance.provider is provider:
                self.FillEventsMenu([])

        worker = Worker(
            lambda progress_callback=None, cancel_event=None: FetchTournamentEvents(
                parsed, SettingsManager.Get("api_keys.parrygg")
            )
        )
        worker.signals.result.connect(loaded)
        worker.signals.error.connect(failed)
        TournamentDataManager.instance.StartWithActivity(worker, "events")

    def FillEventsMenu(self, events):
        """The events at the bottom of the tournament's menu, the loaded one
        checked. None while they're fetched; with none (they couldn't be),
        the event picker instead, which says why."""
        for action in self.eventActions.actions():
            self.eventActions.removeAction(action)
            self.tournamentMenu.removeAction(action)
            action.deleteLater()

        provider = TournamentDataManager.instance.provider
        if events is None:
            self.eventsHeader.setText(QApplication.translate("app", "Loading events..."))
            return
        if not events:
            self.eventsHeader.setText(QApplication.translate("app", "Events in this tournament"))
            action = self.tournamentMenu.addAction(
                ThemedIcon("./assets/icons/swap.svg"),
                QApplication.translate("app", "Select event..."),
            )
            action.triggered.connect(lambda: TournamentDataManager.instance.SelectEvent(self))
            self.eventActions.addAction(action)
            return

        self.eventsHeader.setText(QApplication.translate("app", "Events in this tournament"))
        for event in events:
            action = self.tournamentMenu.addAction(event.get("name") or event.get("url", ""))
            action.setCheckable(True)
            action.setChecked(IsSameEvent(event.get("url"), provider.url if provider else None))
            action.setToolTip(
                " · ".join(
                    part
                    for part in [
                        event.get("game"),
                        QApplication.translate("app", "{0} entrants").format(
                            event.get("numEntrants") or 0
                        ),
                    ]
                    if part
                )
            )
            action.triggered.connect(
                lambda checked=False, url=event.get("url"): self.LoadEvent(url)
            )
            self.eventActions.addAction(action)

    def LoadEvent(self, url):
        # Another event of the loaded tournament, as the event picker loads it
        provider = TournamentDataManager.instance.provider
        if not url or (provider and IsSameEvent(url, provider.url)):
            return
        SettingsManager.Set("TOURNAMENT_URL", url)
        TournamentDataManager.instance.SetTournament(url)

    def UpdateWorkspaceButton(self):
        current = self.workspaces.Current()
        self.workspaceBt.SetLabel(current)
        self.workspaceBt.setToolTip(
            QApplication.translate("app", "Workspace")
            + (QApplication.translate("punctuation", ":") + " " + current if current else "")
        )

    def UpdateWidgetsButton(self):
        # How many widgets are hidden, next to the button
        hidden = [action for action in self.widgetsBt.menu().actions() if not action.isChecked()]
        self.widgetsBt.SetLabel(str(len(hidden)) if hidden else "")
        self.widgetsBt.setToolTip(
            QApplication.translate("app", "Widgets")
            + (
                " "
                + QApplication.translate("punctuation", "(")
                + QApplication.translate("app", "{0} hidden").format(len(hidden))
                + QApplication.translate("punctuation", ")")
                if hidden
                else ""
            )
        )

    # =====================================================
    # UPDATES
    # =====================================================
    def FetchLatestRelease(self, progress_callback=None, cancel_event=None):
        """GitHub's latest release, and the error if it couldn't be fetched"""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{REPOSITORY}/releases/latest", timeout=15
            )
            return (orjson.loads(response.text), None)
        except Exception as e:
            return (None, e)

    def CheckForUpdates(self, silent=False):
        # Stub until REPOSITORY is set: nothing is checked at startup
        if not REPOSITORY:
            if not silent:
                messagebox = QMessageBox()
                messagebox.setWindowTitle(QApplication.translate("app", "Info"))
                messagebox.setText(
                    QApplication.translate("app", "Updates aren't available for HyperDrive yet.")
                )
                messagebox.exec()
            return

        if silent:
            # The check at startup asks GitHub off the UI thread, as waiting
            # for it held the window back
            worker = Worker(self.FetchLatestRelease)
            worker.signals.result.connect(self.SilentUpdateCheckDone)
            self.threadpool.start(worker)
            return

        release, error = self.FetchLatestRelease()
        if error is not None:
            messagebox = QMessageBox()
            messagebox.setWindowTitle(QApplication.translate("app", "Warning"))
            messagebox.setText(
                QApplication.translate("app", "Failed to fetch version from github:")
                + "\n"
                + str(error)
            )
            messagebox.exec()
        self.ShowUpdateCheck(release, silent)

    def SilentUpdateCheckDone(self, result):
        release, error = result
        self.ShowUpdateCheck(release, True)

    def ShowUpdateCheck(self, release, silent):
        versions = get_versions()

        if versions and release:
            myVersion = versions.get("program", "0.0")
            currVersion = release.get("tag_name", "0.0")

            # Compared as versions, so that 1.10.0 is newer than 1.9.0
            try:
                updateAvailable = parse(myVersion) < parse(currVersion)
            except InvalidVersion:
                updateAvailable = False

            if silent == False:
                if updateAvailable:
                    buttonReply = QDialog(self)
                    buttonReply.setWindowTitle(QApplication.translate("app", "Updater"))
                    buttonReply.setWindowModality(Qt.WindowModal)
                    vbox = QVBoxLayout()
                    buttonReply.setLayout(vbox)

                    buttonReply.layout().addWidget(
                        QLabel(
                            QApplication.translate("app", "New version available:")
                            + " "
                            + myVersion
                            + " → "
                            + currVersion
                        )
                    )
                    buttonReply.layout().addWidget(QLabel(release["body"]))
                    buttonReply.layout().addWidget(
                        QLabel(
                            QApplication.translate("app", "Update to latest version?")
                            + "\n\n"
                            + QApplication.translate(
                                "app",
                                "NOTE: This will open a new tab in your browser and close HyperDrive.",
                            )
                        )
                    )

                    hbox = QHBoxLayout()
                    vbox.addLayout(hbox)

                    btUpdate = QPushButton(QApplication.translate("app", "Update"))
                    hbox.addWidget(btUpdate)
                    btCancel = QPushButton(QApplication.translate("app", "Cancel"))
                    hbox.addWidget(btCancel)

                    buttonReply.show()

                    def Update():  # Opens the releases page in the web browser
                        latest_release_url = f"https://github.com/{REPOSITORY}/releases/latest"
                        QDesktopServices.openUrl(QUrl(latest_release_url))
                        QCoreApplication.quit()

                    btUpdate.clicked.connect(Update)
                    btCancel.clicked.connect(lambda: buttonReply.close())
                else:
                    messagebox = QMessageBox()
                    messagebox.setWindowTitle(QApplication.translate("app", "Info"))
                    messagebox.setText(
                        QApplication.translate("app", "You're already using the latest version")
                    )
                    messagebox.exec()
            else:
                if updateAvailable:
                    self.optionsBt.setIcon(
                        ThemedIcon(
                            "assets/icons/menu.svg", badge="./assets/icons/update_circle.svg"
                        )
                    )
                    self.updateAction.setText(
                        QApplication.translate("app", "Check for updates")
                        + " "
                        + QApplication.translate("punctuation", "[")
                        + QApplication.translate("app", "Update available!")
                        + QApplication.translate("punctuation", "]")
                    )

    # Checks for asset updates after game assets are loaded
    # If updates are available, edit QAction icon
    def OnAssetUpdates(self, updates):
        try:
            if len(updates) > 0:
                self.downloadAssetsAction.setIcon(
                    ThemedIcon(
                        "assets/icons/download.svg", badge="./assets/icons/update_circle.svg"
                    )
                )
            else:
                self.downloadAssetsAction.setIcon(ThemedIcon("assets/icons/download.svg"))
        except:
            logger.error(traceback.format_exc())

    # =====================================================
    # WINDOW
    # =====================================================
    def ToggleAlwaysOnTop(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def SetupScoreboardTabs(self):
        """Scoreboards are added, removed and renamed on the Scoreboard
        Manager's own tabs"""
        tabs = ScoreboardManager.instance.tabs
        corner = TabCorner(tabs.tabBar())
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(0, 2, 4, 2)
        layout.setSpacing(4)

        self.removeScoreboardBt = QToolButton()
        self.removeScoreboardBt.setText("−")
        self.removeScoreboardBt.setToolTip(
            QApplication.translate("app", "Remove the last scoreboard")
        )
        self.removeScoreboardBt.clicked.connect(
            lambda: self.SetScoreboardAmount(ScoreboardManager.instance.GetTabAmount() - 1)
        )
        layout.addWidget(self.removeScoreboardBt)

        self.addScoreboardBt = QToolButton()
        self.addScoreboardBt.setText("+ " + QApplication.translate("app", "Scoreboard"))
        self.addScoreboardBt.setToolTip(
            QApplication.translate("app", "Add a scoreboard, for another stream or station")
        )
        self.addScoreboardBt.clicked.connect(
            lambda: self.SetScoreboardAmount(ScoreboardManager.instance.GetTabAmount() + 1)
        )
        layout.addWidget(self.addScoreboardBt)

        # The corner only gets the tab bar's height (TabCorner), which can be
        # less than the buttons' (fonts, density): they fit it instead of
        # being cut off
        for button in (self.removeScoreboardBt, self.addScoreboardBt):
            button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)

        tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        tabBar = tabs.tabBar()
        tabBar.setToolTip(
            QApplication.translate("app", "Double-click or right-click a tab to rename it")
        )
        tabBar.tabBarDoubleClicked.connect(self.RenameScoreboardTab)
        tabBar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabBar.customContextMenuRequested.connect(self.ScoreboardTabMenu)
        self.UpdateScoreboardButtons()

    def SetScoreboardAmount(self, amount):
        amount = max(1, min(MAX_SCOREBOARDS, amount))
        if amount != ScoreboardManager.instance.GetTabAmount():
            ScoreboardManager.instance.signals.ScoreboardAmountChanged.emit(amount)
        self.UpdateScoreboardButtons()

    def UpdateScoreboardButtons(self):
        amount = ScoreboardManager.instance.GetTabAmount()
        self.removeScoreboardBt.setEnabled(amount > 1)
        self.addScoreboardBt.setEnabled(amount < MAX_SCOREBOARDS)

    def ScoreboardTabMenu(self, pos):
        tabBar = ScoreboardManager.instance.tabs.tabBar()
        index = tabBar.tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        menu.addAction(
            QApplication.translate("app", "Rename scoreboard..."),
            lambda: self.RenameScoreboardTab(index),
        )
        menu.exec(tabBar.mapToGlobal(pos))

    def RenameScoreboardTab(self, index):
        if index < 0:
            return
        name, ok = QInputDialog.getText(
            self,
            QApplication.translate("app", "Change Tab Title"),
            QApplication.translate("app", "Name of scoreboard {0}:").format(index + 1)
            + "\n"
            + QApplication.translate("app", "Leave it empty for the default name."),
            text=ScoreboardManager.instance.GetTabName(index + 1),
        )
        if ok:
            ScoreboardManager.instance.SetTabName(index + 1, name.strip())

    def OpenLayoutThemes(self):
        # Built on first use: it lists every installed font
        if self.layoutThemes is None:
            self.layoutThemes = LayoutThemeWindow(self)
        self.layoutThemes.Refresh()
        self.layoutThemes.show()
        self.layoutThemes.raise_()
        self.layoutThemes.activateWindow()

    def closeEvent(self, event):
        logger.info("Shutting down...")
        StateManager.FlushPendingSave()
        self.qtSettings.setValue("geometry", self.saveGeometry())
        self.qtSettings.setValue("windowState", self.saveState())

        tmpDir = ResolvePath("tmp")
        if os.path.isdir(tmpDir):
            shutil.rmtree(tmpDir)

        try:
            crashlog.close()
            if crashpath.stat().st_size == 0:
                crashpath.unlink()
        except:
            pass

        self.webserver.Stop()

        for window in QApplication.allWindows():
            if window != self:
                window.close()

        super().closeEvent(event)
