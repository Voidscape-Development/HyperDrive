# The pieces settings pages are built from, shared by the settings window and
# the layout themes window: a page with a title, cards grouping rows, and rows
# with a label, a description under it, a control, and a dot and reset button
# shown once the value differs from its default. Their look is in
# Theme.StyleSheet (the settings* object names).
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..Theme import Blend, Theme, ThemedIcon

# How long a row found with the search stays highlighted
HIGHLIGHT_MS = 1600


def RetainSizeWhenHidden(widget):
    policy = widget.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    widget.setSizePolicy(policy)


class ToggleSwitch(QAbstractButton):
    """An on/off switch, for settings that take effect as they're flipped"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Clicking shouldn't leave a focus ring, tabbing to it should
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(36, 20)

    def paintEvent(self, event):
        c = Theme.Colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()

        track = c["accent"] if on else c["border"]
        knob = c["onAccent"] if on else c["muted"]
        if not self.isEnabled():
            track = Blend(track, c["window"], 0.72)
            knob = Blend(knob, c["window"], 0.5)
        if self.hasFocus():
            painter.setPen(QPen(c["accentText"], 1.5))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)

        size = rect.height() - 4
        x = rect.right() - 2 - size if on else rect.left() + 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(x, rect.top() + 2, size, size))


class ResetButton(QToolButton):
    """Puts a value back to its default. Rows show it only while the value
    differs from the default."""

    def __init__(self, tooltip=None, parent=None):
        super().__init__(parent)
        self.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.setIconSize(QSize(14, 14))
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip(tooltip or QApplication.translate("settings", "Reset to default"))
        RetainSizeWhenHidden(self)


class ChangedDot(QWidget):
    """The accent dot before the label of a value that isn't the default"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(6, 6)
        self.setToolTip(QApplication.translate("settings", "Changed from the default"))
        RetainSizeWhenHidden(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Theme.Colors()["accent"])
        painter.drawEllipse(QRectF(self.rect()))


def Badge(text):
    badge = QLabel(text)
    badge.setObjectName("settingsBadge")
    font = badge.font()
    font.setPointSizeF(font.pointSizeF() * 0.82)
    font.setBold(True)
    badge.setFont(font)
    return badge


def RestartBadge():
    badge = Badge(QApplication.translate("settings", "Restart"))
    badge.setToolTip(QApplication.translate("settings", "Takes effect after HyperDrive restarts"))
    return badge


