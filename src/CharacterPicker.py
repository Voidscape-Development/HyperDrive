"""A grid to pick characters, skins and variants from, in place of the
dropdowns' lists.

CharacterCombo, SkinCombo and VariantCombo are the character, skin and
variant dropdowns; they hold the selection as before (current index and
data, from GameAssetManager's models), only their popup is the grid.
Picking a character goes on to its skins in the same popup, with the
default one selected. Variants have a grid of their own.
"""

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameAssetManager import GameAssetManager
from .Helpers.CharacterIconHelper import PlaceholderPixmap
from .SettingsManager import SettingsManager
from .Theme import ThemedIcon

# The characters picked last, by game: {game codename: [en_name, ...]}
RECENT_KEY = "character_picker.recent"
RECENT_COUNT = 12
# Settings page "Character Select" turns the mains and recent rows on and off
SHOW_MAINS_KEY = "character_picker.show_mains"
SHOW_RECENT_KEY = "character_picker.show_recent"

COLUMNS = 7
CHARACTER_ICON = QSize(40, 40)
CHARACTER_TILE = QSize(80, 84)
SKIN_ICON = QSize(96, 72)
SKIN_TILE = QSize(112, 112)

# Data of the grid's items: the row in the dropdown's model
SourceRowRole = Qt.ItemDataRole.UserRole + 1


def GameCodename():
    return (GameAssetManager.instance.selectedGame or {}).get("codename")


def RecentCharacters():
    recent = SettingsManager.Get(f"{RECENT_KEY}.{GameCodename()}", []) if GameCodename() else []
    return [c for c in recent if isinstance(c, str)]


def AddRecentCharacter(en_name):
    game = GameCodename()
    if not game or not en_name:
        return
    recent = [en_name] + [c for c in RecentCharacters() if c != en_name]
    SettingsManager.Set(f"{RECENT_KEY}.{game}", recent[:RECENT_COUNT])


def MainsOf(player):
    """The en_names of a player's (a player DB entry's) mains in the game
    loaded, in order."""
    mains = (player or {}).get("mains")
    if not isinstance(mains, dict):
        return []
    selected = GameAssetManager.instance.selectedGame or {}
    game = selected.get("codename")
    entries = mains.get(game) or mains.get(selected.get("base_game_dir", game)) or []
    names = []
    for main in entries:
        if isinstance(main, list) and main and isinstance(main[0], str) and main[0]:
            if main[0] not in names:
                names.append(main[0])
    return names


def DisplayName(en_name):
    character = GameAssetManager.instance.characters.get(en_name) or {}
    return character.get("display_name") or en_name


