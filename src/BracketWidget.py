# The bracket widget: brackets of any type, built here or loaded from
# start.gg, shown on stream through the "bracket" state.
#
# Its phases are a pool: phases built here (e.g. two round robin pools and
# a top cut), all drawing their players from one player list, and start.gg
# phase groups loaded into it, each with its own player list. A built
# phase's seeds can be players or results of another built phase, so the
# top cut fills itself in as the pools finish.
#
# What goes on stream is set by channels (BracketFocus), a tab each here:
# each shows a phase of the pool, with its own top N, focus and view, so
# several phases can be on screens at once. Channels on the same phase
# share its data.
import copy
import os
import traceback

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketExport import ExportBracket, RosterPath, TeamName
from .BracketFocus import BracketFocus, FocusChannel
from .BracketFocusBar import BracketFocusBar
from .BracketModel import *
from .BracketView import BracketView
from .DisplayOptions import DisplayOptionsButton
from .FlowLayout import FlowLayout
from .GameAssetManager import GameAssetManager
from .Helpers.BracketFocusHelper import MAIN_CHANNEL
from .PlayerList import PlayerList
from .Scheduler import (
    BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
    BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS,
    Scheduler,
)
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import ThemedIcon
from .TournamentDataManager import TournamentDataManager

SAVE_PATH = "./user_data/bracket_tournament.json"


def TypeName(type):
    return {
        TYPE_DOUBLE_ELIMINATION: QApplication.translate("app", "Double Elimination"),
        TYPE_SINGLE_ELIMINATION: QApplication.translate("app", "Single Elimination"),
        TYPE_ROUND_ROBIN: QApplication.translate("app", "Round Robin"),
        TYPE_SWISS: QApplication.translate("app", "Swiss"),
    }.get(type, type)


def Ordinal(n):
    return QApplication.translate("app", "#{0}").format(n)


class PhasesWindow(QWidget):
    """The phases and players, in a window of their own floating above the
    bracket widget: they're edited now and then, so they don't take room
    from the bracket. It keeps its size and place."""

    closed = Signal()

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle(QApplication.translate("app", "Phases and players"))
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(4, 4, 4, 4)
        self.resize(380, 640)
        geometry = SettingsManager.Get("bracket_phases_window", "")
        if geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
            except Exception:
                pass

    def SaveGeometry(self):
        SettingsManager.Set("bracket_phases_window", bytes(self.saveGeometry().toBase64()).decode())

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.isVisible():
            self.SaveGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self.SaveGeometry()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()


