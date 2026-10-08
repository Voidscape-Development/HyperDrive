import math
import os
import socket
from copy import deepcopy

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.ColorButton import ColorButton

from .GameAssetManager import GameAssetManager
from .GameReportWidget import GameReportWidget
from .Helpers.DictHelper import deep_get
from .Helpers.LocaleHelper import LocaleHelper
from .Helpers.MediaHelper import MediaHelper
from .Helpers.VersionHelper import add_beta_label
from .Hotkeys import Hotkeys
from .PlayerDB import PlayerDB
from .PlayerRowParts import EyebrowLabel, IconButton, SetRole, SmallFont
from .Scheduler import (
    SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
    SCOREBOARD_AUTO_UPDATE_GROUP,
    SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS,
    Scheduler,
)
from .ScoreboardPlayerWidget import ScoreboardPlayerWidget
from .SelectSetWindow import SelectSetWindow
from .SelectStationWindow import SelectStationWindow
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .StatsUtil import StatsUtil
from .Theme import ThemedIcon
from .TournamentDataManager import TournamentDataManager

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


class ScoreboardWidgetSignals(QObject):
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
    # The players, score or set source changed: the tab's summary follows
    SummaryChanged = Signal()


# Width of the scoreboard under which the two teams' players stack
LANES_STACK_WIDTH = 820
# Width under which the set bar's buttons only show their icon
BUTTON_TEXT_WIDTH = 560