class _IconCache:
    """The characters' stock icons at the grid's size, made when first
    needed, again when another game is loaded."""

    source = None
    icons = {}

    @staticmethod
    def Get(en_name, fallback):
        stockIcons = GameAssetManager.instance.stockIcons
        if _IconCache.source is not stockIcons:
            _IconCache.source = stockIcons
            _IconCache.icons = {}
        icon = _IconCache.icons.get(en_name)
        if icon is None:
            if en_name in stockIcons and not stockIcons[en_name]:
                # No pack has an icon for it: its initials
                icon = QIcon(PlaceholderPixmap(DisplayName(en_name), CHARACTER_ICON.width()))
                _IconCache.icons[en_name] = icon
                return icon
            path = (stockIcons.get(en_name) or {}).get(0)
            image = QImage(path) if path else QImage()
            if image.isNull():
                # Not loaded yet: use the dropdown's icon, and try again later
                return fallback
            icon = QIcon(
                QPixmap.fromImage(
                    image.scaled(
                        CHARACTER_ICON,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            )
            _IconCache.icons[en_name] = icon
        return icon


class _TileDelegate(QStyledItemDelegate):
    """A tile: the icon, and the name under it on up to two lines."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def sizeHint(self, option, index):
        return self.view.gridSize()

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = option.palette
        rect = option.rect.adjusted(2, 2, -2, -2)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            color = QColor(palette.color(QPalette.ColorRole.Highlight))
            if not selected:
                color.setAlpha(60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(rect), 6, 6)

        iconSize = self.view.iconSize()
        iconRect = QRect(
            rect.center().x() - iconSize.width() // 2 + 1,
            rect.top() + 4,
            iconSize.width(),
            iconSize.height(),
        )
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, iconRect)
        elif isinstance(icon, QPixmap):
            painter.drawPixmap(iconRect, icon)

        font = QFont(option.font)
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        painter.setFont(font)
        painter.setPen(
            palette.color(
                QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
            )
        )
        textRect = QRect(rect.left() + 3, iconRect.bottom() + 3, rect.width() - 6, 0)
        textRect.setBottom(rect.bottom() - 2)
        flags = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        metrics = QFontMetrics(font)
        # Shortened until it fits in the two lines
        shown = text
        while shown and metrics.boundingRect(textRect, flags, shown).height() > textRect.height():
            shown = metrics.elidedText(
                shown, Qt.TextElideMode.ElideRight, metrics.horizontalAdvance(shown) - 4
            )
            if shown in ("…", "..."):
                break
        painter.drawText(textRect, flags, shown)
        painter.restore()


class _GridView(QListView):
    """Tiles with an icon and a name, as tall as their rows: the popup
    scrolls, not each grid."""

    picked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # On the popup's background, the tiles draw their own highlight
        self.setStyleSheet("QListView { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self.setItemDelegate(_TileDelegate(self))
        self.setModel(QStandardItemModel(self))
        self.clicked.connect(self.Pick)
        self.activated.connect(self.Pick)

    def SetTiles(self, tiles, iconSize, tileSize):
        """tiles: [(icon, name, source row)]"""
        model = QStandardItemModel(self)
        for icon, name, row in tiles:
            item = QStandardItem(icon, name) if icon is not None else QStandardItem(name)
            item.setToolTip(name)
            item.setData(row, SourceRowRole)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            model.appendRow(item)
        self.setModel(model)
        self.setIconSize(iconSize)
        self.setGridSize(tileSize)
        self.UpdateHeight()

    def Count(self):
        return self.model().rowCount()

    def SelectSourceRow(self, row):
        """Selects the tile of the dropdown's row, or the first one."""
        model = self.model()
        index = model.index(0, 0)
        for i in range(model.rowCount()):
            if model.index(i, 0).data(SourceRowRole) == row:
                index = model.index(i, 0)
                break
        if index.isValid():
            self.setCurrentIndex(index)
            self.scrollTo(index)

    def UpdateHeight(self, width=None):
        width = max(1, width or self.viewport().width() or self.width())
        perRow = max(1, width // max(1, self.gridSize().width()))
        rows = (self.Count() + perRow - 1) // perRow
        self.setFixedHeight(rows * self.gridSize().height() + 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.UpdateHeight()

    def Pick(self, index):
        if index.isValid():
            self.picked.emit(index.data(SourceRowRole))

    def PickCurrent(self):
        index = self.currentIndex()
        if not index.isValid() and self.Count() > 0:
            index = self.model().index(0, 0)
        self.Pick(index)


class CharacterPickerPopup(QFrame):
    """The grid, opened under a CharacterCombo, SkinCombo or VariantCombo."""

    closed = Signal()

    def __init__(self, characterCombo, skinCombo=None, variantCombo=None):
        super().__init__(characterCombo, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.characterCombo = characterCombo
        self.skinCombo = skinCombo
        self.variantCombo = variantCombo
        self.step = "character"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        layout.addLayout(header)
        self.backButton = QToolButton()
        self.backButton.setIcon(ThemedIcon("assets/icons/arrow_left.svg"))
        self.backButton.setToolTip(QApplication.translate("app", "Back to the characters"))
        self.backButton.setAutoRaise(True)
        self.backButton.clicked.connect(self.ShowCharacters)
        header.addWidget(self.backButton)
        self.title = QLabel()
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        header.addWidget(self.title)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.Filter)
        self.search.installEventFilter(self)
        header.addWidget(self.search, 1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        self.contentLayout = QVBoxLayout(content)
        self.contentLayout.setContentsMargins(0, 0, 0, 0)
        self.contentLayout.setSpacing(2)

        # Mains, recent and every character (or the skins)
        self.sections = []
        for name in [
            QApplication.translate("app", "Mains"),
            QApplication.translate("app", "Recent"),
            QApplication.translate("app", "All characters"),
        ]:
            label = QLabel(name.upper())
            small = label.font()
            small.setPointSize(max(7, small.pointSize() - 2))
            small.setBold(True)
            label.setFont(small)
            view = _GridView()
            view.picked.connect(self.Picked)
            self.contentLayout.addWidget(label)
            self.contentLayout.addWidget(view)
            self.sections.append((label, view))
        self.contentLayout.addStretch()
        self.mainsSection, self.recentSection, self.allSection = self.sections

        self.setMinimumWidth(COLUMNS * CHARACTER_TILE.width() + 40)

    # Opening

    def Open(self, step="character", text=""):
        if step == "variant" and self.variantCombo is not None:
            self.ShowVariants()
        elif step == "skin" and self.CurrentCharacterData():
            self.ShowSkins()
        else:
            self.ShowCharacters()
        if text:
            self.search.setText(text)
        self.Place()
        self.show()
        self.search.setFocus()

    def Place(self):
        """Under the dropdown, or above it when there's no room below."""
        anchor = {"skin": self.skinCombo, "variant": self.variantCombo}.get(self.step)
        anchor = anchor or self.characterCombo
        screen = (anchor.screen() or QApplication.primaryScreen()).availableGeometry()
        width = max(self.minimumWidth(), anchor.width())
        width = min(width, screen.width())
        margins = self.layout().contentsMargins()
        inner = width - margins.left() - margins.right()

        # As tall as the rows shown, which depends on the width
        content = 0
        for label, view in self.sections:
            if label.isVisibleTo(self):
                content += label.sizeHint().height() + self.contentLayout.spacing()
            if view.isVisibleTo(self):
                view.UpdateHeight(inner)
                content += view.height() + self.contentLayout.spacing()
        # The search row, taller with the back button
        header = self.layout().itemAt(0).sizeHint().height() + self.layout().spacing()
        height = content + header + margins.top() + margins.bottom() + 8
        maxHeight = min(460, screen.height())
        if height > maxHeight:
            # Scrolls: leave room for the scroll bar
            for _, view in self.sections:
                view.UpdateHeight(inner - self.scroll.verticalScrollBar().sizeHint().width())
            height = maxHeight
        self.resize(width, height)

        below = anchor.mapToGlobal(QPoint(0, anchor.height()))
        x = min(max(screen.left(), below.x()), screen.right() - width + 1)
        y = below.y()
        if y + height > screen.bottom():
            above = anchor.mapToGlobal(QPoint(0, 0)).y() - height
            y = above if above >= screen.top() else max(screen.top(), screen.bottom() - height)
        self.move(x, y)

    # Steps

    def CurrentCharacterData(self):
        data = self.characterCombo.currentData()
        return data if data and data.get("en_name") else None

    def ShowCharacters(self):
        self.step = "character"
        self.backButton.setVisible(False)
        self.title.setVisible(False)
        self.search.setPlaceholderText(QApplication.translate("app", "Search characters..."))
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.Filter("")
        self.allSection[1].SelectSourceRow(self.characterCombo.currentIndex())
        self.search.setFocus()

    def ShowSkins(self):
        data = self.CurrentCharacterData()
        if self.skinCombo is None or data is None:
            self.close()
            return
        self.step = "skin"
        self.backButton.setVisible(True)
        self.title.setText(data.get("display_name") or data.get("en_name"))
        self.title.setVisible(True)
        self.search.setPlaceholderText(QApplication.translate("app", "Search skins..."))
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.Filter("")
        self.allSection[1].SelectSourceRow(max(0, self.skinCombo.currentIndex()))
        self.search.setFocus()

    def ShowVariants(self):
        self.step = "variant"
        self.backButton.setVisible(False)
        self.title.setVisible(False)
        self.search.setPlaceholderText(QApplication.translate("app", "Search variants..."))
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.Filter("")
        self.allSection[1].SelectSourceRow(max(0, self.variantCombo.currentIndex()))
        self.search.setFocus()

    def VariantTiles(self, text=""):
        """[(icon, name, row)] of the variant dropdown's model, matching
        text; the empty first row is the "None" tile."""
        model = self.variantCombo.model() if self.variantCombo else None
        text = text.strip().lower()
        tiles = []
        for row in range(model.rowCount() if model else 0):
            index = model.index(row, 0)
            data = index.data(Qt.ItemDataRole.UserRole)
            if not data or not data.get("en_name"):
                if row == 0 and not text:
                    tiles.append(
                        (
                            ThemedIcon("assets/icons/cancel.svg"),
                            QApplication.translate("app", "None"),
                            row,
                        )
                    )
                continue
            name = data.get("display_name") or data.get("en_name")
            if text and text not in f"{name} {data.get('en_name')}".lower():
                continue
            tiles.append((index.data(Qt.ItemDataRole.DecorationRole), name, row))
        return tiles

    def CharacterTiles(self, text=""):
        """[(icon, name, row)] of the character dropdown's model, matching
        text; the empty first row is the "None" tile."""
        model = self.characterCombo.model()
        text = text.strip().lower()
        tiles = []
        byName = {}
        for row in range(model.rowCount() if model else 0):
            index = model.index(row, 0)
            data = index.data(Qt.ItemDataRole.UserRole)
            if not data or not data.get("en_name"):
                if row == 0 and not text:
                    tiles.append(
                        (
                            ThemedIcon("assets/icons/cancel.svg"),
                            QApplication.translate("app", "None"),
                            row,
                        )
                    )
                continue
            name = data.get("display_name") or data.get("en_name")
            byName[data.get("en_name")] = row
            if text and text not in f"{name} {data.get('en_name')}".lower():
                continue
            icon = _IconCache.Get(data.get("en_name"), index.data(Qt.ItemDataRole.DecorationRole))
            tiles.append((icon, name, row))
        return tiles, byName

    def Filter(self, text):
        searching = bool(text.strip())
        (mainsLabel, mainsView), (recentLabel, recentView), (allLabel, allView) = self.sections

        if self.step in ("skin", "variant"):
            for label, view in [self.mainsSection, self.recentSection]:
                label.setVisible(False)
                view.setVisible(False)
            allLabel.setVisible(False)
            if self.step == "skin":
                allView.SetTiles(self.SkinTiles(text), SKIN_ICON, SKIN_TILE)
            else:
                allView.SetTiles(self.VariantTiles(text), CHARACTER_ICON, CHARACTER_TILE)
            if allView.Count():
                allView.setCurrentIndex(allView.model().index(0, 0))
            return

        tiles, byName = self.CharacterTiles(text)
        allView.SetTiles(tiles, CHARACTER_ICON, CHARACTER_TILE)
        if searching and allView.Count():
            allView.setCurrentIndex(allView.model().index(0, 0))

        # The mains and recent rows are left out while searching
        everything = tiles if not searching else self.CharacterTiles()[0]
        everything = {row: tile for tile in everything for row in [tile[2]]}
        provider = self.characterCombo.mainsProvider
        showMains = SettingsManager.Get(SHOW_MAINS_KEY, True) and not searching
        showRecent = SettingsManager.Get(SHOW_RECENT_KEY, True) and not searching
        mains = provider() if callable(provider) and showMains else []
        recent = RecentCharacters()[:COLUMNS] if showRecent else []
        anyShown = False
        for (label, view), names in [
            ((mainsLabel, mainsView), mains),
            ((recentLabel, recentView), recent),
        ]:
            sectionTiles = [everything[byName[n]] for n in names if byName.get(n) in everything]
            view.SetTiles(sectionTiles, CHARACTER_ICON, CHARACTER_TILE)
            label.setVisible(bool(sectionTiles))
            view.setVisible(bool(sectionTiles))
            anyShown = anyShown or bool(sectionTiles)
        allLabel.setVisible(anyShown)

    def SkinTiles(self, text=""):
        model = self.skinCombo.model() if self.skinCombo else None
        text = text.strip().lower()
        tiles = []
        for row in range(model.rowCount() if model else 0):
            index = model.index(row, 0)
            name = str(index.data(Qt.ItemDataRole.DisplayRole) or row)
            if text and text not in name.lower():
                continue
            tiles.append((index.data(Qt.ItemDataRole.DecorationRole), name, row))
        return tiles

    # Picking

    def Picked(self, row):
        if row is None:
            return
        if self.step == "character":
            # Picking the character already set still goes on to its skins
            if self.characterCombo.currentIndex() != row:
                self.characterCombo.setCurrentIndex(row)
            data = self.CurrentCharacterData()
            if data is None:
                self.close()
                return
            AddRecentCharacter(data.get("en_name"))
            if self.skinCombo is None or self.skinCombo.count() <= 1:
                self.close()
                return
            self.ShowSkins()
            self.Place()
        elif self.step == "variant":
            if self.variantCombo.currentIndex() != row:
                self.variantCombo.setCurrentIndex(row)
            self.close()
        else:
            if self.skinCombo.currentIndex() != row:
                self.skinCombo.setCurrentIndex(row)
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    # Keys typed in the search box move in the grid

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            view = self.allSection[1]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                view.PickCurrent()
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                QApplication.sendEvent(view, event)
                return True
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and not self.search.text():
                QApplication.sendEvent(view, event)
                return True
            if key == Qt.Key.Key_Backspace and not self.search.text() and self.step == "skin":
                self.ShowCharacters()
                self.Place()
                return True
        return super().eventFilter(obj, event)


class CharacterCombo(QComboBox):
    """The character dropdown, opening the grid. mainsProvider, when set,
    returns the en_names shown first as the player's mains."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.skinCombo = None
        self.variantCombo = None
        self.mainsProvider = None
        self.popup = None

    def showPopup(self):
        self.OpenPicker()

    def OpenPicker(self, step="character", text=""):
        if step == "variant":
            model = self.variantCombo.model() if self.variantCombo else None
            fallback = self.variantCombo
        else:
            model = self.model()
            fallback = self
        # Nothing to pick from (no game loaded): the plain list
        if model is None or model.rowCount() <= 1:
            if fallback is not None:
                QComboBox.showPopup(fallback)
            return
        if self.popup is not None:
            self.popup.close()
        self.popup = CharacterPickerPopup(self, self.skinCombo, self.variantCombo)
        self.popup.closed.connect(self._PopupClosed)
        self.popup.Open(step, text)

    def _PopupClosed(self):
        self.popup = None

    def hidePopup(self):
        if self.popup is not None:
            self.popup.close()
        super().hidePopup()

    def keyPressEvent(self, event):
        # Typing on the dropdown searches in the grid
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            self.OpenPicker(text=text)
            return
        super().keyPressEvent(event)


class SkinCombo(QComboBox):
    """The skin dropdown, opening the grid on its character's skins."""

    def __init__(self, characterCombo: CharacterCombo, parent=None):
        super().__init__(parent)
        self.characterCombo = characterCombo
        characterCombo.skinCombo = self

    def showPopup(self):
        if self.count() <= 0 and self.characterCombo.model() is None:
            super().showPopup()
            return
        self.characterCombo.OpenPicker(step="skin")

    def keyPressEvent(self, event):
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            self.characterCombo.OpenPicker(step="skin", text=text)
            return
        super().keyPressEvent(event)


class VariantCombo(QComboBox):
    """The variant dropdown, opening the grid on the game's variants."""

    def __init__(self, characterCombo: CharacterCombo, parent=None):
        super().__init__(parent)
        self.characterCombo = characterCombo
        characterCombo.variantCombo = self

    def showPopup(self):
        self.characterCombo.OpenPicker(step="variant")

    def keyPressEvent(self, event):
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            self.characterCombo.OpenPicker(step="variant", text=text)
            return
        super().keyPressEvent(event)
