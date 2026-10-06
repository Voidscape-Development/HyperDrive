from loguru import logger
from qtpy import uic
from qtpy.QtCore import *
from qtpy.QtGui import QAction
from qtpy.QtWidgets import *

from .ColorButton import ColorButton
from .Helpers.DirHelper import ResolvePath
from .Helpers.LocaleHelper import LocaleHelper
from .Helpers.SponsorHelper import SponsorHelper
from .Helpers.VersionHelper import add_beta_label
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TeamBattleModeEnum import TeamBattleModeEnum
from .TeamPlayerWidget import TeamPlayerWidget
from .Theme import ThemedIcon


class TeamBattleSignals(QObject):
    # Commands, from the webserver or anything else that controls the battle.
    # "Stock up" means the team scored: in Stock Pool the other team's active
    # player loses a stock, in First To the team's active player wins a game.
    # "Stock down" undoes it.

    # GENERAL SIGNALS
    reset_all_stocks = Signal()
    reset_everything = Signal()
    dynamicSpinner_changed = Signal()

    # TEAM 1 SIGNALS
    team1_next_active_player = Signal()
    team1_stock_up = Signal()
    team1_stock_down = Signal()
    # Index (from 0) of the player to make active
    team1_set_active_player = Signal(int)
    # Emitted with the new active player's index, or -1 for none
    team1_active_player_changed = Signal(int)

    # TEAM 2 SIGNALS
    team2_next_active_player = Signal()
    team2_stock_up = Signal()
    team2_stock_down = Signal()
    team2_set_active_player = Signal(int)
    team2_active_player_changed = Signal(int)


