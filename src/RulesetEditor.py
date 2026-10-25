# The parts of the Ruleset tab's editor (ScoreboardStageWidget): the stage
# grid, whose tiles go from not used to neutral to counterpick when clicked,
# the game 1 strike order, the bans after each game and a segmented control
# for picking one of a few options.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Theme import ReadableOn, Theme, ThemedIcon

STAGE_OFF = "off"
STAGE_NEUTRAL = "neutral"
STAGE_COUNTERPICK = "counterpick"
# What a click on a tile turns it into
NEXT_STATE = {
    STAGE_OFF: STAGE_NEUTRAL,
    STAGE_NEUTRAL: STAGE_COUNTERPICK,
    STAGE_COUNTERPICK: STAGE_OFF,
}

TILE_WIDTH = 148
TILE_HEIGHT = 130
TILE_GAP = 8

# The strike order's players: A wins rock-paper-scissors and strikes first
STRIKERS = ["A", "B"]

# A ban count by best-of, when switching to it with none
DEFAULT_BEST_OF = [3, 5]


def StateLabel(state):
    return {
        STAGE_OFF: QApplication.translate("app", "Not used"),
        STAGE_NEUTRAL: QApplication.translate("app", "Neutral"),
        STAGE_COUNTERPICK: QApplication.translate("app", "Counterpick"),
    }[state]


def CounterpickColor(colors):
    """The counterpick stages' color, a blue that stands apart from the
    accent (neutral stages) by its lightness too."""
    dark = colors["window"].lightnessF() < 0.5
    return QColor("#6ea8ff") if dark else QColor("#2f6fd6")


def ErrorColor(colors):
    return ReadableOn(colors["window"], QColor("#ff6b61"))


def Discard(widget):
    """Takes widget out of its layout now: deleteLater() only deletes it once
    back in the event loop, and it would show until then."""
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def Repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# =====================================================
# SEGMENTED CONTROL
# =====================================================
class SegmentedControl(QFrame):
    """One of a few options, as a row of buttons. Styled by its parent's
    style sheet (QFrame#segmented, QPushButton#segment)."""

    changed = Signal(str)

    def __init__(self, options):
        super().__init__()
        self.setObjectName("segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, key=key: self.changed.emit(key))
            self.group.addButton(button)
            layout.addWidget(button, 1)
            self.buttons[key] = button
        self.SetValue(options[0][0])

    def SetValue(self, key):
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def Value(self):
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return None


# =====================================================
# STEPPER
# =====================================================
class Stepper(QWidget):
    """A number with − and + buttons."""

    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=99, name=""):
        super().__init__()
        self.minimum = minimum
        self.maximum = maximum
        self.value = minimum
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.btLess = QToolButton()
        self.btLess.setText("−")
        self.btLess.setObjectName("stepButton")
        self.btLess.setAutoRepeat(True)
        self.btLess.clicked.connect(lambda: self.Step(-1))
        layout.addWidget(self.btLess)

        self.label = QLabel()
        self.label.setObjectName("stepValue")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumWidth(QFontMetrics(self.label.font()).horizontalAdvance("000") + 4)
        layout.addWidget(self.label)

        self.btMore = QToolButton()
        self.btMore.setText("+")
        self.btMore.setObjectName("stepButton")
        self.btMore.setAutoRepeat(True)
        self.btMore.clicked.connect(lambda: self.Step(1))
        layout.addWidget(self.btMore)

        if name:
            self.setAccessibleName(name)
            self.btLess.setToolTip(QApplication.translate("app", "Fewer: {0}").format(name))
            self.btMore.setToolTip(QApplication.translate("app", "More: {0}").format(name))
            self.btLess.setAccessibleName(self.btLess.toolTip())
            self.btMore.setAccessibleName(self.btMore.toolTip())
        self.SetValue(minimum)

    def SetValue(self, value):
        self.value = max(self.minimum, min(self.maximum, int(value)))
        self.label.setText(str(self.value))
        self.btLess.setEnabled(self.value > self.minimum)
        self.btMore.setEnabled(self.value < self.maximum)

    def Step(self, delta):
        before = self.value
        self.SetValue(self.value + delta)
        if self.value != before:
            self.valueChanged.emit(self.value)


