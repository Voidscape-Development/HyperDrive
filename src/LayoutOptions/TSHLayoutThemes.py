# Layout themes: the colors, fonts and display options the stream layouts use,
# so a whole look can be switched or shared without editing the layouts. A
# theme is a value for each field of LayoutThemeSchema(), grouped by section.
# There's a built-in default theme (the schema's defaults) and any number of
# user themes, which can be imported and exported as .json files. The theme in
# use is exported to the program state as "layout_theme": its values, plus
# ready to use CSS custom properties ("css" and "stylesheet") for layouts.
import json
import os

import orjson
from loguru import logger
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from ..StateManager import StateManager

THEMES_FILE = "./user_data/layout_themes.json"
THEME_FILE_VERSION = 1

# The built-in theme's name in the file, whatever its translated label
DEFAULT_THEME = "default"

FIELD_CHECKBOX = "checkbox"
FIELD_COLOR = "color"
# A color, or a linear gradient between two colors
FIELD_FILL = "fill"
FIELD_DROPDOWN = "dropdown"
FIELD_NUMBER = "number"
FIELD_FONT = "font"
FIELD_TEXT = "text"

GRADIENT_DIRECTIONS = [
    "to top left",
    "to top",
    "to top right",
    "to left",
    "to right",
    "to bottom left",
    "to bottom",
    "to bottom right",
]


def Fill(color, color2=None, gradient=False, direction="to right"):
    return {"color": color, "color2": color2 or color, "gradient": gradient, "direction": direction}


class Field:
    def __init__(
        self,
        key,
        label,
        type,
        default,
        options=None,
        minimum=0,
        maximum=100,
        suffix="",
        tooltip=None,
    ):
        self.key = key
        self.label = label
        self.type = type
        self.default = default
        # FIELD_DROPDOWN: [(value, label), ...]
        self.options = options or []
        # FIELD_NUMBER
        self.minimum = minimum
        self.maximum = maximum
        self.suffix = suffix
        self.tooltip = tooltip


class Section:
    def __init__(self, key, label, fields):
        self.key = key
        self.label = label
        self.fields = fields


def _tr(text):
    return QApplication.translate("layout_themes", text)


def GradientDirectionLabels():
    return [
        ("to top left", _tr("Up and left")),
        ("to top", _tr("Up")),
        ("to top right", _tr("Up and right")),
        ("to left", _tr("Left")),
        ("to right", _tr("Right")),
        ("to bottom left", _tr("Down and left")),
        ("to bottom", _tr("Down")),
        ("to bottom right", _tr("Down and right")),
    ]


