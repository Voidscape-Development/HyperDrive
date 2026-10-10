from qtpy.QtCore import *
from qtpy.QtWidgets import *


class CompleterProxyModel(QSortFilterProxyModel):
    def __init__(self, completer, parent=None):
        super().__init__(parent)
        self._completer = completer

    _SEARCH_KEYS = {"gamerTag", "prefix", "name", "twitter"}

    def filterAcceptsRow(self, sourceRow, sourceParent):
        index0 = self.sourceModel().index(sourceRow, 0, sourceParent)
        prefix = self._completer.local_completion_prefix.lower()
        data = self.sourceModel().data(index0, Qt.ItemDataRole.UserRole)

        if data:
            for k in self._SEARCH_KEYS:
                v = data.get(k)
                if isinstance(v, str) and prefix in v.lower():
                    return True
            return False

        display = self.sourceModel().data(index0)
        return isinstance(display, str) and prefix in display.lower()


class _PopupScreenClamp(QObject):
    """Moves the popup back inside the screen when it's shown, as QCompleter
    places it for the width of the field, not the popup's own"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            screen = obj.screen().availableGeometry()
            geometry = obj.geometry()
            if geometry.right() > screen.right():
                obj.move(max(screen.left(), screen.right() - geometry.width() + 1), geometry.y())
        return False


class CustomPlayerCompleter(QCompleter):
    # Rows measured to size the popup; enough for what it can scroll through
    _MEASURED_ROWS = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.local_completion_prefix = ""
        self.source_model = None
        self._proxy_model = CompleterProxyModel(self)
        self._screen_clamp = _PopupScreenClamp(self)
        self.popup().installEventFilter(self._screen_clamp)

    def setModel(self, model):
        self.source_model = model
        self._proxy_model.setSourceModel(model)
        super().setModel(self._proxy_model)

    def splitPath(self, path):
        self.local_completion_prefix = path
        self._proxy_model.invalidateFilter()
        self._FitPopupToNames()
        return [""]

    def _FitPopupToNames(self):
        # QCompleter makes the popup as wide as the field, cutting long names
        # off in narrow fields. A minimum width lets it grow to fit them.
        popup = self.popup()
        metrics = popup.fontMetrics()
        text_width = 0
        for row in range(min(self._proxy_model.rowCount(), self._MEASURED_ROWS)):
            text = self._proxy_model.index(row, 0).data()
            if isinstance(text, str):
                text_width = max(text_width, metrics.horizontalAdvance(text))

        icon_width = popup.iconSize().width()
        if icon_width <= 0:
            icon_width = popup.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)

        # Icon, the spacing around it and the text, the scrollbar and the frame
        width = (
            text_width
            + icon_width
            + 24
            + popup.verticalScrollBar().sizeHint().width()
            + 2 * popup.frameWidth()
        )

        widget = self.widget()
        if widget is not None and widget.screen() is not None:
            width = min(width, widget.screen().availableGeometry().width())

        popup.setMinimumWidth(width)
