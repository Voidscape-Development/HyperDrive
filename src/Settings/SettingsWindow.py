from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..Helpers.DynamicExport import DynamicExport
from ..Scheduler import (
    BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
    BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS,
    COMPLETED_SETS_DEFAULT_INTERVAL_SECS,
    COMPLETED_SETS_MIN_INTERVAL_SECS,
    SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
    SCOREBOARD_AUTO_UPDATE_GROUP,
    SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS,
    Scheduler,
)
from ..SettingsManager import SettingsManager
from .AppearanceSettings import AppearanceSettings
from .PronounSettings import PronounSettings
from .SettingsWidget import SettingsWidget
from .TournamentTermsSettings import TournamentTermsSettings


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # key -> the page's item in the list, see Open()
        self.pageKeys = {}

    def UiMounted(self):
        self.setWindowTitle(QApplication.translate("Settings", "Settings"))

        # Create a list widget for the selection
        self.selection_list = QListWidget()
        self.selection_list.currentRowChanged.connect(self.on_selection_changed)

        # Create a stacked widget for the settings widgets. Each page scrolls
        # on its own, so a short page isn't stretched to the tallest one's
        # height (which pushed the Pronouns page's buttons out of view)
        self.settings_stack = QStackedWidget()

        # Create a splitter for the selection and settings
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.selection_list)
        splitter.addWidget(self.settings_stack)

        # Set the layout for the dialog
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Add general settings
        generalSettings = []

        generalSettings.append(
            (
                QApplication.translate("settings.general", "Webserver Port"),
                "webserver_port",
                "spinbox",
                5500,
            )
        )

        generalSettings.append(
            (
                QApplication.translate("settings.general", "Enable profanity filter"),
                "profanity_filter",
                "checkbox",
                True,
            )
        )

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.completed_sets_pull_interval",
                    "Completed sets auto pull interval (seconds)",
                ),
                "completed_sets_pull_interval",
                "spinbox",
                COMPLETED_SETS_DEFAULT_INTERVAL_SECS,
                lambda: Scheduler.instance.SetInterval(
                    "completed_sets",
                    SettingsManager.Get(
                        "general.completed_sets_pull_interval", COMPLETED_SETS_DEFAULT_INTERVAL_SECS
                    )
                    * 1000,
                ),
                None,
                COMPLETED_SETS_MIN_INTERVAL_SECS,
            )
        )

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.bracket_auto_update_interval",
                    "Bracket auto update interval (seconds)",
                ),
                "bracket_auto_update_interval",
                "spinbox",
                BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                lambda: Scheduler.instance.SetInterval(
                    "bracket_sets",
                    SettingsManager.Get(
                        "general.bracket_auto_update_interval",
                        BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                    )
                    * 1000,
                ),
                None,
                BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS,
            )
        )

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.custom_player_export",
                    "Export custom player data from user_data/custom_player_export",
                ),
                "custom_player_export",
                "checkbox",
                True,
                DynamicExport.SettingChanged,
                QApplication.translate(
                    "settings.custom_player_export",
                    "Sends the files in a folder named after a player's tag (or sponsor and tag) "
                    "to the layouts, as the player's custom data. Changes to the files show up "
                    "on stream within a second.",
                ),
            )
        )

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.team_battle_default_stocks",
                    "Crew/Team Battle: starting stocks per player (Stock Pool)",
                ),
                "team_battle_default_stocks",
                "spinbox",
                3,
            )
        )

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.team_battle_default_first_to",
                    "Crew/Team Battle: games to win a matchup (First To)",
                ),
                "team_battle_default_first_to",
                "spinbox",
                2,
            )
        )

        self.add_setting_widget(
            QApplication.translate("settings", "General"),
            SettingsWidget("general", generalSettings),
            "general",
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Appearance"), AppearanceSettings(), "appearance"
        )

        # Scoreboard settings. Stored under general, where they were before
        # they got their own section
        scoreboardSettings = []

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.control_score_from_stage_strike",
                    "Enable score control from the stage striking app",
                ),
                "control_score_from_stage_strike",
                "checkbox",
                True,
            )
        )

        # Sent to the stage strike page with its data (WebServerActions.ruleset)
        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.stage_strike_ask_characters",
                    "Ask for the next game's characters on the stage striking app after each game",
                ),
                "stage_strike_ask_characters",
                "checkbox",
                True,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.disable_autoupdate",
                    "Disable automatic set updating for the scoreboard",
                ),
                "disable_autoupdate",
                "checkbox",
                False,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.scoreboard_auto_update_interval",
                    "Scoreboard automatic set updating interval (seconds)",
                ),
                "scoreboard_auto_update_interval",
                "spinbox",
                SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                lambda: Scheduler.instance.SetGroupInterval(
                    SCOREBOARD_AUTO_UPDATE_GROUP,
                    SettingsManager.Get(
                        "general.scoreboard_auto_update_interval",
                        SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                    )
                    * 1000,
                ),
                None,
                SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.force_no_mains_on_new_set_loads",
                    "Do not update character data when a set is loaded",
                ),
                "force_no_mains_on_new_set_loads",
                "checkbox",
                False,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.disable_scoreupdate",
                    "Disable automatic score updating for the scoreboard",
                ),
                "disable_scoreupdate",
                "checkbox",
                False,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.disable_overwrite",
                    "Do not override existing values in the local player database (takes effect on next restart)",
                ),
                "disable_overwrite",
                "checkbox",
                False,
            )
        )

        scoreboardSettings.append(
            (
                QApplication.translate(
                    "settings.local_player_data",
                    "Use the local player database for player info when loading sets",
                ),
                "local_player_data",
                "checkbox",
                False,
                None,
                QApplication.translate(
                    "settings.local_player_data",
                    "Sets, the stream queue and station sets are loaded without the players' "
                    "socials, pronouns and location, which come from the local player database "
                    "instead. Players not in it yet are looked up once and saved to it.",
                ),
            )
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Scoreboard"),
            SettingsWidget("general", scoreboardSettings),
            "scoreboard",
        )

        # State Manager settings, also stored under general
        stateManagerSettings = []

        stateManagerSettings.append(
            (
                QApplication.translate("settings.general", "Enable StateManager Logging"),
                "statemanager_logging",
                "checkbox",
                False,
            )
        )

        stateManagerSettings.append(
            (
                QApplication.translate(
                    "settings.disable_export", "Disable HyperDrive file exporting"
                ),
                "disable_export",
                "checkbox",
                False,
            )
        )

        self.add_setting_widget(
            QApplication.translate("settings", "State Manager"),
            SettingsWidget("general", stateManagerSettings),
            "state-manager",
        )

        # Add Display Options settings
        displaySettings = []

        displaySettings.append(
            (
                QApplication.translate("settings.show_name", "Show Real Name"),
                "show_name",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_social", "Show Social Media"),
                "show_social",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_seed", "Show Seed"),
                "show_seed",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_birthday", "Show Birthday"),
                "show_birthday",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_location", "Show Location"),
                "show_location",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_characters", "Show Characters"),
                "show_characters",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_pronouns", "Show Pronouns"),
                "show_pronouns",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.show_additional", "Show Additional Info"),
                "show_additional",
                "checkbox",
                True,
            )
        )

        displaySettings.append(
            (
                QApplication.translate("settings.compact_players", "Compact Player Cards"),
                "compact_players",
                "checkbox",
                False,
            )
        )

        displaySettings.append(
            (
                QApplication.translate(
                    "settings.compact_commentators", "Compact Commentator Cards"
                ),
                "compact_commentators",
                "checkbox",
                False,
            )
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Default Display Options"),
            SettingsWidget("display_options", displaySettings),
            "display-options",
        )

        # The rows above every character in the character select grid
        characterSelectSettings = [
            (
                QApplication.translate(
                    "settings.character_picker", "Show the player's mains in the character grid"
                ),
                "show_mains",
                "checkbox",
                True,
            ),
            (
                QApplication.translate(
                    "settings.character_picker",
                    "Show recently picked characters in the character grid",
                ),
                "show_recent",
                "checkbox",
                True,
            ),
        ]

        self.add_setting_widget(
            QApplication.translate("settings", "Character Select"),
            SettingsWidget("character_picker", characterSelectSettings),
            "character-select",
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Match & Phase Names"),
            TournamentTermsSettings(),
            "match-names",
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Pronouns"), PronounSettings(), "pronouns"
        )

        # Add API Key settings
        APIKeySettings = []
        APIKeySettings.append(
            (
                QApplication.translate("settings.api_keys", "ParryGG"),
                "parrygg",
                "password",
                "",
                None,
                QApplication.translate(
                    "settings.api_keys", "You can get an API Key from parry.gg/api-keys"
                )
                + "\n"
                + QApplication.translate(
                    "settings.api_keys",
                    "Please note that the API Key will be stored in plain text on your computer",
                ),
            )
        )

        APIKeySettings.append(
            (
                QApplication.translate("settings.api_keys", "start.gg (reporting sets)"),
                "startgg",
                "password",
                "",
                None,
                QApplication.translate(
                    "settings.api_keys",
                    "Needed to report sets to start.gg from the scoreboard's Games window. Create a token at start.gg > Developer Settings, with an account that's an admin of the tournament.",
                )
                + "\n"
                + QApplication.translate(
                    "settings.api_keys",
                    "Please note that the API Key will be stored in plain text on your computer",
                ),
            )
        )

        APIKeySettings.append(
            (
                QApplication.translate("settings.api_keys", "Twitch (predictions)"),
                "twitch",
                "password",
                "",
                None,
                QApplication.translate(
                    "settings.api_keys",
                    "A user access token of your channel with the channel:manage:predictions scope, e.g. from a token generator for Twitch's API. See Settings > Twitch Predictions.",
                )
                + "\n"
                + QApplication.translate(
                    "settings.api_keys",
                    "Please note that the API Key will be stored in plain text on your computer",
                ),
            )
        )

        self.add_setting_widget(
            QApplication.translate("settings", "API Keys"),
            SettingsWidget("api_keys", APIKeySettings),
            "api-keys",
        )

        # Reporting sets to start.gg from the scoreboard's Games window
        reportingSettings = []
        reportingSettings.append(
            (
                QApplication.translate(
                    "settings.startgg_reporting",
                    "Send each game to start.gg as it's played (otherwise games are sent when the set is reported)",
                ),
                "live_updates",
                "checkbox",
                True,
                None,
                QApplication.translate(
                    "settings.startgg_reporting",
                    "Lets viewers follow the set on start.gg live. Uses one request per change.",
                ),
            )
        )
        reportingSettings.append(
            (
                QApplication.translate(
                    "settings.startgg_reporting",
                    "Mark sets as in progress on start.gg when they're loaded on a scoreboard",
                ),
                "mark_in_progress",
                "checkbox",
                True,
            )
        )
        reportingSettings.append(
            (
                QApplication.translate("settings.startgg_reporting", "Ask before reporting a set"),
                "confirm_report",
                "checkbox",
                True,
            )
        )
        self.add_setting_widget(
            QApplication.translate("settings", "start.gg Reporting"),
            SettingsWidget("startgg_reporting", reportingSettings),
            "startgg-reporting",
        )

        # Twitch predictions for the set on stream, see src/TwitchPredictions.py
        predictionSettings = [
            (
                QApplication.translate(
                    "settings.twitch_predictions", "Run Twitch predictions for the set on stream"
                ),
                "enabled",
                "checkbox",
                False,
                None,
                QApplication.translate(
                    "settings.twitch_predictions",
                    "Needs the Twitch token of Settings > API Keys, and a channel that's a Twitch affiliate or partner.",
                ),
            ),
            (
                QApplication.translate("settings.twitch_predictions", "Scoreboard"),
                "scoreboard",
                "spinbox",
                1,
                None,
                QApplication.translate(
                    "settings.twitch_predictions", "The number of the scoreboard of the stream"
                ),
            ),
            (
                QApplication.translate(
                    "settings.twitch_predictions", "Start one when a set is loaded"
                ),
                "auto_start",
                "checkbox",
                True,
            ),
            (
                QApplication.translate(
                    "settings.twitch_predictions", "Resolve it with the winner when the set is over"
                ),
                "auto_resolve",
                "checkbox",
                True,
            ),
            (
                QApplication.translate("settings.twitch_predictions", "Title"),
                "title",
                "textbox",
                "Who wins {round}?",
                None,
                QApplication.translate(
                    "settings.twitch_predictions",
                    "{team1}, {team2} and {round} are replaced. Twitch allows 45 characters.",
                ),
            ),
            (
                QApplication.translate(
                    "settings.twitch_predictions", "Seconds viewers have to predict"
                ),
                "window",
                "spinbox",
                180,
                None,
                QApplication.translate("settings.twitch_predictions", "From 30 to 1800"),
                30,
            ),
        ]
        self.add_setting_widget(
            QApplication.translate("settings", "Twitch Predictions"),
            SettingsWidget("twitch_predictions", predictionSettings),
            "twitch-predictions",
        )

        self.resize(1000, 500)
        QApplication.processEvents()
        splitter.setSizes([200, self.width() - 200])

    def Open(self, key=None):
        """Shows the window, on the page with that key if given (e.g. "api-keys",
        used by the guide's links)"""
        item = self.pageKeys.get(key)
        if item is not None:
            self.selection_list.setCurrentItem(item)
        self.show()
        self.raise_()
        self.activateWindow()

    def on_selection_changed(self, index):
        # Get the selected item and its associated widget
        item = self.selection_list.item(index)
        widget = item.data(Qt.UserRole)

        # Set the current widget in the stack
        self.settings_stack.setCurrentWidget(widget)

    def add_setting_widget(self, name, widget, key=None):
        # Create a scroll area for the setting widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(widget)

        # Create a list widget item for the selection
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, scroll_area)
        self.selection_list.addItem(item)
        if key:
            self.pageKeys[key] = item

        # Add the setting widget to the stack
        self.settings_stack.addWidget(scroll_area)
