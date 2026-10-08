import os
import threading
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameAssetManager import GameAssetManager
from .Helpers.BadWordFilter import BadWordFilter
from .Helpers.CountryHelper import CountryHelper
from .Helpers.CustomPlayerCompleter import CustomPlayerCompleter
from .Helpers.DynamicExport import DynamicExport
from .Helpers.LocaleHelper import LocaleHelper
from .Helpers.PronounHelper import PronounHelper
from .PlayerDB import PlayerDB
from .PlayerRowParts import (
    PLAYER_MIME,
    CharacterChip,
    CharacterPicker,
    DragGrip,
    EyebrowLabel,
    IconButton,
    SetRole,
    SetStyleProperty,
    SmallFont,
    StatusDot,
)
from .SeedManager import SeedManager
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import ThemedIcon
from .TournamentDataManager import TournamentDataManager


class ScoreboardPlayerWidgetSignals(QObject):
    playerId_changed = Signal()
    player1Id_changed = Signal()
    player2Id_changed = Signal()
    player_seed_changed = Signal()
    dataChanged = Signal()
    # The details below the row were opened or closed
    detailsToggled = Signal(bool)


class ElidedLabel(QLabel):
    """A one line label that shortens its text with "…" instead of growing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fullText = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def SetFullText(self, text):
        self.fullText = text
        self.setToolTip(text)
        self._Elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._Elide()

    def _Elide(self):
        self.setText(
            self.fontMetrics().elidedText(
                self.fullText, Qt.TextElideMode.ElideRight, max(0, self.width())
            )
        )


class ScoreboardPlayerWidget(QFrame):
    """A player as one row: drag handle, seed, sponsor and tag, a summary
    line, characters and the player database status. The row opens into the
    player's details.

    The fields keep the object names the state is exported under (name,
    team, real_name, twitter, pronoun, country, state, seed,
    custom_textbox, character_N...), and the character, skin and variant
    combo boxes still hold the characters; they are hidden behind the
    character chips and the character picker."""

    # Fields in the details, which also fold away when the details close
    DETAIL_ELEMENTS = [
        "seedLabel",
        "seed",
        "real_name",
        "realNameLabel",
        "pronoun",
        "pronounLabel",
        "twitterLabel",
        "twitter",
        "locationLabel",
        "country",
        "state",
        "custom_textbox",
        "customLabel",
    ]

    # Docks built on this row can add their own signals
    SignalsClass = ScoreboardPlayerWidgetSignals

    countries = None
    countryModel = None
    characterModel = None
    _deleted = False
    _swapping = False

    dataLock = threading.RLock()

    # Width under which the character chips only show their icon
    COMPACT_WIDTH = 460

    def __init__(self, index=0, teamNumber=0, path="", customName="", *args):
        super().__init__(*args)

        self.instanceSignals = self.SignalsClass()

        self.path = path

        self.index = index
        self.teamNumber = teamNumber
        self.customName = customName

        self.losers = False

        # Edits made here by the user are saved to the player database
        # (see AutoSave); data loaded from a set or the database isn't
        self.userEdited = False
        self.dbSaving = False
        self.saveTimer = QTimer(self)
        self.saveTimer.setSingleShot(True)
        self.saveTimer.timeout.connect(self.AutoSave)
        # Swaps players when a row is dropped on this one. Docks that track
        # their players (Crew battle) swap them their own way
        self.onDropSwap = None

        SetRole(self, "playerRow", open=False)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(0)

        # ---------- the row ----------
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        root.addWidget(self.header)

        self.title = QLabel(self)
        self.title.setObjectName("title")
        self.title.hide()

        # Moving the player: drag the grip, or its right click menu. The
        # buttons aren't shown: the docks connect to their clicked signal
        self.btMoveUp = QPushButton(self)
        self.btMoveUp.hide()
        self.btMoveDown = QPushButton(self)
        self.btMoveDown.hide()
        self.grip = DragGrip(self)
        header.addWidget(self.grip)

        self.seedBadge = QLabel()
        SetRole(self.seedBadge, "badge")
        SmallFont(self.seedBadge, 0.85)
        self.seedBadge.setToolTip(QApplication.translate("app", "Seed"))
        self.seedBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seedBadge.setMinimumWidth(30)
        header.addWidget(self.seedBadge)

        who = QVBoxLayout()
        self.whoLayout = who
        who.setSpacing(0)
        who.setContentsMargins(0, 0, 0, 0)
        header.addLayout(who, 1)
        tagLine = QHBoxLayout()
        tagLine.setSpacing(2)
        who.addLayout(tagLine)

        team = QLineEdit()
        team.setObjectName("team")
        team.setPlaceholderText(QApplication.translate("app", "Sponsor"))
        SetRole(team, "inlineMuted")
        team.textChanged.connect(self.FitSponsorWidth)
        tagLine.addWidget(team, 0)

        name = QLineEdit()
        name.setObjectName("name")
        name.setPlaceholderText(QApplication.translate("app", "Tag (searches the player database)"))
        SetRole(name, "inline")
        SmallFont(name, 1.12, bold=True)
        name.setMinimumWidth(60)
        tagLine.addWidget(name, 1)

        self.summary = ElidedLabel()
        SetRole(self.summary, "muted")
        SmallFont(self.summary, 0.85)
        self.summary.setContentsMargins(4, 0, 0, 0)
        who.addWidget(self.summary)

        self.chips = QWidget()
        self.chips.setObjectName("characters")
        chipsLayout = QHBoxLayout(self.chips)
        chipsLayout.setContentsMargins(0, 0, 0, 0)
        chipsLayout.setSpacing(4)
        header.addWidget(self.chips)
        self.character_container = self.chips

        self.dbDot = StatusDot()
        header.addWidget(self.dbDot)

        self.detailsButton = IconButton(
            "assets/icons/chevron_down.svg", QApplication.translate("app", "Show details"), size=26
        )
        self.detailsButton.clicked.connect(lambda: self.SetDetailsShown(not self.detailsShown))
        header.addWidget(self.detailsButton)

        # The character, skin and variant combo boxes, behind the chips
        self.characterStore = QWidget(self)
        self.characterStore.setLayout(QVBoxLayout())
        self.characterStore.hide()

        # ---------- the details ----------
        self.details = QWidget()
        self.details.setObjectName("details")
        root.addWidget(self.details)
        grid = QGridLayout(self.details)
        grid.setContentsMargins(4, 8, 4, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)

        def field(label, labelName, widget, row, col, span=1):
            grid.addWidget(EyebrowLabel(label, objectName=labelName), row, col, 1, span)
            grid.addWidget(widget, row + 1, col, 1, span)

        seed = QSpinBox()
        seed.setObjectName("seed")
        seed.setMaximum(9999)
        seed.setSpecialValueText("—")
        field(QApplication.translate("app", "Seed"), "seedLabel", seed, 0, 0)

        real_name = QLineEdit()
        real_name.setObjectName("real_name")
        real_name.setPlaceholderText(QApplication.translate("app", "Real Name"))
        field(QApplication.translate("app", "Real Name"), "realNameLabel", real_name, 0, 1)

        pronoun = QLineEdit()
        pronoun.setObjectName("pronoun")
        pronoun.setPlaceholderText(QApplication.translate("app", "Pronouns"))
        field(QApplication.translate("app", "Pronouns"), "pronounLabel", pronoun, 0, 2)

        twitter = QLineEdit()
        twitter.setObjectName("twitter")
        twitter.setPlaceholderText(QApplication.translate("app", "Handle Only"))
        field(QApplication.translate("app", "Twitter"), "twitterLabel", twitter, 2, 0)

        country = QComboBox()
        country.setObjectName("country")
        country.setEditable(True)
        country.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        country.setPlaceholderText(QApplication.translate("app", "Country"))
        country.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        country.setMinimumContentsLength(6)
        field(QApplication.translate("app", "Location"), "locationLabel", country, 2, 1)

        state = QComboBox()
        state.setObjectName("state")
        state.setEditable(True)
        state.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        state.setPlaceholderText(QApplication.translate("app", "State / region"))
        state.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        state.setMinimumContentsLength(6)
        grid.addWidget(state, 3, 2)

        self.custom_textbox = QPlainTextEdit()
        self.custom_textbox.setObjectName("custom_textbox")
        self.custom_textbox.setMaximumHeight(70)
        self.custom_textbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.custom_textbox.setPlaceholderText(
            QApplication.translate("app", "Additional information")
        )
        field(
            QApplication.translate("app", "Additional information"),
            "customLabel",
            self.custom_textbox,
            4,
            0,
            3,
        )
        for col in range(3):
            grid.setColumnStretch(col, 1)

        divider = QFrame()
        SetRole(divider, "divider")
        grid.addWidget(divider, 6, 0, 1, 3)

        dbBar = QHBoxLayout()
        dbBar.setSpacing(6)
        grid.addLayout(dbBar, 7, 0, 1, 3)
        self.dbStatus = QLabel()
        SetRole(self.dbStatus, "muted")
        SmallFont(self.dbStatus, 0.9)
        self.dbStatus.setWordWrap(True)
        dbBar.addWidget(self.dbStatus, 1)

        self.save_bt = QPushButton(QApplication.translate("app", "Add to player database"))
        SetRole(self.save_bt, "primary")
        self.save_bt.setIcon(ThemedIcon("assets/icons/save.svg"))
        self.save_bt.clicked.connect(lambda: self.SavePlayerToDB())
        dbBar.addWidget(self.save_bt)

        self.media_bt = QPushButton(QApplication.translate("app", "Media..."))
        self.media_bt.setIcon(ThemedIcon("assets/icons/person.svg"))
        self.media_bt.setToolTip(
            QApplication.translate("app", "Avatar, sponsor logos and custom data of this player")
        )
        self.media_bt.clicked.connect(self.OpenMedia)
        dbBar.addWidget(self.media_bt)

        self.moreButton = IconButton("assets/icons/more.svg", QApplication.translate("app", "More"))
        self.moreButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        moreMenu = QMenu(self.moreButton)
        moreMenu.addAction(
            ThemedIcon("assets/icons/undo.svg"),
            QApplication.translate("app", "Clear this player"),
            lambda: self.Clear(),
        )
        self.reloadAction = moreMenu.addAction(
            ThemedIcon("assets/icons/db.svg"),
            QApplication.translate("app", "Reload from the player database"),
            self.ReloadFromDB,
        )
        moreMenu.addSeparator()
        self.delete_bt = moreMenu.addAction(
            ThemedIcon("assets/icons/cancel.svg"),
            QApplication.translate("app", "Delete from the player database..."),
            self.DeletePlayerFromDBClicked,
        )
        self.moreButton.setMenu(moreMenu)
        dbBar.addWidget(self.moreButton)

        self.LoadCountries()

        CountryHelper.signals.countriesUpdated.connect(self.LoadCountries)

        self.character_elements = []
        self.characterChips = []

        # Shows or folds away the details
        self.hiddenElements = set()
        self.displayElements = set()
        self.detailsShown = True
        self.SetDetailsShown(False)

        self.SetIndex(index, teamNumber)

        self.lastExportedName = ""

        self.custom_textbox.textChanged.connect(
            lambda element=self.custom_textbox: [
                StateManager.Set(f"{self.path}.{element.objectName()}", element.toPlainText()),
                self.instanceSignals.dataChanged.emit(),
            ]
        )

        name.editingFinished.connect(self.NameChanged)
        team.editingFinished.connect(self.NameChanged)
        name.editingFinished.connect(self.RefreshDbState)
        team.editingFinished.connect(self.RefreshDbState)

        for c in self.findChildren(QLineEdit):
            c.editingFinished.connect(
                lambda element=c: [
                    StateManager.Set(
                        f"{self.path}.{element.objectName() if element.objectName() != 'qt_spinbox_lineedit' else element.parent().objectName()}",
                        element.text(),
                    ),
                    self.instanceSignals.dataChanged.emit(),
                ]
            )

        seed.valueChanged.connect(lambda value: StateManager.Set(f"{self.path}.seed", value))
        seed.valueChanged.connect(lambda value: self.instanceSignals.player_seed_changed.emit())
        seed.valueChanged.connect(self.RefreshSummary)

        seed.setValue(0)
        seed.valueChanged.emit(seed.value())

        SeedManager.signals.seed_changed.connect(self.SeedOverrideChanged)

        for c in self.findChildren(QComboBox):
            c.currentIndexChanged.connect(
                lambda text, element=c: [self.ComboBoxIndexChanged(element)]
            )
            c.currentIndexChanged.emit(0)

        # Edits by the user, saved to the player database
        for field_ in (name, team, real_name, twitter, pronoun):
            field_.textEdited.connect(self.MarkUserEdited)
            field_.editingFinished.connect(self.UserEditFinished)
        for combo in (country, state):
            combo.activated.connect(lambda index: [self.MarkUserEdited(), self.ScheduleSave(400)])
        self.custom_textbox.textChanged.connect(self.CustomTextChanged)

        self.instanceSignals.dataChanged.connect(self.RefreshSummary)

        self.SetCharactersPerPlayer(1)

        PlayerDB.signals.db_updated.connect(self.SetupAutocomplete)
        self.SetupAutocomplete()

        GameAssetManager.instance.signals.onLoad.connect(self.ReloadCharacters)

        self.pronoun_completer = QCompleter()
        pronoun.setCompleter(self.pronoun_completer)
        self.pronoun_completer.setModel(PronounHelper.Model())

        self.FitSponsorWidth()
        self.RefreshSummary()
        self.RefreshDbState()

    # =====================================================
    # ROW
    # =====================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < ScoreboardPlayerWidget.COMPACT_WIDTH
        if compact != getattr(self, "_compact", None):
            self._compact = compact
            self.RefreshChips()

    def FitSponsorWidth(self, *args):
        """The sponsor field is as wide as the sponsor, so the tag follows it."""
        team = self.findChild(QLineEdit, "team")
        text = team.text() or team.placeholderText()
        width = team.fontMetrics().horizontalAdvance(text) + 14
        team.setFixedWidth(max(36, min(110, width)))

    def RefreshSummary(self, *args):
        """The line under the tag: country, real name, pronouns and handle,
        each if it is shown, and the seed badge."""
        if self._deleted:
            return
        parts = []

        def shown(name):
            return name not in self.hiddenElements

        country = self.findChild(QComboBox, "country").currentData(Qt.ItemDataRole.UserRole)
        if shown("country") and country and country.get("code"):
            parts.append(country.get("code"))
        for name in ("real_name", "pronoun"):
            text = self.findChild(QLineEdit, name).text().strip()
            if shown(name) and text:
                parts.append(text)
        twitter = self.findChild(QLineEdit, "twitter").text().strip()
        if shown("twitter") and twitter:
            parts.append("@" + twitter.lstrip("@"))
        self.summary.SetFullText("  ·  ".join(parts))
        self.summary.setVisible(bool(parts) or self.detailsShown)

        seed = self.findChild(QSpinBox, "seed").value()
        self.seedBadge.setText(f"#{seed}" if seed else "—")
        self.seedBadge.setVisible(shown("seed"))

    def RefreshChips(self):
        compact = getattr(self, "_compact", False)
        for i, chip in enumerate(self.characterChips):
            if i >= len(self.character_elements):
                break
            _, character, color, variant = self.character_elements[i]
            data = character.currentData()
            name = ""
            if data:
                name = data.get("display_name") or data.get("en_name") or character.currentText()
            elif character.currentText():
                name = character.currentText()
            icon = character.itemIcon(character.currentIndex()) if data else None
            skinIcon = color.itemIcon(color.currentIndex()) if color.currentIndex() >= 0 else None
            if skinIcon is not None and not skinIcon.isNull():
                icon = skinIcon
            tooltip = name
            if data and color.currentIndex() >= 0:
                tooltip += " · " + QApplication.translate("app", "skin {0}").format(
                    color.currentIndex() + 1
                )
            if variant.currentData() and variant.currentText():
                tooltip += " · " + variant.currentText()
            chip.Refresh(name, icon, tooltip, compact)

    def RefreshDbState(self):
        if self._deleted:
            return
        tag = self.GetCurrentPlayerTag().strip()
        inDB = bool(tag) and tag in PlayerDB.database
        if not tag:
            state, text = StatusDot.EMPTY, ""
        elif self.dbSaving:
            state = StatusDot.SAVING
            text = QApplication.translate("app", "Saving to the player database...")
        elif inDB:
            state = StatusDot.SAVED
            text = QApplication.translate(
                "app", "Saved in the player database. Your edits are saved automatically."
            )
        else:
            state = StatusDot.NEW
            text = QApplication.translate("app", "Not in the player database")
        self.dbDot.SetState(state, text)
        self.dbStatus.setText(text)
        self.save_bt.setVisible(bool(tag) and not inDB and not self.dbSaving)
        self.delete_bt.setEnabled(inDB)
        self.reloadAction.setEnabled(inDB)

    def SetDetailsShown(self, shown):
        if shown == self.detailsShown:
            return
        self.detailsShown = shown
        self.details.setVisible(shown)
        SetStyleProperty(self, "open", shown)
        self.detailsButton.setIcon(
            ThemedIcon("assets/icons/chevron_up.svg" if shown else "assets/icons/chevron_down.svg")
        )
        self.detailsButton.setToolTip(
            QApplication.translate("app", "Hide details")
            if shown
            else QApplication.translate("app", "Show details")
        )
        self.UpdateVisibility()
        self.instanceSignals.detailsToggled.emit(shown)

    def mousePressEvent(self, event):
        # A click on the row (not on one of its fields) opens or closes it
        if event.button() == Qt.MouseButton.LeftButton and self.header.geometry().contains(
            event.position().toPoint()
        ):
            self.SetDetailsShown(not self.detailsShown)
            return
        super().mousePressEvent(event)

    # Dropping another row of the same list on this one swaps them
    def _DropSource(self, event):
        if not event.mimeData().hasFormat(PLAYER_MIME):
            return None
        grip = event.source()
        source = getattr(grip, "row", None)
        if source is None or source is self or source.parentWidget() is not self.parentWidget():
            return None
        return source

    def dragEnterEvent(self, event):
        if self._DropSource(event) is not None:
            event.acceptProposedAction()
            SetStyleProperty(self, "dropTarget", True)

    def dragLeaveEvent(self, event):
        SetStyleProperty(self, "dropTarget", False)

    def dropEvent(self, event):
        SetStyleProperty(self, "dropTarget", False)
        source = self._DropSource(event)
        if source is None:
            return
        event.acceptProposedAction()
        if self.onDropSwap is not None:
            self.onDropSwap(source, self)
        else:
            source.SwapWith(self)

    # =====================================================
    # PLAYER DATABASE
    # =====================================================
    def MarkUserEdited(self, *args):
        self.userEdited = True

    def UserEditFinished(self):
        if self.userEdited:
            self.ScheduleSave(250)

    def CustomTextChanged(self):
        if self.custom_textbox.hasFocus():
            self.MarkUserEdited()
            self.ScheduleSave(1500)

    def ScheduleSave(self, delay):
        self.saveTimer.start(delay)

    def ForgetUserEdits(self):
        self.userEdited = False
        self.saveTimer.stop()

    def AutoSave(self):
        """Saves the user's edits to the player database. A player loaded
        from a set is only added once they are edited here."""
        if not self.userEdited or self._deleted:
            return
        self.userEdited = False
        if not self.GetCurrentPlayerTag().strip():
            return
        self.SavePlayerToDB(auto=True)

    def ReloadFromDB(self):
        player = PlayerDB.GetPlayer(self.GetCurrentPlayerTag())
        if player:
            self.SetData(player, dontLoadFromDB=True)

    def DeletePlayerFromDBClicked(self):
        tag = self.GetCurrentPlayerTag()
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Delete player"),
            QApplication.translate(
                "app", "Delete {0} from the player database? The scoreboard keeps them."
            ).format(tag),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.DeletePlayerFromDB()

    # =====================================================
    # CHARACTERS, CHANGED FROM THE CHIPS AND THE PICKER
    # =====================================================
    def OpenCharacterPicker(self, slot):
        if slot >= len(self.character_elements):
            return
        picker = CharacterPicker(self, slot, self.characterChips[slot])
        picker.show()

    def UserCharacterEdited(self):
        self.MarkUserEdited()
        self.ScheduleSave(600)

    def UserSetCharacter(self, slot, row):
        character = self.character_elements[slot][1]
        if character.currentIndex() != row:
            character.setCurrentIndex(row)
            self.UserCharacterEdited()

    def UserSetSkin(self, slot, skin):
        color = self.character_elements[slot][2]
        if color.currentIndex() != skin:
            color.setCurrentIndex(skin)
            self.UserCharacterEdited()

    def UserSetVariant(self, slot, index):
        variant = self.character_elements[slot][3]
        if variant.currentIndex() != index:
            variant.setCurrentIndex(index)
            self.UserCharacterEdited()

    def UserSwapCharacters(self, index1, index2):
        self.SwapCharacters(index1, index2)
        self.UserCharacterEdited()

    def OpenMedia(self):
        # Imported here: the window imports the widgets' modules
        from .PlayerDBWindow import PlayerDBWindow

        if PlayerDBWindow.instance is not None:
            PlayerDBWindow.instance.OpenMedia(
                self.findChild(QLineEdit, "team").text().strip(),
                self.findChild(QLineEdit, "name").text().strip(),
            )

    def deleteLater(self):
        self._deleted = True
        super().deleteLater()

    def ComboBoxIndexChanged(self, element: QComboBox):
        StateManager.Set(f"{self.path}.{element.objectName()}", element.currentData())
        self.instanceSignals.dataChanged.emit()

    def CharactersChanged(self, includeMains=False):
        if self._deleted:
            logger.warning(
                f"CharactersChanged called on deleted ScoreboardPlayerWidget for {self.path}"
            )
            return

        with self.dataLock:
            characters = {}

            for i, (element, character, color, variant) in enumerate(self.character_elements):
                data = character.currentData()

                if data == None:
                    data = {}

                if character.currentData() == None:
                    data = {"name": character.currentText()}

                if color.currentData() and color.currentData().get("name", ""):
                    data["name"] = color.currentData().get("name", "")

                if color.currentData() and color.currentData().get("en_name", ""):
                    data["en_name"] = color.currentData().get("en_name", "")

                if color.currentData() and character.currentData():
                    data["assets"] = color.currentData().get("assets", {})

                if data.get("assets") == None:
                    data["assets"] = {}

                data["skin"] = color.currentIndex()
                if variant.currentData():
                    data["variant"] = variant.currentData()
                else:
                    data["variant"] = {}

                characters[i + 1] = data

            StateManager.Set(f"{self.path}.character", characters)

            if includeMains:
                StateManager.Set(f"{self.path}.mains", characters)

        self.RefreshChips()

    def SetLosers(self, value):
        with self.dataLock:
            self.losers = value
            self.ExportMergedName()

    def NameChanged(self):
        with self.dataLock:
            team = self.findChild(QLineEdit, "team").text()
            name = self.findChild(QLineEdit, "name").text()
            merged = team + " " + name

            if merged != self.lastExportedName:
                self.ExportMergedName()
                self.ExportPlayerImages()
                self.ExportPlayerId()

            self.lastExportedName = merged

            self.SetRomanizedText()

    def ExportMergedName(self):
        with self.dataLock:
            team = self.findChild(QLineEdit, "team").text()
            name = self.findChild(QLineEdit, "name").text()
            merged = ""
            nameOnlyMerged = ""

            if team != "":
                merged += team + " | "

            merged += name
            nameOnlyMerged += name

            if self.losers:
                merged += " [L]"
                nameOnlyMerged += " [L]"

            StateManager.Set(f"{self.path}.mergedName", merged)
            StateManager.Set(f"{self.path}.mergedOnlyName", nameOnlyMerged)

    def ExportPlayerImages(self, onlineAvatar=None):
        with self.dataLock:
            team = self.findChild(QLineEdit, "team").text()
            name = self.findChild(QLineEdit, "name").text()

            StateManager.Set(f"{self.path}.online_avatar", onlineAvatar)

            # Local avatar, sponsor logos and custom data, kept up to date
            DynamicExport.ExportPlayerMedia(name, team, self.path)

    def ExportPlayerId(self, id=None):
        with self.dataLock:
            if StateManager.Get(f"{self.path}.id") != id:
                StateManager.Set(f"{self.path}.id", id)
                # While swapping the id goes through intermediate values;
                # SwapWith emits once for the final one instead
                if not self._swapping:
                    self.EmitPlayerIdChanged()

    def EmitPlayerIdChanged(self):
        # Each of these starts start.gg requests for the player's stats
        if "score" in self.path:
            self.instanceSignals.playerId_changed.emit()
            if "team.1" in self.path:
                self.instanceSignals.player1Id_changed.emit()
            else:
                self.instanceSignals.player2Id_changed.emit()

    def ExportPlayerCity(self, city=None):
        with self.dataLock:
            if StateManager.Get(f"{self.path}.city") != city:
                StateManager.Set(f"{self.path}.city", city)

    def SwapWith(self, other: ScoreboardPlayerWidget, emitIdChanged=True):
        """Swap this player's data with other's.

        With emitIdChanged=False the playerId signals aren't emitted for the
        new ids, for callers that move the player stats themselves instead of
        fetching them again.
        """
        if self == other:
            logger.info("Swapping player with themselves")
            return
        oldIds = [StateManager.Get(f"{w.path}.id") for w in [self, other]]
        self.ForgetUserEdits()
        other.ForgetUserEdits()
        try:
            StateManager.BlockSaving()
            self._swapping = True
            other._swapping = True
            with self.dataLock:
                with other.dataLock:
                    tmpData = []

                    # Save state
                    for w in [self, other]:
                        data = {}
                        for widget in w.findChildren(QWidget):
                            # Unnamed widgets (e.g. the line edits inside
                            # editable combo boxes) can't be found again by
                            # name, and loading them would hit another widget
                            if not widget.objectName():
                                continue
                            if type(widget) == QLineEdit:
                                data[widget.objectName()] = widget.text()
                            if type(widget) == QComboBox:
                                data[widget.objectName()] = widget.currentIndex()
                            if type(widget) == QPlainTextEdit:
                                data[widget.objectName()] = widget.toPlainText()
                            if type(widget) == QCheckBox:
                                data[widget.objectName()] = widget.isChecked()
                        data["online_avatar"] = StateManager.Get(f"{w.path}.online_avatar")
                        data["id"] = StateManager.Get(f"{w.path}.id")
                        data["seed"] = StateManager.Get(f"{w.path}.seed")
                        data["wins"] = StateManager.Get(f"{w.path}.wins")
                        data["losses"] = StateManager.Get(f"{w.path}.losses")
                        data["winPercentage"] = StateManager.Get(f"{w.path}.winPercentage")
                        data["city"] = StateManager.Get(f"{w.path}.city")
                        tmpData.append(data)

                    # Load state
                    for i, w in enumerate([other, self]):
                        lineEdits = []
                        for objName in tmpData[i]:
                            widget = w.findChild(QWidget, objName)
                            if widget:
                                if type(widget) == QLineEdit:
                                    widget.setText(tmpData[i][objName])
                                    lineEdits.append(widget)
                                if type(widget) == QComboBox:
                                    widget.setCurrentIndex(tmpData[i][objName])
                                if type(widget) == QPlainTextEdit:
                                    widget.setPlainText(tmpData[i][objName])
                                if type(widget) == QCheckBox:
                                    widget.setChecked(tmpData[i][objName])
                        # Only once every field is set, so the name/team
                        # handlers run on the final name instead of a mix of
                        # both players' (each run exports images, sponsors...)
                        for widget in lineEdits:
                            widget.editingFinished.emit()
                        w.ExportPlayerId(tmpData[i]["id"])
                        StateManager.Set(f"{w.path}.online_avatar", tmpData[i]["online_avatar"])
                        StateManager.Set(f"{w.path}.seed", tmpData[i]["seed"])
                        StateManager.Set(f"{w.path}.wins", tmpData[i]["wins"])
                        StateManager.Set(f"{w.path}.losses", tmpData[i]["losses"])
                        StateManager.Set(f"{w.path}.winPercentage", tmpData[i]["winPercentage"])
                        StateManager.Set(f"{w.path}.city", tmpData[i]["city"])
        finally:
            self._swapping = False
            other._swapping = False
            StateManager.ReleaseSaving()

        for w in (self, other):
            w.RefreshSummary()
            w.RefreshDbState()
            w.RefreshChips()

        if emitIdChanged:
            for w, oldId in zip([self, other], oldIds):
                if StateManager.Get(f"{w.path}.id") != oldId:
                    w.EmitPlayerIdChanged()

    def SetIndex(self, index: int, team: int):
        if self.customName == "":
            self.findChild(QWidget, "title").setText(
                QApplication.translate("app", "Player {0}").format(index)
            )
        else:
            title = self.customName + " {0}"
            self.findChild(QWidget, "title").setText(
                QApplication.translate("app", title).format(index)
            )
        self.index = index
        self.teamNumber = team

    def SetCharactersPerPlayer(self, number):
        while len(self.character_elements) < number:
            slot = len(self.character_elements)
            character_element = QWidget()
            character_element.setLayout(QHBoxLayout())
            player_character = QComboBox()
            player_character.setEditable(True)
            character_element.layout().addWidget(player_character)
            player_character.setModel(GameAssetManager.instance.characterModel)

            player_character_color = QComboBox()
            character_element.layout().addWidget(player_character_color)
            player_character_color.setEditable(True)

            player_variant = QComboBox()
            player_variant.setObjectName("variants")
            character_element.layout().addWidget(player_variant)
            player_variant.setModel(GameAssetManager.instance.variantModel)
            player_variant.setEditable(True)

            # The combo boxes hold the characters; the chip shows them
            self.characterStore.layout().addWidget(character_element)

            chip = CharacterChip(self, slot)
            chip.clicked.connect(lambda checked=False, slot=slot: self.OpenCharacterPicker(slot))
            self.chips.layout().addWidget(chip)
            self.characterChips.append(chip)

            self.character_elements.append(
                [character_element, player_character, player_character_color, player_variant]
            )

            player_character.currentIndexChanged.connect(
                lambda x, element=player_character, target=player_character_color: [
                    self.LoadSkinOptions(element, target),
                    self.CharactersChanged(),
                ]
            )

            player_character_color.currentIndexChanged.connect(
                lambda index, element=player_character: [self.CharactersChanged()]
            )

            player_variant.currentIndexChanged.connect(
                lambda index, element=player_character: [self.CharactersChanged()]
            )

            player_character.setCurrentIndex(0)
            player_character_color.setCurrentIndex(0)
            player_variant.setCurrentIndex(0)

            player_character.setObjectName(f"character_{len(self.character_elements)}")
            player_character_color.setObjectName(f"character_color_{len(self.character_elements)}")

        while len(self.character_elements) > number:
            self.character_elements[-1][0].setParent(None)
            self.character_elements.pop()
            chip = self.characterChips.pop()
            chip.setParent(None)
            chip.deleteLater()

        self.chips.setVisible(number > 0 and "characters" not in self.hiddenElements)
        self.CharactersChanged(includeMains=True)

    # Labels that go with a field, hidden along with it
    FIELD_LABELS = {
        "real_name": "realNameLabel",
        "pronoun": "pronounLabel",
        "custom_textbox": "customLabel",
    }

    def SetElementVisible(self, name, visible):
        """Shows or hides one of the fields from the display options"""
        names = [name]
        if name in ScoreboardPlayerWidget.FIELD_LABELS:
            names.append(ScoreboardPlayerWidget.FIELD_LABELS[name])
        for n in names:
            self.displayElements.add(n)
            if visible:
                self.hiddenElements.discard(n)
            else:
                self.hiddenElements.add(n)
        self.UpdateVisibility()

    def UpdateVisibility(self):
        for name in self.displayElements:
            widget = self.findChild(QWidget, name)
            if widget is None:
                continue
            if name == "characters":
                widget.setVisible(
                    name not in self.hiddenElements and len(self.character_elements) > 0
                )
                continue
            widget.setVisible(name not in self.hiddenElements)
        self.RefreshSummary()

    def SwapCharacters(self, index1: int, index2: int):
        with StateManager.SaveBlock():
            self.DoSwapCharacters(index1, index2)

    def DoSwapCharacters(self, index1: int, index2: int):
        if index2 > len(self.character_elements) - 1:
            index2 = 0

        char1 = self.character_elements[index1]
        char2 = self.character_elements[index2]

        # Save index1 settings
        tmp = [char1[1].currentText(), char1[2].currentIndex()]

        # Set index1 to index2
        # Character
        found = char1[1].findText(char2[1].currentText())
        if found != -1:
            char1[1].setCurrentIndex(found)
        else:
            char1[1].setCurrentText(char2[1].currentText())

        # Color
        char1[2].setCurrentIndex(char2[2].currentIndex())

        # Set index2 to temp (index1)
        # Character
        found = char2[1].findText(tmp[0])
        if found != -1:
            char2[1].setCurrentIndex(found)
        else:
            char2[1].setCurrentText(tmp[0])

        # Color
        char2[2].setCurrentIndex(tmp[1])

        self.CharactersChanged()

    def LoadCountries(self):
        try:
            if CountryHelper.countryModel == None:
                CountryHelper.LoadCountries()

            countryCompleter = QCompleter(CountryHelper.countryModel)

            country: QComboBox = self.findChild(QComboBox, "country")
            country.setCompleter(countryCompleter)
            country.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            country.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            country.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            country.view().setMinimumWidth(60)
            country.completer().setCompletionMode(QCompleter.PopupCompletion)
            country.completer().popup().setMinimumWidth(300)
            country.setModel(CountryHelper.countryModel)
            country.setFont(QFont(country.font().family(), 9))
            country.lineEdit().setFont(QFont(country.font().family(), 9))

            country.currentIndexChanged.connect(self.LoadStates)
            country.currentIndexChanged.connect(self.SetRomanizedText)

            state: QComboBox = self.findChild(QComboBox, "state")
            state.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            state.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            state.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            state.view().setMinimumWidth(60)
            state.completer().setCompletionMode(QCompleter.PopupCompletion)
            state.completer().popup().setMinimumWidth(300)
            state.setFont(QFont(state.font().family(), 9))
            state.lineEdit().setFont(QFont(state.font().family(), 9))

        except Exception as e:
            logger.error(traceback.format_exc())
            exit()

    def LoadStates(self, index):
        country: QComboBox = self.findChild(QComboBox, "country")

        countryData = None
        if country.currentData(Qt.ItemDataRole.UserRole) != None:
            countryData = CountryHelper.countries.get(
                country.currentData(Qt.ItemDataRole.UserRole).get("code"), {}
            )

        stateModel = QStandardItemModel()

        noState = QStandardItem()
        noState.setData({}, Qt.ItemDataRole.UserRole)
        stateModel.appendRow(noState)

        states = countryData.get("states")

        if states is not None:
            for i, state_code in enumerate(states.keys()):
                item = QStandardItem()
                # Windows has some weird thing with files named CON.png. In case a state code is CON,
                # we try to load _CON.png instead
                path = f"./assets/state_flag/{countryData.get('code')}/{'_CON' if state_code == 'CON' else state_code}.png"

                if not os.path.exists(path):
                    path = None

                states[state_code].update({"asset": path})
                item.setIcon(QIcon(path))
                item.setData(states[state_code], Qt.ItemDataRole.UserRole)
                item.setData(
                    f"{states[state_code]['name']} ({state_code})", Qt.ItemDataRole.EditRole
                )
                stateModel.appendRow(item)

        state: QComboBox = self.findChild(QComboBox, "state")
        state.setModel(stateModel)
        state.setCurrentIndex(0)

    def LoadSkinOptions(self, element, target):
        characterData = element.currentData()

        if characterData:
            target.setModel(GameAssetManager.instance.skinModels.get(characterData.get("en_name")))
        else:
            target.setModel(QStandardItemModel())

    def ReloadCharacters(self):
        for c in self.character_elements:
            c[1].setModel(GameAssetManager.instance.characterModel)
            c[3].setModel(GameAssetManager.instance.variantModel)
        self.RefreshChips()

    def SetupAutocomplete(self):
        if PlayerDB.model:
            self.findChild(QLineEdit, "name").setCompleter(CustomPlayerCompleter(PlayerDB.model))
            self.findChild(QLineEdit, "name").completer().activated[QModelIndex].connect(
                lambda x: self.SetData(x.data(Qt.ItemDataRole.UserRole)) if x is not None else None,
                Qt.QueuedConnection,
            )
            self.findChild(QLineEdit, "name").completer().setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
            self.findChild(QLineEdit, "name").completer().setFilterMode(Qt.MatchFlag.MatchContains)
            self.findChild(QLineEdit, "name").completer().setModel(PlayerDB.model)

        self.RefreshDbState()

    def SetData(self, data, dontLoadFromDB=False, clear=True, no_mains=False, enrichBlocking=True):
        self.dataLock.acquire()
        # Loaded, not edited here: not saved to the player database
        self.ForgetUserEdits()

        logger.debug(f"Setting data for {self.path}: {data}")

        # BlockSaving() lives inside the try so that the finally below always
        # releases it, even if one of the calls in between raises.
        try:
            StateManager.BlockSaving()

            if clear:
                self.Clear(no_mains=no_mains)

            # Load player data from DB; will be overwriten by incoming data
            if not dontLoadFromDB and PlayerDB.model is not None:
                tag = (
                    data.get("prefix") + " " + data.get("gamerTag")
                    if data.get("prefix")
                    else data.get("gamerTag")
                )

                # Looked up by tag instead of converting every row of the
                # model back to a dict, which took tens of ms with a big DB
                item = PlayerDB.GetPlayer(tag)
                if item is not None:
                    self.SetData(
                        item,
                        dontLoadFromDB=True,
                        clear=False,
                        no_mains=no_mains,
                        enrichBlocking=enrichBlocking,
                    )
                    if SettingsManager.Get("general.disable_overwrite", False):
                        data = data | item

            # Provider-side lazy enrichment (e.g. parry → mains from a
            # linked start.gg account). No-op for providers that don't
            # override EnrichPlayerData; cached so repeated loads are free.
            # Bulk loads (e.g. a whole bracket) pass enrichBlocking=False so
            # a cache miss is fetched in the background instead of making a
            # network request per player on the UI thread.
            provider = (
                TournamentDataManager.instance.provider if TournamentDataManager.instance else None
            )
            if provider is not None:
                data = provider.EnrichPlayerData(data, blocking=enrichBlocking) or data

            name = self.findChild(QWidget, "name")
            if data.get("gamerTag") and data.get("gamerTag") != name.text():
                data["gamerTag"] = BadWordFilter.Censor(data["gamerTag"], data.get("country_code"))
                name.setText(f"{data.get('gamerTag')}")
                name.editingFinished.emit()

            team = self.findChild(QWidget, "team")
            if data.get("prefix") and data.get("prefix") != team.text():
                data["prefix"] = BadWordFilter.Censor(data["prefix"], data.get("country_code"))
                team.setText(f"{data.get('prefix')}")
                team.editingFinished.emit()

            real_name = self.findChild(QWidget, "real_name")
            if data.get("name") and data.get("name") != real_name.text():
                data["name"] = BadWordFilter.Censor(data["name"], data.get("country_code"))
                real_name.setText(f"{data.get('name')}")
                real_name.editingFinished.emit()

            if data.get("avatar"):
                self.ExportPlayerImages(data.get("avatar"))

            if data.get("id"):
                self.ExportPlayerId(data.get("id"))

            if data.get("city"):
                self.ExportPlayerCity(data.get("city"))

            twitter = self.findChild(QWidget, "twitter")
            if data.get("twitter") and data.get("twitter") != twitter.text():
                data["twitter"] = BadWordFilter.Censor(data["twitter"], data.get("country_code"))
                twitter.setText(f"{data.get('twitter')}")
                twitter.editingFinished.emit()

            if (
                data.get("custom_textbox")
                and data.get("custom_textbox") != self.custom_textbox.toPlainText()
            ):
                data["custom_textbox"] = BadWordFilter.Censor(
                    data["custom_textbox"], data.get("country_code")
                )
                self.custom_textbox.setPlainText(
                    f"{data.get('custom_textbox')}".replace("\\n", "\n")
                )
                self.custom_textbox.textChanged.emit()

            pronoun = self.findChild(QWidget, "pronoun")
            if data.get("pronoun") and data.get("pronoun") != pronoun.text():
                data["pronoun"] = BadWordFilter.Censor(data["pronoun"], data.get("country_code"))
                pronoun.setText(f"{data.get('pronoun')}")
                pronoun.editingFinished.emit()

            if data.get("country_code"):
                countryElement: QComboBox = self.findChild(QComboBox, "country")
                countryIndex = 0
                for i in range(CountryHelper.countryModel.rowCount()):
                    item = CountryHelper.countryModel.item(i).data(Qt.ItemDataRole.UserRole)
                    if item:
                        if data.get("country_code") == item.get("code"):
                            countryIndex = i
                            break
                if countryElement.currentIndex() != countryIndex:
                    countryElement.setCurrentIndex(countryIndex)

            if data.get("state_code"):
                countryElement: QComboBox = self.findChild(QComboBox, "country")
                stateElement: QComboBox = self.findChild(QComboBox, "state")
                stateIndex = 0
                for i in range(stateElement.model().rowCount()):
                    item = stateElement.model().item(i).data(Qt.ItemDataRole.UserRole)
                    if item:
                        if data.get("state_code") == item.get("original_code"):
                            stateIndex = i
                            break
                if stateElement.currentIndex() != stateIndex:
                    stateElement.setCurrentIndex(stateIndex)

            if data.get("mains") and no_mains != True:
                if type(data.get("mains")) == list:
                    for element in self.character_elements:
                        character_element = element[1]
                        characterIndex = 0
                        for i in range(character_element.model().rowCount()):
                            item = character_element.model().item(i).data(Qt.ItemDataRole.UserRole)
                            if item:
                                if item.get("en_name") == data.get("mains")[0]:
                                    characterIndex = i
                                    break
                        character_element.setCurrentIndex(characterIndex)
                elif type(data.get("mains")) == dict:
                    game_codename = GameAssetManager.instance.selectedGame.get("codename")
                    base_game_dir = GameAssetManager.instance.selectedGame.get(
                        "base_game_dir", game_codename
                    )
                    mains = (
                        data.get("mains").get(game_codename)
                        or data.get("mains").get(base_game_dir)
                        or []
                    )

                    for i, main in enumerate(mains):
                        if i < len(self.character_elements):
                            character_element = self.character_elements[i][1]
                            color_element = self.character_elements[i][2]
                            variant_element = self.character_elements[i][3]
                            characterIndex = 0
                            for i in range(character_element.model().rowCount()):
                                item = (
                                    character_element.model().item(i).data(Qt.ItemDataRole.UserRole)
                                )
                                if item:
                                    if item.get("en_name") == main[0]:
                                        characterIndex = i
                                        break
                            if character_element.currentIndex() != characterIndex:
                                character_element.setCurrentIndex(characterIndex)
                            if len(main) > 1:
                                if color_element.currentIndex() != int(main[1]):
                                    color_element.setCurrentIndex(int(main[1]))
                            else:
                                if color_element.currentIndex() != 0:
                                    color_element.setCurrentIndex(0)

                            variantIndex = 0
                            if variant_element:
                                for i in range(variant_element.model().rowCount()):
                                    item = (
                                        variant_element.model()
                                        .item(i)
                                        .data(Qt.ItemDataRole.UserRole)
                                    )
                                    if item:
                                        if len(main) >= 3:
                                            if item.get("en_name") == main[2]:
                                                variantIndex = i
                                                break
                                        else:
                                            variantIndex = 0
                                            break
                            else:
                                variantIndex = 0
                            if variant_element.currentIndex() != variantIndex:
                                variant_element.setCurrentIndex(variantIndex)

            if data.get("seed") is not None:
                if data.get("seed") > 0:
                    StateManager.Set(f"{self.path}.seed", data.get("seed"))
                    self.findChild(QSpinBox, "seed").setValue(int(data.get("seed")))
                else:
                    self.findChild(QSpinBox, "seed").setValue(0)
            if data.get("wins") is not None:
                StateManager.Set(f"{self.path}.wins", data.get("wins"))
            if data.get("losses") is not None:
                StateManager.Set(f"{self.path}.losses", data.get("losses"))
            if data.get("winPercentage") is not None:
                StateManager.Set(f"{self.path}.winPercentage", data.get("winPercentage"))
            if data.get("city"):
                StateManager.Set(f"{self.path}.city", data.get("city"))

            # Seeds set by hand in the seed editor win over loaded ones
            if data.get("gamerTag"):
                override = SeedManager.GetOverride(self.GetCurrentPlayerTag())
                if override is not None:
                    self.findChild(QSpinBox, "seed").setValue(override)
        finally:
            StateManager.ReleaseSaving()
            self.dataLock.release()
        self.ForgetUserEdits()
        self.RefreshSummary()
        self.RefreshDbState()

    def SeedOverrideChanged(self, tag):
        # Updates the seed shown when the seed editor changes this player's
        currentTag = self.GetCurrentPlayerTag()
        if not currentTag or (tag and tag != currentTag):
            return
        seed = SeedManager.GetSeed(currentTag)
        if seed is None and not tag:
            # Clearing every seed shouldn't wipe a seed that came with the set
            return
        self.findChild(QSpinBox, "seed").setValue(seed or 0)

    def GetCurrentPlayerTag(self):
        gamerTag = self.findChild(QWidget, "name").text()
        prefix = self.findChild(QWidget, "team").text()
        return prefix + " " + gamerTag if prefix else gamerTag

    def SavePlayerToDB(self, auto=False):
        """Saves the player to the player database, over what it holds for
        them. When saving automatically, the mains already saved for the
        game are kept: picking another character for one game doesn't change
        them."""
        tag = self.GetCurrentPlayerTag()
        if not tag.strip():
            return

        existing = PlayerDB.GetPlayer(tag) or {}

        playerData = {
            "prefix": self.findChild(QWidget, "team").text(),
            "gamerTag": self.findChild(QWidget, "name").text(),
            "name": self.findChild(QWidget, "real_name").text(),
            "twitter": self.findChild(QWidget, "twitter").text(),
            "pronoun": self.findChild(QWidget, "pronoun").text(),
            "custom_textbox": "\\n".join(self.custom_textbox.toPlainText().splitlines()),
        }

        codename = GameAssetManager.instance.selectedGame.get("codename")
        if codename:
            mains = []

            for i, (element, character, color, variant) in enumerate(self.character_elements):
                data = {}

                if character.currentData() is not None:
                    data["name"] = character.currentData().get("en_name")
                else:
                    data["name"] = ""

                data["skin"] = color.currentIndex()

                if data["skin"] == None:
                    data["skin"] = 0

                if variant.currentData():
                    data["variant"] = variant.currentData().get("en_name", "")
                else:
                    data["variant"] = ""

                if data["name"] != "":
                    mains.append([data.get("name"), data.get("skin"), data.get("variant")])

            savedMains = existing.get("mains")
            keepMains = auto and isinstance(savedMains, dict) and savedMains.get(codename)
            if mains and not keepMains:
                playerData["mains"] = {codename: mains}

        merged = dict(existing)
        merged.update(playerData)

        country = self.findChild(QComboBox, "country").currentData(Qt.ItemDataRole.UserRole)
        if country:
            merged["country_code"] = country.get("code")
        else:
            merged.pop("country_code", None)

        state = self.findChild(QComboBox, "state").currentData(Qt.ItemDataRole.UserRole)
        if state:
            merged["state_code"] = state.get("code")
        else:
            merged.pop("state_code", None)

        self.dbSaving = True
        self.RefreshDbState()
        try:
            PlayerDB.AddPlayers([merged], overwrite=True)
            PronounHelper.Add(playerData.get("pronoun"))
        finally:
            # Long enough to see that it saved
            QTimer.singleShot(500, self.SavingDone)

        if not auto:
            self.CharactersChanged(includeMains=True)

    def SavingDone(self):
        if self._deleted:
            return
        self.dbSaving = False
        self.RefreshDbState()

    def DeletePlayerFromDB(self):
        tag = self.GetCurrentPlayerTag()
        PlayerDB.DeletePlayer(tag)
        self.RefreshDbState()

    def Clear(self, no_mains=False):
        with StateManager.SaveBlock():
            self.DoClear(no_mains=no_mains)

    def DoClear(self, no_mains=False):
        self.ForgetUserEdits()
        with self.dataLock:
            for c in self.findChildren(QLineEdit):
                if c.objectName() != "" and c.objectName() != "qt_spinbox_lineedit":
                    if c.text() != "":
                        c.setText("")
                        c.editingFinished.emit()

            for c in self.findChildren(QSpinBox):
                c.setValue(0)
                c.lineEdit().editingFinished.emit()

            for c in self.findChildren(QPlainTextEdit):
                if c.toPlainText() != "":
                    c.clear()
                    c.textChanged.emit()

            for c in self.findChildren(QComboBox):
                if no_mains:
                    for charelem in self.character_elements:
                        for i in range(len(charelem)):
                            if charelem[i] == c:
                                break
                        else:
                            c.setCurrentIndex(0)
                        continue  # only executed if the inner loop DID break
                else:
                    c.setCurrentIndex(0)

        self.RefreshSummary()
        self.RefreshDbState()
        StateManager.Unset(f"{self.path}.online_avatar")
        StateManager.Unset(f"{self.path}.wins")
        StateManager.Unset(f"{self.path}.losses")
        StateManager.Unset(f"{self.path}.winPercentage")

    def SetRomanizedText(self):
        name = self.findChild(QWidget, "name").text()
        team = self.findChild(QWidget, "team").text()
        romanized_data = {"name": name, "team": team}
        country = self.findChild(QComboBox, "country")
        if country.currentData(Qt.ItemDataRole.UserRole) != None:
            country_code = country.currentData(Qt.ItemDataRole.UserRole).get("code")
            if country_code:
                romanized_data = {
                    "name": LocaleHelper.RomanizeTextFromCountry(name, country_code),
                    "team": LocaleHelper.RomanizeTextFromCountry(team, country_code),
                }
        StateManager.Set(f"{self.path}.romanized_data", romanized_data)
