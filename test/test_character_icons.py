# Checks where a character's icon comes from when the game's icon pack has
# none for it (another installed pack), and the placeholder shown when no
# pack has one.
# Run from the repository root: python test/test_character_icons.py
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package
helpers = types.ModuleType("src.Helpers")
helpers.__path__ = [os.path.abspath("src/Helpers")]
sys.modules["src.Helpers"] = helpers

from qtpy.QtWidgets import QApplication

from src.Helpers.CharacterIconHelper import IconPackOrder, Initials, PlaceholderPixmap

app = QApplication.instance() or QApplication(sys.argv)


def TestIconPackOrder():
    assets = {
        "base_files": {"name": "Game"},
        "base_files/icon": {"type": ["icon"]},
        "full": {"type": ["full"]},
        "art": {"type": ["art"]},
        "pixel_art": {"type": ["icon"]},
        "portrait": {"type": "portrait"},
        "stage_icon": {"type": ["stage_icon"]},
        "variant_icon": {"type": ["variant_icon"]},
        "icon_hd": {"type": ["icon_hd"]},
    }
    # The icon pack, then other icons, portraits, full art and the rest;
    # never the base config or packs that don't picture characters
    assert IconPackOrder(assets, "base_files/icon") == [
        "base_files/icon",
        "icon_hd",
        "pixel_art",
        "portrait",
        "full",
        "art",
    ]
    # Whatever pack the loader picked comes first
    assert IconPackOrder(assets, "art")[0] == "art"
    # A missing pick, or no packs at all
    assert IconPackOrder({"full": {"type": ["full"]}}, "") == ["full"]
    assert IconPackOrder({}, "") == []
    assert IconPackOrder(None, "") == []


def TestInitials():
    assert Initials("Baby Luigi") == "BL"
    assert Initials("Tifa") == "TI"
    assert Initials("Z+F Splat Charger") == "ZS"
    assert Initials("Roger Jr.") == "RJ"
    assert Initials("Bosch") == "BO"
    assert Initials("") == "?"
    assert Initials(None) == "?"


def TestPlaceholderPixmap():
    pixmap = PlaceholderPixmap("Arjun", 40)
    assert not pixmap.isNull()
    assert pixmap.width() == 40 * pixmap.devicePixelRatio()
    # Not just a transparent square
    image = pixmap.toImage()
    assert image.pixelColor(20, 20).alpha() > 0


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
