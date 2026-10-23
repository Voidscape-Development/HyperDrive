# The bracket widget's controls for the bracket focus layout
# (layout/bracket_focus): zoom it to the sets and rounds selected in the
# bracket view, the winners or losers side, a player's run, the set on a
# scoreboard, or a tour of the rounds. They act on the channel of the widget's current tab; the channels
# are added, renamed and removed from the tabs.
#
# The focus modes are one choice, so they're one segmented control; only the
# setting of the mode in use (the side, the scoreboard to follow, the tour's
# interval, ...) is shown next to it. What the layout shows is on the right.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketFocus import BracketFocus
from .BracketView import BracketView
from .FlowLayout import FlowLayout
from .Helpers.BracketFocusHelper import *
from .SettingsManager import SettingsManager
from .Theme import Theme


class ElidedLabel(QLabel):
    """A label that shortens its text with "…" instead of widening the
    window. The whole text is its tooltip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""

    def SetText(self, text):
        self._text = text
        self.setToolTip(text)
        self._Elide()
        self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()
        margins = self.contentsMargins()
        width = self.fontMetrics().horizontalAdvance(self._text) + margins.left() + margins.right()
        return QSize(width + 2, hint.height())

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._Elide()

    def _Elide(self):
        margins = self.contentsMargins()
        width = max(0, self.width() - margins.left() - margins.right())
        super().setText(
            self.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, width)
        )


class BracketFocusBar(QWidget):
    # The segments, in order, and the modes each one stands for
    SEGMENTS = (
        ("all", (MODE_ALL,)),
        ("selected", (MODE_SETS,)),
        ("round", (MODE_ROUNDS,)),
        ("side", (MODE_SIDE,)),
        ("player", (MODE_PLAYER,)),
        ("follow", (MODE_FOLLOW,)),
        ("tour", (MODE_TOUR,)),
    )

    def __init__(self, view: BracketView, leading=(), parent=None):
        """leading: groups of widgets shown before the focus controls (the
        channel's top N)."""
        super().__init__(parent)
        self.view = view
        self.focus = BracketFocus.instance

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.setLayout(row)

        # Wraps its controls, so they don't set the window's width
        controls = QWidget()
        layout = FlowLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        controls.setLayout(layout)
        row.addWidget(controls, 1)

        for group in leading:
            layout.addGroup(*group)

        self.title = QLabel(QApplication.translate("app", "Focus"))
        self.title.setToolTip(
            QApplication.translate(
                "app",
                "What the bracket focus layout (layout/bracket_focus) zooms to. Ctrl+click sets and round names to select them.",
            )
        )

        # The modes
        self.segments = QWidget()
        self.segments.setObjectName("focusSegments")
        segmentsLayout = QHBoxLayout()
        segmentsLayout.setContentsMargins(2, 2, 2, 2)
        segmentsLayout.setSpacing(2)
        self.segments.setLayout(segmentsLayout)
        self.modeGroup = QButtonGroup(self)
        self.modeGroup.setExclusive(True)
        self.modeButtons = {}
        labels = {
            "all": (
                QApplication.translate("app", "Whole"),
                QApplication.translate("app", "Show the whole bracket"),
            ),
            "selected": (
                QApplication.translate("app", "Selected"),
                QApplication.translate(
                    "app",
                    "Zoom to the sets and rounds selected with Ctrl+click, and highlight them",
                ),
            ),
            "round": (
                QApplication.translate("app", "Round"),
                QApplication.translate("app", "Zoom to a round; the arrows step through them"),
            ),
            "side": (
                QApplication.translate("app", "Side"),
                QApplication.translate(
                    "app",
                    "Zoom to the winners side (with the grand final) or the losers side, and dim the other",
                ),
            ),
            "player": (
                QApplication.translate("app", "Player"),
                QApplication.translate("app", "Zoom to every set of a player, and highlight them"),
            ),
            "follow": (
                QApplication.translate("app", "Follow"),
                QApplication.translate(
                    "app",
                    "Keep zooming to the set on a scoreboard: the one with its start.gg set, or between its two players",
                ),
            ),
            "tour": (
                QApplication.translate("app", "Tour"),
                QApplication.translate(
                    "app", "Show the whole bracket, then each round in turn, over and over"
                ),
            ),
        }
        for key, _modes in self.SEGMENTS:
            text, tip = labels[key]
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setProperty("segment", True)
            button.clicked.connect(lambda _checked=False, key=key: self.SegmentClicked(key))
            self.modeGroup.addButton(button)
            segmentsLayout.addWidget(button)
            self.modeButtons[key] = button
        layout.addGroup(self.title, self.segments)

        # The setting of the mode in use
        self.btPrevious = QToolButton()
        self.btPrevious.setText("◀")
        self.btPrevious.setToolTip(QApplication.translate("app", "Previous round"))
        self.btPrevious.clicked.connect(lambda: self.Ch().MoveRound(-1))
        self.btNext = QToolButton()
        self.btNext.setText("▶")
        self.btNext.setToolTip(QApplication.translate("app", "Next round"))
        self.btNext.clicked.connect(lambda: self.Ch().MoveRound(1))

        # Side mode: which side, a segmented control of its own. Not a button
        # group: an exclusive one can't have none on, as when the mode changes
        self.sides = QWidget()
        self.sides.setObjectName("focusSegments")
        sidesLayout = QHBoxLayout(self.sides)
        sidesLayout.setContentsMargins(2, 2, 2, 2)
        sidesLayout.setSpacing(2)
        self.sideButtons = {}
        for side, text, tip in (
            (
                SIDE_WINNERS,
                QApplication.translate("app", "Winners"),
                QApplication.translate("app", "The winners side and the grand final"),
            ),
            (
                SIDE_LOSERS,
                QApplication.translate("app", "Losers"),
                QApplication.translate("app", "The losers side"),
            ),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setProperty("segment", True)
            button.clicked.connect(lambda _checked=False, side=side: self.SideClicked(side))
            sidesLayout.addWidget(button)
            self.sideButtons[side] = button

        self.player = QComboBox()
        self.player.setMinimumWidth(140)
        self.player.setToolTip(
            QApplication.translate("app", "Zoom to every set of a player, and highlight them")
        )
        self.player.activated.connect(self.PlayerPicked)

        self.scoreboardLabel = QLabel(QApplication.translate("app", "Scoreboard"))
        self.scoreboard = QSpinBox()
        self.scoreboard.setMinimum(1)
        self.scoreboard.setMaximum(99)
        self.scoreboard.setToolTip(QApplication.translate("app", "Scoreboard to follow"))
        self.scoreboard.valueChanged.connect(
            lambda value: (
                self.Ch().Follow(value) if self.Ch().request.get("mode") == MODE_FOLLOW else None
            )
        )

        self.intervalLabel = QLabel(QApplication.translate("app", "Each step"))
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
        self.settingsGroup = layout.addGroup(
            self.btPrevious,
            self.btNext,
            self.sides,
            self.player,
            self.scoreboardLabel,
            self.scoreboard,
            self.intervalLabel,
            self.interval,
        )

        self.btClearSelection = QToolButton()
        self.btClearSelection.setText(QApplication.translate("app", "Unselect"))
        self.btClearSelection.setToolTip(
            QApplication.translate("app", "Unselect the sets and rounds selected with Ctrl+click")
        )
        self.btClearSelection.clicked.connect(self.view.ClearSelection)
        layout.addWidget(self.btClearSelection)

        # What the layout shows, a pill on the right
        self.statusPill = QFrame()
        self.statusPill.setObjectName("focusStatus")
        self.statusPill.setMaximumWidth(320)
        pillLayout = QHBoxLayout(self.statusPill)
        pillLayout.setContentsMargins(10, 6, 10, 6)
        self.status = ElidedLabel()
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        font = self.status.font()
        font.setBold(True)
        self.status.setFont(font)
        pillLayout.addWidget(self.status)
        row.addWidget(self.statusPill, 0, Qt.AlignmentFlag.AlignTop)

        self.view.signals.selectionChanged.connect(self.UpdateSelection)
        self.view.signals.unselected.connect(self.Unselected)
        self.view.signals.focusSets.connect(lambda ids: self.Ch().FocusSets(ids))
        self.view.signals.focusRounds.connect(lambda keys: self.Ch().FocusRounds(keys))
        self.view.signals.focusPlayer.connect(lambda player: self.Ch().FocusPlayer(player))
        self.focus.signals.changed.connect(
            lambda name: self.UpdateFocus() if name == self.focus.current else None
        )
        self.focus.signals.channelsChanged.connect(self.UpdateFocus)

        self.ApplyStyle()
        self.UpdateSelection()
        self.UpdateFocus()

    def ApplyStyle(self):
        colors = Theme.Colors()
        c = {k: v.name() for k, v in colors.items()}
        radius = Theme.Radius()
        self.title.setStyleSheet(f"color: {c['muted']}; font-weight: bold;")
        segmentsStyle = f"""
            QWidget#focusSegments {{
                background: {c["window"]}; border: 1px solid {c["border"]};
                border-radius: {radius + 1}px;
            }}
            QToolButton[segment="true"] {{
                background: transparent; color: {c["muted"]}; border: 1px solid transparent;
                border-radius: {max(radius - 1, 2)}px; padding: 3px 8px;
            }}
            QToolButton[segment="true"]:hover {{ color: {c["text"]}; background: {c["raised"]}; }}
            QToolButton[segment="true"]:checked {{
                color: {c["accentText"]}; background: {c["accentSoft"]};
                border-color: {c["accent"]}; font-weight: bold;
            }}
            QToolButton[segment="true"]:disabled {{ color: {c["disabled"]}; }}
            """
        self.segments.setStyleSheet(segmentsStyle)
        self.sides.setStyleSheet(segmentsStyle)
        self.statusPill.setStyleSheet(
            f"QFrame#focusStatus {{ background: {c['accentSoft']}; border-radius: 14px; }}"
        )
        self.status.setStyleSheet(f"color: {c['accentText']}; background: transparent;")

    def changeEvent(self, event):
        # The theme changed
        if event.type() == QEvent.Type.PaletteChange:
            self.ApplyStyle()
        super().changeEvent(event)

    # =====================================================
    # CHANNELS
    # =====================================================
    def Ch(self):
        """The channel the controls act on."""
        return self.focus.Current()

    # Channels (from the widget's tabs)
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

    def NameTaken(self, name):
        QMessageBox.warning(
            self,
            QApplication.translate("app", "Channel"),
            QApplication.translate("app", 'There\'s already a channel named "{0}".').format(name),
        )

    def AddChannel(self):
        name = self.AskName(QApplication.translate("app", "New channel"))
        if name and self.focus.AddChannel(name) is None:
            self.NameTaken(name)

    def RenameChannel(self):
        old = self.focus.current
        if old == MAIN_CHANNEL:
            return
        name = self.AskName(QApplication.translate("app", "Rename channel"), old)
        if name and name != old and self.focus.RenameChannel(old, name) is None:
            self.NameTaken(name)

    def RemoveChannel(self):
        name = self.focus.current
        if name == MAIN_CHANNEL:
            return
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Remove channel"),
            QApplication.translate(
                "app", 'Remove the channel "{0}"? Layouts showing it will show nothing.'
            ).format(name),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.focus.RemoveChannel(name)

    # =====================================================
    # FOCUS
    # =====================================================
    def SegmentClicked(self, key):
        channel = self.Ch()
        mode = channel.request.get("mode")
        if key == "all":
            channel.ShowAll()
        elif key == "selected":
            self.FocusSelected()
        elif key == "round":
            if mode != MODE_ROUNDS:
                # The round already in focus, else the first one
                focus = channel.focus or {}
                offset = 0 if focus.get("sets") or focus.get("rounds") else 1
                channel.Set(NextRound(channel.Bracket(), focus, offset))
        elif key == "side":
            if mode != MODE_SIDE:
                bracket = channel.Bracket()
                side = SIDE_WINNERS if HasSide(bracket, SIDE_WINNERS) else SIDE_LOSERS
                channel.FocusSide(side)
        elif key == "player":
            if mode != MODE_PLAYER:
                # Pick whose run: the segment shows as on once one is picked
                self.UpdateFocus()
                self.settingsGroup.setVisible(True)
                self.player.setVisible(True)
                self.player.showPopup()
                return
        elif key == "follow":
            if mode != MODE_FOLLOW:
                channel.Follow(self.scoreboard.value())
        elif key == "tour":
            if mode != MODE_TOUR:
                channel.Tour(self.interval.value())
        # The channel's mode decides which segment is on
        self.UpdateFocus()

    def SideClicked(self, side):
        self.Ch().FocusSide(side)
        self.UpdateFocus()

    def FocusSelected(self):
        self.Ch().FocusSets(
            [id for id in self.view.matchItems if id in self.view.selected],
            sorted(self.view.selectedRounds),
        )

    def Unselected(self, sets, rounds):
        # Deselecting a set or round in focus takes it out of the focus too,
        # so its highlight here and on the layout goes away
        request = WithoutPicks(self.Ch().request, sets, rounds)
        if request is not None:
            self.Ch().Set(request)

    def PlayerPicked(self, index):
        player = self.player.itemData(index)
        if player:
            self.Ch().FocusPlayer(player)
        elif self.Ch().request.get("mode") == MODE_PLAYER:
            self.Ch().ShowAll()
        self.UpdateFocus()

    # =====================================================
    # UPDATING
    # =====================================================
    def UpdateSelection(self):
        count = len(self.view.selected) + len(self.view.selectedRounds)
        selected = self.modeButtons["selected"]
        selected.setText(
            QApplication.translate("app", "Selected ({0})").format(count)
            if count
            else QApplication.translate("app", "Selected")
        )
        selected.setEnabled(count > 0 or self.Ch().request.get("mode") == MODE_SETS)
        self.btClearSelection.setVisible(count > 0)

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
        mode = request.get("mode") or MODE_ALL

        for key, modes in self.SEGMENTS:
            button = self.modeButtons[key]
            button.blockSignals(True)
            button.setChecked(mode in modes)
            button.blockSignals(False)
        for spin, key in ((self.scoreboard, "scoreboard"), (self.interval, "interval")):
            if request.get(key):
                spin.blockSignals(True)
                spin.setValue(request.get(key))
                spin.blockSignals(False)
        self.UpdatePlayers()

        # The sides the bracket has: no losers side in single elimination
        bracket = self.Ch().Bracket()
        hasSide = {side: HasSide(bracket, side) for side in self.sideButtons}
        self.modeButtons["side"].setEnabled(any(hasSide.values()) or mode == MODE_SIDE)
        for side, button in self.sideButtons.items():
            button.blockSignals(True)
            button.setChecked(mode == MODE_SIDE and request.get("side") == side)
            button.setEnabled(hasSide[side] or button.isChecked())
            button.blockSignals(False)

        # Only the setting of the mode in use
        self.btPrevious.setVisible(mode in (MODE_ROUNDS, MODE_TOUR))
        self.btNext.setVisible(mode in (MODE_ROUNDS, MODE_TOUR))
        self.btPrevious.setToolTip(
            QApplication.translate("app", "Previous step")
            if mode == MODE_TOUR
            else QApplication.translate("app", "Previous round")
        )
        self.btNext.setToolTip(
            QApplication.translate("app", "Next step")
            if mode == MODE_TOUR
            else QApplication.translate("app", "Next round")
        )
        self.sides.setVisible(mode == MODE_SIDE)
        self.player.setVisible(mode == MODE_PLAYER)
        self.scoreboardLabel.setVisible(mode == MODE_FOLLOW)
        self.scoreboard.setVisible(mode == MODE_FOLLOW)
        self.intervalLabel.setVisible(mode == MODE_TOUR)
        self.interval.setVisible(mode == MODE_TOUR)
        self.settingsGroup.setVisible(mode not in (MODE_ALL, MODE_SETS))

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
        self.status.SetText(text)

        self.UpdateSelection()
        self.view.SetFocused(focus.get("sets"), focus.get("rounds"))
