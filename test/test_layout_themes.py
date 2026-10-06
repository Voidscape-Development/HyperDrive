# Checks the layout theme model: checking themes, the CSS exported for the
# layouts, saving, importing and exporting themes, and the theme in use.
# Run from the repository root: python test/test_layout_themes.py
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

from src.StateManager import StateManager

StateManager.Set = lambda key, value: StateManager.state.__setitem__(key, value)

from src.LayoutOptions.TSHLayoutThemes import (
    DEFAULT_THEME,
    CssVariables,
    DefaultValues,
    ExportLayoutTheme,
    Fill,
    ImportLayoutTheme,
    LayoutThemeSchema,
    NormalizeLayoutTheme,
    StateExport,
    TSHLayoutThemes,
)


def ExpectInvalid(data):
    try:
        NormalizeLayoutTheme(data)
    except ValueError:
        return
    raise AssertionError(f"{data} should not be a layout theme")


def TestSchema():
    keys = set()
    for section in LayoutThemeSchema():
        for field in section.fields:
            key = (section.key, field.key)
            assert key not in keys, key
            keys.add(key)
            # Every default is valid for its own field
            assert (
                NormalizeLayoutTheme({"values": DefaultValues()})["values"][section.key][field.key]
                == field.default
            ), key
    print("TestSchema: OK")


def TestNormalize():
    ExpectInvalid(None)
    ExpectInvalid([])
    ExpectInvalid({"values": "nope"})

    # Empty theme: all defaults
    assert NormalizeLayoutTheme({}, "x") == {"name": "x", "values": DefaultValues()}

    theme = NormalizeLayoutTheme(
        {
            "name": " Mine ",
            "values": {
                "general": {
                    "primary_color": "#FF0000",
                    "text_color": "not a color",
                    "border_radius": "12",
                    "font_family": "  Roboto ",
                    "background": "#00ff00",
                    "unknown_field": 1,
                },
                "chip": {
                    "pronouns_display": "yes",
                    "seed_display": False,
                    "background": {"color": "#80112233", "gradient": True, "direction": "sideways"},
                },
                "bracket": {"score_background": 5},
                "not_a_section": {"a": 1},
            },
        }
    )
    values = theme["values"]
    assert theme["name"] == "Mine"
    assert values["general"]["primary_color"] == "#ff0000"
    assert values["general"]["text_color"] == "#ffffff"
    assert values["general"]["border_radius"] == 12
    assert values["general"]["font_family"] == "Roboto"
    # A plain color for a fill
    assert values["general"]["background"] == Fill("#00ff00")
    assert "unknown_field" not in values["general"]
    assert "not_a_section" not in values
    assert values["chip"]["pronouns_display"] is True
    assert values["chip"]["seed_display"] is False
    # Alpha is kept; missing and bad parts come from the default
    assert values["chip"]["background"] == {
        "color": "#80112233",
        "color2": "#121212",
        "gradient": True,
        "direction": "to right",
    }
    assert values["bracket"]["score_background"] == DefaultValues()["bracket"]["score_background"]

    # Out of range numbers are clamped
    assert (
        NormalizeLayoutTheme({"values": {"general": {"border_radius": 1000}}})["values"]["general"][
            "border_radius"
        ]
        == 64
    )
    assert (
        NormalizeLayoutTheme({"values": {"general": {"border_radius": True}}})["values"]["general"][
            "border_radius"
        ]
        == 0
    )
    print("TestNormalize: OK")


def TestCss():
    theme = NormalizeLayoutTheme(
        {
            "name": "t",
            "values": {
                "general": {"font_family": 'Bad"Font', "border_radius": 4},
                "chip": {
                    "text_color": "#80ff0000",
                    "background": {
                        "color": "#000000",
                        "color2": "#ffffff",
                        "gradient": True,
                        "direction": "to bottom",
                    },
                },
            },
        }
    )
    css = CssVariables(theme)
    assert css["--general-primary-color"] == "#d02670"
    assert css["--general-border-radius"] == "4px"
    assert css["--general-font-family"] == '"BadFont"'
    assert css["--chip-text-color"] == "rgba(255, 0, 0, 0.502)"
    assert css["--chip-background"] == "linear-gradient(to bottom, #000000, #ffffff)"
    assert css["--bracket-score-background"] == "#fe3636"
    # Toggles aren't CSS
    assert "--chip-pronouns-display" not in css

    assert CssVariables(NormalizeLayoutTheme({}))["--general-font-family"] == "inherit"

    exported = StateExport(theme)
    assert exported["name"] == "t"
    assert exported["values"]["chip"]["pronouns_display"] is True
    assert exported["stylesheet"].startswith(":root {\n")
    assert (
        "  --chip-background: linear-gradient(to bottom, #000000, #ffffff);\n"
        in exported["stylesheet"]
    )

    # The custom properties ApplyLayoutTheme() in layout/include/globals.js
    # maps onto the layouts' own
    defaults = CssVariables(NormalizeLayoutTheme({}))
    for key in (
        "--general-text-color",
        "--general-background",
        "--general-border-radius",
        "--general-chip-radius",
        "--general-primary-color",
        "--general-secondary-color",
        "--teams-team1-color",
        "--teams-team2-color",
        "--teams-team1-score-color",
        "--teams-team2-score-color",
        "--chip-text-color",
        "--chip-background",
        "--bracket-score-background",
        "--bracket-sponsor-background",
        "--bracket-winner-color",
        "--bracket-lines-color",
        "--stage-strike-striked-color",
        "--stage-strike-selected-color",
        "--versus-team1-sponsor-color",
        "--versus-team2-sponsor-color",
    ):
        assert key in defaults, key
    assert defaults["--stage-strike-striked-color"] == "rgba(0, 0, 0, 0.69)"
    print("TestCss: OK")


