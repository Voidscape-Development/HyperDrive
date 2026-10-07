import json
import math
import re
import textwrap

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..SettingsManager import SettingsManager
from ..StateManager import StateManager

# Where the descriptive text options are kept in the settings
OPTIONS_KEY = "alt_text"

# Options of the simple mode, and which mode is used. The header and footer
# text and the templates aren't here: their defaults are translated, so they
# come from the functions below.
DEFAULT_OPTIONS = {
    "mode": "simple",
    "show_date": True,
    "show_game": True,
    "show_country": True,
    "show_characters": True,
    "show_variants": True,
    "show_seed": False,
    "show_twitter": False,
    "show_pronoun": False,
    "show_bracket_link": False,
    "show_commentators": True,
}

# What each template can use: {name} is replaced by the value, and a part in
# [[ ]] is left out when any of the values in it is empty
TEMPLATE_PLACEHOLDERS = {
    "header": [
        "tournament",
        "TOURNAMENT",
        "event",
        "date",
        "game",
        "entrants",
        "bracket_link",
        "commentators",
    ],
    "entry": ["placement", "team", "players", "seed"],
    "player": [
        "name",
        "gamertag",
        "prefix",
        "real_name",
        "twitter",
        "pronoun",
        "country",
        "state",
        "characters",
        "characters_variants",
        "seed",
    ],
}
TEMPLATE_PLACEHOLDERS["footer"] = TEMPLATE_PLACEHOLDERS["header"]

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_OPTIONAL = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


def add_alt_text_tooltip_to_button(push_button: QPushButton):
    altTextTooltip = QApplication.translate(
        "tips",
        "Descriptive text (also known as Alt text) describes images for blind and low-vision users, and helps give context around images to everyone. As such, we highly recommend adding it to your image uploads on your websites and social media posts.",
    )
    push_button.setToolTip("\n".join(textwrap.wrap(altTextTooltip, 40)))
    return push_button


def default_footer_text():
    return QApplication.translate("altText", "Stream powered by HyperDrive")


def default_templates():
    # Close to the simple mode's defaults, as a starting point
    return {
        "header": "{TOURNAMENT}\n{event}[[ - {date}]]\n[["
        + QApplication.translate("altText", "Game:")
        + " {game}]]\n\n"
        + QApplication.translate("altText", "Standings:").upper(),
        "entry": "{placement}/ [[{team}: ]]{players}",
        "player": "{name}[[ ({country})]][[ ({characters_variants})]]",
        "footer": "[["
        + QApplication.translate("altText", "Commentators:")
        + " {commentators}]]\n"
        + default_footer_text(),
    }


def load_options():
    options = dict(DEFAULT_OPTIONS)
    options["header_text"] = ""
    options["footer_text"] = default_footer_text()
    options.update({f"template_{part}": template for part, template in default_templates().items()})
    saved = SettingsManager.Get(OPTIONS_KEY, {})
    if isinstance(saved, dict):
        options.update({k: v for k, v in saved.items() if k in options})
    return options


def save_options(options):
    SettingsManager.Set(OPTIONS_KEY, dict(options))


def fill_template(template, values):
    """Replaces {name} with values[name]. A part in [[ ]] is left out when any
    value in it is empty. Unknown names are left as they are, so a typo shows."""

    def value(match):
        key = match.group(1)
        if key not in values:
            return match.group(0)
        return str(values[key] or "")

    def optional(match):
        section = match.group(1)
        keys = [k for k in _PLACEHOLDER.findall(section) if k in values]
        if any(not str(values[k] or "") for k in keys):
            return ""
        return _PLACEHOLDER.sub(value, section)

    return _PLACEHOLDER.sub(value, _OPTIONAL.sub(optional, template))


def load_program_state():
    # Make sure program_state.json has the latest changes
    StateManager.FlushPendingSave()
    data_path = "./out/program_state.json"
    with open(data_path, encoding="utf-8") as data_file:
        data_json = json.loads(data_file.read())
    return data_json


def CalculatePlacementMath(x, bracket_type="DOUBLE_ELIMINATION"):
    # Due to how the logs works, if the player is first seed,
    # the value will always be 0 and no math needs to be done.
    if x <= 1:
        return 0

    single_elim_calc = math.floor(math.log2(x - 1))
    double_elim_calc = math.ceil(math.log2((2 * x) / 3))

    # Double Elimination Sum of Values
    if bracket_type == "DOUBLE_ELIMINATION":
        return single_elim_calc + double_elim_calc
    # Single Elimination Sum of Values
    elif bracket_type == "SINGLE_ELIMINATION":
        return single_elim_calc
    else:
        return 0


def CalculatePlacement(x, bracket_type="DOUBLE_ELIMINATION"):
    if x in [1, 2, 3, 4]:
        return x
    placement_math = CalculatePlacementMath(x, bracket_type)
    change = x
    while CalculatePlacementMath(change, bracket_type) == placement_math:
        change = change - 1
    return change + 1


def format_twitter(handle):
    handle = str(handle or "").strip().lstrip("@")
    return f"@{handle}" if handle else ""


def format_seed(seed):
    try:
        seed = int(seed or 0)
    except TypeError, ValueError:
        return ""
    return str(seed) if seed > 0 else ""


