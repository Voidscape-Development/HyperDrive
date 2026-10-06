import math
import os
import socket
from copy import deepcopy

from loguru import logger
from qtpy import uic
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.TSHColorButton import TSHColorButton

from .Helpers.TSHDictHelper import deep_get
from .Helpers.TSHDirHelper import TSHResolve
from .Helpers.TSHLocaleHelper import TSHLocaleHelper
from .Helpers.TSHVersionHelper import add_beta_label
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHGameReportWidget import TSHGameReportWidget
from .TSHHotkeys import TSHHotkeys
from .TSHPlayerDB import TSHPlayerDB
from .TSHScheduler import (
    SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
    SCOREBOARD_AUTO_UPDATE_GROUP,
    SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS,
    TSHScheduler,
)
from .TSHScoreboardPlayerWidget import TSHScoreboardPlayerWidget
from .TSHSelectSetWindow import TSHSelectSetWindow
from .TSHSelectStationWindow import TSHSelectStationWindow
from .TSHStatsUtil import TSHStatsUtil
from .TSHTheme import ThemedIcon
from .TSHTournamentDataProvider import TSHTournamentDataProvider

empty = {}


class QueueSetsCache:
    queue = []

    def UpdateQueue(self, q):
        self.queue = q

    def CheckQueue(self, q):
        logger.info("----------------- CHECKING QUEUES -------------------")
        if q is None:
            return False

        if len(self.queue) != len(q):
            return False

        for i in range(len(q)):
            savedSet = self.queue[i]
            incSet = q[i]

            if savedSet.get("id") != incSet.get("id"):
                return False

            if savedSet.get("state") != incSet.get("state"):
                return False

            savedSlots = savedSet.get("slots", [empty, empty])
            incSlots = incSet.get("slots", [empty, empty])

            if deep_get(savedSlots[0], "entrant.id") != deep_get(incSlots[0], "entrant.id"):
                return False

            if deep_get(savedSlots[1], "entrant.id") != deep_get(incSlots[1], "entrant.id"):
                return False

        logger.info("----------------- QUEUES CHECK OK -------------------")
        return True


class TSHScoreboardWidgetSignals(QObject):
    UpdateSetData = Signal(object)
    NewSetSelected = Signal(object)
    SetSelection = Signal()
    StreamSetSelection = Signal()
    StationSelection = Signal()
    StationSelected = Signal(object)
    StationSetsLoaded = Signal(object)
    CommandScoreChange = Signal(int, int)
    CommandTeamColor = Signal(int, str)
    SwapTeams = Signal()
    ChangeSetData = Signal(dict)
    # A different set was loaded, so its stage strike starts over
    NewSetLoaded = Signal()
    # The set on the scoreboard is over (reported here or finished on
    # start.gg), with its id
    SetFinished = Signal(object)


