# A setting saved with SettingsManager, shown as a row of a settings page
# (Controls.SettingRow) whose control saves it as it's changed.
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..ColorButton import ColorButton
from ..SettingsManager import SettingsManager
from ..Theme import ThemedIcon
from .Controls import Badge, SettingRow, ToggleSwitch

TYPE_TOGGLE = "checkbox"
TYPE_NUMBER = "spinbox"
TYPE_TEXT = "textbox"
TYPE_PASSWORD = "password"
TYPE_COLOR = "color"
TYPE_DROPDOWN = "dropdown"
TYPE_TEMPLATE = "template"

NUMBER_WIDTH = 120
TEXT_WIDTH = 280


class TemplateEdit(QWidget):
    """A text field with buttons that insert its {placeholders}"""

    textChanged = Signal(str)

    def __init__(self, tokens, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.textChanged.connect(self.textChanged)
        layout.addWidget(self.edit)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        label = QLabel(QApplication.translate("settings", "Insert"))
        label.setObjectName("settingsDescription")
        buttons.addWidget(label)
        for token in tokens:
            button = QToolButton()
            button.setText(token)
            button.setToolTip(QApplication.translate("settings", "Insert {0}").format(token))
            button.clicked.connect(lambda checked=False, t=token: self.Insert(t))
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def Insert(self, token):
        self.edit.insert(token)
        self.edit.setFocus()

    def text(self):
        return self.edit.text()

    def setText(self, text):
        self.edit.setText(text)


def SecretEdit():
    """A password field with a button that shows what's typed"""
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    action = edit.addAction(
        ThemedIcon("assets/icons/eye.svg"), QLineEdit.ActionPosition.TrailingPosition
    )
    action.setCheckable(True)
    action.setToolTip(QApplication.translate("settings", "Show"))
    action.toggled.connect(
        lambda shown: edit.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
    )
    return edit


class Setting(QObject):
    """One setting, as a row. key is its full SettingsManager key (e.g.
    "general.webserver_port"). invert shows a setting stored as "disable X"
    as an "X" switch, without changing what's saved. callback runs after
    each save. restart marks a setting that takes effect on restart."""

    # Every setting by key, so the rows of one key on two pages agree
    instances = {}

    changed = Signal()
    # After the control is filled in from the saved value
    filled = Signal()

    def __init__(
        self,
        key,
        type,
        default,
        title,
        description=None,
        callback=None,
        minimum=1,
        maximum=99999,
        suffix=None,
        invert=False,
        restart=False,
        indent=False,
        options=None,
        tokens=None,
        status=False,
        placeholder=None,
    ):
        super().__init__()
        self.key = key
        self.type = type
        self.default = default
        self.callback = callback
        self.invert = invert
        self.restart = restart
        self.loading = False

        if type == TYPE_TOGGLE:
            control = ToggleSwitch()
            control.toggled.connect(lambda v: self.Save())
        elif type == TYPE_NUMBER:
            control = QSpinBox()
            control.setRange(minimum, maximum)
            if suffix:
                control.setSuffix(" " + suffix)
            control.setFixedWidth(NUMBER_WIDTH)
            control.valueChanged.connect(lambda v: self.Save())
        elif type in (TYPE_TEXT, TYPE_PASSWORD):
            control = SecretEdit() if type == TYPE_PASSWORD else QLineEdit()
            control.setFixedWidth(TEXT_WIDTH)
            if placeholder:
                control.setPlaceholderText(placeholder)
            control.textChanged.connect(lambda t: self.Save())
        elif type == TYPE_TEMPLATE:
            control = TemplateEdit(tokens or [])
            control.setFixedWidth(TEXT_WIDTH)
            control.textChanged.connect(lambda t: self.Save())
        elif type == TYPE_COLOR:
            control = ColorButton(disable_right_click=True)
            control.colorChanged.connect(lambda c: self.Save())
        elif type == TYPE_DROPDOWN:
            control = QComboBox()
            for value, label in options:
                control.addItem(label, value)
            control.currentIndexChanged.connect(lambda i: self.Save())
        else:
            raise ValueError(f"Unknown setting type {type}")
        self.control = control

        self.row = SettingRow(title, control, description, restart=restart, indent=indent)
        self.row.resetClicked.connect(self.Reset)

        self.statusBadge = None
        if status:
            self.statusBadge = Badge("")
            self.row.titleLine.insertWidget(
                self.row.titleLine.count() - 1, self.statusBadge, 0, Qt.AlignmentFlag.AlignVCenter
            )

        Setting.instances.setdefault(key, []).append(self)
        self.Load()
        # What it was when HyperDrive started, to tell if a restart is due
        self.startValue = self.Value()

    # =====================================================
    # VALUES
    # =====================================================
    def Value(self):
        """The saved value"""
        return SettingsManager.Get(self.key, self.default)

    def Shown(self, value):
        return (not value) if self.invert else value

    def ControlValue(self):
        c = self.control
        if self.type == TYPE_TOGGLE:
            return self.Shown(c.isChecked())
        if self.type == TYPE_NUMBER:
            return c.value()
        if self.type == TYPE_COLOR:
            return c.color()
        if self.type == TYPE_DROPDOWN:
            return c.currentData()
        return c.text()

    def Fill(self, value):
        c = self.control
        c.blockSignals(True)
        try:
            if self.type == TYPE_TOGGLE:
                c.setChecked(bool(self.Shown(value)))
            elif self.type == TYPE_NUMBER:
                c.setValue(int(value))
            elif self.type == TYPE_COLOR:
                c.setColor(value)
            elif self.type == TYPE_DROPDOWN:
                c.setCurrentIndex(max(c.findData(value), 0))
            else:
                c.setText(value or "")
        finally:
            c.blockSignals(False)
        if self.type == TYPE_TOGGLE:
            c.update()
        self.UpdateState()
        self.filled.emit()

    def Load(self):
        self.loading = True
        self.Fill(self.Value())
        self.loading = False

    def IsDefault(self):
        return self.Value() == self.default

    def UpdateState(self):
        self.row.SetChanged(not self.IsDefault())
        if self.statusBadge is not None:
            self.statusBadge.setText(
                QApplication.translate("settings", "Set")
                if self.Value()
                else QApplication.translate("settings", "Not set")
            )

    # =====================================================
    # SAVING
    # =====================================================
    def Save(self):
        if self.loading:
            return
        SettingsManager.Set(self.key, self.ControlValue())
        self.UpdateState()
        for other in Setting.instances.get(self.key, []):
            if other is not self:
                other.Load()
        if callable(self.callback):
            self.callback()
        self.changed.emit()
        for other in Setting.instances.get(self.key, []):
            if other is not self:
                other.changed.emit()

    def Reset(self):
        self.Fill(self.default)
        self.Save()

    # =====================================================
    # DEPENDENCIES
    # =====================================================
    def EnabledBy(self, toggle):
        """Only editable while the toggle setting is on"""

        def update(*args):
            self.row.setEnabled(toggle.control.isChecked())

        toggle.control.toggled.connect(update)
        toggle.filled.connect(update)
        update()
        return self