def LayoutThemeSchema():
    """Everything a layout theme sets. Adding a field here is all it takes for
    it to be editable, saved in themes and exported."""
    # Colors, fonts and shapes only reach the layouts with "apply_colors" on,
    # so the default theme leaves every layout looking as it was made. Display
    # options and animations always apply (their defaults change nothing).
    return [
        Section(
            "general",
            _tr("General"),
            [
                Field(
                    "apply_colors",
                    _tr("Use this theme's colors in layouts"),
                    FIELD_CHECKBOX,
                    False,
                    tooltip=_tr(
                        "Off: layouts keep their own colors and corners, and only this theme's "
                        "display options, font and animations apply"
                    ),
                ),
                Field(
                    "primary_color",
                    _tr("Primary color"),
                    FIELD_COLOR,
                    "#d02670",
                    tooltip=_tr("Highlights: winners, the current set, the selected stage"),
                ),
                Field(
                    "secondary_color",
                    _tr("Secondary color"),
                    FIELD_COLOR,
                    "#121212",
                    tooltip=_tr("Headers and labels behind the primary color"),
                ),
                Field("text_color", _tr("Text color"), FIELD_COLOR, "#ffffff"),
                Field("background", _tr("Background"), FIELD_FILL, Fill("#121212")),
                Field(
                    "font_family",
                    _tr("Font"),
                    FIELD_FONT,
                    "",
                    tooltip=_tr("Leave empty to use each layout's own font"),
                ),
                Field(
                    "text_case",
                    _tr("Text case"),
                    FIELD_DROPDOWN,
                    "layout",
                    options=[
                        ("layout", _tr("Layout default")),
                        ("uppercase", _tr("UPPERCASE")),
                        ("none", _tr("As typed")),
                    ],
                ),
                Field(
                    "text_outline",
                    _tr("Text outline"),
                    FIELD_CHECKBOX,
                    True,
                    tooltip=_tr("The thin contrasting outline around all text"),
                ),
                Field(
                    "border_radius",
                    _tr("Corner roundness"),
                    FIELD_NUMBER,
                    0,
                    minimum=0,
                    maximum=64,
                    suffix="px",
                ),
                Field(
                    "chip_radius",
                    _tr("Small corner roundness"),
                    FIELD_NUMBER,
                    5,
                    minimum=0,
                    maximum=64,
                    suffix="px",
                    tooltip=_tr("Badges, seeds and other small boxes"),
                ),
            ],
        ),
        Section(
            "animation",
            _tr("Animations"),
            [
                Field(
                    "enabled",
                    _tr("Animate changes"),
                    FIELD_CHECKBOX,
                    True,
                    tooltip=_tr("Off: layouts change instantly, without fades or slides"),
                ),
                Field(
                    "speed",
                    _tr("Animation speed"),
                    FIELD_NUMBER,
                    100,
                    minimum=25,
                    maximum=400,
                    suffix="%",
                    tooltip=_tr("Higher is faster"),
                ),
            ],
        ),
        Section(
            "teams",
            _tr("Teams"),
            [
                Field(
                    "team1_color",
                    _tr("Team 1 color"),
                    FIELD_COLOR,
                    "#e53935",
                    tooltip=_tr(
                        "Used where a layout has no scoreboard team color, e.g. brackets and top 8"
                    ),
                ),
                Field("team2_color", _tr("Team 2 color"), FIELD_COLOR, "#1e88e5"),
                Field("team1_score_color", _tr("Team 1 score text"), FIELD_COLOR, "#ffffff"),
                Field("team2_score_color", _tr("Team 2 score text"), FIELD_COLOR, "#ffffff"),
            ],
        ),
        Section(
            "chip",
            _tr("Player chips"),
            [
                Field("pronouns_display", _tr("Display player pronouns"), FIELD_CHECKBOX, True),
                Field("seed_display", _tr("Display player seed number"), FIELD_CHECKBOX, True),
                Field(
                    "social_media_display", _tr("Display player social media"), FIELD_CHECKBOX, True
                ),
                Field(
                    "country_flag_display", _tr("Display player country flag"), FIELD_CHECKBOX, True
                ),
                Field("state_flag_display", _tr("Display player state flag"), FIELD_CHECKBOX, True),
                Field("avatar_display", _tr("Display player avatar"), FIELD_CHECKBOX, True),
                Field("losers_display", _tr("Display losers [L] badge"), FIELD_CHECKBOX, True),
                Field("text_color", _tr("Text color"), FIELD_COLOR, "#ffffff"),
                Field("background", _tr("Background"), FIELD_FILL, Fill("#121212")),
            ],
        ),
        Section(
            "bracket",
            _tr("Bracket"),
            [
                Field("avatar_display", _tr("Display player avatar"), FIELD_CHECKBOX, True),
                Field("character_display", _tr("Display player character"), FIELD_CHECKBOX, True),
                Field(
                    "country_flag_display", _tr("Display player country flag"), FIELD_CHECKBOX, True
                ),
                Field("state_flag_display", _tr("Display player state flag"), FIELD_CHECKBOX, True),
                Field("seed_display", _tr("Display player seed number"), FIELD_CHECKBOX, True),
                Field("round_names_display", _tr("Display round names"), FIELD_CHECKBOX, True),
                Field(
                    "identifier_display",
                    _tr("Display set letters"),
                    FIELD_CHECKBOX,
                    False,
                    tooltip=_tr("The set's letter (A, B...) next to each set"),
                ),
                Field(
                    "pending_display",
                    _tr("Display where players come from"),
                    FIELD_CHECKBOX,
                    True,
                    tooltip=_tr('Shows e.g. "Winner of C" in sets still waiting for a player'),
                ),
                Field("dim_losers", _tr("Dim players who lost the set"), FIELD_CHECKBOX, True),
                Field(
                    "score_background",
                    _tr("Score background"),
                    FIELD_FILL,
                    Fill("#fe3636", "#121212"),
                ),
                Field(
                    "sponsor_background",
                    _tr("Sponsor background"),
                    FIELD_FILL,
                    Fill("#fe3636", "#121212"),
                ),
                Field("winner_color", _tr("Winner highlight"), FIELD_COLOR, "#d02670"),
                Field("lines_color", _tr("Bracket lines color"), FIELD_COLOR, "#000000"),
                Field(
                    "focus_color",
                    _tr("Focus highlight"),
                    FIELD_COLOR,
                    "#d02670",
                    tooltip=_tr("Outline of the sets the bracket focus layout zooms to"),
                ),
                Field(
                    "focus_dim",
                    _tr("Opacity of sets out of focus"),
                    FIELD_NUMBER,
                    30,
                    minimum=0,
                    maximum=100,
                    suffix="%",
                    tooltip=_tr("In the bracket focus layout, while it zooms to some sets"),
                ),
                Field(
                    "focus_max_zoom",
                    _tr("Bracket focus maximum zoom"),
                    FIELD_NUMBER,
                    200,
                    minimum=50,
                    maximum=500,
                    suffix="%",
                    tooltip=_tr(
                        "How big the bracket focus layout draws a set it zooms to, at most"
                    ),
                ),
                Field(
                    "focus_label_display",
                    _tr("Display what's in focus"),
                    FIELD_CHECKBOX,
                    True,
                    tooltip=_tr(
                        "The bracket focus layout's caption, e.g. the round or the player in focus"
                    ),
                ),
            ],
        ),
        Section(
            "standings",
            _tr("Standings"),
            [
                Field("game_diff_display", _tr("Display game difference"), FIELD_CHECKBOX, True),
                Field("points_display", _tr("Display points"), FIELD_CHECKBOX, True),
                Field(
                    "buchholz_display",
                    _tr("Display Buchholz (swiss)"),
                    FIELD_CHECKBOX,
                    False,
                    tooltip=_tr("The sum of the opponents' points, used to break ties"),
                ),
                Field(
                    "highlight_top",
                    _tr("Highlight the top"),
                    FIELD_NUMBER,
                    0,
                    minimum=0,
                    maximum=64,
                    tooltip=_tr(
                        "Highlights this many players at the top, e.g. the ones going on. 0 for none"
                    ),
                ),
            ],
        ),
        Section(
            "stage_strike",
            _tr("Stage strike"),
            [
                Field("stage_names_display", _tr("Display stage names"), FIELD_CHECKBOX, True),
                Field("striker_display", _tr("Display who struck or picked"), FIELD_CHECKBOX, True),
                Field("striked_color", _tr("Struck stage tint"), FIELD_COLOR, "#b0000000"),
                Field("selected_color", _tr("Selected stage outline"), FIELD_COLOR, "#d02670"),
            ],
        ),
        Section(
            "versus",
            _tr("Versus"),
            [
                Field(
                    "custom_sponsor_colors",
                    _tr("Custom sponsor colors"),
                    FIELD_CHECKBOX,
                    False,
                    tooltip=_tr("Off: sponsors take a lighter shade of the team's color"),
                ),
                Field("team1_sponsor_color", _tr("Team 1 sponsor color"), FIELD_COLOR, "#000000"),
                Field("team2_sponsor_color", _tr("Team 2 sponsor color"), FIELD_COLOR, "#000000"),
            ],
        ),
    ]


