# The "Track a stream or station" window: the event's streams as cards
# showing what's on them now and next, its stations as tiles showing whether
# they're in use, and a panel with the selected one's sets. Tracking one
# loads each of its sets onto the scoreboard as it comes up.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .SelectSetWindow import (
    STATUS_CALLED,
    STATUS_IN_PROGRESS,
    STATUS_UPCOMING,
    DrawPill,
    ScaledFont,
    SetStatus,
    ThemeColors,
)
from .SettingsManager import SettingsManager
from .Theme import Blend, Theme
from .TournamentDataManager import TournamentDataManager
from .Workers import Worker

TYPE_STREAM = "stream"
TYPE_STATION = "station"

SHOW_ALL = "all"
SHOW_STREAMS = "streams"
SHOW_STATIONS = "stations"

# A station's use: a set in progress on it, a set called to it, or none.
# None while the sets haven't been checked yet.
USE_IN_USE = "in_use"
USE_CALLED = "called"
USE_FREE = "free"

ROLE_CARD = Qt.ItemDataRole.UserRole
CARD_PADDING = 14
CARD_SPACING = 10
SELECTED_BORDER = 2
# Sets shown in the selected stream's or station's queue
QUEUE_PREVIEW = 5


# =====================================================
# STREAMS, STATIONS AND THEIR SETS
# =====================================================
def EntryKey(entry):
    # parry.gg lists a stream once per slot, with the same id
    return (entry.get("type"), str(entry.get("id")), str(entry.get("identifier")))


def StationNumber(entry):
    return str(entry.get("identifier"))


def QueueSets(queue):
    """A stream's queue ({"1": set, "2": ...}) as a list in its order."""
    if not queue:
        return []
    return [queue[key] for key in sorted(queue, key=lambda k: int(k) if str(k).isdigit() else 0)]


def QueueFor(entry, queues):
    """The queue of a stream. parry.gg names its slots "<stream> (Slot 1/2)",
    their queue "<stream>"."""
    name = str(entry.get("identifier") or "").lower()
    byName = {str(key).lower(): queue for key, queue in (queues or {}).items()}
    if name in byName:
        return byName[name]
    for key, queue in byName.items():
        if key and name.startswith(key + " ("):
            return queue
    return None


def SetTitle(s):
    """ "A vs B" for a set from the set list or from a queue."""
    tbd = QApplication.translate("app", "TBD")
    if "team" in s:
        names = []
        for key in ("1", "2"):
            team = (s.get("team") or {}).get(key) or {}
            name = team.get("teamName")
            if not name:
                players = [
                    p.get("mergedName") or p.get("name") or ""
                    for p in (team.get("player") or {}).values()
                ]
                name = " / ".join(p for p in players if p)
            names.append(name or tbd)
    else:
        names = [s.get("p1_name") or tbd, s.get("p2_name") or tbd]
    return f"{names[0]} {QApplication.translate('app', 'vs')} {names[1]}"


def SetRound(s):
    if "team" in s:
        return " · ".join(p for p in [s.get("match"), s.get("phase")] if p)
    return " · ".join(p for p in [s.get("round_name"), s.get("tournament_phase")] if p)


def SetLine(s):
    return " · ".join(p for p in [SetTitle(s), SetRound(s)] if p)


def StreamNowNext(queue):
    """(the set on the stream now, the next one), None for none. The set on
    it now is the queue's first, once it's in progress."""
    sets = QueueSets(queue)
    now = sets[0] if sets and SetStatus(sets[0]) == STATUS_IN_PROGRESS else None
    rest = sets[1:] if now else sets
    return now, (rest[0] if rest else None)


def StationSets(number, sets):
    """A station's sets from the set list: in progress first, then called,
    then the others."""
    order = {STATUS_IN_PROGRESS: 0, STATUS_CALLED: 1}
    onStation = [s for s in sets or [] if str(s.get("station")) == str(number)]
    return sorted(onStation, key=lambda s: order.get(SetStatus(s), 2))


def StationUse(number, sets):
    """(the station's use, its set in progress or called). sets is the set
    list, None while it hasn't loaded."""
    if sets is None:
        return None, None
    stationSets = StationSets(number, sets)
    if stationSets:
        status = SetStatus(stationSets[0])
        if status == STATUS_IN_PROGRESS:
            return USE_IN_USE, stationSets[0]
        if status == STATUS_CALLED:
            return USE_CALLED, stationSets[0]
    return USE_FREE, None


def StationsOnStream(stream, entries):
    return [
        StationNumber(e)
        for e in entries
        if e.get("type") == TYPE_STATION
        and e.get("stream")
        and str(e.get("stream")).lower() == str(stream).lower()
    ]


