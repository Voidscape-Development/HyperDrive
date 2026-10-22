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


# =====================================================
# SCHEMA
# =====================================================
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
                    "#ffb800",
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
                Field("winner_color", _tr("Winner highlight"), FIELD_COLOR, "#ffb800"),
                Field("lines_color", _tr("Bracket lines color"), FIELD_COLOR, "#000000"),
                Field(
                    "focus_color",
                    _tr("Focus highlight"),
                    FIELD_COLOR,
                    "#ffb800",
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
                Field("selected_color", _tr("Selected stage outline"), FIELD_COLOR, "#ffb800"),
            ],
        ),
        Section(
            "stream_queue",
            _tr("Stream queue"),
            [
                Field(
                    "sets_count",
                    _tr("Sets displayed"),
                    FIELD_NUMBER,
                    0,
                    minimum=0,
                    maximum=20,
                    tooltip=_tr("0: as many as the layout's own settings say (all by default)"),
                ),
                Field(
                    "first_set_display",
                    _tr("Display the first set of the queue"),
                    FIELD_CHECKBOX,
                    True,
                    tooltip=_tr("Off: skips the set being played, which stays first in the queue"),
                ),
                Field("eta_display", _tr("Display when sets should start"), FIELD_CHECKBOX, True),
                Field("station_display", _tr("Display stations"), FIELD_CHECKBOX, False),
                Field("avatar_display", _tr("Display player avatars"), FIELD_CHECKBOX, True),
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


# The fields that only reach the layouts with "apply_colors" on (globals.js's
# THEME_COLORS), as (section, field)
APPLY_COLORS_FIELDS = {
    ("general", "primary_color"),
    ("general", "secondary_color"),
    ("general", "text_color"),
    ("general", "background"),
    ("general", "border_radius"),
    ("general", "chip_radius"),
    ("teams", "team1_color"),
    ("teams", "team2_color"),
    ("teams", "team1_score_color"),
    ("teams", "team2_score_color"),
    ("chip", "text_color"),
    ("chip", "background"),
    ("bracket", "score_background"),
    ("bracket", "sponsor_background"),
    ("bracket", "winner_color"),
    ("bracket", "lines_color"),
    ("stage_strike", "striked_color"),
    ("stage_strike", "selected_color"),
    ("versus", "custom_sponsor_colors"),
    ("versus", "team1_sponsor_color"),
    ("versus", "team2_sponsor_color"),
}


# The other built-in themes' names in the file start with this, so they can't
# clash with a user theme's
BUILTIN_PREFIX = "builtin:"


def BuiltinThemeNames():
    """The ready-made themes after the default one, as {name: label}, in the
    order they're listed."""
    return {
        BUILTIN_PREFIX + "esports_neon": _tr("Esports Neon"),
        BUILTIN_PREFIX + "clean_minimal": _tr("Clean Minimal"),
        BUILTIN_PREFIX + "classic_broadcast": _tr("Classic Broadcast"),
        BUILTIN_PREFIX + "daytime": _tr("Daytime"),
    }


# Their values, over the defaults. They only change how the layouts look
# (colors, fonts, corners, animations), never what they show. Their fonts
# are ones layout/main.css loads, so they work without being installed.
_BUILTIN_VALUES = {
    BUILTIN_PREFIX + "esports_neon": {
        "general": {
            "apply_colors": True,
            "primary_color": "#00e5ff",
            "secondary_color": "#0a0618",
            "text_color": "#ffffff",
            "background": Fill("#0a0618", "#1a0b3a", True, "to bottom right"),
            "text_case": "uppercase",
            "border_radius": 0,
            "chip_radius": 2,
        },
        "animation": {"speed": 150},
        "teams": {
            "team1_color": "#ff2bd6",
            "team2_color": "#00e5ff",
            "team1_score_color": "#ffffff",
            "team2_score_color": "#0a0618",
        },
        "chip": {
            "text_color": "#ffffff",
            "background": Fill("#1a0b3a", "#0a0618", True, "to right"),
        },
        "bracket": {
            "score_background": Fill("#ff2bd6", "#7a00ff", True, "to right"),
            "sponsor_background": Fill("#7a00ff", "#0a0618", True, "to right"),
            "winner_color": "#00e5ff",
            "lines_color": "#ff2bd6",
            "focus_color": "#00e5ff",
        },
        "stage_strike": {"striked_color": "#c00a0618", "selected_color": "#00e5ff"},
    },
    BUILTIN_PREFIX + "clean_minimal": {
        "general": {
            "apply_colors": True,
            "primary_color": "#a5b4fc",
            "secondary_color": "#1e293b",
            "text_color": "#f1f5f9",
            "background": Fill("#0f172a"),
            "font_family": "NotoSans",
            "text_case": "none",
            "text_outline": False,
            "border_radius": 12,
            "chip_radius": 8,
        },
        "animation": {"speed": 85},
        "teams": {
            "team1_color": "#f87171",
            "team2_color": "#60a5fa",
            "team1_score_color": "#0f172a",
            "team2_score_color": "#0f172a",
        },
        "chip": {"text_color": "#f1f5f9", "background": Fill("#1e293b")},
        "bracket": {
            "score_background": Fill("#334155"),
            "sponsor_background": Fill("#475569"),
            "winner_color": "#a5b4fc",
            "lines_color": "#475569",
            "focus_color": "#a5b4fc",
        },
        "stage_strike": {"striked_color": "#b30f172a", "selected_color": "#a5b4fc"},
    },
    BUILTIN_PREFIX + "classic_broadcast": {
        "general": {
            "apply_colors": True,
            "primary_color": "#d4a017",
            "secondary_color": "#0b1f3a",
            "text_color": "#ffffff",
            "background": Fill("#132f57", "#0b1f3a", True, "to bottom"),
            "font_family": "RobotoCondensed",
            "text_case": "uppercase",
            "border_radius": 2,
            "chip_radius": 2,
        },
        "teams": {
            "team1_color": "#c8102e",
            "team2_color": "#1d4ed8",
            "team1_score_color": "#ffffff",
            "team2_score_color": "#ffffff",
        },
        "chip": {
            "text_color": "#ffffff",
            "background": Fill("#132f57", "#0b1f3a", True, "to bottom"),
        },
        "bracket": {
            "score_background": Fill("#d4a017", "#a87c0c", True, "to bottom"),
            "sponsor_background": Fill("#132f57"),
            "winner_color": "#d4a017",
            "lines_color": "#3a5a85",
            "focus_color": "#d4a017",
        },
        "stage_strike": {"striked_color": "#c00b1f3a", "selected_color": "#d4a017"},
    },
    BUILTIN_PREFIX + "daytime": {
        "general": {
            "apply_colors": True,
            "primary_color": "#2563eb",
            "secondary_color": "#e2e8f0",
            "text_color": "#0f172a",
            "background": Fill("#ffffff", "#f1f5f9", True, "to bottom"),
            "font_family": "NotoSans",
            "text_outline": False,
            "border_radius": 8,
            "chip_radius": 6,
        },
        "teams": {
            "team1_color": "#dc2626",
            "team2_color": "#2563eb",
            "team1_score_color": "#ffffff",
            "team2_score_color": "#ffffff",
        },
        "chip": {"text_color": "#0f172a", "background": Fill("#ffffff")},
        "bracket": {
            "score_background": Fill("#2563eb"),
            "sponsor_background": Fill("#e2e8f0"),
            "winner_color": "#f59e0b",
            "lines_color": "#94a3b8",
            "focus_color": "#2563eb",
        },
        "stage_strike": {"striked_color": "#b3ffffff", "selected_color": "#2563eb"},
    },
}


def DefaultValues(schema=None):
    return {
        section.key: {field.key: _Copy(field.default) for field in section.fields}
        for section in (schema or LayoutThemeSchema())
    }


# =====================================================
# NORMALIZING VALUES
# =====================================================
def _Copy(value):
    return dict(value) if isinstance(value, dict) else value


def _Color(value, default):
    color = QColor(value.strip()) if isinstance(value, str) else QColor()
    if not color.isValid():
        return default
    # Same format as ColorButton
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
        except (TypeError, ValueError):
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
        raise ValueError("Not a HyperDrive layout theme")
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


# =====================================================
# CSS
# =====================================================
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


# =====================================================
# THEME FILES
# =====================================================
def ExportLayoutTheme(theme, path):
    data = {"hyperdrive_layout_theme": THEME_FILE_VERSION, **NormalizeLayoutTheme(theme)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ImportLayoutTheme(path):
    """Reads a layout theme file. Raises ValueError if it isn't one."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(str(e))
    # Files exported before the rename to HyperDrive have the old key
    if not isinstance(data, dict) or not (
        "hyperdrive_layout_theme" in data or "tsh_layout_theme" in data
    ):
        raise ValueError("Not a HyperDrive layout theme")
    name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
    return NormalizeLayoutTheme(data, name)


# =====================================================
# SAVED THEMES
# =====================================================
class LayoutThemes:
    """The user's layout themes and which one is in use, kept in
    user_data/layout_themes.json:
    {"active": name, "themes": {name: {"values": {...}}}}"""

    data = {"active": DEFAULT_THEME, "themes": {}}
    path = THEMES_FILE

    # =====================================================
    # SAVED THEMES
    # =====================================================
    @staticmethod
    def Load(path=None):
        LayoutThemes.path = path or THEMES_FILE
        try:
            with open(LayoutThemes.path, "rb") as f:
                data = orjson.loads(f.read())
            if not isinstance(data, dict):
                raise ValueError("Not a layout themes file")
        except FileNotFoundError:
            data = {}
        except Exception as e:
            logger.error(f"Could not read {LayoutThemes.path}: {e}")
            data = {}
        themes = data.get("themes") if isinstance(data.get("themes"), dict) else {}
        LayoutThemes.data = {
            "active": data.get("active") if isinstance(data.get("active"), str) else DEFAULT_THEME,
            "themes": themes,
        }

    @staticmethod
    def Save():
        try:
            os.makedirs(os.path.dirname(LayoutThemes.path) or ".", exist_ok=True)
            with open(LayoutThemes.path, "wb") as f:
                f.write(orjson.dumps(LayoutThemes.data, option=orjson.OPT_INDENT_2))
        except OSError as e:
            logger.error(f"Could not save {LayoutThemes.path}: {e}")

    @staticmethod
    def UserThemes():
        themes = {}
        for name, data in LayoutThemes.data["themes"].items():
            if LayoutThemes.IsBuiltin(name) or name.startswith(BUILTIN_PREFIX):
                continue
            try:
                themes[name] = NormalizeLayoutTheme(data, name)
            except ValueError:
                pass
        return themes

    @staticmethod
    def SaveTheme(theme, oldName=None):
        theme = NormalizeLayoutTheme(theme)
        if not theme["name"] or theme["name"] == DEFAULT_THEME:
            raise ValueError("A layout theme needs a name")
        if theme["name"].startswith(BUILTIN_PREFIX):
            raise ValueError("Built-in layout themes can't be changed")
        themes = LayoutThemes.data["themes"]
        if oldName and oldName != theme["name"]:
            themes.pop(oldName, None)
            if LayoutThemes.data.get("active") == oldName:
                LayoutThemes.data["active"] = theme["name"]
        themes[theme["name"]] = {"values": theme["values"]}
        LayoutThemes.Save()
        if LayoutThemes.ActiveName() == theme["name"]:
            LayoutThemes.ExportToState()
        return theme

    @staticmethod
    def DeleteTheme(name):
        LayoutThemes.data["themes"].pop(name, None)
        if LayoutThemes.data.get("active") == name:
            LayoutThemes.data["active"] = DEFAULT_THEME
        LayoutThemes.Save()
        LayoutThemes.ExportToState()

    @staticmethod
    def UniqueName(name):
        name = (name or "").strip() or _tr("Custom theme")
        taken = set(LayoutThemes.UserThemes())
        for builtin in LayoutThemes.BuiltinNames():
            taken |= {builtin, LayoutThemes.DisplayName(builtin)}
        if name not in taken:
            return name
        i = 2
        while f"{name} ({i})" in taken:
            i += 1
        return f"{name} ({i})"

    # =====================================================
    # BUILT-IN THEMES
    # =====================================================
    @staticmethod
    def DefaultTheme():
        return {"name": DEFAULT_THEME, "values": DefaultValues()}

    @staticmethod
    def BuiltinNames():
        """The default theme and the ready-made ones, in the order they're listed."""
        return [DEFAULT_THEME, *BuiltinThemeNames()]

    @staticmethod
    def BuiltinTheme(name):
        if name == DEFAULT_THEME:
            return LayoutThemes.DefaultTheme()
        return NormalizeLayoutTheme({"values": _BUILTIN_VALUES[name]}, name)

    @staticmethod
    def DisplayName(name):
        if name == DEFAULT_THEME:
            return _tr("Default")
        return BuiltinThemeNames().get(name, name)

    @staticmethod
    def IsBuiltin(name):
        return name == DEFAULT_THEME or name in _BUILTIN_VALUES

    # =====================================================
    # ACTIVE THEME
    # =====================================================
    @staticmethod
    def ActiveName():
        active = LayoutThemes.data.get("active")
        if LayoutThemes.IsBuiltin(active) or active in LayoutThemes.UserThemes():
            return active
        return DEFAULT_THEME

    @staticmethod
    def Active():
        """The theme in use, as a theme dict."""
        name = LayoutThemes.ActiveName()
        if LayoutThemes.IsBuiltin(name):
            return LayoutThemes.BuiltinTheme(name)
        return LayoutThemes.UserThemes()[name]

    @staticmethod
    def SetActive(name):
        known = LayoutThemes.IsBuiltin(name) or name in LayoutThemes.UserThemes()
        LayoutThemes.data["active"] = name if known else DEFAULT_THEME
        LayoutThemes.Save()
        LayoutThemes.ExportToState()

    @staticmethod
    def ExportToState():
        theme = dict(LayoutThemes.Active())
        theme["name"] = LayoutThemes.DisplayName(theme["name"])
        StateManager.Set("layout_theme", StateExport(theme))
