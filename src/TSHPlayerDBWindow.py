import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.TSHCountryHelper import TSHCountryHelper
from .Helpers.TSHDictHelper import deep_clone
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerDB import TSHPlayerDB
from .TSHSeedManager import TSHSeedManager
from .TSHTheme import ThemedIcon

TagRole = Qt.ItemDataRole.UserRole + 1


def _FindComboIndex(combo: QComboBox, match):
    """Index of the first item whose UserRole data matches, or 0 (the empty item)."""
    model = combo.model()
    if model is None:
        return 0
    for i in range(model.rowCount()):
        data = model.index(i, 0).data(Qt.ItemDataRole.UserRole)
        if data and match(data):
            return i
    return 0


def _SearchableCombo(model=None):
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
    combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    if model is not None:
        combo.setModel(model)
    return combo


class TSHMainRow(QWidget):
    """One of a player's mains: character, skin, and the variant is kept as is."""

    removed = Signal(object)
    changed = Signal()

    def __init__(self, main=None, parent=None):
        super().__init__(parent)
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.character = _SearchableCombo(TSHGameAssetManager.instance.characterModel)
        self.character.setIconSize(QSize(24, 24))
        self.character.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layout().addWidget(self.character, 3)

        self.skin = QComboBox()
        self.skin.setIconSize(QSize(24, 24))
        self.layout().addWidget(self.skin, 2)

        removeBt = QPushButton()
        removeBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        removeBt.setToolTip(QApplication.translate("app", "Remove character"))
        removeBt.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        removeBt.clicked.connect(lambda: self.removed.emit(self))
        self.layout().addWidget(removeBt)

        self.variant = ""

        self.character.currentIndexChanged.connect(self.LoadSkins)
        self.character.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.skin.currentIndexChanged.connect(lambda _: self.changed.emit())

        if main:
            index = _FindComboIndex(self.character, lambda d: d.get("en_name") == main[0])
            self.character.setCurrentIndex(index)
            self.LoadSkins()
            try:
                skin = int(main[1]) if len(main) > 1 else 0
            except TypeError, ValueError:
                skin = 0
            if 0 <= skin < self.skin.count():
                self.skin.setCurrentIndex(skin)
            if len(main) > 2 and main[2]:
                self.variant = main[2]
        else:
            self.LoadSkins()

    def LoadSkins(self, _=None):
        data = self.character.currentData()
        model = TSHGameAssetManager.instance.skinModels.get(data.get("en_name")) if data else None
        self.skin.setModel(model if model is not None else QStandardItemModel())
        self.skin.setCurrentIndex(0)

    def GetMain(self):
        data = self.character.currentData()
        if not data or not data.get("en_name"):
            return None
        return [data.get("en_name"), max(0, self.skin.currentIndex()), self.variant]


class TSHPlayersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.editingTag = None
        self.dirty = False
        self.loadingForm = False
        self.needsRefresh = True
        self.mainRows = []

        layout = QHBoxLayout()
        self.setLayout(layout)

        splitter = QSplitter()
        layout.addWidget(splitter)

        # Player list
        listWidget = QWidget()
        listWidget.setLayout(QVBoxLayout())
        listWidget.layout().setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(listWidget)

        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("app", "Search players..."))
        self.search.setClearButtonEnabled(True)
        listWidget.layout().addWidget(self.search)

        self.model = QStandardItemModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.search.textChanged.connect(lambda _: self.UpdateCount())

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(24, 24))
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().selectionChanged.connect(self.SelectionChanged)
        listWidget.layout().addWidget(self.table)

        bottom = QHBoxLayout()
        listWidget.layout().addLayout(bottom)

        self.countLabel = QLabel()
        bottom.addWidget(self.countLabel)
        bottom.addStretch()

        self.importBt = QPushButton(QApplication.translate("app", "Import JSON"))
        self.importBt.setToolTip(
            QApplication.translate("app", "Add the players of a local_players.json file")
        )
        self.importBt.clicked.connect(self.ImportJSON)
        bottom.addWidget(self.importBt)

        self.exportBt = QPushButton(QApplication.translate("app", "Export JSON"))
        self.exportBt.setToolTip(
            QApplication.translate("app", "Save the players to a local_players.json file")
        )
        self.exportBt.setIcon(ThemedIcon("./assets/icons/export.svg"))
        self.exportBt.clicked.connect(self.ExportJSON)
        bottom.addWidget(self.exportBt)

        self.newBt = QPushButton(QApplication.translate("app", "New player"))
        self.newBt.setIcon(ThemedIcon("./assets/icons/add_user.svg"))
        self.newBt.clicked.connect(self.NewPlayer)
        bottom.addWidget(self.newBt)

        self.deleteBt = QPushButton(QApplication.translate("app", "Delete"))
        self.deleteBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.deleteBt.clicked.connect(self.DeleteSelected)
        bottom.addWidget(self.deleteBt)

        # Player form
        formScroll = QScrollArea()
        formScroll.setWidgetResizable(True)
        formScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(formScroll)

        formWidget = QWidget()
        formScroll.setWidget(formWidget)
        formWidget.setLayout(QVBoxLayout())

        self.formTitle = QLabel()
        font = self.formTitle.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.formTitle.setFont(font)
        formWidget.layout().addWidget(self.formTitle)

        form = QFormLayout()
        formWidget.layout().addLayout(form)

        self.prefix = QLineEdit()
        form.addRow(QApplication.translate("app", "Sponsor"), self.prefix)
        self.gamerTag = QLineEdit()
        form.addRow(QApplication.translate("app", "Tag"), self.gamerTag)
        self.realName = QLineEdit()
        form.addRow(QApplication.translate("app", "Real Name"), self.realName)
        self.pronoun = QLineEdit()
        form.addRow(QApplication.translate("app", "Pronouns"), self.pronoun)
        self.twitter = QLineEdit()
        form.addRow(QApplication.translate("app", "Twitter"), self.twitter)

        self.country = _SearchableCombo()
        self.country.setIconSize(QSize(24, 16))
        self.country.currentIndexChanged.connect(self.LoadStates)
        form.addRow(QApplication.translate("app", "Country"), self.country)

        self.state = _SearchableCombo()
        self.state.setIconSize(QSize(24, 16))
        form.addRow(QApplication.translate("app", "State"), self.state)

        self.customText = QPlainTextEdit()
        self.customText.setMaximumHeight(70)
        form.addRow(QApplication.translate("app", "Custom text"), self.customText)

        self.mainsLabel = QLabel()
        formWidget.layout().addWidget(self.mainsLabel)

        self.mainsLayout = QVBoxLayout()
        formWidget.layout().addLayout(self.mainsLayout)

        self.addMainBt = QPushButton(QApplication.translate("app", "Add character"))
        self.addMainBt.setIcon(ThemedIcon("./assets/icons/add_user.svg"))
        self.addMainBt.clicked.connect(lambda: [self.AddMainRow(), self.SetDirty()])
        formWidget.layout().addWidget(self.addMainBt)

        formWidget.layout().addStretch()

        self.errorLabel = QLabel()
        self.errorLabel.setStyleSheet("color: #f44336")
        self.errorLabel.setWordWrap(True)
        formWidget.layout().addWidget(self.errorLabel)

        buttons = QHBoxLayout()
        formWidget.layout().addLayout(buttons)
        self.revertBt = QPushButton(QApplication.translate("app", "Revert"))
        self.revertBt.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.revertBt.clicked.connect(self.Revert)
        buttons.addWidget(self.revertBt)
        self.saveBt = QPushButton(QApplication.translate("app", "Save"))
        self.saveBt.setIcon(ThemedIcon("./assets/icons/save.svg"))
        self.saveBt.setDefault(True)
        self.saveBt.clicked.connect(self.Save)
        buttons.addWidget(self.saveBt)

        for edit in [self.prefix, self.gamerTag, self.realName, self.pronoun, self.twitter]:
            edit.textEdited.connect(lambda _: self.SetDirty())
        for combo in [self.country, self.state]:
            combo.currentIndexChanged.connect(lambda _: self.SetDirty())
        self.customText.textChanged.connect(self.SetDirty)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 520])

        TSHPlayerDB.signals.db_updated.connect(self.DBUpdated)
        TSHGameAssetManager.instance.signals.onLoad.connect(self.GameChanged)
        TSHCountryHelper.signals.countriesUpdated.connect(self.SetupCombos)

        self.SetupCombos()
        self.LoadForm(None)

    # List

    def DBUpdated(self):
        if self.isVisible():
            self.RefreshList()
        else:
            self.needsRefresh = True

    def showEvent(self, event):
        super().showEvent(event)
        if self.needsRefresh:
            self.RefreshList()

    def RefreshList(self):
        self.needsRefresh = False
        selected = self.SelectedTags()
        scroll = self.table.verticalScrollBar().value()

        self.model.clear()
        self.model.setHorizontalHeaderLabels(
            [
                QApplication.translate("app", "Player"),
                QApplication.translate("app", "Real Name"),
                QApplication.translate("app", "Pronouns"),
                QApplication.translate("app", "Country"),
                QApplication.translate("app", "Twitter"),
            ]
        )

        # The DB model is only rebuilt on the GUI thread, so it can be read
        # without its lock (which is held while db_updated is emitted)
        dbModel = TSHPlayerDB.model
        if dbModel is not None:
            for row in range(dbModel.rowCount()):
                dbItem = dbModel.item(row)
                player = dbItem.data(Qt.ItemDataRole.UserRole) or {}
                # The text is the key the player is saved under
                tag = dbItem.text()

                tagItem = QStandardItem(tag)
                tagItem.setIcon(dbItem.icon())
                country = player.get("country_code") or ""
                if player.get("state_code"):
                    country += " / " + str(player.get("state_code"))
                items = [
                    tagItem,
                    QStandardItem(player.get("name") or ""),
                    QStandardItem(player.get("pronoun") or ""),
                    QStandardItem(country),
                    QStandardItem(player.get("twitter") or ""),
                ]
                for item in items:
                    item.setData(tag, TagRole)
                self.model.appendRow(items)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, max(160, min(self.table.columnWidth(0), 260)))
        self.UpdateCount()

        if (
            self.editingTag is not None
            and self.editingTag not in TSHPlayerDB.database
            and not self.dirty
        ):
            # Deleted from somewhere else
            self.LoadForm(None)

        self.SelectTags(selected)
        self.table.verticalScrollBar().setValue(scroll)

    def UpdateCount(self):
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        if shown == total:
            self.countLabel.setText(QApplication.translate("app", "{0} players").format(total))
        else:
            self.countLabel.setText(
                QApplication.translate("app", "{0} of {1} players").format(shown, total)
            )

    def SelectedTags(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return [r.data(TagRole) for r in rows]

    def SelectTags(self, tags):
        selection = QItemSelection()
        tags = set(tags)
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            if index.data(TagRole) in tags:
                selection.select(index, self.proxy.index(row, self.proxy.columnCount() - 1))
        self.table.selectionModel().blockSignals(True)
        self.table.selectionModel().select(
            selection, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        self.table.selectionModel().blockSignals(False)

    def SelectionChanged(self, *_):
        tags = self.SelectedTags()
        self.deleteBt.setEnabled(len(tags) > 0)
        if len(tags) != 1 or tags[0] == self.editingTag:
            return
        if not self.ConfirmDiscard():
            self.SelectTags([self.editingTag] if self.editingTag else [])
            return
        self.LoadForm(tags[0])

    def NewPlayer(self):
        if not self.ConfirmDiscard():
            return
        self.table.clearSelection()
        self.LoadForm(None)
        self.gamerTag.setFocus()

    def DeleteSelected(self):
        tags = self.SelectedTags()
        if not tags:
            return
        if len(tags) == 1:
            text = QApplication.translate("app", "Delete {0} from the player database?").format(
                tags[0]
            )
        else:
            text = QApplication.translate(
                "app", "Delete {0} players from the player database?"
            ).format(len(tags))
        answer = QMessageBox.question(self, QApplication.translate("app", "Delete players"), text)
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.editingTag in tags:
            self.dirty = False
            self.LoadForm(None)
        TSHPlayerDB.DeletePlayers(tags)

    def ImportJSON(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            QApplication.translate("app", "Import JSON"),
            "./user_data",
            "JSON (*.json *.json.bak);;" + QApplication.translate("app", "All files") + " (*)",
        )
        if not path:
            return
        try:
            count = TSHPlayerDB.ImportJSON(path)
            QMessageBox.information(
                self,
                QApplication.translate("app", "Import JSON"),
                QApplication.translate("app", "Imported {0} players.").format(count),
            )
        except Exception as e:
            logger.error(traceback.format_exc())
            QMessageBox.warning(self, QApplication.translate("app", "Import JSON"), str(e))

    def ExportJSON(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            QApplication.translate("app", "Export JSON"),
            "./user_data/local_players_export.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            TSHPlayerDB.ExportJSON(path)
        except Exception as e:
            logger.error(traceback.format_exc())
            QMessageBox.warning(self, QApplication.translate("app", "Export JSON"), str(e))

    # Form

    def SetupCombos(self):
        self.loadingForm = True
        try:
            if TSHCountryHelper.countryModel is not None:
                self.country.setModel(TSHCountryHelper.countryModel)
        finally:
            self.loadingForm = False

    def LoadStates(self, _=None):
        stateModel = QStandardItemModel()
        noState = QStandardItem()
        noState.setData({}, Qt.ItemDataRole.UserRole)
        stateModel.appendRow(noState)

        countryData = self.country.currentData(Qt.ItemDataRole.UserRole) or {}
        states = (
            TSHCountryHelper.GetStates(countryData.get("code")) if countryData.get("code") else None
        )
        for code, state in (states or {}).items():
            item = QStandardItem(f"{state.get('name')} ({code})")
            if state.get("asset"):
                item.setIcon(QIcon(state.get("asset")))
            item.setData(state, Qt.ItemDataRole.UserRole)
            stateModel.appendRow(item)

        self.state.setModel(stateModel)
        self.state.setCurrentIndex(0)

    def GameChanged(self):
        # Character models were replaced; reload the mains being edited
        if not self.dirty:
            self.LoadForm(self.editingTag)
        self.DBUpdated()

    def AddMainRow(self, main=None):
        row = TSHMainRow(main)
        row.removed.connect(self.RemoveMainRow)
        row.changed.connect(self.SetDirty)
        self.mainRows.append(row)
        self.mainsLayout.addWidget(row)

    def RemoveMainRow(self, row):
        if row in self.mainRows:
            self.mainRows.remove(row)
            row.deleteLater()
            self.SetDirty()

    def SetDirty(self):
        if self.loadingForm:
            return
        self.dirty = True
        self.UpdateButtons()

    def UpdateButtons(self):
        self.saveBt.setEnabled(self.dirty or self.editingTag is None)
        self.revertBt.setEnabled(self.dirty)
        if self.editingTag is None:
            self.formTitle.setText(QApplication.translate("app", "New player"))
        else:
            self.formTitle.setText(self.editingTag + (" *" if self.dirty else ""))

    def ConfirmDiscard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Unsaved changes"),
            QApplication.translate("app", "Discard the changes made to this player?"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def LoadForm(self, tag):
        self.loadingForm = True
        try:
            player = TSHPlayerDB.GetPlayer(tag) if tag else None
            if player is None:
                tag = None
                player = {}
            self.editingTag = tag
            self.errorLabel.setText("")

            self.prefix.setText(player.get("prefix") or "")
            self.gamerTag.setText(player.get("gamerTag") or "")
            self.realName.setText(player.get("name") or "")
            self.pronoun.setText(player.get("pronoun") or "")
            self.twitter.setText(player.get("twitter") or "")
            self.customText.setPlainText(
                "\n".join((player.get("custom_textbox") or "").split("\\n"))
            )

            countryCode = player.get("country_code")
            self.country.setCurrentIndex(
                _FindComboIndex(
                    self.country, lambda d: countryCode and d.get("code") == countryCode
                )
            )
            self.LoadStates()
            stateCode = player.get("state_code")
            self.state.setCurrentIndex(
                _FindComboIndex(
                    self.state,
                    lambda d: stateCode and stateCode in (d.get("code"), d.get("original_code")),
                )
            )

            for row in self.mainRows:
                row.deleteLater()
            self.mainRows = []

            game = TSHGameAssetManager.instance.selectedGame.get("codename")
            hasGame = bool(game)
            self.mainsLabel.setText(
                QApplication.translate("app", "Characters ({0})").format(
                    TSHGameAssetManager.instance.selectedGame.get("name")
                )
                if hasGame
                else QApplication.translate("app", "Select a game to edit the player's characters")
            )
            self.addMainBt.setEnabled(hasGame)
            if hasGame:
                mains = player.get("mains")
                if isinstance(mains, dict):
                    for main in mains.get(game) or []:
                        if isinstance(main, list) and len(main) > 0:
                            self.AddMainRow(main)
        except Exception:
            logger.error(traceback.format_exc())
        finally:
            self.loadingForm = False
            self.dirty = False
            self.UpdateButtons()

    def Revert(self):
        self.dirty = False
        self.LoadForm(self.editingTag)

    def GetFormData(self):
        countryData = self.country.currentData(Qt.ItemDataRole.UserRole) or {}
        stateData = self.state.currentData(Qt.ItemDataRole.UserRole) or {}

        data = {
            "prefix": self.prefix.text().strip(),
            "gamerTag": self.gamerTag.text().strip(),
            "name": self.realName.text().strip(),
            "pronoun": self.pronoun.text().strip(),
            "twitter": self.twitter.text().strip(),
            "custom_textbox": "\\n".join(self.customText.toPlainText().splitlines()),
            "country_code": countryData.get("code") or "",
            "state_code": stateData.get("code") or "",
        }

        game = TSHGameAssetManager.instance.selectedGame.get("codename")
        if game:
            # Only the loaded game's mains are edited; keep the others
            old = TSHPlayerDB.GetPlayer(self.editingTag) if self.editingTag else None
            mains = (old or {}).get("mains")
            mains = deep_clone(mains) if isinstance(mains, dict) else {}
            mains[game] = [m for m in (row.GetMain() for row in self.mainRows) if m]
            data["mains"] = mains

        return data

    def Save(self):
        data = self.GetFormData()
        if not data["gamerTag"]:
            self.errorLabel.setText(QApplication.translate("app", "The player needs a tag."))
            return

        oldTag = self.editingTag
        newTag = TSHPlayerDB.UpdatePlayer(oldTag, data)
        if newTag is None:
            self.errorLabel.setText(
                QApplication.translate("app", "There is already a player called {0}.").format(
                    TSHPlayerDB.GetTag(data)
                )
            )
            return

        if oldTag is not None:
            TSHSeedManager.RenamePlayer(oldTag, newTag)

        self.dirty = False
        self.LoadForm(newTag)
        self.SelectTags([newTag])
        selected = self.table.selectionModel().selectedRows()
        if selected:
            self.table.scrollTo(selected[0])


class TSHSeedsTab(QWidget):
    COLUMN_PLAYER = 0
    COLUMN_IMPORTED = 1
    COLUMN_SEED = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        self.needsRefresh = True
        self.refreshing = False
        self.refreshTimer = QTimer(self)
        self.refreshTimer.setSingleShot(True)
        self.refreshTimer.setInterval(0)
        self.refreshTimer.timeout.connect(self.RefreshList)

        self.setLayout(QVBoxLayout())

        info = QLabel(
            QApplication.translate(
                "app",
                "Seeds come with the entrants when an event is loaded. Seeds set here replace them on the scoreboards, and are kept until a different event is loaded. With no event loaded, players can be seeded by hand.",
            )
        )
        info.setWordWrap(True)
        self.layout().addWidget(info)

        # Seed a player that may not be in the list yet
        addRow = QHBoxLayout()
        self.layout().addLayout(addRow)
        self.addTag = QLineEdit()
        self.addTag.setPlaceholderText(QApplication.translate("app", "Player tag"))
        self.tagCompleter = QCompleter()
        self.tagCompleter.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tagCompleter.setFilterMode(Qt.MatchFlag.MatchContains)
        self.addTag.setCompleter(self.tagCompleter)
        addRow.addWidget(self.addTag, 3)
        self.addSeed = QSpinBox()
        self.addSeed.setRange(1, 100000)
        self.addSeed.setPrefix(QApplication.translate("app", "Seed") + " ")
        addRow.addWidget(self.addSeed, 1)
        self.addBt = QPushButton(QApplication.translate("app", "Set seed"))
        self.addBt.setIcon(ThemedIcon("./assets/icons/list.svg"))
        self.addBt.clicked.connect(self.AddSeed)
        self.addTag.returnPressed.connect(self.AddSeed)
        addRow.addWidget(self.addBt)

        filterRow = QHBoxLayout()
        self.layout().addLayout(filterRow)
        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("app", "Search players..."))
        self.search.setClearButtonEnabled(True)
        filterRow.addWidget(self.search)
        self.onlySeeded = QCheckBox(QApplication.translate("app", "Only seeded players"))
        self.onlySeeded.setChecked(True)
        self.onlySeeded.toggled.connect(lambda _: self.RefreshList())
        filterRow.addWidget(self.onlySeeded)

        self.model = QStandardItemModel()
        self.model.itemChanged.connect(self.ItemChanged)
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(self.COLUMN_PLAYER)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(self.COLUMN_SEED, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout().addWidget(self.table)

        bottom = QHBoxLayout()
        self.layout().addLayout(bottom)
        self.countLabel = QLabel()
        bottom.addWidget(self.countLabel)
        bottom.addStretch()

        self.resetBt = QPushButton(QApplication.translate("app", "Use imported seed"))
        self.resetBt.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.resetBt.setToolTip(
            QApplication.translate("app", "Drop the seeds set by hand for the selected players")
        )
        self.resetBt.clicked.connect(self.ResetSelected)
        bottom.addWidget(self.resetBt)

        self.clearBt = QPushButton(QApplication.translate("app", "Clear seeds set by hand"))
        self.clearBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.clearBt.clicked.connect(self.ClearAll)
        bottom.addWidget(self.clearBt)

        TSHPlayerDB.signals.db_updated.connect(self.Changed)
        TSHSeedManager.signals.seed_changed.connect(lambda _: self.Changed())

    def Changed(self):
        if self.isVisible():
            self.refreshTimer.start()
        else:
            self.needsRefresh = True

    def showEvent(self, event):
        super().showEvent(event)
        if self.needsRefresh:
            self.RefreshList()

    def RefreshList(self):
        self.needsRefresh = False
        self.refreshing = True
        try:
            scroll = self.table.verticalScrollBar().value()
            self.model.clear()
            self.model.setHorizontalHeaderLabels(
                [
                    QApplication.translate("app", "Player"),
                    QApplication.translate("app", "Imported seed"),
                    QApplication.translate("app", "Seed"),
                ]
            )

            tags = list(TSHPlayerDB.database.keys())
            known = set(tags)
            tags += [t for t in TSHSeedManager.overrides.keys() if t not in known]

            seededCount = 0
            for tag in tags:
                imported = TSHSeedManager.GetImportedSeed(tag)
                override = TSHSeedManager.GetOverride(tag)
                seed = override if override is not None else imported
                if seed:
                    seededCount += 1
                elif self.onlySeeded.isChecked():
                    continue

                playerItem = QStandardItem(tag)
                playerItem.setEditable(False)
                playerItem.setData(tag.lower(), Qt.ItemDataRole.UserRole)
                if tag not in known:
                    playerItem.setToolTip(
                        QApplication.translate("app", "Not in the player database")
                    )
                    playerItem.setForeground(QBrush(QColor("#9e9e9e")))

                importedItem = QStandardItem(str(imported) if imported else "")
                importedItem.setEditable(False)
                importedItem.setData(imported or 10**9, Qt.ItemDataRole.UserRole)

                seedItem = QStandardItem()
                seedItem.setData(seed or 0, Qt.ItemDataRole.EditRole)
                # Unseeded players sort last
                seedItem.setData(seed or 10**9, Qt.ItemDataRole.UserRole)
                seedItem.setData(tag, TagRole)
                if override is not None:
                    font = seedItem.font()
                    font.setBold(True)
                    seedItem.setFont(font)
                    seedItem.setToolTip(QApplication.translate("app", "Set by hand"))

                self.model.appendRow([playerItem, importedItem, seedItem])

            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(0, max(200, min(self.table.columnWidth(0), 320)))
            self.table.verticalScrollBar().setValue(scroll)

            self.countLabel.setText(
                QApplication.translate("app", "{0} seeded players, {1} set by hand").format(
                    seededCount, len(TSHSeedManager.overrides)
                )
            )

            self.tagCompleter.setModel(
                QStringListModel(sorted(known, key=str.lower), self.tagCompleter)
            )
        finally:
            self.refreshing = False

    def ItemChanged(self, item: QStandardItem):
        if self.refreshing or item.column() != self.COLUMN_SEED:
            return
        tag = item.data(TagRole)
        try:
            seed = int(item.data(Qt.ItemDataRole.EditRole) or 0)
        except TypeError, ValueError:
            seed = 0
        current = TSHSeedManager.GetSeed(tag)
        if seed == (current or 0):
            return
        TSHSeedManager.SetSeed(tag, seed)

    def AddSeed(self):
        tag = self.addTag.text().strip()
        if not tag:
            return
        TSHSeedManager.SetSeed(tag, self.addSeed.value())
        self.addTag.clear()
        self.addSeed.setValue(self.addSeed.value() + 1)
        self.addTag.setFocus()

    def SelectedTags(self):
        return [
            self.proxy.index(r.row(), self.COLUMN_SEED).data(TagRole)
            for r in self.table.selectionModel().selectedRows()
        ]

    def ResetSelected(self):
        for tag in self.SelectedTags():
            TSHSeedManager.ResetSeed(tag)

    def ClearAll(self):
        if not TSHSeedManager.overrides:
            return
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Clear seeds"),
            QApplication.translate("app", "Drop all {0} seeds set by hand?").format(
                len(TSHSeedManager.overrides)
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            TSHSeedManager.ClearAll()


class TSHPlayerDBWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QApplication.translate("app", "Player Database"))
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1100, 650)

        self.setLayout(QVBoxLayout())
        self.tabs = QTabWidget()
        self.layout().addWidget(self.tabs)

        self.playersTab = TSHPlayersTab()
        self.tabs.addTab(
            self.playersTab,
            ThemedIcon("./assets/icons/people.svg"),
            QApplication.translate("app", "Players"),
        )

        self.seedsTab = TSHSeedsTab()
        self.tabs.addTab(
            self.seedsTab,
            ThemedIcon("./assets/icons/list.svg"),
            QApplication.translate("app", "Seeds"),
        )

    def Open(self, tab=0):
        self.tabs.setCurrentIndex(tab)
        self.show()
        self.raise_()
        self.activateWindow()

    def reject(self):
        # Escape goes through closeEvent too, to ask about unsaved changes
        self.close()

    def closeEvent(self, event):
        if not self.playersTab.ConfirmDiscard():
            event.ignore()
            return
        self.playersTab.Revert()
        super().closeEvent(event)
