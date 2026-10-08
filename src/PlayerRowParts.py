from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameAssetManager import GameAssetManager
from .PlayerDB import PlayerDB
from .Theme import Theme, ThemedIcon

# Drag and drop of player rows and of the characters inside a row
PLAYER_MIME = "application/x-hyperdrive-player"
CHARACTER_MIME = "application/x-hyperdrive-character"


def SetRole(widget, role, **properties):
    """Styles a widget with the theme's hdRole rules (see Theme.StyleSheet)."""
    widget.setProperty("hdRole", role)
    for key, value in properties.items():
        widget.setProperty(key, value)
    return widget


def SetStyleProperty(widget, key, value):
    """Changes a property the stylesheet reads, and restyles the widget."""
    if widget.property(key) == value:
        return
    widget.setProperty(key, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def EyebrowLabel(text, parent=None, objectName=None):
    """A small uppercase field label."""
    label = QLabel(text.upper(), parent)
    SetRole(label, "eyebrow")
    font = QFont(label.font())
    font.setPointSizeF(max(7.0, font.pointSizeF() * 0.78))
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
    label.setFont(font)
    if objectName:
        label.setObjectName(objectName)
    return label


def SmallFont(widget, factor=0.85, bold=False):
    font = QFont(widget.font())
    font.setPointSizeF(max(7.0, font.pointSizeF() * factor))
    font.setBold(bold)
    widget.setFont(font)
    return widget


def IconButton(icon, tooltip, role="ghost", size=28):
    button = QToolButton()
    button.setIcon(ThemedIcon(icon))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFixedSize(size, size)
    button.setIconSize(QSize(size - 12, size - 12))
    SetRole(button, role)
    return button


class StatusDot(QWidget):
    """The player database status of a player: saved, saving, or not in it."""

    SAVED = "saved"
    SAVING = "saving"
    NEW = "new"
    EMPTY = "empty"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = StatusDot.EMPTY
        self.setFixedSize(12, 12)
        self.blink = False
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._Blink)

    def SetState(self, state, tooltip=""):
        self.state = state
        self.setToolTip(tooltip)
        if state == StatusDot.SAVING:
            self.timer.start()
        else:
            self.timer.stop()
            self.blink = False
        self.update()

    def _Blink(self):
        self.blink = not self.blink
        self.update()

    def paintEvent(self, event):
        if self.state == StatusDot.EMPTY:
            return
        colors = Theme.Colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2, 2, 8, 8)
        if self.state == StatusDot.NEW:
            painter.setPen(QPen(colors["muted"], 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            color = QColor("#4cc283") if self.state == StatusDot.SAVED else QColor("#6aa2ff")
            if self.blink:
                color.setAlphaF(0.3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
        painter.drawEllipse(rect)


class DragGrip(QLabel):
    """The handle a player row is dragged by. Right click moves it one place."""

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.pressPos = None
        self.setPixmap(ThemedIcon("assets/icons/grip.svg").pixmap(QSize(14, 14)))
        self.setFixedWidth(16)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(QApplication.translate("app", "Drag to reorder"))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.ShowMenu)

    def ShowMenu(self, pos):
        menu = QMenu(self)
        menu.addAction(QApplication.translate("app", "Move up"), self.row.btMoveUp.click)
        menu.addAction(QApplication.translate("app", "Move down"), self.row.btMoveDown.click)
        menu.exec(self.mapToGlobal(pos))

    # The grip's clicks are its own: passed on, they'd open or close the row
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressPos = event.position().toPoint()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.pressPos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self.pressPos).manhattanLength() < 6:
            return
        self.pressPos = None
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(PLAYER_MIME, QByteArray(str(id(self.row)).encode()))
        drag.setMimeData(mime)
        drag.setPixmap(self.row.grab().scaledToWidth(min(320, self.row.width())))
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        self.pressPos = None
        event.accept()


class CharacterChip(QToolButton):
    """One of a player's characters: the icon, name and skin number. Click it
    to pick another character, drag it onto another chip to swap them."""

    def __init__(self, row, index, parent=None):
        super().__init__(parent)
        self.row = row
        self.index = index
        self.pressPos = None
        SetRole(self, "chip", empty=True)
        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        SmallFont(self, 0.9)

    def Refresh(self, name, icon, tooltip, compact):
        empty = not name
        SetStyleProperty(self, "empty", empty)
        if empty:
            self.setIcon(QIcon())
            self.setText("+" if compact else QApplication.translate("app", "+ Character"))
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            self.setToolTip(QApplication.translate("app", "Pick a character"))
            return
        self.setIcon(icon or QIcon())
        self.setText(name)
        self.setToolTip(tooltip)
        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if compact and not (icon is None or icon.isNull())
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressPos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressPos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self.pressPos).manhattanLength() < 8:
            return
        self.pressPos = None
        self.setDown(False)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(CHARACTER_MIME, QByteArray(f"{id(self.row)}:{self.index}".encode()))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)

    def _Source(self, event):
        if not event.mimeData().hasFormat(CHARACTER_MIME):
            return None
        rowId, index = bytes(event.mimeData().data(CHARACTER_MIME)).decode().split(":")
        if rowId != str(id(self.row)) or int(index) == self.index:
            return None
        return int(index)

    def dragEnterEvent(self, event):
        if self._Source(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event):
        source = self._Source(event)
        if source is not None:
            event.acceptProposedAction()
            self.row.UserSwapCharacters(source, self.index)


