# Checks the character grid: the mains and recent rows, searching, picking a
# character then a skin, the "None" tile, typing on the dropdown, and the
# variants' grid.
# Run from the repository root: python test/test_character_picker.py
# (with an optional path to save a screenshot of the grid to)
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QObject, QSize, Qt, Signal
from qtpy.QtGui import QColor, QIcon, QPixmap, QStandardItem, QStandardItemModel
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

app = QApplication.instance() or QApplication(sys.argv)

repoDir = os.path.abspath(".")
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))

CHARACTERS = {"Mario": 3, "Luigi": 1, "Peach": 2, "Bowser": 4, "Yoshi": 2, "Mr. Game & Watch": 1}
COLORS = {"Mario": "#e53935", "Luigi": "#43a047", "Peach": "#ec407a", "Bowser": "#fb8c00"}


def Swatch(color, size):
    pixmap = QPixmap(size)
    pixmap.fill(QColor(color))
    return pixmap


# The asset manager loads games on import; the grid needs its models
class FakeAssetSignals(QObject):
    onLoad = Signal()


class FakeAssetManager:
    instance = None

    def __init__(self):
        self.signals = FakeAssetSignals()
        self.selectedGame = {"codename": "fake"}
        self.stockIcons = {}
        self.characterModel = QStandardItemModel()
        self.characterModel.appendRow(QStandardItem(""))
        self.skinModels = {}
        for name, skins in sorted(CHARACTERS.items()):
            path = os.path.join(workDir, f"{name}.png")
            Swatch(COLORS.get(name, "#5e35b1"), QSize(32, 32)).save(path)
            self.stockIcons[name] = {0: path}
            item = QStandardItem(QIcon(path), name)
            item.setData(
                {"en_name": name, "display_name": name, "name": name}, Qt.ItemDataRole.UserRole
            )
            self.characterModel.appendRow(item)
            skinModel = QStandardItemModel()
            for skin in range(skins):
                shade = QColor(COLORS.get(name, "#5e35b1")).darker(100 + 25 * skin)
                skinItem = QStandardItem(QIcon(Swatch(shade, QSize(96, 72))), f"{name} {skin + 1}")
                skinModel.appendRow(skinItem)
            self.skinModels[name] = skinModel
        self.variantModel = QStandardItemModel()
        self.variantModel.appendRow(QStandardItem(""))
        for name, color in [("Classic", "#607d8b"), ("Gold", "#fbc02d"), ("Metal", "#90a4ae")]:
            item = QStandardItem(QIcon(Swatch(color, QSize(32, 32))), name)
            item.setData({"en_name": name, "display_name": name}, Qt.ItemDataRole.UserRole)
            self.variantModel.appendRow(item)


FakeAssetManager.instance = FakeAssetManager()
assetModule = types.ModuleType("src.GameAssetManager")
assetModule.GameAssetManager = FakeAssetManager
sys.modules["src.GameAssetManager"] = assetModule

os.chdir(workDir)
# Theme reads the icons from the repository
os.symlink(os.path.join(repoDir, "assets"), os.path.join(workDir, "assets"))

from src.CharacterPicker import CharacterCombo, RecentCharacters, SkinCombo, VariantCombo


def Row():
    """A character, skin and variant dropdown, as the player widgets make
    them. The variant one is character.variantCombo."""
    widget = QWidget()
    widget.setLayout(QHBoxLayout())
    character = CharacterCombo()
    character.setModel(FakeAssetManager.instance.characterModel)
    skin = SkinCombo(character)
    variant = VariantCombo(character)
    variant.setModel(FakeAssetManager.instance.variantModel)
    widget.layout().addWidget(character)
    widget.layout().addWidget(skin)
    widget.layout().addWidget(variant)

    def LoadSkins(_):
        data = character.currentData()
        model = FakeAssetManager.instance.skinModels.get(data.get("en_name")) if data else None
        skin.setModel(model if model is not None else QStandardItemModel())

    character.currentIndexChanged.connect(LoadSkins)
    widget.resize(400, 40)
    widget.show()
    return widget, character, skin


def Names(view):
    model = view.model()
    return [model.index(i, 0).data() for i in range(model.rowCount())]


def TestPickCharacterThenSkin():
    widget, character, skin = Row()
    character.mainsProvider = lambda: ["Peach", "Nobody"]
    character.showPopup()
    popup = character.popup
    assert popup is not None and popup.isVisible()
    mains, recent, everyone = [view for _, view in popup.sections]
    assert Names(mains) == ["Peach"]
    assert not recent.isVisibleTo(popup)
    assert Names(everyone) == [
        "None",
        "Bowser",
        "Luigi",
        "Mario",
        "Mr. Game & Watch",
        "Peach",
        "Yoshi",
    ]

    # Searching hides the rows above, Enter picks the first match
    QTest.keyClicks(popup.search, "mar")
    assert Names(everyone) == ["Mario"] and not mains.isVisibleTo(popup)
    QTest.keyClick(popup.search, Qt.Key.Key_Return)
    assert character.currentData()["en_name"] == "Mario"

    # Then the skins, the default one selected
    assert popup.step == "skin" and popup.isVisible()
    assert Names(everyone) == ["Mario 1", "Mario 2", "Mario 3"]
    assert everyone.currentIndex().row() == 0
    QTest.keyClick(popup.search, Qt.Key.Key_Right)
    QTest.keyClick(popup.search, Qt.Key.Key_Right)
    QTest.keyClick(popup.search, Qt.Key.Key_Return)
    assert skin.currentIndex() == 2, skin.currentIndex()
    assert character.popup is None
    assert RecentCharacters() == ["Mario"]
    print("TestPickCharacterThenSkin: OK")


