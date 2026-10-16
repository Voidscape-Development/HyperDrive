# The bar a scoreboard shows while it follows a set, a stream or a station:
# what it follows, when it checks again, the set on it now and the next one,
# and buttons to change what it follows or stop.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .SelectSetWindow import ScaledFont, ThemeColors
from .SelectStationWindow import QueueFor, QueueSets, SetLine
from .Theme import Theme, ThemedIcon

MODE_SET = "set"
MODE_STREAM = "stream"
MODE_STATION = "station"

# start.gg's state of a finished set
STATE_COMPLETED = 3


def TrackingTitle(mode, name=""):
    if mode == MODE_STREAM:
        return QApplication.translate("app", "Tracking stream {0}").format(name)
    if mode == MODE_STATION:
        return QApplication.translate("app", "Tracking station {0}").format(name)
    return QApplication.translate("app", "Keeping this set updated")


def CountdownText(remainingMs):
    if remainingMs is None:
        return QApplication.translate("app", "checking now...")
    return QApplication.translate("app", "checks again in {0}s").format(
        -(-int(remainingMs) // 1000)
    )


def NextQueued(sets, currentId):
    """The first set of a queue that isn't the one on the scoreboard and
    isn't finished, None for none."""
    for s in sets or []:
        if not s:
            continue
        if currentId is not None and str(s.get("id")) == str(currentId):
            continue
        if s.get("state") == STATE_COMPLETED:
            continue
        return s
    return None


def QueueOf(mode, name, streamQueues, stationQueue):
    """The sets queued after the one on the scoreboard: a stream's from the
    stream queue ({stream name: [sets]}), a station's from its queue
    ({"1": set, ...}). [] for a set."""
    if mode == MODE_STREAM:
        return QueueFor({"identifier": name}, streamQueues) or []
    if mode == MODE_STATION:
        return QueueSets(stationQueue)
    return []


class TrackingBar(QFrame):
    changeClicked = Signal()
    stopClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trackingBar")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        top.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.titleLabel = QLabel()
        self.titleLabel.setFont(ScaledFont(self.font(), bold=True))
        top.addWidget(self.titleLabel)
        self.countdownLabel = QLabel()
        top.addWidget(self.countdownLabel, 1)
        self.changeButton = QPushButton(QApplication.translate("app", "Change"))
        self.changeButton.setAutoDefault(False)
        self.changeButton.clicked.connect(self.changeClicked.emit)
        top.addWidget(self.changeButton)
        self.stopButton = QPushButton(QApplication.translate("app", "Stop"))
        self.stopButton.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.stopButton.setIconSize(QSize(12, 12))
        self.stopButton.setAutoDefault(False)
        self.stopButton.clicked.connect(self.stopClicked.emit)
        top.addWidget(self.stopButton)
        layout.addLayout(top)

        # Now and next
        sets = QGridLayout()
        sets.setHorizontalSpacing(10)
        sets.setVerticalSpacing(2)
        sets.setColumnStretch(1, 1)
        self.nowName = QLabel(QApplication.translate("app", "Now"))
        self.nowName.setFont(ScaledFont(self.font(), bold=True))
        self.nowLabel = QLabel()
        self.nextName = QLabel(QApplication.translate("app", "Next"))
        self.nextName.setFont(ScaledFont(self.font(), bold=True))
        self.nextLabel = QLabel()
        for label in [self.nowLabel, self.nextLabel]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            # Long sets don't widen the scoreboard
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sets.addWidget(self.nowName, 0, 0)
        sets.addWidget(self.nowLabel, 0, 1)
        sets.addWidget(self.nextName, 1, 0)
        sets.addWidget(self.nextLabel, 1, 1)
        layout.addLayout(sets)

        self.mode = MODE_SET
        self.ApplyStyle()
        self.SetSets(None, None)

    def ApplyStyle(self):
        colors = ThemeColors()
        # Styling it changes its palette again: only once per theme
        if colors == getattr(self, "colors", None):
            return
        # Before styling, which sends the palette change straight away
        self.colors = colors
        radius = Theme.Radius()
        self.setStyleSheet(f"""
            QFrame#trackingBar {{
                background: {colors["selected"].name()};
                border: 1px solid {colors["accent"].name()};
                border-radius: {radius + 2}px;
            }}
        """)
        self.dot.setStyleSheet(f"background: {colors['accent'].name()}; border-radius: 4px;")
        self.countdownLabel.setStyleSheet(f"color: {colors['text'].name()};")
        self.nowName.setStyleSheet(f"color: {colors['accentText'].name()};")
        self.nextName.setStyleSheet(f"color: {colors['text'].name()};")

    def changeEvent(self, event):
        # The theme changed
        if event.type() == QEvent.Type.PaletteChange:
            self.ApplyStyle()
        super().changeEvent(event)

    def SetTracking(self, mode, name=""):
        self.mode = mode
        self.titleLabel.setText(TrackingTitle(mode, name))
        self.changeButton.setToolTip(
            QApplication.translate("app", "Track another stream or station")
            if mode in (MODE_STREAM, MODE_STATION)
            else QApplication.translate("app", "Load another set")
        )
        self.stopButton.setToolTip(
            QApplication.translate("app", "Stop updating the scoreboard from the bracket")
        )

    def SetCountdown(self, remainingMs):
        self.countdownLabel.setText("·  " + CountdownText(remainingMs))

    def SetSets(self, now, following, waiting=False):
        """now: the set on the scoreboard, following: the next one queued;
        either may be None. waiting: tracking from the next set, which hasn't
        come yet."""
        if now is not None:
            self.nowLabel.setText(SetLine(now))
        elif waiting:
            self.nowLabel.setText(QApplication.translate("app", "Waiting for the next set"))
        else:
            self.nowLabel.setText(QApplication.translate("app", "No set yet"))
        # A set has no queue
        showNext = self.mode in (MODE_STREAM, MODE_STATION)
        self.nextName.setVisible(showNext)
        self.nextLabel.setVisible(showNext)
        self.nextLabel.setText(
            SetLine(following) if following else QApplication.translate("app", "Nothing queued")
        )
        # Long sets are cut short on screen, whole in the tooltip
        self.nowLabel.setToolTip(self.nowLabel.text())
        self.nextLabel.setToolTip(self.nextLabel.text())