def DefaultValues(schema=None):
    return {
        section.key: {field.key: _Copy(field.default) for field in section.fields}
        for section in (schema or LayoutThemeSchema())
    }


def _Copy(value):
    return dict(value) if isinstance(value, dict) else value


def _Color(value, default):
    color = QColor(value.strip()) if isinstance(value, str) else QColor()
    if not color.isValid():
        return default
    # Same format as TSHColorButton
    if color.alpha() < 255:
        return color.name(QColor.NameFormat.HexArgb)
    return color.name()


def NormalizeValue(field, value):
    """value checked against the field, or the field's default."""
    if field.type == FIELD_CHECKBOX:
        return value if isinstance(value, bool) else field.default
    if field.type == FIELD_COLOR:
        return _Color(value, field.default)
    if field.type == FIELD_FILL:
        default = field.default
        if isinstance(value, str):
            # A plain color
            color = _Color(value, default["color"])
            return Fill(color, color)
        if not isinstance(value, dict):
            return _Copy(default)
        direction = value.get("direction")
        return {
            "color": _Color(value.get("color"), default["color"]),
            "color2": _Color(value.get("color2"), default["color2"]),
            "gradient": value.get("gradient")
            if isinstance(value.get("gradient"), bool)
            else default["gradient"],
            "direction": direction if direction in GRADIENT_DIRECTIONS else default["direction"],
        }
    if field.type == FIELD_DROPDOWN:
        values = [option[0] for option in field.options]
        return value if value in values else field.default
    if field.type == FIELD_NUMBER:
        if isinstance(value, bool):
            return field.default
        try:
            number = int(value)
        except TypeError, ValueError:
            return field.default
        return max(field.minimum, min(field.maximum, number))
    if field.type in (FIELD_FONT, FIELD_TEXT):
        return value.strip() if isinstance(value, str) else field.default
    return field.default


