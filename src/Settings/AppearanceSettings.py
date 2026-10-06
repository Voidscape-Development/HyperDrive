from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..ColorButton import ColorButton
from ..SettingsManager import SettingsManager
from ..Theme import (
    COLOR_KEYS,
    CUSTOM_PREFIX,
    DEFAULT_ACCENT,
    DEFAULT_UI_SCALE,
    MAX_RADIUS,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    UI_SCALES,
    ColorLabels,
    DefaultColors,
    ExportTheme,
    ImportTheme,
    SpacingLabels,
    Theme,
    ThemedIcon,
)

# Edits are saved and applied after this long without another change, so
# dragging the roundness slider doesn't restyle the app on every step
APPLY_DELAY_MS = 150


class AppearanceSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editing = None  # the custom theme being edited, as a theme dict
        self.updating = False  # set while the controls are being filled in

        self.applyTimer = QTimer(self)
        self.applyTimer.setSingleShot(True)
        self.applyTimer.setInterval(APPLY_DELAY_MS)
        self.applyTimer.timeout.connect(self.SaveEdits)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        form = QGridLayout()
        layout.addLayout(form)

        form.addWidget(QLabel(QApplication.translate("settings.appearance", "Theme")), 0, 0)
        self.themeSelect = QComboBox()
        self.themeSelect.currentIndexChanged.connect(self.ThemeSelected)
        form.addWidget(self.themeSelect, 0, 1)

        self.accentLabel = QLabel(QApplication.translate("settings.appearance", "Accent color"))
        form.addWidget(self.accentLabel, 1, 0)
        self.accentButton = ColorButton(
            color=SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT),
            disable_right_click=True,
        )
        self.accentButton.colorChanged.connect(self.AccentChanged)
        self.accentReset = self.ResetButton(
            QApplication.translate("settings.appearance", "Reset the accent color to default")
        )
        self.accentReset.clicked.connect(lambda: self.accentButton.setColor(DEFAULT_ACCENT))
        accent = QHBoxLayout()
        accent.addWidget(self.accentButton)
        accent.addWidget(self.accentReset)
        form.addLayout(accent, 1, 1, Qt.AlignmentFlag.AlignLeft)

        form.addWidget(
            QLabel(
                QApplication.translate(
                    "settings.appearance", "UI scale (takes effect on next restart)"
                )
            ),
            2,
            0,
        )
        self.scaleSelect = QComboBox()
        for scale in UI_SCALES:
            self.scaleSelect.addItem(f"{scale}%", scale)
        current = self.scaleSelect.findData(
            SettingsManager.Get("appearance.ui_scale", DEFAULT_UI_SCALE)
        )
        self.scaleSelect.setCurrentIndex(
            current if current >= 0 else self.scaleSelect.findData(DEFAULT_UI_SCALE)
        )
        self.scaleSelect.currentIndexChanged.connect(
            lambda i: SettingsManager.Set("appearance.ui_scale", self.scaleSelect.currentData())
        )
        form.addWidget(self.scaleSelect, 2, 1)
        form.setColumnStretch(2, 1)

        # Managing custom themes
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.newButton = QPushButton(
            QApplication.translate("settings.appearance", "New custom theme...")
        )
        self.newButton.setToolTip(
            QApplication.translate(
                "settings.appearance", "Starts a custom theme from the one in use"
            )
        )
        self.newButton.clicked.connect(self.NewTheme)
        buttons.addWidget(self.newButton)
        self.importButton = QPushButton(QApplication.translate("settings.appearance", "Import..."))
        self.importButton.clicked.connect(self.Import)
        buttons.addWidget(self.importButton)
        self.exportButton = QPushButton(QApplication.translate("settings.appearance", "Export..."))
        self.exportButton.setToolTip(
            QApplication.translate(
                "settings.appearance", "Saves the theme in use to a file you can share"
            )
        )
        self.exportButton.clicked.connect(self.Export)
        buttons.addWidget(self.exportButton)
        self.renameButton = QPushButton(QApplication.translate("settings.appearance", "Rename..."))
        self.renameButton.clicked.connect(self.Rename)
        buttons.addWidget(self.renameButton)
        self.deleteButton = QPushButton(QApplication.translate("settings.appearance", "Delete"))
        self.deleteButton.clicked.connect(self.Delete)
        buttons.addWidget(self.deleteButton)
        buttons.addStretch()

        # The custom theme editor
        self.editor = QGroupBox()
        layout.addWidget(self.editor)
        editorLayout = QGridLayout(self.editor)

        self.colorButtons = {}
        self.colorResets = {}
        labels = ColorLabels()
        for i, key in enumerate(COLOR_KEYS):
            row, column = i // 2, (i % 2) * 2
            editorLayout.addWidget(QLabel(labels[key]), row, column)
            button = ColorButton(disable_right_click=True)
            button.colorChanged.connect(lambda color, key=key: self.ColorEdited(key, color))
            reset = self.ResetButton(
                QApplication.translate("settings.appearance", 'Reset "{0}" to default').format(
                    labels[key]
                )
            )
            reset.clicked.connect(lambda checked=False, key=key: self.ResetColor(key))
            cell = QHBoxLayout()
            cell.addWidget(button)
            cell.addWidget(reset)
            editorLayout.addLayout(cell, row, column + 1, Qt.AlignmentFlag.AlignLeft)
            self.colorButtons[key] = button
            self.colorResets[key] = reset

        row = (len(COLOR_KEYS) + 1) // 2
        self.resetColorsButton = QPushButton(
            QApplication.translate("settings.appearance", "Reset all colors")
        )
        self.resetColorsButton.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.resetColorsButton.setToolTip(
            QApplication.translate(
                "settings.appearance",
                "Resets every color to the built-in Dark or Light theme, whichever this theme is closest to",
            )
        )
        self.resetColorsButton.clicked.connect(self.ResetAllColors)
        editorLayout.addWidget(self.resetColorsButton, row, 0, 1, 2, Qt.AlignmentFlag.AlignLeft)
        row += 1
        editorLayout.addWidget(
            QLabel(QApplication.translate("settings.appearance", "Corner roundness")), row, 0
        )
        roundness = QHBoxLayout()
        self.radiusSlider = QSlider(Qt.Orientation.Horizontal)
        self.radiusSlider.setRange(0, MAX_RADIUS)
        self.radiusLabel = QLabel()
        self.radiusLabel.setMinimumWidth(40)
        self.radiusSlider.valueChanged.connect(
            lambda value: [
                self.radiusLabel.setText(f"{value} px"),
                self.Edit(lambda theme: theme.__setitem__("radius", value)),
            ]
        )
        roundness.addWidget(self.radiusSlider)
        roundness.addWidget(self.radiusLabel)
        editorLayout.addLayout(roundness, row, 1, 1, 3)

        editorLayout.addWidget(
            QLabel(QApplication.translate("settings.appearance", "Spacing")), row + 1, 0
        )
        self.spacingSelect = QComboBox()
        for value, label in SpacingLabels().items():
            self.spacingSelect.addItem(label, value)
        self.spacingSelect.currentIndexChanged.connect(
            lambda i: self.Edit(
                lambda theme: theme.__setitem__("spacing", self.spacingSelect.currentData())
            )
        )
        editorLayout.addWidget(self.spacingSelect, row + 1, 1, 1, 3)

        editorLayout.addWidget(
            QLabel(QApplication.translate("settings.appearance", "Font")), row + 2, 0
        )
        self.fontSelect = QComboBox()
        self.fontSelect.setMaxVisibleItems(20)
        self.fontSelect.addItem(QApplication.translate("settings.appearance", "System default"), "")
        for family in QFontDatabase.families():
            self.fontSelect.addItem(family, family)
        self.fontSelect.currentIndexChanged.connect(
            lambda i: self.Edit(
                lambda theme: theme.__setitem__("font", self.fontSelect.currentData())
            )
        )
        editorLayout.addWidget(self.fontSelect, row + 2, 1, 1, 3)
        editorLayout.setColumnStretch(3, 1)

        self.Refresh()

    def Refresh(self):
        # Fills the controls in from the settings
        self.updating = True
        mode = Theme.Mode()

        self.themeSelect.clear()
        self.themeSelect.addItem(QApplication.translate("settings.appearance", "Dark"), THEME_DARK)
        self.themeSelect.addItem(
            QApplication.translate("settings.appearance", "Light"), THEME_LIGHT
        )
        self.themeSelect.addItem(
            QApplication.translate("settings.appearance", "Follow system"), THEME_SYSTEM
        )
        customThemes = Theme.CustomThemes()
        if customThemes:
            self.themeSelect.insertSeparator(self.themeSelect.count())
            for name in sorted(customThemes, key=str.lower):
                self.themeSelect.addItem(name, CUSTOM_PREFIX + name)
        self.themeSelect.setCurrentIndex(max(self.themeSelect.findData(mode), 0))

        custom = Theme.CustomThemeName()
        self.editing = customThemes.get(custom)
        builtin = self.editing is None
        self.accentLabel.setVisible(builtin)
        self.accentButton.setVisible(builtin)
        self.accentReset.setVisible(builtin)
        self.accentReset.setEnabled(
            QColor(SettingsManager.Get("appearance.accent_color", DEFAULT_ACCENT))
            != QColor(DEFAULT_ACCENT)
        )
        self.renameButton.setEnabled(not builtin)
        self.deleteButton.setEnabled(not builtin)
        self.editor.setVisible(not builtin)

        if self.editing:
            self.editor.setTitle(
                QApplication.translate("settings.appearance", "Customize {0}").format(
                    self.editing["name"]
                )
            )
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
        self.updating = False

    def ThemeSelected(self, index):
        if self.updating:
            return
        self.SaveEdits()
        SettingsManager.Set("appearance.theme", self.themeSelect.currentData())
        Theme.Apply()
        self.Refresh()

    def AccentChanged(self, color):
        if self.updating or not color:
            return
        SettingsManager.Set("appearance.accent_color", color)
        self.accentReset.setEnabled(QColor(color) != QColor(DEFAULT_ACCENT))
        Theme.Apply()

    def ResetButton(self, tooltip):
        button = QToolButton()
        button.setIcon(ThemedIcon("assets/icons/undo.svg"))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        return button

    def ColorEdited(self, key, color):
        self.Edit(lambda theme: theme["colors"].__setitem__(key, color))
        self.UpdateResetButtons()

    def UpdateResetButtons(self):
        # Reset buttons are only enabled for colors that differ from the default
        if self.editing is None:
            return
        defaults = DefaultColors(self.editing["colors"])
        changed = False
        for key, reset in self.colorResets.items():
            differs = QColor(self.editing["colors"][key]) != QColor(defaults[key])
            reset.setEnabled(differs)
            changed = changed or differs
        self.resetColorsButton.setEnabled(changed)

    def ResetColor(self, key):
        if self.editing is None:
            return
        self.colorButtons[key].setColor(DefaultColors(self.editing["colors"])[key])

    def ResetAllColors(self):
        if self.editing is None:
            return
        answer = QMessageBox.question(
            self,
            QApplication.translate("settings.appearance", "Reset all colors"),
            QApplication.translate(
                "settings.appearance", 'Reset every color of "{0}" to default?'
            ).format(self.editing["name"]),
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

    def SelectCustom(self, name):
        SettingsManager.Set("appearance.theme", CUSTOM_PREFIX + name)
        Theme.Apply()
        self.Refresh()

    def AskName(self, title, name):
        name, ok = QInputDialog.getText(
            self,
            title,
            QApplication.translate("settings.appearance", "Theme name"),
            QLineEdit.EchoMode.Normal,
            name,
        )
        name = name.strip()
        return name if ok and name else None

    def NewTheme(self):
        self.SaveEdits()
        current = Theme.Current()
        name = self.AskName(
            QApplication.translate("settings.appearance", "New custom theme"),
            Theme.UniqueName(
                QApplication.translate("settings.appearance", "{0} (custom)").format(
                    current["name"]
                )
            ),
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
        name = self.AskName(QApplication.translate("settings.appearance", "Rename theme"), oldName)
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
            self,
            QApplication.translate("settings.appearance", "Delete theme"),
            QApplication.translate("settings.appearance", 'Delete the theme "{0}"?').format(name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.applyTimer.stop()
        self.editing = None
        Theme.DeleteCustomTheme(name)
        SettingsManager.Set("appearance.theme", THEME_DARK)
        Theme.Apply()
        self.Refresh()

    def Import(self):
        self.SaveEdits()
        path, _ = QFileDialog.getOpenFileName(
            self,
            QApplication.translate("settings.appearance", "Import theme"),
            "",
            QApplication.translate("settings.appearance", "HyperDrive theme") + " (*.json)",
        )
        if not path:
            return
        try:
            theme = ImportTheme(path)
        except ValueError as e:
            logger.error(f"Could not import theme {path}: {e}")
            QMessageBox.warning(
                self,
                QApplication.translate("settings.appearance", "Import theme"),
                QApplication.translate(
                    "settings.appearance", "This file isn't a HyperDrive theme."
                ),
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
            QApplication.translate("settings.appearance", "Export theme"),
            f"{theme['name']}.json",
            QApplication.translate("settings.appearance", "HyperDrive theme") + " (*.json)",
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
                self,
                QApplication.translate("settings.appearance", "Export theme"),
                QApplication.translate("settings.appearance", "The theme could not be saved.")
                + f"\n\n{e}",
            )