def collect_data(data, bracket_link="", bracket_type="DOUBLE_ELIMINATION"):
    """The values the text is made of, from program_state.json's data"""
    info = data.get("tournamentInfo") or {}
    commentators = [
        c.get("mergedName")
        for c in (data.get("commentary") or {}).values()
        if (c or {}).get("mergedName")
    ]
    tournament = info.get("tournamentName") or ""
    if not bracket_link and info.get("shortLink"):
        bracket_link = f"https://start.gg/{info.get('shortLink')}"

    general = {
        "tournament": tournament,
        "TOURNAMENT": tournament.upper(),
        "event": info.get("eventName") or "",
        "date": info.get("startAt") or "",
        "game": (data.get("game") or {}).get("name") or "",
        "entrants": info.get("numEntrants") or "",
        "bracket_link": bracket_link or "",
        "commentators": " / ".join(commentators),
    }

    entries = []
    slots = (data.get("player_list") or {}).get("slot") or {}
    for slot_id, slot in slots.items():
        slot = slot or {}
        players = []
        for player in (slot.get("player") or {}).values():
            player = player or {}
            if not player.get("mergedName"):
                continue
            characters = []
            characters_variants = []
            for character in (player.get("character") or {}).values():
                name = (character or {}).get("name")
                if not name:
                    continue
                characters.append(name)
                variant = ((character or {}).get("variant") or {}).get("name")
                characters_variants.append(f"{name} - {variant}" if variant else name)
            players.append(
                {
                    "name": player.get("mergedName") or "",
                    "gamertag": player.get("name") or "",
                    "prefix": player.get("team") or "",
                    "real_name": player.get("real_name") or "",
                    "twitter": format_twitter(player.get("twitter")),
                    "pronoun": player.get("pronoun") or "",
                    "country": (player.get("country") or {}).get("code") or "",
                    "state": (player.get("state") or {}).get("code") or "",
                    "characters": " / ".join(characters),
                    "characters_variants": " / ".join(characters_variants),
                    "seed": format_seed(player.get("seed")),
                }
            )
        if not players and not slot.get("name"):
            # An empty slot
            continue
        try:
            placement = CalculatePlacement(int(slot_id), bracket_type)
        except ValueError:
            placement = slot_id
        entries.append(
            {
                "placement": placement,
                "team": slot.get("name") or "",
                "players": players,
                # The entrant's seed, from its first player that has one
                "seed": next((p["seed"] for p in players if p["seed"]), ""),
            }
        )
    return general, entries


def _join_lines(lines):
    return "\n".join(lines)


def render_simple(general, entries, options):
    lines = []
    if options.get("header_text"):
        lines.append(options["header_text"])
    if general["TOURNAMENT"]:
        lines.append(general["TOURNAMENT"])
    event_line = general["event"]
    if options.get("show_date") and general["date"]:
        event_line = f"{event_line} - {general['date']}" if event_line else general["date"]
    if event_line:
        lines.append(event_line)
    if options.get("show_game") and general["game"]:
        lines.append(QApplication.translate("altText", "Game:") + " " + general["game"])
    if options.get("show_bracket_link") and general["bracket_link"]:
        lines.append(QApplication.translate("altText", "Bracket:") + " " + general["bracket_link"])
    lines.append("")
    lines.append(QApplication.translate("altText", "Standings:").upper())

    for entry in entries:
        players_text = []
        for player in entry["players"]:
            text = player["name"]
            if options.get("show_twitter") and player["twitter"]:
                text += f" {player['twitter']}"
            if options.get("show_pronoun") and player["pronoun"]:
                text += f" ({player['pronoun']})"
            details = []
            if options.get("show_country") and player["country"]:
                details.append(player["country"])
            if options.get("show_characters"):
                characters = player[
                    "characters_variants" if options.get("show_variants") else "characters"
                ]
                if characters:
                    details.append(characters)
            if details:
                text += f" ({', '.join(details)})"
            players_text.append(text)
        players_text = " / ".join(players_text)
        if entry["team"]:
            line = f"{entry['placement']}/ {entry['team']} [{players_text}]"
        else:
            line = f"{entry['placement']}/ {players_text}"
        if options.get("show_seed") and entry["seed"]:
            line += " - " + QApplication.translate("altText", "Seed {0}").format(entry["seed"])
        lines.append(line)

    footer = []
    if options.get("show_commentators") and general["commentators"]:
        footer.append(
            QApplication.translate("altText", "Commentators:") + " " + general["commentators"]
        )
    if options.get("footer_text"):
        footer.append(options["footer_text"])
    if footer:
        lines.append("")
        lines.append("")
        lines.extend(footer)

    return _join_lines(lines)


def render_template(general, entries, options):
    templates = default_templates()
    templates.update(
        {
            part: options[f"template_{part}"]
            for part in templates
            if isinstance(options.get(f"template_{part}"), str)
        }
    )

    entry_lines = []
    for entry in entries:
        players = [fill_template(templates["player"], player) for player in entry["players"]]
        values = dict(entry, players=" / ".join(players))
        entry_lines.append(fill_template(templates["entry"], values))

    parts = [
        fill_template(templates["header"], general),
        _join_lines(entry_lines),
        fill_template(templates["footer"], general),
    ]
    return "\n\n".join(part.strip("\n") for part in parts if part.strip())


def generate_alt_text(data, options=None, bracket_link="", bracket_type="DOUBLE_ELIMINATION"):
    options = options if options is not None else load_options()
    general, entries = collect_data(data, bracket_link, bracket_type)
    if options.get("mode") == "template":
        text = render_template(general, entries, options)
    else:
        text = render_simple(general, entries, options)
    return text.strip("\n")


def generate_top_n_alt_text(bracket_type="DOUBLE_ELIMINATION", options=None):
    return generate_alt_text(
        load_program_state(),
        options,
        bracket_link=SettingsManager.Get("TOURNAMENT_URL", "") or "",
        bracket_type=bracket_type,
    )


if __name__ == "__main__":
    from termcolor import colored

    print(colored("TEST MODE - AltTextHelper.py", "red"))
    print("====")
    print(colored("\nTop 8 alt text: \n", "yellow") + f"{generate_top_n_alt_text()}")