def NormalizeLayoutTheme(data, name=None, schema=None):
    """Checks a layout theme (from the themes file or a shared file) and
    fills in what's missing with the defaults. Raises ValueError if it isn't
    a layout theme."""
    if not isinstance(data, dict) or not isinstance(data.get("values", {}), dict):
        raise ValueError("Not a TSH layout theme")
    values = data.get("values", {})
    schema = schema or LayoutThemeSchema()

    theme = {"name": str(name or data.get("name") or "").strip(), "values": {}}
    for section in schema:
        stored = values.get(section.key)
        stored = stored if isinstance(stored, dict) else {}
        theme["values"][section.key] = {
            field.key: NormalizeValue(field, stored.get(field.key, field.default))
            for field in section.fields
        }
    return theme


def CssColor(color):
    # Qt writes alpha first (#AARRGGBB), CSS last; rgba() reads the same in both
    qcolor = QColor(color)
    if not qcolor.isValid():
        return "transparent"
    if qcolor.alpha() < 255:
        return (
            f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {round(qcolor.alphaF(), 3)})"
        )
    return qcolor.name()


def CssValue(field, value):
    """The value as a CSS property value, or None if it isn't one."""
    if field.type == FIELD_COLOR:
        return CssColor(value)
    if field.type == FIELD_FILL:
        if value.get("gradient"):
            return f"linear-gradient({value['direction']}, {CssColor(value['color'])}, {CssColor(value['color2'])})"
        return CssColor(value["color"])
    if field.type == FIELD_NUMBER:
        return f"{value}{field.suffix}"
    if field.type == FIELD_FONT:
        if not value:
            return "inherit"
        return '"' + value.replace('"', "").replace("\\", "") + '"'
    return None


def CssVariables(theme, schema=None):
    """--<section>-<field> custom properties, with underscores as dashes."""
    css = {}
    for section in schema or LayoutThemeSchema():
        for field in section.fields:
            value = CssValue(field, theme["values"][section.key][field.key])
            if value is not None:
                css[f"--{section.key}-{field.key}".replace("_", "-")] = value
    return css


def StateExport(theme, schema=None):
    css = CssVariables(theme, schema)
    return {
        "name": theme["name"],
        "values": theme["values"],
        "css": css,
        "stylesheet": ":root {\n" + "".join(f"  {k}: {v};\n" for k, v in css.items()) + "}\n",
    }


