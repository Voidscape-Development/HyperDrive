from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..ColorButton import ColorButton
from ..FlowLayout import FlowLayout
from ..SettingsManager import SettingsManager
from ..Theme import (
    COLOR_KEYS,
    CUSTOM_PREFIX,
    DEFAULT_ACCENT,
    DEFAULT_UI_SCALE,
    MAX_RADIUS,
    PRESET_PREFIX,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    UI_SCALES,
    BuiltinTheme,
    ColorLabels,
    DefaultColors,
    ExportTheme,
    ImportTheme,
    PresetNames,
    PresetTheme,
    SpacingLabels,
    Theme,
    ThemedIcon,
)
from .Controls import NoDefaultButtons, SettingRow, SettingsPage, ThemeCard
from .SettingsWidget import TYPE_COLOR, TYPE_DROPDOWN, Setting

# Edits are saved and applied after this long without another change, so
# dragging the roundness slider doesn't restyle the app on every step
APPLY_DELAY_MS = 150

# Accents offered next to the color picker, for the built-in themes
ACCENT_SWATCHES = ["#ffb800", "#4f8cff", "#4ade80", "#ff4fd8", "#ff7a1a", "#a78bfa"]


def _tr(text):
    return QApplication.translate("settings.appearance", text)


def DrawAppTheme(colors):
    """Paints a small window in a theme's colors, for its card"""
    c = {k: QColor(v) for k, v in colors.items()}

    def Draw(painter, rect):
        painter.fillRect(rect, c["window"])
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 9), c["window"].darker(115))
        painter.fillRect(
            QRectF(rect.left(), rect.top() + 9, rect.width() * 0.3, rect.height() - 9), c["surface"]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        x = rect.left() + rect.width() * 0.38
        for top, width, key in ((22, 0.46, "border"), (34, 0.32, "raised")):
            painter.setBrush(c[key])
            painter.drawRoundedRect(QRectF(x, rect.top() + top, rect.width() * width, 6), 3, 3)
        painter.setBrush(c["accent"])
        painter.drawRoundedRect(QRectF(x, rect.bottom() - 18, rect.width() * 0.22, 9), 3, 3)

    return Draw


def DrawSystemTheme(dark, light):
    drawDark, drawLight = DrawAppTheme(dark), DrawAppTheme(light)

    def Draw(painter, rect):
        drawLight(painter, rect)
        painter.save()
        triangle = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomLeft()])
        path = QPainterPath()
        path.addPolygon(triangle)
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
        drawDark(painter, rect)
        painter.restore()

    return Draw


