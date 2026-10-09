# The popup a ColorButton opens: groups of named swatches given by the
# button's owner (like the loaded game's colors), the user's saved custom
# colors, a hex field and the full color dialog for anything else.
# QColorDialog can't show named swatches or say which one was picked, and
# its custom colors are a single list of 16 shared by every dialog.

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .SettingsManager import SettingsManager

CUSTOM_COLORS_KEY = "color_picker.custom_colors"
CUSTOM_COLORS_MAX = 24
COLUMNS = 8
SWATCH_SIZE = 24


class Swatch:
    """A color in a group. data is handed back when the swatch is picked."""

    def __init__(self, color, name="", data=None, tooltip=""):
        self.color = QColor(color)
        self.name = name
        self.data = data
        self.tooltip = tooltip


def CustomColors() -> list[str]:
    colors = SettingsManager.Get(CUSTOM_COLORS_KEY, [])
    if not isinstance(colors, list):
        return []
    return [c for c in colors if isinstance(c, str) and QColor(c).isValid()]


def SaveCustomColors(colors):
    SettingsManager.Set(CUSTOM_COLORS_KEY, list(dict.fromkeys(colors))[:CUSTOM_COLORS_MAX])


def ColorName(color: QColor, alpha=False):
    if alpha and color.alpha() < 255:
        return color.name(QColor.NameFormat.HexArgb)
    return color.name(QColor.NameFormat.HexRgb)


def GameColorSwatchGroups():
    """The loaded game's preset colors, for the team color pickers. A
    swatch's data is its row in the asset manager's color model."""
    # Imported here: the picker itself doesn't need the game's assets
    from .GameAssetManager import GameAssetManager

    model = GameAssetManager.instance.colorModel
    swatches = []
    for row in range(1, model.rowCount()):
        data = model.item(row).data(Qt.ItemDataRole.UserRole) or {}
        if not data.get("value"):
            continue
        tooltip = ""
        if data.get("force_opponent"):
            tooltip = QApplication.translate("app", "Also sets the other team to {0}").format(
                "#" + data["force_opponent"]
            )
        swatches.append(Swatch("#" + data["value"], data.get("display_name") or "", row, tooltip))
    game = GameAssetManager.instance.selectedGame.get("name")
    title = QApplication.translate("app", "Game colors")
    return [(f"{title} ({game})" if game else title, swatches)]


def GameColorValues(row, force_opponent=False):
    """The color of a game color swatch (its row in the color model), or the
    color it sets the other team to; None if it doesn't set one."""
    from .GameAssetManager import GameAssetManager

    model = GameAssetManager.instance.colorModel
    item = model.item(row) if 0 < row < model.rowCount() else None
    data = (item.data(Qt.ItemDataRole.UserRole) if item else None) or {}
    value = data.get("force_opponent" if force_opponent else "value")
    return "#" + value if value else None


