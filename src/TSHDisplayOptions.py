from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .SettingsManager import SettingsManager
from .TSHTheme import ThemedIcon


def PlayerDisplayElements():
    """The player fields that can be shown or hidden, as
    [label, object names of the widgets, setting key]. Same as the
    scoreboard's and commentary's display options."""
    return [
        [QApplication.translate("app", "Real Name"), ["real_name"], "show_name"],
        [QApplication.translate("app", "Twitter"), ["twitter", "twitterLabel"], "show_social"],
        [QApplication.translate("app", "Seed"), ["seed", "seedLabel"], "show_seed"],
        [QApplication.translate("app", "Birthday"), ["birthday"], "show_birthday"],
        [
            QApplication.translate("app", "Location"),
            ["locationLabel", "state", "country"],
            "show_location",
        ],
        [QApplication.translate("app", "Characters"), ["characters"], "show_characters"],
        [QApplication.translate("app", "Pronouns"), ["pronoun"], "show_pronouns"],
        [
            QApplication.translate("app", "Additional information"),
            ["custom_textbox"],
            "show_additional",
        ],
    ]


def ApplyHiddenElements(playerWidget, hidden):
    """Shows or hides a player widget's fields: hidden is the set of
    object names to hide, everything else from the list is shown."""
    for element in PlayerDisplayElements():
        for name in element[1]:
            widget = playerWidget.findChild(QWidget, name)
            if widget is not None:
                widget.setVisible(name not in hidden)


class TSHDisplayOptionsButton(QToolButton):
    """The eye button with a menu of the player fields to show.

    Choices are saved under settingsKey, so each widget using one keeps its
    own; until a field is changed here it follows the default from the
    settings (display_options)."""

    changed = Signal()

    def __init__(self, settingsKey, parent=None):
        super().__init__(parent)
        self.settingsKey = settingsKey
        self.elements = PlayerDisplayElements()

        self.setIcon(ThemedIcon("assets/icons/eye.svg"))
        self.setToolTip(QApplication.translate("app", "Display options"))
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        self.setMenu(menu)

        menu.addSection(QApplication.translate("app", "Players"))
        self.actions_ = []
        for element in self.elements:
            action: QAction = menu.addAction(element[0])
            action.setCheckable(True)
            action.setChecked(self.IsShown(element[2]))
            action.toggled.connect(lambda checked, key=element[2]: self.Toggled(key, checked))
            self.actions_.append(action)

    def IsShown(self, key):
        return bool(
            SettingsManager.Get(
                f"{self.settingsKey}.{key}", SettingsManager.Get(f"display_options.{key}", True)
            )
        )

    def Toggled(self, key, checked):
        SettingsManager.Set(f"{self.settingsKey}.{key}", checked)
        self.changed.emit()

    def HiddenElements(self):
        """The object names of the fields that are hidden."""
        hidden = set()
        for element, action in zip(self.elements, self.actions_):
            if not action.isChecked():
                hidden.update(element[1])
        return hidden
