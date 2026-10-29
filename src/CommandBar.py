# The bar at the top of the main window. It holds what applies to every
# widget: the tournament and game that are loaded, whether completed sets are
# being pulled, and the window's own controls (workspaces, widgets, the menu).
# The look is in Theme.StyleSheet, under #commandBar.
import base64
import json

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

# Under this width, labels the bar can do without are dropped so it stays
# one row
COMPACT_WIDTH = 1100

STATUS_OK = "ok"
STATUS_BUSY = "busy"
STATUS_OFF = "off"


def _Repolish(widget):
    # Style sheet rules on a dynamic property only apply once the widget is
    # polished again
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _Elided(label, text, width):
    return label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)


class _LayoutButton(QToolButton):
    """A tool button that lays out its own labels: its size comes from them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.box = QHBoxLayout(self)
        self.box.setSpacing(8)

    def AddLabel(self, label):
        # Clicks go through to the button
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.box.addWidget(label)
        return label

    def sizeHint(self):
        return self.box.sizeHint()

    def minimumSizeHint(self):
        return self.box.minimumSize()


class ContextChip(_LayoutButton):
    """Shows something that's loaded, as a caption over a title, and opens
    its actions. As a primary button it's the one thing to do first."""

    TITLE_WIDTH = 360
    TITLE_WIDTH_COMPACT = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contextChip")
        self.box.setContentsMargins(8, 4, 10, 4)

        self.iconLabel = self.AddLabel(QLabel())
        self.iconLabel.setFixedSize(20, 20)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.captionLabel = QLabel()
        self.captionLabel.setObjectName("chipCaption")
        self.captionLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = self.captionLabel.font()
        font.setPointSizeF(font.pointSizeF() * 0.85)
        self.captionLabel.setFont(font)
        text.addWidget(self.captionLabel)
        self.titleLabel = QLabel()
        self.titleLabel.setObjectName("chipTitle")
        self.titleLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = self.titleLabel.font()
        font.setBold(True)
        self.titleLabel.setFont(font)
        text.addWidget(self.titleLabel)
        self.box.addLayout(text)

        self.chevron = self.AddLabel(QLabel("▾"))
        self.chevron.setObjectName("chipCaption")

        self.icon_ = QIcon()
        self.title = ""
        self.compact = False

    def SetIcon(self, icon):
        self.icon_ = icon
        self.iconLabel.setVisible(not icon.isNull())
        self.iconLabel.setPixmap(icon.pixmap(20, 20))

    def SetCaption(self, caption):
        self.captionLabel.setText(caption)
        self.captionLabel.setVisible(bool(caption) and not self.compact)

    def SetTitle(self, title):
        self.title = title
        width = self.TITLE_WIDTH_COMPACT if self.compact else self.TITLE_WIDTH
        self.titleLabel.setText(_Elided(self.titleLabel, title, width))
        self.setToolTip(title if self.titleLabel.text() != title else "")
        self.updateGeometry()

    def SetPrimary(self, primary):
        """A primary chip is a plain button: it has no menu."""
        self.setProperty("primary", primary)
        self.chevron.setVisible(not primary)
        _Repolish(self)
        for label in (self.captionLabel, self.titleLabel, self.chevron):
            _Repolish(label)

    def SetCompact(self, compact):
        self.compact = compact
        self.SetCaption(self.captionLabel.text())
        self.SetTitle(self.title)

    def changeEvent(self, event):
        # The icon is a pixmap: draw it again in the new theme's colors
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.iconLabel.setPixmap(self.icon_.pixmap(20, 20))
        super().changeEvent(event)


class StatusPill(_LayoutButton):
    """A status light, a name and what it's doing now, e.g. completed sets
    and when they're pulled next."""

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.box.setContentsMargins(12, 6, 12, 6)

        self.dot = self.AddLabel(QLabel())
        self.dot.setObjectName("statusDot")
        self.dot.setFixedSize(8, 8)
        self.nameLabel = self.AddLabel(QLabel(name))
        font = self.nameLabel.font()
        font.setBold(True)
        self.nameLabel.setFont(font)
        self.detailLabel = self.AddLabel(QLabel())
        self.detailLabel.setObjectName("chipCaption")

    def SetStatus(self, status, detail):
        if self.dot.property("status") != status:
            self.dot.setProperty("status", status)
            _Repolish(self.dot)
        self.detailLabel.setText(detail)
        self.updateGeometry()

    def SetCompact(self, compact):
        self.nameLabel.setVisible(not compact)


class BarButton(QToolButton):
    """A flat button of the bar, an icon with an optional label."""

    def __init__(self, icon, tooltip, parent=None):
        super().__init__(parent)
        self.setObjectName("barButton")
        self.setIcon(icon)
        self.setIconSize(QSize(18, 18))
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.compact = False

    def SetLabel(self, text):
        """Text next to the icon, dropped when the bar is compact (the
        tooltip still has it)"""
        self.setText(text)
        self._UpdateStyle()

    def SetCompact(self, compact):
        self.compact = compact
        self._UpdateStyle()

    def _UpdateStyle(self):
        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if self.text() and not self.compact
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )


class ActivityStrip(QWidget):
    """A thin line along the bottom of the bar, with a stretch of the accent
    color sweeping across it while something is loading in the background
    (a tournament, its entrants, completed sets). Hidden otherwise."""

    HEIGHT = 2
    SWEEP_MS = 1400
    # The sweeping stretch, as a share of the bar's width
    SEGMENT = 0.3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedHeight(self.HEIGHT)
        # How many of each activity are running
        self.running = {}
        self.position = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(self.SWEEP_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setLoopCount(-1)
        self.animation.valueChanged.connect(self._Moved)
        self.hide()

    def Start(self, activity):
        self.running[activity] = self.running.get(activity, 0) + 1
        self._Update()

    def Finish(self, activity):
        count = self.running.get(activity, 0) - 1
        if count > 0:
            self.running[activity] = count
        else:
            self.running.pop(activity, None)
        self._Update()

    def _Update(self):
        busy = bool(self.running)
        if busy and not self.isVisible():
            self.show()
            self.raise_()
            self.animation.start()
        elif not busy and self.isVisible():
            self.animation.stop()
            self.hide()

    def _Moved(self, value):
        self.position = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        accent = self.palette().color(QPalette.ColorRole.Highlight)
        track = QColor(accent)
        track.setAlphaF(0.2)
        painter.fillRect(self.rect(), track)
        segment = self.width() * self.SEGMENT
        x = -segment + self.position * (self.width() + segment)
        painter.fillRect(QRectF(x, 0, segment, self.height()), accent)


class CommandBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("commandBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.box = QHBoxLayout(self)
        self.box.setContentsMargins(10, 6, 10, 6)
        self.box.setSpacing(6)
        self.compact = None
        # Over the bar's bottom edge, outside its layout so it doesn't make
        # the bar taller
        self.activity = ActivityStrip(self)

    def AddWidget(self, widget):
        self.box.addWidget(widget)
        return widget

    def AddLayout(self, layout):
        self.box.addLayout(layout)
        return layout

    def AddStretch(self):
        self.box.addStretch(1)

    def AddSeparator(self):
        line = QFrame()
        line.setObjectName("barSeparator")
        line.setFixedSize(1, 26)
        self.box.addWidget(line)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.activity.setGeometry(
            0, self.height() - ActivityStrip.HEIGHT, self.width(), ActivityStrip.HEIGHT
        )
        compact = self.width() < COMPACT_WIDTH
        if compact != self.compact:
            self.compact = compact
            for widget in self.findChildren(QWidget):
                if hasattr(widget, "SetCompact"):
                    widget.SetCompact(compact)


class Workspaces(QObject):
    """Named arrangements of the widgets, saved and restored with the main
    window's saveState and restoreState."""

    changed = Signal()

    def __init__(self, window, qtSettings):
        super().__init__(window)
        self.window = window
        self.qtSettings = qtSettings
        self.default = None

    def SetDefault(self, state):
        # How the widgets are arranged before any saved arrangement is
        # restored, for Reset
        self.default = state

    def Saved(self):
        try:
            return json.loads(self.qtSettings.value("workspaces", "{}") or "{}")
        except (TypeError, ValueError):
            return {}

    def Current(self):
        name = self.qtSettings.value("workspace", "") or ""
        return name if name in self.Saved() else ""

    def _SetCurrent(self, name):
        self.qtSettings.setValue("workspace", name)
        self.changed.emit()

    def Load(self, name):
        state = self.Saved().get(name)
        if state is None:
            return
        self.window.restoreState(QByteArray(base64.b64decode(state)))
        self._SetCurrent(name)

    def Save(self, name):
        saved = self.Saved()
        saved[name] = base64.b64encode(bytes(self.window.saveState())).decode()
        self.qtSettings.setValue("workspaces", json.dumps(saved))
        self._SetCurrent(name)

    def Delete(self, name):
        saved = self.Saved()
        saved.pop(name, None)
        self.qtSettings.setValue("workspaces", json.dumps(saved))
        self.changed.emit()

    def Reset(self):
        if self.default is not None:
            self.window.restoreState(self.default)
        self._SetCurrent("")

    def AskSave(self):
        name, ok = QInputDialog.getText(
            self.window,
            QApplication.translate("app", "Save workspace"),
            QApplication.translate("app", "Name of this arrangement of the widgets:"),
            text=self.Current(),
        )
        name = name.strip()
        if ok and name:
            self.Save(name)

    def FillMenu(self, menu):
        """The menu of the bar's workspace button, built when it opens"""
        menu.clear()
        saved = self.Saved()
        current = self.Current()
        for name in sorted(saved, key=str.lower):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(lambda checked=False, n=name: self.Load(n))
        if saved:
            menu.addSeparator()
        action = menu.addAction(QApplication.translate("app", "Save current arrangement..."))
        action.triggered.connect(self.AskSave)
        if saved:
            deleteMenu = menu.addMenu(QApplication.translate("app", "Delete workspace"))
            for name in sorted(saved, key=str.lower):
                action = deleteMenu.addAction(name)
                action.triggered.connect(lambda checked=False, n=name: self.Delete(n))
        action = menu.addAction(QApplication.translate("app", "Reset to default arrangement"))
        action.triggered.connect(self.Reset)