def TestLayoutDefaults():
    values = DefaultValues()
    # The default theme leaves the layouts' own colors alone...
    assert values["general"]["apply_colors"] is False
    assert values["versus"]["custom_sponsor_colors"] is False
    # ...and its display options show everything, as the layouts do
    assert values["general"]["text_case"] == "layout"
    assert values["animation"] == {"enabled": True, "speed": 100}
    assert all(values["chip"][k] is True for k in values["chip"] if k.endswith("_display"))

    theme = NormalizeLayoutTheme(
        {
            "values": {
                "general": {"text_case": "shouting"},
                "animation": {"speed": 1000},
                "standings": {"highlight_top": -3},
            }
        }
    )["values"]
    assert theme["general"]["text_case"] == "layout"
    assert theme["animation"]["speed"] == 400
    assert theme["standings"]["highlight_top"] == 0
    print("TestLayoutDefaults: OK")


def TestImportExport():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "Shared.json")
        theme = NormalizeLayoutTheme(
            {"name": "Shared", "values": {"general": {"primary_color": "#123456"}}}
        )
        ExportLayoutTheme(theme, path)
        with open(path) as f:
            assert json.load(f)["tsh_layout_theme"] == 1
        assert ImportLayoutTheme(path) == theme

        # No name: the file's
        with open(path, "w") as f:
            json.dump({"tsh_layout_theme": 1, "values": {}}, f)
        assert ImportLayoutTheme(path)["name"] == "Shared"

        for content in ["{}", "not json", json.dumps({"values": {}})]:
            with open(path, "w") as f:
                f.write(content)
            try:
                ImportLayoutTheme(path)
                raise AssertionError(content)
            except ValueError:
                pass
        try:
            ImportLayoutTheme(os.path.join(folder, "missing.json"))
            raise AssertionError("missing file")
        except ValueError:
            pass
    print("TestImportExport: OK")


def TestManager():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "user_data", "layout_themes.json")
        TSHLayoutThemes.Load(path)
        assert TSHLayoutThemes.ActiveName() == DEFAULT_THEME
        assert TSHLayoutThemes.Active()["values"] == DefaultValues()
        assert TSHLayoutThemes.UserThemes() == {}

        TSHLayoutThemes.ExportToState()
        assert StateManager.state["layout_theme"]["name"] == "Default"

        # The default theme can't be overwritten
        for name in ("", DEFAULT_THEME):
            try:
                TSHLayoutThemes.SaveTheme({"name": name, "values": {}})
                raise AssertionError(name)
            except ValueError:
                pass

        TSHLayoutThemes.SaveTheme(
            {"name": "Mine", "values": {"general": {"primary_color": "#111111"}}}
        )
        assert TSHLayoutThemes.UniqueName("Mine") == "Mine (2)"
        assert TSHLayoutThemes.UniqueName("Default") == "Default (2)"
        # Saving a theme that isn't in use doesn't change the layouts
        assert StateManager.state["layout_theme"]["name"] == "Default"

        TSHLayoutThemes.SetActive("Mine")
        assert StateManager.state["layout_theme"]["name"] == "Mine"
        assert StateManager.state["layout_theme"]["css"]["--general-primary-color"] == "#111111"

        # Edits to the theme in use go straight to the layouts
        TSHLayoutThemes.SaveTheme(
            {"name": "Mine", "values": {"general": {"primary_color": "#222222"}}}
        )
        assert StateManager.state["layout_theme"]["css"]["--general-primary-color"] == "#222222"

        # Kept in the file
        TSHLayoutThemes.Load(path)
        assert TSHLayoutThemes.ActiveName() == "Mine"
        assert TSHLayoutThemes.Active()["values"]["general"]["primary_color"] == "#222222"

        # Renaming the theme in use keeps it in use
        TSHLayoutThemes.SaveTheme(dict(TSHLayoutThemes.Active(), name="Renamed"), "Mine")
        assert TSHLayoutThemes.ActiveName() == "Renamed"
        assert list(TSHLayoutThemes.UserThemes()) == ["Renamed"]
        assert StateManager.state["layout_theme"]["name"] == "Renamed"

        # Unknown themes fall back to the default
        TSHLayoutThemes.SetActive("Nope")
        assert TSHLayoutThemes.ActiveName() == DEFAULT_THEME

        TSHLayoutThemes.SetActive("Renamed")
        TSHLayoutThemes.DeleteTheme("Renamed")
        assert TSHLayoutThemes.ActiveName() == DEFAULT_THEME
        assert StateManager.state["layout_theme"]["name"] == "Default"

        # A broken file means no user themes, not a crash
        with open(path, "w") as f:
            f.write("[1, 2")
        TSHLayoutThemes.Load(path)
        assert TSHLayoutThemes.UserThemes() == {}
        with open(path, "w") as f:
            json.dump({"active": "x", "themes": {"x": {"values": "bad"}, "y": {"values": {}}}}, f)
        TSHLayoutThemes.Load(path)
        assert list(TSHLayoutThemes.UserThemes()) == ["y"]
        assert TSHLayoutThemes.ActiveName() == DEFAULT_THEME
    print("TestManager: OK")


if __name__ == "__main__":
    TestSchema()
    TestNormalize()
    TestCss()
    TestLayoutDefaults()
    TestImportExport()
    TestManager()
