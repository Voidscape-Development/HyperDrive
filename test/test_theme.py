# Checks Theme's theme model: checking themes, importing and exporting
# them, and working out which theme is in use from the settings.
# Run from the repository root: python test/test_theme.py
import json
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None

from src.Theme import (
    _PRESETS,
    COLOR_KEYS,
    DEFAULT_ACCENT,
    DEFAULT_ACCENT_ON_LIGHT,
    DEFAULT_RADIUS,
    DEFAULT_SPACING,
    MAX_RADIUS,
    PRESET_PREFIX,
    THEME_DARK,
    THEME_LIGHT,
    BuiltinTheme,
    Contrast,
    ExportTheme,
    ImportTheme,
    NormalizeTheme,
    PresetNames,
    PresetTheme,
    Theme,
)


def Settings(appearance=None, **other):
    SettingsManager.settings = {"appearance": appearance or {}, **other}


def ExpectInvalid(data):
    try:
        NormalizeTheme(data)
    except ValueError:
        return
    raise AssertionError(f"Expected {data} to be rejected")


def TestNormalizeFillsMissing():
    theme = NormalizeTheme({"colors": {"accent": "#00ff88"}}, "Mine")
    dark = BuiltinTheme(THEME_DARK)
    assert theme["name"] == "Mine"
    assert theme["colors"]["accent"] == "#00ff88"
    assert theme["colors"]["window"] == dark["colors"]["window"]
    assert theme["radius"] == DEFAULT_RADIUS
    assert theme["spacing"] == DEFAULT_SPACING
    assert theme["font"] == ""
    assert set(theme["colors"]) == set(COLOR_KEYS)

    # A light background fills in from the light theme
    theme = NormalizeTheme({"colors": {"window": "#fafafa"}})
    assert theme["colors"]["text"] == BuiltinTheme(THEME_LIGHT)["colors"]["text"]


def TestNormalizeCleansValues():
    theme = NormalizeTheme(
        {
            "name": "  Spaced  ",
            "colors": {"window": "not a color", "accent": "#ABCDEF"},
            "radius": 99,
            "spacing": "huge",
            "font": 12,
        }
    )
    assert theme["name"] == "Spaced"
    assert theme["colors"]["window"] == BuiltinTheme(THEME_DARK)["colors"]["window"]
    assert theme["colors"]["accent"] == "#abcdef"
    assert theme["radius"] == MAX_RADIUS
    assert theme["spacing"] == DEFAULT_SPACING
    assert theme["font"] == ""
    assert NormalizeTheme({"colors": {"text": "#fff"}, "radius": -3})["radius"] == 0
    assert NormalizeTheme({"colors": {"text": "#fff"}, "radius": "x"})["radius"] == DEFAULT_RADIUS


def TestNormalizeRejects():
    for data in [
        None,
        [],
        "theme",
        {},
        {"colors": {}},
        {"colors": "red"},
        {"colors": {"other": "#fff"}},
    ]:
        ExpectInvalid(data)


def TestExportImport():
    with tempfile.TemporaryDirectory() as folder:
        theme = NormalizeTheme(
            {
                "colors": {"accent": "#f4b400"},
                "radius": 12,
                "spacing": "compact",
                "font": "DejaVu Serif",
            },
            "Midnight",
        )
        path = os.path.join(folder, "midnight.json")
        ExportTheme(theme, path)
        data = json.load(open(path))
        assert data["hyperdrive_theme"] == 1
        assert ImportTheme(path) == theme

        # The file name is used when the theme has none
        del data["name"]
        unnamed = os.path.join(folder, "Sunset.json")
        json.dump(data, open(unnamed, "w"))
        assert ImportTheme(unnamed)["name"] == "Sunset"

        # Files exported before the rename have the old key
        data["tsh_theme"] = data.pop("hyperdrive_theme")
        json.dump(data, open(unnamed, "w"))
        assert ImportTheme(unnamed)["name"] == "Sunset"

        for content in [
            '{"colors": {"text": "#fff"}}',
            "not json",
            "[1, 2]",
            '{"hyperdrive_theme": 1}',
        ]:
            bad = os.path.join(folder, "bad.json")
            open(bad, "w").write(content)
            try:
                ImportTheme(bad)
            except ValueError:
                continue
            raise AssertionError(f"Expected {content} to be rejected")

        try:
            ImportTheme(os.path.join(folder, "missing.json"))
        except ValueError:
            pass
        else:
            raise AssertionError("Expected a missing file to be rejected")


