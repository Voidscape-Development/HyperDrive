from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..Helpers.PronounHelper import PronounHelper


class PronounSettings(QWidget):
    """Edits the pronouns the player fields suggest. The list shows the shared
    model, so pronouns added from the scoreboard show up here too."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = PronounHelper.Model()

        layout = QVBoxLayout(self)

        hint = QLabel(
            QApplication.translate(
                "settings.pronouns",
                "The pronouns suggested while typing in a player's pronouns field. "
                "Pronouns of players you save are added here automatically.",
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.list.itemDelegate().closeEditor.connect(self.Save)
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        addButton = QPushButton(QApplication.translate("settings.pronouns", "Add"))
        addButton.clicked.connect(self.Add)
        buttons.addWidget(addButton)
        removeButton = QPushButton(QApplication.translate("settings.pronouns", "Remove"))
        removeButton.clicked.connect(self.Remove)
        buttons.addWidget(removeButton)
        sortButton = QPushButton(QApplication.translate("settings.pronouns", "Sort A-Z"))
        sortButton.clicked.connect(self.Sort)
        buttons.addWidget(sortButton)
        buttons.addStretch()
        layout.addLayout(buttons)

    def Save(self, *args):
        # Also drops empty rows and duplicates left by an edit
        PronounHelper.Save(self.model.stringList())

    def Add(self):
        row = self.model.rowCount()
        self.model.insertRows(row, 1)
        index = self.model.index(row)
        self.list.setCurrentIndex(index)
        self.list.edit(index)

    def Remove(self):
        index = self.list.currentIndex()
        if index.isValid():
            self.model.removeRows(index.row(), 1)
            self.Save()

    def Sort(self):
        self.model.sort(0)
        self.Save()
