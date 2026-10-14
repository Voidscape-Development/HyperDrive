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