def SortedStations(entries):
    def key(entry):
        number = StationNumber(entry)
        return (not number.isdigit(), int(number) if number.isdigit() else 0, number)

    return sorted((e for e in entries if e.get("type") == TYPE_STATION), key=key)


def UseNames():
    return {
        USE_IN_USE: QApplication.translate("app", "In use"),
        USE_CALLED: QApplication.translate("app", "Called"),
        USE_FREE: QApplication.translate("app", "Free"),
    }


def Matches(words, texts):
    haystack = " ".join(t for t in texts if t).lower()
    return all(word in haystack for word in words)


# =====================================================
# CARDS
# =====================================================
class CardGrid(QListView):
    """Cards in rows of equal columns. It's as tall as its rows, so the
    window scrolls rather than each grid."""

    def __init__(self, cardHeight, minCardWidth, maxColumns, parent=None):
        super().__init__(parent)
        self.cardHeight = cardHeight
        self.minCardWidth = minCardWidth
        self.maxColumns = maxColumns
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def Fit(self):
        # A row that fills the width exactly wraps, so a few px are left over
        width = max(1, self.viewport().width() - 4)
        columns = max(1, min(self.maxColumns, width // self.minCardWidth))
        self.setGridSize(QSize(width // columns, self.cardHeight + CARD_SPACING))
        rows = -(-self.model().rowCount() // columns) if self.model() else 0
        height = rows * (self.cardHeight + CARD_SPACING)
        if self.height() != height:
            self.setFixedHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.Fit()


class CardDelegate(QStyledItemDelegate):
    def __init__(self, grid):
        super().__init__(grid)
        self.grid = grid
        self.colors = ThemeColors()

    def sizeHint(self, option, index):
        return QSize(self.grid.gridSize().width(), self.grid.cardHeight)

    def CardRect(self, option):
        # The card in its grid cell, the gap on its right and below it
        rect = QRectF(option.rect)
        rect.setWidth(self.grid.gridSize().width())
        rect.setHeight(self.grid.cardHeight)
        return rect.adjusted(0, 0, -CARD_SPACING, 0)

    def PaintCard(self, painter, option, rect):
        """The card's box. Returns whether it's selected and its secondary
        text color."""
        colors = self.colors
        radius = Theme.Radius() + 2
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            inset = SELECTED_BORDER / 2
            painter.setPen(QPen(colors["accent"], SELECTED_BORDER))
            painter.setBrush(colors["selected"])
            painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), radius, radius)
        else:
            hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
            painter.setPen(QPen(colors["muted"] if hover else colors["border"], 1))
            painter.setBrush(colors["hover"] if hover else colors["surface"])
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        # Secondary text a bit lighter on the selection's tint
        muted = Blend(colors["muted"], colors["text"], 0.5) if selected else colors["muted"]
        return selected, muted

    def DrawText(self, painter, rect, text, font, color):
        painter.setFont(font)
        painter.setPen(color)
        text = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class StreamCardDelegate(CardDelegate):
    def paint(self, painter, option, index):
        card = index.data(ROLE_CARD)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.CardRect(option)
        selected, muted = self.PaintCard(painter, option, rect)
        colors = self.colors
        inner = rect.adjusted(CARD_PADDING, CARD_PADDING - 2, -CARD_PADDING, -CARD_PADDING)
        lh = option.fontMetrics.height()

        # A screen, the stream's name and where it's from, and its queue's length
        glyph = QRectF(inner.left(), inner.top() + 5, 20, 14)
        glyphColor = colors["accent"] if selected else muted
        painter.setPen(QPen(glyphColor, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(glyph, 3, 3)
        center = glyph.center()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glyphColor)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center.x() - 3, center.y() - 4),
                    QPointF(center.x() + 4, center.y()),
                    QPointF(center.x() - 3, center.y() + 4),
                ]
            )
        )

        textLeft = glyph.right() + 10
        badgeWidth = 0
        if card["badge"]:
            badgeFont = ScaledFont(option.font, 0.88)
            badgeWidth = DrawPill(
                painter,
                QRect(
                    int(inner.right())
                    - QFontMetrics(badgeFont).horizontalAdvance(card["badge"])
                    - 16,
                    int(inner.top()),
                    0,
                    lh + 6,
                ),
                card["badge"],
                badgeFont,
                colors["raised"],
                colors["text"],
            )
        titleFont = ScaledFont(option.font, 1.1, bold=True)
        titleHeight = QFontMetrics(titleFont).height()
        titleRect = QRectF(
            textLeft, inner.top(), inner.right() - textLeft - badgeWidth - 8, titleHeight
        )
        self.DrawText(painter, titleRect, card["title"], titleFont, colors["text"])
        self.DrawText(
            painter,
            QRectF(textLeft, titleRect.bottom() + 1, inner.right() - textLeft, lh),
            card["subtitle"],
            ScaledFont(option.font, 0.9),
            muted,
        )

        # Now and next
        lineTop = titleRect.bottom() + lh + 14
        painter.setPen(QPen(colors["border"], 1))
        painter.drawLine(QPointF(inner.left(), lineTop - 7), QPointF(inner.right(), lineTop - 7))
        labelFont = ScaledFont(option.font, bold=True)
        labelWidth = max(
            QFontMetrics(labelFont).horizontalAdvance(label) for label, _, _ in card["lines"]
        )
        for i, (label, text, live) in enumerate(card["lines"]):
            top = lineTop + i * (lh + 4)
            self.DrawText(
                painter,
                QRectF(inner.left(), top, labelWidth, lh),
                label,
                labelFont,
                colors["accentText"] if live else muted,
            )
            self.DrawText(
                painter,
                QRectF(inner.left() + labelWidth + 10, top, inner.width() - labelWidth - 10, lh),
                text,
                option.font,
                colors["text"] if live else muted,
            )
        painter.restore()