class SwatchButton(QToolButton):
    def __init__(self, color: QColor, selected=False, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.selected = selected
        self.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        palette = self.palette()
        if self.color.alpha() < 255:
            # A checkerboard behind see-through colors
            painter.save()
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            painter.setClipPath(path)
            cell = 5
            for y in range(int(rect.top()), int(rect.bottom()) + 1, cell):
                for x in range(int(rect.left()), int(rect.right()) + 1, cell):
                    dark = ((x - int(rect.left())) // cell + (y - int(rect.top())) // cell) % 2
                    painter.fillRect(x, y, cell, cell, QColor("#bbbbbb" if dark else "#ffffff"))
            painter.restore()
        painter.setBrush(self.color)
        border = palette.color(QPalette.ColorRole.Text)
        border.setAlphaF(0.25)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 4, 4)
        if self.selected or self.underMouse():
            highlight = palette.color(QPalette.ColorRole.Highlight)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(highlight if self.selected else border, 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)
        painter.end()


class ColorPicker(QFrame):
    """The popup. picked(color name, data) is emitted with the swatch's data,
    or None for a custom, typed or dialog color."""

    picked = Signal(str, object)

    def __init__(self, current=None, groups=None, alpha=False, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.current = QColor(current) if current else QColor()
        self.alpha = alpha

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        for title, swatches in groups or []:
            if not swatches:
                continue
            layout.addWidget(self.Title(title))
            grid = self.Grid()
            for i, swatch in enumerate(swatches):
                button = self.Swatch(swatch.color)
                tooltip = swatch.name
                if swatch.tooltip:
                    tooltip = f"{tooltip}\n{swatch.tooltip}" if tooltip else swatch.tooltip
                button.setToolTip(tooltip or ColorName(swatch.color, self.alpha))
                button.clicked.connect(lambda _=False, s=swatch: self.Pick(s.color, s.data))
                grid.addWidget(button, i // COLUMNS, i % COLUMNS)
            layout.addLayout(grid)

        layout.addWidget(self.Title(QApplication.translate("app", "Custom colors")))
        self.customGrid = self.Grid()
        layout.addLayout(self.customGrid)
        self.FillCustomColors()

        row = QHBoxLayout()
        row.setSpacing(6)
        self.hex = QLineEdit(ColorName(self.current, self.alpha) if self.current.isValid() else "")
        self.hex.setPlaceholderText("#rrggbb")
        self.hex.setMaximumWidth(110)
        self.hex.returnPressed.connect(self.PickTyped)
        row.addWidget(self.hex)
        more = QPushButton(QApplication.translate("app", "More colors..."))
        more.clicked.connect(self.OpenDialog)
        row.addWidget(more)
        row.addStretch()
        layout.addLayout(row)

    def Title(self, text):
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def Grid(self):
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return grid

    def Swatch(self, color):
        same = self.current.isValid() and QColor(color).rgba() == self.current.rgba()
        return SwatchButton(color, same, self)

    def FillCustomColors(self):
        while self.customGrid.count():
            self.customGrid.takeAt(0).widget().deleteLater()
        colors = CustomColors()
        for i, name in enumerate(colors):
            button = self.Swatch(QColor(name))
            button.setToolTip(name + "\n" + QApplication.translate("app", "Right-click to remove"))
            button.clicked.connect(lambda _=False, c=name: self.Pick(QColor(c), None))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda _pos, c=name: self.RemoveCustomColor(c)
            )
            self.customGrid.addWidget(button, i // COLUMNS, i % COLUMNS)
        if len(colors) < CUSTOM_COLORS_MAX:
            add = QToolButton(self)
            add.setText("+")
            add.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
            add.setToolTip(QApplication.translate("app", "Save the current color"))
            add.setEnabled(self.current.isValid())
            add.clicked.connect(self.AddCustomColor)
            n = len(colors)
            self.customGrid.addWidget(add, n // COLUMNS, n % COLUMNS)

    def AddCustomColor(self):
        if self.current.isValid():
            SaveCustomColors(CustomColors() + [ColorName(self.current, self.alpha)])
            self.FillCustomColors()

    def RemoveCustomColor(self, name):
        SaveCustomColors([c for c in CustomColors() if c != name])
        self.FillCustomColors()

    def PickTyped(self):
        text = self.hex.text().strip()
        if text and not text.startswith("#"):
            text = "#" + text
        color = QColor(text)
        if color.isValid():
            self.Pick(color, None)
        else:
            self.hex.selectAll()

    def OpenDialog(self):
        # Closed first: a popup would close itself when the dialog opens,
        # taking the dialog's result with it
        current, alpha, picked = QColor(self.current), self.alpha, self.picked
        parent = self.parentWidget()
        self.hide()
        dialog = QColorDialog(parent)
        if alpha:
            dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if current.isValid():
            dialog.setCurrentColor(current)
        if dialog.exec():
            picked.emit(ColorName(dialog.currentColor(), alpha), None)
        self.close()

    def Pick(self, color, data):
        self.picked.emit(ColorName(QColor(color), self.alpha), data)
        self.close()

    def Show(self, anchor: QWidget):
        self.adjustSize()
        position = anchor.mapToGlobal(QPoint(0, anchor.height()))
        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if position.y() + self.height() > area.bottom():
                position.setY(anchor.mapToGlobal(QPoint(0, 0)).y() - self.height())
            position.setX(max(area.left(), min(position.x(), area.right() - self.width())))
        self.move(position)
        self.show()
        self.hex.setFocus()
