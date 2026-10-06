# The bracket widget's controls for the bracket focus layout
# (layout/bracket_focus): zoom it to the sets and rounds selected in the
# bracket view, a player's run, the set on a scoreboard, or a tour of the
# rounds. They act on the focus channel picked here.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketFocus import BracketFocus
from .BracketView import BracketView
from .Helpers.BracketFocusHelper import *
from .SettingsManager import SettingsManager


class BracketFocusBar(QWidget):
    def __init__(self, view: BracketView, parent=None):
        super().__init__(parent)
        self.view = view
        self.focus = BracketFocus.instance

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        title = QLabel(QApplication.translate("app", "Layout focus"))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        title.setToolTip(
            QApplication.translate(
                "app",
                "What the bracket focus layout (layout/bracket_focus) zooms to. Ctrl+click sets and round names to select them.",
            )
        )
        layout.addWidget(title)

        # The channel the controls act on
        self.channel = QComboBox()
        self.channel.setMinimumWidth(90)
        self.channel.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.channel.setToolTip(
            QApplication.translate(
                "app",
                "Focus channel: each bracket focus layout shows one, picked with ?channel=<name> in its URL (main without it)",
            )
        )
        self.channel.activated.connect(
            lambda index: self.focus.SetCurrent(self.channel.itemData(index))
        )
        layout.addWidget(self.channel)
        self.btChannels = QToolButton()
        self.btChannels.setText("⋯")
        self.btChannels.setToolTip(QApplication.translate("app", "Add, rename or remove channels"))
        self.btChannels.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.btChannels)
        menu.addAction(QApplication.translate("app", "New channel..."), self.AddChannel)
        self.actRename = menu.addAction(
            QApplication.translate("app", "Rename channel..."), self.RenameChannel
        )
        self.actRemove = menu.addAction(
            QApplication.translate("app", "Remove channel"), self.RemoveChannel
        )
        self.btChannels.setMenu(menu)
        layout.addWidget(self.btChannels)

        self.btAll = QPushButton(QApplication.translate("app", "Whole bracket"))
        self.btAll.setToolTip(QApplication.translate("app", "Show the whole bracket"))
        self.btAll.clicked.connect(lambda: self.Ch().ShowAll())
        layout.addWidget(self.btAll)

        self.btSelected = QPushButton()
        self.btSelected.setToolTip(
            QApplication.translate(
                "app", "Zoom to the sets and rounds selected with Ctrl+click, and highlight them"
            )
        )
        self.btSelected.clicked.connect(self.FocusSelected)
        layout.addWidget(self.btSelected)

        self.btClearSelection = QPushButton(QApplication.translate("app", "Unselect"))
        self.btClearSelection.clicked.connect(self.view.ClearSelection)
        layout.addWidget(self.btClearSelection)

        self.btPrevious = QPushButton("◀")
        self.btPrevious.setToolTip(QApplication.translate("app", "Previous round"))
        self.btPrevious.setMaximumWidth(32)
        self.btPrevious.clicked.connect(lambda: self.Ch().MoveRound(-1))
        layout.addWidget(self.btPrevious)
        self.btNext = QPushButton("▶")
        self.btNext.setToolTip(QApplication.translate("app", "Next round"))
        self.btNext.setMaximumWidth(32)
        self.btNext.clicked.connect(lambda: self.Ch().MoveRound(1))
        layout.addWidget(self.btNext)

        self.player = QComboBox()
        self.player.setMinimumWidth(140)
        self.player.setToolTip(
            QApplication.translate("app", "Zoom to every set of a player, and highlight them")
        )
        self.player.activated.connect(self.PlayerPicked)
        layout.addWidget(self.player)

        self.btFollow = QPushButton(QApplication.translate("app", "Follow scoreboard"))
        self.btFollow.setCheckable(True)
        self.btFollow.setToolTip(
            QApplication.translate(
                "app",
                "Keep zooming to the set on this scoreboard: the one with its start.gg set, or between its two players",
            )
        )
        self.btFollow.clicked.connect(
            lambda on: self.Ch().Follow(self.scoreboard.value()) if on else self.Ch().ShowAll()
        )
        layout.addWidget(self.btFollow)
        self.scoreboard = QSpinBox()
        self.scoreboard.setMinimum(1)
        self.scoreboard.setMaximum(99)
        self.scoreboard.setToolTip(QApplication.translate("app", "Scoreboard to follow"))
        self.scoreboard.valueChanged.connect(
            lambda value: (
                self.Ch().Follow(value) if self.Ch().request.get("mode") == MODE_FOLLOW else None
            )
        )
        layout.addWidget(self.scoreboard)

        self.btTour = QPushButton(QApplication.translate("app", "Round tour"))
        self.btTour.setCheckable(True)
        self.btTour.setToolTip(
            QApplication.translate(
                "app", "Show the whole bracket, then each round in turn, over and over"
            )
        )
        self.btTour.clicked.connect(
            lambda on: self.Ch().Tour(self.interval.value()) if on else self.Ch().ShowAll()
        )
        layout.addWidget(self.btTour)
        self.interval = QSpinBox()
        self.interval.setMinimum(MIN_INTERVAL)
        self.interval.setMaximum(MAX_INTERVAL)
        self.interval.setSuffix(QApplication.translate("app", " s"))
        self.interval.setToolTip(QApplication.translate("app", "Time on each step of the tour"))
        self.interval.setValue(
            SettingsManager.Get("bracket_focus_tour_interval", DEFAULT_INTERVAL) or DEFAULT_INTERVAL
        )
        self.interval.valueChanged.connect(
            lambda value: (
                self.Ch().Tour(value) if self.Ch().request.get("mode") == MODE_TOUR else None
            )
        )
        layout.addWidget(self.interval)

        self.status = QLabel()
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(self.status)
        layout.addStretch()

        self.view.signals.selectionChanged.connect(self.UpdateSelection)
        self.view.signals.focusSets.connect(lambda ids: self.Ch().FocusSets(ids))
        self.view.signals.focusRounds.connect(lambda keys: self.Ch().FocusRounds(keys))
        self.view.signals.focusPlayer.connect(lambda player: self.Ch().FocusPlayer(player))
        self.focus.signals.changed.connect(
            lambda name: self.UpdateFocus() if name == self.focus.current else None
        )
        self.focus.signals.channelsChanged.connect(self.UpdateChannels)

        self.UpdateSelection()
        self.UpdateChannels()

    def Ch(self):
        """The channel the controls act on."""
        return self.focus.Current()

    # Channels

    def UpdateChannels(self):
        self.channel.blockSignals(True)
        self.channel.clear()
        for name in self.focus.channels:
            self.channel.addItem(name, name)
        self.channel.setCurrentIndex(max(0, self.channel.findData(self.focus.current)))
        self.channel.blockSignals(False)
        main = self.focus.current == MAIN_CHANNEL
        self.actRename.setEnabled(not main)
        self.actRemove.setEnabled(not main)
        self.UpdateFocus()

    def AskName(self, title, text=""):
        name, ok = QInputDialog.getText(
            self,
            title,
            QApplication.translate(
                "app", "Name (layouts show it with ?channel=<name> in their URL):"
            ),
            text=text,
        )
        return NormalizeChannelName(name) if ok else None

    def AddChannel(self):
        name = self.AskName(QApplication.translate("app", "New focus channel"))
        if name and self.focus.AddChannel(name) is None:
            self.NameTaken(name)

    def RenameChannel(self):
        old = self.focus.current
        name = self.AskName(QApplication.translate("app", "Rename focus channel"), old)
        if name and name != old and self.focus.RenameChannel(old, name) is None:
            self.NameTaken(name)

    def NameTaken(self, name):
        QMessageBox.warning(
            self,
            QApplication.translate("app", "Focus channel"),
            QApplication.translate("app", 'There\'s already a channel named "{0}".').format(name),
        )

    def RemoveChannel(self):
        name = self.focus.current
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Remove focus channel"),
            QApplication.translate(
                "app", 'Remove the channel "{0}"? Layouts showing it will show the whole bracket.'
            ).format(name),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.focus.RemoveChannel(name)

    def FocusSelected(self):
        self.Ch().FocusSets(
            [id for id in self.view.matchItems if id in self.view.selected],
            sorted(self.view.selectedRounds),
        )

    def PlayerPicked(self, index):
        player = self.player.itemData(index)
        if player:
            self.Ch().FocusPlayer(player)
        elif self.Ch().request.get("mode") == MODE_PLAYER:
            self.Ch().ShowAll()

    def UpdateSelection(self):
        count = len(self.view.selected) + len(self.view.selectedRounds)
        self.btSelected.setText(
            QApplication.translate("app", "Focus selected ({0})").format(count)
            if count
            else QApplication.translate("app", "Focus selected")
        )
        self.btSelected.setEnabled(count > 0)
        self.btClearSelection.setEnabled(count > 0)

    def UpdatePlayers(self):
        """The player list, from the sets sent to the layouts."""
        players = self.focus.State()["players"]
        request = self.Ch().request
        current = request.get("player") if request.get("mode") == MODE_PLAYER else None
        self.player.blockSignals(True)
        self.player.clear()
        self.player.addItem(QApplication.translate("app", "Player's run..."), None)
        for p in players:
            label = f"{p['seed']}. {p['name']}" if p.get("seed") else p["name"]
            self.player.addItem(label, p["id"])
        self.player.setCurrentIndex(max(0, self.player.findData(current)) if current else 0)
        self.player.blockSignals(False)

    def UpdateFocus(self):
        request = self.Ch().request
        focus = self.Ch().focus or {}
        mode = request.get("mode")

        for button, on in ((self.btFollow, mode == MODE_FOLLOW), (self.btTour, mode == MODE_TOUR)):
            button.blockSignals(True)
            button.setChecked(on)
            button.blockSignals(False)
        for spin, key in ((self.scoreboard, "scoreboard"), (self.interval, "interval")):
            if request.get(key):
                spin.blockSignals(True)
                spin.setValue(request.get(key))
                spin.blockSignals(False)
        self.UpdatePlayers()

        if not focus.get("sets"):
            text = QApplication.translate("app", "Showing the whole bracket")
            if mode == MODE_FOLLOW:
                text = QApplication.translate(
                    "app", "Scoreboard {0}'s set isn't in this bracket: showing the whole bracket"
                ).format(request.get("scoreboard", 1))
        elif mode == MODE_TOUR:
            text = QApplication.translate("app", "Tour {0}/{1}: {2}").format(
                focus.get("step", 0) + 1, focus.get("steps", 1), focus.get("label") or ""
            )
        else:
            text = QApplication.translate("app", "Showing: {0}").format(
                focus.get("label")
                or QApplication.translate("app", "{0} sets").format(len(focus["sets"]))
            )
        self.status.setText(text)

        self.view.SetFocused(focus.get("sets"), focus.get("rounds"))
