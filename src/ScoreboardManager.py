from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .ScoreboardWidget import ScoreboardWidget
from .StateManager import StateManager


class ScoreboardManagerSignals(QObject):
    ScoreboardAmountChanged = Signal(int)
    # Emitted with the scoreboard's number once it was created or removed
    ScoreboardAdded = Signal(int)
    ScoreboardRemoved = Signal(int)
    TabNamesChanged = Signal()


class ScoreboardManager(QDockWidget):
    instance: ScoreboardManager = None

    def __init__(self, *args):
        super().__init__(*args)

        StateManager.Unset("score")

        self.signals: ScoreboardManagerSignals = ScoreboardManagerSignals()
        logger.info("Scoreboard Manager - Initializing")

        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.widget.setLayout(QVBoxLayout())

        self.tabs = QTabWidget()
        self.widget.layout().addWidget(self.tabs)

        self.signals.ScoreboardAmountChanged.connect(lambda val: self.UpdateAmount(val))

        self.scoreboardholder = []

    def UpdateAmount(self, amount):
        added = None
        removed = None
        # BlockSaving() lives inside the try so that the finally below always
        # releases it, even if one of the calls in between raises.
        try:
            StateManager.BlockSaving()

            if amount > len(self.scoreboardholder):
                logger.info("Scoreboard Manager - Creating Scoreboard " + str(amount))

                scoreboard = QWidget()
                scoreboard.setLayout(QVBoxLayout())
                scoreboardObj = ScoreboardWidget(scoreboardNumber=amount)
                self.scoreboardholder.append(scoreboardObj)
                scoreboard.layout().addWidget(scoreboardObj)
                self.tabs.addTab(
                    scoreboard, QApplication.translate("app", "Scoreboard") + " " + str(amount)
                )
                # The teams, score and set source, next to the tab's name
                summary = QLabel()
                summary.setProperty("hdRole", "muted")
                font = QFont(summary.font())
                font.setPointSizeF(max(7.0, font.pointSizeF() * 0.85))
                summary.setFont(font)
                summary.setContentsMargins(0, 0, 6, 0)
                self.tabs.tabBar().setTabButton(
                    self.tabs.count() - 1, QTabBar.ButtonPosition.RightSide, summary
                )
                scoreboardObj.signals.SummaryChanged.connect(
                    lambda obj=scoreboardObj, label=summary: self.UpdateSummary(obj, label)
                )
                self.UpdateSummary(scoreboardObj, summary)
                added = amount
            else:
                logger.info("Scoreboard Manager - Removing Scoreboard " + str(amount + 1))
                self.tabs.removeTab(amount)
                self.scoreboardholder[amount].RemoveAutoUpdate()
                self.scoreboardholder[amount].deleteLater()
                self.scoreboardholder.pop(amount)
                StateManager.Unset(f"score.{amount + 1}")
                removed = amount + 1
        finally:
            StateManager.ReleaseSaving()

        if added is not None:
            self.signals.ScoreboardAdded.emit(added)
        if removed is not None:
            self.signals.ScoreboardRemoved.emit(removed)

    def UpdateSummary(self, scoreboard, label):
        try:
            text = scoreboard.Summary()
        except RuntimeError:
            # The scoreboard is being deleted
            return
        metrics = label.fontMetrics()
        label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, 260))
        label.setFixedWidth(metrics.horizontalAdvance(label.text()) + 8)
        label.setToolTip(text)
        index = (
            self.scoreboardholder.index(scoreboard) if scoreboard in self.scoreboardholder else -1
        )
        if index >= 0:
            self.tabs.setTabToolTip(index, text)
            # Setting the text again makes the tab take the label's new width
            self.tabs.setTabText(index, self.tabs.tabText(index))

    def GetScoreboard(self, number):
        if int(number) - 1 < len(self.scoreboardholder):
            return self.scoreboardholder[int(number) - 1]
        elif len(self.scoreboardholder) > 0:
            logger.error(
                f"Scoreboard Manager - Unable to retrieve scoreboard {number}, defaulting to scoreboard 1"
            )
            return self.scoreboardholder[0]
        else:
            logger.error(
                f"Scoreboard Manager - Unable to retrieve scoreboard {number}, no scoreboards available"
            )
            return None

    def SetTabName(self, index, name):
        if int(index) - 1 < self.tabs.count():
            if name != "":
                self.tabs.setTabText(int(index) - 1, name)
            else:
                self.tabs.setTabText(
                    int(index) - 1, QApplication.translate("app", "Scoreboard") + " " + str(index)
                )
            self.signals.TabNamesChanged.emit()
        else:
            logger.error(f"Invalid Scoreboard ID provided: {index}")
            logger.error(f"Please provide an ID between 1 and {self.tabs.count()}")

    def GetScoreboardNumbers(self):
        return list(range(1, len(self.scoreboardholder) + 1))

    def GetTabName(self, number):
        if 0 < int(number) <= self.tabs.count():
            return self.tabs.tabText(int(number) - 1)
        return QApplication.translate("app", "Scoreboard") + " " + str(number)

    def GetTabAmount(self):
        return self.tabs.count()


ScoreboardManager.instance = ScoreboardManager()