def TestMode():
    Settings()
    assert Theme.Mode() == THEME_DARK
    assert Theme.IsDark()

    # Light mode from before the Appearance settings
    Settings(light_mode=True)
    assert Theme.Mode() == THEME_LIGHT
    assert not Theme.IsDark()
    Settings({"theme": THEME_DARK}, light_mode=True)
    assert Theme.Mode() == THEME_DARK

    Settings({"theme": "custom:Mine", "custom_themes": {"Mine": {"colors": {"window": "#ffffff"}}}})
    assert Theme.Mode() == "custom:Mine"
    assert Theme.CustomThemeName() == "Mine"
    assert Theme.Current()["name"] == "Mine"
    assert not Theme.IsDark()

    # A custom theme that's gone falls back to the default
    Settings({"theme": "custom:Gone"})
    assert Theme.Mode() == THEME_DARK
    assert Theme.CustomThemeName() is None

    Settings({"theme": "nonsense"})
    assert Theme.Mode() == THEME_DARK


def TestPresets():
    names = PresetNames()
    assert list(names) == list(_PRESETS)
    for key in _PRESETS:
        # Every value is valid, so nothing was filled in from a built-in theme
        theme = PresetTheme(key)
        preset = _PRESETS[key]
        assert theme["name"] == names[key]
        assert theme["colors"] == preset["colors"], key

        # Text and secondary text read on the background and on panels
        c = theme["colors"]
        minimum = 15 if key.startswith("high_contrast") else 7
        for background in (c["window"], c["surface"]):
            assert Contrast(c["text"], background) >= minimum, key
            assert Contrast(c["muted"], background) >= 4.5, key

        Settings({"theme": PRESET_PREFIX + key, "accent_color": "#123456"})
        assert Theme.Mode() == PRESET_PREFIX + key
        assert Theme.PresetName() == key
        assert Theme.CustomThemeName() is None
        # A preset keeps its own accent
        assert Theme.Current() == theme

    # A preset that's gone falls back to the default
    Settings({"theme": PRESET_PREFIX + "gone"})
    assert Theme.Mode() == THEME_DARK
    assert Theme.PresetName() is None


def TestAccent():
    Settings({"theme": THEME_LIGHT, "accent_color": "#2f80ed"})
    assert Theme.Current()["colors"]["accent"] == "#2f80ed"
    Settings({"accent_color": "nope"})
    assert Theme.Current()["colors"]["accent"] == DEFAULT_ACCENT
    # The default amber is the logo's deeper one on the light theme
    Settings({"theme": THEME_LIGHT})
    assert Theme.Current()["colors"]["accent"] == DEFAULT_ACCENT_ON_LIGHT
    # Amber takes dark text, and is darkened as text on a light window
    colors = Theme.Colors()
    assert colors["onAccent"].name() == "#111111"
    assert Contrast(colors["accentText"], colors["window"]) >= 4.5
    Settings({"theme": THEME_DARK})
    colors = Theme.Colors()
    assert colors["accent"].name() == DEFAULT_ACCENT
    assert colors["onAccent"].name() == "#111111"
    assert Contrast(colors["accentText"], colors["window"]) >= 4.5
    # Text on a light accent is dark, on a dark accent white
    Settings({"accent_color": "#ffe066"})
    assert Theme.Colors()["onAccent"].name() == "#111111"
    Settings({"accent_color": "#1a237e"})
    assert Theme.Colors()["onAccent"].name() == "#ffffff"


def TestCustomThemes():
    Settings({"custom_themes": {"Good": {"colors": {"text": "#fff"}}, "Broken": "x"}})
    assert list(Theme.CustomThemes()) == ["Good"]

    Theme.SaveCustomTheme(NormalizeTheme({"colors": {"text": "#000"}}, "New"))
    assert sorted(Theme.CustomThemes()) == ["Good", "New"]
    assert Theme.UniqueName("New") == "New (2)"
    assert Theme.UniqueName("Other") == "Other"

    # Renaming replaces the old entry
    Theme.SaveCustomTheme(NormalizeTheme({"colors": {"text": "#000"}}, "Renamed"), "New")
    assert sorted(Theme.CustomThemes()) == ["Good", "Renamed"]

    Theme.DeleteCustomTheme("Good")
    assert sorted(Theme.CustomThemes()) == ["Renamed"]


def LinkColor(label):
    # The most common saturated color: the link's
    image = label.grab().toImage()
    counts = {}
    for x in range(image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if color.saturation() > 120:
                counts[color.name()] = counts.get(color.name(), 0) + 1
    return max(counts, key=counts.get) if counts else None


def TestLinksTakeAccent():
    from qtpy.QtWidgets import QApplication, QLabel

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    Settings({"theme": THEME_DARK, "accent_color": "#22c55e"})
    Theme.Apply()
    label = QLabel("Open <a href='http://localhost'>http://localhost:5500</a> now")
    label.resize(400, 30)
    label.show()
    app.processEvents()
    assert LinkColor(label) == Theme.Colors()["accentText"].name()

    # A label shown before the accent changed takes the new one too
    Settings({"theme": THEME_DARK, "accent_color": "#e11d48"})
    Theme.Apply()
    app.processEvents()
    assert LinkColor(label) == Theme.Colors()["accentText"].name()
    assert "<a href='http://localhost'>" in label.text()
    label.close()


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
