# Draws a bracket (TSHBracketModel.Bracket) and lets it be edited: double
# click a set (or right click it) to change its result or players, drag a
# player onto another slot to swap them, double click a round's name to
# rename it. Ctrl+click sets and round names to pick what the bracket focus
# layout zooms to.
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .TSHBracketModel import *


class TSHBracketViewSignals(QObject):
    # The bracket was edited in the view
    edited = Signal()
    # Sets or rounds were selected for the bracket focus layout
    selectionChanged = Signal()
    # Asked from a menu: focus the layout on sets, rounds or a player
    focusSets = Signal(list)
    focusRounds = Signal(list)
    focusPlayer = Signal(int)


def SourceText(bracket, source):
    """What a slot waiting for its player says, like start.gg does."""
    type = (source or {}).get("type")
    other = bracket.matches.get(str((source or {}).get("match")))
    if type == "slot" and other is not None:
        # Same player as in the grand final
        return SourceText(bracket, other.sources[int(source.get("slot") or 0)])
    if type == "winner" and other is not None:
        return QApplication.translate("app", "Winner of {0}").format(other.identifier)
    if type == "loser" and other is not None:
        return QApplication.translate("app", "Loser of {0}").format(other.identifier)
    if type == "seed":
        return QApplication.translate("app", "Seed {0}").format(source.get("seed"))
    return QApplication.translate("app", "TBD")