class BracketWidget(QDockWidget):
    instance: "BracketWidget" = None

    def __init__(self, *args):
        with StateManager.SaveBlock():
            super().__init__(*args)
            BracketWidget.instance = self
            self.SetupUi()

    # =====================================================
    # BUILDING THE UI
    # =====================================================
    def SetupUi(self):
        self.setWindowTitle(QApplication.translate("app", "Bracket"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setWindowFlags(Qt.WindowType.Window)

        StateManager.Set("bracket", {})

        self.tournament = BracketTournament()
        if BracketFocus.instance is None:
            BracketFocus.instance = BracketFocus()
        # The channel the widget shows (its view state is kept when another
        # tab is picked)
        self.shownChannel = None
        # Player lists: "local" (the phases built here) and one per start.gg
        # phase group, by its id
        self.rosters: dict[str, PlayerList] = {}
        # Names and bracket type of each start.gg phase group asked for, by
        # id, to build the bracket when its data comes in
        self.phaseGroupInfo = {}
        # The phase group the Load button asked for, to show it once it's in
        self.userLoad = None
        # Phase groups whose results are being fetched
        self.fetching = 0
        # Entrants of each loaded phase group, so mains fetched in the
        # background after the load can be applied to their slots
        self.groupEntrants = {}
        self.mainsApplied = {}
        # Don't react to our own changes to the phase controls
        self.updatingControls = False
        # The player list changes while the UI is being built
        self.ready = False

        self.saveTimer = QTimer(self)
        self.saveTimer.setSingleShot(True)
        self.saveTimer.setInterval(1000)
        self.saveTimer.timeout.connect(self.Save)

        contents = QWidget()
        contents.setLayout(QVBoxLayout())
        self.setWidget(contents)

        # A tab per channel
        tabsRow = QHBoxLayout()
        contents.layout().addLayout(tabsRow)
        self.channelTabs = QTabBar()
        self.channelTabs.setExpanding(False)
        self.channelTabs.setDocumentMode(True)
        self.channelTabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channelTabs.currentChanged.connect(self.ChannelTabPicked)
        self.channelTabs.customContextMenuRequested.connect(self.ChannelTabMenu)
        self.channelTabs.tabBarDoubleClicked.connect(
            lambda index: self.focusBar.RenameChannel() if index >= 0 else None
        )
        tabsRow.addWidget(self.channelTabs)
        btAddChannel = QToolButton()
        btAddChannel.setText("+")
        btAddChannel.setToolTip(
            QApplication.translate(
                "app",
                "New channel: shows a phase on its own, e.g. on another screen. Right-click a tab to rename or remove it.",
            )
        )
        btAddChannel.clicked.connect(lambda: self.focusBar.AddChannel())
        tabsRow.addWidget(btAddChannel)
        tabsRow.addStretch()

        # Loading from start.gg
        # The bars wrap their controls, so they don't set the window's width
        providerRow = FlowLayout()
        contents.layout().addLayout(providerRow)
        self.phaseSelection = QComboBox()
        self.phaseSelection.setMinimumWidth(160)
        self.phaseSelection.currentIndexChanged.connect(self.UpdatePhaseGroups)
        self.btRefreshPhase = QPushButton()
        self.btRefreshPhase.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.btRefreshPhase.setToolTip(QApplication.translate("app", "Reload the phases"))
        self.btRefreshPhase.clicked.connect(
            lambda: (
                TournamentDataManager.instance.GetTournamentPhases()
                if TournamentDataManager.instance.provider
                else None
            )
        )
        providerRow.addGroup(
            QLabel(QApplication.translate("app", "Phase")),
            self.phaseSelection,
            self.btRefreshPhase,
        )
        self.phaseGroupSelection = QComboBox()
        self.phaseGroupSelection.setMinimumWidth(120)
        providerRow.addGroup(
            QLabel(QApplication.translate("app", "Phase Group")), self.phaseGroupSelection
        )
        self.btLoadPhaseGroup = QPushButton(QApplication.translate("app", "Load"))
        self.btLoadPhaseGroup.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.btLoadPhaseGroup.setToolTip(
            QApplication.translate(
                "app",
                "Load the phase group, its players and its sets into the phases, and show it on this channel. Loading it again reloads it.",
            )
        )
        self.btLoadPhaseGroup.clicked.connect(self.PhaseGroupChanged)
        providerRow.addWidget(self.btLoadPhaseGroup)
        self.btRefreshSets = QPushButton(QApplication.translate("app", "Update sets"))
        self.btRefreshSets.setToolTip(
            QApplication.translate(
                "app",
                "Update only the set results of the loaded phase groups, without reloading their players",
            )
        )
        self.btRefreshSets.clicked.connect(lambda: self.RefreshSets())
        self.cbAutoUpdateSets = QCheckBox(QApplication.translate("app", "Auto update"))
        self.cbAutoUpdateSets.setToolTip(
            QApplication.translate(
                "app",
                "Update the set results of the loaded phase groups periodically. The interval can be changed in Settings > General.",
            )
        )
        self.labelAutoUpdateTimer = QLabel()
        providerRow.addGroup(self.btRefreshSets, self.cbAutoUpdateSets, self.labelAutoUpdateTimer)

        # The player list changes as it's built, which updates these
        self.view = BracketView()
        self.view.playerName = lambda player: TeamName(player, self.CurrentRosterPath())
        self.view.rosterIds = lambda: range(1, len(self.CurrentRoster().slotWidgets) + 1)
        self.view.signals.edited.connect(self.BracketEdited)
        self.standingsTable = QTableWidget()
        self.standingsTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.standingsTable.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.standingsTable.verticalHeader().setVisible(False)

        # Phases, phase options and the player list, in their own window
        self.phasesWindow = PhasesWindow(self)
        self.phasesWindow.closed.connect(lambda: self.btToggleSide.setChecked(False))
        left = QTabWidget()
        self.phasesWindow.layout().addWidget(left)

        # The tabs scroll, so the window can be smaller than their contents
        def Scrolling(tab):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(tab)
            return scroll

        left.addTab(Scrolling(self.BuildPhasesTab()), QApplication.translate("app", "Phases"))
        # The player list of the channel's phase
        self.playersStack = QStackedWidget()
        self.localPlayersPage = self.BuildPlayersTab()
        self.playersStack.addWidget(self.localPlayersPage)
        left.addTab(Scrolling(self.playersStack), QApplication.translate("app", "Players"))

        # The bracket
        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().setContentsMargins(0, 0, 0, 0)
        contents.layout().addWidget(right, 1)

        viewBar = FlowLayout()
        right.layout().addLayout(viewBar)
        self.btToggleSide = QPushButton(QApplication.translate("app", "Phases and players"))
        self.btToggleSide.setCheckable(True)
        self.btToggleSide.setIcon(ThemedIcon("./assets/icons/people.svg"))
        self.btToggleSide.setToolTip(
            QApplication.translate(
                "app", "Show or hide the window to edit the phases and the player lists"
            )
        )
        self.btToggleSide.toggled.connect(self.SetPhasesWindowShown)
        self.phaseTitle = QLabel()
        font = self.phaseTitle.font()
        font.setBold(True)
        self.phaseTitle.setFont(font)
        viewBar.addGroup(self.btToggleSide, self.phaseTitle)

        self.limitExport = QCheckBox(QApplication.translate("app", "Only show the top"))
        self.limitExport.setToolTip(
            QApplication.translate(
                "app",
                "Only the sets of players that can still finish in the top N are sent to this channel's layouts",
            )
        )
        self.limitExport.toggled.connect(self.ExportOptionsChanged)
        self.limitExportNumber = QSpinBox()
        self.limitExportNumber.setMinimum(2)
        self.limitExportNumber.setMaximum(1024)
        self.limitExportNumber.setValue(8)
        self.limitExportNumber.valueChanged.connect(self.ExportOptionsChanged)
        viewBar.addGroup(self.limitExport, self.limitExportNumber)

        self.btClearEdits = QPushButton(QApplication.translate("app", "Clear manual changes"))
        self.btClearEdits.setToolTip(
            QApplication.translate(
                "app",
                "Puts back the players the bracket gives each set, undoing players placed by hand",
            )
        )
        self.btClearEdits.clicked.connect(self.ClearManualChanges)
        viewBar.addWidget(self.btClearEdits)

        btFit = QPushButton(QApplication.translate("app", "Fit"))
        btFit.clicked.connect(lambda: self.view.FitInView())
        viewBar.addWidget(btFit)

        BracketFocus.instance.signals.channelsChanged.connect(self.ChannelsChanged)
        BracketFocus.instance.signals.settingsChanged.connect(self.ChannelSettingsChanged)
        self.focusBar = BracketFocusBar(self.view)
        right.layout().addWidget(self.focusBar)

        viewSplitter = QSplitter(Qt.Orientation.Vertical)
        right.layout().addWidget(viewSplitter, 1)

        viewSplitter.addWidget(self.view)
        viewSplitter.addWidget(self.standingsTable)
        viewSplitter.setSizes([3, 1])

        # Hidden until needed
        self.btToggleSide.setChecked(SettingsManager.Get("bracket_phases_window_shown", False))

        TournamentDataManager.instance.signals.tournament_phases_updated.connect(self.UpdatePhases)
        TournamentDataManager.instance.signals.tournament_phasegroup_updated.connect(
            self.UpdatePhaseGroup
        )
        TournamentDataManager.instance.signals.player_mains_updated.connect(self.ApplyFetchedMains)
        TournamentDataManager.instance.signals.tournament_phasegroup_sets_updated.connect(
            self.ApplySetsUpdate
        )
        GameAssetManager.instance.signals.onLoad.connect(self.SetDefaultsFromAssets)

        Scheduler.instance.Register(
            "bracket_sets",
            self.AutoUpdateSets,
            SettingsManager.Get(
                "general.bracket_auto_update_interval", BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS
            )
            * 1000,
            BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS * 1000,
        )
        Scheduler.instance.signals.job_state_changed.connect(
            lambda name: self.UpdateAutoUpdateTimer() if name == "bracket_sets" else None
        )
        Scheduler.instance.signals.tick.connect(self.UpdateAutoUpdateTimer)
        autoUpdate = SettingsManager.Get("general.bracket_auto_update", False)
        self.cbAutoUpdateSets.setChecked(autoUpdate)
        if autoUpdate:
            Scheduler.instance.Start("bracket_sets")
        self.UpdateAutoUpdateTimer()
        self.cbAutoUpdateSets.toggled.connect(self.ToggleAutoUpdateSets)

        # Changes from the last second are saved on the way out
        QApplication.instance().aboutToQuit.connect(
            lambda: self.Save() if self.saveTimer.isActive() else None
        )

        # bracket.players follows the main channel's player list, which can
        # change without the widget hearing of it (e.g. characters loading)
        self.mirrorTimer = QTimer(self)
        self.mirrorTimer.setInterval(1000)
        self.mirrorTimer.timeout.connect(self.MirrorPlayers)
        self.mirrorTimer.start()

        self.UpdateTabs()
        self.ready = True
        self.Load()

    # Building the UI
    def BuildPhasesTab(self):
        tab = QWidget()
        tab.setLayout(QVBoxLayout())

        self.phaseList = QListWidget()
        self.phaseList.setMaximumHeight(120)
        self.phaseList.currentRowChanged.connect(self.PhaseSelected)
        tab.layout().addWidget(self.phaseList)

        buttons = QHBoxLayout()
        tab.layout().addLayout(buttons)
        btAdd = QPushButton(QApplication.translate("app", "New phase"))
        btAdd.clicked.connect(self.NewPhase)
        buttons.addWidget(btAdd)
        self.btRemovePhase = QPushButton(QApplication.translate("app", "Remove"))
        self.btRemovePhase.clicked.connect(self.RemovePhase)
        buttons.addWidget(self.btRemovePhase)

        self.phaseOptions = QWidget()
        form = QFormLayout()
        self.phaseOptions.setLayout(form)
        tab.layout().addWidget(self.phaseOptions)

        self.phaseName = QLineEdit()
        self.phaseName.editingFinished.connect(self.PhaseNameChanged)
        form.addRow(QApplication.translate("app", "Name"), self.phaseName)

        self.phaseType = QComboBox()
        for type in BRACKET_TYPES:
            self.phaseType.addItem(TypeName(type), type)
        self.phaseType.currentIndexChanged.connect(self.StructureChanged)
        form.addRow(QApplication.translate("app", "Type"), self.phaseType)

        self.seedCount = QSpinBox()
        self.seedCount.setRange(2, 1024)
        self.seedCount.valueChanged.connect(self.SeedCountChanged)
        form.addRow(QApplication.translate("app", "Players"), self.seedCount)

        self.losersSeedCount = QSpinBox()
        self.losersSeedCount.setRange(0, 512)
        self.losersSeedCount.setToolTip(
            QApplication.translate(
                "app",
                "How many of the seeds start on the losers side (e.g. players coming from pools they didn't win). They're the last seeds.",
            )
        )
        self.losersSeedCount.valueChanged.connect(self.StructureChanged)
        form.addRow(QApplication.translate("app", "Starting in losers"), self.losersSeedCount)

        self.grandFinalReset = QCheckBox()
        self.grandFinalReset.toggled.connect(self.StructureChanged)
        form.addRow(QApplication.translate("app", "Grand final reset"), self.grandFinalReset)

        self.thirdPlace = QCheckBox()
        self.thirdPlace.toggled.connect(self.StructureChanged)
        form.addRow(QApplication.translate("app", "3rd place match"), self.thirdPlace)

        self.progressionsOut = QSpinBox()
        self.progressionsOut.setRange(0, 512)
        self.progressionsOut.setToolTip(
            QApplication.translate(
                "app",
                "How many players go on to another phase instead of playing to a champion. Double elimination sends half from each side.",
            )
        )
        self.progressionsOut.valueChanged.connect(self.StructureChanged)
        form.addRow(QApplication.translate("app", "Players going on"), self.progressionsOut)

        swiss = QHBoxLayout()
        self.swissRounds = QSpinBox()
        self.swissRounds.setRange(1, 99)
        self.swissRounds.valueChanged.connect(self.SwissRoundsChanged)
        swiss.addWidget(self.swissRounds)
        self.btPairNext = QPushButton(QApplication.translate("app", "Pair next round"))
        self.btPairNext.setToolTip(
            QApplication.translate(
                "app",
                "Pairs the next round from the current standings, avoiding rematches. Every set of the last round has to be finished first.",
            )
        )
        self.btPairNext.clicked.connect(self.PairNextRound)
        swiss.addWidget(self.btPairNext)
        self.btUnpairLast = QPushButton(QApplication.translate("app", "Remove last round"))
        self.btUnpairLast.clicked.connect(self.UnpairLastRound)
        swiss.addWidget(self.btUnpairLast)
        self.swissRow = QWidget()
        self.swissRow.setLayout(swiss)
        swiss.setContentsMargins(0, 0, 0, 0)
        form.addRow(QApplication.translate("app", "Swiss rounds"), self.swissRow)

        seedsLabel = QLabel(QApplication.translate("app", "Seeds"))
        font = seedsLabel.font()
        font.setBold(True)
        seedsLabel.setFont(font)
        tab.layout().addWidget(seedsLabel)

        self.seedsTable = QTableWidget()
        self.seedsTable.setColumnCount(1)
        self.seedsTable.horizontalHeader().setVisible(False)
        self.seedsTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.seedsTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.seedsTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tab.layout().addWidget(self.seedsTable)

        seedButtons = QHBoxLayout()
        tab.layout().addLayout(seedButtons)
        self.btSeedUp = QPushButton("▲")
        self.btSeedUp.setToolTip(QApplication.translate("app", "Move the seed up"))
        self.btSeedUp.clicked.connect(lambda: self.MoveSeed(-1))
        seedButtons.addWidget(self.btSeedUp)
        self.btSeedDown = QPushButton("▼")
        self.btSeedDown.setToolTip(QApplication.translate("app", "Move the seed down"))
        self.btSeedDown.clicked.connect(lambda: self.MoveSeed(1))
        seedButtons.addWidget(self.btSeedDown)
        self.btSeedFromPhases = QPushButton(QApplication.translate("app", "Take from phases..."))
        self.btSeedFromPhases.setToolTip(
            QApplication.translate(
                "app",
                "Seeds this phase with the top players of other phases, spread out so players from the same pool don't meet early",
            )
        )
        self.btSeedFromPhases.clicked.connect(self.SeedFromPhases)
        seedButtons.addWidget(self.btSeedFromPhases)
        self.btSeedFromList = QPushButton(QApplication.translate("app", "Player list order"))
        self.btSeedFromList.setToolTip(
            QApplication.translate("app", "Seeds this phase with the player list, in its order")
        )
        self.btSeedFromList.clicked.connect(self.SeedFromPlayerList)
        seedButtons.addWidget(self.btSeedFromList)

        self.btRebuild = QPushButton(QApplication.translate("app", "Rebuild bracket"))
        self.btRebuild.setToolTip(
            QApplication.translate(
                "app", "Builds the bracket again from the seeds, clearing its results"
            )
        )
        self.btRebuild.clicked.connect(lambda: self.Rebuild(ask=True))
        tab.layout().addWidget(self.btRebuild)

        self.providerNotice = QLabel(
            QApplication.translate(
                "app",
                "Loaded from start.gg: results come from start.gg. Changes made here only affect what's shown on stream.",
            )
        )
        self.providerNotice.setWordWrap(True)
        tab.layout().addWidget(self.providerNotice)

        return tab

    def BuildPlayersTab(self):
        tab = QWidget()
        tab.setLayout(QVBoxLayout())

        row = QHBoxLayout()
        tab.layout().addLayout(row)

        self.playerList = PlayerList(base=RosterPath())
        self.rosters["local"] = self.playerList

        def Spin(label, minimum, setter):
            col = QVBoxLayout()
            col.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setMinimum(minimum)
            spin.setMaximum(1024)
            spin.valueChanged.connect(setter)
            col.addWidget(spin)
            row.addLayout(col)
            return spin

        self.slotNumber = Spin(
            QApplication.translate("app", "Number of slots"), 2, self.RosterSizeChanged
        )
        self.playerPerTeam = Spin(
            QApplication.translate("app", "Players per slot"),
            1,
            lambda val: self.playerList.SetPlayersPerTeam(val),
        )
        self.charNumber = Spin(
            QApplication.translate("app", "Characters per player"),
            0,
            self.CharactersPerPlayerChanged,
        )

        self.displayOptions = DisplayOptionsButton("bracket_display_options")
        self.displayOptions.changed.connect(
            lambda: [
                roster.SetHiddenElements(self.displayOptions.HiddenElements())
                for roster in self.rosters.values()
            ]
        )
        self.playerList.SetHiddenElements(self.displayOptions.HiddenElements())
        row.addWidget(self.displayOptions, 0, Qt.AlignmentFlag.AlignBottom)

        tab.layout().addWidget(self.playerList)
        self.playerList.signals.DataChanged.connect(self.PlayersChanged)

        self.slotNumber.blockSignals(True)
        self.slotNumber.setValue(8)
        self.slotNumber.blockSignals(False)
        self.playerList.SetSlotNumber(8)
        # Already at 1, so setting it wouldn't apply it
        self.playerList.SetPlayersPerTeam(1)
        self.charNumber.setValue(1)
        return tab

    # =====================================================
    # WINDOW
    # =====================================================
    def showEvent(self, event):
        super().showEvent(event)
        # The phases window comes back with the widget, if it was open
        if self.btToggleSide.isChecked():
            QTimer.singleShot(0, lambda: self.SetPhasesWindowShown(True))

    def hideEvent(self, event):
        super().hideEvent(event)
        self.phasesWindow.hide()

    def SetPhasesWindowShown(self, shown):
        # While the widget is hidden, it's shown with it (showEvent)
        if shown and self.isVisible():
            self.phasesWindow.show()
            self.phasesWindow.raise_()
            self.phasesWindow.activateWindow()
        elif not shown:
            self.phasesWindow.hide()
        if SettingsManager.Get("bracket_phases_window_shown", False) != shown:
            SettingsManager.Set("bracket_phases_window_shown", shown)

    # =====================================================
    # PHASES
    # =====================================================
    # Phases
    def CurrentPhase(self) -> BracketPhase:
        """The current channel's phase."""
        phase = self.Ch().phase
        return self.tournament.GetPhase(phase) if phase else None

    def NewPhase(self, type=TYPE_DOUBLE_ELIMINATION, name=None):
        phase = BracketPhase(
            self.tournament.NewPhaseId(),
            name
            or QApplication.translate("app", "Phase {0}").format(len(self.tournament.phases) + 1),
            type,
        )
        phase.seedSources = [{"type": "player", "player": p} for p in self.RosterIds()]
        phase.Generate(self.tournament.SeedPlayers(phase))
        self.tournament.AddPhase(phase)
        # Shown on this channel
        self.Ch().SetPhase(phase.id)
        self.saveTimer.start()
        return phase

    def RemovePhase(self):
        phase = self.CurrentPhase()
        if phase is None:
            return
        text = QApplication.translate("app", "Remove {0}? Its results will be lost.").format(
            phase.name
        )
        others = [n for n in BracketFocus.instance.ChannelsOn(phase.id) if n != self.Ch().name]
        if others:
            text += "\n\n" + QApplication.translate(
                "app", "These channels show it too, and will show another phase: {0}"
            ).format(", ".join(others))
        if (
            QMessageBox.question(self, QApplication.translate("app", "Remove phase"), text)
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.tournament.RemovePhase(phase.id)
        if phase.providerPhaseGroupId is not None:
            id = str(phase.providerPhaseGroupId)
            self.DropRoster(id)
            self.groupEntrants.pop(id, None)
        self.tournament.Resolve()
        if not self.tournament.phases:
            self.NewPhase()
        # Its channels show the first phase
        self.FixChannelPhases()
        self.saveTimer.start()

    def RefreshPhaseList(self):
        """The phases, with the channels showing each. The current
        channel's is selected."""
        self.phaseList.blockSignals(True)
        self.phaseList.clear()
        for phase in self.tournament.phases:
            text = f"{phase.name} ({TypeName(phase.type)})"
            if phase.providerPhaseGroupId is not None:
                text += " · start.gg"
            channels = BracketFocus.instance.ChannelsOn(phase.id)
            if channels:
                text += "  ◀ " + ", ".join(channels)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, phase.id)
            self.phaseList.addItem(item)
        index = next(
            (i for i, p in enumerate(self.tournament.phases) if p.id == self.Ch().phase), -1
        )
        self.phaseList.setCurrentRow(index)
        self.phaseList.blockSignals(False)

    def PhaseSelected(self, row):
        # Picking a phase shows it on the current channel
        if 0 <= row < len(self.tournament.phases):
            self.Ch().SetPhase(self.tournament.phases[row].id)

    def PhaseNameChanged(self):
        phase = self.CurrentPhase()
        if phase is None or self.updatingControls:
            return
        phase.name = self.phaseName.text().strip() or phase.name
        self.RefreshPhaseList()
        self.Changed(rebuildView=False)

    def UpdateControls(self):
        phase = self.CurrentPhase()
        self.updatingControls = True
        try:
            self.phaseOptions.setEnabled(phase is not None)
            if phase is None:
                return
            local = phase.bracket is None or not phase.bracket.fromProvider
            self.phaseName.setText(phase.name)
            self.phaseType.setCurrentIndex(max(0, self.phaseType.findData(phase.type)))
            self.seedCount.setValue(max(2, len(phase.seedSources)))
            self.losersSeedCount.setMaximum(max(0, len(phase.seedSources) - 2))
            self.losersSeedCount.setValue(phase.losersSeedCount)
            self.grandFinalReset.setChecked(phase.grandFinalReset)
            self.thirdPlace.setChecked(phase.thirdPlace)
            self.progressionsOut.setValue(phase.progressionsOut)
            self.swissRounds.setValue(
                max(1, phase.bracket.totalRounds if phase.bracket else phase.swissRounds or 1)
            )

            double = phase.type == TYPE_DOUBLE_ELIMINATION
            single = phase.type == TYPE_SINGLE_ELIMINATION
            swiss = phase.type == TYPE_SWISS
            form: QFormLayout = self.phaseOptions.layout()
            for widget, visible in (
                (self.losersSeedCount, double),
                (self.grandFinalReset, double),
                (self.thirdPlace, single),
                (self.progressionsOut, double or single),
                (self.swissRow, swiss),
            ):
                widget.setVisible(visible)
                label = form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)

            for widget in (
                self.phaseType,
                self.seedCount,
                self.losersSeedCount,
                self.grandFinalReset,
                self.thirdPlace,
                self.progressionsOut,
                self.swissRounds,
                self.seedsTable,
                self.btSeedUp,
                self.btSeedDown,
                self.btSeedFromPhases,
                self.btSeedFromList,
                self.btRebuild,
            ):
                widget.setEnabled(local)
            bracket = phase.bracket
            self.btPairNext.setEnabled(local and bracket is not None and bracket.CanPairNextRound())
            self.btUnpairLast.setEnabled(
                local and bracket is not None and len(bracket.PoolRounds()) > 1
            )
            self.providerNotice.setVisible(not local)
            self.btRemovePhase.setEnabled(len(self.tournament.phases) > 1)
            self.btRefreshSets.setEnabled(bool(self.ProviderPhases()) and not self.fetching)
            self.RefreshSeedsTable()
        finally:
            self.updatingControls = False

    # =====================================================
    # SEEDS
    # =====================================================
    def SeedSourceOptions(self, phase):
        """(label, source) for every seed source this phase can take."""
        options = [(QApplication.translate("app", "Bye"), None)]
        for p in self.RosterIds():
            options.append(
                (
                    f"{TeamName(p) or QApplication.translate('app', 'Player {0}').format(p)}",
                    {"type": "player", "player": p},
                )
            )
        for other in self.tournament.phases:
            # start.gg's phase groups have their own players
            if (
                other.id == phase.id
                or self.tournament.DependsOn(other, phase)
                or other.bracket is None
                or other.providerPhaseGroupId is not None
            ):
                continue
            for place in range(1, len(other.bracket.Results()) + 1):
                if other.bracket.progressionsOut > 0:
                    label = QApplication.translate("app", "{0}: going on {1}").format(
                        other.name, Ordinal(place)
                    )
                else:
                    label = QApplication.translate("app", "{0}: {1}").format(
                        other.name, Ordinal(place)
                    )
                options.append((label, {"type": "result", "phase": other.id, "place": place}))
        return options

    def RefreshSeedsTable(self):
        phase = self.CurrentPhase()
        self.seedsTable.blockSignals(True)
        self.seedsTable.setRowCount(0)
        if phase is None:
            self.seedsTable.blockSignals(False)
            return
        options = self.SeedSourceOptions(phase)
        winners = (
            phase.WinnersSeedCount()
            if phase.type == TYPE_DOUBLE_ELIMINATION
            else len(phase.seedSources)
        )
        self.seedsTable.setRowCount(len(phase.seedSources))
        labels = []
        for i, source in enumerate(phase.seedSources):
            if i < winners:
                labels.append(str(i + 1))
            else:
                labels.append(QApplication.translate("app", "L{0}").format(i - winners + 1))
            combo = QComboBox()
            for label, value in options:
                combo.addItem(label, value)
            index = next((j for j, (_l, value) in enumerate(options) if value == source), 0)
            combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(
                lambda _i, row=i, combo=combo: self.SeedSourceChanged(row, combo.currentData())
            )
            self.seedsTable.setCellWidget(i, 0, combo)
        self.seedsTable.setVerticalHeaderLabels(labels)
        self.seedsTable.blockSignals(False)

    def SeedSourceChanged(self, row, source):
        phase = self.CurrentPhase()
        if phase is None or row >= len(phase.seedSources):
            return
        phase.seedSources[row] = source
        # Who plays changed, not the bracket itself: results are kept
        self.tournament.Resolve()
        self.view.Refresh()
        self.Changed(rebuildView=False)

    def MoveSeed(self, offset):
        phase = self.CurrentPhase()
        row = self.seedsTable.currentRow()
        if phase is None or row < 0:
            return
        target = row + offset
        if not 0 <= target < len(phase.seedSources):
            return
        sources = phase.seedSources
        sources[row], sources[target] = sources[target], sources[row]
        self.tournament.Resolve()
        self.RefreshSeedsTable()
        self.seedsTable.setCurrentCell(target, 0)
        self.view.Refresh()
        self.Changed(rebuildView=False)

    def SeedFromPlayerList(self):
        phase = self.CurrentPhase()
        if phase is None:
            return
        players = self.RosterIds()
        phase.seedSources = [{"type": "player", "player": p} for p in players]
        phase.losersSeedCount = min(phase.losersSeedCount, max(0, len(players) - 2))
        self.Rebuild(ask=True)

    def SeedFromPhases(self):
        phase = self.CurrentPhase()
        if phase is None:
            return
        others = [
            p
            for p in self.tournament.phases
            if p.id != phase.id
            and not self.tournament.DependsOn(p, phase)
            and p.bracket is not None
            and p.providerPhaseGroupId is None
        ]
        if not others:
            QMessageBox.information(
                self,
                QApplication.translate("app", "Take from phases"),
                QApplication.translate("app", "Add other phases (e.g. pools) first."),
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(QApplication.translate("app", "Take from phases"))
        dialog.setLayout(QVBoxLayout())
        dialog.layout().addWidget(
            QLabel(QApplication.translate("app", "Phases to take players from:"))
        )
        checks = []
        for other in others:
            check = QCheckBox(other.name)
            check.setChecked(other.type in POOL_TYPES or other.progressionsOut > 0)
            dialog.layout().addWidget(check)
            checks.append((check, other))
        row = QHBoxLayout()
        row.addWidget(QLabel(QApplication.translate("app", "Players from each phase")))
        perPhase = QSpinBox()
        perPhase.setRange(1, 256)
        perPhase.setValue(2)
        row.addWidget(perPhase)
        dialog.layout().addLayout(row)
        losers = QCheckBox(
            QApplication.translate(
                "app", "Players after the first place of each phase start in losers"
            )
        )
        losers.setVisible(phase.type == TYPE_DOUBLE_ELIMINATION)
        dialog.layout().addWidget(losers)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.layout().addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        chosen = [other.id for check, other in checks if check.isChecked()]
        if not chosen:
            return
        sources = SnakeSeeding(chosen, perPhase.value())
        phase.losersSeedCount = 0
        if losers.isChecked() and phase.type == TYPE_DOUBLE_ELIMINATION and perPhase.value() > 1:
            # Each phase's winner starts in winners, everyone else in losers
            firsts = [s for s in sources if s["place"] == 1]
            rest = [s for s in sources if s["place"] > 1]
            sources = firsts + rest
            phase.losersSeedCount = len(rest)
        phase.seedSources = sources
        self.Rebuild(ask=True)

    def SeedCountChanged(self, count):
        phase = self.CurrentPhase()
        if phase is None or self.updatingControls:
            return
        sources = phase.seedSources
        used = {s.get("player") for s in sources if s and s.get("type") == "player"}
        while len(sources) < count:
            nextPlayer = next((p for p in self.RosterIds() if p not in used), None)
            sources.append({"type": "player", "player": nextPlayer} if nextPlayer else None)
            if nextPlayer:
                used.add(nextPlayer)
        del sources[count:]
        phase.losersSeedCount = min(phase.losersSeedCount, max(0, count - 2))
        self.Rebuild(ask=True)

    # =====================================================
    # BRACKET STRUCTURE
    # =====================================================
    def StructureChanged(self, *args):
        phase = self.CurrentPhase()
        if phase is None or self.updatingControls:
            return
        phase.type = self.phaseType.currentData()
        phase.losersSeedCount = (
            self.losersSeedCount.value() if phase.type == TYPE_DOUBLE_ELIMINATION else 0
        )
        phase.grandFinalReset = self.grandFinalReset.isChecked()
        phase.thirdPlace = self.thirdPlace.isChecked()
        phase.progressionsOut = self.progressionsOut.value()
        self.Rebuild(ask=True)

    def SwissRoundsChanged(self, value):
        phase = self.CurrentPhase()
        if phase is None or self.updatingControls or phase.bracket is None:
            return
        phase.swissRounds = value
        phase.bracket.totalRounds = max(value, len(phase.bracket.PoolRounds()))
        self.UpdateControls()
        self.Changed(rebuildView=False)

    def PairNextRound(self):
        phase = self.CurrentPhase()
        if phase and phase.bracket and phase.bracket.CanPairNextRound():
            phase.bracket.PairNextRound()
            self.Changed()

    def UnpairLastRound(self):
        phase = self.CurrentPhase()
        if phase and phase.bracket and phase.bracket.UnpairLastRound():
            self.Changed()

    def Rebuild(self, ask=False):
        """Builds the phase's bracket again from its options and seeds."""
        phase = self.CurrentPhase()
        if phase is None:
            return
        hasResults = phase.bracket is not None and any(
            m.finished and not m.isBye for m in phase.bracket.matches.values()
        )
        if ask and hasResults:
            answer = QMessageBox.question(
                self,
                QApplication.translate("app", "Rebuild bracket"),
                QApplication.translate(
                    "app", "This builds {0} again and clears its results. Continue?"
                ).format(phase.name),
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.UpdateControls()
                return
        roundNames = phase.bracket.roundNames if phase.bracket else {}
        try:
            phase.Generate(self.tournament.SeedPlayers(phase))
            if phase.bracket.type == phase.type:
                phase.bracket.roundNames = roundNames
        except Exception:
            logger.error(traceback.format_exc())
        self.tournament.Resolve()
        self.RefreshPhaseList()
        self.Changed()

    def ClearManualChanges(self):
        phase = self.CurrentPhase()
        if phase and phase.bracket:
            phase.bracket.ClearOverrides()
            self.Changed(rebuildView=False)
            self.view.Refresh()

    # Changes
    def BracketEdited(self):
        # Results of this phase can be the seeds of another
        self.tournament.Resolve()
        self.Changed(rebuildView=False)

    # =====================================================
    # UPDATING AFTER CHANGES
    # =====================================================
    def PlayersChanged(self):
        if not self.ready:
            return
        self.view.Refresh()
        self.UpdateView()
        self.saveTimer.start()

    def RosterSizeChanged(self, value):
        self.playerList.SetSlotNumber(value)
        if self.ready and self.CurrentPhase() is not None:
            self.RefreshSeedsTable()

    def ExportOptionsChanged(self, *args):
        # The channel's top N
        self.Ch().SetLimit(self.limitExportNumber.value() if self.limitExport.isChecked() else None)

    def Changed(self, rebuildView=True):
        phase = self.CurrentPhase()
        if rebuildView:
            self.view.SetBracket(phase.bracket if phase else None, fit=False)
        self.UpdateControls()
        self.UpdateView()
        self.saveTimer.start()

    def UpdateView(self):
        phase = self.CurrentPhase()
        self.phaseTitle.setText(phase.name if phase else "")
        bracket = phase.bracket if phase else None
        self.btClearEdits.setVisible(bracket is not None and bracket.HasOverrides())
        pool = bracket is not None and bracket.IsPool()
        self.standingsTable.setVisible(pool)
        self.limitExport.setEnabled(not pool)
        self.limitExportNumber.setEnabled(not pool)
        if pool:
            self.UpdateStandingsTable(bracket)
        with StateManager.SaveBlock():
            self.ExportBracketState()

    def UpdateStandingsTable(self, bracket):
        columns = [
            ("rank", QApplication.translate("app", "Rank")),
            ("seed", QApplication.translate("app", "Seed")),
            ("playerName", QApplication.translate("app", "Name")),
            ("wins", QApplication.translate("app", "W")),
            ("losses", QApplication.translate("app", "L")),
            ("draws", QApplication.translate("app", "D")),
            ("points", QApplication.translate("app", "Points")),
            ("games", QApplication.translate("app", "Games")),
            ("gameDiff", QApplication.translate("app", "Game diff.")),
        ]
        if bracket.type == TYPE_SWISS:
            columns.append(("buchholz", QApplication.translate("app", "Buchholz")))
        standings = bracket.GetStandings()
        self.standingsTable.setColumnCount(len(columns))
        self.standingsTable.setHorizontalHeaderLabels([c[1] for c in columns])
        self.standingsTable.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.standingsTable.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.standingsTable.setRowCount(len(standings))
        for r, row in enumerate(standings):
            for c, (key, _label) in enumerate(columns):
                if key == "games":
                    value = f"{row['gameWins']}-{row['gameLosses']}"
                elif key == "gameDiff":
                    value = f"{row['gameDiff']:+d}"
                elif key == "playerName":
                    value = TeamName(row["playerId"], self.CurrentRosterPath())
                elif key == "seed":
                    value = str(bracket.SeedOf(row["playerId"]))
                else:
                    value = str(row.get(key, ""))
                item = QTableWidgetItem(value)
                if key != "playerName":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.standingsTable.setItem(r, c, item)

    # =====================================================
    # CHANNELS
    # =====================================================
    # Channels: a tab each. The widget shows the current channel's phase,
    # its top N and its view of the bracket (zoom, scroll and selection)
    def Ch(self) -> FocusChannel:
        return BracketFocus.instance.Current()

    def UpdateTabs(self):
        focus = BracketFocus.instance
        self.channelTabs.blockSignals(True)
        while self.channelTabs.count():
            self.channelTabs.removeTab(0)
        for name in focus.channels:
            index = self.channelTabs.addTab(name)
            self.channelTabs.setTabData(index, name)
            self.channelTabs.setTabToolTip(
                index,
                QApplication.translate(
                    "app", "Layouts show this channel with ?channel={0} in their URL"
                ).format(name)
                if name != MAIN_CHANNEL
                else QApplication.translate(
                    "app", "Layouts without ?channel= in their URL show this channel"
                ),
            )
        names = list(focus.channels)
        self.channelTabs.setCurrentIndex(names.index(focus.current))
        self.channelTabs.blockSignals(False)

    def ChannelTabPicked(self, index):
        name = self.channelTabs.tabData(index)
        if name and name != BracketFocus.instance.current:
            self.SaveViewState()
            BracketFocus.instance.SetCurrent(name)

    def ChannelTabMenu(self, pos):
        index = self.channelTabs.tabAt(pos)
        if index < 0:
            return
        name = self.channelTabs.tabData(index)
        if name != BracketFocus.instance.current:
            self.channelTabs.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction(QApplication.translate("app", "New channel..."), self.focusBar.AddChannel)
        rename = menu.addAction(
            QApplication.translate("app", "Rename channel..."), self.focusBar.RenameChannel
        )
        remove = menu.addAction(
            QApplication.translate("app", "Remove channel"), self.focusBar.RemoveChannel
        )
        rename.setEnabled(name != MAIN_CHANNEL)
        remove.setEnabled(name != MAIN_CHANNEL)
        menu.exec(self.channelTabs.mapToGlobal(pos))

    def ChannelsChanged(self):
        """Channels were added, removed or renamed, or another tab was picked."""
        self.UpdateTabs()
        self.FixChannelPhases()
        self.ShowChannel()

    def ChannelSettingsChanged(self, name):
        """A channel's phase or top N changed, here or from the web page."""
        if not self.ready:
            return
        if name == BracketFocus.instance.current:
            phase = self.CurrentPhase()
            if self.view.bracket is not (phase.bracket if phase else None):
                self.ShowChannel()
                return
            self.view.exportLimit = self.Ch().limit
            self.UpdateLimitControls()
            self.view.Refresh()
        self.RefreshPhaseList()
        self.UpdateView()

    def FixChannelPhases(self):
        """Channels showing a phase that isn't there show the first one."""
        ids = [p.id for p in self.tournament.phases]
        for channel in list(BracketFocus.instance.channels.values()):
            if channel.phase not in ids:
                channel.SetPhase(ids[0] if ids else None)

    def SaveViewState(self):
        channel = BracketFocus.instance.channels.get(self.shownChannel)
        if channel is None:
            return
        channel.viewState = {
            "phase": channel.phase,
            "transform": self.view.transform(),
            "scroll": (
                self.view.horizontalScrollBar().value(),
                self.view.verticalScrollBar().value(),
            ),
            "selected": set(self.view.selected),
            "rounds": set(self.view.selectedRounds),
        }

    def ShowChannel(self):
        """Shows the current channel: its phase, players, top N and view."""
        channel = self.Ch()
        phase = self.CurrentPhase()
        self.shownChannel = channel.name
        self.view.exportLimit = channel.limit
        self.UpdateLimitControls()

        state = channel.viewState
        if state is not None and state.get("phase") != channel.phase:
            state = None
        self.view.SetBracket(phase.bracket if phase else None, fit=state is None)
        if state is not None:
            self.view.setTransform(state["transform"])
            h, v = state["scroll"]
            QTimer.singleShot(
                0,
                lambda: (
                    self.view.horizontalScrollBar().setValue(h),
                    self.view.verticalScrollBar().setValue(v),
                ),
            )
            self.view.SetSelection(state["selected"], state["rounds"])
        else:
            self.view.SetSelection(set(), set())

        self.playersStack.setCurrentWidget(self.RosterPage(self.RosterKey(phase)))
        self.RefreshPhaseList()
        self.UpdateControls()
        self.UpdateView()
        self.focusBar.UpdateFocus()

    def UpdateLimitControls(self):
        limit = self.Ch().limit
        for widget in (self.limitExport, self.limitExportNumber):
            widget.blockSignals(True)
        self.limitExport.setChecked(limit is not None)
        if limit is not None:
            self.limitExportNumber.setValue(limit)
        for widget in (self.limitExport, self.limitExportNumber):
            widget.blockSignals(False)

    # =====================================================
    # PLAYER LISTS
    # =====================================================
    def RosterIds(self):
        return list(range(1, len(self.playerList.slotWidgets) + 1))

    # Player lists: the phases built here share one, each start.gg phase
    # group has its own
    def RosterKey(self, phase):
        if phase is not None and phase.providerPhaseGroupId is not None:
            return str(phase.providerPhaseGroupId)
        return "local"

    def CurrentRosterPath(self):
        return RosterPath(self.RosterKey(self.CurrentPhase()))

    def CurrentRoster(self) -> PlayerList:
        return self.rosters.get(self.RosterKey(self.CurrentPhase())) or self.playerList

    def RosterPage(self, key):
        roster = self.rosters.get(key)
        return getattr(roster, "page", None) or self.localPlayersPage

    def GroupRoster(self, id) -> PlayerList:
        """A start.gg phase group's player list, made the first time."""
        id = str(id)
        if id in self.rosters:
            return self.rosters[id]
        page = QWidget()
        page.setLayout(QVBoxLayout())
        title = QLabel()
        title.setWordWrap(True)
        page.layout().addWidget(title)
        roster = PlayerList(base=RosterPath(id))
        roster.SetCharactersPerPlayer(self.playerList.charactersPerPlayer)
        roster.SetHiddenElements(self.displayOptions.HiddenElements())
        roster.signals.DataChanged.connect(self.PlayersChanged)
        page.layout().addWidget(roster)
        self.playersStack.addWidget(page)
        roster.page = page
        roster.title = title
        self.rosters[id] = roster
        return roster

    def DropRoster(self, id):
        roster = self.rosters.pop(str(id), None)
        if roster is None:
            return
        self.playersStack.removeWidget(roster.page)
        roster.page.deleteLater()
        StateManager.Unset(RosterPath(str(id)))

    def MirrorPlayers(self):
        """bracket.players is the main channel's player list, for layouts
        reading it."""
        main = BracketFocus.instance.channels[MAIN_CHANNEL]
        phase = self.tournament.GetPhase(main.phase) if main.phase else None
        players = StateManager.Get(RosterPath(self.RosterKey(phase)), {}) or {}
        if players != (StateManager.Get("bracket.players", {}) or {}):
            StateManager.Set("bracket.players", copy.deepcopy(players))

    # Saving, so a tournament run in HyperDrive survives a restart. The
    # channels are saved in the settings (BracketFocus).
    def RosterSnapshot(self, key="local"):
        roster = []
        count = len(self.rosters[key].slotWidgets) if key in self.rosters else 0
        for i in range(1, count + 1):
            slot = StateManager.Get(f"{RosterPath(key)}.slot.{i}", {}) or {}
            players = []
            for p in (slot.get("player") or {}).values():
                players.append(
                    {
                        "gamerTag": p.get("name") or "",
                        "prefix": p.get("team") or "",
                        "name": p.get("real_name") or "",
                        "country_code": (p.get("country") or {}).get("code")
                        if isinstance(p.get("country"), dict)
                        else None,
                        "state_code": (p.get("state") or {}).get("code")
                        if isinstance(p.get("state"), dict)
                        else None,
                        "pronoun": p.get("pronoun") or "",
                    }
                )
            roster.append({"name": slot.get("name") or "", "players": players})
        return roster

    # =====================================================
    # EXPORTS
    # =====================================================
    # Exporting to the layouts
    def ChannelExport(self, phase, limit, cache):
        if phase is None:
            return {
                "bracket": {},
                "phase": "",
                "phaseGroup": "",
                "phaseId": None,
                "playersPath": RosterPath(),
            }
        path = RosterPath(self.RosterKey(phase))
        key = (phase.id, limit)
        if key not in cache:
            cache[key] = (
                ExportBracket(phase.bracket, phase.name, limit, path) if phase.bracket else {}
            )
        provider = phase.providerPhaseGroupId is not None
        info = phase.providerInfo or {}
        return {
            "bracket": cache[key],
            "phase": (info.get("phase") or phase.name) if provider else phase.name,
            "phaseGroup": (info.get("group") or "") if provider else "",
            "phaseId": phase.id,
            "playersPath": path,
        }

    def ExportBracketState(self):
        focus = BracketFocus.instance
        main = focus.channels[MAIN_CHANNEL]

        StateManager.Set(
            "bracket.phases",
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "type": p.type,
                    "source": "startgg" if p.providerPhaseGroupId is not None else "local",
                    "phaseGroupId": p.providerPhaseGroupId,
                    "channels": focus.ChannelsOn(p.id),
                    "current": p.id == main.phase,
                }
                for p in self.tournament.phases
            ],
        )

        cache = {}
        channels = {
            name: self.ChannelExport(
                self.tournament.GetPhase(c.phase) if c.phase else None, c.limit, cache
            )
            for name, c in focus.channels.items()
        }
        StateManager.Set("bracket.channels", channels)

        # The main channel's, as the layouts always had it
        StateManager.Set("bracket.bracket", channels[MAIN_CHANNEL]["bracket"])
        StateManager.Set("bracket.phase", channels[MAIN_CHANNEL]["phase"])
        StateManager.Set("bracket.phaseGroup", channels[MAIN_CHANNEL]["phaseGroup"])
        self.MirrorPlayers()
        self.FocusBracketChanged()

    def FocusBracketChanged(self):
        # What the bracket focus layout shows can change with the bracket
        if BracketFocus.instance is not None:
            BracketFocus.instance.Refresh()
        if getattr(self, "focusBar", None) is not None:
            self.focusBar.UpdatePlayers()

    # =====================================================
    # PROVIDER PHASES
    # =====================================================
    # start.gg: phase groups are loaded into the phases, each with its own
    # player list. Loading one again reloads it.
    def UpdatePhases(self, phases):
        self.phaseSelection.blockSignals(True)
        self.phaseSelection.clear()
        self.phaseSelection.addItem("", {})
        for phase in phases:
            self.phaseSelection.addItem(phase.get("name"), phase)
        self.phaseSelection.blockSignals(False)
        self.UpdatePhaseGroups()

    def UpdatePhaseGroups(self):
        self.phaseGroupSelection.clear()
        provider = TournamentDataManager.instance.provider
        supported = getattr(provider, "SUPPORTS_BRACKETS", False)
        for phaseGroup in (self.phaseSelection.currentData() or {}).get("groups", []):
            self.phaseGroupSelection.addItem(phaseGroup.get("name"), phaseGroup)
            if not supported or phaseGroup.get("bracketType") not in BRACKET_TYPES:
                model: QStandardItemModel = self.phaseGroupSelection.model()
                model.item(model.rowCount() - 1).setEnabled(False)

    def PhaseGroupChanged(self):
        phaseGroup = self.phaseGroupSelection.currentData()
        if phaseGroup is None or TournamentDataManager.instance.provider is None:
            return
        phase = self.phaseSelection.currentData() or {}
        groups = phase.get("groups") or []
        id = str(phaseGroup.get("id"))
        self.phaseGroupInfo[id] = {
            "phase": phase.get("name") or "",
            "group": (phaseGroup.get("name") or "") if len(groups) > 1 else "",
            "bracketType": phaseGroup.get("bracketType"),
        }
        # Shown on this channel once it's in
        self.userLoad = id
        TournamentDataManager.instance.GetTournamentPhaseGroup(phaseGroup.get("id"))

    def ProviderPhases(self):
        return [p for p in self.tournament.phases if p.providerPhaseGroupId is not None]

    def ProviderPhase(self, id):
        return next(
            (p for p in self.ProviderPhases() if str(p.providerPhaseGroupId) == str(id)), None
        )

    def UpdatePhaseGroup(self, data):
        if not data:
            return
        id = str(data.get("phaseGroupId"))
        entrants = data.get("entrants") or []
        sets = data.get("sets")
        if not entrants or not sets:
            logger.warning(
                "Phase group fetch looks partial (no entrants or no sets); bracket left as is"
            )
            return

        existing = self.ProviderPhase(id)
        info = dict(existing.providerInfo if existing else {})
        info.update(self.phaseGroupInfo.get(id, {}))
        try:
            bracket = FromProviderSets(
                info.get("bracketType") or (existing.type if existing else TYPE_DOUBLE_ELIMINATION),
                sets,
                len(entrants),
                data.get("entrantIds"),
                progressionsOut=data.get("progressionsOut") or 0,
            )
        except Exception:
            logger.error(traceback.format_exc())
            logger.error("Couldn't build the bracket from start.gg's sets")
            return

        # The same phase group again: keep the names typed in for its rounds
        if existing is not None and existing.bracket is not None:
            bracket.roundNames = existing.bracket.roundNames

        with StateManager.SaveBlock():
            roster = self.GroupRoster(id)
            roster.setUpdatesEnabled(False)
            try:
                roster.signals.DataChanged.disconnect(self.PlayersChanged)
            except (TypeError, RuntimeError):
                pass
            try:
                self.groupEntrants[id] = entrants
                self.mainsApplied[id] = set()
                roster.LoadFromStandings(entrants, enrichBlocking=False)
            finally:
                roster.signals.DataChanged.connect(self.PlayersChanged)
                roster.setUpdatesEnabled(True)

            if existing is not None:
                phase = existing
                phase.type = bracket.type
            else:
                name = " - ".join(n for n in (info.get("phase"), info.get("group")) if n)
                phase = BracketPhase(
                    self.tournament.NewPhaseId(),
                    name or QApplication.translate("app", "start.gg"),
                    bracket.type,
                )
                phase.providerPhaseGroupId = id
                self.tournament.AddPhase(phase)
            phase.bracket = bracket
            phase.providerInfo = info
            phase.seedSources = [
                {"type": "player", "player": p} for p in range(1, len(entrants) + 1)
            ]
            roster.title.setText(
                QApplication.translate("app", "{0}: its players, from start.gg").format(phase.name)
            )

            # Loaded from here: shown on this channel
            if self.userLoad == id:
                self.userLoad = None
                if self.Ch().phase != phase.id:
                    self.Ch().SetPhase(phase.id)
                    self.saveTimer.start()
                    return
            if self.Ch().phase == phase.id:
                self.view.SetBracket(bracket, fit=existing is None)
            self.RefreshPhaseList()
            self.Changed(rebuildView=False)

    def ApplyFetchedMains(self):
        provider = TournamentDataManager.instance.provider
        if provider is None:
            return
        for id, entrants in self.groupEntrants.items():
            roster = self.rosters.get(id)
            if roster is None:
                continue
            applied = self.mainsApplied.setdefault(id, set())
            slots = roster.slotWidgets
            toUpdate = []
            for i, entrant in enumerate(entrants):
                if i >= len(slots) or i in applied:
                    continue
                for player in (entrant or {}).get("players") or []:
                    if not player.get("mains") and provider.GetCachedMains(player):
                        toUpdate.append(i)
                        break
            if not toUpdate:
                continue
            applied.update(toUpdate)
            with StateManager.SaveBlock():
                roster.childDataChangedLock = True
                try:
                    for i in toUpdate:
                        slots[i].SetTeamData(entrants[i], enrichBlocking=False)
                except Exception:
                    logger.error(traceback.format_exc())
                finally:
                    roster.childDataChangedLock = False
        self.MirrorPlayers()

    # =====================================================
    # PROVIDER SETS
    # =====================================================
    def RefreshSets(self):
        # Returns what it did, for the web server's update-bracket-sets
        if not self.ProviderPhases():
            selected = self.phaseGroupSelection.currentData()
            if selected is None or selected.get("id") is None:
                return "NO_PHASE_GROUP"
            self.PhaseGroupChanged()
            return "RELOADING_PHASE_GROUP"

        if self.fetching:
            return "ALREADY_UPDATING"

        self.FetchSets()
        return "OK"

    def FetchSets(self, onFinished=None):
        """Fetches the results of every phase group loaded."""
        ids = [str(p.providerPhaseGroupId) for p in self.ProviderPhases()]
        if not ids:
            if onFinished:
                onFinished()
            return
        # The button stays disabled while a fetch runs, so manual and
        # automatic updates can't overlap
        self.fetching = len(ids)
        self.btRefreshSets.setEnabled(False)

        def finished():
            self.fetching -= 1
            if self.fetching > 0:
                return
            self.btRefreshSets.setEnabled(bool(self.ProviderPhases()))
            if onFinished:
                onFinished()

        for id in ids:
            TournamentDataManager.instance.GetTournamentPhaseGroupSets(id, onFinished=finished)

    # Bracket auto update
    def AutoUpdateSets(self, done):
        # Nothing to update without a phase group loaded, or while a manual
        # update is still running
        if (
            not self.ProviderPhases()
            or TournamentDataManager.instance.provider is None
            or self.fetching
        ):
            done()
            return
        self.FetchSets(onFinished=done)

    def ToggleAutoUpdateSets(self, enabled):
        SettingsManager.Set("general.bracket_auto_update", enabled)
        if enabled:
            Scheduler.instance.Start("bracket_sets", run_now=True)
        else:
            Scheduler.instance.Stop("bracket_sets")

    def UpdateAutoUpdateTimer(self):
        scheduler = Scheduler.instance
        if not scheduler.IsEnabled("bracket_sets"):
            self.labelAutoUpdateTimer.setVisible(False)
            return
        self.labelAutoUpdateTimer.setVisible(True)
        if not self.ProviderPhases():
            self.labelAutoUpdateTimer.setText(
                QApplication.translate("app", "Waiting for a loaded bracket")
            )
        elif scheduler.IsRunning("bracket_sets"):
            self.labelAutoUpdateTimer.setText(QApplication.translate("app", "Updating..."))
        else:
            remaining = scheduler.RemainingMs("bracket_sets")
            if remaining is not None:
                self.labelAutoUpdateTimer.setText(
                    QApplication.translate("app", "Next update in {0}s").format(
                        round(remaining / 1000)
                    )
                )

    def ApplySetsUpdate(self, update):
        id = update.get("phaseGroupId")
        phase = self.ProviderPhase(id)
        if phase is None or phase.bracket is None:
            return
        sets = (update.get("data") or {}).get("sets") or []
        if not sets:
            logger.warning("Got no sets for the phase group; bracket left as is")
            return
        try:
            if not ApplyProviderUpdate(phase.bracket, sets):
                logger.info("The phase group's sets changed since it was loaded; reloading it")
                TournamentDataManager.instance.GetTournamentPhaseGroup(id)
                return
            if phase.id == self.Ch().phase:
                self.view.Refresh()
            self.Changed(rebuildView=False)
        except Exception:
            logger.error(traceback.format_exc())

    # =====================================================
    # GAME DEFAULTS
    # =====================================================
    def SetDefaultsFromAssets(self):
        if StateManager.Get("game.defaults"):
            players = StateManager.Get("game.defaults.players_per_team", 1)
            characters = StateManager.Get("game.defaults.characters_per_player", 1)
        else:
            players, characters = 1, 1
        # The spin boxes show the new sizes; the slots are resized a few at a
        # time, so loading a game doesn't freeze the window
        for spin, value in [(self.playerPerTeam, players), (self.charNumber, characters)]:
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        if (
            self.playerList.playersPerTeam != players
            or self.playerList.charactersPerPlayer != characters
        ):
            self.playerList.SetSizesGradually(players, characters)
        # start.gg's player lists keep their team sizes
        for key, roster in self.rosters.items():
            if key != "local" and roster.charactersPerPlayer != characters:
                roster.SetCharactersPerPlayer(characters)

    def CharactersPerPlayerChanged(self, value):
        for roster in self.rosters.values():
            roster.SetCharactersPerPlayer(value)

    # =====================================================
    # SAVING
    # =====================================================
    def Save(self):
        try:
            data = {
                "tournament": self.tournament.ToDict(),
                "rosters": {key: self.RosterSnapshot(key) for key in self.rosters},
            }
            os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
            tmp = SAVE_PATH + ".tmp"
            with open(tmp, "wb") as f:
                f.write(orjson.dumps(data))
            os.replace(tmp, SAVE_PATH)
        except Exception:
            logger.error(traceback.format_exc())

    def Load(self):
        data = None
        try:
            if os.path.exists(SAVE_PATH):
                with open(SAVE_PATH, "rb") as f:
                    data = orjson.loads(f.read())
        except Exception:
            logger.error(f"Couldn't read {SAVE_PATH}: {traceback.format_exc()}")

        main = BracketFocus.instance.channels[MAIN_CHANNEL]
        if data:
            try:
                self.tournament = BracketTournament.FromDict(data.get("tournament"))
                rosters = data.get("rosters")
                if rosters is None:
                    # Saved before channels: one player list, the loaded
                    # phase group's if there was one, and the phase shown
                    group = data.get("loadedPhaseGroupId")
                    key = str(group) if group and self.ProviderPhase(group) else "local"
                    rosters = {key: data.get("roster") or []}
                    if main.phase is None and data.get("currentPhase"):
                        main.phase = str(data.get("currentPhase"))

                local = rosters.get("local") or []
                if local:
                    self.slotNumber.blockSignals(True)
                    self.slotNumber.setValue(max(2, len(local)))
                    self.slotNumber.blockSignals(False)
                    playersPerTeam = max([len(t.get("players") or []) for t in local] + [1])
                    self.playerPerTeam.setValue(playersPerTeam)
                    self.playerList.LoadFromStandings(local, enrichBlocking=False)
                for key, roster in rosters.items():
                    phase = self.ProviderPhase(key) if key != "local" else None
                    if phase is None:
                        continue
                    groupRoster = self.GroupRoster(key)
                    groupRoster.LoadFromStandings(roster, enrichBlocking=False)
                    groupRoster.title.setText(
                        QApplication.translate("app", "{0}: its players, from start.gg").format(
                            phase.name
                        )
                    )
            except Exception:
                logger.error(traceback.format_exc())
                self.tournament = BracketTournament()

        if not self.tournament.phases:
            self.NewPhase()
        self.FixChannelPhases()
        self.ShowChannel()
