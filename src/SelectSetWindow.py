# The "Load a set" window: the event's sets grouped by status (in progress,
# called, upcoming, completed), with a search, filters by stream, station and
# phase, and a panel showing the selected set before it's loaded.
import traceback
from urllib.parse import urlparse

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import Blend, Theme
from .TournamentDataManager import TournamentDataManager

STATUS_IN_PROGRESS = "in_progress"
STATUS_CALLED = "called"
STATUS_UPCOMING = "upcoming"
STATUS_COMPLETED = "completed"
# The order of the groups in the list
STATUS_ORDER = [STATUS_IN_PROGRESS, STATUS_CALLED, STATUS_UPCOMING, STATUS_COMPLETED]

# The status buttons, and the sets each one shows
SHOW_NOT_FINISHED = "not_finished"
SHOW_IN_PROGRESS = "in_progress"
SHOW_COMPLETED = "completed"
SHOW_ALL = "all"
SHOWN_STATUSES = {
    SHOW_NOT_FINISHED: {STATUS_IN_PROGRESS, STATUS_CALLED, STATUS_UPCOMING},
    SHOW_IN_PROGRESS: {STATUS_IN_PROGRESS},
    SHOW_COMPLETED: {STATUS_COMPLETED},
    SHOW_ALL: set(STATUS_ORDER),
}

ROLE_SET = Qt.ItemDataRole.UserRole
# A group's header row holds its status and number of sets
ROLE_HEADER = Qt.ItemDataRole.UserRole + 1

STATUS_COLUMN_WIDTH = 112
COLUMN_GAP = 12
ROW_PADDING = 12
# Width of the selected row's border
SELECTED_BORDER = 2
# Text color of a called set's status, on dark and on light themes
CALLED_COLORS = {"dark": "#9cc2ff", "light": "#1d4ed8"}


# =====================================================
# SETS
# =====================================================
def SetStatus(s):
    # start.gg's set states: 2 in progress, 3 finished, 6 called; the others
    # (1 created, 4 ready, 7 queued) haven't started
    state = s.get("state")
    if state == 2:
        return STATUS_IN_PROGRESS
    if state == 3:
        return STATUS_COMPLETED
    if state == 6:
        return STATUS_CALLED
    return STATUS_UPCOMING


def StatusNames():
    return {
        STATUS_IN_PROGRESS: QApplication.translate("app", "In progress"),
        STATUS_CALLED: QApplication.translate("app", "Called"),
        STATUS_UPCOMING: QApplication.translate("app", "Upcoming"),
        STATUS_COMPLETED: QApplication.translate("app", "Completed"),
    }


def StreamName(url):
    # "https://twitch.tv/name" is shown as "name"
    if not url:
        return ""
    path = urlparse(url if "://" in url else "https://" + url).path.strip("/")
    return path.split("/")[-1] if path else url


def StationText(s):
    station = s.get("station")
    return "" if station in (None, "", -1) else str(station)


def SeedText(seed):
    return "" if seed in (None, "", -1) else str(seed)


def TeamMembers(s):
    # For doubles, each team's players, to show under the team names
    members = ["", ""]
    try:
        entrants = s.get("entrants") or [[]]
        if len(entrants[0]) > 1:
            for t, team in enumerate(entrants[:2]):
                members[t] = ", ".join(p.get("gamerTag") or "" for p in team)
    except Exception:
        logger.error(traceback.format_exc())
    return members


def HasEmptySlot(s):
    return not s.get("p1_name") or not s.get("p2_name")


def SearchText(s):
    return " ".join(
        [
            s.get("p1_name") or "",
            s.get("p2_name") or "",
            *TeamMembers(s),
            s.get("round_name") or "",
            s.get("tournament_phase") or "",
            StreamName(s.get("stream")),
            StationText(s),
        ]
    ).lower()


def FilterOptions(sets):
    """The streams, stations and phases the sets have, for the filters."""
    streams = sorted({StreamName(s.get("stream")) for s in sets} - {""}, key=str.lower)
    # Stations by number
    stations = sorted(
        {StationText(s) for s in sets} - {""},
        key=lambda station: (
            not station.isdigit(),
            int(station) if station.isdigit() else 0,
            station,
        ),
    )
    # Phases in the order the sets have them (the bracket's order)
    phases = list(
        dict.fromkeys(s.get("tournament_phase") for s in sets if s.get("tournament_phase"))
    )
    return streams, stations, phases