class TSHScoreboardWidget(QWidget):
    stationQueueCache = QueueSetsCache()

    def __init__(self, scoreboardNumber=1, *args):
        super().__init__(*args)

        self.scoreboardNumber = scoreboardNumber

        StateManager.Set(f"score.{self.scoreboardNumber}", {})
        StateManager.Set(f"score.{self.scoreboardNumber}.last_sets.1", {})
        StateManager.Set(f"score.{self.scoreboardNumber}.last_sets.2", {})
        StateManager.Set(f"score.{self.scoreboardNumber}.history_sets.1", {})
        StateManager.Set(f"score.{self.scoreboardNumber}.history_sets.2", {})
        StateManager.Set(f"score.{self.scoreboardNumber}.station_queue", {})

        self.signals = TSHScoreboardWidgetSignals()
        self.signals.UpdateSetData.connect(self.UpdateSetData)
        self.signals.NewSetSelected.connect(self.NewSetSelected)
        self.signals.StationSetsLoaded.connect(self.StationSetsLoaded)
        self.signals.SetSelection.connect(self.LoadSetClicked)
        self.signals.StationSelected.connect(self.LoadStationSets)
        self.signals.StationSelection.connect(self.LoadStationSetClicked)
        self.signals.ChangeSetData.connect(self.ChangeSetData)

        if self.scoreboardNumber == 1:
            TSHHotkeys.signals.load_set.connect(self.LoadSetClicked)
            TSHHotkeys.signals.swap_teams.connect(self.SwapTeams)
            TSHHotkeys.signals.reset_scores.connect(self.ResetScore)

            TSHHotkeys.signals.team1_score_up.connect(lambda: [self.CommandScoreChange(0, 1)])

            TSHHotkeys.signals.team1_score_down.connect(lambda: [self.CommandScoreChange(0, -1)])

            TSHHotkeys.signals.team2_score_up.connect(lambda: [self.CommandScoreChange(1, 1)])

            TSHHotkeys.signals.team2_score_down.connect(lambda: [self.CommandScoreChange(1, -1)])

        self.signals.CommandScoreChange.connect(self.CommandScoreChange)
        self.signals.SwapTeams.connect(self.SwapTeams)
        self.signals.CommandTeamColor.connect(self.CommandTeamColor)

        self.stats = TSHStatsUtil(self.scoreboardNumber, self)

        self.lastSetSelected = None

        self.lastStationSelected = None

        # The set (or stream/station/user selection) being auto updated
        self.autoUpdateData = None
        self.autoUpdateJob = f"scoreboard_{self.scoreboardNumber}_auto_update"
        TSHScheduler.instance.Register(
            self.autoUpdateJob,
            self.RunAutoUpdate,
            SettingsManager.Get(
                "general.scoreboard_auto_update_interval",
                SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
            )
            * 1000,
            SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS * 1000,
            group=SCOREBOARD_AUTO_UPDATE_GROUP,
        )
        TSHScheduler.instance.signals.job_state_changed.connect(self.AutoUpdateJobStateChanged)
        TSHScheduler.instance.signals.tick.connect(self.UpdateTimeLeftTimer)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setLayout(QVBoxLayout())

        self.innerWidget = QWidget()
        self.innerWidget.setLayout(QVBoxLayout())

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidget(self.innerWidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setStyleSheet("QTabWidget::pane { margin: 0px,0px,0px,0px }")

        # The scoreboard, and the games of its set
        self.innerTabs = QTabWidget()
        self.innerTabs.setDocumentMode(True)
        self.innerTabs.addTab(self.scrollArea, QApplication.translate("app", "Scoreboard"))
        self.layout().addWidget(self.innerTabs)

        topOptions = QWidget()
        topOptions.setLayout(QHBoxLayout())
        topOptions.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)

        self.innerWidget.layout().addWidget(topOptions)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        topOptions.layout().addWidget(col)
        self.charNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "Characters per player")))
        col.layout().addWidget(self.charNumber)
        self.charNumber.valueChanged.connect(self.SetCharacterNumber)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        topOptions.layout().addWidget(col)
        topOptions.layout().addStretch()
        self.playerNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "Players per team")))
        col.layout().addWidget(self.playerNumber)
        self.playerNumber.valueChanged.connect(self.SetPlayersPerTeam)

        # VISIBILITY
        col = QWidget()
        col.setLayout(QVBoxLayout())
        col.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        col.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        topOptions.layout().addWidget(col)

        self.eyeBt = QToolButton()
        self.eyeBt.setIcon(ThemedIcon("assets/icons/eye.svg"))
        self.eyeBt.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        col.layout().addWidget(self.eyeBt, Qt.AlignmentFlag.AlignRight)
        self.eyeBt.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu()
        self.eyeBt.setMenu(menu)

        menu.addSection("Players")

        self.elements = [
            [QApplication.translate("app", "Real Name"), ["real_name"], "show_name"],
            [QApplication.translate("app", "Twitter"), ["twitter", "twitterLabel"], "show_social"],
            [QApplication.translate("app", "Seed"), ["seed", "seedLabel"], "show_seed"],
            [QApplication.translate("app", "Birthday"), ["birthday"], "show_birthday"],
            [
                QApplication.translate("app", "Location"),
                ["locationLabel", "state", "country"],
                "show_location",
            ],
            [QApplication.translate("app", "Characters"), ["characters"], "show_characters"],
            [QApplication.translate("app", "Pronouns"), ["pronoun"], "show_pronouns"],
            [
                QApplication.translate("app", "Additional information"),
                ["custom_textbox"],
                "show_additional",
            ],
        ]
        for element in self.elements:
            action: QAction = self.eyeBt.menu().addAction(element[0])
            action.setCheckable(True)
            action.setChecked(SettingsManager.Get(f"display_options.{element[2]}", True))
            action.toggled.connect(
                lambda toggled, action=action, element=element: self.ToggleElements(
                    action, element[1]
                )
            )

        self.playerWidgets: list[TSHScoreboardPlayerWidget] = []
        self.team1playerWidgets: list[TSHScoreboardPlayerWidget] = []
        self.team2playerWidgets: list[TSHScoreboardPlayerWidget] = []

        self.team1swaps = []
        self.team2swaps = []

        self.columns = QWidget()
        self.columns.setLayout(QHBoxLayout())
        self.innerWidget.layout().addWidget(self.columns)

        bottomOptions = QWidget()
        bottomOptions.setLayout(QVBoxLayout())
        bottomOptions.layout().setContentsMargins(0, 0, 0, 0)
        bottomOptions.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)

        self.innerWidget.layout().addWidget(bottomOptions)

        self.btSelectSet = QPushButton(QApplication.translate("app", "Load set"))
        self.btSelectSet.setIcon(ThemedIcon("./assets/icons/list.svg"))
        self.btSelectSet.setEnabled(False)
        bottomOptions.layout().addWidget(self.btSelectSet)
        self.btSelectSet.clicked.connect(self.signals.SetSelection.emit)

        hbox = QHBoxLayout()
        bottomOptions.layout().addLayout(hbox)

        self.btLoadStationSet = QPushButton(
            QApplication.translate("app", "Track sets from a stream or station")
        )
        self.btLoadStationSet.setIcon(ThemedIcon("./assets/icons/station.svg"))
        hbox.addWidget(self.btLoadStationSet)
        self.btLoadStationSet.clicked.connect(self.signals.StationSelection.emit)

        self.remoteScoreboardLabel = QApplication.translate(
            "app", "Open {0} in a browser to edit the scoreboard remotely."
        ).format(
            f"<a href='http://{self.GetIP()}:{SettingsManager.Get('general.webserver_port', 5500)}/scoreboard'>http://{self.GetIP()}:{SettingsManager.Get('general.webserver_port', 5500)}/scoreboard</a>"
        )
        self.remoteScoreboardLabel = add_beta_label(self.remoteScoreboardLabel, "web_score")
        self.remoteScoreboardLabel = QLabel(self.remoteScoreboardLabel)

        self.remoteScoreboardLabel.setOpenExternalLinks(True)
        bottomOptions.layout().addWidget(self.remoteScoreboardLabel)

        TSHTournamentDataProvider.instance.signals.tournament_changed.connect(
            self.UpdateBottomButtons
        )
        TSHTournamentDataProvider.instance.signals.tournament_changed.emit()

        self.selectSetWindow = TSHSelectSetWindow(self)
        self.selectStationWindow = TSHSelectStationWindow(self)

        self.timerLayout = QWidget()
        self.timerLayout.setLayout(QHBoxLayout())
        self.timerLayout.layout().setContentsMargins(0, 0, 0, 0)
        self.timerLayout.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        self.timerLayout.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottomOptions.layout().addWidget(self.timerLayout)
        self.labelAutoUpdate = QLabel("Auto update")
        self.timerLayout.layout().addWidget(self.labelAutoUpdate)
        self.timerTime = QLabel("0")
        self.timerLayout.layout().addWidget(self.timerTime)
        self.timerCancelBt = QPushButton()
        self.timerCancelBt.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.timerCancelBt.setIconSize(QSize(12, 12))
        self.timerCancelBt.clicked.connect(lambda: self.StopAutoUpdate(clear_variables=True))
        self.timerLayout.layout().addWidget(self.timerCancelBt)
        self.timerLayout.setVisible(False)

        self.team1column = uic.loadUi(TSHResolve("src/layout/TSHScoreboardTeam.ui"))
        self.columns.layout().addWidget(self.team1column)
        self.team1column.findChild(QLabel, "teamLabel").setText(
            QApplication.translate("app", "TEAM {0}").format(1)
        )
        self.team1column.findChild(QLabel, "teamLabel").setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Minimum
        )

        colorGroup1 = QWidget()
        colorGroup1.setLayout(QHBoxLayout())
        colorGroup1.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        DEFAULT_TEAM1_COLOR = SettingsManager.Get("general.team_1_default_color", "#fe3636")
        self.colorButton1 = TSHColorButton(color=DEFAULT_TEAM1_COLOR)
        # self.colorButton1.setText(QApplication.translate("app", "COLOR"))
        self.colorButton1.colorChanged.connect(
            lambda color: StateManager.Set(f"score.{self.scoreboardNumber}.team.1.color", color)
        )
        self.CommandTeamColor(0, DEFAULT_TEAM1_COLOR)

        self.colorMenu1 = QComboBox()
        self.colorMenu1.setVisible(False)
        self.colorMenu1.setModel(TSHGameAssetManager.instance.colorModel)
        self.colorMenu1.setEditable(True)
        self.colorMenu1.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.colorMenu1.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.colorMenu1.setMaximumWidth(200)
        self.colorMenu1.setIconSize(QSize(24, 24))

        colorGroup1.layout().addWidget(self.colorButton1)
        colorGroup1.layout().addWidget(self.colorMenu1)

        self.colorMenu1.currentIndexChanged.connect(
            lambda element=self.colorMenu1: [
                self.CommandTeamColor(0, element),
                self.CommandTeamColor(1, element, force_opponent=True),
            ]
        )

        self.team1column.findChild(QHBoxLayout, "horizontalLayout_2").layout().insertWidget(
            0, colorGroup1
        )
        self.team1column.findChild(QScrollArea).setWidget(QWidget())
        self.team1column.findChild(QScrollArea).widget().setLayout(QVBoxLayout())

        for c in self.team1column.findChildren(QLineEdit):
            c.editingFinished.connect(
                lambda element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.team.1.{element.objectName()}",
                        element.text(),
                    )
                ]
            )
            c.editingFinished.emit()

        for c in self.team1column.findChildren(QCheckBox):
            c.toggled.connect(
                lambda state, element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.team.1.{element.objectName()}", state
                    )
                ]
            )
            c.toggled.emit(False)

        self.scoreColumn = uic.loadUi(TSHResolve("src/layout/TSHScoreboardScore.ui"))
        self.columns.layout().addWidget(self.scoreColumn)

        colorGroup2 = QWidget()
        colorGroup2.setLayout(QHBoxLayout())
        colorGroup2.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.team2column = uic.loadUi(TSHResolve("src/layout/TSHScoreboardTeam.ui"))
        self.columns.layout().addWidget(self.team2column)
        self.team2column.findChild(QLabel, "teamLabel").setText(
            QApplication.translate("app", "TEAM {0}").format(2)
        )
        self.team2column.findChild(QLabel, "teamLabel").setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Minimum
        )

        DEFAULT_TEAM2_COLOR = SettingsManager.Get("general.team_2_default_color", "#2e89ff")
        self.colorButton2 = TSHColorButton(color=DEFAULT_TEAM2_COLOR)
        self.colorButton2.colorChanged.connect(
            lambda color: StateManager.Set(f"score.{self.scoreboardNumber}.team.2.color", color)
        )
        # self.colorButton2.setText(QApplication.translate("app", "COLOR"))
        self.CommandTeamColor(1, DEFAULT_TEAM2_COLOR)

        self.colorMenu2 = QComboBox()
        self.colorMenu2.setVisible(False)
        self.colorMenu2.setModel(TSHGameAssetManager.instance.colorModel)
        self.colorMenu2.setEditable(True)
        self.colorMenu2.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.colorMenu2.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.colorMenu2.setMaximumWidth(200)
        self.colorMenu2.setIconSize(QSize(24, 24))

        colorGroup2.layout().addWidget(self.colorButton2)
        colorGroup2.layout().addWidget(self.colorMenu2)

        self.colorMenu2.currentIndexChanged.connect(
            lambda element=self.colorMenu2: [
                self.CommandTeamColor(1, element),
                self.CommandTeamColor(0, element, force_opponent=True),
            ]
        )

        self.team2column.findChild(QHBoxLayout, "horizontalLayout_2").layout().insertWidget(
            0, colorGroup2
        )

        self.team2column.findChild(QScrollArea).setWidget(QWidget())
        self.team2column.findChild(QScrollArea).widget().setLayout(QVBoxLayout())

        for c in self.team2column.findChildren(QLineEdit):
            c.editingFinished.connect(
                lambda element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.team.2.{element.objectName()}",
                        element.text(),
                    )
                ]
            )
            c.editingFinished.emit()

        for c in self.team2column.findChildren(QCheckBox):
            c.toggled.connect(
                lambda state, element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.team.2.{element.objectName()}", state
                    )
                ]
            )
            c.toggled.emit(False)

        StateManager.Unset(f"score.{self.scoreboardNumber}.team.1.player")
        StateManager.Unset(f"score.{self.scoreboardNumber}.team.2.player")
        StateManager.Unset(f"score.{self.scoreboardNumber}.stage_strike")
        self.playerNumber.setValue(1)
        self.charNumber.setValue(1)

        for c in self.scoreColumn.findChildren(QComboBox):
            c.lineEdit().editingFinished.connect(
                lambda element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.{element.objectName()}",
                        element.currentText(),
                    )
                ]
            )
            c.currentIndexChanged.connect(
                lambda x, element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.{element.objectName()}",
                        element.currentText(),
                    )
                ]
            )
            c.lineEdit().editingFinished.emit()
            c.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.colorMenu1.setVisible(StateManager.Get("game.has_colors", False))
        self.colorMenu2.setVisible(StateManager.Get("game.has_colors", False))

        # Sets that were over, so that's only told once per set
        self.finishedSets = set()
        # Set while data from start.gg is applied, so it isn't taken for
        # changes made here
        self.applyingProviderData = False

        # Games of the set, and reporting it to start.gg
        self.gameReport = TSHGameReportWidget(self)
        self.gameReport.signals.scoreChanged.connect(self.StageResultsToScore)
        self.gameReport.signals.setReported.connect(self.SetOver)
        self.innerTabs.addTab(self.gameReport, QApplication.translate("app", "Games"))

        self.scoreColumn.findChild(QSpinBox, "best_of").valueChanged.connect(self.ExportBestOf)
        self.scoreColumn.findChild(QSpinBox, "best_of").valueChanged.emit(0)

        self.scoreColumn.findChild(QSpinBox, "score_left").valueChanged.connect(
            lambda value: [
                StateManager.Set(f"score.{self.scoreboardNumber}.team.1.score", value),
                self.gameReport.ScoreChanged(0, value),
            ]
        )
        self.scoreColumn.findChild(QSpinBox, "score_left").valueChanged.emit(0)

        self.scoreColumn.findChild(QSpinBox, "score_right").valueChanged.connect(
            lambda value: [
                StateManager.Set(f"score.{self.scoreboardNumber}.team.2.score", value),
                self.gameReport.ScoreChanged(1, value),
            ]
        )
        self.scoreColumn.findChild(QSpinBox, "score_right").valueChanged.emit(0)

        self.team1column.findChild(QLineEdit, "teamName").editingFinished.connect(
            lambda: [
                self.ExportTeamLogo("1", self.team1column.findChild(QLineEdit, "teamName").text()),
                self.ExportLosersStatus(
                    "1",
                    self.team1column.findChild(QLineEdit, "teamName").text(),
                    self.team1column.findChild(QCheckBox, "losers").isChecked(),
                ),
            ]
        )
        self.team2column.findChild(QLineEdit, "teamName").editingFinished.connect(
            lambda: [
                self.ExportTeamLogo("2", self.team2column.findChild(QLineEdit, "teamName").text()),
                self.ExportLosersStatus(
                    "2",
                    self.team2column.findChild(QLineEdit, "teamName").text(),
                    self.team2column.findChild(QCheckBox, "losers").isChecked(),
                ),
            ]
        )

        self.teamsSwapped = False

        self.scoreColumn.findChild(QPushButton, "btSwapTeams").clicked.connect(self.SwapTeams)
        self.scoreColumn.findChild(QPushButton, "btSwapTeams").setIcon(
            ThemedIcon("assets/icons/swap.svg")
        )

        self.scoreColumn.findChild(QPushButton, "btResetScore").clicked.connect(
            lambda: [
                self.ResetScore(),
                self.scoreColumn.findChild(QSpinBox, "best_of").valueChanged.emit(
                    self.scoreColumn.findChild(QSpinBox, "best_of").value()
                ),
            ]
        )
        self.scoreColumn.findChild(QPushButton, "btResetScore").setIcon(
            ThemedIcon("assets/icons/undo.svg")
        )

        # Add default and user tournament phase title files
        self.scoreColumn.findChild(QComboBox, "phase").addItem("")
        TSHLocaleHelper.LoadPhaseNamesToWidget(self.scoreColumn.findChild(QComboBox, "phase"))

        self.scoreColumn.findChild(QComboBox, "match").addItem("")
        TSHLocaleHelper.LoadMatchNamesToWidget(self.scoreColumn.findChild(QComboBox, "match"))

        TSHGameAssetManager.instance.signals.onLoad.connect(
            lambda: [
                self.SetDefaultsFromAssets(),
                self.scoreColumn.findChild(QSpinBox, "best_of").valueChanged.emit(
                    self.scoreColumn.findChild(QSpinBox, "best_of").value()
                ),
                self.colorMenu1.setModel(TSHGameAssetManager.instance.colorModel),
                self.colorMenu2.setModel(TSHGameAssetManager.instance.colorModel),
                self.colorMenu1.setVisible(StateManager.Get("game.has_colors", False)),
                self.colorMenu2.setVisible(StateManager.Get("game.has_colors", False)),
            ]
        )

    def ExportBestOf(self, value):
        with StateManager.SaveBlock():
            StateManager.Set(f"score.{self.scoreboardNumber}.best_of", value)
            StateManager.Set(f"score.{self.scoreboardNumber}.best_of_short_text", f"BO{value}")
            StateManager.Set(
                f"score.{self.scoreboardNumber}.best_of_text",
                TSHLocaleHelper.matchNames.get("best_of").format(value) if value > 0 else "",
            )
            StateManager.Set(f"score.{self.scoreboardNumber}.first_to", math.ceil(value / 2))
            StateManager.Set(
                f"score.{self.scoreboardNumber}.first_to_short_text", f"FT{math.ceil(value / 2)}"
            )
            StateManager.Set(
                f"score.{self.scoreboardNumber}.first_to_text",
                TSHLocaleHelper.matchNames.get("first_to").format(math.ceil(value / 2))
                if value > 0
                else "",
            )
            self.gameReport.SetBestOf(value)

    def StageResultsToScore(self, team_1_score, team_2_score):
        with QSignalBlocker(self.scoreColumn.findChild(QSpinBox, "score_left")):
            self.scoreColumn.findChild(QSpinBox, "score_left").setValue(team_1_score)
            StateManager.Set(f"score.{self.scoreboardNumber}.team.1.score", team_1_score)

        with QSignalBlocker(self.scoreColumn.findChild(QSpinBox, "score_right")):
            self.scoreColumn.findChild(QSpinBox, "score_right").setValue(team_2_score)
            StateManager.Set(f"score.{self.scoreboardNumber}.team.2.score", team_2_score)

    def closeEvent(self, event):
        TSHScheduler.instance.Stop(self.autoUpdateJob)

    def RemoveAutoUpdate(self):
        """Called before the scoreboard is deleted, so its job doesn't keep
        running for a widget that no longer exists."""
        self.autoUpdateData = None
        TSHScheduler.instance.signals.job_state_changed.disconnect(self.AutoUpdateJobStateChanged)
        TSHScheduler.instance.signals.tick.disconnect(self.UpdateTimeLeftTimer)
        TSHScheduler.instance.Unregister(self.autoUpdateJob)

    def ExportTeamLogo(self, team, value):
        if os.path.exists(f"./user_data/team_logo/{value.lower()}.png"):
            StateManager.Set(
                f"score.{self.scoreboardNumber}.team.{team}.logo",
                f"./user_data/team_logo/{value.lower()}.png",
            )
        else:
            StateManager.Set(f"score.{self.scoreboardNumber}.team.{team}.logo", None)

    def ExportLosersStatus(self, team, team_name, is_in_losers):
        merged_team_name = deepcopy(team_name)
        if (
            not team_name
        ):  # If no manually set team name, add generated team name based on player names
            players = StateManager.Get(f"score.{self.scoreboardNumber}.team.{team}.player", {})
            player_names = []
            players_names_only = []
            for index in players.keys():
                if players[index].get("name", ""):
                    players_names_only.append(players[index].get("name", ""))
                    if players[index].get("team"):
                        player_names.append(
                            f"{players[index].get('team', '')} | {players[index].get('name', '')}"
                        )
                    else:
                        player_names.append(players[index].get("name", ""))
            if (
                len(player_names) >= 2
            ):  # If the team has 2 players or more, only export the names of the players in the team name
                merged_team_name = " / ".join(players_names_only)
            else:
                merged_team_name = " / ".join(player_names)
        losers_indicator = ""
        if is_in_losers:
            losers_indicator = "[L]"
            merged_team_name = merged_team_name + " " + losers_indicator
        StateManager.Set(
            f"score.{self.scoreboardNumber}.team.{team}.mergedTeamName", merged_team_name
        )
        StateManager.Set(
            f"score.{self.scoreboardNumber}.team.{team}.losersIndicator", losers_indicator
        )

    def ToggleElements(self, action: QAction, elements):
        for pw in self.playerWidgets:
            for element in elements:
                pw.findChild(QWidget, element).setVisible(action.isChecked())

    def UpdateBottomButtons(self):
        if (
            TSHTournamentDataProvider.instance.provider
            and TSHTournamentDataProvider.instance.provider.url
        ):
            self.btSelectSet.setText(
                QApplication.translate("app", "Load set from {0}").format(
                    TSHTournamentDataProvider.instance.provider.url
                )
            )
            self.btSelectSet.setEnabled(True)
            self.btLoadStationSet.setEnabled(True)
        else:
            self.btSelectSet.setText(QApplication.translate("app", "Load set"))
            self.btSelectSet.setEnabled(False)
            self.btLoadStationSet.setEnabled(False)

    def SetCharacterNumber(self, value):
        # logger.info(f"TSHScoreboardWidget#SetCharacterNumber({value})")
        for pw in self.playerWidgets:
            pw.SetCharactersPerPlayer(value)

    def ConnectLosersStatus(self, p, team, teamColumn):
        # Connected once per player widget: connecting every existing player
        # on each call made the export run several times per edit
        for field in ("name", "team"):
            p.findChild(QLineEdit, field).editingFinished.connect(
                lambda: self.ExportLosersStatus(
                    team,
                    teamColumn.findChild(QLineEdit, "teamName").text(),
                    teamColumn.findChild(QCheckBox, "losers").isChecked(),
                )
            )

    def SetPlayersPerTeam(self, number):
        # logger.info(f"TSHScoreboardWidget#SetPlayersPerTeam({number})")
        while len(self.team1playerWidgets) < number:
            p = TSHScoreboardPlayerWidget(
                index=len(self.team1playerWidgets) + 1,
                teamNumber=1,
                path=f"score.{self.scoreboardNumber}.team.{1}.player.{len(self.team1playerWidgets) + 1}",
            )
            self.playerWidgets.append(p)

            self.team1column.findChild(QScrollArea).widget().layout().addWidget(p)
            p.SetCharactersPerPlayer(self.charNumber.value())
            self.team1column.findChild(QCheckBox, "losers").toggled.connect(
                lambda: [
                    p.SetLosers,
                    self.ExportLosersStatus(
                        "1",
                        self.team1column.findChild(QLineEdit, "teamName").text(),
                        self.team1column.findChild(QCheckBox, "losers").isChecked(),
                    ),
                ]
            )

            p.btMoveUp.clicked.connect(
                lambda index, p=p: p.SwapWith(
                    self.team1playerWidgets[max(0, self.team1playerWidgets.index(p) - 1)]
                )
            )
            p.btMoveDown.clicked.connect(
                lambda index, p=p: p.SwapWith(
                    self.team1playerWidgets[
                        min(len(self.team1playerWidgets) - 1, self.team1playerWidgets.index(p) + 1)
                    ]
                )
            )

            p.instanceSignals.playerId_changed.connect(self.stats.signals.RecentSetsSignal.emit)
            p.instanceSignals.player1Id_changed.connect(self.stats.signals.LastSetsP1Signal.emit)
            p.instanceSignals.player1Id_changed.connect(
                self.stats.signals.PlayerHistoryStandingsP1Signal.emit
            )
            p.instanceSignals.player_seed_changed.connect(
                self.stats.signals.UpsetFactorCalculation.emit
            )
            self.ConnectLosersStatus(p, "1", self.team1column)

            self.team1playerWidgets.append(p)

            p = TSHScoreboardPlayerWidget(
                index=len(self.team2playerWidgets) + 1,
                teamNumber=2,
                path=f"score.{self.scoreboardNumber}.team.{2}.player.{len(self.team2playerWidgets) + 1}",
            )
            self.playerWidgets.append(p)

            self.team2column.findChild(QScrollArea).widget().layout().addWidget(p)
            p.SetCharactersPerPlayer(self.charNumber.value())
            self.team2column.findChild(QCheckBox, "losers").toggled.connect(
                lambda: [
                    p.SetLosers,
                    self.ExportLosersStatus(
                        "2",
                        self.team2column.findChild(QLineEdit, "teamName").text(),
                        self.team2column.findChild(QCheckBox, "losers").isChecked(),
                    ),
                ]
            )

            p.btMoveUp.clicked.connect(
                lambda index, p=p: p.SwapWith(
                    self.team2playerWidgets[max(0, self.team2playerWidgets.index(p) - 1)]
                )
            )
            p.btMoveDown.clicked.connect(
                lambda index, p=p: p.SwapWith(
                    self.team2playerWidgets[
                        min(len(self.team2playerWidgets) - 1, self.team2playerWidgets.index(p) + 1)
                    ]
                )
            )

            p.instanceSignals.playerId_changed.connect(self.stats.signals.RecentSetsSignal.emit)
            p.instanceSignals.player2Id_changed.connect(self.stats.signals.LastSetsP2Signal.emit)
            p.instanceSignals.player2Id_changed.connect(
                self.stats.signals.PlayerHistoryStandingsP2Signal.emit
            )
            p.instanceSignals.player_seed_changed.connect(
                self.stats.signals.UpsetFactorCalculation.emit
            )
            self.ConnectLosersStatus(p, "2", self.team2column)

            self.team2playerWidgets.append(p)

        while len(self.team1playerWidgets) > number:
            team1player = self.team1playerWidgets[-1]
            StateManager.Unset(team1player.path)
            team1player.setParent(None)
            self.playerWidgets.remove(team1player)
            self.team1playerWidgets.remove(team1player)
            team1player.deleteLater()

            team2player = self.team2playerWidgets[-1]
            StateManager.Unset(team2player.path)
            team2player.setParent(None)
            self.playerWidgets.remove(team2player)
            self.team2playerWidgets.remove(team2player)
            team2player.deleteLater()

        for team in [1, 2]:
            if StateManager.Get(f"score.{self.scoreboardNumber}.team.{team}"):
                for k in list(
                    StateManager.Get(f"score.{self.scoreboardNumber}.team.{team}.player").keys()
                ):
                    if int(k) > number:
                        StateManager.Unset(f"score.{self.scoreboardNumber}.team.{team}.player.{k}")

        if number > 1:
            self.team1column.findChild(QLineEdit, "teamName").setVisible(True)
            self.team2column.findChild(QLineEdit, "teamName").setVisible(True)
            self.team1column.findChild(QLabel, "teamLabel").setVisible(False)
            self.team2column.findChild(QLabel, "teamLabel").setVisible(False)
        else:
            self.team1column.findChild(QLineEdit, "teamName").setVisible(False)
            self.team1column.findChild(QLineEdit, "teamName").setText("")
            self.team1column.findChild(QLineEdit, "teamName").editingFinished.emit()
            self.team2column.findChild(QLineEdit, "teamName").setVisible(False)
            self.team2column.findChild(QLineEdit, "teamName").setText("")
            self.team2column.findChild(QLineEdit, "teamName").editingFinished.emit()
            self.team1column.findChild(QLabel, "teamLabel").setVisible(True)
            self.team2column.findChild(QLabel, "teamLabel").setVisible(True)

        for x, element in enumerate(self.elements, start=1):
            action: QAction = self.eyeBt.menu().actions()[x]
            self.ToggleElements(action, element[1])

    def SwapTeams(self):
        # Lock all player widgets
        for p in self.playerWidgets:
            p.dataLock.acquire()

        # BlockSaving() lives inside the try so that the finally below always
        # releases it, even if one of the calls in between raises.
        try:
            StateManager.BlockSaving()

            # The players' stats are swapped below instead of being fetched
            # again from start.gg for both players
            for i, p in enumerate(self.team1playerWidgets):
                p.SwapWith(self.team2playerWidgets[i], emitIdChanged=False)
            self.SwapStats()

            # Scores. Signals are blocked because each score change would
            # make the games tab add/remove wins (and rebuild itself), losing
            # which games were won; gameReport.Swap() below swaps them as is.
            scoreLeft = self.scoreColumn.findChild(QSpinBox, "score_left").value()
            scoreRight = self.scoreColumn.findChild(QSpinBox, "score_right").value()
            self.StageResultsToScore(scoreRight, scoreLeft)

            # Losers
            losersLeft = self.team1column.findChild(QCheckBox, "losers").isChecked()
            self.team1column.findChild(QCheckBox, "losers").setChecked(
                self.team2column.findChild(QCheckBox, "losers").isChecked()
            )
            self.team2column.findChild(QCheckBox, "losers").setChecked(losersLeft)

            # Team Names
            teamNameLeft = self.team1column.findChild(QLineEdit, "teamName").text()
            self.team1column.findChild(QLineEdit, "teamName").setText(
                self.team2column.findChild(QLineEdit, "teamName").text()
            )
            self.team2column.findChild(QLineEdit, "teamName").setText(teamNameLeft)
            self.team1column.findChild(QLineEdit, "teamName").editingFinished.emit()
            self.team2column.findChild(QLineEdit, "teamName").editingFinished.emit()

            self.gameReport.Swap()
            self.teamsSwapped = not self.teamsSwapped
        finally:
            StateManager.Set(f"score.{self.scoreboardNumber}.teamsSwapped", self.teamsSwapped)

            for p in self.playerWidgets:
                p.dataLock.release()

            StateManager.ReleaseSaving()

    def SwapStats(self):
        """Swap the teams' player stats, which don't change when they swap."""
        base = f"score.{self.scoreboardNumber}"

        for key in ("last_sets", "history_sets"):
            stats1 = StateManager.Get(f"{base}.{key}.1")
            stats2 = StateManager.Get(f"{base}.{key}.2")
            if stats1 is None and stats2 is None:
                continue
            for team, stats in (("1", stats2), ("2", stats1)):
                if stats is None:
                    StateManager.Unset(f"{base}.{key}.{team}")
                else:
                    StateManager.Set(f"{base}.{key}.{team}", stats)

        recentSets = StateManager.Get(f"{base}.recent_sets")
        if recentSets and recentSets.get("state") == "done":
            # Head to head sets are from team 1's side: mirror them
            sets = []
            for s in recentSets.get("sets") or []:
                s = dict(s)
                if isinstance(s.get("score"), list):
                    s["score"] = list(reversed(s["score"]))
                if s.get("winner") in (0, 1):
                    s["winner"] = 1 - s["winner"]
                if "p1_char" in s or "p2_char" in s:
                    s["p1_char"], s["p2_char"] = s.get("p2_char"), s.get("p1_char")
                sets.append(s)
            StateManager.Set(f"{base}.recent_sets", dict(recentSets, sets=sets))
        elif recentSets:
            # Still loading for the old order, ask again for the new one
            self.stats.signals.RecentSetsSignal.emit()

    def ResetScore(self):
        self.scoreColumn.findChild(QSpinBox, "score_left").setValue(0)
        self.scoreColumn.findChild(QSpinBox, "score_right").setValue(0)

    def RunAutoUpdate(self, done):
        data = self.autoUpdateData or {}

        # done() once every request started below has finished, so the next
        # update can't start while this one is still loading. Starts at 1 so
        # a request finishing immediately can't call it before the others
        # are started.
        pending = [1]

        def finished():
            pending[0] -= 1
            if pending[0] == 0:
                done()

        def track():
            pending[0] += 1
            return finished

        TSHTournamentDataProvider.instance.GetMatch(
            self, data.get("id"), overwrite=False, on_finished=track()
        )

        if data.get("auto_update") in ("stream", "station"):
            TSHTournamentDataProvider.instance.LoadStationSets(self, on_finished=track())

        finished()

    def StationSetsLoaded(self, data):
        # Ici peut être lancer le chargement des sets voire même trigger un autre signal ?

        logger.info("STATION SETS LOADED -----------------------------")
        logger.info(data)

        StateManager.Set(f"score.{self.scoreboardNumber}.station_queue", data)

    def NewSetSelected(self, data):
        autoUpdate = not SettingsManager.Get("general.disable_autoupdate", False)
        if autoUpdate:
            self.autoUpdateData = data
            if data.get("id") != None and data.get("id") != self.lastSetSelected:
                # Updates start once the new set has loaded (see below), so
                # they can't overlap its first load
                TSHScheduler.instance.Stop(self.autoUpdateJob)
            else:
                # In stream/station mode, every update selects the set
                # again. Then the job is still running, so this only updates
                # what the next run loads. Otherwise it restarts the countdown.
                TSHScheduler.instance.Start(self.autoUpdateJob)
            self.timerLayout.setVisible(True)

            if data.get("auto_update") == "set":
                self.labelAutoUpdate.setText(QApplication.translate("app", "Auto update (Set)"))
            elif data.get("auto_update") == "stream":
                self.labelAutoUpdate.setText(
                    QApplication.translate("app", "Auto update (Stream [{0}])").format(
                        self.lastStationSelected.get("identifier")
                    )
                )
            elif data.get("auto_update") == "station":
                self.labelAutoUpdate.setText(
                    QApplication.translate("app", "Auto update (Station [{0}])").format(
                        self.lastStationSelected.get("identifier")
                    )
                )
            else:
                self.labelAutoUpdate.setText(QApplication.translate("app", "Auto update"))

        newSet = False

        # Lock all player widgets
        for p in self.playerWidgets:
            p.dataLock.acquire()

        # BlockSaving() lives inside the try so that the finally below always
        # releases it, even if one of the calls in between raises.
        try:
            StateManager.BlockSaving()

            if data.get("id") != None and data.get("id") != self.lastSetSelected:
                no_mains = data.get("no_mains")
                if no_mains is None:
                    no_mains = SettingsManager.Get("general.force_no_mains_on_new_set_loads", False)

                # Clear previous scores
                # Important because when we receive scores as 0 we don't update based on that
                # Otherwise an offline set which is only updated after it's complete would reset the score
                # all the time since it would be 0-0 until then
                self.CommandClearAll(no_mains=no_mains)
                self.ClearScore()

                # A new set was loaded
                self.lastSetSelected = data.get("id")
                newSet = True

                # Clear stage strike data
                StateManager.Unset(f"score.{self.scoreboardNumber}.stage_strike")

                # Add general set data to object: id, auto update type, station/stream identifier, etc
                StateManager.Set(f"score.{self.scoreboardNumber}.set_id", data.get("id"))
                self.gameReport.NewSet(data.get("id"))

                StateManager.Set(
                    f"score.{self.scoreboardNumber}.auto_update", data.get("auto_update")
                )

                if self.lastStationSelected:
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.station",
                        self.lastStationSelected.get("identifier"),
                    )
                else:
                    StateManager.Set(f"score.{self.scoreboardNumber}.station", None)

                TSHTournamentDataProvider.instance.GetMatch(
                    self,
                    data["id"],
                    overwrite=True,
                    no_mains=no_mains,
                    on_finished=(lambda: self.StartAutoUpdateAfterLoad(data))
                    if autoUpdate
                    else None,
                )
        finally:
            for p in self.playerWidgets:
                p.dataLock.release()
            StateManager.ReleaseSaving()

        if newSet:
            self.signals.NewSetLoaded.emit()

    def StartAutoUpdateAfterLoad(self, data):
        # Unless another set was selected or auto update was stopped meanwhile
        if self.autoUpdateData is data:
            TSHScheduler.instance.Start(self.autoUpdateJob)

    def StopAutoUpdate(self, clear_variables=False):
        self.autoUpdateData = None
        TSHScheduler.instance.Stop(self.autoUpdateJob)

        if clear_variables:
            self.lastSetSelected = None
            self.lastStationSelected = None

            StateManager.Set(f"score.{self.scoreboardNumber}.auto_update", None)
            StateManager.Set(f"score.{self.scoreboardNumber}.set_id", None)
            StateManager.Set(f"score.{self.scoreboardNumber}.station", None)
            self.gameReport.NewSet(None)

        self.timerLayout.setVisible(False)

    def AutoUpdateJobStateChanged(self, name):
        if name == self.autoUpdateJob:
            self.UpdateTimeLeftTimer()

    def UpdateTimeLeftTimer(self):
        # None while an update or a newly selected set is loading
        remaining = TSHScheduler.instance.RemainingMs(self.autoUpdateJob)
        self.timerTime.setText(str(math.ceil(remaining / 1000) if remaining is not None else 0))

    def LoadSetClicked(self):
        self.selectSetWindow.LoadSets()
        self.selectSetWindow.show()

    def LoadStationSets(self, station):
        self.lastSetSelected = None
        self.lastStationSelected = station
        TSHTournamentDataProvider.instance.LoadStationSets(self)

    def LoadStationSetClicked(self):
        self.selectStationWindow.LoadStations()
        self.selectStationWindow.show()

    # Used for score change commands
    # Change <team>(0, 1) score by <change>(+X, -X)
    def CommandScoreChange(self, team: int, change: int):
        if team in (0, 1):
            scoreContainers = [
                self.scoreColumn.findChild(QSpinBox, "score_left"),
                self.scoreColumn.findChild(QSpinBox, "score_right"),
            ]
            scoreContainers[team].setValue(scoreContainers[team].value() + change)

    def CommandClearAll(self, no_mains=False):
        for t, team in enumerate([self.team1playerWidgets, self.team2playerWidgets]):
            for i, p in enumerate(team):
                p.Clear(no_mains)
        self.lastSetSelected = None

    # Sets a team's name, losers state and color from the web API.
    # <team>(0, 1) is the side on screen, like CommandScoreChange
    def CommandTeamInfo(self, team: int, data):
        if team not in (0, 1):
            return
        column = [self.team1column, self.team2column][team]
        if data.get("name") is not None:
            teamName = column.findChild(QLineEdit, "teamName")
            teamName.setText(str(data.get("name")))
            teamName.editingFinished.emit()
        if data.get("losers") is not None:
            column.findChild(QCheckBox, "losers").setChecked(bool(data.get("losers")))
        if data.get("color"):
            self.CommandTeamColor(team, data.get("color"))

    def ClearScore(self):
        for c in self.scoreColumn.findChildren(QComboBox):
            c.setCurrentText("")
            c.lineEdit().editingFinished.emit()

        self.scoreColumn.findChild(QSpinBox, "score_left").setValue(0)
        self.scoreColumn.findChild(QSpinBox, "score_right").setValue(0)

        self.team1column.findChild(QCheckBox, "losers").setChecked(False)
        self.team2column.findChild(QCheckBox, "losers").setChecked(False)

    def CommandTeamColor(self, team: int, color, force_opponent=False):
        if color:
            value = None
            if type(color) is str:
                value = color
            if type(color) is int and color > 0:
                value = TSHGameAssetManager.instance.colorModel.item(color).data(
                    Qt.ItemDataRole.UserRole
                )
                if force_opponent:
                    value = value.get("force_opponent")
                else:
                    value = value.get("value")
                if value:
                    value = "#" + value

            if value:
                if team == 0:
                    self.colorButton1.setColor(value)
                if team == 1:
                    self.colorButton2.setColor(value)
                if team in (0, 1):
                    StateManager.Set(f"score.{self.scoreboardNumber}.team.{team + 1}.color", value)

                # Set in menu if recognized
                if type(color) is int and force_opponent:
                    for i in range(1, TSHGameAssetManager.instance.colorModel.rowCount()):
                        current_menu_item_data = TSHGameAssetManager.instance.colorModel.item(
                            i
                        ).data(Qt.ItemDataRole.UserRole)
                        if current_menu_item_data.get("value") in value:
                            if team == 0:
                                self.colorMenu1.setCurrentIndex(i)
                            if team == 1:
                                self.colorMenu2.setCurrentIndex(i)

    # Modifies the current set data. Does not check for id, so do not call this with data that may lead to another hbox incident
    #
    # team1/team2 values (scores, losers) are the set's entrants, so they go
    # to the opposite sides while the teams are swapped. Data with
    # "as_displayed" set (sent by hand from the web API / remote scoreboard)
    # is already in on-screen order: team 1 is the left side.
    def ChangeSetData(self, data):
        asDisplayed = bool(data.get("as_displayed"))
        reverseTeams = self.teamsSwapped and not asDisplayed

        # BlockSaving() lives inside the try so that the finally below always
        # releases it, even if one of the calls in between raises.
        try:
            StateManager.BlockSaving()

            StateManager.Set(f"score.{self.scoreboardNumber}.phase_size", data.get("numSeeds"))
            StateManager.Set(f"score.{self.scoreboardNumber}.num_groups", data.get("groupCount"))
            StateManager.Set(f"score.{self.scoreboardNumber}.round", data.get("round"))

            round_name = data.get("round_name")
            if round_name:
                self.scoreColumn.findChild(QComboBox, "match").setCurrentText(round_name)
                self.scoreColumn.findChild(QComboBox, "match").lineEdit().editingFinished.emit()
                StateManager.Set(f"score.{self.scoreboardNumber}.match", round_name)

            tournament_phase = data.get("tournament_phase")
            if tournament_phase:
                # Is this Top 16 - Top ??? (even 128), if so...
                # check if this isn't pools and isn't a qualifier
                round_division = data.get("roundDivision", 0)
                if round_division:
                    if data.get("isPools", False) is False:
                        phase = tournament_phase
                        original_str = tournament_phase.split(" - ")
                        if round_division > 4:
                            tournament_phase = TSHLocaleHelper.phaseNames.get(
                                "top_n", "Top {0}"
                            ).format(round_division)
                        elif round_division <= 4:
                            tournament_phase = TSHLocaleHelper.phaseNames.get(
                                "top_n", "Top {0}"
                            ).format(4)

                        # Include "Bracket - XYZ" similar to if it's Pools
                        if len(original_str) > 1:
                            tournament_phase = f"{original_str[0]} - {tournament_phase}"
                        elif "Top" not in phase:
                            tournament_phase = f"{phase} - {tournament_phase}"

                self.scoreColumn.findChild(QComboBox, "phase").setCurrentText(tournament_phase)
                self.scoreColumn.findChild(QComboBox, "phase").lineEdit().editingFinished.emit()
                StateManager.Set(f"score.{self.scoreboardNumber}.phase", tournament_phase)

            scoreContainers = [
                self.scoreColumn.findChild(QSpinBox, "score_left"),
                self.scoreColumn.findChild(QSpinBox, "score_right"),
            ]
            if reverseTeams:
                scoreContainers.reverse()

            if data.get("reset_score"):
                scoreContainers[0].setValue(0)
                scoreContainers[1].setValue(0)
            # The setting only turns off automatic updates, not scores set by hand
            if asDisplayed or not SettingsManager.Get("general.disable_scoreupdate", False):
                if data.get("team1score") is not None:
                    if data.get("team1score") != 0:
                        scoreContainers[0].setValue(data.get("team1score"))
                    else:
                        scoreContainers[0].setValue(0)
                if data.get("team2score") is not None:
                    if data.get("team2score") != 0:
                        scoreContainers[1].setValue(data.get("team2score"))
                    else:
                        scoreContainers[1].setValue(0)

            if data.get("bestOf"):
                self.scoreColumn.findChild(QSpinBox, "best_of").setValue(data.get("bestOf"))

            losersContainers = [
                self.team1column.findChild(QCheckBox, "losers"),
                self.team2column.findChild(QCheckBox, "losers"),
            ]
            if reverseTeams:
                losersContainers.reverse()

            if data.get("team1losers") is not None:
                losersContainers[0].setChecked(data.get("team1losers"))
            if data.get("team2losers") is not None:
                losersContainers[1].setChecked(data.get("team2losers"))

            if data.get("entrants"):
                self.playerNumber.setValue(len(max(data.get("entrants"), key=lambda x: len(x))))

                # Lock all player widgets
                for p in self.playerWidgets:
                    p.dataLock.acquire()

                try:
                    for t, team in enumerate(data.get("entrants")):
                        teamInstances = [self.team1playerWidgets, self.team2playerWidgets]
                        if self.teamsSwapped:
                            teamInstances.reverse()

                        if t >= len(teamInstances):
                            logger.warning(
                                f"Entrant team index {t} out of range (max {len(teamInstances)})"
                            )
                            break

                        teamInstance = teamInstances[t]

                        if len(team) > 1:
                            teamColumns = [self.team1column, self.team2column]
                            teamNames = [data.get("p1_name"), data.get("p2_name")]
                            if self.teamsSwapped:
                                teamNames.reverse()
                            teamColumns[t].findChild(QLineEdit, "teamName").setText(teamNames[t])
                            teamColumns[t].findChild(QLineEdit, "teamName").editingFinished.emit()

                        for p, player in enumerate(team):
                            if p >= len(teamInstance):
                                logger.warning(
                                    f"Player index {p} out of range for team {t + 1} (max {len(teamInstance)})"
                                )
                                break
                            if data.get("overwrite"):
                                teamInstance[p].SetData(
                                    player,
                                    False,
                                    True,
                                    data.get("no_mains") if data.get("no_mains") != None else False,
                                )
                            if data.get("has_selection_data") and data.get("no_mains") != True:
                                player = {"mains": player.get("mains")}
                                teamInstance[p].SetData(player, True, False)
                except Exception as e:
                    logger.error(f"Error while setting entrants: {e}")
                finally:
                    for p in self.playerWidgets:
                        p.dataLock.release()
            else:
                try:
                    # Lock all player widgets
                    for p in self.playerWidgets:
                        p.dataLock.acquire()

                    if not data.get("team") or not data.get("player"):
                        return

                    team = int(data.get("team")) - 1
                    player = int(data.get("player")) - 1

                    teamInstances = [self.team1playerWidgets, self.team2playerWidgets]

                    if team >= len(teamInstances):
                        logger.warning(
                            f"Team index {team + 1} out of range (max {len(teamInstances)})"
                        )
                        return

                    teamInstance = teamInstances[team]

                    if player >= len(teamInstance):
                        logger.warning(
                            f"Player index {player + 1} out of range for team {team + 1} (max {len(teamInstance)})"
                        )
                        return

                    teamInstance[player].SetData(data.get("data"), False, False)
                    if data.get("data", {}).get("savePlayerToDb", False):
                        teamInstance[player].SavePlayerToDB()
                except Exception as e:
                    logger.error(f"Error while setting entrants: {e}")
                finally:
                    for p in self.playerWidgets:
                        p.dataLock.release()

            if data.get("stage_strike"):
                StateManager.Set(
                    f"score.{self.scoreboardNumber}.stage_strike", data.get("stage_strike")
                )
                StateManager.Set(f"score.{self.scoreboardNumber}.ruleset", data.get("ruleset"))
                if self.scoreboardNumber == 1:
                    StateManager.Set("score.ruleset", data.get("ruleset"))

            if data.get("bracket_type"):
                StateManager.Set("score.bracket_type", data.get("bracket_type"))
                self.stats.signals.UpsetFactorCalculation.emit()

            if data.get("top_n"):
                StateManager.Set(f"score.{self.scoreboardNumber}.top_n", data.get("top_n"))
        finally:
            StateManager.ReleaseSaving()

    def UpdateSetData(self, data):
        # Do not update the scoreboard on empty data
        if data is None or len(data) == 0 or data.get("id") == None:
            return

        # If you switched sets and it was still finishing an async update call
        # Avoid loading data from the previous set
        if str(data.get("id")) != str(self.lastSetSelected):
            return

        if self.gameReport.HoldProviderResults():
            # The score here is ahead of start.gg's (games being reported)
            data = dict(data)
            data.pop("team1score", None)
            data.pop("team2score", None)

        self.applyingProviderData = True
        try:
            self.ChangeSetData(data)
            self.gameReport.ApplySetData(data)
        finally:
            self.applyingProviderData = False

        # Finished on start.gg
        if data.get("state") == 3:
            self.SetOver(data.get("id"))

    def SetOver(self, setId):
        if setId is None or str(setId) in self.finishedSets:
            return
        self.finishedSets.add(str(setId))
        self.signals.SetFinished.emit(setId)

    def LoadPlayerFromTag(self, tag, team, player, no_mains=False):
        team = int(team) - 1
        player = int(player) - 1
        teamInstances = [self.team1playerWidgets, self.team2playerWidgets]

        if self.teamsSwapped:
            teamInstances.reverse()

        if team >= len(teamInstances):
            logger.warning(f"Team index {team + 1} out of range in LoadPlayerFromTag")
            return False

        if player >= len(teamInstances[team]):
            logger.warning(f"Player index {player + 1} out of range in LoadPlayerFromTag")
            return False

        playerData = TSHPlayerDB.GetPlayerFromTag(tag)
        if playerData:
            teamInstances[team][player].SetData(playerData, False, True, no_mains)
            return True
        return False

    def SetDefaultsFromAssets(self):
        if StateManager.Get("game.defaults"):
            players, characters = (
                StateManager.Get("game.defaults.players_per_team", 1),
                StateManager.Get("game.defaults.characters_per_player", 1),
            )
        else:
            players, characters = 1, 1
        logger.info(f"{players} players, {characters} characters")
        self.playerNumber.setValue(players)
        self.charNumber.setValue(characters)

    def GetIP(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = "127.0.0.1"
        finally:
            s.close()
        return IP

    pass