def Description(text):
    label = QLabel(text)
    label.setObjectName("settingsDescription")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class SettingRow(QWidget):
    """One setting: its label and description on the left, its control on
    the right, then a reset button that shows while the value isn't the
    default. reset=False leaves the reset button out."""

    resetClicked = Signal()

    def __init__(
        self,
        title,
        control=None,
        description=None,
        restart=False,
        indent=False,
        reset=True,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("settingRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.title = title
        self.descriptionText = description or ""
        # Words the search finds this row by, besides its title and description
        self.keywords = ""
        self.control = control

        layout = QHBoxLayout(self)
        layout.setContentsMargins(36 if indent else 12, 9, 8, 9)
        layout.setSpacing(8)

        self.dot = ChangedDot()
        self.dot.hide()
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(2)
        titleLine = QHBoxLayout()
        titleLine.setSpacing(6)
        self.label = QLabel(title)
        self.label.setWordWrap(True)
        font = self.label.font()
        font.setWeight(QFont.Weight.Medium)
        self.label.setFont(font)
        titleLine.addWidget(self.label)
        if restart:
            titleLine.addWidget(RestartBadge(), 0, Qt.AlignmentFlag.AlignVCenter)
        titleLine.addStretch(1)
        text.addLayout(titleLine)
        self.titleLine = titleLine
        self.description = None
        if description:
            self.description = Description(description)
            text.addWidget(self.description)
        layout.addLayout(text, 1)

        if control is not None:
            if control.accessibleName() == "":
                control.setAccessibleName(title)
            if description and control.accessibleDescription() == "":
                control.setAccessibleDescription(description)
            self.label.setBuddy(control)
            layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

        self.resetButton = None
        if reset:
            self.resetButton = ResetButton(
                QApplication.translate("settings", 'Reset "{0}" to default').format(title)
            )
            self.resetButton.hide()
            self.resetButton.clicked.connect(self.resetClicked)
            layout.addWidget(self.resetButton, 0, Qt.AlignmentFlag.AlignVCenter)

    def SetChanged(self, changed):
        self.dot.setVisible(changed)
        if self.resetButton is not None:
            self.resetButton.setVisible(changed)

    def SearchText(self):
        return " ".join((self.title, self.descriptionText, self.keywords)).lower()

    def Highlight(self):
        self.setProperty("highlight", True)
        self.style().polish(self)
        QTimer.singleShot(HIGHLIGHT_MS, self.Unhighlight)

    def Unhighlight(self):
        self.setProperty("highlight", False)
        self.style().polish(self)


class SettingsGroup(QFrame):
    """A card of rows under a title, with a line between rows"""

    def __init__(self, title=None, description=None, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsGroup")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(0)
        self.items = 0
        if title:
            header = QHBoxLayout()
            header.setContentsMargins(12, 8, 12, 2)
            header.setSpacing(8)
            self.titleLabel = QLabel(title)
            self.titleLabel.setObjectName("settingsGroupTitle")
            font = self.titleLabel.font()
            font.setBold(True)
            self.titleLabel.setFont(font)
            header.addWidget(self.titleLabel)
            if description:
                header.addWidget(Description(description), 1)
            else:
                header.addStretch()
            self.header = header
            self.layout.addLayout(header)

    def AddRow(self, row):
        self.AddWidget(row)
        return row

    def AddWidget(self, widget):
        if self.items:
            line = QFrame()
            line.setObjectName("settingsSeparator")
            line.setFixedHeight(1)
            self.layout.addWidget(line)
        self.layout.addWidget(widget)
        self.items += 1
        return widget


class SettingsPage(QScrollArea):
    """A scrolling page: a title, a line about it, then groups"""

    def __init__(self, title=None, description=None, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.title = title or ""
        self.descriptionText = description or ""

        inner = QWidget()
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(24, 18, 24, 18)
        self.body.setSpacing(12)
        if title:
            heading = QLabel(title)
            heading.setObjectName("settingsPageTitle")
            font = heading.font()
            font.setPointSizeF(font.pointSizeF() * 1.4)
            font.setBold(True)
            heading.setFont(font)
            header = QVBoxLayout()
            header.setSpacing(3)
            header.addWidget(heading)
            if description:
                header.addWidget(Description(description))
            self.body.addLayout(header)
        self.setWidget(inner)
        self.finished = False

    def AddGroup(self, title=None, description=None):
        return self.AddWidget(SettingsGroup(title, description))

    def AddWidget(self, widget, stretch=0):
        self.body.addWidget(widget, stretch)
        return widget

    def AddLayout(self, layout, stretch=0):
        self.body.addLayout(layout, stretch)
        return layout

    def Finish(self):
        """Keeps the groups at the top of a tall window"""
        if not self.finished:
            self.body.addStretch()
            self.finished = True
        return self

    def Rows(self):
        return self.widget().findChildren(SettingRow)

    def ShowRow(self, row):
        self.ensureWidgetVisible(row, 0, 48)
        row.Highlight()


class Banner(QFrame):
    """A message across the top of a page, with buttons on its right.
    kind is "info" (blue) or "accent" (the theme's accent)."""

    def __init__(self, title, text=None, icon=None, kind="info", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsBanner")
        self.setProperty("kind", kind)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(12)
        if icon:
            iconLabel = QLabel()
            iconLabel.setPixmap(ThemedIcon(icon).pixmap(18, 18))
            layout.addWidget(iconLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        text_ = QVBoxLayout()
        text_.setSpacing(2)
        self.titleLabel = QLabel(title)
        self.titleLabel.setWordWrap(True)
        font = self.titleLabel.font()
        font.setBold(True)
        self.titleLabel.setFont(font)
        text_.addWidget(self.titleLabel)
        self.textLabel = Description(text or "")
        self.textLabel.setVisible(bool(text))
        text_.addWidget(self.textLabel)
        layout.addLayout(text_, 1)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(6)
        layout.addLayout(self.buttons)

    def SetText(self, title, text=None):
        self.titleLabel.setText(title)
        self.textLabel.setText(text or "")
        self.textLabel.setVisible(bool(text))

    def AddButton(self, text, primary=False):
        button = QPushButton(text)
        button.setAutoDefault(False)
        if primary:
            button.setObjectName("primaryButton")
        self.buttons.addWidget(button)
        return button


class ThemeCard(QAbstractButton):
    """A theme to pick from a gallery: a picture of it, its name and a line
    under the name. draw(painter, rect) paints the picture. layout is
    "grid" (picture over the name) or "list" (a small picture beside it)."""

    def __init__(self, name, draw, subtitle="", layout="grid", parent=None):
        super().__init__(parent)
        self.draw = draw
        self.subtitle = subtitle
        self.layout_ = layout
        self.setText(name)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip(name)
        self.setAccessibleName(name)
        if layout == "grid":
            self.setFixedSize(124, 100)
        else:
            self.setMinimumHeight(46)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def SetSubtitle(self, subtitle):
        self.subtitle = subtitle
        self.update()

    def sizeHint(self):
        return QSize(124, 100) if self.layout_ == "grid" else QSize(200, 46)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        c = Theme.Colors()
        r = Theme.Radius()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        hover = self.underMouse()
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        if self.layout_ == "grid":
            picture = QRectF(rect.left() + 1, rect.top() + 1, rect.width() - 2, 66)
            textRect = QRectF(rect.left(), picture.bottom() + 6, rect.width(), 20)
        else:
            if on or hover:
                painter.setPen(QPen(c["accent"] if on else c["border"], 1))
                painter.setBrush(c["raised"] if on else c["raisedHover"])
                painter.drawRoundedRect(rect, r + 2, r + 2)
            picture = QRectF(rect.left() + 8, rect.center().y() - 15, 44, 30)
            textRect = QRectF(
                picture.right() + 10,
                rect.top() + 4,
                rect.right() - picture.right() - 14,
                rect.height() - 8,
            )

        path = QPainterPath()
        path.addRoundedRect(picture, 6, 6)
        painter.save()
        painter.setClipPath(path)
        self.draw(painter, picture)
        painter.restore()
        if self.layout_ == "grid" and (on or hover):
            painter.setPen(QPen(c["accent"] if on else c["muted"], 2 if on else 1))
        else:
            painter.setPen(QPen(c["border"], 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        if self.hasFocus():
            painter.setPen(QPen(c["accentText"], 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect, r + 2, r + 2)

        font = self.font()
        font.setWeight(QFont.Weight.DemiBold if on else QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(c["text"])
        metrics = QFontMetrics(font)
        if self.layout_ == "grid":
            name = metrics.elidedText(
                self.text(), Qt.TextElideMode.ElideRight, int(textRect.width())
            )
            painter.drawText(
                textRect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name
            )
            return
        name = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, int(textRect.width()))
        if self.subtitle:
            top = QRectF(textRect.left(), textRect.top(), textRect.width(), textRect.height() / 2)
            painter.drawText(top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, name)
            small = self.font()
            small.setPointSizeF(small.pointSizeF() * 0.88)
            painter.setFont(small)
            painter.setPen(c["accentText"] if on else c["muted"])
            bottom = QRectF(
                textRect.left(), top.bottom() + 1, textRect.width(), textRect.height() / 2
            )
            subtitle = QFontMetrics(small).elidedText(
                self.subtitle, Qt.TextElideMode.ElideRight, int(textRect.width())
            )
            painter.drawText(
                bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, subtitle
            )
        else:
            painter.drawText(
                textRect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name
            )


def NoDefaultButtons(widget):
    """A dialog makes its push buttons default buttons, so Enter in any field
    clicked the first one (in the settings, a reset button). Turns that off
    for every push button in the widget."""
    for button in widget.findChildren(QPushButton):
        button.setAutoDefault(False)
        button.setDefault(False)