def DrawNewTheme(painter, rect):
    c = Theme.Colors()
    painter.setPen(QPen(c["muted"], 1.5, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
    painter.setPen(QPen(c["muted"], 2))
    center = rect.center()
    painter.drawLine(QPointF(center.x() - 8, center.y()), QPointF(center.x() + 8, center.y()))
    painter.drawLine(QPointF(center.x(), center.y() - 8), QPointF(center.x(), center.y() + 8))


class Swatch(QAbstractButton):
    """A round color to pick"""

    def __init__(self, color, tooltip, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setCheckable(True)
        self.setFixedSize(26, 26)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def paintEvent(self, event):
        c = Theme.Colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isChecked() or self.hasFocus():
            painter.setPen(QPen(c["text"], 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)
            rect = rect.adjusted(3, 3, -3, -3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(rect)


class AppearanceSettings(SettingsPage):
    def __init__(self, parent=None):
        super().__init__(
            _tr("Appearance"),
            _tr("How HyperDrive's own windows look. Your layouts' look is set in Layout Themes."),
            parent,
        )
        self.editing = None  # the custom theme being edited, as a theme dict
        self.updating = False  # set while the controls are being filled in
        # The settings saved as they're changed, for the settings window
        self.settings = []

        self.applyTimer = QTimer(self)
        self.applyTimer.setSingleShot(True)
        self.applyTimer.setInterval(APPLY_DELAY_MS)
        self.applyTimer.timeout.connect(self.SaveEdits)

        # ---------------- Gallery ----------------
        self.galleryGroup = self.AddGroup(_tr("App theme"))
        importButton = QPushButton(_tr("Import..."))
        importButton.setIcon(ThemedIcon("assets/icons/download.svg"))
        importButton.clicked.connect(self.Import)
        self.galleryGroup.header.addWidget(importButton)
        exportButton = QPushButton(_tr("Export..."))
        exportButton.setIcon(ThemedIcon("assets/icons/export.svg"))
        exportButton.setToolTip(_tr("Saves the theme in use to a file you can share"))
        exportButton.clicked.connect(self.Export)
        self.galleryGroup.header.addWidget(exportButton)
        self.galleryHolder = QWidget()
        QVBoxLayout(self.galleryHolder).setContentsMargins(12, 6, 12, 12)
        self.galleryGroup.AddWidget(self.galleryHolder)
        self.gallery = None
        self.cards = QButtonGroup(self)
        self.cards.setExclusive(True)

        # ---------------- Accent and size ----------------
        group = self.AddGroup()
        accent = QWidget()
        accentLayout = QHBoxLayout(accent)
        accentLayout.setContentsMargins(0, 0, 0, 0)
        accentLayout.setSpacing(8)
        self.swatches = []
        for color in ACCENT_SWATCHES:
            swatch = Swatch(
                color, _tr("Default amber") if color == DEFAULT_ACCENT else QColor(color).name()
            )
            swatch.clicked.connect(lambda checked=False, c=color: self.accentButton.setColor(c))
            accentLayout.addWidget(swatch)
            self.swatches.append(swatch)
        self.accentButton = ColorButton(
            color=SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT),
            disable_right_click=True,
        )
        self.accentButton.setToolTip(_tr("Pick any color"))
        self.accentButton.colorChanged.connect(self.AccentChanged)
        accentLayout.addWidget(self.accentButton)
        self.accentRow = group.AddRow(
            SettingRow(_tr("Accent color"), accent, _tr("Selections, switches and highlights"))
        )
        self.accentRow.resetClicked.connect(lambda: self.accentButton.setColor(DEFAULT_ACCENT))

        scale = Setting(
            "appearance.ui_scale",
            TYPE_DROPDOWN,
            DEFAULT_UI_SCALE,
            _tr("Interface size"),
            options=[(s, f"{s}%") for s in UI_SCALES],
            restart=True,
        )
        scale.setParent(self)
        group.AddRow(scale.row)
        self.settings.append(scale)

        # ---------------- Custom theme editor ----------------
        self.editor = self.AddGroup(" ")
        self.renameButton = QPushButton(_tr("Rename..."))
        self.renameButton.setIcon(ThemedIcon("assets/icons/pencil.svg"))
        self.renameButton.clicked.connect(self.Rename)
        self.editor.header.addWidget(self.renameButton)
        self.resetColorsButton = QPushButton(_tr("Reset all colors"))
        self.resetColorsButton.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.resetColorsButton.setToolTip(
            _tr(
                "Resets every color to the built-in Dark or Light theme, whichever this theme is closest to"
            )
        )
        self.resetColorsButton.clicked.connect(self.ResetAllColors)
        self.editor.header.addWidget(self.resetColorsButton)
        self.deleteButton = QPushButton(_tr("Delete"))
        self.deleteButton.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.deleteButton.clicked.connect(self.Delete)
        self.editor.header.addWidget(self.deleteButton)

        colors = QWidget()
        colorGrid = QGridLayout(colors)
        colorGrid.setContentsMargins(0, 0, 0, 0)
        colorGrid.setHorizontalSpacing(8)
        colorGrid.setVerticalSpacing(0)
        self.colorButtons = {}
        self.colorRows = {}
        labels = ColorLabels()
        for i, key in enumerate(COLOR_KEYS):
            button = ColorButton(disable_right_click=True)
            button.colorChanged.connect(lambda color, key=key: self.ColorEdited(key, color))
            row = SettingRow(labels[key], button)
            row.resetClicked.connect(lambda key=key: self.ResetColor(key))
            colorGrid.addWidget(row, i // 2, i % 2)
            self.colorButtons[key] = button
            self.colorRows[key] = row
        self.editor.AddWidget(colors)

        roundness = QWidget()
        roundnessLayout = QHBoxLayout(roundness)
        roundnessLayout.setContentsMargins(0, 0, 0, 0)
        self.radiusSlider = QSlider(Qt.Orientation.Horizontal)
        self.radiusSlider.setRange(0, MAX_RADIUS)
        self.radiusSlider.setFixedWidth(180)
        self.radiusLabel = QLabel()
        self.radiusLabel.setMinimumWidth(40)
        self.radiusSlider.valueChanged.connect(
            lambda value: [
                self.radiusLabel.setText(f"{value} px"),
                self.Edit(lambda theme: theme.__setitem__("radius", value)),
            ]
        )
        roundnessLayout.addWidget(self.radiusSlider)
        roundnessLayout.addWidget(self.radiusLabel)
        self.editor.AddRow(SettingRow(_tr("Corner roundness"), roundness, reset=False))

        self.spacingSelect = QComboBox()
        for value, label in SpacingLabels().items():
            self.spacingSelect.addItem(label, value)
        self.spacingSelect.currentIndexChanged.connect(
            lambda i: self.Edit(
                lambda theme: theme.__setitem__("spacing", self.spacingSelect.currentData())
            )
        )
        self.editor.AddRow(SettingRow(_tr("Spacing"), self.spacingSelect, reset=False))

        self.fontSelect = QComboBox()
        self.fontSelect.setMaxVisibleItems(20)
        self.fontSelect.addItem(_tr("System default"), "")
        for family in QFontDatabase.families():
            self.fontSelect.addItem(family, family)
        self.fontSelect.currentIndexChanged.connect(
            lambda i: self.Edit(
                lambda theme: theme.__setitem__("font", self.fontSelect.currentData())
            )
        )
        self.editor.AddRow(SettingRow(_tr("Font"), self.fontSelect, reset=False))

        # The colors teams start with. Stored under general, where they were
        # before they moved here
        teams = self.AddGroup(_tr("Team colors for new sets"))
        for key, title, default in (
            ("team_1_default_color", _tr("Team 1"), "#fe3636"),
            ("team_2_default_color", _tr("Team 2"), "#2e89ff"),
        ):
            setting = Setting("general." + key, TYPE_COLOR, default, title)
            setting.setParent(self)
            teams.AddRow(setting.row)
            self.settings.append(setting)

        self.Refresh()

    # =====================================================
    # REFRESHING
    # =====================================================
    def BuildGallery(self):
        """The cards of every theme, the one in use checked"""
        if self.gallery is not None:
            self.gallery.deleteLater()
        for button in self.cards.buttons():
            self.cards.removeButton(button)
        self.gallery = QWidget()
        flow = FlowLayout(self.gallery, spacing=12)
        flow.setContentsMargins(0, 0, 0, 0)
        mode = Theme.Mode()
        accent = SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT)

        def Add(name, data, draw, tooltip=None, custom=None):
            card = ThemeCard(name, draw)
            card.setChecked(data == mode)
            if tooltip:
                card.setToolTip(tooltip)
            card.clicked.connect(lambda checked=False, d=data: self.ThemeSelected(d))
            if custom:
                card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                card.customContextMenuRequested.connect(
                    lambda pos, c=card, n=custom: self.CardMenu(c, n, pos)
                )
            self.cards.addButton(card)
            flow.addWidget(card)

        dark = BuiltinTheme(THEME_DARK, accent)["colors"]
        light = BuiltinTheme(THEME_LIGHT, accent)["colors"]
        Add(_tr("Dark"), THEME_DARK, DrawAppTheme(dark))
        Add(_tr("Light"), THEME_LIGHT, DrawAppTheme(light))
        Add(_tr("Follow system"), THEME_SYSTEM, DrawSystemTheme(dark, light))
        for key, name in PresetNames().items():
            Add(name, PRESET_PREFIX + key, DrawAppTheme(PresetTheme(key)["colors"]))
        for name, theme in sorted(Theme.CustomThemes().items(), key=lambda t: t[0].lower()):
            Add(
                name,
                CUSTOM_PREFIX + name,
                DrawAppTheme(theme["colors"]),
                _tr("{0} (yours). Right-click to rename or delete it.").format(name),
                custom=name,
            )
        new = ThemeCard(_tr("New from current"), DrawNewTheme)
        new.setCheckable(False)
        new.setToolTip(_tr("Starts a custom theme from the one in use"))
        new.clicked.connect(self.NewTheme)
        flow.addWidget(new)

        self.galleryHolder.layout().addWidget(self.gallery)

    def Refresh(self):
        # Fills the controls in from the settings
        self.updating = True
        mode = Theme.Mode()
        self.BuildGallery()

        custom = Theme.CustomThemeName()
        self.editing = Theme.CustomThemes().get(custom)
        # Presets and custom themes come with their own accent
        hasAccent = mode in (THEME_DARK, THEME_LIGHT, THEME_SYSTEM)
        self.accentRow.setVisible(hasAccent)
        accent = QColor(SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT))
        self.accentButton.setColor(accent.name())
        self.UpdateAccent()
        self.editor.setVisible(self.editing is not None)

        if self.editing:
            self.editor.titleLabel.setText(_tr("Customize {0}").format(self.editing["name"]))
            for key, button in self.colorButtons.items():
                button.setColor(self.editing["colors"][key])
            self.UpdateResetButtons()
            self.radiusSlider.setValue(self.editing["radius"])
            self.radiusLabel.setText(f"{self.editing['radius']} px")
            self.spacingSelect.setCurrentIndex(self.spacingSelect.findData(self.editing["spacing"]))
            font = self.fontSelect.findData(self.editing["font"])
            if font < 0:
                # A font from a shared theme that isn't installed here
                self.fontSelect.addItem(self.editing["font"], self.editing["font"])
                font = self.fontSelect.count() - 1
            self.fontSelect.setCurrentIndex(font)
        NoDefaultButtons(self)
        self.updating = False

    def UpdateAccent(self):
        accent = QColor(SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT))
        for swatch in self.swatches:
            swatch.setChecked(swatch.color == accent)
        self.accentRow.SetChanged(accent != QColor(DEFAULT_ACCENT))

    def UpdateResetButtons(self):
        # Reset buttons only show for colors that differ from the default
        if self.editing is None:
            return
        defaults = DefaultColors(self.editing["colors"])
        changed = False
        for key, row in self.colorRows.items():
            differs = QColor(self.editing["colors"][key]) != QColor(defaults[key])
            row.SetChanged(differs)
            changed = changed or differs
        self.resetColorsButton.setEnabled(changed)

    def CardMenu(self, card, name, pos):
        menu = QMenu(self)
        menu.addAction(ThemedIcon("assets/icons/pencil.svg"), _tr("Rename..."), self.Rename)
        menu.addAction(ThemedIcon("assets/icons/cancel.svg"), _tr("Delete"), self.Delete)
        if Theme.CustomThemeName() != name:
            self.SelectCustom(name)
        menu.exec(card.mapToGlobal(pos))

    # =====================================================
    # THEME SELECTION
    # =====================================================
    def ThemeSelected(self, mode):
        if self.updating:
            return
        self.SaveEdits()
        SettingsManager.Set("appearance.theme", mode)
        Theme.Apply()
        self.Refresh()

    def SelectCustom(self, name):
        SettingsManager.Set("appearance.theme", CUSTOM_PREFIX + name)
        Theme.Apply()
        self.Refresh()

    def AccentChanged(self, color):
        if self.updating or not color:
            return
        SettingsManager.Set("appearance.accent_color", color)
        self.UpdateAccent()
        Theme.Apply()
        # The cards of the built-in themes show the accent
        self.updating = True
        self.BuildGallery()
        self.updating = False

    # =====================================================
    # EDITING COLORS
    # =====================================================
    def ColorEdited(self, key, color):
        self.Edit(lambda theme: theme["colors"].__setitem__(key, color))
        self.UpdateResetButtons()

    def ResetColor(self, key):
        if self.editing is None:
            return
        self.colorButtons[key].setColor(DefaultColors(self.editing["colors"])[key])

    def ResetAllColors(self):
        if self.editing is None:
            return
        answer = QMessageBox.question(
            self,
            _tr("Reset all colors"),
            _tr('Reset every color of "{0}" to default?').format(self.editing["name"]),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Taken once up front: resetting the background could otherwise
        # switch which built-in theme the remaining colors come from
        defaults = DefaultColors(self.editing["colors"])
        for key, button in self.colorButtons.items():
            button.setColor(defaults[key])

    def Edit(self, change):
        # Changes the custom theme being edited, then saves and applies it
        # once the edits stop for a moment
        if self.updating or self.editing is None:
            return
        change(self.editing)
        self.applyTimer.start()

    def SaveEdits(self):
        if self.applyTimer.isActive():
            self.applyTimer.stop()
        if self.editing is None:
            return
        Theme.SaveCustomTheme(self.editing)
        Theme.Apply()
        # Its card shows its colors
        if not self.updating:
            self.updating = True
            self.BuildGallery()
            self.updating = False

    # =====================================================
    # MANAGING THEMES
    # =====================================================
    def AskName(self, title, name):
        name, ok = QInputDialog.getText(
            self, title, _tr("Theme name"), QLineEdit.EchoMode.Normal, name
        )
        name = name.strip()
        return name if ok and name else None

    def NewTheme(self):
        self.SaveEdits()
        current = Theme.Current()
        name = self.AskName(
            _tr("New custom theme"),
            Theme.UniqueName(_tr("{0} (custom)").format(current["name"])),
        )
        if not name:
            return
        theme = dict(current, name=Theme.UniqueName(name), colors=dict(current["colors"]))
        Theme.SaveCustomTheme(theme)
        self.SelectCustom(theme["name"])

    def Rename(self):
        if self.editing is None:
            return
        self.SaveEdits()
        oldName = self.editing["name"]
        name = self.AskName(_tr("Rename theme"), oldName)
        if not name or name == oldName:
            return
        theme = dict(self.editing, name=Theme.UniqueName(name))
        Theme.SaveCustomTheme(theme, oldName)
        self.SelectCustom(theme["name"])

    def Delete(self):
        if self.editing is None:
            return
        name = self.editing["name"]
        answer = QMessageBox.question(
            self, _tr("Delete theme"), _tr('Delete the theme "{0}"?').format(name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.applyTimer.stop()
        self.editing = None
        Theme.DeleteCustomTheme(name)
        SettingsManager.Set("appearance.theme", THEME_DARK)
        Theme.Apply()
        self.Refresh()

    # =====================================================
    # IMPORT AND EXPORT
    # =====================================================
    def Import(self):
        self.SaveEdits()
        path, _ = QFileDialog.getOpenFileName(
            self, _tr("Import theme"), "", _tr("HyperDrive theme") + " (*.json)"
        )
        if not path:
            return
        try:
            theme = ImportTheme(path)
        except ValueError as e:
            logger.error(f"Could not import theme {path}: {e}")
            QMessageBox.warning(
                self, _tr("Import theme"), _tr("This file isn't a HyperDrive theme.")
            )
            return
        theme["name"] = Theme.UniqueName(theme["name"])
        Theme.SaveCustomTheme(theme)
        self.SelectCustom(theme["name"])

    def Export(self):
        self.SaveEdits()
        theme = Theme.Current()
        path, _ = QFileDialog.getSaveFileName(
            self,
            _tr("Export theme"),
            f"{theme['name']}.json",
            _tr("HyperDrive theme") + " (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            ExportTheme(theme, path)
        except OSError as e:
            logger.error(f"Could not export theme to {path}: {e}")
            QMessageBox.warning(
                self, _tr("Export theme"), _tr("The theme could not be saved.") + f"\n\n{e}"
            )
