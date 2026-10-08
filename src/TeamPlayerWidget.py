from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .PlayerRowParts import SetRole, SetStyleProperty, SmallFont
from .ScoreboardPlayerWidget import ScoreboardPlayerWidget, ScoreboardPlayerWidgetSignals
from .StateManager import StateManager
from .TeamBattleModeEnum import TeamBattleModeEnum
from .Theme import Theme


class TeamPlayerWidgetSignals(ScoreboardPlayerWidgetSignals):
    dynamicSpinner_changed = Signal()
    activeStatus_changed = Signal(int)
    deathStatus_changed = Signal(int)
    toggleDeathTrigger = Signal(bool)


class StockPips(QWidget):
    """The player's stocks as dots (Stock Pool), or games won (First To)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.maximum = 0
        self.dots = True
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def SetValue(self, value, maximum, dots):
        self.value, self.maximum, self.dots = value, maximum, dots
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        if self.dots and 0 < self.maximum <= 8:
            return QSize(self.maximum * 12, 20)
        return QSize(32, 20)

    def paintEvent(self, event):
        colors = Theme.Colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.dots and 0 < self.maximum <= 8:
            for i in range(self.maximum):
                rect = QRectF(i * 12 + 1.5, 5.5, 9, 9)
                if i < self.value:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(colors["accent"])
                else:
                    painter.setPen(QPen(colors["border"], 1.5))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(rect)
        else:
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() * 1.25)
            painter.setFont(font)
            painter.setPen(colors["text"])
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.value))


class TeamPlayerWidget(ScoreboardPlayerWidget):
    """A Crew/Team Battle player: the scoreboard's player row with the
    battle controls in it. ACTIVE marks who is playing, OUT who is
    eliminated, and the stocks left (Stock Pool) or games won (First To)
    sit at the end of the row."""

    SignalsClass = TeamPlayerWidgetSignals

    defaultSpinnerValue = 0
    battleMode: TeamBattleModeEnum = TeamBattleModeEnum.STOCK_POOL
    dynamicSpinner: QSpinBox = None

    def __init__(self, index=0, teamNumber=0, path="", *args):
        # Loading a player into the slot keeps their stocks/games
        self.keepBattleValues = False

        self.battleControls = QWidget()
        super().__init__(index, teamNumber, path, "", *args)

        # Seeds don't matter in a crew battle
        for name in ("seed", "seedLabel"):
            self.SetElementVisible(name, False)

        # ---------- battle controls, in the row ----------
        controls = QHBoxLayout(self.battleControls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(4)

        self.order = QLabel()
        SetRole(self.order, "muted")
        SmallFont(self.order, 0.85)
        self.order.setMinimumWidth(16)
        self.order.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.layout().insertWidget(1, self.order)

        active = QCheckBox(QApplication.translate("app", "ACTIVE"))
        active.setObjectName("activePlayer")
        SetRole(active, "pill", tone="accent")
        SmallFont(active, 0.8, bold=True)
        active.setToolTip(QApplication.translate("app", "The team's player who is playing"))
        dead = QCheckBox(QApplication.translate("app", "OUT"))
        dead.setObjectName("dead")
        SetRole(dead, "pill", tone="danger")
        SmallFont(dead, 0.8, bold=True)
        dead.setToolTip(QApplication.translate("app", "Eliminated"))
        statusRow = QHBoxLayout()
        statusRow.setContentsMargins(0, 2, 0, 0)
        statusRow.setSpacing(4)
        statusRow.addWidget(active)
        statusRow.addWidget(dead)
        statusRow.addStretch()
        # Under the tag and its summary
        self.whoLayout.addLayout(statusRow)

        self.dynamicSpinner = QSpinBox()
        self.dynamicSpinner.setObjectName("dynamicSpinner")
        self.dynamicSpinner.hide()
        self.dynamicLabel = QLabel(self)
        self.dynamicLabel.setObjectName("dynamicLabel")
        self.dynamicLabel.hide()

        self.minusBt = QPushButton("−")
        self.minusBt.setFixedSize(24, 24)
        self.minusBt.setStyleSheet("padding: 0px;")
        self.minusBt.clicked.connect(lambda: self.ChangeSpinner(-1))
        self.pips = StockPips()
        self.plusBt = QPushButton("+")
        self.plusBt.setFixedSize(24, 24)
        self.plusBt.setStyleSheet("padding: 0px;")
        self.plusBt.clicked.connect(lambda: self.ChangeSpinner(1))
        controls.addWidget(self.minusBt)
        controls.addWidget(self.pips)
        controls.addWidget(self.plusBt)
        controls.addWidget(self.dynamicSpinner)
        # Before the database dot and the details button
        self.header.layout().insertWidget(self.header.layout().count() - 2, self.battleControls)

        self.dimEffect = QGraphicsOpacityEffect(self.header)
        self.dimEffect.setOpacity(0.5)
        self.dimEffect.setEnabled(False)
        self.header.setGraphicsEffect(self.dimEffect)

        dead.toggled.connect(
            lambda state: [
                self.ExportEliminatedStatus(),
                self.RefreshBattleState(),
                self.instanceSignals.deathStatus_changed.emit(int(state)),
            ]
        )

        active.toggled.connect(
            lambda state: [
                self.ExportActiveStatus(),
                self.RefreshBattleState(),
                self.instanceSignals.activeStatus_changed.emit(int(state)),
            ]
        )

        self.dynamicSpinner.valueChanged.connect(self.instanceSignals.dynamicSpinner_changed.emit)
        self.dynamicSpinner.valueChanged.connect(self.SpinnerHandling)
        self.dynamicSpinner.valueChanged.connect(self.RefreshBattleState)

        self.SetIndex(index, teamNumber)
        self.SetEliminatedStatus()
        self.RefreshBattleState()

    def GetIndex(self):
        return self.index

    def SetIndex(self, index: int, team: int):
        super().SetIndex(index, team)
        if hasattr(self, "order"):
            self.order.setText(str(index))

    def RefreshBattleState(self, *args):
        if not hasattr(self, "pips"):
            return
        maximum = self.defaultSpinnerValue
        stock = self.battleMode is TeamBattleModeEnum.STOCK_POOL
        self.pips.SetValue(self.dynamicSpinner.value(), maximum, stock)
        self.pips.setToolTip(
            QApplication.translate("app", "{0} of {1} stocks left").format(
                self.dynamicSpinner.value(), maximum
            )
            if stock
            else QApplication.translate("app", "{0} games won (first to {1})").format(
                self.dynamicSpinner.value(), maximum
            )
        )
        self.minusBt.setToolTip(
            QApplication.translate("app", "Lose a stock")
            if stock
            else QApplication.translate("app", "Remove a game won")
        )
        self.plusBt.setToolTip(
            QApplication.translate("app", "Give a stock back")
            if stock
            else QApplication.translate("app", "Win a game")
        )
        SetStyleProperty(self, "active", self.IsActive() and not self.IsEliminated())
        self.dimEffect.setEnabled(self.IsEliminated())
        name = self.findChild(QLineEdit, "name")
        font = QFont(name.font())
        font.setStrikeOut(self.IsEliminated())
        name.setFont(font)

    def ChangeSpinner(self, delta):
        self.dynamicSpinner.setValue(self.dynamicSpinner.value() + delta)

    # =====================================================
    # BATTLE SPECIFIC CALLS
    # =====================================================
    def ToggleSponsorDisplay(self):
        team = self.findChild(QLineEdit, "team")
        team.setVisible(team.isHidden())

    def SetBattleMode(self, mode: TeamBattleModeEnum):
        self.battleMode = mode
        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            self.SetDynamicSpinnerLabelText(QApplication.translate("app", "STOCKS/LIVES"))
        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            self.SetDynamicSpinnerLabelText(QApplication.translate("app", "GAMES WON"))
        self.RefreshBattleState()

    def SetDefaultSpinnerValue(self, value: int):
        self.defaultSpinnerValue = value
        self.dynamicSpinner.setMaximum(value)
        self.ResetDynamicSpinner()
        self.RefreshBattleState()

    # Changes based on battle mode
    def SetDynamicSpinnerLabelText(self, text: str):
        self.dynamicLabel.setText(text)

    def GetSpinnerValue(self):
        return self.dynamicSpinner.value()

    def ResetDynamicSpinner(self):
        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            self.dynamicSpinner.setValue(self.defaultSpinnerValue)
        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            self.dynamicSpinner.setValue(0)
        self.findChild(QCheckBox, "dead").setChecked(False)

    def IsActive(self):
        return self.findChild(QCheckBox, "activePlayer").isChecked()

    def SetActiveStatus(self, status: bool):
        self.findChild(QCheckBox, "activePlayer").setChecked(status)
        self.ExportActiveStatus()

    def IsEliminated(self):
        return self.findChild(QCheckBox, "dead").isChecked()

    def SetEliminatedStatus(self, status: bool = False):
        self.findChild(QCheckBox, "dead").setChecked(status)
        self.ExportEliminatedStatus()

    def SpinnerHandling(self):
        value = self.dynamicSpinner
        StateManager.Set(f"{self.path}.dynamic_spinner", value.value())
        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            if value.value() <= 0:
                self.SetEliminatedStatus(True)
            else:
                self.SetEliminatedStatus(False)

        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            # Without a "First To" amount there is nothing to reach
            if self.defaultSpinnerValue > 0 and value.value() >= self.defaultSpinnerValue:
                self.instanceSignals.toggleDeathTrigger.emit(True)
            else:
                self.instanceSignals.toggleDeathTrigger.emit(False)

    def IncreaseCall(self):
        value = self.dynamicSpinner

        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            if value.value() <= 0:
                return
            value.setValue(value.value() - 1)

        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            if value.value() >= self.defaultSpinnerValue:
                return
            value.setValue(value.value() + 1)

    def DecreaseCall(self):
        value = self.dynamicSpinner

        if self.battleMode is TeamBattleModeEnum.STOCK_POOL:
            if value.value() >= self.defaultSpinnerValue:
                return
            value.setValue(value.value() + 1)
        elif self.battleMode is TeamBattleModeEnum.FIRST_TO:
            if value.value() <= 0:
                return
            value.setValue(value.value() - 1)

    # =====================================================
    # EXPORT CALLS
    # =====================================================
    def ExportActiveStatus(self):
        StateManager.Set(
            f"{self.path}.active", self.findChild(QCheckBox, "activePlayer").isChecked()
        )

    def ExportEliminatedStatus(self):
        StateManager.Set(f"{self.path}.dead", self.findChild(QCheckBox, "dead").isChecked())

    # =====================================================
    # DATA
    # =====================================================
    def SwapWith(self, other: TeamPlayerWidget, emitIdChanged=True):
        """Swaps the players, with their active and eliminated state and
        their stocks or games."""
        if self == other:
            return
        values = [self.dynamicSpinner.value(), other.dynamicSpinner.value()]
        super().SwapWith(other, emitIdChanged=emitIdChanged)
        self.dynamicSpinner.setValue(values[1])
        other.dynamicSpinner.setValue(values[0])
        for w in (self, other):
            w.ExportActiveStatus()
            w.ExportEliminatedStatus()
            w.RefreshBattleState()

    def SetData(self, data, dontLoadFromDB=False, clear=True, no_mains=False, enrichBlocking=True):
        self.keepBattleValues = True
        try:
            super().SetData(data, dontLoadFromDB, clear, no_mains, enrichBlocking)
        finally:
            self.keepBattleValues = False

    def Clear(self, no_mains=False, keep_battle_values=False):
        with StateManager.SaveBlock():
            self.DoClear(no_mains=no_mains, keep_battle_values=keep_battle_values)

    def DoClear(self, no_mains=False, keep_battle_values=False):
        keep = keep_battle_values or self.keepBattleValues
        value = self.dynamicSpinner.value()
        # Setting the stocks to 0 would eliminate the player: the row's
        # clear doesn't touch them, they go back to the mode's starting value
        with QSignalBlocker(self.dynamicSpinner):
            super().DoClear(no_mains=no_mains)
            self.dynamicSpinner.setValue(value)
        if not keep:
            self.ResetDynamicSpinner()
        self.RefreshBattleState()