class TeamBattleWidget(QDockWidget):
    # The widget the webserver controls
    instance: TeamBattleWidget = None

    battleMode = TeamBattleModeEnum.STOCK_POOL

    def __init__(self, *args):
        super().__init__(*args)
        logger.info("BATTLE START")
        TeamBattleWidget.instance = self
        self.signals = TeamBattleSignals()

        self.playerWidgets: list[TeamPlayerWidget] = []
        self.team1playerWidgets: list[TeamPlayerWidget] = []
        self.team2playerWidgets: list[TeamPlayerWidget] = []

        # Index (from 0) of each team's active player, -1 for none
        self.currentActiveIndexTeam1: int = -1
        self.currentActiveIndexTeam2: int = -1

        # Players auto advance moved away from, latest last, so undoing a
        # stock can bring them back
        self.advanceHistory: dict[int, list[TeamPlayerWidget]] = {1: [], 2: []}
        # First To: the opposing player each player eliminated by reaching
        # the "First To" amount, until the opponent's next player comes in
        self.firstToVictims: dict[TeamPlayerWidget, TeamPlayerWidget] = {}

        # Set while players swap places or many values change at once, so
        # their checkboxes don't set off auto advance or eliminations
        self.swapping = False
        self.bulkUpdate = False

        StateManager.Unset("team_battle")

        self.setWindowTitle(
            add_beta_label(QApplication.translate("app", "Crew/Team Battle"), "team_battle")
        )
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.widget.setLayout(QVBoxLayout())
        self.setWindowFlags(Qt.WindowType.Window)

        self.playerNumber = QSpinBox()
        self.playerNumber.setObjectName("playerNumber")
        self.playerNumber.setFixedWidth(50)
        self.playerNumber.valueChanged.connect(lambda val: self.SetPlayersPerTeam(val))

        self.characterNumber = QSpinBox()
        self.characterNumber.setFixedWidth(50)
        self.characterNumber.valueChanged.connect(self.SetCharacterNumber)

        self.lifeLabel = QLabel(QApplication.translate("app", "Stocks"))
        self.livesNumber = QSpinBox()
        self.livesNumber.setFixedWidth(50)
        self.livesNumber.valueChanged.connect(self.SetSpinnerForPlayers)
        self.livesNumber.valueChanged.connect(self.TotalScoreExport)

        self.modeCombo = QComboBox()
        for mode in TeamBattleModeEnum:
            self.modeCombo.addItem(mode.translated())
        # After adding the modes: switching needs the rest of the widget
        self.modeCombo.currentIndexChanged.connect(self.SwitchBattleMode)

        self.phaseCombo = QComboBox()
        self.phaseCombo.setObjectName("phaseCombo")
        self.phaseCombo.setEditable(True)
        self.phaseCombo.currentIndexChanged.connect(self.PhaseExport)
        self.phaseCombo.lineEdit().editingFinished.connect(self.PhaseExport)
        self.phaseCombo.addItem("")
        LocaleHelper.LoadPhaseNamesToWidget(self.phaseCombo)

        self.matchCombo = QComboBox()
        self.matchCombo.setObjectName("matchCombo")
        self.matchCombo.setEditable(True)
        self.matchCombo.currentIndexChanged.connect(self.MatchExport)
        self.matchCombo.lineEdit().editingFinished.connect(self.MatchExport)
        self.matchCombo.addItem("")
        LocaleHelper.LoadMatchNamesToWidget(self.matchCombo)

        resetValues = QPushButton(QApplication.translate("app", "Reset Player Mode Values"))
        resetValues.setFixedHeight(24)
        resetValues.clicked.connect(self.ResetAllStocks)

        resetEverything = QPushButton(QApplication.translate("app", "Reset Battle Mode"))
        resetEverything.setFixedHeight(24)
        resetEverything.clicked.connect(self.ResetEverything)

        # Top toolbar row
        row = QWidget()
        rowLayout = QHBoxLayout(row)
        rowLayout.setContentsMargins(4, 2, 4, 2)
        rowLayout.setSpacing(10)
        row.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.widget.layout().addWidget(row, 0, Qt.AlignmentFlag.AlignTop)

        # Group 1: Match Rules (Players, Characters, Mode, Stocks)
        rulesCol = QWidget()
        rulesLayout = QGridLayout(rulesCol)
        rulesLayout.setContentsMargins(0, 0, 0, 0)
        rulesLayout.setHorizontalSpacing(6)
        rulesLayout.setVerticalSpacing(3)

        playerLabel = QLabel(QApplication.translate("app", "Players"))
        charLabel = QLabel(QApplication.translate("app", "Characters"))
        modeLabel = QLabel(QApplication.translate("app", "Mode"))

        rulesLayout.addWidget(
            playerLabel, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        rulesLayout.addWidget(self.playerNumber, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(
            modeLabel, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        rulesLayout.addWidget(self.modeCombo, 0, 3, Qt.AlignmentFlag.AlignVCenter)

        rulesLayout.addWidget(
            charLabel, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        rulesLayout.addWidget(self.characterNumber, 1, 1, Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(
            self.lifeLabel, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        rulesLayout.addWidget(
            self.livesNumber, 1, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        rowLayout.addWidget(rulesCol)

        # Group 2: Tournament Info (Phase, Match)
        infoCol = QWidget()
        infoLayout = QGridLayout(infoCol)
        infoLayout.setContentsMargins(0, 0, 0, 0)
        infoLayout.setHorizontalSpacing(6)
        infoLayout.setVerticalSpacing(3)

        phaseLabel = QLabel(QApplication.translate("app", "Phase"))
        matchLabel = QLabel(QApplication.translate("app", "Match"))

        infoLayout.addWidget(
            phaseLabel, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        infoLayout.addWidget(self.phaseCombo, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        infoLayout.addWidget(
            matchLabel, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        infoLayout.addWidget(self.matchCombo, 1, 1, Qt.AlignmentFlag.AlignVCenter)

        rowLayout.addWidget(infoCol)

        # Group 3: Actions & Visibility
        actionsCol = QWidget()
        actionsLayout = QGridLayout(actionsCol)
        actionsLayout.setContentsMargins(0, 0, 0, 0)
        actionsLayout.setHorizontalSpacing(6)
        actionsLayout.setVerticalSpacing(3)

        self.eyeBt = QToolButton()
        self.eyeBt.setIcon(ThemedIcon("assets/icons/eye.svg"))
        self.eyeBt.setFixedSize(26, 26)
        self.eyeBt.setIconSize(QSize(18, 18))
        self.eyeBt.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu()
        self.eyeBt.setMenu(menu)

        menu.addSection(QApplication.translate("app", "Players"))

        self.elements = [
            [QApplication.translate("app", "Twitter"), ["twitter", "twitterLabel"], "show_social"],
            [
                QApplication.translate("app", "Location"),
                ["locationLabel", "state", "country"],
                "show_location",
            ],
            [QApplication.translate("app", "Characters"), ["characters"], "show_characters"],
            [QApplication.translate("app", "Pronouns"), ["pronoun"], "show_pronouns"],
        ]
        for element in self.elements:
            action: QAction = self.eyeBt.menu().addAction(element[0])
            action.setCheckable(True)
            action.setChecked(SettingsManager.Get(f"display_options.{element[2]}", True))
            action.toggled.connect(
                lambda toggled, action=action, element=element: [
                    self.ToggleElements(action, element[1]),
                    SettingsManager.Set(f"display_options.{element[2]}", toggled),
                ]
            )

        self.autoAdvance = QCheckBox(QApplication.translate("app", "Auto advance"))
        self.autoAdvance.setToolTip(
            QApplication.translate(
                "app",
                "When the active player is eliminated, make the team's next player in line active",
            )
        )
        self.autoAdvance.setChecked(SettingsManager.Get("team_battle.auto_advance", True))
        self.autoAdvance.toggled.connect(
            lambda checked: SettingsManager.Set("team_battle.auto_advance", checked)
        )

        actionsLayout.addWidget(resetValues, 0, 0)
        actionsLayout.addWidget(self.eyeBt, 0, 1, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        actionsLayout.addWidget(resetEverything, 1, 0)
        actionsLayout.addWidget(self.autoAdvance, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)

        rowLayout.addWidget(actionsCol)
        rowLayout.addStretch()

        scrollArea = QScrollArea()
        scrollArea.setFrameShadow(QFrame.Shadow.Plain)
        scrollArea.setFrameShape(QFrame.Shape.Panel)
        scrollArea.setWidgetResizable(True)

        self.widgetArea = QWidget()
        self.widgetArea.setLayout(QHBoxLayout())
        self.widgetArea.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        scrollArea.setWidget(self.widgetArea)

        self.team1column = uic.loadUi(ResolvePath("src/layout/BattleTeam.ui"))
        self.team1column.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.team1column.findChild(QLineEdit, "teamName").editingFinished.connect(
            self.Team1SponsorExport
        )
        DEFAULT_TEAM1_COLOR = SettingsManager.Get("general.team_1_default_color", "#fe3636")
        self.colorButton1 = ColorButton(color=DEFAULT_TEAM1_COLOR, ignore_same_color=False)
        self.team1column.findChild(QHBoxLayout, "team_header").layout().insertWidget(
            0, self.colorButton1
        )
        self.colorButton1.colorChanged.connect(
            lambda color: StateManager.Set(f"team_battle.team.{1}.color", color)
        )
        self.colorButton1.setColor(DEFAULT_TEAM1_COLOR)
        self.team1score = QSpinBox()
        self.team1column.findChild(QHBoxLayout, "team_header").layout().addWidget(self.team1score)
        self.team1score.valueChanged.connect(self.Team1TotalScoreExport)
        self.team1score.valueChanged.emit(0)
        self.widgetArea.layout().addWidget(self.team1column)

        self.team2column = uic.loadUi(ResolvePath("src/layout/BattleTeam.ui"))
        self.team2column.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.team2column.findChild(QLineEdit, "teamName").editingFinished.connect(
            self.Team2SponsorExport
        )
        DEFAULT_TEAM2_COLOR = SettingsManager.Get("general.team_2_default_color", "#2e89ff")
        self.colorButton2 = ColorButton(color=DEFAULT_TEAM2_COLOR, ignore_same_color=False)
        self.team2column.findChild(QHBoxLayout, "team_header").layout().insertWidget(
            0, self.colorButton2
        )
        self.colorButton2.colorChanged.connect(
            lambda color: StateManager.Set(f"team_battle.team.{2}.color", color)
        )
        self.colorButton2.setColor(DEFAULT_TEAM2_COLOR)
        self.team2score = QSpinBox()
        self.team2column.findChild(QHBoxLayout, "team_header").layout().addWidget(self.team2score)
        self.team2score.valueChanged.connect(self.Team2TotalScoreExport)
        self.team2score.valueChanged.emit(0)
        self.widgetArea.layout().addWidget(self.team2column)

        self.widget.layout().addWidget(scrollArea, 1)

        self.team1score.valueChanged.connect(self.Team1TotalScoreExport)
        self.team2score.valueChanged.connect(self.Team2TotalScoreExport)

        self.team1column.findChild(QCheckBox, "separateSponsors").toggled.connect(
            self.ToggleSponsorsForTeam1
        )
        self.team2column.findChild(QCheckBox, "separateSponsors").toggled.connect(
            self.ToggleSponsorsForTeam2
        )

        # Hook into Signals for Control
        self.signals.reset_all_stocks.connect(self.ResetAllStocks)
        self.signals.reset_everything.connect(self.ResetEverything)
        self.signals.dynamicSpinner_changed.connect(self.TotalScoreExport)

        self.signals.team1_next_active_player.connect(self.Team1NextUp)
        self.signals.team2_next_active_player.connect(self.Team2NextUp)
        self.signals.team1_set_active_player.connect(lambda index: self.SetActivePlayer(1, index))
        self.signals.team2_set_active_player.connect(lambda index: self.SetActivePlayer(2, index))

        self.signals.team1_stock_up.connect(self.T1_Stock_Up)
        self.signals.team1_stock_down.connect(self.T1_Stock_Down)
        self.signals.team2_stock_up.connect(self.T2_Stock_Up)
        self.signals.team2_stock_down.connect(self.T2_Stock_Down)

        self.SwitchBattleMode()
        self.playerNumber.setValue(1)
        self.characterNumber.setValue(1)

    # =====================================================
    # GENERAL CONTROL METHODS
    # =====================================================
    def DefaultValueForMode(self, mode: TeamBattleModeEnum = None):
        """The starting Stocks or First To amount set in the settings."""
        mode = mode or self.battleMode
        if mode is TeamBattleModeEnum.FIRST_TO:
            return SettingsManager.Get("general.team_battle_default_first_to", 2)
        return SettingsManager.Get("general.team_battle_default_stocks", 3)

    def SwitchBattleMode(self):
        self.battleMode = TeamBattleModeEnum.MatchToMode(self.modeCombo.currentText())
        logger.info(f"Switching Battle Mode to: {self.battleMode.name}")

        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            self.lifeLabel.setText(QApplication.translate("app", "Stocks"))
        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            self.lifeLabel.setText(QApplication.translate("app", "First To"))

        # Players need the new mode before their values are reset, or they
        # reset to the old mode's starting value
        for pw in self.playerWidgets:
            pw.SetBattleMode(self.battleMode)
        StateManager.Set("team_battle.battle_mode", self.battleMode.name)

        self.SetBattleValue(self.DefaultValueForMode())

    def SetBattleValue(self, value: int):
        """Sets the Stocks/First To amount and resets every player to it."""
        self.livesNumber.blockSignals(True)
        self.livesNumber.setValue(value)
        self.livesNumber.blockSignals(False)
        self.SetSpinnerForPlayers()
        self.TotalScoreExport()

    def ClearBattleTracking(self):
        self.advanceHistory = {1: [], 2: []}
        self.firstToVictims = {}

    def ResetAllStocks(self):
        self.bulkUpdate = True
        try:
            for pw in self.playerWidgets:
                pw.ResetDynamicSpinner()
            self.ClearBattleTracking()
        finally:
            self.bulkUpdate = False

    def ResetEverything(self):
        self.bulkUpdate = True
        try:
            for pw in self.playerWidgets:
                pw.Clear()
                pw.SetActiveStatus(False)
            self.ClearBattleTracking()
            self.SetBattleValue(self.DefaultValueForMode())
            # Each team starts with their first player
            for team in [1, 2]:
                if self.Players(team):
                    self.Players(team)[0].SetActiveStatus(True)
        finally:
            self.bulkUpdate = False

    def ToggleSponsorsForTeam1(self):
        for player in self.team1playerWidgets:
            player.ToggleSponsorDisplay()

    def ToggleSponsorsForTeam2(self):
        for player in self.team2playerWidgets:
            player.ToggleSponsorDisplay()

    def SetSpinnerForPlayers(self):
        self.bulkUpdate = True
        try:
            for pw in self.playerWidgets:
                pw.SetDefaultSpinnerValue(self.livesNumber.value())
            self.ClearBattleTracking()
        finally:
            self.bulkUpdate = False

    # =====================================================
    # NECESSARY PLAYER METHODS
    # =====================================================
    def SetCharacterNumber(self, value):
        for pw in self.playerWidgets:
            pw.SetCharactersPerPlayer(value)

    def Players(self, team: int) -> list[TeamPlayerWidget]:
        return self.team1playerWidgets if team == 1 else self.team2playerWidgets

    @staticmethod
    def OtherTeam(team: int) -> int:
        return 2 if team == 1 else 1

    def AddPlayer(self, team: int):
        players = self.Players(team)
        column = self.team1column if team == 1 else self.team2column

        p = TeamPlayerWidget(
            index=len(players) + 1,
            teamNumber=team,
            path=f"team_battle.team.{team}.player.{len(players) + 1}",
        )
        self.playerWidgets.append(p)

        column.findChild(QScrollArea).widget().layout().addWidget(p)
        p.SetCharactersPerPlayer(self.characterNumber.value())

        if column.findChild(QCheckBox, "separateSponsors").isChecked():
            p.ToggleSponsorDisplay()

        self.ApplyVisibility(p)

        self.signals.dynamicSpinner_changed.connect(p.instanceSignals.dynamicSpinner_changed)
        p.instanceSignals.dynamicSpinner_changed.connect(self.TotalScoreExport)

        p.instanceSignals.activeStatus_changed.connect(
            lambda active, p=p, team=team: self.PlayerActiveChanged(team, p, bool(active))
        )
        p.instanceSignals.deathStatus_changed.connect(
            lambda dead, p=p, team=team: self.PlayerEliminatedChanged(team, p, bool(dead))
        )
        p.instanceSignals.toggleDeathTrigger.connect(
            lambda reached, p=p, team=team: self.PlayerReachedFirstTo(team, p, reached)
        )

        p.btMoveUp.clicked.connect(
            lambda checked=False, p=p, team=team: self.MovePlayer(team, p, -1)
        )
        p.btMoveDown.clicked.connect(
            lambda checked=False, p=p, team=team: self.MovePlayer(team, p, 1)
        )

        players.append(p)

        self.bulkUpdate = True
        try:
            p.SetBattleMode(self.battleMode)
            p.SetDefaultSpinnerValue(self.livesNumber.value())
            # A team starts with their first player
            if len(players) == 1:
                p.SetActiveStatus(True)
        finally:
            self.bulkUpdate = False

    def RemoveLastPlayer(self, team: int):
        players = self.Players(team)
        player = players[-1]
        if self.ActivePlayer(team) is player:
            self.SetActiveIndex(team, -1)
        StateManager.Unset(player.path)
        player.setParent(None)
        self.playerWidgets.remove(player)
        players.remove(player)

        self.advanceHistory[team] = [w for w in self.advanceHistory[team] if w is not player]
        self.firstToVictims = {
            winner: victim
            for winner, victim in self.firstToVictims.items()
            if player not in (winner, victim)
        }

        player.deleteLater()

    def SetPlayersPerTeam(self, number):
        while len(self.team1playerWidgets) < number:
            self.AddPlayer(1)
            self.AddPlayer(2)

        while len(self.team1playerWidgets) > number:
            self.RemoveLastPlayer(1)
            self.RemoveLastPlayer(2)

        for team in [1, 2]:
            if StateManager.Get(f"team_battle.team.{team}.player"):
                for k in list(StateManager.Get(f"team_battle.team.{team}.player").keys()):
                    if int(k) > number:
                        StateManager.Unset(f"team_battle.team.{team}.player.{k}")

        self.TotalScoreExport()

    def MovePlayer(self, team: int, p: TeamPlayerWidget, offset: int):
        players = self.Players(team)
        index = max(0, min(len(players) - 1, players.index(p) + offset))
        self.SwapPlayers(p, players[index])

    def SwapPlayers(self, p: TeamPlayerWidget, other: TeamPlayerWidget):
        """Swaps two players' data. The active and eliminated checkboxes go
        with the data, so the tracking follows the players to their new place."""
        if p is other:
            return

        self.swapping = True
        try:
            p.SwapWith(other)
        finally:
            self.swapping = False

        def swapped(w):
            return other if w is p else p if w is other else w

        for team in [1, 2]:
            self.advanceHistory[team] = [swapped(w) for w in self.advanceHistory[team]]
        self.firstToVictims = {
            swapped(winner): swapped(victim) for winner, victim in self.firstToVictims.items()
        }

    def ApplyVisibility(self, pw):
        if hasattr(self, "elements"):
            for element in self.elements:
                visible = SettingsManager.Get(f"display_options.{element[2]}", True)
                for el in element[1]:
                    w = pw.findChild(QWidget, el)
                    if w:
                        w.setVisible(visible)

    def ToggleElements(self, action: QAction, elements):
        for pw in self.playerWidgets:
            for element in elements:
                w = pw.findChild(QWidget, element)
                if w:
                    w.setVisible(action.isChecked())

    # =====================================================
    # ACTIVE PLAYERS
    # =====================================================
    def GetActiveIndex(self, team: int) -> int:
        return self.currentActiveIndexTeam1 if team == 1 else self.currentActiveIndexTeam2

    def ActivePlayer(self, team: int) -> TeamPlayerWidget | None:
        index = self.GetActiveIndex(team)
        players = self.Players(team)
        if 0 <= index < len(players):
            return players[index]
        return None

    def SetActiveIndex(self, team: int, index: int):
        oldIndex = self.GetActiveIndex(team)
        if team == 1:
            self.currentActiveIndexTeam1 = index
        else:
            self.currentActiveIndexTeam2 = index

        # Exported as the player's number in team_battle.team.<team>.player
        StateManager.Set(
            f"team_battle.team.{team}.active_player", index + 1 if index >= 0 else None
        )

        if index != oldIndex:
            if team == 1:
                self.signals.team1_active_player_changed.emit(index)
            else:
                self.signals.team2_active_player_changed.emit(index)

    def SetActivePlayer(self, team: int, index: int):
        """Makes the player at index (from 0) the team's active player."""
        players = self.Players(team)
        if 0 <= index < len(players):
            players[index].SetActiveStatus(True)

    def PlayerActiveChanged(self, team: int, p: TeamPlayerWidget, active: bool):
        players = self.Players(team)
        if p not in players:
            return

        if not active:
            if self.ActivePlayer(team) is p:
                self.SetActiveIndex(team, -1)
            return

        newPlayer = self.ActivePlayer(team) is not p
        self.SetActiveIndex(team, players.index(p))

        # A team has one active player at a time
        for other in players:
            if other is not p and other.IsActive():
                other.SetActiveStatus(False)

        # First To: a new player coming in starts a new matchup, so the
        # opponents who beat the last player start counting from 0 again.
        # Swapping places doesn't bring in anyone new.
        if (
            newPlayer
            and not self.swapping
            and not self.bulkUpdate
            and self.battleMode is TeamBattleModeEnum.FIRST_TO
        ):
            self.ResetFirstToWinners(self.OtherTeam(team))

    def NextActivePlayer(self, team: int) -> bool:
        """Makes the next player in line who isn't eliminated active, going
        back to the first player after the last one. Returns whether the
        active player changed."""
        players = self.Players(team)
        start = self.GetActiveIndex(team)
        for step in range(1, len(players) + 1):
            index = (start + step) % len(players)
            if not players[index].IsEliminated():
                if index == start:
                    return False
                players[index].SetActiveStatus(True)
                return True
        return False

    def Team1NextUp(self):
        self.NextActivePlayer(1)

    def Team2NextUp(self):
        self.NextActivePlayer(2)

    def PlayerEliminatedChanged(self, team: int, p: TeamPlayerWidget, dead: bool):
        if self.swapping or self.bulkUpdate:
            return
        if dead and p is self.ActivePlayer(team) and self.autoAdvance.isChecked():
            if self.NextActivePlayer(team):
                self.advanceHistory[team].append(p)

    # =====================================================
    # FIRST TO
    # =====================================================
    def PlayerReachedFirstTo(self, team: int, p: TeamPlayerWidget, reached: bool):
        """Reaching the "First To" amount eliminates the opposing active
        player. Going back under it (an undo) brings them back."""
        if self.battleMode is not TeamBattleModeEnum.FIRST_TO:
            return
        if self.swapping or self.bulkUpdate:
            return

        otherTeam = self.OtherTeam(team)

        if reached:
            if p in self.firstToVictims:
                return
            victim = self.ActivePlayer(otherTeam)
            if victim is None or victim.IsEliminated():
                return
            self.firstToVictims[p] = victim
            victim.SetEliminatedStatus(True)
        else:
            victim = self.firstToVictims.pop(p, None)
            if victim is None or victim not in self.Players(otherTeam):
                return
            history = self.advanceHistory[otherTeam]
            if history and history[-1] is victim:
                history.pop()
                victim.SetActiveStatus(True)
            victim.SetEliminatedStatus(False)

    def ResetFirstToWinners(self, team: int):
        for p in self.Players(team):
            if p in self.firstToVictims:
                # Forget the win first, so going back to 0 doesn't undo it
                del self.firstToVictims[p]
                p.ResetDynamicSpinner()

    # =====================================================
    # STOCK CONTROL
    # =====================================================
    def TeamScored(self, team: int):
        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            # The other team's active player loses a stock
            target = self.ActivePlayer(self.OtherTeam(team))
        else:
            # The team's active player wins a game
            target = self.ActivePlayer(team)
        if target is not None:
            target.IncreaseCall()

    def UndoTeamScored(self, team: int):
        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            otherTeam = self.OtherTeam(team)
            target = self.ActivePlayer(otherTeam)
            history = self.advanceHistory[otherTeam]
            # If the active player hasn't lost a stock yet, the last stock
            # taken was from the player auto advance moved away from
            if history and (target is None or target.GetSpinnerValue() >= self.livesNumber.value()):
                previous = history.pop()
                if previous in self.Players(otherTeam):
                    previous.SetActiveStatus(True)
                    target = previous
        else:
            target = self.ActivePlayer(team)
        if target is not None:
            target.DecreaseCall()

    def T1_Stock_Up(self):
        self.TeamScored(1)

    def T1_Stock_Down(self):
        self.UndoTeamScored(1)

    def T2_Stock_Up(self):
        self.TeamScored(2)

    def T2_Stock_Down(self):
        self.UndoTeamScored(2)

    # =====================================================
    # EXPORTS
    # =====================================================

    def Team1SponsorExport(self):
        path = f"team_battle.team.{1}"
        team = self.team1column.findChild(QLineEdit, "teamName").text()
        StateManager.Set(path + ".sponsor", team)
        SponsorHelper.ExportValidSponsors(team, path)

    def Team2SponsorExport(self):
        path = f"team_battle.team.{2}"
        team = self.team2column.findChild(QLineEdit, "teamName").text()
        StateManager.Set(path + ".sponsor", team)
        SponsorHelper.ExportValidSponsors(team, path)

    def PhaseExport(self):
        StateManager.Set("team_battle.phase", self.phaseCombo.currentText())

    def MatchExport(self):
        StateManager.Set("team_battle.match", self.matchCombo.currentText())

    def TotalScoreExport(self):
        self.Team1TotalScoreExport()
        self.Team2TotalScoreExport()

    def Team1TotalScoreExport(self):
        scoreCount = 0
        for player in self.team1playerWidgets:
            scoreCount += player.GetSpinnerValue()
        StateManager.Set("team_battle.team1_spinner-total", scoreCount)
        StateManager.Set("team_battle.team1_total-score", self.team1score.value())

    def Team2TotalScoreExport(self):
        scoreCount = 0
        for player in self.team2playerWidgets:
            scoreCount += player.GetSpinnerValue()
        StateManager.Set("team_battle.team2_spinner-total", scoreCount)
        StateManager.Set("team_battle.team2_total-score", self.team2score.value())