class StationTileDelegate(CardDelegate):
    def paint(self, painter, option, index):
        card = index.data(ROLE_CARD)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.CardRect(option)
        selected, muted = self.PaintCard(painter, option, rect)
        colors = self.colors
        inner = rect.adjusted(12, 10, -12, -10)
        lh = option.fontMetrics.height()

        numberFont = ScaledFont(option.font, 1.6, bold=True)
        numberHeight = QFontMetrics(numberFont).height()
        self.DrawText(
            painter,
            QRectF(inner.left(), inner.top(), inner.width() / 2, numberHeight),
            card["number"],
            numberFont,
            colors["text"],
        )

        # Its use, as a dot and a word
        use = card["use"]
        useFont = ScaledFont(option.font, 0.85, bold=use in (USE_IN_USE, USE_CALLED))
        useText = UseNames().get(use, "")
        if useText:
            useColor = {USE_IN_USE: colors["accentText"], USE_CALLED: colors["called"]}.get(
                use, muted
            )
            useWidth = QFontMetrics(useFont).horizontalAdvance(useText) + 2
            useRect = QRectF(inner.right() - useWidth, inner.top(), useWidth, numberHeight)
            self.DrawText(painter, useRect, useText, useFont, useColor)
            dot = QRectF(useRect.left() - 12, useRect.center().y() - 3.5, 7, 7)
            if use in (USE_IN_USE, USE_CALLED):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(colors["accent"] if use == USE_IN_USE else colors["called"])
            else:
                painter.setPen(QPen(muted, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(dot)

        top = inner.top() + numberHeight + 4
        self.DrawText(
            painter,
            QRectF(inner.left(), top, inner.width(), lh),
            card["set"],
            option.font,
            colors["text"] if card["hasSet"] else muted,
        )
        self.DrawText(
            painter,
            QRectF(inner.left(), top + lh + 2, inner.width(), lh),
            card["where"],
            ScaledFont(option.font, 0.88),
            muted,
        )
        painter.restore()


# =====================================================
# THE SELECTED STREAM OR STATION
# =====================================================
class TrackDetails(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trackDetails")
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.kindLabel = QLabel()
        self.kindLabel.setFont(ScaledFont(self.font(), 0.85, bold=True))
        layout.addWidget(self.kindLabel)
        self.nameLabel = QLabel()
        self.nameLabel.setFont(ScaledFont(self.font(), 1.25, bold=True))
        self.nameLabel.setWordWrap(True)
        layout.addWidget(self.nameLabel)

        self.queueLayout = QVBoxLayout()
        self.queueLayout.setSpacing(6)
        layout.addLayout(self.queueLayout)
        self.emptyLabel = QLabel()
        self.emptyLabel.setWordWrap(True)
        layout.addWidget(self.emptyLabel)
        layout.addStretch()

        # With the auto update setting on: the set on it now, or the next one
        self.startGroup = QWidget()
        startLayout = QVBoxLayout(self.startGroup)
        startLayout.setContentsMargins(0, 0, 0, 0)
        startLayout.setSpacing(6)
        self.startTitle = QLabel(QApplication.translate("app", "When tracking starts"))
        self.startTitle.setFont(ScaledFont(self.font(), 0.92, bold=True))
        startLayout.addWidget(self.startTitle)
        self.loadNow = QRadioButton(QApplication.translate("app", "Load the current set now"))
        self.loadNow.setChecked(True)
        startLayout.addWidget(self.loadNow)
        self.waitForNext = QRadioButton(QApplication.translate("app", "Wait for the next set"))
        startLayout.addWidget(self.waitForNext)
        layout.addWidget(self.startGroup)
        self.noAutoUpdate = QLabel(
            QApplication.translate(
                "app",
                "Automatic set updating is off in the settings, so only the set on it now "
                "will load.",
            )
        )
        self.noAutoUpdate.setWordWrap(True)
        layout.addWidget(self.noAutoUpdate)

        self.startButton = QPushButton()
        # The theme draws the default button in the accent color
        self.startButton.setDefault(True)
        self.startButton.setMinimumHeight(40)
        layout.addWidget(self.startButton)
        self.hint = QLabel(
            QApplication.translate("app", "You can stop at any time from the scoreboard.")
        )
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)

        self.queueRows = []
        self.ApplyStyle()
        self.SetAutoUpdate(True)
        self.SetEntry(None, [], "")

    def ApplyStyle(self):
        self.colors = ThemeColors()
        radius = Theme.Radius()
        self.setStyleSheet(f"""
            QFrame#trackDetails {{
                background: {self.colors["surface"].name()};
                border: 1px solid {self.colors["border"].name()};
                border-radius: {radius + 2}px;
            }}
            QFrame#queueRow {{
                background: {self.colors["raised"].name()}; border-radius: {radius}px;
            }}
            QFrame#queueRow[live="true"] {{ background: {self.colors["selected"].name()}; }}
        """)
        muted = f"color: {self.colors['muted'].name()};"
        for label in [
            self.kindLabel,
            self.emptyLabel,
            self.startTitle,
            self.noAutoUpdate,
            self.hint,
        ]:
            label.setStyleSheet(muted)

    def SetAutoUpdate(self, enabled):
        self.startGroup.setHidden(not enabled)
        self.noAutoUpdate.setHidden(enabled)

    def WaitForNext(self):
        return not self.startGroup.isHidden() and self.waitForNext.isChecked()

    def SetEntry(self, entry, queue, emptyText):
        """queue: [(badge, set, live)], live for the set being played"""
        for row in self.queueRows:
            # Gone now: deleteLater waits for the event loop
            self.queueLayout.removeWidget(row)
            row.hide()
            row.setParent(None)
            row.deleteLater()
        self.queueRows = []

        hasEntry = entry is not None
        for widget in [self.kindLabel, self.nameLabel, self.startButton]:
            widget.setVisible(hasEntry)
        self.startButton.setEnabled(hasEntry)
        if not hasEntry:
            self.emptyLabel.setText(
                QApplication.translate("app", "Pick a stream or station to see its sets here.")
            )
            self.emptyLabel.show()
            return

        isStream = entry.get("type") == TYPE_STREAM
        kind = (
            QApplication.translate("app", "Stream queue")
            if isStream
            else QApplication.translate("app", "Station")
        )
        self.kindLabel.setText(kind.upper())
        name = (
            str(entry.get("identifier"))
            if isStream
            else QApplication.translate("app", "Station {0}").format(StationNumber(entry))
        )
        self.nameLabel.setText(name)
        self.startButton.setText(QApplication.translate("app", "Start tracking {0}").format(name))

        badgeFont = ScaledFont(self.font(), 0.8, bold=True)
        badgeWidth = max(
            QFontMetrics(badgeFont).horizontalAdvance(badge)
            for badge, _, _ in queue or [("", 0, 0)]
        )
        for badge, s, live in queue[:QUEUE_PREVIEW]:
            row = QFrame()
            row.setObjectName("queueRow")
            row.setProperty("live", live)
            rowLayout = QHBoxLayout(row)
            rowLayout.setContentsMargins(10, 7, 10, 7)
            rowLayout.setSpacing(10)
            badgeLabel = QLabel(badge)
            badgeLabel.setFont(badgeFont)
            badgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badgeLabel.setFixedWidth(badgeWidth + 12)
            if live:
                badgeLabel.setStyleSheet(
                    f"background: {self.colors['accent'].name()};"
                    f"color: {self.colors['onAccent'].name()};"
                    "border-radius: 4px; padding: 1px 0px;"
                )
            else:
                badgeLabel.setStyleSheet(
                    f"color: {self.colors['muted'].name()};"
                    f"border: 1px solid {self.colors['border'].name()};"
                    "border-radius: 4px; padding: 0px;"
                )
            rowLayout.addWidget(badgeLabel, 0, Qt.AlignmentFlag.AlignVCenter)
            texts = QVBoxLayout()
            texts.setSpacing(0)
            title = QLabel(SetTitle(s))
            title.setFont(ScaledFont(self.font(), bold=live))
            title.setWordWrap(True)
            texts.addWidget(title)
            detail = QLabel(SetRound(s))
            detail.setStyleSheet(f"color: {self.colors['muted'].name()};")
            detail.setWordWrap(True)
            detail.setVisible(bool(detail.text()))
            texts.addWidget(detail)
            rowLayout.addLayout(texts, 1)
            self.queueLayout.addWidget(row)
            self.queueRows.append(row)

        self.emptyLabel.setText(emptyText)
        self.emptyLabel.setVisible(not queue)


# =====================================================
# WINDOW
# =====================================================
class SelectStationWindow(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle(QApplication.translate("app", "Track a stream or station"))
        self.setWindowModality(Qt.WindowModal)

        # The streams and stations, as the provider's GetStations gives them
        self.entries = []
        # {stream name: queue}, None until loaded
        self.queues = None
        # The set list, for the stations' use, None until loaded
        self.sets = None
        self.loadingStations = False
        self.loadingQueues = False
        self.loadingSets = False
        # Results of an earlier load are dropped
        self.loadToken = 0
        self.showing = SHOW_ALL
        self.selectedKey = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title, what tracking does, refreshing
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel(QApplication.translate("app", "Track a stream or station"))
        title.setFont(ScaledFont(self.font(), 1.4, bold=True))
        titles.addWidget(title)
        self.descriptionLabel = QLabel(
            QApplication.translate(
                "app",
                "HyperDrive follows its sets and loads each one onto this scoreboard as it "
                "comes up.",
            )
        )
        self.descriptionLabel.setWordWrap(True)
        titles.addWidget(self.descriptionLabel)
        header.addLayout(titles, 1)
        self.refreshButton = QPushButton(QApplication.translate("app", "Refresh"))
        self.refreshButton.setAutoDefault(False)
        self.refreshButton.clicked.connect(self.LoadStations)
        header.addWidget(self.refreshButton, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # Search and which ones to show
        searchRow = QHBoxLayout()
        self.searchBar = QLineEdit()
        self.searchBar.setPlaceholderText(
            QApplication.translate("app", "Search streams, stations or players on them")
        )
        self.searchBar.setClearButtonEnabled(True)
        self.searchBar.textChanged.connect(lambda text: self.Rebuild())
        searchRow.addWidget(self.searchBar, 1)
        self.showButtons = QButtonGroup(self)
        self.showButtons.setExclusive(True)
        self.showButtonsByKey = {}
        showRow = QHBoxLayout()
        showRow.setSpacing(2)
        for key in [SHOW_ALL, SHOW_STREAMS, SHOW_STATIONS]:
            button = QPushButton()
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(key == self.showing)
            button.setProperty("show", key)
            self.showButtons.addButton(button)
            self.showButtonsByKey[key] = button
            showRow.addWidget(button)
        self.showButtons.buttonClicked.connect(
            lambda button: self.SetShowing(button.property("show"))
        )
        searchRow.addLayout(showRow)
        layout.addLayout(searchRow)

        # Streams and stations, and the selected one
        body = QHBoxLayout()
        body.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("trackContent")
        contentLayout = QVBoxLayout(content)
        contentLayout.setContentsMargins(0, 0, 4, 0)
        contentLayout.setSpacing(8)

        lineHeight = self.fontMetrics().height()
        self.streamsTitle = QLabel()
        self.streamsTitle.setFont(ScaledFont(self.font(), 0.85, bold=True))
        contentLayout.addWidget(self.streamsTitle)
        self.streamModel = QStandardItemModel(self)
        self.streamGrid = CardGrid(round(lineHeight * 5.4) + 2 * CARD_PADDING, 300, 2)
        self.streamGrid.setModel(self.streamModel)
        self.streamDelegate = StreamCardDelegate(self.streamGrid)
        self.streamGrid.setItemDelegate(self.streamDelegate)
        contentLayout.addWidget(self.streamGrid)

        self.stationsTitle = QLabel()
        self.stationsTitle.setFont(ScaledFont(self.font(), 0.85, bold=True))
        contentLayout.addWidget(self.stationsTitle)
        self.stationModel = QStandardItemModel(self)
        self.stationGrid = CardGrid(round(lineHeight * 4.6) + 20, 160, 6)
        self.stationGrid.setModel(self.stationModel)
        self.stationDelegate = StationTileDelegate(self.stationGrid)
        self.stationGrid.setItemDelegate(self.stationDelegate)
        contentLayout.addWidget(self.stationGrid)

        self.emptyLabel = QLabel()
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyLabel.setWordWrap(True)
        self.emptyLabel.setMinimumHeight(120)
        contentLayout.addWidget(self.emptyLabel)
        contentLayout.addStretch()
        self.scroll.setWidget(content)
        body.addWidget(self.scroll, 1)

        for grid in [self.streamGrid, self.stationGrid]:
            grid.installEventFilter(self)
            grid.doubleClicked.connect(lambda index: self.StartTracking())
            grid.selectionModel().selectionChanged.connect(
                lambda selected, deselected, grid=grid: self.Selected(
                    grid, selected.indexes()[0] if selected.indexes() else QModelIndex()
                )
            )
        self.searchBar.installEventFilter(self)

        self.details = TrackDetails()
        self.details.startButton.clicked.connect(self.StartTracking)
        body.addWidget(self.details)
        layout.addLayout(body, 1)

        # Loading progress, keyboard hints and cancel
        footer = QHBoxLayout()
        progressColumn = QVBoxLayout()
        progressColumn.setSpacing(4)
        self.statusLabel = QLabel()
        progressColumn.addWidget(self.statusLabel)
        self.progressBar = QProgressBar()
        self.progressBar.setTextVisible(False)
        self.progressBar.setFixedSize(220, 4)
        # Busy: the providers don't say how far along they are
        self.progressBar.setRange(0, 0)
        progressColumn.addWidget(self.progressBar)
        footer.addLayout(progressColumn)
        footer.addStretch()
        self.hintLabel = QLabel(
            QApplication.translate(
                "app", "Arrow keys to move · Enter or double-click to start · Esc to close"
            )
        )
        footer.addWidget(self.hintLabel)
        footer.addStretch()
        cancelButton = QPushButton(QApplication.translate("app", "Cancel"))
        cancelButton.setAutoDefault(False)
        cancelButton.clicked.connect(self.reject)
        footer.addWidget(cancelButton)
        layout.addLayout(footer)

        QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self, self.FocusSearch)

        self.ApplyStyle()
        self.UpdateStatus()
        self.resize(1200, 720)

        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        TournamentDataManager.instance.signals.get_stations_finished.connect(self.SetStations)

    def ApplyStyle(self):
        colors = ThemeColors()
        muted = f"color: {colors['muted'].name()};"
        for label in [
            self.descriptionLabel,
            self.streamsTitle,
            self.stationsTitle,
            self.emptyLabel,
            self.statusLabel,
            self.hintLabel,
        ]:
            label.setStyleSheet(muted)
        for grid, delegate in [
            (self.streamGrid, self.streamDelegate),
            (self.stationGrid, self.stationDelegate),
        ]:
            grid.setStyleSheet(
                "QListView { background: transparent; border: none; outline: none; }"
            )
            delegate.colors = colors
        self.scroll.setStyleSheet("QScrollArea, QWidget#trackContent { background: transparent; }")
        self.details.ApplyStyle()

    def showEvent(self, event):
        # The theme and the setting may have changed since it was last open
        self.ApplyStyle()
        self.details.SetAutoUpdate(not SettingsManager.Get("general.disable_autoupdate", False))
        self.details.loadNow.setChecked(True)
        super().showEvent(event)
        self.FocusSearch()

    def FocusSearch(self):
        self.searchBar.setFocus()
        self.searchBar.selectAll()

    # =====================================================
    # LOADING
    # =====================================================
    def LoadStations(self):
        self.loadToken += 1
        self.entries = []
        self.queues = None
        self.sets = None
        provider = TournamentDataManager.instance.GetProvider()
        self.loadingStations = self.loadingQueues = provider is not None
        self.loadingSets = False
        self.Rebuild()
        self.UpdateStatus()
        if provider is None:
            return

        TournamentDataManager.instance.LoadStations()

        token = self.loadToken
        worker = Worker(provider.GetStreamQueue)
        worker.signals.result.connect(lambda queues: self.SetQueues(queues, token))
        worker.signals.error.connect(lambda error: self.SetQueues({}, token))
        TournamentDataManager.instance.threadPool.start(worker)

    def SetStations(self, stations):
        # Every scoreboard's window hears it; only the one that asked takes it
        if not self.loadingStations:
            return
        self.entries = list(stations or [])
        self.loadingStations = False
        # Whether stations are in use comes from the set list, only fetched
        # when there are stations
        provider = TournamentDataManager.instance.GetProvider()
        if provider is not None and any(e.get("type") == TYPE_STATION for e in self.entries):
            token = self.loadToken
            self.loadingSets = True
            worker = Worker(provider.GetMatches, getFinished=False)
            worker.signals.result.connect(lambda sets: self.SetSets(sets, token))
            worker.signals.error.connect(lambda error: self.SetSets([], token))
            TournamentDataManager.instance.threadPool.start(worker)
        self.Rebuild()
        self.UpdateStatus()

    def SetQueues(self, queues, token):
        if token != self.loadToken:
            return
        self.queues = queues or {}
        self.loadingQueues = False
        self.Rebuild()
        self.UpdateStatus()

    def SetSets(self, sets, token):
        if token != self.loadToken:
            return
        self.sets = sets or []
        self.loadingSets = False
        self.Rebuild()
        self.UpdateStatus()

    def UpdateStatus(self):
        loading = self.loadingStations or self.loadingQueues or self.loadingSets
        self.progressBar.setVisible(loading)
        self.refreshButton.setEnabled(not loading)
        if self.loadingStations:
            text = QApplication.translate("app", "Loading streams and stations...")
        elif self.loadingQueues:
            text = QApplication.translate("app", "Loading the stream queues...")
        elif self.loadingSets:
            text = QApplication.translate("app", "Checking which stations are in use...")
        else:
            text = ""
        self.statusLabel.setText(text)

    # =====================================================
    # THE CARDS
    # =====================================================
    def StreamCard(self, entry):
        queue = QueueFor(entry, self.queues)
        subtitle = []
        if entry.get("stream"):
            subtitle.append(str(entry.get("stream")).split("://")[-1].rstrip("/"))
        stations = StationsOnStream(entry.get("identifier"), self.entries)
        if stations:
            subtitle.append(
                QApplication.translate("app", "uses Station {0}").format(", ".join(stations))
            )
        now = QApplication.translate("app", "Now")
        upNext = QApplication.translate("app", "Next")
        if self.queues is None:
            lines = [
                (now, QApplication.translate("app", "Loading the queue..."), False),
                (upNext, "", False),
            ]
        else:
            current, following = StreamNowNext(queue)
            lines = [
                (
                    now,
                    SetLine(current)
                    if current
                    else QApplication.translate("app", "Nothing on stream"),
                    current is not None,
                ),
                (
                    upNext,
                    SetLine(following)
                    if following
                    else QApplication.translate("app", "Nothing queued"),
                    False,
                ),
            ]
        return {
            "entry": entry,
            "title": str(entry.get("identifier") or ""),
            "subtitle": " · ".join(subtitle),
            "badge": QApplication.translate("app", "{0} queued").format(len(QueueSets(queue)))
            if self.queues is not None
            else "",
            "lines": lines,
            "search": [str(entry.get("identifier")), str(entry.get("stream") or "")]
            + [SetTitle(s) for s in QueueSets(queue)],
        }

    def StationCard(self, entry):
        number = StationNumber(entry)
        use, current = StationUse(number, self.sets)
        stream = entry.get("stream")
        if current:
            setText = SetTitle(current)
        elif use is None:
            setText = QApplication.translate("app", "Checking...")
        else:
            setText = QApplication.translate("app", "No set")
        return {
            "entry": entry,
            "number": number,
            "use": use,
            "set": setText,
            "hasSet": current is not None,
            "where": QApplication.translate("app", "On {0}").format(stream)
            if stream
            else QApplication.translate("app", "Off stream"),
            "search": [number, str(stream or "")]
            + [SetTitle(s) for s in StationSets(number, self.sets)],
        }

    def Rebuild(self):
        words = self.searchBar.text().lower().split()
        streams = [e for e in self.entries if e.get("type") == TYPE_STREAM]
        stations = SortedStations(self.entries)

        self.showButtonsByKey[SHOW_ALL].setText(QApplication.translate("app", "All"))
        self.showButtonsByKey[SHOW_STREAMS].setText(
            QApplication.translate("app", "Streams · {0}").format(len(streams))
        )
        self.showButtonsByKey[SHOW_STATIONS].setText(
            QApplication.translate("app", "Stations · {0}").format(len(stations))
        )

        shown = 0
        selected = None
        for grid, model, entries, makeCard, title, kind, name in [
            (
                self.streamGrid,
                self.streamModel,
                streams,
                self.StreamCard,
                self.streamsTitle,
                SHOW_STREAMS,
                QApplication.translate("app", "Streams"),
            ),
            (
                self.stationGrid,
                self.stationModel,
                stations,
                self.StationCard,
                self.stationsTitle,
                SHOW_STATIONS,
                QApplication.translate("app", "Stations"),
            ),
        ]:
            grid.selectionModel().blockSignals(True)
            model.clear()
            if self.showing in (SHOW_ALL, kind):
                for entry in entries:
                    card = makeCard(entry)
                    if words and not Matches(words, card["search"]):
                        continue
                    item = QStandardItem()
                    item.setData(card, ROLE_CARD)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    model.appendRow(item)
                    if EntryKey(entry) == self.selectedKey:
                        selected = (grid, model.index(model.rowCount() - 1, 0))
            grid.selectionModel().blockSignals(False)
            title.setText(name.upper())
            title.setVisible(model.rowCount() > 0)
            grid.setVisible(model.rowCount() > 0)
            grid.Fit()
            shown += model.rowCount()

        # Keep the selection while it's listed, or select the first card
        if selected is None:
            for grid, model in [
                (self.streamGrid, self.streamModel),
                (self.stationGrid, self.stationModel),
            ]:
                if model.rowCount() > 0:
                    selected = (grid, model.index(0, 0))
                    break
        if selected is not None:
            self.Select(*selected)
        else:
            self.selectedKey = None
            self.details.SetEntry(None, [], "")

        self.emptyLabel.setVisible(shown == 0)
        if self.loadingStations:
            self.emptyLabel.setText(
                QApplication.translate("app", "Loading streams and stations...")
            )
        elif not self.entries:
            self.emptyLabel.setText(
                QApplication.translate("app", "This event has no streams or stations.")
            )
        else:
            self.emptyLabel.setText(
                QApplication.translate("app", "No streams or stations match the search.")
            )

    def SetShowing(self, showing):
        self.showing = showing
        self.Rebuild()

    # =====================================================
    # SELECTING
    # =====================================================
    def Select(self, grid, index):
        grid.selectionModel().blockSignals(True)
        grid.setCurrentIndex(index)
        grid.selectionModel().blockSignals(False)
        self.Selected(grid, index)

    def Selected(self, grid, index):
        if not index.isValid():
            return
        # One card is selected across both grids
        other = self.stationGrid if grid is self.streamGrid else self.streamGrid
        other.selectionModel().blockSignals(True)
        other.selectionModel().clear()
        other.selectionModel().blockSignals(False)
        grid.selectionModel().select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        entry = index.data(ROLE_CARD)["entry"]
        self.selectedKey = EntryKey(entry)
        self.ShowSelected(entry)

    def SelectedEntry(self):
        for grid in [self.streamGrid, self.stationGrid]:
            index = grid.currentIndex()
            if index.isValid() and grid.selectionModel().isSelected(index):
                return index.data(ROLE_CARD)["entry"]
        return None

    def ShowSelected(self, entry):
        queue = []
        if entry.get("type") == TYPE_STREAM:
            if self.queues is None:
                empty = QApplication.translate("app", "Loading the queue...")
            else:
                current, following = StreamNowNext(QueueFor(entry, self.queues))
                for i, s in enumerate(QueueSets(QueueFor(entry, self.queues))):
                    if s is current:
                        badge = QApplication.translate("app", "Now")
                    elif s is following:
                        badge = QApplication.translate("app", "Next")
                    else:
                        badge = str(i + 1)
                    queue.append((badge.upper(), s, s is current))
                empty = QApplication.translate("app", "Nothing is queued on this stream.")
        elif self.sets is None:
            empty = QApplication.translate("app", "Checking the station's sets...")
        else:
            badges = {
                STATUS_IN_PROGRESS: QApplication.translate("app", "Now"),
                STATUS_CALLED: QApplication.translate("app", "Called"),
                STATUS_UPCOMING: QApplication.translate("app", "Next"),
            }
            for s in StationSets(StationNumber(entry), self.sets):
                status = SetStatus(s)
                queue.append((badges.get(status, "").upper(), s, status == STATUS_IN_PROGRESS))
            empty = QApplication.translate("app", "No sets are on this station.")
        self.details.SetEntry(entry, queue, empty)

    def MoveFromSearch(self):
        for grid in [self.streamGrid, self.stationGrid]:
            if grid.isVisible() and grid.model().rowCount() > 0:
                grid.setFocus()
                return

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and obj in (
            self.searchBar,
            self.streamGrid,
            self.stationGrid,
        ):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.StartTracking()
                return True
            if key == Qt.Key.Key_Down and obj is self.searchBar:
                self.MoveFromSearch()
                return True
        return super().eventFilter(obj, event)

    # =====================================================
    # TRACKING
    # =====================================================
    def StartTracking(self):
        entry = self.SelectedEntry()
        if entry is None:
            return
        station = dict(entry)
        # Read before the window closes
        station["wait_for_next"] = self.details.WaitForNext()
        self.accept()
        self.parent().signals.StationSelected.emit(station)