class _CharacterFilter(QSortFilterProxyModel):
    """The game's characters without the empty first row, filtered by name."""

    def filterAcceptsRow(self, row, parent):
        index = self.sourceModel().index(row, 0, parent)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return False
        return super().filterAcceptsRow(row, parent)


class CharacterPicker(QFrame):
    """A grid of the game's characters, with the player's mains first and the
    skins of the chosen character below. Changes apply right away."""

    def __init__(self, row, slot, anchor):
        super().__init__(None, Qt.WindowType.Popup)
        self.row = row
        self.slot = slot
        _, self.characterCombo, self.colorCombo, self.variantCombo = row.character_elements[slot]
        SetRole(self, "card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        tag = row.GetCurrentPlayerTag() or QApplication.translate("app", "Player")
        title = QLabel(QApplication.translate("app", "{0} · character {1}").format(tag, slot + 1))
        SmallFont(title, 1.05, bold=True)
        layout.addWidget(title)

        # The player's mains from the database
        mains = self.Mains()
        if mains:
            mainsRow = QHBoxLayout()
            mainsRow.setSpacing(4)
            mainsRow.addWidget(EyebrowLabel(QApplication.translate("app", "Mains")))
            for name in mains:
                item = self.FindCharacter(name)
                if item is None:
                    continue
                button = QToolButton()
                SetRole(button, "chip")
                button.setIcon(item.icon())
                button.setIconSize(QSize(20, 20))
                button.setText(item.text())
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.clicked.connect(lambda checked=False, r=item.row(): self.PickRow(r))
                mainsRow.addWidget(button)
            mainsRow.addStretch()
            layout.addLayout(mainsRow)

        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("app", "Search characters"))
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.proxy = _CharacterFilter(self)
        self.proxy.setSourceModel(self.characterCombo.model())
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.search.returnPressed.connect(self.PickFirst)

        self.grid = QListView()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setIconSize(QSize(36, 36))
        self.grid.setGridSize(QSize(86, 72))
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setMinimumHeight(220)
        self.grid.setModel(self.proxy)
        self.grid.clicked.connect(lambda index: self.PickRow(self.proxy.mapToSource(index).row()))
        self.grid.activated.connect(lambda index: self.PickRow(self.proxy.mapToSource(index).row()))
        layout.addWidget(self.grid, 1)

        self.skinLabel = EyebrowLabel(QApplication.translate("app", "Skin"))
        layout.addWidget(self.skinLabel)
        self.skins = QListView()
        self.skins.setViewMode(QListView.ViewMode.IconMode)
        self.skins.setFlow(QListView.Flow.LeftToRight)
        self.skins.setWrapping(True)
        self.skins.setResizeMode(QListView.ResizeMode.Adjust)
        self.skins.setMovement(QListView.Movement.Static)
        self.skins.setIconSize(QSize(40, 40))
        self.skins.setGridSize(QSize(52, 52))
        self.skins.setMaximumHeight(120)
        self.skins.clicked.connect(lambda index: self.PickSkin(index.row()))
        layout.addWidget(self.skins)

        self.variantLabel = EyebrowLabel(QApplication.translate("app", "Variant"))
        layout.addWidget(self.variantLabel)
        self.variant = QComboBox()
        self.variant.setModel(self.variantCombo.model())
        self.variant.setCurrentIndex(self.variantCombo.currentIndex())
        self.variant.activated.connect(self.PickVariant)
        layout.addWidget(self.variant)
        hasVariants = len(GameAssetManager.instance.variants) > 0
        self.variantLabel.setVisible(hasVariants)
        self.variant.setVisible(hasVariants)

        buttons = QHBoxLayout()
        remove = QPushButton(QApplication.translate("app", "Remove"))
        SetRole(remove, "ghost")
        remove.clicked.connect(lambda: [self.PickRow(0), self.close()])
        buttons.addWidget(remove)
        buttons.addStretch()
        done = QPushButton(QApplication.translate("app", "Done"))
        SetRole(done, "primary")
        done.clicked.connect(self.close)
        buttons.addWidget(done)
        layout.addLayout(buttons)

        self.RefreshSkins()
        self.SelectCurrent()

        self.adjustSize()
        self.resize(max(self.width(), 470), max(self.height(), 480))
        # Below the chip, kept on the screen
        screen = (anchor.screen() or QApplication.primaryScreen()).availableGeometry()
        pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        x = max(screen.left(), min(pos.x(), screen.right() - self.width()))
        y = pos.y()
        if y + self.height() > screen.bottom():
            y = max(screen.top(), anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() - 4)
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus()

    def Mains(self):
        player = PlayerDB.GetPlayer(self.row.GetCurrentPlayerTag()) or {}
        mains = player.get("mains")
        if not isinstance(mains, dict):
            return []
        game = GameAssetManager.instance.selectedGame
        codename = game.get("codename")
        mains = mains.get(codename) or mains.get(game.get("base_game_dir", codename)) or []
        return [m[0] for m in mains if m]

    def FindCharacter(self, enName):
        model = self.characterCombo.model()
        if not isinstance(model, QStandardItemModel):
            return None
        for i in range(model.rowCount()):
            item = model.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("en_name") == enName:
                return item
        return None

    def SelectCurrent(self):
        row = self.characterCombo.currentIndex()
        if row > 0:
            index = self.proxy.mapFromSource(self.characterCombo.model().index(row, 0))
            self.grid.setCurrentIndex(index)
            self.grid.scrollTo(index)
        skin = self.colorCombo.currentIndex()
        if skin >= 0 and self.skins.model() is not None:
            self.skins.setCurrentIndex(self.skins.model().index(skin, 0))

    def RefreshSkins(self):
        self.skins.setModel(self.colorCombo.model())
        hasSkins = self.characterCombo.currentIndex() > 0 and self.colorCombo.count() > 1
        self.skinLabel.setVisible(hasSkins)
        self.skins.setVisible(hasSkins)

    def PickFirst(self):
        if self.proxy.rowCount() > 0:
            self.PickRow(self.proxy.mapToSource(self.proxy.index(0, 0)).row())

    def PickRow(self, row):
        self.row.UserSetCharacter(self.slot, row)
        self.RefreshSkins()
        self.SelectCurrent()

    def PickSkin(self, skin):
        self.row.UserSetSkin(self.slot, skin)

    def PickVariant(self, index):
        self.row.UserSetVariant(self.slot, index)


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