class MatchItem(QGraphicsObject):
    WIDTH = 240
    ROW_HEIGHT = 24
    GUTTER = 26
    SCORE_WIDTH = 32
    SEED_WIDTH = 26

    def __init__(self, view: TSHBracketView, match: BracketMatch):
        super().__init__()
        self.view = view
        self.match = match
        self.hovered = None
        self.dropTarget = None
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            QApplication.translate(
                "app",
                "Double click to edit. Drag a player onto another slot to swap them. Ctrl+click to select it for the bracket focus layout.",
            )
        )

    def boundingRect(self):
        # Room around the set for the selection outline
        return QRectF(-4, -4, MatchItem.WIDTH + 8, MatchItem.ROW_HEIGHT * 2 + 9)

    def SetRect(self):
        return QRectF(0, 0, MatchItem.WIDTH, MatchItem.ROW_HEIGHT * 2 + 1)

    def RowAt(self, pos: QPointF):
        if not self.SetRect().contains(pos) or pos.x() < MatchItem.GUTTER:
            return None
        return 0 if pos.y() < MatchItem.ROW_HEIGHT else 1

    def hoverMoveEvent(self, event):
        row = self.RowAt(event.pos())
        if row != self.hovered:
            self.hovered = row
            self.update()

    def hoverLeaveEvent(self, event):
        self.hovered = None
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        m = self.match
        bracket = self.view.bracket
        palette = QApplication.palette()
        base = palette.color(QPalette.ColorRole.Base)
        alt = palette.color(QPalette.ColorRole.AlternateBase)
        text = palette.color(QPalette.ColorRole.Text)
        mid = palette.color(QPalette.ColorRole.Mid)
        accent = palette.color(QPalette.ColorRole.Highlight)
        dim = QColor(text)
        dim.setAlphaF(0.45)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        faded = m.notNeeded or not self.view.InExport(m)
        painter.setOpacity(0.45 if faded else 1.0)

        rect = self.SetRect()
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        painter.fillPath(path, base)

        # Identifier gutter
        gutter = QRectF(0, 0, MatchItem.GUTTER, rect.height())
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(gutter, alt)
        painter.restore()
        font = painter.font()
        small = QFont(font)
        small.setPointSizeF(max(6.0, font.pointSizeF() * 0.8))
        painter.setFont(small)
        painter.setPen(dim)
        painter.drawText(gutter, Qt.AlignmentFlag.AlignCenter, m.identifier)

        for slot in range(2):
            top = slot * (MatchItem.ROW_HEIGHT + 1)
            row = QRectF(
                MatchItem.GUTTER, top, rect.width() - MatchItem.GUTTER, MatchItem.ROW_HEIGHT
            )
            player = m.players[slot]
            won = m.winnerSlot == slot and m.finished and BYE not in m.players
            lost = m.winnerSlot == 1 - slot and m.finished and BYE not in m.players

            if self.dropTarget == slot:
                highlight = QColor(accent)
                highlight.setAlphaF(0.35)
                painter.fillRect(row, highlight)
            elif self.hovered == slot:
                highlight = QColor(accent)
                highlight.setAlphaF(0.12)
                painter.fillRect(row, highlight)

            if won:
                painter.fillRect(QRectF(row.left(), row.top() + 3, 3, row.height() - 6), accent)

            # Seed
            seedRect = QRectF(row.left() + 5, row.top(), MatchItem.SEED_WIDTH, row.height())
            painter.setFont(small)
            painter.setPen(dim)
            if player > 0:
                seed = bracket.SeedOf(player)
                if seed != 9999:
                    painter.drawText(
                        seedRect,
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        str(seed),
                    )

            # Name
            nameFont = QFont(font)
            nameFont.setBold(won)
            nameRect = QRectF(
                seedRect.right() + 2,
                row.top(),
                row.width() - MatchItem.SEED_WIDTH - MatchItem.SCORE_WIDTH - 12,
                row.height(),
            )
            if player > 0:
                name = self.view.PlayerName(player) or QApplication.translate(
                    "app", "Player {0}"
                ).format(player)
                painter.setPen(dim if lost else text)
            elif player == BYE:
                name = QApplication.translate("app", "Bye")
                nameFont.setItalic(True)
                painter.setPen(dim)
            else:
                name = SourceText(bracket, m.sources[slot])
                nameFont.setItalic(True)
                painter.setPen(dim)
            if m.override[slot] is not None:
                name = "✎ " + name
            painter.setFont(nameFont)
            name = QFontMetrics(nameFont).elidedText(
                name, Qt.TextElideMode.ElideRight, int(nameRect.width())
            )
            painter.drawText(
                nameRect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name
            )

            # Score
            scoreRect = QRectF(
                row.right() - MatchItem.SCORE_WIDTH, row.top(), MatchItem.SCORE_WIDTH, row.height()
            )
            painter.fillRect(
                scoreRect,
                alt if not won else QColor(accent.red(), accent.green(), accent.blue(), 70),
            )
            score = m.score[slot]
            if player > 0 and (m.finished or any(m.score)):
                if score == -1:
                    scoreText = QApplication.translate("app", "DQ")
                elif m.finished and m.winnerOverride is not None and m.score == [0, 0]:
                    scoreText = (
                        QApplication.translate("app", "W")
                        if won
                        else QApplication.translate("app", "L")
                    )
                else:
                    scoreText = str(score)
                scoreFont = QFont(font)
                scoreFont.setBold(won)
                painter.setFont(scoreFont)
                painter.setPen(text if not lost else dim)
                painter.drawText(scoreRect, Qt.AlignmentFlag.AlignCenter, scoreText)

        # Line between the slots
        painter.setPen(QPen(mid, 1))
        painter.drawLine(
            QPointF(MatchItem.GUTTER, MatchItem.ROW_HEIGHT + 0.5),
            QPointF(rect.width(), MatchItem.ROW_HEIGHT + 0.5),
        )

        if m.notNeeded:
            painter.setOpacity(1.0)
            painter.setFont(small)
            painter.setPen(text)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, QApplication.translate("app", "Not needed")
            )

        painter.setOpacity(1.0)
        painter.setPen(QPen(accent if self.hovered is not None else mid, 1))
        painter.drawPath(path)

        # In focus on the bracket focus layout, and selected to be
        if m.id in self.view.focused:
            painter.setPen(QPen(accent, 3))
            painter.drawPath(path)
        if m.id in self.view.selected:
            pen = QPen(text, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            outline = QPainterPath()
            outline.addRoundedRect(rect.adjusted(-3, -3, 3, 3), 6, 6)
            painter.drawPath(outline)

    def mouseDoubleClickEvent(self, event):
        self.view.EditMatch(self.match)

    def contextMenuEvent(self, event):
        self.view.MatchMenu(self.match, self.RowAt(event.pos()), event.screenPos())


class RoundHeaderItem(QGraphicsSimpleTextItem):
    def __init__(self, view, side, column, text):
        super().__init__(text)
        self.view = view
        self.side = side
        self.column = column
        self.key = Bracket.RoundKey(side, column)
        font = self.font()
        font.setBold(True)
        self.setFont(font)
        self.UpdateStyle()
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setToolTip(
            QApplication.translate(
                "app",
                "Double click to rename this round. Ctrl+click to select it for the bracket focus layout.",
            )
        )

    def UpdateStyle(self):
        palette = QApplication.palette()
        selected = self.key in self.view.selectedRounds
        focused = self.key in self.view.focusedRounds
        font = self.font()
        font.setUnderline(selected)
        self.setFont(font)
        self.setBrush(
            palette.color(QPalette.ColorRole.Highlight)
            if focused or selected
            else palette.color(QPalette.ColorRole.Text)
        )

    def mouseDoubleClickEvent(self, event):
        self.view.RenameRound(self.side, self.column)

    def contextMenuEvent(self, event):
        self.view.RoundMenu(self.key, event.screenPos())


class MatchEditDialog(QDialog):
    """Result and players of a set."""

    def __init__(self, view: TSHBracketView, match: BracketMatch):
        super().__init__(view)
        self.view = view
        self.match = match
        bracket = view.bracket
        self.setWindowTitle(QApplication.translate("app", "Set {0}").format(match.identifier))

        layout = QGridLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel(QApplication.translate("app", "Player")), 0, 0)
        layout.addWidget(QLabel(QApplication.translate("app", "Score")), 0, 1)

        self.playerSelects = []
        self.scores = []
        for slot in range(2):
            select = QComboBox()
            current = match.players[slot]
            if match.override[slot] is not None:
                auto = QApplication.translate("app", "From the bracket")
            elif current > 0:
                auto = QApplication.translate("app", "From the bracket ({0})").format(
                    view.PlayerName(current)
                )
            else:
                auto = QApplication.translate("app", "From the bracket ({0})").format(
                    QApplication.translate("app", "Bye")
                    if current == BYE
                    else SourceText(bracket, match.sources[slot])
                )
            select.addItem(auto, None)
            select.addItem(QApplication.translate("app", "Bye"), BYE)
            for player in view.RosterIds():
                select.addItem(
                    f"{bracket.SeedOf(player) if bracket.SeedOf(player) != 9999 else '-'}. {view.PlayerName(player)}",
                    player,
                )
            if match.override[slot] is not None:
                index = select.findData(match.override[slot])
                select.setCurrentIndex(max(index, 0))
            if bracket.fromProvider:
                select.setToolTip(
                    QApplication.translate("app", "Changes made here aren't sent to start.gg")
                )
            layout.addWidget(select, slot + 1, 0)
            self.playerSelects.append(select)

            score = QSpinBox()
            score.setMinimum(-1)
            score.setMaximum(999)
            score.setSpecialValueText(QApplication.translate("app", "DQ"))
            score.setValue(match.score[slot])
            layout.addWidget(score, slot + 1, 1)
            self.scores.append(score)

        layout.addWidget(QLabel(QApplication.translate("app", "Winner")), 3, 0)
        self.winner = QComboBox()
        self.winner.addItem(QApplication.translate("app", "By score"), None)
        self.winner.addItem(QApplication.translate("app", "Top player"), 0)
        self.winner.addItem(QApplication.translate("app", "Bottom player"), 1)
        self.winner.setCurrentIndex(max(0, self.winner.findData(match.winnerOverride)))
        layout.addWidget(self.winner, 3, 1)

        self.finished = QCheckBox(QApplication.translate("app", "Finished"))
        self.finished.setChecked(match.finished)
        layout.addWidget(self.finished, 4, 0, 1, 2)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        clear = buttons.addButton(
            QApplication.translate("app", "Clear result"), QDialogButtonBox.ButtonRole.ResetRole
        )
        clear.clicked.connect(self.ClearResult)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 5, 0, 1, 2)

    def ClearResult(self):
        for score in self.scores:
            score.setValue(0)
        self.winner.setCurrentIndex(0)
        self.finished.setChecked(False)

    def Apply(self):
        m = self.match
        for slot in range(2):
            m.override[slot] = self.playerSelects[slot].currentData()
            m.score[slot] = self.scores[slot].value()
        m.winnerOverride = self.winner.currentData()
        m.finished = self.finished.isChecked()
        self.view.bracket.Resolve()


