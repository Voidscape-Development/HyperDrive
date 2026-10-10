# The bracket widget: brackets of any type, built here or loaded from
# start.gg, shown on stream through the "bracket" state.
#
# A tournament built here is made of phases (e.g. two round robin pools and
# a top cut), all drawing their players from the player list. A phase's
# seeds can be players or results of another phase, so the top cut fills
# itself in as the pools finish. Loading a phase group from start.gg
# replaces them with that phase group.
import os
import traceback

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketFocus import BracketFocus
from .BracketFocusBar import BracketFocusBar
from .BracketModel import *
from .BracketView import BracketView, SourceText
from .DisplayOptions import DisplayOptionsButton
from .FlowLayout import FlowLayout
from .GameAssetManager import GameAssetManager
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


def TeamName(playerId):
    if playerId is None or playerId <= 0:
        return ""
    team = StateManager.Get(f"bracket.players.slot.{playerId}", {}) or {}
    if team.get("name"):
        return team.get("name")
    return " / ".join(
        [p.get("name", "") for p in (team.get("player") or {}).values() if p.get("name")]
    )


def Ordinal(n):
    return QApplication.translate("app", "#{0}").format(n)


class BracketWidget(QDockWidget):
    instance: "BracketWidget" = None

    def __init__(self, *args):
        with StateManager.SaveBlock():
            super().__init__(*args)
            BracketWidget.instance = self
            self.SetupUi()

    def SetupUi(self):
        self.setWindowTitle(QApplication.translate("app", "Bracket"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setWindowFlags(Qt.WindowType.Window)

        StateManager.Set("bracket", {})

        self.tournament = BracketTournament()
        self.currentPhaseId = None
        # Bracket type of each start.gg phase group asked for, by id, to know
        # how to build the bracket when its data comes in
        self.phaseGroupTypes = {}
        self.loadedPhaseGroupId = None
        # Entrants of the loaded phase group, so mains fetched in the
        # background after the load can be applied to their slots
        self.loadedEntrants = []
        self.mainsAppliedSlots = set()
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
                "Load the phase group, its players and its sets. Replaces the brackets in this widget.",
            )
        )
        self.btLoadPhaseGroup.clicked.connect(self.PhaseGroupChanged)
        providerRow.addWidget(self.btLoadPhaseGroup)
        self.btRefreshSets = QPushButton(QApplication.translate("app", "Update sets"))
        self.btRefreshSets.setToolTip(
            QApplication.translate(
                "app",
                "Update only the set results of the loaded bracket, without reloading its players",
            )
        )
        self.btRefreshSets.clicked.connect(lambda: self.RefreshSets())
        self.cbAutoUpdateSets = QCheckBox(QApplication.translate("app", "Auto update"))
        self.cbAutoUpdateSets.setToolTip(
            QApplication.translate(
                "app",
                "Update the set results of the loaded bracket periodically. The interval can be changed in Settings > General.",
            )
        )
        self.labelAutoUpdateTimer = QLabel()
        providerRow.addGroup(self.btRefreshSets, self.cbAutoUpdateSets, self.labelAutoUpdateTimer)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        contents.layout().addWidget(self.splitter, 1)

        # The player list changes as it's built, which updates these
        self.view = BracketView()
        self.view.playerName = TeamName
        self.view.rosterIds = lambda: range(1, len(self.playerList.slotWidgets) + 1)
        self.view.signals.edited.connect(self.BracketEdited)
        self.standingsTable = QTableWidget()
        self.standingsTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.standingsTable.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.standingsTable.verticalHeader().setVisible(False)

        # Left: phases, phase options and the player list
        left = QTabWidget()
        left.setMinimumWidth(200)
        self.splitter.addWidget(left)
        self.sidePanel = left

        # The tabs scroll, so the window can be smaller than their contents
        def Scrolling(tab):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(tab)
            return scroll

        left.addTab(Scrolling(self.BuildPhasesTab()), QApplication.translate("app", "Phases"))
        left.addTab(Scrolling(self.BuildPlayersTab()), QApplication.translate("app", "Players"))

        # Right: the bracket
        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(right)

        viewBar = FlowLayout()
        right.layout().addLayout(viewBar)
        self.btToggleSide = QPushButton()
        self.btToggleSide.setCheckable(True)
        self.btToggleSide.setIcon(ThemedIcon("./assets/icons/people.svg"))
        self.btToggleSide.setToolTip(QApplication.translate("app", "Show or hide the side panel"))
        self.btToggleSide.toggled.connect(self.SetSidePanelHidden)
        self.phaseTitle = QLabel()
        font = self.phaseTitle.font()
        font.setBold(True)
        self.phaseTitle.setFont(font)
        viewBar.addGroup(self.btToggleSide, self.phaseTitle)

        self.limitExport = QCheckBox(QApplication.translate("app", "Only show the top"))
        self.limitExport.setToolTip(
            QApplication.translate(
                "app",
                "Only the sets of players that can still finish in the top N are sent to the layouts",
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

        if BracketFocus.instance is None:
            BracketFocus.instance = BracketFocus()
        self.focusBar = BracketFocusBar(self.view)
        right.layout().addWidget(self.focusBar)

        viewSplitter = QSplitter(Qt.Orientation.Vertical)
        right.layout().addWidget(viewSplitter, 1)

        viewSplitter.addWidget(self.view)
        viewSplitter.addWidget(self.standingsTable)
        viewSplitter.setSizes([3, 1])

        self.splitter.setSizes([320, 900])
        self.btToggleSide.setChecked(SettingsManager.Get("bracket_player_list_hidden", False))

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

        self.playerList = PlayerList(base="bracket.players")

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
            self.playerList.SetCharactersPerPlayer,
        )

        self.displayOptions = DisplayOptionsButton("bracket_display_options")
        self.displayOptions.changed.connect(
            lambda: self.playerList.SetHiddenElements(self.displayOptions.HiddenElements())
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

    def SetSidePanelHidden(self, hidden):
        self.sidePanel.setHidden(hidden)
        if SettingsManager.Get("bracket_player_list_hidden", False) != hidden:
            SettingsManager.Set("bracket_player_list_hidden", hidden)

    # Phases

    def CurrentPhase(self) -> BracketPhase:
        return self.tournament.GetPhase(self.currentPhaseId)

    def RosterIds(self):
        return list(range(1, len(self.playerList.slotWidgets) + 1))

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
        self.currentPhaseId = phase.id
        self.RefreshPhaseList()
        self.Changed()
        return phase

    def RemovePhase(self):
        phase = self.CurrentPhase()
        if phase is None:
            return
        if (
            QMessageBox.question(
                self,
                QApplication.translate("app", "Remove phase"),
                QApplication.translate("app", "Remove {0}? Its results will be lost.").format(
                    phase.name
                ),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.tournament.RemovePhase(phase.id)
        if not self.tournament.phases:
            self.NewPhase()
            return
        self.currentPhaseId = self.tournament.phases[0].id
        self.RefreshPhaseList()
        self.Changed()

    def RefreshPhaseList(self):
        self.phaseList.blockSignals(True)
        self.phaseList.clear()
        for phase in self.tournament.phases:
            item = QListWidgetItem(f"{phase.name} ({TypeName(phase.type)})")
            item.setData(Qt.ItemDataRole.UserRole, phase.id)
            self.phaseList.addItem(item)
        index = next(
            (i for i, p in enumerate(self.tournament.phases) if p.id == self.currentPhaseId), 0
        )
        self.phaseList.setCurrentRow(index)
        self.phaseList.blockSignals(False)
        self.PhaseSelected(index)

    def PhaseSelected(self, row):
        if 0 <= row < len(self.tournament.phases):
            self.currentPhaseId = self.tournament.phases[row].id
        self.UpdateControls()
        phase = self.CurrentPhase()
        self.view.SetBracket(phase.bracket if phase else None)
        self.UpdateView()

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
            self.btRefreshSets.setEnabled(self.loadedPhaseGroupId is not None)
            self.RefreshSeedsTable()
        finally:
            self.updatingControls = False

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
            if (
                other.id == phase.id
                or self.tournament.DependsOn(other, phase)
                or other.bracket is None
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

    def PhaseNameChanged(self):
        phase = self.CurrentPhase()
        if phase is None or self.updatingControls:
            return
        phase.name = self.phaseName.text().strip() or phase.name
        self.RefreshPhaseList()
        self.Changed(rebuildView=False)

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
        self.view.exportLimit = (
            self.limitExportNumber.value() if self.limitExport.isChecked() else None
        )
        self.view.Refresh()
        self.UpdateView()

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
                    value = TeamName(row["playerId"])
                elif key == "seed":
                    value = str(bracket.SeedOf(row["playerId"]))
                else:
                    value = str(row.get(key, ""))
                item = QTableWidgetItem(value)
                if key != "playerName":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.standingsTable.setItem(r, c, item)

    # Exporting to the layouts

    def PlayerExport(self, bracket, m, slot):
        player = m.players[slot]
        data = {
            "id": player if player > 0 else None,
            "seed": bracket.SeedOf(player)
            if player > 0 and bracket.SeedOf(player) != 9999
            else None,
            "name": TeamName(player) if player > 0 else "",
            "bye": player == BYE,
            "pending": player == PENDING,
            # What the slot waits for, e.g. "Winner of C"
            "source": SourceText(bracket, m.sources[slot]) if player == PENDING else "",
            "manual": m.override[slot] is not None,
        }
        return data

    def ExportBracketState(self):
        phase = self.CurrentPhase()
        bracket = phase.bracket if phase else None

        StateManager.Set(
            "bracket.phases",
            [
                {"id": p.id, "name": p.name, "type": p.type, "current": p.id == self.currentPhaseId}
                for p in self.tournament.phases
            ],
        )

        if bracket is None:
            StateManager.Set("bracket.bracket", {})
            self.FocusBracketChanged()
            return

        limit = self.view.exportLimit if not bracket.IsPool() else None
        included = {
            m.id
            for m in bracket.matches.values()
            if not m.isBye and (limit is None or bracket.InTopN(m, limit))
        }

        sets = {}
        for m in bracket.matches.values():
            if m.id not in included:
                continue
            winner = None
            if m.winnerSlot is not None and m.finished:
                winner = m.winnerSlot
            elif m.IsDraw():
                winner = "draw"

            def Next(link):
                if link is None or link[0] not in included:
                    return None
                return {"set": link[0], "slot": link[1]}

            sets[m.id] = {
                "id": m.id,
                "identifier": m.identifier,
                "side": m.side,
                "column": m.column,
                "row": m.row,
                "roundName": bracket.RoundName(m.side, m.column),
                "players": [self.PlayerExport(bracket, m, slot) for slot in range(2)],
                "score": list(m.score),
                "completed": bool(m.finished),
                # 0 or 1 for the slot that won, "draw" or None
                "winner": winner,
                "nextWin": Next(m.nextWin),
                "nextLose": Next(m.nextLose),
                "loserPlacement": bracket.LoserPlacementOf(m) if not bracket.IsPool() else None,
                "isGrandFinal": m.isGrandFinal,
                "isReset": m.isReset,
                "resetNeeded": not m.notNeeded,
                "startggId": m.providerId,
            }

        sides = {}
        for side in SIDES:
            columns = []
            for column in bracket.Columns(side, includeHidden=side == SIDE_GRAND_FINAL):
                ids = [m.id for m in column if m.id in included]
                if not ids:
                    continue
                columns.append(
                    {
                        "key": Bracket.RoundKey(side, column[0].column),
                        "name": bracket.RoundName(side, column[0].column),
                        "sets": ids,
                    }
                )
            if columns:
                sides[side] = columns

        data = {
            "type": bracket.type,
            "name": phase.name,
            "fromStartgg": bracket.fromProvider,
            "progressionsOut": bracket.progressionsOut,
            "limitExportNumber": limit,
            "sides": sides,
            "sets": sets,
        }

        if bracket.IsPool():
            standings = bracket.GetStandings()
            data["standings"] = [dict(row, name=TeamName(row["playerId"])) for row in standings]
            data["totalRounds"] = bracket.totalRounds
            data["byes"] = {
                Bracket.RoundKey(SIDE_POOL, int(r)): [
                    {"id": p, "name": TeamName(p)} for p in players
                ]
                for r, players in bracket.byes.items()
            }
        else:
            results = []
            for i, player in enumerate(bracket.Results()):
                if player > 0:
                    results.append({"order": i + 1, "id": player, "name": TeamName(player)})
            data["results"] = results

        StateManager.Set("bracket.bracket", data)
        self.FocusBracketChanged()

    def FocusBracketChanged(self):
        # What the bracket focus layout shows can change with the bracket
        if BracketFocus.instance is not None:
            BracketFocus.instance.Refresh()
        if getattr(self, "focusBar", None) is not None:
            self.focusBar.UpdatePlayers()

    # start.gg

    def UpdatePhases(self, phases):
        self.phaseSelection.blockSignals(True)
        self.phaseSelection.clear()
        self.phaseSelection.addItem("", {})
        for phase in phases:
            self.phaseSelection.addItem(phase.get("name"), phase)
        self.phaseSelection.blockSignals(False)
        self.UpdatePhaseGroups()

    def UpdatePhaseGroups(self):
        try:
            StateManager.Set(
                "bracket.phase", (self.phaseSelection.currentData() or {}).get("name", "")
            )
        except Exception:
            StateManager.Set("bracket.phase", "")

        self.phaseGroupSelection.clear()
        provider = TournamentDataManager.instance.provider
        supported = getattr(provider, "SUPPORTS_BRACKETS", False)
        for phaseGroup in (self.phaseSelection.currentData() or {}).get("groups", []):
            self.phaseGroupSelection.addItem(phaseGroup.get("name"), phaseGroup)
            if not supported or phaseGroup.get("bracketType") not in BRACKET_TYPES:
                model: QStandardItemModel = self.phaseGroupSelection.model()
                model.item(model.rowCount() - 1).setEnabled(False)

    def PhaseGroupChanged(self):
        try:
            if len((self.phaseSelection.currentData() or {}).get("groups", [])) > 1:
                StateManager.Set(
                    "bracket.phaseGroup", (self.phaseGroupSelection.currentData() or {}).get("name")
                )
            else:
                StateManager.Set("bracket.phaseGroup", "")
        except Exception:
            StateManager.Set("bracket.phaseGroup", "")

        phaseGroup = self.phaseGroupSelection.currentData()
        if phaseGroup is None or TournamentDataManager.instance.provider is None:
            return

        local = [
            p
            for p in self.tournament.phases
            if p.bracket is not None
            and not p.bracket.fromProvider
            and any(m.finished for m in p.bracket.matches.values())
        ]
        if local and self.isVisible():
            answer = QMessageBox.question(
                self,
                QApplication.translate("app", "Load phase group"),
                QApplication.translate(
                    "app",
                    "Loading a phase group replaces the brackets built here, and their results. Continue?",
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.phaseGroupTypes[str(phaseGroup.get("id"))] = phaseGroup.get("bracketType")
        TournamentDataManager.instance.GetTournamentPhaseGroup(phaseGroup.get("id"))

    def RefreshSets(self):
        # Returns what it did, for the web server's update-bracket-sets
        selected = self.phaseGroupSelection.currentData()
        if self.loadedPhaseGroupId is None:
            if selected is None or selected.get("id") is None:
                return "NO_PHASE_GROUP"
            self.PhaseGroupChanged()
            return "RELOADING_PHASE_GROUP"

        if not self.btRefreshSets.isEnabled():
            return "ALREADY_UPDATING"

        self.FetchSets()
        return "OK"

    def FetchSets(self, onFinished=None):
        # The button stays disabled while a fetch runs, so manual and
        # automatic updates can't overlap
        self.btRefreshSets.setEnabled(False)

        def finished():
            self.btRefreshSets.setEnabled(self.loadedPhaseGroupId is not None)
            if onFinished:
                onFinished()

        TournamentDataManager.instance.GetTournamentPhaseGroupSets(
            self.loadedPhaseGroupId, onFinished=finished
        )

    # Bracket auto update

    def AutoUpdateSets(self, done):
        # Nothing to update without a bracket loaded from the provider, or
        # while a manual update is still running
        if (
            self.loadedPhaseGroupId is None
            or TournamentDataManager.instance.provider is None
            or not self.btRefreshSets.isEnabled()
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
        if self.loadedPhaseGroupId is None:
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

    def ProviderPhase(self):
        return next(
            (
                p
                for p in self.tournament.phases
                if p.bracket is not None
                and p.bracket.fromProvider
                and str(p.providerPhaseGroupId) == str(self.loadedPhaseGroupId)
            ),
            None,
        )

    def ApplySetsUpdate(self, update):
        if self.loadedPhaseGroupId is None or str(update.get("phaseGroupId")) != str(
            self.loadedPhaseGroupId
        ):
            return
        phase = self.ProviderPhase()
        sets = (update.get("data") or {}).get("sets") or []
        if phase is None or not sets:
            logger.warning("Got no sets for the phase group; bracket left as is")
            return
        try:
            if not ApplyProviderUpdate(phase.bracket, sets):
                logger.info("The phase group's sets changed since it was loaded; reloading it")
                TournamentDataManager.instance.GetTournamentPhaseGroup(self.loadedPhaseGroupId)
                return
            self.tournament.Resolve()
            if phase.id == self.currentPhaseId:
                self.view.Refresh()
            self.Changed(rebuildView=False)
        except Exception:
            logger.error(traceback.format_exc())

    def UpdatePhaseGroup(self, data):
        if not data:
            return
        phaseGroupId = data.get("phaseGroupId")
        entrants = data.get("entrants") or []
        type = self.phaseGroupTypes.get(str(phaseGroupId)) or TYPE_DOUBLE_ELIMINATION
        sets = data.get("sets")
        if not entrants or not sets:
            logger.warning(
                "Phase group fetch looks partial (no entrants or no sets); bracket left as is"
            )
            return

        try:
            bracket = FromProviderSets(
                type,
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
        previous = (
            self.ProviderPhase() if str(self.loadedPhaseGroupId) == str(phaseGroupId) else None
        )
        if previous is not None and previous.bracket is not None:
            bracket.roundNames = previous.bracket.roundNames

        with StateManager.SaveBlock():
            self.playerList.setUpdatesEnabled(False)
            try:
                self.playerList.signals.DataChanged.disconnect(self.PlayersChanged)
            except (TypeError, RuntimeError):
                pass
            try:
                self.loadedEntrants = entrants
                self.mainsAppliedSlots = set()
                self.playerList.LoadFromStandings(entrants, enrichBlocking=False)
                self.slotNumber.blockSignals(True)
                self.slotNumber.setValue(len(self.playerList.slotWidgets))
                self.slotNumber.blockSignals(False)
                self.playerPerTeam.blockSignals(True)
                self.playerPerTeam.setValue(max(1, self.playerList.playersPerTeam))
                self.playerPerTeam.blockSignals(False)
            finally:
                self.playerList.signals.DataChanged.connect(self.PlayersChanged)
                self.playerList.setUpdatesEnabled(True)

            name = StateManager.Get("bracket.phase") or QApplication.translate("app", "start.gg")
            group = StateManager.Get("bracket.phaseGroup")
            if group:
                name = f"{name} - {group}"

            tournament = BracketTournament()
            phase = BracketPhase(tournament.NewPhaseId(), name, bracket.type)
            phase.bracket = bracket
            phase.providerPhaseGroupId = phaseGroupId
            phase.seedSources = [
                {"type": "player", "player": p} for p in range(1, len(entrants) + 1)
            ]
            tournament.AddPhase(phase)
            self.tournament = tournament
            self.currentPhaseId = phase.id
            self.loadedPhaseGroupId = phaseGroupId

            self.RefreshPhaseList()
            self.view.SetBracket(bracket, fit=previous is None)
            self.Changed(rebuildView=False)

    def ApplyFetchedMains(self):
        provider = TournamentDataManager.instance.provider
        if provider is None or not self.loadedEntrants:
            return
        slots = self.playerList.slotWidgets
        toUpdate = []
        for i, entrant in enumerate(self.loadedEntrants):
            if i >= len(slots) or i in self.mainsAppliedSlots:
                continue
            for player in (entrant or {}).get("players") or []:
                if not player.get("mains") and provider.GetCachedMains(player):
                    toUpdate.append(i)
                    break
        if not toUpdate:
            return
        self.mainsAppliedSlots.update(toUpdate)
        with StateManager.SaveBlock():
            self.playerList.childDataChangedLock = True
            try:
                for i in toUpdate:
                    slots[i].SetTeamData(self.loadedEntrants[i], enrichBlocking=False)
            except Exception:
                logger.error(traceback.format_exc())
            finally:
                self.playerList.childDataChangedLock = False

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

    # Saving, so a tournament run in HyperDrive survives a restart

    def RosterSnapshot(self):
        roster = []
        for i in self.RosterIds():
            slot = StateManager.Get(f"bracket.players.slot.{i}", {}) or {}
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

    def Save(self):
        try:
            data = {
                "tournament": self.tournament.ToDict(),
                "currentPhase": self.currentPhaseId,
                "loadedPhaseGroupId": self.loadedPhaseGroupId,
                "roster": self.RosterSnapshot(),
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

        if data:
            try:
                roster = data.get("roster") or []
                if roster:
                    self.slotNumber.blockSignals(True)
                    self.slotNumber.setValue(max(2, len(roster)))
                    self.slotNumber.blockSignals(False)
                    playersPerTeam = max([len(t.get("players") or []) for t in roster] + [1])
                    self.playerPerTeam.setValue(playersPerTeam)
                    self.playerList.LoadFromStandings(roster, enrichBlocking=False)
                self.tournament = BracketTournament.FromDict(data.get("tournament"))
                self.currentPhaseId = data.get("currentPhase")
                self.loadedPhaseGroupId = data.get("loadedPhaseGroupId")
                if self.ProviderPhase() is None:
                    self.loadedPhaseGroupId = None
            except Exception:
                logger.error(traceback.format_exc())
                self.tournament = BracketTournament()

        if not self.tournament.phases:
            self.NewPhase()
        else:
            if self.CurrentPhase() is None:
                self.currentPhaseId = self.tournament.phases[0].id
            self.RefreshPhaseList()