def GroupSets(
    sets,
    show=SHOW_NOT_FINISHED,
    text="",
    hideEmptySlots=False,
    stream=None,
    station=None,
    phase=None,
):
    """The sets to list, as [(status, sets)] in STATUS_ORDER, leaving out
    empty groups. Every word of text has to match. stream, station and phase
    are None for any."""
    words = text.lower().split()
    statuses = SHOWN_STATUSES[show]
    groups = {status: [] for status in STATUS_ORDER}
    for s in sets:
        status = SetStatus(s)
        if status not in statuses:
            continue
        if hideEmptySlots and HasEmptySlot(s):
            continue
        if stream is not None and StreamName(s.get("stream")) != stream:
            continue
        if station is not None and StationText(s) != station:
            continue
        if phase is not None and s.get("tournament_phase") != phase:
            continue
        if words:
            haystack = SearchText(s)
            if not all(word in haystack for word in words):
                continue
        groups[status].append(s)
    return [(status, groups[status]) for status in STATUS_ORDER if groups[status]]


def ShowsScore(s):
    return SetStatus(s) in (STATUS_IN_PROGRESS, STATUS_COMPLETED)


def ScoreText(s):
    if not ShowsScore(s):
        return ""
    return f"{s.get('team1score') or 0}–{s.get('team2score') or 0}"


# =====================================================
# LOOK
# =====================================================
def ThemeColors():
    theme = Theme.Colors()
    called = QColor(CALLED_COLORS["dark" if Theme.IsDark() else "light"])
    return {
        "text": theme["text"],
        "muted": theme["muted"],
        "surface": theme["surface"],
        "raised": theme["raised"],
        "border": theme["border"],
        "accent": theme["accent"],
        "accentText": theme["accentText"],
        "selected": theme["accentSoft"],
        "onAccent": theme["onAccent"],
        "hover": Blend(theme["surface"], theme["text"], 0.05),
        "called": called,
        "calledSoft": Blend(theme["surface"], called, 0.18),
    }


def StatusPillColors(status, colors):
    """(background, text, border) of a status pill; None for none."""
    if status == STATUS_IN_PROGRESS:
        # Solid, so it shows on the selected row too
        return colors["accent"], colors["onAccent"], None
    if status == STATUS_CALLED:
        return colors["calledSoft"], colors["called"], None
    if status == STATUS_COMPLETED:
        return colors["raised"], colors["muted"], None
    return None, colors["muted"], colors["border"]


def Columns(rect):
    """The match, round, stream/station and status columns of a row."""
    left = rect.left() + ROW_PADDING
    width = max(0, rect.width() - 2 * ROW_PADDING - STATUS_COLUMN_WIDTH - 3 * COLUMN_GAP)
    widths = [round(width * 0.44), round(width * 0.30)]
    widths.append(width - sum(widths))
    widths.append(STATUS_COLUMN_WIDTH)
    columns = []
    for w in widths:
        columns.append(QRect(left, rect.top(), w, rect.height()))
        left += w + COLUMN_GAP
    return columns


def ScaledFont(font, scale=1.0, bold=False):
    font = QFont(font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * scale)
    font.setBold(bold)
    return font


