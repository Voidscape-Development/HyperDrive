#!/usr/bin/env python3
import atexit
import faulthandler
import json
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
from .Helpers.VersionHelper import PROJECT_URL, REPOSITORY, add_beta_label

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
from src.WebServer import WebServer

from .AlertNotification import AlertNotification
from .BracketWidget import BracketWidget
from .CommentaryWidget import CommentaryWidget
from .GameAssetManager import GameAssetManager
from .Helpers.CountryHelper import CountryHelper
from .Hotkeys import Hotkeys
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
from .TournamentInfoWidget import TournamentInfoWidget
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


def remove_accents_lower(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


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

        if not os.path.exists("out/"):
            os.mkdir("out/")

        if not os.path.exists("./user_data/games"):
            os.makedirs("./user_data/games")

        if os.path.exists("./HyperDrive_old.exe"):
            os.remove("./HyperDrive_old.exe")

        self.font_small = QFont("./assets/font/RobotoCondensed.ttf", pointSize=8)

        self.threadpool = QThreadPool()
        self.saveMutex = QMutex()

        self.player_layouts = []

        self.allplayers = None
        self.local_players = None

        RemoveObsoleteFiles()
        CountryHelper.LoadCountries()

        try:
            version = json.load(open(ResolvePath("./assets/versions.json"), encoding="utf-8")).get(
                "program", "?"
            )
        except Exception as e:
            version = "?"

        self.setGeometry(300, 300, 800, 100)
        self.setWindowTitle("HyperDrive v" + version)

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
        teamBattle.setObjectName(
            add_beta_label(QApplication.translate("app", "Crew/Team Battle"), "team_battle")
        )
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

        commentary = CommentaryWidget()
        commentary.setWindowIcon(ThemedIcon("assets/icons/mic.svg"))
        commentary.setObjectName(QApplication.translate("app", "Commentary"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, commentary)
        self.dockWidgets.append(commentary)

        self.webserver = WebServer(
            parent=self, stageWidget=self.stageWidget, commentaryWidget=commentary
        )
        self.webserver.start()
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
        self.scoreboard.raise_()

        # Game
        base_layout = QHBoxLayout()

        group_box = QWidget()
        group_box.setLayout(QVBoxLayout())
        group_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        base_layout.layout().addWidget(group_box)

        # Set tournament
        hbox = QHBoxLayout()
        group_box.layout().addLayout(hbox)

        self.setTournamentBt = QPushButton(QApplication.translate("app", "Set tournament"))
        hbox.addWidget(self.setTournamentBt)
        self.setTournamentBt.clicked.connect(
            lambda bt=None, s=self: TournamentDataManager.instance.SetStartggEventSlug(s)
        )

        # Switch to another event of the same tournament
        self.selectEventBt = QPushButton(QApplication.translate("app", "Select event"))
        self.selectEventBt.setIcon(ThemedIcon("./assets/icons/swap.svg"))
        self.selectEventBt.setToolTip(
            QApplication.translate("app", "Switch to another event of the same tournament")
        )
        self.selectEventBt.clicked.connect(
            lambda bt=None, s=self: TournamentDataManager.instance.SelectEvent(s)
        )
        hbox.addWidget(self.selectEventBt)

        # For entrants who registered after the event was loaded
        self.repullEntrantsBt = QPushButton(QApplication.translate("app", "Repull entrants"))
        self.repullEntrantsBt.setIcon(ThemedIcon("./assets/icons/people.svg"))
        self.repullEntrantsBt.setToolTip(
            QApplication.translate(
                "app",
                "Pull the event's entrants again, to get players who registered after it was loaded",
            )
        )
        self.repullEntrantsBt.clicked.connect(
            lambda: TournamentDataManager.instance.RepullEntrants()
        )
        hbox.addWidget(self.repullEntrantsBt)

        self.unsetTournamentBt = QPushButton()
        self.unsetTournamentBt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.unsetTournamentBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.unsetTournamentBt.clicked.connect(
            lambda: [TournamentDataManager.instance.SetTournament(None)]
        )
        hbox.addWidget(self.unsetTournamentBt)

        # Completed Sets Feature
        hbox = QHBoxLayout()
        group_box.layout().addLayout(hbox)
        self.btPullCompletedSets = QPushButton(
            QApplication.translate("app", "Pull Latest Completed Sets from StartGG")
        )
        self.btPullCompletedSets.setIcon(ThemedIcon("./assets/icons/startgg.svg"))
        # Manual pulls go through the scheduler too, so they can't overlap
        # an automatic one and they push the next automatic one back
        self.btPullCompletedSets.clicked.connect(
            lambda: Scheduler.instance.TriggerNow("completed_sets")
        )
        hbox.addWidget(self.btPullCompletedSets)

        self.cbAutoPullCompletedSets = QCheckBox(QApplication.translate("app", "Auto pull"))
        self.cbAutoPullCompletedSets.setToolTip(
            QApplication.translate(
                "app",
                "Pull the latest completed sets periodically. The interval can be changed in Settings > General.",
            )
        )
        self.cbAutoPullCompletedSets.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        hbox.addWidget(self.cbAutoPullCompletedSets)

        self.labelCompletedSetsTimer = QLabel()
        self.labelCompletedSetsTimer.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        hbox.addWidget(self.labelCompletedSetsTimer)

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
        self.cbAutoPullCompletedSets.setChecked(autoPull)
        if autoPull:
            Scheduler.instance.Start("completed_sets")
        self.cbAutoPullCompletedSets.toggled.connect(self.ToggleCompletedSetsAutoPull)

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
        self.UpdateCompletedSetsTimer()

        # Settings
        menu_margin = " " * 6
        self.optionsBt = QToolButton()
        self.optionsBt.setIcon(ThemedIcon("assets/icons/menu.svg"))
        self.optionsBt.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.optionsBt.setPopupMode(QToolButton.InstantPopup)
        base_layout.addWidget(self.optionsBt)
        self.optionsBt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.optionsBt.setFixedSize(QSize(32, 32))
        self.optionsBt.setIconSize(QSize(32, 32))
        menu = QMenu()
        self.optionsBt.setMenu(menu)
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

        toggleWidgets = QMenu(
            QApplication.translate("app", "Toggle widgets") + menu_margin, self.optionsBt.menu()
        )
        self.optionsBt.menu().addMenu(toggleWidgets)
        toggleWidgets.addAction(self.scoreboard.toggleViewAction())
        toggleWidgets.addAction(self.stageWidget.toggleViewAction())
        toggleWidgets.addAction(commentary.toggleViewAction())
        toggleWidgets.addAction(tournamentInfo.toggleViewAction())
        # toggleWidgets.addAction(teamBattle.toggleViewAction())
        toggleWidgets.addAction(playerList.toggleViewAction())
        toggleWidgets.addAction(bracket.toggleViewAction())
        toggleWidgets.addAction(streamQueue.toggleViewAction())

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

        action = self.optionsBt.menu().addAction(QApplication.translate("app", "Migrate Layout"))
        action.triggered.connect(self.MigrateWindow)

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

        # Help menu code
        help_messagebox = QMessageBox()
        help_messagebox.setWindowTitle(QApplication.translate("app", "Warning"))
        help_messagebox.setText(
            QApplication.translate(
                "app", "A new window has been opened in your default webbrowser."
            )
        )

        helpMenu = QMenu(QApplication.translate("app", "Help") + menu_margin, self.optionsBt.menu())
        self.optionsBt.menu().addMenu(helpMenu)
        action = helpMenu.addAction(QApplication.translate("app", "Report a bug"))
        issues_url = f"{PROJECT_URL}/issues"
        action.triggered.connect(
            lambda x=None: [QDesktopServices.openUrl(QUrl(issues_url)), help_messagebox.exec()]
        )

        helpMenu.addSeparator()

        action = helpMenu.addAction(
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
        action.triggered.connect(lambda: self.settingsWindow.show())

        self.aboutWidget = AboutWidget()
        action = self.optionsBt.menu().addAction(QApplication.translate("About", "About"))
        action.setIcon(ThemedIcon("assets/icons/info.svg"))
        action.triggered.connect(lambda: self.aboutWidget.show())

        # Game Select and Scoreboard Count
        hbox = QHBoxLayout()
        group_box.layout().addLayout(hbox)

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

        label_margin = " " * 5

        # Modded content UI
        self.moddedContentWidget = QWidget()
        moddedContentLayout = QHBoxLayout()
        self.moddedContentWidget.setLayout(moddedContentLayout)
        self.moddedContentCheck = QCheckBox()
        self.moddedContentWidget.setVisible(False)
        self.moddedContentCheck.setChecked(False)
        moddedContentCheckLabel = QLabel()
        moddedContentCheckLabel.setText(
            label_margin + QApplication.translate("app", "Modded content")
        )
        self.moddedContentWidget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        moddedContentLayout.addWidget(moddedContentCheckLabel)
        moddedContentLayout.addWidget(self.moddedContentCheck)

        def _on_game_load():
            self.moddedContentWidget.setVisible(GameAssetManager.instance.has_modded_content)
            # Block stateChanged so setting the checkbox programmatically doesn't trigger a reload
            with QSignalBlocker(self.moddedContentCheck):
                self.moddedContentCheck.setChecked(
                    StateManager.Get("game").get("mods_active", False)
                )

        GameAssetManager.instance.signals.onLoad.connect(_on_game_load)

        GameAssetManager.instance.signals.onLoad.connect(
            lambda x=None: [
                self.moddedContentWidget.setVisible(GameAssetManager.instance.has_modded_content),
                self.moddedContentCheck.setChecked(
                    StateManager.Get("game").get("mods_active", False)
                ),
            ]
        )

        self.moddedContentCheck.stateChanged.connect(
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

        self.gameReloadBtn = QPushButton()
        self.gameReloadBtn.setIcon(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.gameReloadBtn.setToolTip(QApplication.translate("app", "Reload game assets"))
        self.gameReloadBtn.setFixedSize(24, 24)
        self.gameReloadBtn.clicked.connect(
            lambda: GameAssetManager.instance.LoadGameAssets(
                self.gameSelect.currentData(),
                mods_active=self.moddedContentCheck.isChecked(),
                mods_reload_mode=True,
            )
        )

        pre_base_layout.addLayout(base_layout)
        hbox.addWidget(self.gameSelect)
        hbox.addWidget(self.gameReloadBtn)
        hbox.addWidget(self.moddedContentWidget)

        self.scoreboardAmount = QSpinBox()
        self.scoreboardAmount.setMaximumWidth(100)
        self.scoreboardAmount.lineEdit().setReadOnly(True)
        self.scoreboardAmount.setMinimum(1)
        self.scoreboardAmount.setMaximum(10)

        self.scoreboardAmount.valueChanged.connect(
            lambda val: ScoreboardManager.instance.signals.ScoreboardAmountChanged.emit(val)
        )

        label = QLabel(label_margin + QApplication.translate("app", "Number of Scoreboards"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.btLoadModifyTabName = QPushButton(QApplication.translate("app", "Modify Tab Name"))
        self.btLoadModifyTabName.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.btLoadModifyTabName.clicked.connect(self.ChangeTab)

        hbox.addWidget(label)
        hbox.addWidget(self.scoreboardAmount)
        hbox.addWidget(self.btLoadModifyTabName)

        ScoreboardManager.instance.UpdateAmount(1)

        self.CheckForUpdates(True)
        self.ReloadGames()

        self.qtSettings = QSettings("Voidscape Development", "HyperDrive")

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
        Hotkeys.instance.UiMounted(self)
        PlayerDB.signals.db_updated.connect(self.webserver.ws_playerdb)
        PlayerDB.LoadDB()

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
            self.signals.GameChanged.emit()

    def Signal_GameChange(self, url):
        if url == "":
            self.gameSelect.setCurrentIndex(0)
            GameAssetManager.instance.selectedGame = {}

    def _CompletedSetsProviderName(self):
        provider = (
            TournamentDataManager.instance.provider if TournamentDataManager.instance else None
        )
        return provider.name if provider else None

    def _CompletedSetsSupported(self):
        # Both providers implement GetCompletedSets
        return self._CompletedSetsProviderName() in ("StartGG", "ParryGG")

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
        if not scheduler.IsEnabled("completed_sets"):
            self.labelCompletedSetsTimer.setVisible(False)
            return
        self.labelCompletedSetsTimer.setVisible(True)
        if not self._CompletedSetsSupported():
            self.labelCompletedSetsTimer.setText(
                QApplication.translate("app", "Waiting for a tournament")
            )
        elif scheduler.IsRunning("completed_sets"):
            self.labelCompletedSetsTimer.setText(QApplication.translate("app", "Pulling..."))
        else:
            remaining = scheduler.RemainingMs("completed_sets")
            if remaining is not None:
                self.labelCompletedSetsTimer.setText(
                    QApplication.translate("app", "Next pull in {0}s").format(
                        round(remaining / 1000)
                    )
                )

    def UpdateLastSetsButton(self):
        provider_name = self._CompletedSetsProviderName()

        self.btPullCompletedSets.setEnabled(self._CompletedSetsSupported())

        if provider_name == "StartGG":
            self.btPullCompletedSets.setText(
                QApplication.translate("app", "Pull Latest Completed Sets from StartGG")
            )
            self.btPullCompletedSets.setIcon(ThemedIcon("./assets/icons/startgg.svg"))
        elif provider_name == "ParryGG":
            self.btPullCompletedSets.setText(
                QApplication.translate("app", "Pull Latest Completed Sets from ParryGG")
            )
            self.btPullCompletedSets.setIcon(QIcon("./assets/icons/parrygg.png"))
        else:
            self.btPullCompletedSets.setText(
                QApplication.translate("app", "Pull Latest Completed Sets from StartGG")
            )
            self.btPullCompletedSets.setIcon(ThemedIcon("./assets/icons/startgg.svg"))

    def UpdateTournamentButtons(self):
        # Both need an event loaded
        loaded = TournamentDataManager.instance.provider is not None
        self.selectEventBt.setEnabled(loaded)
        self.repullEntrantsBt.setEnabled(loaded)

    def LoadCompletedSetsClicked(self, data):
        StateManager.Set("completed_sets", {index + 1: set for index, set in enumerate(data)})

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
            self.SetGame()

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
        versions = None

        try:
            versions = json.load(open(ResolvePath("./assets/versions.json"), encoding="utf-8"))
        except Exception as e:
            logger.error("Local version file not found")

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

    def ToggleAlwaysOnTop(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def ChangeTab(self):
        tabNameWindow = QDialog(self)
        tabNameWindow.setWindowTitle(QApplication.translate("app", "Change Tab Title"))
        tabNameWindow.setMinimumWidth(400)
        vbox = QVBoxLayout()
        tabNameWindow.setLayout(vbox)
        hbox = QHBoxLayout()
        label = QLabel(QApplication.translate("app", "Scoreboard Number"))
        number = QSpinBox()
        number.setMinimum(1)
        number.setMaximum(ScoreboardManager.instance.GetTabAmount())
        hbox.addWidget(label)
        hbox.addWidget(number)
        vbox.addLayout(hbox)
        name = QLineEdit()
        vbox.addWidget(name)

        setSelection = QPushButton(text=QApplication.translate("app", "Set Tab Title"))

        def UpdateTabName():
            ScoreboardManager.instance.SetTabName(number.value(), name.text())
            tabNameWindow.close()

        setSelection.clicked.connect(UpdateTabName)

        vbox.addWidget(setSelection)

        tabNameWindow.show()

    def OpenLayoutThemes(self):
        # Built on first use: it lists every installed font
        if self.layoutThemes is None:
            self.layoutThemes = LayoutThemeWindow(self)
        self.layoutThemes.Refresh()
        self.layoutThemes.show()
        self.layoutThemes.raise_()
        self.layoutThemes.activateWindow()

    def MigrateWindow(self):
        migrateWindow = QDialog(self)
        migrateWindow.setWindowTitle(QApplication.translate("app", "Migrate Scoreboard Layout"))
        migrateWindow.setMinimumWidth(800)
        vbox = QVBoxLayout()
        migrateWindow.setLayout(vbox)
        hbox = QHBoxLayout()
        label = QLabel(QApplication.translate("app", "File Path"))
        filePath = QLineEdit()
        fileExplorer = QPushButton(text=QApplication.translate("app", "Find File..."))
        hbox.addWidget(label)
        hbox.addWidget(filePath)
        hbox.addWidget(fileExplorer)
        vbox.addLayout(hbox)

        migrate = QPushButton(text=QApplication.translate("app", "Migrate Layout"))

        def open_dialog():
            fname, _ok = QFileDialog.getOpenFileName(
                migrateWindow,
                QApplication.translate("app", "Open Layout Javascript File"),
                os.getcwd(),
                QApplication.translate("app", "Javascript File") + "  (*.js)",
            )
            if fname:
                filePath.setText(str(fname))

        fileExplorer.clicked.connect(open_dialog)

        def MigrateLayout():
            data = None
            with open(filePath.text()) as file:
                data = file.read()

                data = data.replace("data.score.", "data.score[1].")
                data = data.replace("oldData.score.", "oldData.score[1].")
                data = data.replace(
                    '_.get(data, "score.stage_strike.', '_.get(data, "score.1.stage_strike.'
                )
                data = data.replace(
                    '_.get(oldData, "score.stage_strike.', '_.get(oldData, "score.1.stage_strike.'
                )
                data = data.replace(
                    "source: `score.team.${t + 1}`", "source: `score.1.team.${t + 1}`"
                )
                data = data.replace("data.score[1].ruleset", "data.score.ruleset")

            with open(filePath.text(), "w") as file:
                file.write(data)

            logger.info("Completed Layout Migration at: " + filePath.text())

            completeDialog = QDialog(migrateWindow)
            completeDialog.setWindowTitle(QApplication.translate("app", "Migration Complete"))
            completeDialog.setMinimumWidth(500)
            vbox2 = QVBoxLayout()
            completeDialog.setLayout(vbox2)
            completeText = QLabel(QApplication.translate("app", "Layout Migration has completed!"))
            completeText.setAlignment(Qt.AlignmentFlag.AlignCenter)
            closeButton = QPushButton(text=QApplication.translate("app", "Close Window"))
            vbox2.addWidget(completeText)
            vbox2.addWidget(closeButton)
            closeButton.clicked.connect(completeDialog.close)
            completeDialog.show()

        migrate.clicked.connect(MigrateLayout)

        vbox.addWidget(migrate)

        migrateWindow.show()