class ScoreboardWidget(QWidget):
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

        self.signals = ScoreboardWidgetSignals()
        self.signals.UpdateSetData.connect(self.UpdateSetData)
        self.signals.NewSetSelected.connect(self.NewSetSelected)
        self.signals.StationSetsLoaded.connect(self.StationSetsLoaded)
        self.signals.SetSelection.connect(self.LoadSetClicked)
        self.signals.StationSelected.connect(self.LoadStationSets)
        self.signals.StationSelection.connect(self.LoadStationSetClicked)
        self.signals.ChangeSetData.connect(self.ChangeSetData)

        if self.scoreboardNumber == 1:
            Hotkeys.signals.load_set.connect(self.LoadSetClicked)
            Hotkeys.signals.swap_teams.connect(self.SwapTeams)
            Hotkeys.signals.reset_scores.connect(self.ResetScore)

            Hotkeys.signals.team1_score_up.connect(lambda: [self.CommandScoreChange(0, 1)])

            Hotkeys.signals.team1_score_down.connect(lambda: [self.CommandScoreChange(0, -1)])

            Hotkeys.signals.team2_score_up.connect(lambda: [self.CommandScoreChange(1, 1)])

            Hotkeys.signals.team2_score_down.connect(lambda: [self.CommandScoreChange(1, -1)])

        self.signals.CommandScoreChange.connect(self.CommandScoreChange)
        self.signals.SwapTeams.connect(self.SwapTeams)
        self.signals.CommandTeamColor.connect(self.CommandTeamColor)

        self.stats = StatsUtil(self.scoreboardNumber, self)

        self.lastSetSelected = None

        self.lastStationSelected = None

        # The set (or stream/station/user selection) being auto updated
        self.autoUpdateData = None
        # Auto update paused from the set bar, the set stays linked
        self.autoUpdatePaused = False
        self.autoUpdateJob = f"scoreboard_{self.scoreboardNumber}_auto_update"
        Scheduler.instance.Register(
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
        Scheduler.instance.signals.job_state_changed.connect(self.AutoUpdateJobStateChanged)
        Scheduler.instance.signals.tick.connect(self.UpdateTimeLeftTimer)

        self.playerWidgets: list[ScoreboardPlayerWidget] = []
        self.team1playerWidgets: list[ScoreboardPlayerWidget] = []
        self.team2playerWidgets: list[ScoreboardPlayerWidget] = []

        self.team1swaps = []
        self.team2swaps = []

        self.teamsSwapped = False
        # Sets that were over, so that's only told once per set
        self.finishedSets = set()
        # Set while data from start.gg is applied, so it isn't taken for
        # changes made here
        self.applyingProviderData = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # The set, the score and the round stay at the top while the
        # players scroll. scoreColumn holds the score, best of, phase and
        # match fields (the web API finds them in it by name)
        self.scoreColumn = QWidget()
        top = QVBoxLayout(self.scoreColumn)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        root.addWidget(self.scoreColumn)

        self.BuildSetBar(top)
        self.BuildScoreBar(top)
        self.BuildBanner(top)
        self.BuildRound(top)

        # The players
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scrollArea, 1)

        self.innerWidget = QWidget()
        inner = QVBoxLayout(self.innerWidget)
        inner.setContentsMargins(0, 0, 0, 0)
        self.scrollArea.setWidget(self.innerWidget)

        self.lanesLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.lanesLayout.setSpacing(10)
        inner.addLayout(self.lanesLayout)
        inner.addStretch()
        self.laneHeaders = []
        self.laneCounts = []
        self.laneLists = []
        for t in (1, 2):
            # Both lanes take half the width, whatever their players hold
            laneWidget = QWidget()
            laneWidget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            lane = QVBoxLayout(laneWidget)
            lane.setContentsMargins(0, 0, 0, 0)
            lane.setSpacing(6)
            head = QHBoxLayout()
            header = EyebrowLabel(QApplication.translate("app", "Team {0}").format(t))
            count = EyebrowLabel("")
            head.addWidget(header)
            head.addStretch()
            head.addWidget(count)
            lane.addLayout(head)
            players = QWidget()
            playersLayout = QVBoxLayout(players)
            playersLayout.setContentsMargins(0, 0, 0, 0)
            playersLayout.setSpacing(6)
            lane.addWidget(players)
            lane.addStretch()
            self.lanesLayout.addWidget(laneWidget, 1)
            self.laneHeaders.append(header)
            self.laneCounts.append(count)
            self.laneLists.append(players)

        self.BuildStatusLine(root)

        TournamentDataManager.instance.signals.tournament_changed.connect(self.UpdateBottomButtons)
        TournamentDataManager.instance.signals.tournament_changed.emit()

        self.selectSetWindow = SelectSetWindow(self)
        self.selectStationWindow = SelectStationWindow(self)

        # Exports of the team fields
        for t in (0, 1):
            team = t + 1
            self.teamNameEdits[t].editingFinished.connect(
                lambda team=team, t=t: StateManager.Set(
                    f"score.{self.scoreboardNumber}.team.{team}.teamName",
                    self.teamNameEdits[t].text(),
                )
            )
            self.teamNameEdits[t].editingFinished.emit()
            self.losersChecks[t].toggled.connect(
                lambda state, team=team: StateManager.Set(
                    f"score.{self.scoreboardNumber}.team.{team}.losers", state
                )
            )
            self.losersChecks[t].toggled.connect(
                lambda state, team=team, t=t: self.ExportLosersStatus(
                    str(team), self.teamNameEdits[t].text(), state
                )
            )
            self.losersChecks[t].toggled.emit(False)
            self.teamNameEdits[t].editingFinished.connect(
                lambda team=team, t=t: [
                    self.ExportTeamLogo(str(team), self.teamNameEdits[t].text()),
                    self.ExportLosersStatus(
                        str(team), self.teamNameEdits[t].text(), self.losersChecks[t].isChecked()
                    ),
                    self.RefreshTeamLabels(),
                ]
            )

        StateManager.Unset(f"score.{self.scoreboardNumber}.team.1.player")
        StateManager.Unset(f"score.{self.scoreboardNumber}.team.2.player")
        StateManager.Unset(f"score.{self.scoreboardNumber}.stage_strike")
        self.playerNumber.setValue(1)
        self.SetPlayersPerTeam(self.playerNumber.value())
        self.charNumber.setValue(1)

        for c in (self.phaseCombo, self.matchCombo):
            c.lineEdit().editingFinished.connect(
                lambda element=c: [
                    StateManager.Set(
                        f"score.{self.scoreboardNumber}.{element.objectName()}",
                        element.currentText(),
                    ),
                    self.signals.SummaryChanged.emit(),
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

        self.colorMenu1.setVisible(StateManager.Get("game.has_colors", False))
        self.colorMenu2.setVisible(StateManager.Get("game.has_colors", False))

        # Games of the set, and reporting it to start.gg
        self.gameReport = GameReportWidget(self)
        self.gameReport.signals.scoreChanged.connect(self.StageResultsToScore)
        self.gameReport.signals.setReported.connect(self.SetOver)
        self.gameReport.signals.changed.connect(self.RefreshPips)

        # The games of the set, in a window of their own
        self.gamesWindow = QDialog(self)
        self.gamesWindow.setWindowTitle(
            QApplication.translate("app", "Games - Scoreboard {0}").format(self.scoreboardNumber)
        )
        self.gamesWindow.setLayout(QVBoxLayout())
        self.gamesWindow.layout().addWidget(self.gameReport)
        self.gamesWindow.resize(900, 600)

        self.bestOfSpin.valueChanged.connect(self.ExportBestOf)
        self.bestOfSpin.valueChanged.emit(0)

        for t in (0, 1):
            self.scoreSpins[t].valueChanged.connect(
                lambda value, t=t: [
                    StateManager.Set(f"score.{self.scoreboardNumber}.team.{t + 1}.score", value),
                    self.gameReport.ScoreChanged(t, value),
                    self.ScoreDisplayChanged(),
                ]
            )
            self.scoreSpins[t].valueChanged.emit(0)

        MediaHelper.signals.changed.connect(self.RefreshTeamLogos)

        # Add default and user tournament phase title files
        self.phaseCombo.addItem("")
        LocaleHelper.LoadPhaseNamesToWidget(self.phaseCombo)

        self.matchCombo.addItem("")
        LocaleHelper.LoadMatchNamesToWidget(self.matchCombo)
        LocaleHelper.signals.termsChanged.connect(self.ReloadTournamentTerms)

        GameAssetManager.instance.signals.onLoad.connect(
            lambda: [
                self.SetDefaultsFromAssets(),
                self.bestOfSpin.valueChanged.emit(self.bestOfSpin.value()),
                self.colorMenu1.setModel(GameAssetManager.instance.colorModel),
                self.colorMenu2.setModel(GameAssetManager.instance.colorModel),
                self.colorMenu1.setVisible(StateManager.Get("game.has_colors", False)),
                self.colorMenu2.setVisible(StateManager.Get("game.has_colors", False)),
            ]
        )

        self.RefreshTeamLabels()
        self.RefreshSource()
        self.RefreshPips()

    # =====================================================
    # BUILDING THE PARTS
    # =====================================================
    def BuildSetBar(self, parent):
        """Where the scoreboard's set comes from: the linked set or
        station, its auto update, and the buttons to load another."""
        bar = QHBoxLayout()
        bar.setSpacing(6)
        parent.addLayout(bar)

        self.sourceFrame = QFrame()
        SetRole(self.sourceFrame, "card")
        source = QHBoxLayout(self.sourceFrame)
        source.setContentsMargins(10, 4, 4, 4)
        source.setSpacing(8)
        self.sourceDot = QLabel()
        self.sourceDot.setFixedSize(8, 8)
        source.addWidget(self.sourceDot)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.sourceTitle = QLabel()
        SmallFont(self.sourceTitle, 1.0, bold=True)
        self.sourceTitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.sourceSub = QLabel()
        SetRole(self.sourceSub, "muted")
        SmallFont(self.sourceSub, 0.85)
        self.sourceSub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        texts.addWidget(self.sourceTitle)
        texts.addWidget(self.sourceSub)
        source.addLayout(texts, 1)
        self.pauseBt = IconButton(
            "assets/icons/pause.svg", QApplication.translate("app", "Pause auto update")
        )
        self.pauseBt.clicked.connect(self.ToggleAutoUpdatePause)
        source.addWidget(self.pauseBt)
        self.timerCancelBt = IconButton(
            "assets/icons/cancel.svg", QApplication.translate("app", "Unlink the set")
        )
        self.timerCancelBt.clicked.connect(lambda: self.StopAutoUpdate(clear_variables=True))
        source.addWidget(self.timerCancelBt)
        bar.addWidget(self.sourceFrame, 1)

        self.btSelectSet = QPushButton(QApplication.translate("app", "Load set"))
        self.btSelectSet.setIcon(ThemedIcon("./assets/icons/list.svg"))
        self.btSelectSet.setEnabled(False)
        self.btSelectSet.setMinimumWidth(34)
        self.btSelectSet.clicked.connect(self.signals.SetSelection.emit)
        bar.addWidget(self.btSelectSet)

        self.btLoadStationSet = QPushButton(QApplication.translate("app", "Track station"))
        self.btLoadStationSet.setIcon(ThemedIcon("./assets/icons/station.svg"))
        self.btLoadStationSet.setMinimumWidth(34)
        self.btLoadStationSet.setToolTip(
            QApplication.translate("app", "Track sets from a stream or station")
        )
        self.btLoadStationSet.clicked.connect(self.signals.StationSelection.emit)
        bar.addWidget(self.btLoadStationSet)

        self.formatBt = IconButton(
            "assets/icons/settings.svg",
            QApplication.translate("app", "Format"),
            role="icon",
            size=32,
        )
        self.formatBt.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.formatBt.setMenu(self.BuildFormatMenu())
        bar.addWidget(self.formatBt)

        self.moreBt = IconButton(
            "assets/icons/more.svg", QApplication.translate("app", "More"), role="icon", size=32
        )
        self.moreBt.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        moreMenu = QMenu(self.moreBt)
        moreMenu.addAction(
            ThemedIcon("assets/icons/list.svg"),
            QApplication.translate("app", "Games..."),
            lambda: self.OpenGames(),
        )
        moreMenu.addAction(
            ThemedIcon("assets/icons/copy.svg"),
            QApplication.translate("app", "Copy the remote scoreboard address"),
            self.CopyRemoteLink,
        )
        moreMenu.addAction(
            QApplication.translate("app", "Rename this scoreboard..."), self.RenameScoreboard
        )
        moreMenu.addSeparator()
        clearAll = moreMenu.addAction(
            ThemedIcon("assets/icons/cancel.svg"),
            QApplication.translate("app", "Clear all..."),
            self.ClearAllClicked,
        )
        clearAll.setToolTip(
            QApplication.translate(
                "app",
                "Clear the players, scores, phase and match, and unlink the loaded set",
            )
        )
        moreMenu.setToolTipsVisible(True)
        self.moreBt.setMenu(moreMenu)
        bar.addWidget(self.moreBt)

    def BuildFormatMenu(self):
        """Players per team, characters per player and the player fields."""
        menu = QMenu(self)
        menu.setToolTipsVisible(True)

        panel = QWidget()
        form = QFormLayout(panel)
        form.setContentsMargins(10, 6, 10, 6)
        self.playerNumber = QSpinBox()
        self.playerNumber.setRange(1, 16)
        self.playerNumber.valueChanged.connect(self.SetPlayersPerTeam)
        form.addRow(QApplication.translate("app", "Players per team"), self.playerNumber)
        self.charNumber = QSpinBox()
        self.charNumber.valueChanged.connect(self.SetCharacterNumber)
        form.addRow(QApplication.translate("app", "Characters per player"), self.charNumber)
        panelAction = QWidgetAction(menu)
        panelAction.setDefaultWidget(panel)
        menu.addAction(panelAction)

        menu.addSection(QApplication.translate("app", "Player fields"))
        self.elements = [
            [QApplication.translate("app", "Real Name"), ["real_name"], "show_name"],
            [QApplication.translate("app", "Twitter"), ["twitter", "twitterLabel"], "show_social"],
            [QApplication.translate("app", "Seed"), ["seed", "seedLabel"], "show_seed"],
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
        self.elementActions = []
        for element in self.elements:
            action: QAction = menu.addAction(element[0])
            action.setCheckable(True)
            action.setChecked(SettingsManager.Get(f"display_options.{element[2]}", True))
            action.toggled.connect(
                lambda toggled, action=action, element=element: self.ToggleElements(
                    action, element[1]
                )
            )
            self.elementActions.append(action)

        menu.addSeparator()
        self.expandAction = menu.addAction(
            QApplication.translate("app", "Open every player's details")
        )
        self.expandAction.setCheckable(True)
        self.expandAction.setChecked(SettingsManager.Get("display_options.expand_players", False))
        self.expandAction.toggled.connect(self.SetExpandPlayers)
        return menu

    def BuildScoreBar(self, parent):
        """The two teams with their score, and the set's format between them."""
        self.hero = QGridLayout()
        self.hero.setSpacing(8)
        parent.addLayout(self.hero)

        self.teamSides = []
        self.teamNameEdits = []
        self.teamLabels = []
        self.teamHints = []
        self.losersChecks = []
        self.scoreSpins = []
        self.colorGroups = []

        DEFAULT_TEAM1_COLOR = SettingsManager.Get("general.team_1_default_color", "#fe3636")
        DEFAULT_TEAM2_COLOR = SettingsManager.Get("general.team_2_default_color", "#2e89ff")
        self.colorButton1 = ColorButton(color=DEFAULT_TEAM1_COLOR)
        self.colorButton2 = ColorButton(color=DEFAULT_TEAM2_COLOR)

        for t, colorButton in enumerate((self.colorButton1, self.colorButton2)):
            side = QFrame()
            side.setObjectName(f"teamSide{t + 1}")
            SetRole(side, "card")
            side.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            layout = QHBoxLayout(side)
            layout.setContentsMargins(12, 8, 10, 8)
            layout.setSpacing(8)

            colorGroup = QWidget()
            colorLayout = QVBoxLayout(colorGroup)
            colorLayout.setContentsMargins(0, 0, 0, 0)
            colorLayout.setSpacing(2)
            colorButton.setFixedSize(28, 28)
            colorButton.setToolTip(QApplication.translate("app", "Team color"))
            colorLayout.addWidget(colorButton, 0, Qt.AlignmentFlag.AlignCenter)
            colorMenu = QComboBox()
            colorMenu.setVisible(False)
            colorMenu.setModel(GameAssetManager.instance.colorModel)
            colorMenu.setEditable(True)
            colorMenu.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            colorMenu.completer().setCompletionMode(QCompleter.PopupCompletion)
            colorMenu.setMaximumWidth(150)
            colorMenu.setIconSize(QSize(24, 24))
            colorLayout.addWidget(colorMenu)
            if t == 0:
                self.colorMenu1 = colorMenu
            else:
                self.colorMenu2 = colorMenu

            ident = QVBoxLayout()
            ident.setSpacing(2)
            teamLabel = QLabel(QApplication.translate("app", "TEAM {0}").format(t + 1))
            teamLabel.setObjectName("teamLabel")
            SmallFont(teamLabel, 1.45, bold=True)
            teamLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            teamName = QLineEdit()
            teamName.setObjectName("teamName")
            teamName.setPlaceholderText(QApplication.translate("app", "Team Name"))
            SetRole(teamName, "inline")
            SmallFont(teamName, 1.3, bold=True)
            teamName.setVisible(False)
            teamName.setMinimumWidth(40)
            meta = QHBoxLayout()
            meta.setSpacing(6)
            losers = QCheckBox("[L]")
            losers.setObjectName("losers")
            SetRole(losers, "pill")
            losers.setToolTip(QApplication.translate("app", "Losers side"))
            hint = QLabel()
            SetRole(hint, "muted")
            SmallFont(hint, 0.85)
            hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            ident.addWidget(teamLabel)
            ident.addWidget(teamName)
            if t == 0:
                meta.addWidget(losers)
                meta.addWidget(hint, 1)
            else:
                meta.addWidget(hint, 1)
                meta.addWidget(losers)
                teamLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                teamName.setAlignment(Qt.AlignmentFlag.AlignRight)
                hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            ident.addLayout(meta)

            score = QSpinBox()
            score.setObjectName("score_left" if t == 0 else "score_right")
            SetRole(score, "score")
            score.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            score.setAlignment(Qt.AlignmentFlag.AlignCenter)
            score.setMaximum(999)
            SmallFont(score, 2.6, bold=True)
            score.setFixedWidth(64)
            buttons = QVBoxLayout()
            buttons.setSpacing(4)
            up = QPushButton("+")
            SetRole(up, "primary")
            up.setFixedSize(30, 26)
            up.setStyleSheet("padding: 0px;")
            up.setToolTip(QApplication.translate("app", "Score +1 (can also be set on a hotkey)"))
            up.clicked.connect(lambda checked=False, t=t: self.CommandScoreChange(t, 1))
            down = QPushButton("−")
            down.setFixedSize(30, 26)
            down.setStyleSheet("padding: 0px;")
            down.setToolTip(QApplication.translate("app", "Score -1"))
            down.clicked.connect(lambda checked=False, t=t: self.CommandScoreChange(t, -1))
            buttons.addWidget(up)
            buttons.addWidget(down)

            if t == 0:
                layout.addWidget(colorGroup)
                layout.addLayout(ident, 1)
                layout.addLayout(buttons)
                layout.addWidget(score)
            else:
                layout.addWidget(score)
                layout.addLayout(buttons)
                layout.addLayout(ident, 1)
                layout.addWidget(colorGroup)

            self.teamSides.append(side)
            self.teamNameEdits.append(teamName)
            self.teamLabels.append(teamLabel)
            self.teamHints.append(hint)
            self.losersChecks.append(losers)
            self.scoreSpins.append(score)
            self.colorGroups.append(colorGroup)

        self.colorButton1.colorChanged.connect(
            lambda color: [
                StateManager.Set(f"score.{self.scoreboardNumber}.team.1.color", color),
                self.RefreshTeamColors(),
            ]
        )
        self.colorButton2.colorChanged.connect(
            lambda color: [
                StateManager.Set(f"score.{self.scoreboardNumber}.team.2.color", color),
                self.RefreshTeamColors(),
            ]
        )
        self.CommandTeamColor(0, DEFAULT_TEAM1_COLOR)
        self.CommandTeamColor(1, DEFAULT_TEAM2_COLOR)
        self.colorMenu1.currentIndexChanged.connect(
            lambda element=self.colorMenu1: [
                self.CommandTeamColor(0, element),
                self.CommandTeamColor(1, element, force_opponent=True),
            ]
        )
        self.colorMenu2.currentIndexChanged.connect(
            lambda element=self.colorMenu2: [
                self.CommandTeamColor(1, element),
                self.CommandTeamColor(0, element, force_opponent=True),
            ]
        )

        # The set's format, between the teams
        self.center = QFrame()
        SetRole(self.center, "card")
        self.center.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        center = QVBoxLayout(self.center)
        center.setContentsMargins(10, 6, 10, 6)
        center.setSpacing(6)

        boRow = QHBoxLayout()
        boRow.setSpacing(0)
        boRow.addStretch()
        self.boButtons = {}
        self.boGroup = QButtonGroup(self)
        self.boGroup.setExclusive(False)
        values = (1, 3, 5, 7)
        for i, value in enumerate(values):
            button = QPushButton(f"BO{value}")
            SetRole(button, "segment", first=i == 0, last=i == len(values) - 1)
            button.setCheckable(True)
            button.setToolTip(QApplication.translate("app", "Best of {0}").format(value))
            button.clicked.connect(
                lambda checked, value=value: self.bestOfSpin.setValue(value if checked else 0)
            )
            self.boGroup.addButton(button)
            self.boButtons[value] = button
            boRow.addWidget(button)
        boRow.addSpacing(6)
        # Any other best of, and the value the web API and start.gg set
        self.bestOfSpin = QSpinBox()
        self.bestOfSpin.setObjectName("best_of")
        self.bestOfSpin.setPrefix("BO")
        self.bestOfSpin.setSpecialValueText("BO –")
        self.bestOfSpin.setMaximum(99)
        self.bestOfSpin.setFixedWidth(70)
        self.bestOfSpin.setToolTip(QApplication.translate("app", "Best of"))
        boRow.addWidget(self.bestOfSpin)
        boRow.addStretch()
        center.addLayout(boRow)

        self.pipsLayout = QHBoxLayout()
        self.pipsLayout.setSpacing(4)
        self.pipsWidget = QWidget()
        self.pipsWidget.setLayout(self.pipsLayout)
        self.pipsLayout.setContentsMargins(0, 0, 0, 0)
        pipsRow = QHBoxLayout()
        pipsRow.addStretch()
        pipsRow.addWidget(self.pipsWidget)
        pipsRow.addStretch()
        center.addLayout(pipsRow)
        self.pips = []

        actions = QHBoxLayout()
        actions.setSpacing(4)
        actions.addStretch()
        self.ftLabel = QLabel()
        SetRole(self.ftLabel, "muted")
        SmallFont(self.ftLabel, 0.85)
        actions.addWidget(self.ftLabel)
        self.btSwapTeams = IconButton(
            "assets/icons/swap.svg", QApplication.translate("app", "Swap teams")
        )
        self.btSwapTeams.setObjectName("btSwapTeams")
        self.btSwapTeams.clicked.connect(self.SwapTeams)
        actions.addWidget(self.btSwapTeams)
        self.btResetScore = IconButton(
            "assets/icons/undo.svg", QApplication.translate("app", "Reset score")
        )
        self.btResetScore.setObjectName("btResetScore")
        self.btResetScore.clicked.connect(
            lambda: [
                self.ResetScore(),
                self.bestOfSpin.valueChanged.emit(self.bestOfSpin.value()),
            ]
        )
        actions.addWidget(self.btResetScore)
        self.btGames = IconButton("assets/icons/list.svg", QApplication.translate("app", "Games"))
        self.btGames.setToolTip(
            QApplication.translate(
                "app", "The result, stage and characters of each game of the set"
            )
        )
        self.btGames.clicked.connect(lambda: self.OpenGames())
        actions.addWidget(self.btGames)
        actions.addStretch()
        center.addLayout(actions)

        self.ArrangeScoreBar(stacked=False, centerOnTop=False)

    def ArrangeScoreBar(self, stacked, centerOnTop):
        for w in (self.teamSides[0], self.center, self.teamSides[1]):
            self.hero.removeWidget(w)
        for col in range(3):
            self.hero.setColumnStretch(col, 0)
            self.hero.setColumnMinimumWidth(col, 0)
        if stacked:
            self.hero.addWidget(self.center, 0, 0)
            self.hero.addWidget(self.teamSides[0], 1, 0)
            self.hero.addWidget(self.teamSides[1], 2, 0)
            self.hero.setColumnStretch(0, 1)
        elif centerOnTop:
            self.hero.addWidget(self.center, 0, 0, 1, 2)
            self.hero.addWidget(self.teamSides[0], 1, 0)
            self.hero.addWidget(self.teamSides[1], 1, 1)
            self.hero.setColumnStretch(0, 1)
            self.hero.setColumnStretch(1, 1)
        else:
            self.hero.addWidget(self.teamSides[0], 0, 0)
            self.hero.addWidget(self.center, 0, 1)
            self.hero.addWidget(self.teamSides[1], 0, 2)
            # The center can shrink to nothing: keep it at its own width
            self.hero.setColumnMinimumWidth(1, self.center.sizeHint().width())
            self.hero.setColumnStretch(0, 1)
            self.hero.setColumnStretch(2, 1)

    def BuildBanner(self, parent):
        """Shown when a team has won the set, until it is reported."""
        self.banner = QFrame()
        SetRole(self.banner, "banner")
        layout = QHBoxLayout(self.banner)
        layout.setContentsMargins(10, 6, 6, 6)
        self.bannerLabel = QLabel()
        self.bannerLabel.setWordWrap(True)
        layout.addWidget(self.bannerLabel, 1)
        review = QPushButton(QApplication.translate("app", "Review and report..."))
        SetRole(review, "primary")
        review.clicked.connect(lambda: self.OpenGames())
        layout.addWidget(review)
        self.banner.hide()
        parent.addWidget(self.banner)

    def BuildRound(self, parent):
        row = QGridLayout()
        row.setHorizontalSpacing(8)
        row.setVerticalSpacing(2)
        self.phaseCombo = QComboBox()
        self.phaseCombo.setObjectName("phase")
        self.phaseCombo.setEditable(True)
        self.phaseCombo.lineEdit().setPlaceholderText(
            QApplication.translate("app", "Pool A, Bracket, Top 8, etc")
        )
        self.matchCombo = QComboBox()
        self.matchCombo.setObjectName("match")
        self.matchCombo.setEditable(True)
        self.matchCombo.lineEdit().setPlaceholderText(
            QApplication.translate("app", "Winners Finals, Losers Semis, etc")
        )
        row.addWidget(EyebrowLabel(QApplication.translate("app", "Phase")), 0, 0)
        row.addWidget(EyebrowLabel(QApplication.translate("app", "Match")), 0, 1)
        row.addWidget(self.phaseCombo, 1, 0)
        row.addWidget(self.matchCombo, 1, 1)
        row.setColumnStretch(0, 1)
        row.setColumnStretch(1, 1)
        parent.addLayout(row)

    def BuildStatusLine(self, parent):
        line = QHBoxLayout()
        line.setContentsMargins(2, 0, 2, 0)
        self.remoteScoreboardUrl = f"http://{self.GetIP()}:{SettingsManager.Get('general.webserver_port', 5500)}/scoreboard"
        text = QApplication.translate(
            "app", "Open {0} in a browser to edit the scoreboard remotely."
        ).format(f"<a href='{self.remoteScoreboardUrl}'>{self.remoteScoreboardUrl}</a>")
        self.remoteScoreboardLabel = QLabel(add_beta_label(text, "web_score"))
        self.remoteScoreboardLabel.setOpenExternalLinks(True)
        self.remoteScoreboardLabel.setWordWrap(True)
        SetRole(self.remoteScoreboardLabel, "muted")
        SmallFont(self.remoteScoreboardLabel, 0.9)
        line.addWidget(self.remoteScoreboardLabel, 1)
        copy = IconButton("assets/icons/copy.svg", QApplication.translate("app", "Copy address"))
        copy.clicked.connect(self.CopyRemoteLink)
        line.addWidget(copy)
        parent.addLayout(line)

    # =====================================================
    # LAYOUT AND DISPLAY
    # =====================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ArrangeForWidth(self.width())

    def ArrangeForWidth(self, width):
        """Stacks the lanes and the score bar when they don't fit side by
        side. Their parts can shrink to nothing, so the dock can be made
        narrow, and they stack before they get squeezed."""
        spacing = self.hero.spacing()
        sides = [side.sizeHint().width() for side in self.teamSides]
        center = self.center.sizeHint().width()
        lanesStacked = width < LANES_STACK_WIDTH
        if width >= sides[0] + center + sides[1] + 2 * spacing and not lanesStacked:
            centerOnTop, scoreStacked = False, False
        elif width >= max(center, sides[0] + sides[1] + spacing):
            centerOnTop, scoreStacked = True, False
        else:
            centerOnTop, scoreStacked = False, True
        # Only the buttons' icons in a narrow dock
        iconsOnly = width < BUTTON_TEXT_WIDTH
        state = (lanesStacked, scoreStacked, centerOnTop, iconsOnly)
        if state == getattr(self, "_layoutState", None):
            return
        self._layoutState = state
        self.lanesLayout.setDirection(
            QBoxLayout.Direction.TopToBottom if lanesStacked else QBoxLayout.Direction.LeftToRight
        )
        self.btSelectSet.setText("" if iconsOnly else QApplication.translate("app", "Load set"))
        self.btLoadStationSet.setText(
            "" if iconsOnly else QApplication.translate("app", "Track station")
        )
        self.ArrangeScoreBar(stacked=scoreStacked, centerOnTop=centerOnTop)

    def RefreshTeamColors(self):
        for t, button in enumerate((self.colorButton1, self.colorButton2)):
            color = button.color() or "#888888"
            side = "left" if t == 0 else "right"
            self.teamSides[t].setStyleSheet(
                f"QFrame#teamSide{t + 1} {{ border-{side}: 4px solid {color}; }}"
            )
        self.RefreshPips()

    def RefreshTeamLabels(self):
        """The name on each side: the team name with 2+ players, else the
        player's tag. The hint under it lists the players."""
        multi = self.playerNumber.value() > 1
        for t, players in enumerate((self.team1playerWidgets, self.team2playerWidgets)):
            tags = [p.findChild(QLineEdit, "name").text() for p in players]
            tags = [tag for tag in tags if tag]
            self.teamNameEdits[t].setVisible(multi)
            self.teamLabels[t].setVisible(not multi)
            fallback = QApplication.translate("app", "Team {0}").format(t + 1)
            if not multi:
                self.teamLabels[t].setText(tags[0] if tags else fallback)
                self.teamHints[t].setText(fallback)
            else:
                self.teamHints[t].setText(" / ".join(tags) if tags else fallback)
            name = self.teamNameEdits[t].text() if multi else ""
            self.laneHeaders[t].setText((name or fallback).upper())
            count = len(players)
            self.laneCounts[t].setText(
                (
                    QApplication.translate("app", "{0} player")
                    if count == 1
                    else QApplication.translate("app", "{0} players")
                )
                .format(count)
                .upper()
            )
        self.signals.SummaryChanged.emit()

    def TeamDisplayName(self, t):
        if self.playerNumber.value() > 1 and self.teamNameEdits[t].text():
            return self.teamNameEdits[t].text()
        return (
            self.teamLabels[t].text()
            if self.playerNumber.value() == 1
            else self.teamHints[t].text()
        )

    def Summary(self):
        """One line for the scoreboard's tab: the teams, the score and where
        the set comes from."""
        score = f"{self.scoreSpins[0].value()}–{self.scoreSpins[1].value()}"
        names = [self.TeamDisplayName(0), self.TeamDisplayName(1)]
        text = f"{names[0]} {score} {names[1]}"
        source = self.SourceShortText()
        return f"{text} · {source}" if source else text

    def SourceShortText(self):
        data = self.autoUpdateData or {}
        if data.get("auto_update") in ("stream", "station") and self.lastStationSelected:
            kind = (
                QApplication.translate("app", "Stream")
                if data.get("auto_update") == "stream"
                else QApplication.translate("app", "Station")
            )
            return f"{kind} {self.lastStationSelected.get('identifier')}"
        if self.lastSetSelected:
            return ""
        return QApplication.translate("app", "manual")

    def ScoreDisplayChanged(self):
        self.RefreshBanner()
        self.signals.SummaryChanged.emit()

    def RefreshPips(self):
        """A pip per game, filled with the color of the team that won it."""
        if not hasattr(self, "gameReport"):
            return
        games = self.gameReport.Games()
        count = max(self.bestOfSpin.value(), len(games))
        while len(self.pips) < count:
            pip = QPushButton()
            SetRole(pip, "pip")
            pip.setFixedSize(16, 16)
            pip.setCursor(Qt.CursorShape.PointingHandCursor)
            index = len(self.pips)
            pip.clicked.connect(lambda checked=False, index=index: self.OpenGames(index))
            self.pipsLayout.addWidget(pip)
            self.pips.append(pip)
        while len(self.pips) > count:
            pip = self.pips.pop()
            pip.setParent(None)
            pip.deleteLater()
        colors = [self.colorButton1.color(), self.colorButton2.color()]
        for i, pip in enumerate(self.pips):
            winner = games[i] if i < len(games) else None
            if winner in (1, 2):
                color = colors[winner - 1] or "#888888"
                pip.setStyleSheet(f"background: {color}; border-color: {color};")
                tip = QApplication.translate("app", "Game {0}: won by {1}").format(
                    i + 1, self.TeamDisplayName(winner - 1)
                )
            elif winner == 0:
                pip.setStyleSheet("background: #9298ab;")
                tip = QApplication.translate("app", "Game {0}: draw").format(i + 1)
            else:
                pip.setStyleSheet("")
                tip = QApplication.translate("app", "Game {0}").format(i + 1)
            pip.setToolTip(tip + " · " + QApplication.translate("app", "click to open it"))
        self.pipsWidget.setVisible(count > 0)
        self.RefreshBanner()

    def RefreshBanner(self):
        if not hasattr(self, "banner"):
            return
        bestOf = self.bestOfSpin.value()
        firstTo = math.ceil(bestOf / 2) if bestOf > 0 else 0
        scores = [s.value() for s in self.scoreSpins]
        winner = None
        if firstTo > 0:
            if scores[0] >= firstTo and scores[0] > scores[1]:
                winner = 0
            elif scores[1] >= firstTo and scores[1] > scores[0]:
                winner = 1
        linked = self.lastSetSelected is not None
        reported = str(self.lastSetSelected) in self.finishedSets
        if winner is None or not linked or reported:
            self.banner.hide()
            return
        self.bannerLabel.setText(
            QApplication.translate("app", "{0} wins {1}–{2}. Report the set to start.gg?").format(
                self.TeamDisplayName(winner), max(scores), min(scores)
            )
        )
        self.banner.show()

    def RefreshSource(self):
        """The set bar: the linked set or station and its auto update."""
        if not hasattr(self, "sourceTitle"):
            return
        data = self.autoUpdateData or {}
        linked = self.lastSetSelected is not None or bool(data)
        color = "#4cc283" if linked and not self.autoUpdatePaused else "#9298ab"
        self.sourceDot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        if not linked:
            self.sourceTitle.setText(QApplication.translate("app", "Manual"))
            self.sourceSub.setText(
                QApplication.translate("app", "Not linked to a set. Load one, or edit by hand.")
            )
        else:
            parts = []
            provider = TournamentDataManager.instance.provider
            name = getattr(provider, "name", None) if provider else None
            if name:
                parts.append(str(name))
            if self.matchCombo.currentText():
                parts.append(self.matchCombo.currentText())
            names = [self.TeamDisplayName(0), self.TeamDisplayName(1)]
            parts.append(f"{names[0]} vs {names[1]}")
            self.sourceTitle.setText(" · ".join(parts))

            sub = []
            if data.get("auto_update") == "stream" and self.lastStationSelected:
                sub.append(
                    QApplication.translate("app", "Stream [{0}]").format(
                        self.lastStationSelected.get("identifier")
                    )
                )
            elif data.get("auto_update") == "station" and self.lastStationSelected:
                sub.append(
                    QApplication.translate("app", "Station [{0}]").format(
                        self.lastStationSelected.get("identifier")
                    )
                )
            if not data:
                sub.append(QApplication.translate("app", "Auto update off"))
            elif self.autoUpdatePaused:
                sub.append(QApplication.translate("app", "Auto update paused"))
            else:
                remaining = Scheduler.instance.RemainingMs(self.autoUpdateJob)
                if remaining is None:
                    sub.append(QApplication.translate("app", "Updating..."))
                else:
                    sub.append(
                        QApplication.translate("app", "Updates in {0}s").format(
                            math.ceil(remaining / 1000)
                        )
                    )
            self.sourceSub.setText(" · ".join(sub))
        self.sourceFrame.setToolTip(self.sourceTitle.text())
        self.pauseBt.setVisible(bool(data))
        self.pauseBt.setIcon(
            ThemedIcon(
                "assets/icons/play.svg" if self.autoUpdatePaused else "assets/icons/pause.svg"
            )
        )
        self.pauseBt.setToolTip(
            QApplication.translate("app", "Resume auto update")
            if self.autoUpdatePaused
            else QApplication.translate("app", "Pause auto update")
        )
        self.timerCancelBt.setVisible(linked)
        self.btSelectSet.setProperty("hdRole", None if linked else "primary")
        self.btSelectSet.style().unpolish(self.btSelectSet)
        self.btSelectSet.style().polish(self.btSelectSet)

    def ToggleAutoUpdatePause(self):
        if not self.autoUpdateData:
            return
        self.autoUpdatePaused = not self.autoUpdatePaused
        if self.autoUpdatePaused:
            Scheduler.instance.Stop(self.autoUpdateJob)
        else:
            Scheduler.instance.Start(self.autoUpdateJob)
        self.RefreshSource()

    def CopyRemoteLink(self):
        QApplication.clipboard().setText(self.remoteScoreboardUrl)

    def RenameScoreboard(self):
        # Imported here: the manager imports this module
        from .ScoreboardManager import ScoreboardManager

        manager = ScoreboardManager.instance
        current = manager.GetTabName(self.scoreboardNumber)
        name, ok = QInputDialog.getText(
            self,
            QApplication.translate("app", "Rename scoreboard"),
            QApplication.translate("app", "Name (empty for the default name)"),
            text=current,
        )
        if ok:
            manager.SetTabName(self.scoreboardNumber, name.strip())

    def ReloadTournamentTerms(self):
        # The match and phase names were edited in the settings
        LocaleHelper.RefreshNamesInWidget(self.phaseCombo, LocaleHelper.LoadPhaseNamesToWidget)
        LocaleHelper.RefreshNamesInWidget(self.matchCombo, LocaleHelper.LoadMatchNamesToWidget)

    def ExportBestOf(self, value):
        with StateManager.SaveBlock():
            StateManager.Set(f"score.{self.scoreboardNumber}.best_of", value)
            StateManager.Set(f"score.{self.scoreboardNumber}.best_of_short_text", f"BO{value}")
            StateManager.Set(
                f"score.{self.scoreboardNumber}.best_of_text",
                LocaleHelper.matchNames.get("best_of").format(value) if value > 0 else "",
            )
            StateManager.Set(f"score.{self.scoreboardNumber}.first_to", math.ceil(value / 2))
            StateManager.Set(
                f"score.{self.scoreboardNumber}.first_to_short_text", f"FT{math.ceil(value / 2)}"
            )
            StateManager.Set(
                f"score.{self.scoreboardNumber}.first_to_text",
                LocaleHelper.matchNames.get("first_to").format(math.ceil(value / 2))
                if value > 0
                else "",
            )
            self.gameReport.SetBestOf(value)
        for bo, button in self.boButtons.items():
            button.setChecked(bo == value)
        self.ftLabel.setText(
            QApplication.translate("app", "First to {0}").format(math.ceil(value / 2))
            if value > 0
            else ""
        )
        self.RefreshPips()

    def StageResultsToScore(self, team_1_score, team_2_score):
        with QSignalBlocker(self.scoreSpins[0]):
            self.scoreSpins[0].setValue(team_1_score)
            StateManager.Set(f"score.{self.scoreboardNumber}.team.1.score", team_1_score)

        with QSignalBlocker(self.scoreSpins[1]):
            self.scoreSpins[1].setValue(team_2_score)
            StateManager.Set(f"score.{self.scoreboardNumber}.team.2.score", team_2_score)

    def closeEvent(self, event):
        Scheduler.instance.Stop(self.autoUpdateJob)

    def RemoveAutoUpdate(self):
        """Called before the scoreboard is deleted, so its job doesn't keep
        running for a widget that no longer exists."""
        self.autoUpdateData = None
        Scheduler.instance.signals.job_state_changed.disconnect(self.AutoUpdateJobStateChanged)
        Scheduler.instance.signals.tick.disconnect(self.UpdateTimeLeftTimer)
        Scheduler.instance.Unregister(self.autoUpdateJob)
        MediaHelper.signals.changed.disconnect(self.RefreshTeamLogos)

    def ExportTeamLogo(self, team, value):
        logo = MediaHelper.TeamLogoPath(value)
        StateManager.Set(
            f"score.{self.scoreboardNumber}.team.{team}.logo",
            logo if os.path.exists(logo) else None,
        )

    def RefreshTeamLogos(self):
        """After a team logo is changed in the Player Database window"""
        for t in (0, 1):
            self.ExportTeamLogo(str(t + 1), self.teamNameEdits[t].text())

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
                pw.SetElementVisible(element, action.isChecked())

    def SetExpandPlayers(self, expand):
        SettingsManager.Set("display_options.expand_players", expand)
        for pw in self.playerWidgets:
            pw.SetDetailsShown(expand)

    def OpenGames(self, index=None):
        self.gamesWindow.show()
        self.gamesWindow.raise_()
        self.gamesWindow.activateWindow()
        if index is not None:
            self.gameReport.FocusGame(index)

    def UpdateBottomButtons(self):
        provider = TournamentDataManager.instance.provider
        if provider and provider.url:
            self.btSelectSet.setToolTip(
                QApplication.translate("app", "Load set from {0}").format(provider.url)
            )
            self.btSelectSet.setEnabled(True)
            self.btLoadStationSet.setEnabled(True)
        else:
            self.btSelectSet.setToolTip(QApplication.translate("app", "Set a tournament first"))
            self.btSelectSet.setEnabled(False)
            self.btLoadStationSet.setEnabled(False)
        self.RefreshSource()

    def SetCharacterNumber(self, value):
        # logger.info(f"ScoreboardWidget#SetCharacterNumber({value})")
        for pw in self.playerWidgets:
            pw.SetCharactersPerPlayer(value)

    def ConnectLosersStatus(self, p, t):
        # Connected once per player widget: connecting every existing player
        # on each call made the export run several times per edit
        for field in ("name", "team"):
            p.findChild(QLineEdit, field).editingFinished.connect(
                lambda t=t: [
                    self.ExportLosersStatus(
                        str(t + 1),
                        self.teamNameEdits[t].text(),
                        self.losersChecks[t].isChecked(),
                    ),
                    self.RefreshTeamLabels(),
                    self.RefreshSource(),
                ]
            )

    def SetPlayersPerTeam(self, number):
        teams = (self.team1playerWidgets, self.team2playerWidgets)
        while len(self.team1playerWidgets) < number:
            for t, players in enumerate(teams):
                team = t + 1
                p = ScoreboardPlayerWidget(
                    index=len(players) + 1,
                    teamNumber=team,
                    path=f"score.{self.scoreboardNumber}.team.{team}.player.{len(players) + 1}",
                )
                self.playerWidgets.append(p)
                self.laneLists[t].layout().addWidget(p)
                p.SetCharactersPerPlayer(self.charNumber.value())
                p.SetDetailsShown(self.expandAction.isChecked())

                p.btMoveUp.clicked.connect(
                    lambda checked=False, p=p, players=players: p.SwapWith(
                        players[max(0, players.index(p) - 1)]
                    )
                )
                p.btMoveDown.clicked.connect(
                    lambda checked=False, p=p, players=players: p.SwapWith(
                        players[min(len(players) - 1, players.index(p) + 1)]
                    )
                )

                p.instanceSignals.playerId_changed.connect(self.stats.signals.RecentSetsSignal.emit)
                if team == 1:
                    p.instanceSignals.player1Id_changed.connect(
                        self.stats.signals.LastSetsP1Signal.emit
                    )
                    p.instanceSignals.player1Id_changed.connect(
                        self.stats.signals.PlayerHistoryStandingsP1Signal.emit
                    )
                else:
                    p.instanceSignals.player2Id_changed.connect(
                        self.stats.signals.LastSetsP2Signal.emit
                    )
                    p.instanceSignals.player2Id_changed.connect(
                        self.stats.signals.PlayerHistoryStandingsP2Signal.emit
                    )
                p.instanceSignals.player_seed_changed.connect(
                    self.stats.signals.UpsetFactorCalculation.emit
                )
                self.ConnectLosersStatus(p, t)

                players.append(p)

        while len(self.team1playerWidgets) > number:
            for players in teams:
                player = players[-1]
                StateManager.Unset(player.path)
                player.setParent(None)
                self.playerWidgets.remove(player)
                players.remove(player)
                player.deleteLater()

        for team in [1, 2]:
            if StateManager.Get(f"score.{self.scoreboardNumber}.team.{team}"):
                for k in list(
                    StateManager.Get(f"score.{self.scoreboardNumber}.team.{team}.player").keys()
                ):
                    if int(k) > number:
                        StateManager.Unset(f"score.{self.scoreboardNumber}.team.{team}.player.{k}")

        if number <= 1:
            for t in (0, 1):
                if self.teamNameEdits[t].text():
                    self.teamNameEdits[t].setText("")
                    self.teamNameEdits[t].editingFinished.emit()

        for action, element in zip(self.elementActions, self.elements):
            self.ToggleElements(action, element[1])

        self.RefreshTeamLabels()
        if hasattr(self, "gameReport"):
            self.gameReport.RebuildRows()

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
            # make the games window add/remove wins (and rebuild itself), losing
            # which games were won; gameReport.Swap() below swaps them as is.
            scoreLeft = self.scoreSpins[0].value()
            scoreRight = self.scoreSpins[1].value()
            self.StageResultsToScore(scoreRight, scoreLeft)

            # Losers
            losersLeft = self.losersChecks[0].isChecked()
            self.losersChecks[0].setChecked(self.losersChecks[1].isChecked())
            self.losersChecks[1].setChecked(losersLeft)

            # Team Names
            teamNameLeft = self.teamNameEdits[0].text()
            self.teamNameEdits[0].setText(self.teamNameEdits[1].text())
            self.teamNameEdits[1].setText(teamNameLeft)
            self.teamNameEdits[0].editingFinished.emit()
            self.teamNameEdits[1].editingFinished.emit()

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
        self.scoreSpins[0].setValue(0)
        self.scoreSpins[1].setValue(0)

    def ClearAllClicked(self):
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Clear All"),
            QApplication.translate(
                "app",
                "Clear the players, scores, phase and match of this scoreboard, and unlink the loaded set?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.ClearAll()

    # Back to an empty scoreboard. Team names and colors are kept
    def ClearAll(self):
        with StateManager.SaveBlock():
            self.StopAutoUpdate(clear_variables=True)
            self.CommandClearAll()
            self.ClearScore()
            StateManager.Unset(f"score.{self.scoreboardNumber}.stage_strike")

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

        TournamentDataManager.instance.GetMatch(
            self, data.get("id"), overwrite=False, on_finished=track()
        )

        if data.get("auto_update") in ("stream", "station"):
            TournamentDataManager.instance.LoadStationSets(self, on_finished=track())

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
                Scheduler.instance.Stop(self.autoUpdateJob)
            else:
                # In stream/station mode, every update selects the set
                # again. Then the job is still running, so this only updates
                # what the next run loads. Otherwise it restarts the countdown.
                Scheduler.instance.Start(self.autoUpdateJob)
            # Loading a set (or the station's next set) resumes updates
            self.autoUpdatePaused = False

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

                TournamentDataManager.instance.GetMatch(
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
        self.RefreshSource()
        self.RefreshBanner()
        self.signals.SummaryChanged.emit()

    def StartAutoUpdateAfterLoad(self, data):
        # Unless another set was selected or auto update was stopped meanwhile
        if self.autoUpdateData is data:
            Scheduler.instance.Start(self.autoUpdateJob)

    def StopAutoUpdate(self, clear_variables=False):
        self.autoUpdateData = None
        Scheduler.instance.Stop(self.autoUpdateJob)

        if clear_variables:
            self.lastSetSelected = None
            self.lastStationSelected = None

            StateManager.Set(f"score.{self.scoreboardNumber}.auto_update", None)
            StateManager.Set(f"score.{self.scoreboardNumber}.set_id", None)
            StateManager.Set(f"score.{self.scoreboardNumber}.station", None)
            self.gameReport.NewSet(None)

        self.autoUpdatePaused = False
        self.RefreshSource()
        self.RefreshBanner()
        self.signals.SummaryChanged.emit()

    def AutoUpdateJobStateChanged(self, name):
        if name == self.autoUpdateJob:
            self.UpdateTimeLeftTimer()

    def UpdateTimeLeftTimer(self):
        # None while an update or a newly selected set is loading
        if self.autoUpdateData and not self.autoUpdatePaused:
            self.RefreshSource()

    def LoadSetClicked(self):
        self.selectSetWindow.LoadSets()
        self.selectSetWindow.show()

    def LoadStationSets(self, station):
        self.lastSetSelected = None
        self.lastStationSelected = station
        TournamentDataManager.instance.LoadStationSets(self)

    def LoadStationSetClicked(self):
        self.selectStationWindow.LoadStations()
        self.selectStationWindow.show()

    # Used for score change commands
    # Change <team>(0, 1) score by <change>(+X, -X)
    def CommandScoreChange(self, team: int, change: int):
        if team in (0, 1):
            scoreContainers = [
                self.scoreSpins[0],
                self.scoreSpins[1],
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
        if data.get("name") is not None:
            teamName = self.teamNameEdits[team]
            teamName.setText(str(data.get("name")))
            teamName.editingFinished.emit()
        if data.get("losers") is not None:
            self.losersChecks[team].setChecked(bool(data.get("losers")))
        if data.get("color"):
            self.CommandTeamColor(team, data.get("color"))

    def ClearScore(self):
        for c in (self.phaseCombo, self.matchCombo):
            c.setCurrentText("")
            c.lineEdit().editingFinished.emit()

        self.scoreSpins[0].setValue(0)
        self.scoreSpins[1].setValue(0)

        self.losersChecks[0].setChecked(False)
        self.losersChecks[1].setChecked(False)

    def CommandTeamColor(self, team: int, color, force_opponent=False):
        if color:
            value = None
            if type(color) is str:
                value = color
            if type(color) is int and color > 0:
                value = GameAssetManager.instance.colorModel.item(color).data(
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
                    for i in range(1, GameAssetManager.instance.colorModel.rowCount()):
                        current_menu_item_data = GameAssetManager.instance.colorModel.item(i).data(
                            Qt.ItemDataRole.UserRole
                        )
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
                self.matchCombo.setCurrentText(round_name)
                self.matchCombo.lineEdit().editingFinished.emit()
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
                            tournament_phase = LocaleHelper.phaseNames.get(
                                "top_n", "Top {0}"
                            ).format(round_division)
                        elif round_division <= 4:
                            tournament_phase = LocaleHelper.phaseNames.get(
                                "top_n", "Top {0}"
                            ).format(4)

                        # Include "Bracket - XYZ" similar to if it's Pools
                        if len(original_str) > 1:
                            tournament_phase = f"{original_str[0]} - {tournament_phase}"
                        elif "Top" not in phase:
                            tournament_phase = f"{phase} - {tournament_phase}"

                self.phaseCombo.setCurrentText(tournament_phase)
                self.phaseCombo.lineEdit().editingFinished.emit()
                StateManager.Set(f"score.{self.scoreboardNumber}.phase", tournament_phase)

            scoreContainers = [
                self.scoreSpins[0],
                self.scoreSpins[1],
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
                self.bestOfSpin.setValue(data.get("bestOf"))

            losersContainers = [
                self.losersChecks[0],
                self.losersChecks[1],
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
                            teamNames = [data.get("p1_name"), data.get("p2_name")]
                            if self.teamsSwapped:
                                teamNames.reverse()
                            self.teamNameEdits[t].setText(teamNames[t])
                            self.teamNameEdits[t].editingFinished.emit()

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
                        # Like edits made here: the saved mains stay
                        teamInstance[player].SavePlayerToDB(auto=True)
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
        self.RefreshSource()

    def SetOver(self, setId):
        if setId is None or str(setId) in self.finishedSets:
            return
        self.finishedSets.add(str(setId))
        self.signals.SetFinished.emit(setId)
        self.RefreshBanner()

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

        playerData = PlayerDB.GetPlayerFromTag(tag)
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