class TSHBracketView(QGraphicsView):
    COLUMN_GAP = 56
    ROW_GAP = 14
    HEADER_HEIGHT = 28
    SECTION_GAP = 56

    def __init__(self, *args):
        super().__init__(*args)
        self.signals = TSHBracketViewSignals()

        self.bracket: Bracket = None
        # Set by the bracket widget
        self.playerName = lambda player: ""
        self.rosterIds = lambda: []
        self.exportLimit = None

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QApplication.palette().color(QPalette.ColorRole.Window))
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.matchItems: dict[str, MatchItem] = {}
        self.headerItems: dict[str, RoundHeaderItem] = {}
        # Sets and rounds selected for the bracket focus layout, and the ones
        # it shows now
        self.selected: set[str] = set()
        self.selectedRounds: set[str] = set()
        self.focused: set[str] = set()
        self.focusedRounds: set[str] = set()
        self._dragFrom = None
        self._dragPos = None
        self._dragging = False
        self._lastTarget = None
        self._fitPending = False

    # Data the widget provides

    def PlayerName(self, player):
        try:
            return self.playerName(player)
        except Exception:
            return ""

    def RosterIds(self):
        return list(self.rosterIds())

    def InExport(self, m):
        if self.exportLimit is None or self.bracket is None or self.bracket.IsPool():
            return True
        return self.bracket.InTopN(m, self.exportLimit)

    # Building the scene

    def SetBracket(self, bracket: Bracket, fit=True):
        self.bracket = bracket
        self.Rebuild()
        if fit:
            self._fitPending = True
            QTimer.singleShot(0, self._FitIfPending)

    def _FitIfPending(self):
        if self._fitPending:
            self._fitPending = False
            self.FitInView()

    def Rebuild(self):
        self._scene.clear()
        self.matchItems = {}
        self.headerItems = {}
        if self.bracket is None:
            if self.selected or self.selectedRounds:
                self.ClearSelection()
            return

        if self.bracket.IsPool():
            self._LayOutPool()
        else:
            self._LayOutElimination()

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-30, -30, 30, 30))

        # Sets and rounds that are gone can't stay selected
        selected = self.selected & set(self.matchItems.keys())
        rounds = self.selectedRounds & set(self.headerItems.keys())
        if selected != self.selected or rounds != self.selectedRounds:
            self.selected, self.selectedRounds = selected, rounds
            self.signals.selectionChanged.emit()

    def Refresh(self):
        """Results changed but the structure didn't."""
        if self.bracket is None:
            return
        # Byes and resets that aren't needed can change what's shown
        shown = {m.id for side in SIDES for column in self.bracket.Columns(side) for m in column}
        if shown != set(self.matchItems.keys()):
            self.Rebuild()
            return
        for item in self.matchItems.values():
            item.update()

    def _AddHeader(self, side, column, x, y):
        header = RoundHeaderItem(self, side, column, self.bracket.RoundName(side, column))
        header.setPos(x, y)
        self._scene.addItem(header)
        self.headerItems[header.key] = header

    def _AddMatch(self, m, x, y):
        item = MatchItem(self, m)
        item.setPos(x, y)
        item.setZValue(1)
        self._scene.addItem(item)
        self.matchItems[m.id] = item
        return item

    def _LayOutSide(self, side, top, left=0):
        """Places a side's columns from `left`, `top`. Each set goes next to
        the sets that feed it. Returns {match id: (x, y)} and the bottom."""
        height = MatchItem.ROW_HEIGHT * 2 + 1
        positions = {}
        bottom = top
        for ci, column in enumerate(self.bracket.Columns(side)):
            x = left + ci * (MatchItem.WIDTH + TSHBracketView.COLUMN_GAP)
            self._AddHeader(side, column[0].column, x, top)
            cursor = top + TSHBracketView.HEADER_HEIGHT
            for m in column:
                feeders = [positions[p] for p in self.bracket._Prereqs(m) if p in positions]
                y = cursor
                if feeders:
                    y = max(cursor, sum(f[1] for f in feeders) / len(feeders))
                positions[m.id] = (x, y)
                self._AddMatch(m, x, y)
                cursor = y + height + TSHBracketView.ROW_GAP
                bottom = max(bottom, cursor)
        return positions, bottom

    def _LayOutElimination(self):
        height = MatchItem.ROW_HEIGHT * 2 + 1
        positions, bottom = self._LayOutSide(SIDE_WINNERS, 0)
        columns = len(self.bracket.Columns(SIDE_WINNERS))

        # Grand final and its reset after the winners side, level with the
        # winners final
        winnersFinal = None
        for m in self.bracket.matches.values():
            if (
                m.side == SIDE_WINNERS
                and m.id in positions
                and m.nextWin is not None
                and self.bracket.matches[m.nextWin[0]].side == SIDE_GRAND_FINAL
            ):
                winnersFinal = m
        gfY = positions[winnersFinal.id][1] if winnersFinal else TSHBracketView.HEADER_HEIGHT
        for ci, column in enumerate(self.bracket.Columns(SIDE_GRAND_FINAL, includeHidden=True)):
            x = (columns + ci) * (MatchItem.WIDTH + TSHBracketView.COLUMN_GAP)
            self._AddHeader(
                SIDE_GRAND_FINAL, column[0].column, x, gfY - TSHBracketView.HEADER_HEIGHT
            )
            for m in column:
                positions[m.id] = (x, gfY)
                self._AddMatch(m, x, gfY)

        # Third place match under the final
        third = self.bracket.Columns(SIDE_THIRD_PLACE)
        if third:
            final = next(
                (
                    m
                    for m in self.bracket.matches.values()
                    if m.side == SIDE_WINNERS and m.nextWin is None and m.id in positions
                ),
                None,
            )
            x, y = positions[final.id] if final else (0, bottom)
            y = max(y + height + TSHBracketView.SECTION_GAP, bottom + TSHBracketView.ROW_GAP)
            self._AddHeader(SIDE_THIRD_PLACE, third[0][0].column, x, y)
            for m in third[0]:
                y += TSHBracketView.HEADER_HEIGHT
                positions[m.id] = (x, y)
                self._AddMatch(m, x, y)
                bottom = max(bottom, y + height)

        if self.bracket.Columns(SIDE_LOSERS):
            losers, _bottom = self._LayOutSide(SIDE_LOSERS, bottom + TSHBracketView.SECTION_GAP)
            positions.update(losers)

        self._DrawLines(positions)

    def _DrawLines(self, positions):
        height = MatchItem.ROW_HEIGHT * 2 + 1
        path = QPainterPath()
        for m in self.bracket.matches.values():
            if m.id not in positions:
                continue
            for slot, source in enumerate(m.sources):
                if source.get("type") not in ("winner", "slot"):
                    continue
                prereq = str(source.get("match"))
                if prereq not in positions:
                    continue
                if source.get("type") == "slot" and slot != 0:
                    continue
                px, py = positions[prereq]
                x, y = positions[m.id]
                if x <= px:
                    continue
                start = QPointF(px + MatchItem.WIDTH, py + height / 2)
                end = QPointF(x, y + MatchItem.ROW_HEIGHT / 2 + slot * (MatchItem.ROW_HEIGHT + 1))
                midX = start.x() + (end.x() - start.x()) / 2
                path.moveTo(start)
                path.lineTo(midX, start.y())
                path.lineTo(midX, end.y())
                path.lineTo(end)
        color = QApplication.palette().color(QPalette.ColorRole.Mid)
        item = self._scene.addPath(path, QPen(color, 2))
        item.setZValue(0)

    def _LayOutPool(self):
        height = MatchItem.ROW_HEIGHT * 2 + 1
        dim = QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        for ci, column in enumerate(self.bracket.Columns(SIDE_POOL)):
            x = ci * (MatchItem.WIDTH + TSHBracketView.COLUMN_GAP)
            round = column[0].column
            self._AddHeader(SIDE_POOL, round, x, 0)
            y = TSHBracketView.HEADER_HEIGHT
            for m in column:
                self._AddMatch(m, x, y)
                y += height + TSHBracketView.ROW_GAP
            byes = self.bracket.byes.get(str(column[0].round)) or []
            if byes:
                text = QGraphicsSimpleTextItem(
                    QApplication.translate("app", "Bye: {0}").format(
                        ", ".join(self.PlayerName(p) or str(p) for p in byes)
                    )
                )
                text.setBrush(dim)
                text.setPos(x, y)
                self._scene.addItem(text)

    # Editing

    def Edited(self):
        self.Refresh()
        self.signals.edited.emit()

    def EditMatch(self, m):
        dialog = MatchEditDialog(self, m)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.Apply()
            self.Edited()

    # Selecting for the bracket focus layout

    def ToggleSelected(self, id):
        self.selected ^= {id}
        if id in self.matchItems:
            self.matchItems[id].update()
        self.signals.selectionChanged.emit()

    def ToggleSelectedRound(self, key):
        self.selectedRounds ^= {key}
        if key in self.headerItems:
            self.headerItems[key].UpdateStyle()
        self.signals.selectionChanged.emit()

    def ClearSelection(self):
        self.selected = set()
        self.selectedRounds = set()
        for item in self.matchItems.values():
            item.update()
        for header in self.headerItems.values():
            header.UpdateStyle()
        self.signals.selectionChanged.emit()

    def SetFocused(self, sets, rounds):
        """Shows which sets and rounds the bracket focus layout shows."""
        sets, rounds = set(sets or []), set(rounds or [])
        if sets == self.focused and rounds == self.focusedRounds:
            return
        self.focused, self.focusedRounds = sets, rounds
        for item in self.matchItems.values():
            item.update()
        for header in self.headerItems.values():
            header.UpdateStyle()

    def RoundMenu(self, key, screenPos):
        menu = QMenu(self)
        menu.addAction(
            QApplication.translate("app", "Focus the layout on this round"),
            lambda: self.signals.focusRounds.emit([key]),
        )
        menu.addAction(
            QApplication.translate("app", "Unselect this round")
            if key in self.selectedRounds
            else QApplication.translate("app", "Select this round"),
            lambda: self.ToggleSelectedRound(key),
        )
        menu.exec(screenPos if isinstance(screenPos, QPoint) else screenPos.toPoint())

    def MatchMenu(self, m, row, screenPos):
        menu = QMenu(self)
        menu.addAction(QApplication.translate("app", "Edit..."), lambda: self.EditMatch(m))
        menu.addSeparator()
        menu.addAction(
            QApplication.translate("app", "Focus the layout on this set"),
            lambda: self.signals.focusSets.emit([m.id]),
        )
        menu.addAction(
            QApplication.translate("app", "Unselect this set")
            if m.id in self.selected
            else QApplication.translate("app", "Select this set"),
            lambda: self.ToggleSelected(m.id),
        )
        if row is not None and m.players[row] > 0:
            player = m.players[row]
            menu.addAction(
                QApplication.translate("app", "Focus the layout on {0}'s run").format(
                    self.PlayerName(player) or player
                ),
                lambda: self.signals.focusPlayer.emit(player),
            )
        menu.addSeparator()
        for slot, label in (
            (0, QApplication.translate("app", "Top player won")),
            (1, QApplication.translate("app", "Bottom player won")),
        ):
            action = menu.addAction(
                label, lambda slot=slot: [self.bracket.SetWinner(m.id, slot), self.Edited()]
            )
            action.setEnabled(m.players[slot] > 0)
        menu.addAction(
            QApplication.translate("app", "Clear result"),
            lambda: [self.bracket.ClearResult(m.id), self.Edited()],
        )
        if any(o is not None for o in m.override):
            menu.addAction(
                QApplication.translate("app", "Use the bracket's players"),
                lambda: [
                    setattr(m, "override", [None, None]),
                    self.bracket.Resolve(),
                    self.Edited(),
                ],
            )
        menu.exec(screenPos if isinstance(screenPos, QPoint) else screenPos.toPoint())

    def RenameRound(self, side, column):
        key = Bracket.RoundKey(side, column)
        name, ok = QInputDialog.getText(
            self,
            QApplication.translate("app", "Round name"),
            QApplication.translate("app", "Name (leave empty for the default one):"),
            text=self.bracket.roundNames.get(key, ""),
        )
        if ok:
            if name.strip():
                self.bracket.roundNames[key] = name.strip()
            else:
                self.bracket.roundNames.pop(key, None)
            self.Rebuild()
            self.signals.edited.emit()

    # Dragging a player onto another slot swaps them

    def _SlotAt(self, viewPos):
        for item in self._scene.items(self.mapToScene(viewPos)):
            if isinstance(item, MatchItem):
                row = item.RowAt(item.mapFromScene(self.mapToScene(viewPos)))
                if row is not None:
                    return item, row
        return None

    def mousePressEvent(self, event):
        # Ctrl+click selects sets and rounds for the bracket focus layout
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            for item in self._scene.items(self.mapToScene(event.pos())):
                if isinstance(item, MatchItem):
                    self.ToggleSelected(item.match.id)
                    return
                if isinstance(item, RoundHeaderItem):
                    self.ToggleSelectedRound(item.key)
                    return
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._SlotAt(event.pos())
            if hit is not None and hit[0].match.players[hit[1]] != BYE:
                self._dragFrom = hit
                self._dragPos = event.pos()
                self._dragging = False
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragFrom is not None:
            if (
                not self._dragging
                and (event.pos() - self._dragPos).manhattanLength()
                > QApplication.startDragDistance()
            ):
                self._dragging = True
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragging:
                target = self._SlotAt(event.pos())
                if self._lastTarget is not None and self._lastTarget != target:
                    self._lastTarget[0].dropTarget = None
                    self._lastTarget[0].update()
                if target is not None and target != self._dragFrom:
                    target[0].dropTarget = target[1]
                    target[0].update()
                self._lastTarget = target
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragFrom is not None:
            source = self._dragFrom
            dragging = self._dragging
            self._dragFrom = None
            self._dragging = False
            self.viewport().unsetCursor()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            if self._lastTarget is not None:
                self._lastTarget[0].dropTarget = None
                self._lastTarget[0].update()
                self._lastTarget = None
            if dragging:
                target = self._SlotAt(event.pos())
                if target is not None and target != source:
                    try:
                        self.bracket.SwapSlots(
                            source[0].match.id, source[1], target[0].match.id, target[1]
                        )
                        self.Edited()
                    except Exception:
                        logger.exception("Couldn't swap the players")
                return
        super().mouseReleaseEvent(event)

    # Zoom

    def FitInView(self):
        rect = self._scene.sceneRect()
        if rect.isNull():
            return
        self.resetTransform()
        viewRect = self.viewport().rect()
        factor = min(viewRect.width() / rect.width(), viewRect.height() / rect.height())
        # Not bigger than life size
        factor = min(factor, 1.0)
        self.scale(factor, factor)
        self.ensureVisible(QRectF(rect.topLeft(), QSizeF(1, 1)), 0, 0)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = self.transform().m11()
        if 0.1 < current * factor < 4:
            self.scale(factor, factor)
