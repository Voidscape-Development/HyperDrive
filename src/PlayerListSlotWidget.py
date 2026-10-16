import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .DisplayOptions import ApplyHiddenElements
from .ScoreboardPlayerWidget import ScoreboardPlayerWidget
from .StateManager import StateManager
from .Theme import ThemedIcon


class PlayerListSlotWidgetSignals(QObject):
    dataChanged = Signal()
    # Folded or unfolded with its arrow
    collapsedChanged = Signal(bool)


class PlayerListSlotWidget(QGroupBox):
    def __init__(self, index, playerList, base="player_list", *args):
        super().__init__(*args)
        self.index = index
        self.playerList = playerList

        self.base = base

        self.signals = PlayerListSlotWidgetSignals()

        self.setLayout(QVBoxLayout())

        # The slot's title: its place, team name and score, still shown
        # (and edited) when the slot is collapsed to it
        header = QHBoxLayout()
        header.setSpacing(6)
        self.layout().addLayout(header)

        self.collapsed = False
        self.collapseButton = QToolButton()
        self.collapseButton.setAutoRaise(True)
        self.collapseButton.setFixedSize(24, 24)
        self.collapseButton.clicked.connect(self.ToggleCollapsed)
        header.addWidget(self.collapseButton)

        numberLabel = QLabel(f"{index}.")
        numberLabel.setStyleSheet("font-weight: bold;")
        # Room for two digits, so the names line up from slot to slot
        bold = QFont(numberLabel.font())
        bold.setBold(True)
        numberLabel.setMinimumWidth(QFontMetrics(bold).horizontalAdvance("00."))
        numberLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(numberLabel)

        self.slotName = QLineEdit()
        self.slotName.setToolTip(QApplication.translate("Form", "Team Name"))
        self.slotName.setAccessibleName(QApplication.translate("Form", "Team Name"))
        header.addWidget(self.slotName, 1)

        self.scoreWidget = QWidget()
        self.scoreWidget.setLayout(QHBoxLayout())
        self.scoreWidget.layout().setContentsMargins(0, 0, 0, 0)
        scoreLabel = QLabel()
        scoreLabel.setText(QApplication.translate("app", "Score"))
        score = QSpinBox()
        score.setMaximum(999999)
        self.scoreWidget.layout().addWidget(scoreLabel)
        self.scoreWidget.layout().addWidget(score)
        score.editingFinished.connect(
            lambda: [StateManager.Set(f"{self.base}.slot.{self.index}.score", score.value())]
        )
        header.addWidget(self.scoreWidget)
        score.editingFinished.emit()
        self.scoreWidget.setVisible(False)

        self.childDataChangedLock = False

        self.slotName.editingFinished.connect(
            lambda: [StateManager.Set(f"{self.base}.slot.{self.index}.name", self.slotName.text())]
        )
        self.slotName.editingFinished.emit()

        self.list = QWidget()
        self.list.setLayout(QHBoxLayout())
        self.layout().addWidget(self.list)

        self.playerWidgets = []

        self.UpdateCollapseButton()
        self.UpdatePlaceholder()

    # =====================================================
    # COLLAPSING
    # =====================================================
    def ToggleCollapsed(self):
        self.SetCollapsed(not self.collapsed)
        self.signals.collapsedChanged.emit(self.collapsed)

    def SetCollapsed(self, collapsed):
        """Folds the slot to its title row, or shows its players."""
        self.collapsed = collapsed
        self.list.setVisible(not collapsed)
        self.UpdateCollapseButton()

    def UpdateCollapseButton(self):
        self.collapseButton.setIcon(
            ThemedIcon(
                "assets/icons/arrow_right.svg" if self.collapsed else "assets/icons/arrow_down.svg"
            )
        )
        self.collapseButton.setToolTip(
            QApplication.translate("app", "Show players")
            if self.collapsed
            else QApplication.translate("app", "Hide players")
        )

    def UpdatePlaceholder(self):
        # With no team name, the players' tags hint at who is in the slot
        tags = [pw.GetCurrentPlayerTag().strip() for pw in self.playerWidgets]
        tags = [t for t in tags if t]
        self.slotName.setPlaceholderText(
            " / ".join(tags) if tags else QApplication.translate("Form", "Team Name")
        )

    # =====================================================
    # SIZE
    # =====================================================
    def SetPlayersPerTeam(self, number):
        # logger.info(f"PlayerListSlotWidget#SetPlayersPerTeam({number})")
        if number != len(self.playerWidgets):
            with StateManager.SaveBlock():
                self.DoSetPlayersPerTeam(number)
        # if number > 1:
        #     self.team1column.findChild(QLineEdit, "teamName").setVisible(True)
        #     self.team2column.findChild(QLineEdit, "teamName").setVisible(True)
        # else:
        #     self.team1column.findChild(QLineEdit, "teamName").setVisible(False)
        #     self.team1column.findChild(QLineEdit, "teamName").setText("")
        #     self.team2column.findChild(QLineEdit, "teamName").setVisible(False)
        #     self.team2column.findChild(QLineEdit, "teamName").setText("")

    def DoSetPlayersPerTeam(self, number):
        while len(self.playerWidgets) < number:
            p = ScoreboardPlayerWidget(
                index=len(self.playerWidgets) + 1,
                teamNumber=1,
                path=f"{self.base}.slot.{self.index}.player.{len(self.playerWidgets) + 1}",
            )
            self.playerWidgets.append(p)
            # At the top, also when a player beside it has its details shown
            self.list.layout().addWidget(p, 0, Qt.AlignmentFlag.AlignTop)
            self.playerList.dragBoard.Register(p)

            p.SetCharactersPerPlayer(self.playerList.charactersPerPlayer)
            ApplyHiddenElements(p, self.playerList.hiddenElements)

            index = len(self.playerWidgets) - 1

            p.btMoveUp.clicked.connect(
                lambda x=None, index=index, p=p: p.SwapWith(
                    self.playerWidgets[max(0, self.playerWidgets.index(p) - 1)]
                )
            )
            p.btMoveDown.clicked.connect(
                lambda x=None, index=index, p=p: p.SwapWith(
                    self.playerWidgets[
                        min(len(self.playerWidgets) - 1, self.playerWidgets.index(p) + 1)
                    ]
                )
            )

            p.instanceSignals.dataChanged.connect(self.ChildDataChangedEmit)

            # Folded as it was last time, or as the list's "compact players" says
            p.SetDetailsShown(self.playerList.PlayerDetailsShown(self.index, p.index))
            # After the player's own handler, so detailsShown is the new state
            p.detailsButton.clicked.connect(
                lambda x=None, p=p: self.playerList.SavePlayerDetailsShown(
                    self.index, p.index, p.detailsShown
                )
            )

        while len(self.playerWidgets) > number:
            p = self.playerWidgets[-1]
            p.setParent(None)
            self.playerWidgets.remove(p)
            StateManager.Unset(p.path)
            p.deleteLater()

        self.UpdatePlaceholder()

    def SetCharacterNumber(self, value):
        # logger.info(f"PlayerListSlotWidget#SetCharacterNumber({value})")
        with StateManager.SaveBlock():
            for pw in self.playerWidgets:
                pw.SetCharactersPerPlayer(value)

    # =====================================================
    # TEAM DATA
    # =====================================================
    def SetTeamData(self, data, enrichBlocking=True):
        data = data or {}

        try:
            with StateManager.SaveBlock():
                self.childDataChangedLock = True

                if data.get("name"):
                    self.slotName.setText(data.get("name"))
                    self.slotName.editingFinished.emit()
                else:
                    self.slotName.setText("")
                    self.slotName.editingFinished.emit()

                StateManager.Set(f"{self.base}.slot.{self.index}.wins", data.get("wins"))
                StateManager.Set(f"{self.base}.slot.{self.index}.loses", data.get("losses"))
                StateManager.Set(
                    f"{self.base}.slot.{self.index}.winPercentage", data.get("winPercentage")
                )

                for i, pw in enumerate(self.playerWidgets):
                    if data.get("players"):
                        try:
                            data.get("players")[i]["wins"] = data.get("wins")
                            data.get("players")[i]["losses"] = data.get("losses")
                            data.get("players")[i]["winPercentage"] = data.get("winPercentage")
                            pw.SetData(data.get("players")[i], enrichBlocking=enrichBlocking)
                        except:
                            pw.Clear()
                            logger.error(traceback.format_exc())
                    else:
                        pw.Clear()
        finally:
            self.childDataChangedLock = False

        self.UpdatePlaceholder()
        self.signals.dataChanged.emit()

    def Clear(self):
        try:
            with StateManager.SaveBlock():
                self.childDataChangedLock = True
                for i, pw in enumerate(self.playerWidgets):
                    pw.Clear()
        finally:
            self.childDataChangedLock = False

        self.UpdatePlaceholder()
        self.signals.dataChanged.emit()

    def ChildDataChangedEmit(self):
        if not self.childDataChangedLock:
            self.UpdatePlaceholder()
            self.signals.dataChanged.emit()
