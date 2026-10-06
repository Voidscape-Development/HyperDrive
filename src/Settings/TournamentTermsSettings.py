from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..Helpers.LocaleHelper import TERM_KINDS, LocaleHelper

# Edits are saved after this long without another change, so typing a name
# doesn't rewrite the file and refill the dropdowns on every key
SAVE_DELAY_MS = 400

COLUMN_DEFAULT = 0
COLUMN_CUSTOM = 1


class TermsEditor(QWidget):
    """Edits the match or phase names: a table to rename the built-in ones
    and a list of extra names to add to the dropdowns"""

    changed = Signal()

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.updating = False

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            [
                QApplication.translate("settings.tournament_terms", "Default"),
                QApplication.translate("settings.tournament_terms", "Custom"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.itemChanged.connect(self.ItemChanged)
        layout.addWidget(self.table, 1)

        layout.addWidget(
            QLabel(
                QApplication.translate(
                    "settings.tournament_terms", "Extra names to list in the dropdowns"
                )
            )
        )

        self.extraList = QListWidget()
        self.extraList.setMaximumHeight(140)
        self.extraList.itemChanged.connect(self.ItemChanged)
        self.extraList.itemDelegate().closeEditor.connect(self.ExtraEditorClosed)
        layout.addWidget(self.extraList)

        buttons = QHBoxLayout()
        addButton = QPushButton(QApplication.translate("settings.tournament_terms", "Add"))
        addButton.clicked.connect(self.AddExtra)
        buttons.addWidget(addButton)
        removeButton = QPushButton(QApplication.translate("settings.tournament_terms", "Remove"))
        removeButton.clicked.connect(self.RemoveExtra)
        buttons.addWidget(removeButton)
        buttons.addStretch()
        layout.addLayout(buttons)

    def Fill(self, terms: dict):
        self.updating = True
        try:
            defaults = LocaleHelper.defaultNames.get(self.kind, {})
            overrides = terms.get(self.kind, {})
            # Names the user gave to keys HyperDrive doesn't have are kept too
            keys = list(defaults) + [k for k in overrides if k not in defaults]

            self.table.setRowCount(len(keys))
            for row, key in enumerate(keys):
                default = QTableWidgetItem(defaults.get(key, ""))
                default.setData(Qt.ItemDataRole.UserRole, key)
                default.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                default.setToolTip(key)
                self.table.setItem(row, COLUMN_DEFAULT, default)

                custom = QTableWidgetItem(overrides.get(key, ""))
                custom.setToolTip(key)
                self.table.setItem(row, COLUMN_CUSTOM, custom)

            self.extraList.clear()
            for name in terms.get(f"custom_{self.kind}", []):
                self.AddExtraItem(name)
        finally:
            self.updating = False

    def Overrides(self) -> dict:
        overrides = {}
        for row in range(self.table.rowCount()):
            key = self.table.item(row, COLUMN_DEFAULT).data(Qt.ItemDataRole.UserRole)
            value = self.table.item(row, COLUMN_CUSTOM).text().strip()
            if value:
                overrides[key] = value
        return overrides

    def Extras(self) -> list:
        return [self.extraList.item(i).text() for i in range(self.extraList.count())]

    def ItemChanged(self, item=None):
        if not self.updating:
            self.changed.emit()

    def AddExtraItem(self, name: str) -> QListWidgetItem:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.extraList.addItem(item)
        return item

    def AddExtra(self):
        self.updating = True
        item = self.AddExtraItem("")
        self.updating = False
        self.extraList.setCurrentItem(item)
        self.extraList.editItem(item)

    def ExtraEditorClosed(self, editor=None, hint=None):
        # Drop names that were added and left empty
        self.updating = True
        for i in reversed(range(self.extraList.count())):
            if not self.extraList.item(i).text().strip():
                self.extraList.takeItem(i)
        self.updating = False
        self.changed.emit()

    def RemoveExtra(self):
        row = self.extraList.currentRow()
        if row >= 0:
            self.extraList.takeItem(row)
            self.changed.emit()


class TournamentTermsSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.saveTimer = QTimer(self)
        self.saveTimer.setSingleShot(True)
        self.saveTimer.setInterval(SAVE_DELAY_MS)
        self.saveTimer.timeout.connect(self.Save)

        layout = QVBoxLayout(self)

        hint = QLabel(
            QApplication.translate(
                "settings.tournament_terms",
                "Rename the match and phase names HyperDrive uses in the scoreboard dropdowns "
                "and for sets loaded from start.gg. Leave a custom name empty to use the "
                "default. {0} is replaced with a number or letter, like the round number.",
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        tabNames = {
            "match": QApplication.translate("settings.tournament_terms", "Match names"),
            "phase": QApplication.translate("settings.tournament_terms", "Phase names"),
        }
        self.editors: dict[str, TermsEditor] = {}
        for kind in TERM_KINDS:
            editor = TermsEditor(kind)
            editor.changed.connect(self.saveTimer.start)
            self.editors[kind] = editor
            self.tabs.addTab(editor, tabNames[kind])

        bottom = QHBoxLayout()
        bottom.addStretch()
        resetButton = QPushButton(
            QApplication.translate("settings.tournament_terms", "Reset all to default")
        )
        resetButton.clicked.connect(self.ResetAll)
        bottom.addWidget(resetButton)
        layout.addLayout(bottom)

        self.Fill(LocaleHelper.customTerms or LocaleHelper.LoadCustomTerms())

    def Fill(self, terms: dict):
        terms = LocaleHelper.NormalizeCustomTerms(terms)
        for editor in self.editors.values():
            editor.Fill(terms)

    def Terms(self) -> dict:
        terms = {}
        for kind, editor in self.editors.items():
            terms[kind] = editor.Overrides()
            terms[f"custom_{kind}"] = editor.Extras()
        return terms

    def Save(self):
        self.saveTimer.stop()
        if not LocaleHelper.SaveCustomTerms(self.Terms()):
            QMessageBox.warning(
                self,
                QApplication.translate("app", "Error"),
                QApplication.translate(
                    "settings.tournament_terms", "The match and phase names couldn't be saved."
                ),
            )

    def ResetAll(self):
        answer = QMessageBox.question(
            self,
            QApplication.translate("settings.tournament_terms", "Reset all to default"),
            QApplication.translate(
                "settings.tournament_terms",
                "Remove all of your custom match and phase names?",
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.Fill({})
            self.Save()

    def hideEvent(self, event):
        # Save edits still waiting on the timer when the window closes
        if self.saveTimer.isActive():
            self.Save()
        super().hideEvent(event)
