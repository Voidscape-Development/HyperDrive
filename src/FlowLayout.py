from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *


class FlowLayout(QLayout):
    """Lays its items out in rows, wrapping to the next row when the width
    runs out (the layout from the Qt examples)."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self.items = []
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def addGroup(self, *widgets):
        """Adds widgets that wrap together, like a label and its field."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing())
        for widget in widgets:
            layout.addWidget(widget)
        self.addWidget(group)
        return group

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._Do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._Do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _Do(self, rect, testOnly):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, lineHeight = area.x(), area.y(), 0
        spacing = self.spacing()
        for item in self.items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and lineHeight > 0:
                x = area.x()
                y += lineHeight + spacing
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + spacing
            lineHeight = max(lineHeight, hint.height())
        return y + lineHeight - rect.y() + margins.bottom()