# =====================================================
# STRIKE ORDER
# =====================================================
class StrikePips(QWidget):
    """The neutral stages in strike order: who strikes each one, and the one
    left to play."""

    SIZE = 26
    GAP = 6

    def __init__(self):
        super().__init__()
        self.pips = []
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def SetPips(self, pips):
        """pips: "A" or "B" (who strikes it), "over" (a strike too many),
        "left" (not struck: a strike is missing) or "play"."""
        self.pips = pips
        self.updateGeometry()
        self.update()

    def PerRow(self, width):
        return max(1, (width + self.GAP) // (self.SIZE + self.GAP))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        rows = max(1, -(-len(self.pips) // self.PerRow(width)))
        return rows * (self.SIZE + self.GAP) - self.GAP

    def sizeHint(self):
        return QSize(len(self.pips) * (self.SIZE + self.GAP), self.heightForWidth(300))

    def minimumSizeHint(self):
        return QSize(self.SIZE, self.SIZE)

    def paintEvent(self, event):
        colors = Theme.Colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        perRow = self.PerRow(self.width())
        for i, pip in enumerate(self.pips):
            x = (i % perRow) * (self.SIZE + self.GAP)
            y = (i // perRow) * (self.SIZE + self.GAP)
            rect = QRectF(x + 0.5, y + 0.5, self.SIZE - 1, self.SIZE - 1)
            text = pip if pip in STRIKERS else ""
            pen = Qt.PenStyle.NoPen
            if pip == "A":
                fill, textColor = colors["text"], colors["window"]
            elif pip == "B":
                fill, textColor = colors["raised"], colors["text"]
                pen = QPen(colors["muted"], 1)
            elif pip == "play":
                fill, textColor = QColor("#3fbf6f"), QColor("#111111")
            elif pip == "over":
                fill, textColor = Qt.GlobalColor.transparent, ErrorColor(colors)
                pen = QPen(textColor, 1)
                text = "!"
            else:
                fill, textColor = Qt.GlobalColor.transparent, colors["muted"]
                pen = QPen(colors["border"], 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(textColor)
            if pip == "play":
                triangle = QPolygonF(
                    [
                        QPointF(rect.center().x() - 4, rect.center().y() - 6),
                        QPointF(rect.center().x() - 4, rect.center().y() + 6),
                        QPointF(rect.center().x() + 6, rect.center().y()),
                    ]
                )
                painter.setBrush(textColor)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(triangle)
            elif text:
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class StrikeOrderEditor(QWidget):
    """Game 1's strike order: how many stages each player strikes in turn,
    starting with the winner of rock-paper-scissors."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        self.order = [1, 2, 1]
        self.neutralCount = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.pips = StrikePips()
        layout.addWidget(self.pips)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.rowsLayout = QVBoxLayout()
        self.rowsLayout.setSpacing(6)
        layout.addLayout(self.rowsLayout)
        self.rows = []

        self.btAddStep = QPushButton(QApplication.translate("app", "+ Add a step"))
        self.btAddStep.setObjectName("dashedButton")
        self.btAddStep.setAutoDefault(False)
        self.btAddStep.clicked.connect(self.AddStep)
        layout.addWidget(self.btAddStep)

        note = QLabel(
            QApplication.translate(
                "app",
                "A wins rock-paper-scissors and strikes first; the players then take turns.",
            )
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.SetOrder(self.order)

    def SetOrder(self, order):
        self.order = [max(1, int(n)) for n in order] or [1]
        self.Rebuild()
        self.Refresh()

    def Order(self):
        return list(self.order)

    def SetNeutralCount(self, count):
        self.neutralCount = count
        self.Refresh()

    def Rebuild(self):
        for row in self.rows:
            Discard(row)
        self.rows = []
        for i, count in enumerate(self.order):
            striker = STRIKERS[i % 2]
            row = QFrame()
            row.setObjectName("strikeRow")
            rowLayout = QHBoxLayout(row)
            rowLayout.setContentsMargins(8, 4, 4, 4)
            rowLayout.setSpacing(8)
            chip = QLabel(striker)
            chip.setObjectName(f"striker{striker}")
            chip.setFixedSize(22, 22)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rowLayout.addWidget(chip)
            label = QLabel(QApplication.translate("app", "Player {0} strikes").format(striker))
            rowLayout.addWidget(label, 1)
            stepper = Stepper(1, 20, label.text())
            stepper.SetValue(count)
            stepper.valueChanged.connect(lambda value, i=i: self.SetCount(i, value))
            rowLayout.addWidget(stepper)
            remove = QToolButton()
            remove.setObjectName("flatButton")
            remove.setIcon(ThemedIcon("assets/icons/cancel.svg"))
            remove.setIconSize(QSize(12, 12))
            remove.setToolTip(QApplication.translate("app", "Remove this step"))
            remove.setAccessibleName(remove.toolTip())
            remove.setEnabled(len(self.order) > 1)
            remove.clicked.connect(lambda checked=False, i=i: self.RemoveStep(i))
            rowLayout.addWidget(remove)
            self.rowsLayout.addWidget(row)
            self.rows.append(row)

    def SetCount(self, index, value):
        self.order[index] = value
        self.Refresh()
        self.changed.emit()

    def AddStep(self):
        self.order.append(1)
        self.Rebuild()
        self.Refresh()
        self.changed.emit()

    def RemoveStep(self, index):
        if len(self.order) > 1:
            self.order.pop(index)
            # Not deleted while its own button's click is handled
            QTimer.singleShot(0, self.Rebuild)
            self.Refresh()
            self.changed.emit()

    def Issue(self):
        """What's wrong with the strike order for the neutral stages, or
        None. No neutral stages is not wrong: there's nothing to strike."""
        needed = self.neutralCount - 1
        struck = sum(self.order)
        if self.neutralCount == 0 or struck == needed:
            return None
        if struck < needed:
            return QApplication.translate(
                "app", "Strike {0} more: {1} neutral stages need {2} strikes."
            ).format(needed - struck, self.neutralCount, needed)
        return QApplication.translate(
            "app", "Strike {0} fewer: {1} neutral stages need {2} strikes."
        ).format(struck - needed, self.neutralCount, needed)

    def Refresh(self):
        needed = max(self.neutralCount - 1, 0)
        pips = []
        for i, count in enumerate(self.order):
            for _ in range(count):
                pips.append(STRIKERS[i % 2] if len(pips) < needed else "over")
        left = self.neutralCount - sum(self.order)
        pips += ["left"] * max(left - 1, 0)
        if left >= 1:
            pips.append("play")
        self.pips.SetPips(pips)
        self.pips.setVisible(bool(pips))

        colors = Theme.Colors()
        issue = self.Issue()
        if self.neutralCount == 0:
            text = QApplication.translate("app", "Add neutral stages to strike from.")
            color = colors["muted"]
        elif issue:
            text, color = issue, ErrorColor(colors)
        else:
            text = QApplication.translate(
                "app", "{0} strikes from {1} neutral stages leave 1 stage to play."
            ).format(sum(self.order), self.neutralCount)
            color = ReadableOn(colors["surface"], QColor("#3fbf6f"))
        self.message.setText(text)
        self.message.setStyleSheet(f"color: {color.name()};")


# =====================================================
# BANS
# =====================================================
class BanEditor(QWidget):
    """How many stages the winner of a game bans for the next one: the same
    every set, or by the set's best-of."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mode = SegmentedControl(
            [
                ("fixed", QApplication.translate("app", "Same every set")),
                ("bestOf", QApplication.translate("app", "Depends on best-of")),
            ]
        )
        self.mode.changed.connect(self.ModePicked)
        layout.addWidget(self.mode)

        self.fixedRow = QWidget()
        fixed = QHBoxLayout(self.fixedRow)
        fixed.setContentsMargins(0, 0, 0, 0)
        fixed.addWidget(QLabel(QApplication.translate("app", "Winner bans")), 1)
        self.banCount = Stepper(0, 20, QApplication.translate("app", "Banned stages"))
        self.banCount.valueChanged.connect(lambda _: self.changed.emit())
        fixed.addWidget(self.banCount)
        fixed.addWidget(self.Unit())
        layout.addWidget(self.fixedRow)

        self.bestOfBox = QWidget()
        bestOf = QVBoxLayout(self.bestOfBox)
        bestOf.setContentsMargins(0, 0, 0, 0)
        bestOf.setSpacing(6)
        self.bestOfLayout = QVBoxLayout()
        self.bestOfLayout.setSpacing(6)
        bestOf.addLayout(self.bestOfLayout)
        self.btAddBestOf = QPushButton(QApplication.translate("app", "+ Add a best-of"))
        self.btAddBestOf.setObjectName("dashedButton")
        self.btAddBestOf.setAutoDefault(False)
        self.btAddBestOf.clicked.connect(self.AddBestOf)
        bestOf.addWidget(self.btAddBestOf)
        layout.addWidget(self.bestOfBox)

        self.bestOfRows = []
        self.SetValues(0, {})

    def Unit(self):
        label = QLabel(QApplication.translate("app", "stages"))
        label.setObjectName("muted")
        return label

    def SetValues(self, banCount, banByMaxGames):
        # A fixed count when it has one or there's no count by best-of
        rows = []
        for games, bans in (banByMaxGames or {}).items():
            try:
                rows.append((int(games), int(bans)))
            except (TypeError, ValueError):
                pass
        bestOf = not banCount and bool(rows)
        self.banCount.SetValue(banCount or 0)
        self.SetRows(sorted(rows))
        self.mode.SetValue("bestOf" if bestOf else "fixed")
        self.ShowMode()

    def Values(self):
        """(banCount, banByMaxGames), as in a Ruleset."""
        if self.mode.Value() == "fixed":
            return self.banCount.value, {}
        return 0, {str(games.value()): bans.value for _, games, bans in self.bestOfRows}

    def ModePicked(self, mode):
        if mode == "bestOf" and not self.bestOfRows:
            self.SetRows([(games, self.banCount.value) for games in DEFAULT_BEST_OF])
        self.ShowMode()
        self.changed.emit()

    def ShowMode(self):
        fixed = self.mode.Value() == "fixed"
        self.fixedRow.setVisible(fixed)
        self.bestOfBox.setVisible(not fixed)

    def SetRows(self, rows):
        for row, _, _ in self.bestOfRows:
            Discard(row)
        self.bestOfRows = []
        for games, bans in rows:
            self.AddRow(games, bans)

    def AddRow(self, games, bans):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel(QApplication.translate("app", "Best of")))
        gamesBox = QSpinBox()
        gamesBox.setRange(1, 99)
        gamesBox.setValue(games)
        gamesBox.setAccessibleName(QApplication.translate("app", "Best of"))
        gamesBox.valueChanged.connect(lambda _: self.changed.emit())
        layout.addWidget(gamesBox)
        layout.addStretch(1)
        bansBox = Stepper(0, 20, QApplication.translate("app", "Banned stages"))
        bansBox.SetValue(bans)
        bansBox.valueChanged.connect(lambda _: self.changed.emit())
        layout.addWidget(bansBox)
        layout.addWidget(self.Unit())
        remove = QToolButton()
        remove.setObjectName("flatButton")
        remove.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        remove.setIconSize(QSize(12, 12))
        remove.setToolTip(QApplication.translate("app", "Remove this best-of"))
        remove.setAccessibleName(remove.toolTip())
        remove.clicked.connect(lambda checked=False, row=row: self.RemoveRow(row))
        layout.addWidget(remove)
        self.bestOfLayout.addWidget(row)
        self.bestOfRows.append((row, gamesBox, bansBox))

    def AddBestOf(self):
        games = max((g.value() for _, g, _ in self.bestOfRows), default=1) + 2
        bans = self.bestOfRows[-1][2].value if self.bestOfRows else self.banCount.value
        self.AddRow(min(games, 99), bans)
        self.changed.emit()

    def RemoveRow(self, row):
        self.bestOfRows = [r for r in self.bestOfRows if r[0] is not row]
        Discard(row)
        self.changed.emit()


# =====================================================
# STAGE GRID
# =====================================================
class StageFilter(QSortFilterProxyModel):
    """The stages whose name has the search text, and only those in the
    ruleset when asked to."""

    def __init__(self, grid):
        super().__init__()
        self.grid = grid
        self.text = ""
        self.inRulesetOnly = False

    def SetText(self, text):
        self.text = text.strip().casefold()
        self.invalidateFilter()

    def SetInRulesetOnly(self, only):
        self.inRulesetOnly = only
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        index = self.sourceModel().index(row, 0, parent)
        if self.text and self.text not in str(index.data() or "").casefold():
            return False
        if self.inRulesetOnly:
            return self.grid.StateOf(StageGrid.Codename(index)) != STAGE_OFF
        return True


class StageTileDelegate(QStyledItemDelegate):
    def __init__(self, grid):
        super().__init__(grid)
        self.grid = grid

    def sizeHint(self, option, index):
        return QSize(TILE_WIDTH, TILE_HEIGHT)

    def paint(self, painter, option, index):
        colors = self.grid.colors
        state = self.grid.StateOf(StageGrid.Codename(index))
        on = state != STAGE_OFF
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focus = bool(option.state & QStyle.StateFlag.State_HasFocus) and self.grid.hasFocus()
        radius = Theme.Radius() + 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        tile = QRectF(option.rect).adjusted(1, 1, -1, -1)
        if state == STAGE_NEUTRAL:
            ring, width = colors["accent"], 2
        elif state == STAGE_COUNTERPICK:
            ring, width = CounterpickColor(colors), 2
        else:
            ring, width = (colors["muted"] if hover else colors["border"]), 1
        if focus:
            ring, width = colors["text"], 2
        painter.setPen(QPen(ring, width))
        painter.setBrush(colors["raisedHover"] if hover and not on else colors["surface"])
        painter.drawRoundedRect(tile, radius, radius)

        # The stage's image, covering a 16:9 frame
        thumb = QRectF(
            tile.left() + 6, tile.top() + 6, tile.width() - 12, (tile.width() - 12) * 9 / 16
        )
        path = QPainterPath()
        path.addRoundedRect(thumb, radius - 2, radius - 2)
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(thumb, colors["raised"])
        pixmap = self.grid.Thumbnail(index, thumb.size().toSize())
        if pixmap is not None:
            if not on:
                painter.setOpacity(0.35)
            size = pixmap.deviceIndependentSize()
            painter.drawPixmap(
                QPointF(
                    thumb.center().x() - size.width() / 2, thumb.center().y() - size.height() / 2
                ),
                pixmap,
            )
        painter.restore()

        # Its name
        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        nameRect = QRectF(thumb.left() + 2, thumb.bottom() + 6, thumb.width() - 4, metrics.height())
        painter.setPen(colors["text"] if on else colors["muted"])
        painter.drawText(
            nameRect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(
                str(index.data() or ""), Qt.TextElideMode.ElideRight, int(nameRect.width())
            ),
        )

        # What it is in the ruleset
        badgeFont = QFont(option.font)
        badgeFont.setBold(True)
        badgeFont.setPointSizeF(max(badgeFont.pointSizeF() * 0.78, 6))
        painter.setFont(badgeFont)
        badgeMetrics = QFontMetrics(badgeFont)
        label = StateLabel(state).upper()
        badge = QRectF(
            nameRect.left(),
            nameRect.bottom() + 5,
            badgeMetrics.horizontalAdvance(label) + 12,
            badgeMetrics.height() + 4,
        )
        if on:
            fill = colors["accent"] if state == STAGE_NEUTRAL else CounterpickColor(colors)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#111111") if fill.lightnessF() > 0.45 else QColor("#ffffff"))
        else:
            painter.setPen(QPen(colors["border"], 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(colors["muted"])
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()


class StageGrid(QListView):
    """The game's stages as tiles. A click on a tile goes from not used to
    neutral to counterpick and back; right-click picks one."""

    stagesChanged = Signal()

    def __init__(self):
        super().__init__()
        # The stages in the ruleset, by codename, in order
        self.neutral = []
        self.counterpick = []
        self.states = {}
        self.colors = Theme.Colors()
        self.thumbnails = {}
        self.sourceModel = QStandardItemModel()

        self.proxy = StageFilter(self)
        self.proxy.setSourceModel(self.sourceModel)
        self.setModel(self.proxy)
        self.setItemDelegate(StageTileDelegate(self))

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(TILE_WIDTH + TILE_GAP, TILE_HEIGHT + TILE_GAP))
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(TILE_HEIGHT * 2 + TILE_GAP * 2)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.ContextMenu)
        self.clicked.connect(lambda index: self.Cycle(self.Codename(index)))

    @staticmethod
    def Codename(index):
        data = index.data(Qt.ItemDataRole.UserRole)
        return data.get("codename") if isinstance(data, dict) else None

    def SetSourceModel(self, model):
        self.sourceModel = model
        self.thumbnails = {}
        self.proxy.setSourceModel(model)

    def SetColors(self, colors):
        self.colors = colors
        self.viewport().update()

    def SetStages(self, neutral, counterpick):
        self.neutral = [c for c in neutral if c]
        self.counterpick = [c for c in counterpick if c and c not in self.neutral]
        self.UpdateStates()

    def UpdateStates(self):
        self.states = {c: STAGE_NEUTRAL for c in self.neutral}
        self.states.update({c: STAGE_COUNTERPICK for c in self.counterpick})
        if self.proxy.inRulesetOnly:
            self.proxy.invalidateFilter()
        self.viewport().update()

    def StateOf(self, codename):
        return self.states.get(codename, STAGE_OFF)

    def DisplayName(self, codename):
        for row in range(self.sourceModel.rowCount()):
            index = self.sourceModel.index(row, 0)
            if self.Codename(index) == codename:
                return str(index.data() or "")
        return ""

    def SetState(self, codename, state):
        if not codename or self.StateOf(codename) == state:
            return
        self.neutral = [c for c in self.neutral if c != codename]
        self.counterpick = [c for c in self.counterpick if c != codename]
        # Added stages are kept in alphabetical order, like the lists were
        if state == STAGE_NEUTRAL:
            self.neutral = sorted(self.neutral + [codename], key=self.DisplayName)
        elif state == STAGE_COUNTERPICK:
            self.counterpick = sorted(self.counterpick + [codename], key=self.DisplayName)
        self.UpdateStates()
        self.stagesChanged.emit()

    def Cycle(self, codename):
        self.SetState(codename, NEXT_STATE[self.StateOf(codename)])

    def ContextMenu(self, position):
        index = self.indexAt(position)
        codename = self.Codename(index) if index.isValid() else None
        if not codename:
            return
        menu = QMenu(self)
        for state in (STAGE_NEUTRAL, STAGE_COUNTERPICK, STAGE_OFF):
            action = menu.addAction(StateLabel(state))
            action.setCheckable(True)
            action.setChecked(self.StateOf(codename) == state)
            action.triggered.connect(
                lambda checked=False, state=state: self.SetState(codename, state)
            )
        menu.exec(self.viewport().mapToGlobal(position))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid():
                self.Cycle(self.Codename(index))
                return
        super().keyPressEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self.indexAt(event.pos())
            if index.isValid():
                QToolTip.showText(
                    event.globalPos(),
                    f"{index.data()}: {StateLabel(self.StateOf(self.Codename(index)))}\n"
                    + QApplication.translate(
                        "app", "Click to change it, right-click to pick what it is"
                    ),
                    self.viewport(),
                )
                return True
        return super().viewportEvent(event)

    def Thumbnail(self, index, size):
        """The stage's image covering size, from its file when it has one
        (sharper than its icon), else its icon."""
        ratio = self.devicePixelRatioF()
        data = index.data(Qt.ItemDataRole.UserRole)
        path = data.get("path") if isinstance(data, dict) else None
        key = (path or self.Codename(index), size.width(), size.height(), ratio)
        if key in self.thumbnails:
            return self.thumbnails[key]
        source = QPixmap(path) if path else QPixmap()
        if source.isNull():
            icon = index.data(Qt.ItemDataRole.DecorationRole)
            if not isinstance(icon, QIcon) or icon.isNull():
                # Its icon may still be loading: try again next time
                return None
            source = icon.pixmap(128, 128)
        pixmap = source.scaled(
            size * ratio,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        pixmap.setDevicePixelRatio(ratio)
        self.thumbnails[key] = pixmap
        return pixmap
