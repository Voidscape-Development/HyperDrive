# Checks the color picker: named swatch groups hand back their data, typed
# colors, and saving and removing custom colors.
# Run from the repository root: python test/test_color_picker.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None
SettingsManager.settings = {}

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QToolButton

app = QApplication.instance() or QApplication(sys.argv)

from src.ColorButton import ColorButton
from src.ColorPicker import ColorPicker, CustomColors, SaveCustomColors, Swatch, SwatchButton

picks = []


def Open(current="#ff0000", groups=None, alpha=False):
    picker = ColorPicker(current, groups, alpha)
    picker.picked.connect(lambda color, data: picks.append((color, data)))
    return picker


# A group's swatch is picked with its data; the current color is marked
groups = [("Game", [Swatch("#ff0000", "Red", 1), Swatch("#0000ff", "Blue", 2, "Note")])]
picker = Open(groups=groups)
swatches = picker.findChildren(SwatchButton)
assert [s.toolTip() for s in swatches] == ["Red", "Blue\nNote"]
assert swatches[0].selected and not swatches[1].selected
swatches[1].click()
assert picks[-1] == ("#0000ff", 2)

# Typed colors, with or without the #; invalid ones are ignored
picker = Open()
picker.hex.setText("00ff00")
QTest.keyClick(picker.hex, Qt.Key.Key_Return)
assert picks[-1] == ("#00ff00", None)
picker = Open()
count = len(picks)
picker.hex.setText("nope")
QTest.keyClick(picker.hex, Qt.Key.Key_Return)
assert len(picks) == count

# See-through colors keep their alpha only when the button allows it
picker = Open(alpha=True)
picker.hex.setText("#80112233")
QTest.keyClick(picker.hex, Qt.Key.Key_Return)
assert picks[-1] == ("#80112233", None)

# Custom colors: saved once each, picked, and removed with a right-click
SaveCustomColors(["#123456", "#123456", "not a color"])
assert CustomColors() == ["#123456"]
picker = Open("#abcdef")
add = [b for b in picker.findChildren(QToolButton) if b.text() == "+"][0]
add.click()
assert CustomColors() == ["#123456", "#abcdef"]
custom = [b for b in picker.findChildren(SwatchButton) if b.toolTip().startswith("#123456")][0]
custom.customContextMenuRequested.emit(custom.rect().center())
assert CustomColors() == ["#abcdef"]

# The button takes the picked color and reports a swatch's data
button = ColorButton(color="#ff0000")
button.swatchGroups = lambda: groups
picked = []
button.swatchPicked.connect(picked.append)
button.onPicked("#0000ff", 2)
assert button.color() == "#0000ff" and picked == [2]
button.onPicked("#00ff00", None)
assert button.color() == "#00ff00" and picked == [2]

print("All color picker tests passed")
