"""The row of squares under a scoreboard's score, one per game of the set.

A game won by a team is filled with that team's color, a draw is split
between both colors, and a game not played yet is an empty outline. The
game being played is outlined in the theme's highlight color. Clicking a
square opens the game in the Games window; right-clicking sets who won it.
"""

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameReport import DRAW, UNDECIDED

SQUARE = 22
GAP = 5


class GamesTracker(QWidget):
    """games: GameReport.games. colors: the teams' colors. tooltip(index)
    and teamName(team) are asked for when needed."""

    gameClicked = Signal(int)
    # Game index, and 1, 2, DRAW or UNDECIDED
    winnerPicked = Signal(int, object)

    def __init__(self, tooltip=None, teamName=None, parent=None):
        super().__init__(parent)
        self.games = []
        self.current = -1
        self.colors = [QColor("#fe3636"), QColor("#2e89ff")]
        self.tooltip = tooltip
        self.teamName = teamName or (
            lambda team: QApplication.translate("app", "Team {0}").format(team)
        )
        self.hovered = -1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def SetGames(self, games, current):
        self.games = list(games or [])
        self.current = current
        self.setVisible(bool(self.games))
        self.UpdateHeight()
        self.update()

    def SetColors(self, color1, color2):
        self.colors = [QColor(color1), QColor(color2)]
        self.update()

    # Layout: rows of squares, centered, wrapping when narrow

    def PerRow(self, width=None):
        width = width if width is not None else self.width()
        return max(1, (width + GAP) // (SQUARE + GAP))

    def Rects(self):
        rects = []
        perRow = self.PerRow()
        count = len(self.games)
        for i in range(count):
            row, column = divmod(i, perRow)
            inRow = min(perRow, count - row * perRow)
            rowWidth = inRow * SQUARE + (inRow - 1) * GAP
            left = (self.width() - rowWidth) // 2
            rects.append(
                QRect(left + column * (SQUARE + GAP), 2 + row * (SQUARE + GAP), SQUARE, SQUARE)
            )
        return rects

    def heightForWidth(self, width):
        if not self.games:
            return 0
        rows = (len(self.games) + self.PerRow(width) - 1) // self.PerRow(width)
        return rows * SQUARE + (rows - 1) * GAP + 4

    def sizeHint(self):
        count = max(1, len(self.games))
        return QSize(count * SQUARE + (count - 1) * GAP, self.heightForWidth(10_000))

    def minimumSizeHint(self):
        return QSize(SQUARE, self.heightForWidth(SQUARE))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # The rows may wrap differently
        self.UpdateHeight()

    def UpdateHeight(self):
        height = self.heightForWidth(max(self.width(), SQUARE))
        if self.height() != height or self.minimumHeight() != height:
            self.setFixedHeight(height)

    def IndexAt(self, pos):
        for i, rect in enumerate(self.Rects()):
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                return i
        return -1

    # Drawing

    @staticmethod
    def TextColorOn(color):
        luminance = 0.299 * color.redF() + 0.587 * color.greenF() + 0.114 * color.blueF()
        return QColor("#111111") if luminance > 0.6 else QColor("#ffffff")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        font.setBold(True)
        painter.setFont(font)

        for i, rect in enumerate(self.Rects()):
            game = self.games[i]
            winner = game.get("winner")
            square = QRectF(rect).adjusted(1, 1, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(square, 4, 4)

            if winner in (1, 2):
                fill = self.colors[winner - 1]
                painter.fillPath(path, fill)
                textColor = self.TextColorOn(fill)
            elif winner == DRAW:
                # Split diagonally between both teams' colors
                painter.save()
                painter.setClipPath(path)
                first = QPolygonF([square.topLeft(), square.topRight(), square.bottomLeft()])
                second = QPolygonF([square.topRight(), square.bottomRight(), square.bottomLeft()])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.colors[0])
                painter.drawPolygon(first)
                painter.setBrush(self.colors[1])
                painter.drawPolygon(second)
                painter.restore()
                textColor = QColor("#ffffff")
            else:
                textColor = palette.color(QPalette.ColorRole.Text)
                textColor.setAlpha(150)

            # Outline: the current game in the highlight color, unplayed ones
            # in a faint one, hovered ones a bit stronger
            if i == self.current:
                pen = QPen(palette.color(QPalette.ColorRole.Highlight), 2)
            else:
                outline = QColor(palette.color(QPalette.ColorRole.Text))
                outline.setAlpha(140 if i == self.hovered else 70)
                pen = QPen(outline, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(square, 4, 4)

            painter.setPen(textColor)
            painter.drawText(square, Qt.AlignmentFlag.AlignCenter, str(i + 1))

    # Mouse

    def mouseMoveEvent(self, event):
        index = self.IndexAt(event.position().toPoint())
        if index != self.hovered:
            self.hovered = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered = -1
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.IndexAt(event.position().toPoint())
            if index >= 0:
                self.gameClicked.emit(index)
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        index = self.IndexAt(event.pos())
        if index < 0:
            return
        menu = QMenu(self)
        winner = self.games[index].get("winner")
        for value, text in [
            (1, QApplication.translate("app", "Won by {0}").format(self.teamName(1))),
            (2, QApplication.translate("app", "Won by {0}").format(self.teamName(2))),
            (DRAW, QApplication.translate("app", "Draw")),
            (UNDECIDED, QApplication.translate("app", "Not played")),
        ]:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(winner == value)
            action.triggered.connect(lambda _c=False, v=value: self.winnerPicked.emit(index, v))
        menu.addSeparator()
        menu.addAction(
            QApplication.translate("app", "Open in the Games window"),
            lambda: self.gameClicked.emit(index),
        )
        menu.exec(event.globalPos())

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self.IndexAt(event.pos())
            if index >= 0 and self.tooltip is not None:
                QToolTip.showText(event.globalPos(), self.tooltip(index), self)
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)