def ExportLayoutTheme(theme, path):
    data = {"tsh_layout_theme": THEME_FILE_VERSION, **NormalizeLayoutTheme(theme)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ImportLayoutTheme(path):
    """Reads a layout theme file. Raises ValueError if it isn't one."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(str(e))
    if not isinstance(data, dict) or "tsh_layout_theme" not in data:
        raise ValueError("Not a TSH layout theme")
    name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
    return NormalizeLayoutTheme(data, name)


class TSHLayoutThemes:
    """The user's layout themes and which one is in use, kept in
    user_data/layout_themes.json:
    {"active": name, "themes": {name: {"values": {...}}}}"""

    data = {"active": DEFAULT_THEME, "themes": {}}
    path = THEMES_FILE

    @staticmethod
    def Load(path=None):
        TSHLayoutThemes.path = path or THEMES_FILE
        try:
            with open(TSHLayoutThemes.path, "rb") as f:
                data = orjson.loads(f.read())
            if not isinstance(data, dict):
                raise ValueError("Not a layout themes file")
        except FileNotFoundError:
            data = {}
        except Exception as e:
            logger.error(f"Could not read {TSHLayoutThemes.path}: {e}")
            data = {}
        themes = data.get("themes") if isinstance(data.get("themes"), dict) else {}
        TSHLayoutThemes.data = {
            "active": data.get("active") if isinstance(data.get("active"), str) else DEFAULT_THEME,
            "themes": themes,
        }

    @staticmethod
    def Save():
        try:
            os.makedirs(os.path.dirname(TSHLayoutThemes.path) or ".", exist_ok=True)
            with open(TSHLayoutThemes.path, "wb") as f:
                f.write(orjson.dumps(TSHLayoutThemes.data, option=orjson.OPT_INDENT_2))
        except OSError as e:
            logger.error(f"Could not save {TSHLayoutThemes.path}: {e}")

    @staticmethod
    def DefaultTheme():
        return {"name": DEFAULT_THEME, "values": DefaultValues()}

    @staticmethod
    def DisplayName(name):
        return _tr("Default") if name == DEFAULT_THEME else name

    @staticmethod
    def UserThemes():
        themes = {}
        for name, data in TSHLayoutThemes.data["themes"].items():
            if name == DEFAULT_THEME:
                continue
            try:
                themes[name] = NormalizeLayoutTheme(data, name)
            except ValueError:
                pass
        return themes

    @staticmethod
    def IsBuiltin(name):
        return name == DEFAULT_THEME

    @staticmethod
    def ActiveName():
        active = TSHLayoutThemes.data.get("active")
        if active in TSHLayoutThemes.UserThemes():
            return active
        return DEFAULT_THEME

    @staticmethod
    def Active():
        """The theme in use, as a theme dict."""
        name = TSHLayoutThemes.ActiveName()
        if name == DEFAULT_THEME:
            return TSHLayoutThemes.DefaultTheme()
        return TSHLayoutThemes.UserThemes()[name]

    @staticmethod
    def SetActive(name):
        TSHLayoutThemes.data["active"] = (
            name if name in TSHLayoutThemes.UserThemes() else DEFAULT_THEME
        )
        TSHLayoutThemes.Save()
        TSHLayoutThemes.ExportToState()

    @staticmethod
    def SaveTheme(theme, oldName=None):
        theme = NormalizeLayoutTheme(theme)
        if not theme["name"] or theme["name"] == DEFAULT_THEME:
            raise ValueError("A layout theme needs a name")
        themes = TSHLayoutThemes.data["themes"]
        if oldName and oldName != theme["name"]:
            themes.pop(oldName, None)
            if TSHLayoutThemes.data.get("active") == oldName:
                TSHLayoutThemes.data["active"] = theme["name"]
        themes[theme["name"]] = {"values": theme["values"]}
        TSHLayoutThemes.Save()
        if TSHLayoutThemes.ActiveName() == theme["name"]:
            TSHLayoutThemes.ExportToState()
        return theme

    @staticmethod
    def DeleteTheme(name):
        TSHLayoutThemes.data["themes"].pop(name, None)
        if TSHLayoutThemes.data.get("active") == name:
            TSHLayoutThemes.data["active"] = DEFAULT_THEME
        TSHLayoutThemes.Save()
        TSHLayoutThemes.ExportToState()

    @staticmethod
    def UniqueName(name):
        name = (name or "").strip() or _tr("Custom theme")
        taken = set(TSHLayoutThemes.UserThemes()) | {
            DEFAULT_THEME,
            TSHLayoutThemes.DisplayName(DEFAULT_THEME),
        }
        if name not in taken:
            return name
        i = 2
        while f"{name} ({i})" in taken:
            i += 1
        return f"{name} ({i})"

    @staticmethod
    def ExportToState():
        theme = dict(TSHLayoutThemes.Active())
        theme["name"] = TSHLayoutThemes.DisplayName(theme["name"])
        StateManager.Set("layout_theme", StateExport(theme))
