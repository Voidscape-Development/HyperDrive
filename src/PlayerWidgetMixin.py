import os

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .CharacterPicker import MainsOf
from .GameAssetManager import GameAssetManager
from .Helpers.CountryHelper import CountryHelper
from .Helpers.DynamicExport import DynamicExport
from .PlayerDB import PlayerDB
from .StateManager import StateManager


def _SetCharacter(combo: QComboBox, text: str):
    found = combo.findText(text)
    if found != -1:
        combo.setCurrentIndex(found)
    else:
        combo.setCurrentText(text)


def _IndexOf(combo: QComboBox, en_name):
    """The row of the item with this en_name, or 0 (none) if there isn't one"""
    model = combo.model()
    for i in range(model.rowCount()):
        item = model.index(i, 0).data(Qt.ItemDataRole.UserRole)
        if item and item.get("en_name") == en_name:
            return i
    return 0


class PlayerWidgetMixin:
    """Methods shared by ScoreboardPlayerWidget and TeamPlayerWidget. They
    use the widgets' path, dataLock, character_elements and child fields."""

    def GetCurrentPlayerTag(self):
        gamerTag = self.findChild(QWidget, "name").text()
        prefix = self.findChild(QWidget, "team").text()
        return prefix + " " + gamerTag if prefix else gamerTag

    def SavedMains(self):
        """The mains saved in the player DB for the player in this widget,
        shown first in the character grid."""
        return MainsOf(PlayerDB.GetPlayer(self.GetCurrentPlayerTag()))

    def ExportPlayerImages(self, onlineAvatar=None):
        with self.dataLock:
            team = self.findChild(QLineEdit, "team").text()
            name = self.findChild(QLineEdit, "name").text()

            StateManager.Set(f"{self.path}.online_avatar", onlineAvatar)

            # Local avatar, sponsor logos and custom data, kept up to date
            DynamicExport.ExportPlayerMedia(name, team, self.path)

    def SwapCharacters(self, index1: int, index2: int):
        with StateManager.SaveBlock():
            self.DoSwapCharacters(index1, index2)

    def DoSwapCharacters(self, index1: int, index2: int):
        if index2 > len(self.character_elements) - 1:
            index2 = 0

        # [_, character combo, skin combo, ...]
        char1 = self.character_elements[index1]
        char2 = self.character_elements[index2]
        character1, skin1 = char1[1].currentText(), char1[2].currentIndex()

        _SetCharacter(char1[1], char2[1].currentText())
        char1[2].setCurrentIndex(char2[2].currentIndex())
        _SetCharacter(char2[1], character1)
        char2[2].setCurrentIndex(skin1)

        self.CharactersChanged()

    def ApplyMains(self, mains):
        """Puts a player's mains in the character slots, in order. mains is
        either a {game codename: [[name, skin, variant], ...]} dict or a
        single [name, skin] character (a set's selected character). The
        characters already in the slots (e.g. the player database's mains)
        move down after them, so none is lost while there's room, and a
        character is only ever put in one slot."""
        if isinstance(mains, dict):
            game = GameAssetManager.instance.selectedGame or {}
            codename = game.get("codename")
            entries = mains.get(codename) or mains.get(game.get("base_game_dir", codename)) or []
        elif isinstance(mains, list) and mains and isinstance(mains[0], str):
            entries = [mains]
        else:
            entries = []

        current = []
        for _, character, color, variant in self.character_elements:
            data = character.currentData(Qt.ItemDataRole.UserRole)
            if data and data.get("en_name"):
                variantData = variant.currentData(Qt.ItemDataRole.UserRole) if variant else None
                current.append(
                    [data["en_name"], color.currentIndex(), (variantData or {}).get("en_name")]
                )

        unique = []
        for main in entries + current:
            if main and main[0] and main[0] not in [m[0] for m in unique]:
                unique.append(main)

        for i, (_, character, color, variant) in enumerate(self.character_elements):
            main = unique[i] if i < len(unique) else [None]
            characterIndex = _IndexOf(character, main[0])
            if character.currentIndex() != characterIndex:
                character.setCurrentIndex(characterIndex)
            skin = int(main[1]) if len(main) > 1 and main[1] is not None else 0
            if color.currentIndex() != skin:
                color.setCurrentIndex(skin)
            if variant:
                variantIndex = _IndexOf(variant, main[2]) if len(main) >= 3 else 0
                if variant.currentIndex() != variantIndex:
                    variant.setCurrentIndex(variantIndex)

    def LoadStates(self, index):
        country = self.findChild(QComboBox, "country").currentData(Qt.ItemDataRole.UserRole)
        countryData = CountryHelper.countries.get((country or {}).get("code"), {})

        stateModel = QStandardItemModel()

        noState = QStandardItem()
        noState.setData({}, Qt.ItemDataRole.UserRole)
        stateModel.appendRow(noState)

        for state_code, stateData in (countryData.get("states") or {}).items():
            # Windows has some weird thing with files named CON.png. In case a state code is CON,
            # we try to load _CON.png instead
            path = f"./assets/state_flag/{countryData.get('code')}/{'_CON' if state_code == 'CON' else state_code}.png"
            stateData["asset"] = path if os.path.exists(path) else None

            item = QStandardItem()
            item.setIcon(QIcon(stateData["asset"]))
            item.setData(stateData, Qt.ItemDataRole.UserRole)
            item.setData(f"{stateData['name']} ({state_code})", Qt.ItemDataRole.EditRole)
            stateModel.appendRow(item)

        state: QComboBox = self.findChild(QComboBox, "state")
        state.setModel(stateModel)
        state.setCurrentIndex(0)

    def LoadSkinOptions(self, element, target):
        characterData = element.currentData()
        target.setModel(
            GameAssetManager.instance.skinModels.get(characterData.get("en_name"))
            if characterData
            else QStandardItemModel()
        )