def DrawPill(painter, rect, text, font, background, foreground, border=None):
    """A rounded label at rect's left, centered on its height. Returns its width."""
    metrics = QFontMetrics(font)
    width = metrics.horizontalAdvance(text) + 16
    height = metrics.height() + 4
    pill = QRectF(rect.left(), rect.center().y() - height / 2 + 1, width, height)
    painter.setPen(QPen(border, 1) if border is not None else Qt.PenStyle.NoPen)
    painter.setBrush(background if background is not None else Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(pill.adjusted(0.5, 0.5, -0.5, -0.5), height / 2, height / 2)
    painter.setPen(foreground)
    painter.setFont(font)
    painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
    return width


class SetRowDelegate(QStyledItemDelegate):
    """Draws the group headers and the set rows. Painted rather than made of
    widgets, so events with hundreds of sets list quickly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = ThemeColors()

    def sizeHint(self, option, index):
        lineHeight = option.fontMetrics.height()
        if index.data(ROLE_HEADER) is not None:
            return QSize(0, lineHeight + 16)
        return QSize(0, 2 * lineHeight + 22)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        header = index.data(ROLE_HEADER)
        if header is not None:
            self.PaintHeader(painter, option, header)
        else:
            self.PaintSet(painter, option, index.data(ROLE_SET))
        painter.restore()

    def PaintHeader(self, painter, option, header):
        status, count = header
        painter.setFont(ScaledFont(option.font, 0.92, bold=True))
        painter.setPen(self.colors["muted"])
        painter.drawText(
            option.rect.adjusted(ROW_PADDING, 6, -ROW_PADDING, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{StatusNames()[status]} · {count}",
        )

    def PaintSet(self, painter, option, s):
        colors = dict(self.colors)
        rect = option.rect.adjusted(2, 1, -2, -1)
        radius = Theme.Radius()
        if option.state & QStyle.StateFlag.State_Selected:
            # Lighter secondary text, readable on the selection's tint
            colors["muted"] = Blend(colors["muted"], colors["text"], 0.5)
            painter.setPen(QPen(colors["accent"], SELECTED_BORDER))
            painter.setBrush(colors["selected"])
            inset = SELECTED_BORDER / 2
            painter.drawRoundedRect(
                QRectF(rect).adjusted(inset, inset, -inset, -inset), radius, radius
            )
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors["hover"])
            painter.drawRoundedRect(QRectF(rect), radius, radius)

        matchColumn, roundColumn, whereColumn, statusColumn = Columns(rect)
        lineHeight = option.fontMetrics.height()
        top = rect.top() + (rect.height() - 2 * lineHeight - 2) // 2
        firstLine = QRect(matchColumn.left(), top, matchColumn.width(), lineHeight)
        secondLine = QRect(
            matchColumn.left(), top + lineHeight + 2, matchColumn.width(), lineHeight
        )
        mutedFont = ScaledFont(option.font, 0.92)

        # Match: each side's seed and name, then the phase, teams and score
        self.PaintMatchup(
            painter,
            firstLine,
            s,
            colors,
            ScaledFont(option.font, 1.05, bold=True),
            ScaledFont(option.font, 0.82),
        )
        members = [m for m in TeamMembers(s) if m]
        details = [s.get("tournament_phase") or "", "  ·  ".join(members), ScoreText(s)]
        self.DrawText(
            painter, secondLine, " · ".join(d for d in details if d), mutedFont, colors["muted"]
        )

        self.DrawText(painter, roundColumn, s.get("round_name") or "", option.font, colors["text"])

        # Stream and station
        tags = []
        if StreamName(s.get("stream")):
            tags.append(StreamName(s.get("stream")))
        if StationText(s):
            tags.append(QApplication.translate("app", "Station {0}").format(StationText(s)))
        if not tags:
            self.DrawText(
                painter,
                whereColumn,
                QApplication.translate("app", "Not assigned"),
                mutedFont,
                colors["muted"],
            )
        painter.save()
        painter.setClipRect(whereColumn)
        tagRect = QRect(whereColumn)
        tagFont = ScaledFont(option.font, 0.88)
        for tag in tags:
            width = DrawPill(painter, tagRect, tag, tagFont, colors["raised"], colors["text"])
            tagRect.setLeft(tagRect.left() + width + 6)
        painter.restore()

        status = SetStatus(s)
        background, foreground, border = StatusPillColors(status, colors)
        DrawPill(
            painter,
            statusColumn,
            StatusNames()[status],
            ScaledFont(option.font, 0.88, bold=status != STATUS_UPCOMING),
            background,
            foreground,
            border,
        )

    def PaintMatchup(self, painter, rect, s, colors, nameFont, seedFont):
        names = [s.get("p1_name") or "", s.get("p2_name") or ""]
        seeds = [SeedText(s.get("p1_seed")), SeedText(s.get("p2_seed"))]
        vs = " " + QApplication.translate("app", "vs") + " "
        nameMetrics, seedMetrics = QFontMetrics(nameFont), QFontMetrics(seedFont)
        fixed = seedMetrics.horizontalAdvance(vs) + sum(
            seedMetrics.horizontalAdvance(seed + " ") for seed in seeds if seed
        )
        nameWidth = max(20, (rect.width() - fixed) // 2)

        x = rect.left()
        for i in range(2):
            if i == 1:
                x += self.DrawRun(painter, x, rect, vs, seedFont, colors["muted"])
            if seeds[i]:
                x += self.DrawRun(painter, x, rect, seeds[i] + " ", seedFont, colors["muted"])
            name = nameMetrics.elidedText(
                names[i] or QApplication.translate("app", "TBD"),
                Qt.TextElideMode.ElideRight,
                nameWidth,
            )
            x += self.DrawRun(
                painter, x, rect, name, nameFont, colors["text"] if names[i] else colors["muted"]
            )

    def DrawRun(self, painter, x, rect, text, font, color):
        # Text along the line's baseline, so smaller seeds sit with the names
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(
            QRect(x, rect.top(), max(0, rect.right() - x), rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            text,
        )
        return QFontMetrics(font).horizontalAdvance(text)

    def DrawText(self, painter, rect, text, font, color):
        painter.setFont(font)
        painter.setPen(color)
        text = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class ColumnHeader(QWidget):
    """The column names above the list, lined up with the rows' columns."""

    def __init__(self, listView, parent=None):
        super().__init__(parent)
        self.listView = listView
        self.setFixedHeight(self.fontMetrics().height() + 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(ScaledFont(self.font(), 0.85, bold=True))
        painter.setPen(Theme.Colors()["muted"])
        # The rows' width: the list's viewport, less the rows' margins
        viewport = self.listView.viewport()
        left = (
            viewport.mapTo(self.window(), QPoint(0, 0)).x()
            - self.mapTo(self.window(), QPoint(0, 0)).x()
        )
        rect = QRect(left + 2, 0, viewport.width() - 4, self.height())
        names = [
            QApplication.translate("app", "Match"),
            QApplication.translate("app", "Round"),
            QApplication.translate("app", "Stream · Station"),
            QApplication.translate("app", "Status"),
        ]
        for column, name in zip(Columns(rect), names):
            painter.drawText(
                column, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name.upper()
            )
        painter.end()


class SetDetails(QFrame):
    """The selected set: its sides with seeds and scores, its round and
    phase, and where it's played."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("setDetails")
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.title = QLabel(QApplication.translate("app", "Selected set").upper())
        self.title.setFont(ScaledFont(self.font(), 0.85, bold=True))
        layout.addWidget(self.title)

        self.empty = QLabel(
            QApplication.translate("app", "Pick a set from the list to see it here.")
        )
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        self.sides = []
        for _ in range(2):
            frame = QFrame()
            frame.setObjectName("setSide")
            row = QHBoxLayout(frame)
            row.setContentsMargins(10, 8, 10, 8)
            row.setSpacing(10)
            seed = QLabel()
            seed.setFixedWidth(QFontMetrics(seed.font()).horizontalAdvance("0000"))
            row.addWidget(seed)
            names = QVBoxLayout()
            names.setSpacing(0)
            name = QLabel()
            name.setFont(ScaledFont(self.font(), 1.15, bold=True))
            name.setWordWrap(True)
            names.addWidget(name)
            members = QLabel()
            members.setWordWrap(True)
            names.addWidget(members)
            row.addLayout(names, 1)
            score = QLabel()
            score.setFont(ScaledFont(self.font(), 1.3, bold=True))
            row.addWidget(score)
            layout.addWidget(frame)
            self.sides.append(
                {"frame": frame, "seed": seed, "name": name, "members": members, "score": score}
            )

        facts = QGridLayout()
        facts.setHorizontalSpacing(10)
        facts.setVerticalSpacing(6)
        facts.setColumnStretch(1, 1)
        self.factLabels = {}
        self.factValues = {}
        for row, (key, label) in enumerate(
            [
                ("round", QApplication.translate("app", "Round")),
                ("phase", QApplication.translate("app", "Phase")),
                ("stream", QApplication.translate("app", "Stream")),
                ("station", QApplication.translate("app", "Station")),
                ("status", QApplication.translate("app", "Status")),
            ]
        ):
            name = QLabel(label)
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            facts.addWidget(name, row, 0, Qt.AlignmentFlag.AlignTop)
            facts.addWidget(value, row, 1)
            self.factLabels[key] = name
            self.factValues[key] = value
        layout.addLayout(facts)
        layout.addStretch()

        # For this set only; starts as the setting says each time the window
        # opens (see SelectSetWindow.showEvent)
        self.keepUpdated = QCheckBox(QApplication.translate("app", "Keep scores updated"))
        self.keepUpdated.setFont(ScaledFont(self.font(), bold=True))
        layout.addWidget(self.keepUpdated)
        self.keepUpdatedHint = QLabel(
            QApplication.translate(
                "app", "Loads new scores and characters from the bracket while the set is played."
            )
        )
        self.keepUpdatedHint.setWordWrap(True)
        layout.addWidget(self.keepUpdatedHint)

        self.loadButton = QPushButton(QApplication.translate("app", "Load set"))
        # The theme draws the default button in the accent color
        self.loadButton.setDefault(True)
        self.loadButton.setMinimumHeight(40)
        layout.addWidget(self.loadButton)

        self.ApplyStyle()
        self.SetSet(None)

    def ApplyStyle(self):
        self.colors = ThemeColors()
        radius = Theme.Radius()
        self.setStyleSheet(f"""
            QFrame#setDetails {{
                background: {self.colors["surface"].name()};
                border: 1px solid {self.colors["border"].name()};
                border-radius: {radius + 2}px;
            }}
            QFrame#setSide {{
                background: {self.colors["raised"].name()}; border-radius: {radius}px;
            }}
        """)
        muted = f"color: {self.colors['muted'].name()};"
        for label in [self.title, self.empty, self.keepUpdatedHint, *self.factLabels.values()]:
            label.setStyleSheet(muted)
        for side in self.sides:
            side["seed"].setStyleSheet(muted)
            side["members"].setStyleSheet(muted)

    def SetSet(self, s):
        hasSet = s is not None
        self.empty.setVisible(not hasSet)
        for side in self.sides:
            side["frame"].setVisible(hasSet)
        for key in self.factLabels:
            self.factLabels[key].setVisible(hasSet)
            self.factValues[key].setVisible(hasSet)
        self.loadButton.setEnabled(hasSet)
        if not hasSet:
            return

        showScore = ShowsScore(s)
        scores = [s.get("team1score") or 0, s.get("team2score") or 0]
        members = TeamMembers(s)
        for i, side in enumerate(self.sides):
            side["seed"].setText(SeedText(s.get(f"p{i + 1}_seed")))
            side["name"].setText(s.get(f"p{i + 1}_name") or QApplication.translate("app", "TBD"))
            side["members"].setText(members[i])
            side["members"].setVisible(bool(members[i]))
            side["score"].setText(str(scores[i]) if showScore else "")
            # The side that's behind is muted
            behind = showScore and scores[i] < scores[1 - i]
            side["score"].setStyleSheet(
                f"color: {self.colors['muted' if behind else 'text'].name()};"
            )

        status = SetStatus(s)
        dash = "—"
        self.factValues["round"].setText(s.get("round_name") or dash)
        self.factValues["phase"].setText(s.get("tournament_phase") or dash)
        self.factValues["stream"].setText(s.get("stream") or dash)
        self.factValues["station"].setText(StationText(s) or dash)
        self.factValues["status"].setText(StatusNames()[status])
        statusColor = {
            STATUS_IN_PROGRESS: self.colors["accentText"],
            STATUS_CALLED: self.colors["called"],
        }.get(status, self.colors["text"])
        self.factValues["status"].setStyleSheet(f"color: {statusColor.name()};")


# =====================================================
# WINDOW
# =====================================================
class SelectSetWindow(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle(QApplication.translate("app", "Load a set"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.sets = []
        # Which status button is on
        self.showing = SHOW_NOT_FINISHED
        # Whether the sets were fetched with the completed ones
        self.fetchedFinished = False
        self.loading = False
        # Set when the list changed while the window was closed
        self.dirty = False

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title, the event and refreshing
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel(QApplication.translate("app", "Load a set"))
        title.setFont(ScaledFont(self.font(), 1.4, bold=True))
        titles.addWidget(title)
        self.eventLabel = QLabel()
        titles.addWidget(self.eventLabel)
        header.addLayout(titles, 1)
        self.updatedLabel = QLabel()
        header.addWidget(self.updatedLabel)
        self.refreshButton = QPushButton(QApplication.translate("app", "Refresh"))
        self.refreshButton.setAutoDefault(False)
        self.refreshButton.clicked.connect(self.LoadSets)
        header.addWidget(self.refreshButton)
        layout.addLayout(header)

        # Search and the status buttons
        searchRow = QHBoxLayout()
        self.searchBar = QLineEdit()
        self.searchBar.setPlaceholderText(
            QApplication.translate("app", "Search players, teams, round or phase")
        )
        self.searchBar.setClearButtonEnabled(True)
        self.searchBar.textChanged.connect(lambda text: self.Rebuild())
        searchRow.addWidget(self.searchBar, 1)

        self.showButtons = QButtonGroup(self)
        self.showButtons.setExclusive(True)
        statusButtons = QHBoxLayout()
        statusButtons.setSpacing(2)
        for key, label in [
            (SHOW_NOT_FINISHED, QApplication.translate("app", "Not finished")),
            (SHOW_IN_PROGRESS, QApplication.translate("app", "In progress")),
            (SHOW_COMPLETED, QApplication.translate("app", "Completed")),
            (SHOW_ALL, QApplication.translate("app", "All")),
        ]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(key == self.showing)
            button.setProperty("show", key)
            self.showButtons.addButton(button)
            statusButtons.addWidget(button)
        self.showButtons.buttonClicked.connect(
            lambda button: self.SetShowing(button.property("show"))
        )
        searchRow.addLayout(statusButtons)
        layout.addLayout(searchRow)

        # Filters
        filters = QHBoxLayout()
        self.streamFilter = self.AddFilter(filters, QApplication.translate("app", "Stream"))
        self.stationFilter = self.AddFilter(filters, QApplication.translate("app", "Station"))
        self.phaseFilter = self.AddFilter(filters, QApplication.translate("app", "Phase"))
        self.hideEmptySlots = QCheckBox(
            QApplication.translate("app", "Hide sets with an empty slot")
        )
        self.hideEmptySlots.toggled.connect(lambda checked: self.Rebuild())
        filters.addWidget(self.hideEmptySlots)
        filters.addStretch()
        self.countLabel = QLabel()
        filters.addWidget(self.countLabel)
        layout.addLayout(filters)

        # The sets, and the selected one
        body = QHBoxLayout()
        body.setSpacing(12)
        listColumn = QVBoxLayout()
        listColumn.setSpacing(0)
        self.model = QStandardItemModel(self)
        self.setList = QListView()
        self.setList.setModel(self.model)
        self.delegate = SetRowDelegate(self.setList)
        self.setList.setItemDelegate(self.delegate)
        self.setList.setMouseTracking(True)
        self.setList.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setList.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setList.doubleClicked.connect(
            lambda index: self.LoadSelectedSet() if index.data(ROLE_SET) else None
        )
        # Enter, up and down from both, once both exist
        self.setList.installEventFilter(self)
        self.searchBar.installEventFilter(self)
        # On the selection, not the current index: a click moves the current
        # index before it selects the row, so the set isn't selected yet then
        self.setList.selectionModel().selectionChanged.connect(
            lambda selected, deselected: self.details.SetSet(self.SelectedSet())
        )
        self.columnHeader = ColumnHeader(self.setList)
        listColumn.addWidget(self.columnHeader)
        listColumn.addWidget(self.setList, 1)
        self.emptyLabel = QLabel()
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyLabel.setWordWrap(True)
        self.emptyLabel.hide()
        listColumn.addWidget(self.emptyLabel, 1)
        body.addLayout(listColumn, 1)

        self.details = SetDetails()
        self.details.loadButton.clicked.connect(self.LoadSelectedSet)
        body.addWidget(self.details)
        layout.addLayout(body, 1)

        # Fetching progress, keyboard hints and cancel
        footer = QHBoxLayout()
        progressColumn = QVBoxLayout()
        progressColumn.setSpacing(4)
        self.labelStatus = QLabel()
        progressColumn.addWidget(self.labelStatus)
        self.progressBar = QProgressBar()
        self.progressBar.setTextVisible(False)
        self.progressBar.setFixedSize(220, 4)
        progressColumn.addWidget(self.progressBar)
        footer.addLayout(progressColumn)
        footer.addStretch()
        self.hintLabel = QLabel(
            QApplication.translate(
                "app",
                "↑ ↓ to move · Enter or double-click to load · Ctrl+F to search · Esc to close",
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
        self.SetLoading(False)
        self.resize(1200, 720)

        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        TournamentDataManager.instance.signals.sets_data_updated.connect(self.SetsUpdated)

    def AddFilter(self, layout, name):
        # A choice of one of the sets' values, "Any" first
        combo = QComboBox()
        combo.setProperty("filterName", name)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.currentIndexChanged.connect(lambda index: self.Rebuild())
        layout.addWidget(combo)
        self.FillFilter(combo, [])
        return combo

    def FillFilter(self, combo, values):
        name = combo.property("filterName")
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(QApplication.translate("app", "{0}: Any").format(name), None)
        for value in values:
            combo.addItem(f"{name}: {value}", value)
        # Keep what was picked while the sets still have it
        combo.setCurrentIndex(max(0, combo.findData(current)) if current is not None else 0)
        combo.blockSignals(False)
        combo.setVisible(len(values) > 0)

    def ApplyStyle(self):
        colors = ThemeColors()
        muted = f"color: {colors['muted'].name()};"
        for label in [
            self.eventLabel,
            self.updatedLabel,
            self.countLabel,
            self.labelStatus,
            self.hintLabel,
            self.emptyLabel,
        ]:
            label.setStyleSheet(muted)
        self.setList.setStyleSheet(f"""
            QListView {{
                background: {colors["surface"].name()}; outline: none;
                border: 1px solid {colors["border"].name()};
                border-radius: {Theme.Radius() + 2}px;
            }}
        """)
        self.delegate.colors = colors
        self.details.ApplyStyle()

    def showEvent(self, event):
        # The theme may have changed since the window was last open
        self.ApplyStyle()
        info = StateManager.Get("tournamentInfo") or {}
        self.eventLabel.setText(
            " · ".join(n for n in [info.get("tournamentName"), info.get("eventName")] if n)
        )
        self.eventLabel.setVisible(bool(self.eventLabel.text()))
        self.details.keepUpdated.setChecked(
            not SettingsManager.Get("general.disable_autoupdate", False)
        )
        super().showEvent(event)
        if self.dirty:
            self.Rebuild()
        self.FocusSearch()

    def FocusSearch(self):
        self.searchBar.setFocus()
        self.searchBar.selectAll()

    # =====================================================
    # FETCHING
    # =====================================================
    def LoadSets(self):
        self.fetchedFinished = STATUS_COMPLETED in SHOWN_STATUSES[self.showing]
        self.sets = []
        self.SetLoading(True)
        self.Rebuild()
        TournamentDataManager.instance.LoadSets(showFinished=self.fetchedFinished)

    def SetLoading(self, loading, progress=0, total=0):
        self.loading = loading
        self.progressBar.setVisible(loading)
        # No total yet: a busy bar
        self.progressBar.setRange(0, max(total, 0))
        self.progressBar.setValue(progress)
        if not loading:
            self.labelStatus.setText("")
        elif total > 0:
            self.labelStatus.setText(
                QApplication.translate("app", "Fetching sets...({0}/{1})").format(progress, total)
            )
        else:
            self.labelStatus.setText(QApplication.translate("app", "Fetching sets..."))
        self.refreshButton.setEnabled(not loading)

    def SetsUpdated(self, data):
        if data is None:
            return

        # Pages come in one at a time; the sets come once they're all in
        if data["progress"] < data["totalPages"]:
            self.SetLoading(True, data["progress"], data["totalPages"])
            return

        self.SetLoading(False)
        self.sets = data["sets"] or []
        self.updatedLabel.setText(
            QApplication.translate("app", "Updated at {0}").format(
                QLocale().toString(QTime.currentTime(), QLocale.FormatType.ShortFormat)
            )
        )
        streams, stations, phases = FilterOptions(self.sets)
        self.FillFilter(self.streamFilter, streams)
        self.FillFilter(self.stationFilter, stations)
        self.FillFilter(self.phaseFilter, phases)
        self.Rebuild()

    def SetShowing(self, showing):
        self.showing = showing
        # The completed sets are only fetched once they're asked for
        if STATUS_COMPLETED in SHOWN_STATUSES[showing] and not self.fetchedFinished:
            self.LoadSets()
        else:
            self.Rebuild()

    # =====================================================
    # THE LIST
    # =====================================================
    def Rebuild(self):
        if not self.isVisible():
            self.dirty = True
            return
        self.dirty = False

        selected = self.SelectedSet()
        selectedId = selected.get("id") if selected else None

        groups = GroupSets(
            self.sets,
            show=self.showing,
            text=self.searchBar.text(),
            hideEmptySlots=self.hideEmptySlots.isChecked(),
            stream=self.streamFilter.currentData(),
            station=self.stationFilter.currentData(),
            phase=self.phaseFilter.currentData(),
        )

        self.model.clear()
        firstRow, selectedRow = None, None
        shown = 0
        vs = QApplication.translate("app", "vs")
        for status, sets in groups:
            header = QStandardItem()
            header.setData((status, len(sets)), ROLE_HEADER)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.model.appendRow(header)
            for s in sets:
                item = QStandardItem()
                item.setData(s, ROLE_SET)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setToolTip(f"{s.get('p1_name') or ''} {vs} {s.get('p2_name') or ''}")
                self.model.appendRow(item)
                row = self.model.rowCount() - 1
                if firstRow is None:
                    firstRow = row
                if selectedId is not None and s.get("id") == selectedId:
                    selectedRow = row
                shown += 1

        self.countLabel.setText(
            QApplication.translate("app", "Showing {0} of {1} sets").format(shown, len(self.sets))
            if self.sets
            else ""
        )

        # Keep a set selected, so Load and Enter load what's on screen
        row = selectedRow if selectedRow is not None else firstRow
        if row is not None:
            index = self.model.index(row, 0)
            self.setList.setCurrentIndex(index)
            self.setList.scrollTo(index)
        self.details.SetSet(self.SelectedSet())

        empty = shown == 0
        self.setList.setVisible(not empty)
        self.columnHeader.setVisible(not empty)
        self.emptyLabel.setVisible(empty)
        if self.loading:
            self.emptyLabel.setText(QApplication.translate("app", "Fetching sets..."))
        elif not self.sets:
            self.emptyLabel.setText(QApplication.translate("app", "There are no sets to show."))
        else:
            self.emptyLabel.setText(
                QApplication.translate("app", "No sets match the search and filters.")
            )

    def SelectedSet(self):
        index = self.setList.currentIndex()
        if not index.isValid() or not self.setList.selectionModel().isSelected(index):
            return None
        return index.data(ROLE_SET)

    def MoveSelection(self, step):
        # To the next set up or down, past the group headers
        row = self.setList.currentIndex().row()
        row = row + step if row >= 0 else 0
        while 0 <= row < self.model.rowCount():
            index = self.model.index(row, 0)
            if index.data(ROLE_SET) is not None:
                self.setList.setCurrentIndex(index)
                self.setList.scrollTo(index)
                return
            row += step

    def eventFilter(self, obj, event):
        if obj in (self.setList, self.searchBar) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.LoadSelectedSet()
                return True
            # Up and down pick a set from the search bar too
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self.MoveSelection(-1 if key == Qt.Key.Key_Up else 1)
                return True
        return super().eventFilter(obj, event)

    # =====================================================
    # LOADING THE SET
    # =====================================================
    def LoadSelectedSet(self):
        s = self.SelectedSet()
        if s is None:
            return
        self.accept()

        setData = dict(s)
        setData["auto_update"] = "set"
        setData["keep_updated"] = self.details.keepUpdated.isChecked()
        self.parent().signals.NewSetSelected.emit(setData)

        if TournamentDataManager.instance.setLoadingWorker:
            # If there was a previous set loading worker,
            # block its signals
            TournamentDataManager.instance.setLoadingWorker.cancel()
            TournamentDataManager.instance.setLoadingWorker.signals.blockSignals(True)
