import json
import math
import textwrap

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..StateManager import StateManager


def add_alt_text_tooltip_to_button(push_button: QPushButton):
    altTextTooltip = QApplication.translate(
        "tips",
        "Descriptive text (also known as Alt text) describes images for blind and low-vision users, and helps give context around images to everyone. As such, we highly recommend adding it to your image uploads on your websites and social media posts.",
    )
    push_button.setToolTip("\n".join(textwrap.wrap(altTextTooltip, 40)))
    return push_button


def load_program_state():
    # Make sure program_state.json has the latest changes
    StateManager.FlushPendingSave()
    data_path = "./out/program_state.json"
    with open(data_path, encoding="utf-8") as data_file:
        data_json = json.loads(data_file.read())
    return data_json


def generate_top_n_alt_text(bracket_type="DOUBLE_ELIMINATION"):
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

    data = load_program_state()
    tournament_name = data.get("tournamentInfo").get("tournamentName")
    event_name = data.get("tournamentInfo").get("eventName")
    event_date = data.get("tournamentInfo").get("startAt")
    game_name = data.get("game").get("name")
    game_localisation = QApplication.translate("altText", "Game:")
    standings_localisation = QApplication.translate("altText", "Standings:")
    alt_text = (
        f"""
{tournament_name.upper()}
{event_name} - {event_date}
{game_localisation} {game_name}

"""
        + standings_localisation.upper()
        + "\n"
    )

    team_list = data.get("player_list").get("slot")
    for team_id in team_list.keys():
        current_team_data = team_list.get(team_id)
        team_name = current_team_data.get("name")
        players_text = []
        players_text_with_variants = []
        player_data = current_team_data.get("player")
        for player_id in player_data.keys():
            character_names = []
            character_names_with_variants = []
            current_player_data = player_data.get(player_id)
            player_name = current_player_data.get("mergedName")
            character_data = current_player_data.get("character")
            if current_player_data.get("country"):
                country_code = current_player_data.get("country").get("code")
            else:
                country_code = ""
            for character_id in character_data.keys():
                current_character_data = character_data.get(character_id)
                if current_character_data.get("name"):
                    current_character_name = current_character_data.get("name")
                    current_character_name_with_variants = current_character_data.get("name")
                    if current_character_data.get("variant", {}).get("name"):
                        current_character_name_with_variants = f"{current_character_name} - {current_character_data.get('variant', {}).get('name')}"
                    character_names.append(current_character_name)
                    character_names_with_variants.append(current_character_name_with_variants)
            player_text = f"{player_name}"
            characters_text = " / ".join(character_names)
            characters_text_with_variants = " / ".join(character_names_with_variants)
            if country_code:
                if characters_text:
                    characters_text = country_code + ", " + characters_text
                    characters_text_with_variants = (
                        country_code + ", " + characters_text_with_variants
                    )
                else:
                    characters_text = country_code
                    characters_text_with_variants = country_code
            if characters_text:
                player_text, player_text_with_variants = (
                    player_text + f" ({characters_text})",
                    player_text + f" ({characters_text_with_variants})",
                )
            if player_name:
                players_text.append(player_text)
                players_text_with_variants.append(player_text_with_variants)
        placement = CalculatePlacement(int(team_id), bracket_type)
        players_text = " / ".join(players_text)
        players_text_with_variants = " / ".join(players_text_with_variants)
        if team_name:
            alt_text = alt_text + f"{placement}/ {team_name} [{players_text_with_variants}]\n"
        else:
            alt_text = alt_text + f"{placement}/ {players_text_with_variants}\n"

    alt_text = f"{alt_text}\n\n"
    commentator_data = data.get("commentary")
    commentator_names = []
    for commentator_id in commentator_data.keys():
        current_commentator_data = commentator_data.get(commentator_id)
        if current_commentator_data.get("mergedName"):
            commentator_names.append(current_commentator_data.get("mergedName"))
    if commentator_names:
        alt_text = (
            alt_text
            + QApplication.translate("altText", "Commentators:")
            + " "
            + " / ".join(commentator_names)
            + "\n"
        )

    alt_text = alt_text + QApplication.translate("altText", "Stream powered by HyperDrive")

    alt_text.strip()
    return alt_text


if __name__ == "__main__":
    from termcolor import colored

    print(colored("TEST MODE - TSHAltTextHelper.py", "red"))
    print("====")
    print(colored("\nTop 8 alt text: \n", "yellow") + f"{generate_top_n_alt_text()}")
