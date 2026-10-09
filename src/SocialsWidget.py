import os

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers import SocialsHelper
from .Theme import SetLabelIcon, ThemedIcon

# A copy of the icons is in layout/icons for the layouts; the app doesn't
# load files from the layout folder
ICONS_DIR = "./assets/icons/socials"


def PlatformIcon(platform):
    """The platform's icon in the theme's colors, or None."""
    path = f"{ICONS_DIR}/{platform}.svg"
    return ThemedIcon(path) if os.path.isfile(path) else None


def SetPlatformIcon(label: QLabel, platform):
    """Shows the platform's icon in label instead of its text, with the
    platform's name as tooltip. Returns False when it has no icon."""
    icon = PlatformIcon(platform)
    if icon is None:
        return False
    SetLabelIcon(label, f"{ICONS_DIR}/{platform}.svg", SocialsHelper.Label(platform))
    return True


class SocialsDialog(QDialog):
    """Edits a player's socials, one field per platform."""

    def __init__(self, socials, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QApplication.translate("app", "Socials"))
        self.setMinimumWidth(320)

        socials = SocialsHelper.Clean(socials)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.edits = {}
        # The known platforms, then any other one the player has
        platforms = SocialsHelper.PLATFORM_KEYS + [
            p for p in socials if p not in SocialsHelper.PLATFORM_KEYS
        ]
        for platform in platforms:
            name = SocialsHelper.Label(platform)
            edit = QLineEdit(socials.get(platform, ""))
            edit.setObjectName(f"social_{platform}")
            edit.setPlaceholderText(name)
            edit.setToolTip(name)

            # The platform's icon, or its name for one without an icon
            label = QLabel(name)
            SetPlatformIcon(label, platform)
            label.setBuddy(edit)
            form.addRow(label, edit)
            self.edits[platform] = edit

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def Socials(self):
        return SocialsHelper.Clean({p: edit.text() for p, edit in self.edits.items()})


class SocialsButton(QToolButton):
    """The button next to a player's Twitter field that edits their other
    socials. Twitter stays in its own field; this keeps the others.

    changed is emitted when any of them, Twitter included, changes."""

    changed = Signal()

    def __init__(self, twitterEdit: QLineEdit, parent=None):
        super().__init__(parent)
        self.setObjectName("socials")
        self.twitterEdit = twitterEdit
        self.others = {}

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(28)
        self.clicked.connect(self.Edit)
        twitterEdit.editingFinished.connect(self.Changed)
        self.UpdateText()

    @staticmethod
    def Attach(twitterEdit: QLineEdit):
        """Creates a button and places it right of twitterEdit, wherever that
        is in its parent's layout."""
        button = SocialsButton(twitterEdit, twitterEdit.parentWidget())
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        layout = twitterEdit.parentWidget().layout()
        container = SocialsButton._FindLayout(layout, twitterEdit)
        if container is None:
            return button

        if isinstance(container, QGridLayout):
            index = container.indexOf(twitterEdit)
            r, c, rs, cs = container.getItemPosition(index)
            container.removeWidget(twitterEdit)
            container.addLayout(row, r, c, rs, cs)
        elif isinstance(container, QFormLayout):
            r, role = container.getWidgetPosition(twitterEdit)
            container.removeWidget(twitterEdit)
            container.setLayout(r, role, row)
        elif isinstance(container, QBoxLayout):
            index = container.indexOf(twitterEdit)
            stretch = container.stretch(index)
            container.removeWidget(twitterEdit)
            container.insertLayout(index, row, stretch)
        row.addWidget(twitterEdit)
        row.addWidget(button)
        return button

    @staticmethod
    def _FindLayout(layout, widget):
        """The layout, layout or one inside it, that holds widget."""
        if layout is None:
            return None
        if layout.indexOf(widget) >= 0:
            return layout
        for i in range(layout.count()):
            child = layout.itemAt(i).layout()
            found = SocialsButton._FindLayout(child, widget)
            if found is not None:
                return found
        return None

    def Socials(self):
        """Every social, Twitter first."""
        socials = {"twitter": self.twitterEdit.text()}
        socials.update(self.others)
        return SocialsHelper.Clean(socials)

    def Others(self):
        return dict(self.others)

    def SetOthers(self, others):
        """Replaces the socials other than Twitter."""
        others = SocialsHelper.Clean(others)
        others.pop("twitter", None)
        if others != self.others:
            self.others = others
            self.Changed()

    def MergeOthers(self, socials):
        """Adds socials' platforms other than Twitter, keeping the ones only
        this player has."""
        self.SetOthers(SocialsHelper.Merge(self.others, socials))

    def Clear(self):
        self.SetOthers({})

    def Edit(self):
        dialog = SocialsDialog(self.Socials(), self.window())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        socials = dialog.Socials()
        twitter = socials.pop("twitter", "")
        self.others = socials
        if twitter != self.twitterEdit.text():
            self.twitterEdit.setText(twitter)
            # Exports twitter, and Changed() through the connection above
            self.twitterEdit.editingFinished.emit()
        else:
            self.Changed()

    def Changed(self):
        self.UpdateText()
        self.changed.emit()

    def UpdateText(self):
        self.setText(f"+{len(self.others)}" if self.others else "+")
        lines = [f"{SocialsHelper.Label(p)}: {handle}" for p, handle in self.Socials().items()]
        tip = QApplication.translate("app", "Other socials (Twitch, YouTube, Instagram...)")
        self.setToolTip("\n".join([tip] + lines))
