# Checks putting a player's mains in the character slots (ApplyMains, shared
# by the scoreboard and team battle player widgets) with more than one
# character slot: a character never ends up in two slots, whether the mains
# repeat one, a set's selected character is loaded, or the mains replace
# ones loaded from the player database before.
# Run from the repository root: python test/test_apply_mains.py
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import Qt
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QApplication, QComboBox

app = QApplication.instance() or QApplication(sys.argv)

from src.GameAssetManager import GameAssetManager
from src.PlayerWidgetMixin import PlayerWidgetMixin

CHARACTERS = ["Mario", "Fox", "Falco", "Sheik"]


def Model(names):
    model = QStandardItemModel()
    model.appendRow(QStandardItem(""))
    for n in names:
        item = QStandardItem(n)
        item.setData({"en_name": n}, Qt.ItemDataRole.UserRole)
        model.appendRow(item)
    return model


class FakePlayer(PlayerWidgetMixin):
    def __init__(self, slots):
        self.character_elements = []
        for _ in range(slots):
            character, color, variant = QComboBox(), QComboBox(), QComboBox()
            character.setModel(Model(CHARACTERS))
            color.setModel(Model([str(i) for i in range(8)]))
            variant.setModel(Model(["A", "B"]))
            self.character_elements.append([None, character, color, variant])

    def Slots(self):
        return [
            (c.currentData(Qt.ItemDataRole.UserRole) or {}).get("en_name")
            for _, c, _, _ in self.character_elements
        ]

    def Skins(self):
        return [color.currentIndex() for _, _, color, _ in self.character_elements]


GameAssetManager.instance = types.SimpleNamespace(
    selectedGame={"codename": "ssbm", "base_game_dir": "ssbm"}
)


def TestDictMains():
    p = FakePlayer(3)
    p.ApplyMains({"ssbm": [["Fox", 2], ["Falco"]]})
    assert p.Slots() == ["Fox", "Falco", None], p.Slots()
    assert p.Skins() == [2, 0, 0], p.Skins()
    print("TestDictMains: OK")


def TestRepeatedMains():
    # e.g. two start.gg characters that are the same character here
    p = FakePlayer(3)
    p.ApplyMains({"ssbm": [["Fox"], ["Fox", 1], ["Sheik"]]})
    assert p.Slots() == ["Fox", "Sheik", None], p.Slots()
    print("TestRepeatedMains: OK")


def TestSelectedCharacter():
    # A set's selected character goes in the first slot only, instead of in
    # every slot
    p = FakePlayer(3)
    p.ApplyMains(["Sheik", 3])
    assert p.Slots() == ["Sheik", None, None], p.Slots()
    assert p.Skins() == [3, 0, 0], p.Skins()
    print("TestSelectedCharacter: OK")


def TestSelectedCharacterOverSavedMains():
    # Saved mains first, then the set's selected character: it's the second
    # main, so its old slot is emptied
    p = FakePlayer(3)
    p.ApplyMains({"ssbm": [["Fox"], ["Sheik"], ["Falco"]]})
    p.ApplyMains(["Sheik", 0])
    assert p.Slots() == ["Sheik", None, "Falco"], p.Slots()
    print("TestSelectedCharacterOverSavedMains: OK")


def TestFewerMainsOverSavedMains():
    # Mains from the provider replacing more saved ones keep the other saved
    # characters, but not one now in an earlier slot
    p = FakePlayer(2)
    p.ApplyMains({"ssbm": [["Fox"], ["Falco"]]})
    p.ApplyMains({"ssbm": [["Falco"]]})
    assert p.Slots() == ["Falco", None], p.Slots()

    p = FakePlayer(2)
    p.ApplyMains({"ssbm": [["Fox"], ["Falco"]]})
    p.ApplyMains({"ssbm": [["Mario"]]})
    assert p.Slots() == ["Mario", "Falco"], p.Slots()
    print("TestFewerMainsOverSavedMains: OK")


def TestOtherGame():
    p = FakePlayer(2)
    p.ApplyMains({"ssbu": [["Fox"]]})
    assert p.Slots() == [None, None], p.Slots()
    print("TestOtherGame: OK")


if __name__ == "__main__":
    TestDictMains()
    TestRepeatedMains()
    TestSelectedCharacter()
    TestSelectedCharacterOverSavedMains()
    TestFewerMainsOverSavedMains()
    TestOtherGame()
