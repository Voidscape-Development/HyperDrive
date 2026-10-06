import copy
import textwrap

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..ColorButton import ColorButton
from ..Theme import ThemedIcon
from .LayoutThemes import (
    DEFAULT_THEME,
    FIELD_CHECKBOX,
    FIELD_COLOR,
    FIELD_DROPDOWN,
    FIELD_FILL,
    FIELD_FONT,
    FIELD_NUMBER,
    ExportLayoutTheme,
    GradientDirectionLabels,
    ImportLayoutTheme,
    LayoutThemes,
    LayoutThemeSchema,
    NormalizeValue,
)

# Edits are saved and exported after this long without another change
APPLY_DELAY_MS = 150


class FillEditor(QWidget):
    """A color, or a linear gradient between two colors."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.color = ColorButton(disable_right_click=True, enable_alpha_selection=True)
        self.color.colorChanged.connect(lambda c: self.changed.emit())
        layout.addWidget(self.color)

        self.gradient = QCheckBox(QApplication.translate("layout_themes", "Gradient"))
        self.gradient.toggled.connect(lambda v: [self.UpdateEnabled(), self.changed.emit()])
        layout.addWidget(self.gradient)

        self.color2 = ColorButton(disable_right_click=True, enable_alpha_selection=True)
        self.color2.colorChanged.connect(lambda c: self.changed.emit())
        layout.addWidget(self.color2)

        self.direction = QComboBox()
        for value, label in GradientDirectionLabels():
            self.direction.addItem(label, value)
        self.direction.currentIndexChanged.connect(lambda i: self.changed.emit())
        layout.addWidget(self.direction)
        layout.addStretch()

        self.UpdateEnabled()

    def UpdateEnabled(self):
        self.color2.setEnabled(self.gradient.isChecked())
        self.direction.setEnabled(self.gradient.isChecked())

    def Value(self):
        return {
            "color": self.color.color(),
            "color2": self.color2.color(),
            "gradient": self.gradient.isChecked(),
            "direction": self.direction.currentData(),
        }

    def SetValue(self, value):
        for w in (self.color, self.color2, self.gradient, self.direction):
            w.blockSignals(True)
        self.color.setColor(value["color"])
        self.color2.setColor(value["color2"])
        self.gradient.setChecked(value["gradient"])
        self.direction.setCurrentIndex(max(self.direction.findData(value["direction"]), 0))
        for w in (self.color, self.color2, self.gradient, self.direction):
            w.blockSignals(False)
        self.UpdateEnabled()


class FieldEditor:
    """The control for one theme field, with a way to read and fill it."""

    def __init__(self, field, onChange):
        self.field = field
        type = field.type

        if type == FIELD_CHECKBOX:
            self.widget = QCheckBox()
            self.widget.toggled.connect(lambda v: onChange())
            self.get = self.widget.isChecked
            self.set = self.widget.setChecked
        elif type == FIELD_COLOR:
            self.widget = ColorButton(disable_right_click=True, enable_alpha_selection=True)
            self.widget.colorChanged.connect(lambda c: onChange())
            self.get = self.widget.color
            self.set = self.widget.setColor
        elif type == FIELD_FILL:
            self.widget = FillEditor()
            self.widget.changed.connect(onChange)
            self.get = self.widget.Value
            self.set = self.widget.SetValue
        elif type == FIELD_DROPDOWN:
            self.widget = QComboBox()
            for value, label in field.options:
                self.widget.addItem(label, value)
            self.widget.currentIndexChanged.connect(lambda i: onChange())
            self.get = self.widget.currentData
            self.set = lambda v: self.widget.setCurrentIndex(max(self.widget.findData(v), 0))
        elif type == FIELD_NUMBER:
            self.widget = QSpinBox()
            self.widget.setRange(field.minimum, field.maximum)
            if field.suffix:
                self.widget.setSuffix(" " + field.suffix)
            self.widget.valueChanged.connect(lambda v: onChange())
            self.get = self.widget.value
            self.set = self.widget.setValue
        elif type == FIELD_FONT:
            self.widget = QComboBox()
            self.widget.setMaxVisibleItems(20)
            self.widget.addItem(QApplication.translate("layout_themes", "Layout default"), "")
            for family in QFontDatabase.families():
                self.widget.addItem(family, family)
            self.widget.currentIndexChanged.connect(lambda i: onChange())
            self.get = self.widget.currentData
            self.set = self.SetFont
        else:
            self.widget = QLineEdit()
            self.widget.textChanged.connect(lambda t: onChange())
            self.get = self.widget.text
            self.set = self.widget.setText

        if field.tooltip:
            self.widget.setToolTip("\n".join(textwrap.wrap(field.tooltip, 40)))

    def SetFont(self, family):
        index = self.widget.findData(family)
        if index < 0:
            # A font from a shared theme that isn't installed here
            self.widget.addItem(family, family)
            index = self.widget.count() - 1
        self.widget.setCurrentIndex(index)

    def Fill(self, value):
        self.widget.blockSignals(True)
        try:
            self.set(value)
        finally:
            self.widget.blockSignals(False)


class LayoutThemeWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(QApplication.translate("layout_themes", "Layout Themes"))

        self.editing = None  # the user theme being edited, as a theme dict
        self.updating = False  # set while the controls are being filled in

        self.applyTimer = QTimer(self)
        self.applyTimer.setSingleShot(True)
        self.applyTimer.setInterval(APPLY_DELAY_MS)
        self.applyTimer.timeout.connect(self.SaveEdits)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        layout.addLayout(top)
        top.addWidget(QLabel(QApplication.translate("layout_themes", "Theme")))
        self.themeSelect = QComboBox()
        self.themeSelect.setMinimumWidth(200)
        self.themeSelect.setToolTip(
            QApplication.translate(
                "layout_themes",
                "The theme the layouts use. Changes are saved and sent to the layouts as you make them.",
            )
        )
        self.themeSelect.currentIndexChanged.connect(self.ThemeSelected)
        top.addWidget(self.themeSelect)

        self.newButton = QPushButton(QApplication.translate("layout_themes", "New theme..."))
        self.newButton.setIcon(ThemedIcon("assets/icons/save.svg"))
        self.newButton.setToolTip(
            QApplication.translate("layout_themes", "Starts a new theme from the one in use")
        )
        self.newButton.clicked.connect(self.NewTheme)
        top.addWidget(self.newButton)
        self.importButton = QPushButton(QApplication.translate("layout_themes", "Import..."))
        self.importButton.clicked.connect(self.Import)
        top.addWidget(self.importButton)
        self.exportButton = QPushButton(QApplication.translate("layout_themes", "Export..."))
        self.exportButton.setToolTip(
            QApplication.translate(
                "layout_themes", "Saves the theme in use to a file you can share"
            )
        )
        self.exportButton.clicked.connect(self.Export)
        top.addWidget(self.exportButton)
        self.renameButton = QPushButton(QApplication.translate("layout_themes", "Rename..."))
        self.renameButton.clicked.connect(self.Rename)
        top.addWidget(self.renameButton)
        self.deleteButton = QPushButton(QApplication.translate("layout_themes", "Delete"))
        self.deleteButton.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.deleteButton.clicked.connect(self.Delete)
        top.addWidget(self.deleteButton)
        top.addStretch()
        # Enter shouldn't make a new theme
        for button in (
            self.newButton,
            self.importButton,
            self.exportButton,
            self.renameButton,
            self.deleteButton,
        ):
            button.setAutoDefault(False)

        self.builtinNotice = QLabel(
            QApplication.translate(
                "layout_themes",
                "The default theme can't be changed. Create a new theme to customize it.",
            )
        )
        self.builtinNotice.setWordWrap(True)
        layout.addWidget(self.builtinNotice)

        # Sections on the left, their fields on the right
        self.sectionList = QListWidget()
        self.sectionList.currentRowChanged.connect(
            lambda row: self.sectionStack.setCurrentIndex(row)
        )
        self.sectionStack = QStackedWidget()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.sectionStack)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sectionList)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.editors = {}
        for section in LayoutThemeSchema():
            self.sectionList.addItem(section.label)
            page = QWidget()
            grid = QGridLayout(page)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop)
            for row, field in enumerate(section.fields):
                editor = FieldEditor(field, lambda s=section.key, f=field: self.Edited(s, f))
                grid.addWidget(QLabel(field.label), row, 0)
                grid.addWidget(editor.widget, row, 1, Qt.AlignmentFlag.AlignLeft)
                resetButton = QPushButton(QApplication.translate("settings", "Default"))
                resetButton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
                resetButton.clicked.connect(
                    lambda checked=False, s=section.key, f=field: self.Reset(s, f)
                )
                grid.addWidget(resetButton, row, 2)
                self.editors[(section.key, field.key)] = (editor, resetButton)
            grid.setColumnStretch(1, 1)
            self.sectionStack.addWidget(page)
        self.sectionList.setCurrentRow(0)

        self.resize(900, 520)
        splitter.setSizes([200, 700])

        self.Refresh()

    def Refresh(self):
        # Fills the controls in from the saved themes
        self.updating = True
        active = LayoutThemes.ActiveName()

        self.themeSelect.clear()
        self.themeSelect.addItem(LayoutThemes.DisplayName(DEFAULT_THEME), DEFAULT_THEME)
        userThemes = LayoutThemes.UserThemes()
        if userThemes:
            self.themeSelect.insertSeparator(self.themeSelect.count())
            for name in sorted(userThemes, key=str.lower):
                self.themeSelect.addItem(name, name)
        self.themeSelect.setCurrentIndex(max(self.themeSelect.findData(active), 0))

        theme = LayoutThemes.Active()
        builtin = LayoutThemes.IsBuiltin(active)
        self.editing = None if builtin else copy.deepcopy(theme)

        self.builtinNotice.setVisible(builtin)
        self.renameButton.setEnabled(not builtin)
        self.deleteButton.setEnabled(not builtin)

        for (sectionKey, fieldKey), (editor, resetButton) in self.editors.items():
            editor.Fill(theme["values"][sectionKey][fieldKey])
            editor.widget.setEnabled(not builtin)
            resetButton.setEnabled(not builtin)
        self.updating = False

    def Edited(self, sectionKey, field):
        if self.updating or self.editing is None:
            return
        editor, _ = self.editors[(sectionKey, field.key)]
        self.editing["values"][sectionKey][field.key] = NormalizeValue(field, editor.get())
        self.applyTimer.start()

    def Reset(self, sectionKey, field):
        if self.editing is None:
            return
        editor, _ = self.editors[(sectionKey, field.key)]
        editor.Fill(field.default)
        self.Edited(sectionKey, field)

    def SaveEdits(self):
        if self.applyTimer.isActive():
            self.applyTimer.stop()
        if self.editing is None:
            return
        LayoutThemes.SaveTheme(self.editing)

    def ThemeSelected(self, index):
        if self.updating:
            return
        self.SaveEdits()
        LayoutThemes.SetActive(self.themeSelect.currentData())
        self.Refresh()

    def SelectTheme(self, name):
        LayoutThemes.SetActive(name)
        self.Refresh()

    def AskName(self, title, name):
        name, ok = QInputDialog.getText(
            self,
            title,
            QApplication.translate("layout_themes", "Theme name"),
            QLineEdit.EchoMode.Normal,
            name,
        )
        name = name.strip()
        return name if ok and name else None

    def NewTheme(self):
        self.SaveEdits()
        current = LayoutThemes.Active()
        name = self.AskName(
            QApplication.translate("layout_themes", "New theme"),
            LayoutThemes.UniqueName(
                QApplication.translate("layout_themes", "{0} (custom)").format(
                    LayoutThemes.DisplayName(current["name"])
                )
            ),
        )
        if not name:
            return
        theme = LayoutThemes.SaveTheme(
            {
                "name": LayoutThemes.UniqueName(name),
                "values": copy.deepcopy(current["values"]),
            }
        )
        self.SelectTheme(theme["name"])

    def Rename(self):
        if self.editing is None:
            return
        self.SaveEdits()
        oldName = self.editing["name"]
        name = self.AskName(QApplication.translate("layout_themes", "Rename theme"), oldName)
        if not name or name == oldName:
            return
        theme = LayoutThemes.SaveTheme(
            dict(self.editing, name=LayoutThemes.UniqueName(name)), oldName
        )
        self.SelectTheme(theme["name"])

    def Delete(self):
        if self.editing is None:
            return
        name = self.editing["name"]
        answer = QMessageBox.question(
            self,
            QApplication.translate("layout_themes", "Delete theme"),
            QApplication.translate("layout_themes", 'Delete the theme "{0}"?').format(name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.applyTimer.stop()
        self.editing = None
        LayoutThemes.DeleteTheme(name)
        self.Refresh()

    def Import(self):
        self.SaveEdits()
        path, _ = QFileDialog.getOpenFileName(
            self,
            QApplication.translate("layout_themes", "Import theme"),
            "",
            QApplication.translate("layout_themes", "HyperDrive layout theme") + " (*.json)",
        )
        if not path:
            return
        try:
            theme = ImportLayoutTheme(path)
        except ValueError as e:
            logger.error(f"Could not import layout theme {path}: {e}")
            QMessageBox.warning(
                self,
                QApplication.translate("layout_themes", "Import theme"),
                QApplication.translate(
                    "layout_themes", "This file isn't a HyperDrive layout theme."
                ),
            )
            return
        theme["name"] = LayoutThemes.UniqueName(theme["name"])
        LayoutThemes.SaveTheme(theme)
        self.SelectTheme(theme["name"])

    def Export(self):
        self.SaveEdits()
        theme = dict(LayoutThemes.Active())
        theme["name"] = LayoutThemes.DisplayName(theme["name"])
        path, _ = QFileDialog.getSaveFileName(
            self,
            QApplication.translate("layout_themes", "Export theme"),
            f"{theme['name']}.json",
            QApplication.translate("layout_themes", "HyperDrive layout theme") + " (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            ExportLayoutTheme(theme, path)
        except OSError as e:
            logger.error(f"Could not export layout theme to {path}: {e}")
            QMessageBox.warning(
                self,
                QApplication.translate("layout_themes", "Export theme"),
                QApplication.translate("layout_themes", "The theme could not be saved.")
                + f"\n\n{e}",
            )

    def closeEvent(self, event):
        self.SaveEdits()
        super().closeEvent(event)

    def done(self, result):
        self.SaveEdits()
        super().done(result)
