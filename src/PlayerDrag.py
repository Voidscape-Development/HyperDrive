"""Dragging players by the grip in their header to another place.

A PlayerDragBoard holds the groups of player widgets a player can be dragged
between (a scoreboard's two teams, the commentators, a player list's slots,
the team battle's teams). Dropping a player on another one of the same group
puts them in that place and shifts the ones in between; dropping on a player
of another group swaps the two, as the groups keep their size. The widgets
stay where they are: their data is moved, with the swaps the move buttons
already use.
"""

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .StateManager import StateManager
from .Theme import SetLabelIcon

MIME_TYPE = "application/x-hyperdrive-player"

# The player being dragged. Drags only happen inside the app, so the widget
# itself is kept here rather than in the drag's data.
_dragged = None


def Dragged():
    return _dragged


class _Grip(QLabel):
    """The handle a player is dragged by."""

    def __init__(self, player, board):
        super().__init__()
        self.setObjectName("dragGrip")
        self.player = player
        self.board = board
        self.pressPos = None
        SetLabelIcon(self, "assets/icons/grip.svg", QApplication.translate("app", "Drag to move"))
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressPos = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressPos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        distance = (event.position().toPoint() - self.pressPos).manhattanLength()
        if distance >= QApplication.startDragDistance():
            self.pressPos = None
            self.board.StartDrag(self.player, self)

    def mouseReleaseEvent(self, event):
        self.pressPos = None
        super().mouseReleaseEvent(event)


class _DropHighlight(QWidget):
    """The outline drawn over the player a drop would land on."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def Show(self):
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.palette().color(QPalette.ColorRole.Highlight))
        pen = QPen(color, 2)
        painter.setPen(pen)
        color.setAlpha(30)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)


class _DropTarget(QObject):
    """Takes the drags and drops over a player widget."""

    def __init__(self, player, board):
        super().__init__(player)
        self.player = player
        self.board = board
        self.highlight = _DropHighlight(player)
        player.setAcceptDrops(True)
        player.installEventFilter(self)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if event.mimeData().hasFormat(MIME_TYPE) and self.board.CanDrop(_dragged, self.player):
                event.acceptProposedAction()
                self.highlight.Show()
            else:
                event.ignore()
                self.highlight.hide()
            return True
        if kind == QEvent.Type.DragLeave:
            self.highlight.hide()
            return True
        if kind == QEvent.Type.Drop:
            self.highlight.hide()
            if event.mimeData().hasFormat(MIME_TYPE) and self.board.CanDrop(_dragged, self.player):
                event.acceptProposedAction()
                # After the drag ends, so the source's drag loop is finished
                source = _dragged
                QTimer.singleShot(0, lambda: self.board.Move(source, self.player))
            else:
                event.ignore()
            return True
        return False


class PlayerDragBoard(QObject):
    """The player widgets that can be dragged between each other.

    groups returns the current lists of player widgets (a list each team,
    for example). swap(a, b) swaps two players' data. Player widgets are
    added with Register when they're made."""

    moved = Signal()

    def __init__(self, groups, swap, parent=None):
        super().__init__(parent)
        self.groups = groups
        self.swap = swap

    def Register(self, player):
        """Adds the grip to the player's header and takes drops on it."""
        grip = _Grip(player, self)
        header = player.findChild(QHBoxLayout, "titleContainer")
        if header is not None:
            header.insertWidget(0, grip)
        player.dragGrip = grip
        player.dropTarget = _DropTarget(player, self)
        return grip

    def Find(self, player):
        """(group index, index in the group) of a player, or None."""
        for g, group in enumerate(self.groups()):
            for i, widget in enumerate(group):
                if widget is player:
                    return g, i
        return None

    def CanDrop(self, source, target):
        return (
            source is not None
            and source is not target
            and self.Find(source) is not None
            and self.Find(target) is not None
        )

    def StartDrag(self, player, grip):
        global _dragged
        _dragged = player
        try:
            drag = QDrag(grip)
            data = QMimeData()
            data.setData(MIME_TYPE, QByteArray())
            drag.setMimeData(data)

            # A smaller picture of the player follows the cursor
            picture = player.grab()
            if not picture.isNull():
                width = min(picture.width(), 320)
                picture = picture.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
                faded = QPixmap(picture.size())
                faded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(faded)
                painter.setOpacity(0.75)
                painter.drawPixmap(0, 0, picture)
                painter.end()
                drag.setPixmap(faded)
                drag.setHotSpot(QPoint(12, 12))

            grip.setCursor(Qt.CursorShape.ClosedHandCursor)
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            grip.setCursor(Qt.CursorShape.OpenHandCursor)
            _dragged = None

    def Pairs(self, source, target):
        """The swaps, in order, that move source to target's place."""
        sourceAt, targetAt = self.Find(source), self.Find(target)
        if sourceAt is None or targetAt is None or source is target:
            return []
        if sourceAt[0] != targetAt[0]:
            return [(source, target)]
        group = self.groups()[sourceAt[0]]
        i, j = sourceAt[1], targetAt[1]
        step = 1 if j > i else -1
        # The player moves one place at a time, pushing the others back
        return [(group[k], group[k + step]) for k in range(i, j, step)]

    def Move(self, source, target):
        pairs = self.Pairs(source, target)
        if not pairs:
            return
        affected = list(dict.fromkeys(w for pair in pairs for w in pair))
        ids = {w: StateManager.Get(f"{w.path}.id") for w in affected}
        StateManager.BlockSaving()
        try:
            for a, b in pairs:
                self.swap(a, b)
        finally:
            StateManager.ReleaseSaving()
        # Once at the end: each starts requests for the player's stats
        for w in affected:
            if hasattr(w, "EmitPlayerIdChanged") and StateManager.Get(f"{w.path}.id") != ids[w]:
                w.EmitPlayerIdChanged()
        self.moved.emit()
