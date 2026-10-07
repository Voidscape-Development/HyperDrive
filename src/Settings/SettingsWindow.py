from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..Helpers.DynamicExport import DynamicExport
from ..Hotkeys import Hotkeys
from ..Scheduler import (
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

    def UiMounted(self):
        self.setWindowTitle(QApplication.translate("Settings", "Settings"))

        # Create a list widget for the selection
        self.selection_list = QListWidget()
        self.selection_list.currentRowChanged.connect(self.on_selection_changed)

        # Create a stacked widget for the settings widgets
        self.settings_stack = QStackedWidget()

        # Create a scroll area for the settings stack
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.settings_stack)

        # Create a splitter for the selection and settings
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.selection_list)
        splitter.addWidget(scroll_area)

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
                QApplication.translate("settings.general", "Enable StateManager Logging"),
                "statemanager_logging",
                "checkbox",
                False,
            )
        )

        generalSettings.append(
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

        generalSettings.append(
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

        generalSettings.append(
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
                    "settings.force_no_mains_on_new_set_loads",
                    "Do not update character data when a set is loaded",
                ),
                "force_no_mains_on_new_set_loads",
                "checkbox",
                False,
            )
        )

        generalSettings.append(
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

        generalSettings.append(
            (
                QApplication.translate(
                    "settings.disable_export", "Disable HyperDrive file exporting"
                ),
                "disable_export",
                "checkbox",
                False,
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
                    "settings.disable_overwrite",
                    "Do not override existing values in the local player database (takes effect on next restart)",
                ),
                "disable_overwrite",
                "checkbox",
                False,
            )
        )

        generalSettings.append(
            (
                QApplication.translate("settings.team_1_default_color", "Default Color of Team 1"),
                "team_1_default_color",
                "color",
                "#fe3636",
            )
        )

        generalSettings.append(
            (
                QApplication.translate("settings.team_2_default_color", "Default Color of Team 2"),
                "team_2_default_color",
                "color",
                "#2e89ff",
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
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Appearance"), AppearanceSettings()
        )

        # Add hotkey settings
        hotkeySettings = []

        hotkeySettings.append(
            (
                QApplication.translate("settings.hotkeys", "Enable hotkeys"),
                "hotkeys_enabled",
                "checkbox",
                True,
            )
        )

        key_names = {
            "load_set": QApplication.translate("settings.hotkeys", "Load set"),
            "team1_score_up": QApplication.translate("settings.hotkeys", "Team 1 score up"),
            "team1_score_down": QApplication.translate("settings.hotkeys", "Team 1 score down"),
            "team2_score_up": QApplication.translate("settings.hotkeys", "Team 2 score up"),
            "team2_score_down": QApplication.translate("settings.hotkeys", "Team 2 score down"),
            "reset_scores": QApplication.translate("settings.hotkeys", "Reset scores"),
            "swap_teams": QApplication.translate("settings.hotkeys", "Swap teams"),
            "refresh_phase_group": QApplication.translate(
                "settings.hotkeys", "Refresh bracket phase groups"
            ),
            "limit_export": QApplication.translate(
                "settings.hotkeys", "Toggle bracket limit export"
            ),
            "bracket_focus_all": QApplication.translate(
                "settings.hotkeys", "Bracket focus: show the whole bracket"
            ),
            "bracket_focus_previous_round": QApplication.translate(
                "settings.hotkeys", "Bracket focus: previous round"
            ),
            "bracket_focus_next_round": QApplication.translate(
                "settings.hotkeys", "Bracket focus: next round"
            ),
            "bracket_focus_follow": QApplication.translate(
                "settings.hotkeys", "Bracket focus: follow the set on stream on/off"
            ),
            "bracket_focus_tour": QApplication.translate(
                "settings.hotkeys", "Bracket focus: round tour on/off"
            ),
        }

        for i, (setting, value) in enumerate(Hotkeys.instance.keys.items()):
            hotkeySettings.append(
                (key_names[setting], setting, "hotkey", value, Hotkeys.instance.ReloadHotkeys)
            )

        self.add_setting_widget(
            QApplication.translate("settings", "Hotkeys"), SettingsWidget("hotkeys", hotkeySettings)
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

        self.add_setting_widget(
            QApplication.translate("settings", "Default Display Options"),
            SettingsWidget("display_options", displaySettings),
        )

        self.add_setting_widget(
            QApplication.translate("settings", "Match & Phase Names"), TournamentTermsSettings()
        )

        self.add_setting_widget(QApplication.translate("settings", "Pronouns"), PronounSettings())

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

        self.add_setting_widget(
            QApplication.translate("settings", "API Keys"),
            SettingsWidget("api_keys", APIKeySettings),
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
        )

        self.resize(1000, 500)
        QApplication.processEvents()
        splitter.setSizes([200, self.width() - 200])

    def on_selection_changed(self, index):
        # Get the selected item and its associated widget
        item = self.selection_list.item(index)
        widget = item.data(Qt.UserRole)

        # Set the current widget in the stack
        self.settings_stack.setCurrentWidget(widget)

    def add_setting_widget(self, name, widget):
        # Create a list widget item for the selection
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, widget)
        self.selection_list.addItem(item)

        # Add the setting widget to the stack
        self.settings_stack.addWidget(widget)