def TestOneSkinClosesAndRecent():
    widget, character, skin = Row()
    character.showPopup()
    popup = character.popup
    _, recent = popup.sections[1]
    assert Names(recent) == ["Mario"]
    QTest.keyClicks(popup.search, "lui")
    QTest.keyClick(popup.search, Qt.Key.Key_Return)
    assert character.currentData()["en_name"] == "Luigi"
    # Only one skin: nothing to pick
    assert character.popup is None
    assert RecentCharacters()[:2] == ["Luigi", "Mario"]
    print("TestOneSkinClosesAndRecent: OK")


def TestSkinDropdownAndBack():
    widget, character, skin = Row()
    character.setCurrentIndex(character.findText("Bowser"))
    skin.setCurrentIndex(3)
    skin.showPopup()
    popup = character.popup
    assert popup.step == "skin"
    everyone = popup.sections[2][1]
    assert everyone.currentIndex().row() == 3
    # Backspace in the empty search goes back to the characters
    QTest.keyClick(popup.search, Qt.Key.Key_Backspace)
    assert popup.step == "character"
    popup.close()
    print("TestSkinDropdownAndBack: OK")


def TestNoneTileAndTyping():
    widget, character, skin = Row()
    character.setCurrentIndex(character.findText("Peach"))
    # Typing on the dropdown opens the grid with the text searched
    character.setFocus()
    QTest.keyClick(character, Qt.Key.Key_Y)
    popup = character.popup
    assert popup.search.text() == "y"
    popup.search.clear()
    everyone = popup.sections[2][1]
    everyone.picked.emit(0)
    assert character.currentIndex() == 0 and character.popup is None
    print("TestNoneTileAndTyping: OK")


def TestVariants():
    widget, character, skin = Row()
    variant = character.variantCombo
    character.setCurrentIndex(character.findText("Bowser"))
    skin.setCurrentIndex(2)
    variant.showPopup()
    popup = character.popup
    assert popup.step == "variant"
    everyone = popup.sections[2][1]
    assert Names(everyone) == ["None", "Classic", "Gold", "Metal"]
    assert not popup.sections[0][1].isVisibleTo(popup)
    QTest.keyClicks(popup.search, "gol")
    assert Names(everyone) == ["Gold"]
    QTest.keyClick(popup.search, Qt.Key.Key_Return)
    assert variant.currentData()["en_name"] == "Gold"
    assert character.popup is None
    # The character and skin are left alone
    assert character.currentData()["en_name"] == "Bowser" and skin.currentIndex() == 2

    # Typing on it searches; the None tile clears it
    variant.setFocus()
    QTest.keyClick(variant, Qt.Key.Key_M)
    popup = character.popup
    assert popup.step == "variant" and Names(popup.sections[2][1]) == ["Metal"]
    popup.search.clear()
    popup.sections[2][1].picked.emit(0)
    assert variant.currentIndex() == 0
    print("TestVariants: OK")


def Screenshot(path, theme=None):
    """Saves the characters to path and the skins to path with _skins."""
    if theme:
        from src.SettingsManager import SettingsManager
        from src.Theme import Theme

        SettingsManager.Set("appearance.theme", theme)
        Theme.Apply()
    path = path if os.path.isabs(path) else os.path.join(repoDir, path)
    widget, character, skin = Row()
    character.mainsProvider = lambda: ["Peach", "Bowser"]
    character.setCurrentIndex(character.findText("Mario"))
    character.showPopup()
    app.processEvents()
    character.popup.grab().save(path)
    skin.showPopup()
    app.processEvents()
    character.popup.grab().save(path.replace(".png", "_skins.png"))
    character.popup.close()
    character.variantCombo.setCurrentIndex(2)
    character.variantCombo.showPopup()
    app.processEvents()
    character.popup.grab().save(path.replace(".png", "_variants.png"))
    character.popup.close()


if __name__ == "__main__":
    try:
        TestPickCharacterThenSkin()
        TestOneSkinClosesAndRecent()
        TestSkinDropdownAndBack()
        TestNoneTileAndTyping()
        TestVariants()
        if len(sys.argv) > 1:
            Screenshot(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    finally:
        os.chdir(repoDir)
    print("OK")
