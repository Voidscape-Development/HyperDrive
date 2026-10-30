import atexit
import os
import subprocess
import sys

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
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
    TRACKING_NEXT_SET_DEFAULT_DELAY_SECS,
    Scheduler,
)
from ..SettingsManager import SettingsManager
from ..Theme import ThemedIcon
from .AppearanceSettings import AppearanceSettings
from .Controls import Banner, Description, NoDefaultButtons, SettingsPage
from .PronounSettings import PronounSettings
from .SettingsWidget import (
    TYPE_NUMBER,
    TYPE_PASSWORD,
    TYPE_TEMPLATE,
    TYPE_TOGGLE,
    Setting,
)
from .TournamentTermsSettings import TournamentTermsSettings

PAGE_ROLE = Qt.ItemDataRole.UserRole
# A search result's row, or None for a page
ROW_ROLE = Qt.ItemDataRole.UserRole + 1

SIDEBAR_WIDTH = 248

# Pages that were merged into others, so old links still open the right one
PAGE_ALIASES = {"state-manager": "data"}

# The most results the search lists
MAX_RESULTS = 60


def _tr(context, text):
    return QApplication.translate(context, text)


def Restart():
    """Closes HyperDrive and starts it again once it's closed"""
    if getattr(sys, "frozen", False):
        command = [sys.executable] + sys.argv[1:]
    else:
        command = [sys.executable] + sys.argv
    folder = os.getcwd()

    def Start():
        try:
            subprocess.Popen(command, cwd=folder, close_fds=True)
        except OSError:
            logger.opt(exception=True).error("Could not start HyperDrive again")

    atexit.register(Start)
    for window in QApplication.topLevelWidgets():
        if isinstance(window, QMainWindow):
            window.close()
            return
    QApplication.quit()


def Embedded(widget):
    """A page's widget, lined up with the page's title"""
    widget.layout().setContentsMargins(0, 0, 0, 0)
    return widget


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # key -> the page's item in the sidebar, see Open()
        self.pageKeys = {}
        # (key, title, page) in the order they're listed
        self.pages = []
        # The settings that take effect on restart
        self.restartSettings = []

    # =====================================================
    # BUILDING
    # =====================================================
    def UiMounted(self):
        self.setWindowTitle(_tr("Settings", "Settings"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sideLayout = QVBoxLayout(sidebar)
        sideLayout.setContentsMargins(10, 12, 10, 12)
        sideLayout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText(_tr("settings", "Search settings"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            ThemedIcon("assets/icons/search.svg"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.textChanged.connect(self.Search)
        self.search.returnPressed.connect(self.OpenFirstResult)
        self.search.installEventFilter(self)
        sideLayout.addWidget(self.search)

        self.navStack = QStackedWidget()
        self.nav = QListWidget()
        self.nav.setIconSize(QSize(16, 16))
        self.nav.currentItemChanged.connect(self.PageSelected)
        self.navStack.addWidget(self.nav)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.itemActivated.connect(self.OpenResult)
        self.results.itemClicked.connect(self.OpenResult)
        self.navStack.addWidget(self.results)
        sideLayout.addWidget(self.navStack, 1)
        layout.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.restartBanner = Banner("", icon="assets/icons/restart.svg")
        self.restartBanner.AddButton(_tr("settings", "Later")).clicked.connect(
            self.restartBanner.hide
        )
        self.restartBanner.AddButton(_tr("settings", "Restart now"), primary=True).clicked.connect(
            Restart
        )
        self.restartBanner.hide()
        bannerBox = QVBoxLayout()
        bannerBox.setContentsMargins(24, 14, 24, 0)
        bannerBox.addWidget(self.restartBanner)
        content.addLayout(bannerBox)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        layout.addLayout(content, 1)

        QShortcut(QKeySequence.StandardKey.Find, self, self.FocusSearch)

        self.BuildPages()

        for setting in self.restartSettings:
            setting.changed.connect(self.UpdateRestartBanner)
        NoDefaultButtons(self)
        self.nav.setCurrentRow(1)
        self.resize(1080, 680)

    def Heading(self, text):
        item = QListWidgetItem(text.upper())
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 0.8)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        item.setFont(font)
        if self.nav.count():
            item.setSizeHint(QSize(0, 34))
        self.nav.addItem(item)

    def AddPage(self, key, title, icon, page):
        if isinstance(page, SettingsPage):
            page.Finish()
        item = QListWidgetItem(ThemedIcon(icon), title)
        item.setData(PAGE_ROLE, page)
        self.nav.addItem(item)
        self.stack.addWidget(page)
        self.pageKeys[key] = item
        self.pages.append((key, title, page))
        return page

    def Track(self, *settings):
        for setting in settings:
            if setting.restart:
                self.restartSettings.append(setting)
        return settings

    def Rows(self, group, *settings):
        """Adds the settings' rows to the group, keeping the settings alive"""
        self.Track(*settings)
        for setting in settings:
            setting.setParent(group)
            group.AddRow(setting.row)
        return settings

    def BuildPages(self):
        # ---------------- HyperDrive ----------------
        self.Heading(_tr("settings", "HyperDrive"))

        page = SettingsPage(
            _tr("settings", "General"),
            _tr("settings", "Tournament data and how often HyperDrive gets it."),
        )
        self.Rows(
            page.AddGroup(_tr("settings", "Tournament data")),
            Setting(
                "general.profanity_filter",
                TYPE_TOGGLE,
                True,
                _tr("settings.general", "Profanity filter"),
                _tr(
                    "settings.general",
                    "Masks offensive words in the tags, sponsors, names and handles of players loaded from a tournament",
                ),
            ),
            Setting(
                "general.completed_sets_pull_interval",
                TYPE_NUMBER,
                COMPLETED_SETS_DEFAULT_INTERVAL_SECS,
                _tr("settings.completed_sets_pull_interval", "Pull completed sets every"),
                _tr("settings.completed_sets_pull_interval", "While Auto pull is on"),
                lambda: Scheduler.instance.SetInterval(
                    "completed_sets",
                    SettingsManager.Get(
                        "general.completed_sets_pull_interval", COMPLETED_SETS_DEFAULT_INTERVAL_SECS
                    )
                    * 1000,
                ),
                minimum=COMPLETED_SETS_MIN_INTERVAL_SECS,
                suffix="s",
            ),
            Setting(
                "general.bracket_auto_update_interval",
                TYPE_NUMBER,
                BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                _tr("settings.bracket_auto_update_interval", "Update the bracket every"),
                _tr(
                    "settings.bracket_auto_update_interval", "While the bracket's Auto update is on"
                ),
                lambda: Scheduler.instance.SetInterval(
                    "bracket_sets",
                    SettingsManager.Get(
                        "general.bracket_auto_update_interval",
                        BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                    )
                    * 1000,
                ),
                minimum=BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS,
                suffix="s",
            ),
        )
        self.AddPage("general", _tr("settings", "General"), "assets/icons/settings.svg", page)

        appearance = AppearanceSettings()
        self.Track(*appearance.settings)
        self.AddPage(
            "appearance", _tr("settings", "Appearance"), "assets/icons/palette.svg", appearance
        )

        page = SettingsPage(
            _tr("settings", "Web pages & PIN"),
            _tr(
                "settings",
                "HyperDrive's web pages, for your phone or a second screen: the remote scoreboard, the dashboard and the players' pages.",
            ),
        )
        self.Rows(
            page.AddGroup(),
            Setting(
                "general.webserver_port",
                TYPE_NUMBER,
                5500,
                _tr("settings.general", "Web server port"),
                _tr("settings.general", "The pages are at http://<this computer>:<port>"),
                minimum=1,
                maximum=65535,
                restart=True,
            ),
            Setting(
                "general.dashboard_pin",
                TYPE_PASSWORD,
                "",
                _tr("settings.general", "Web dashboard PIN"),
                _tr(
                    "settings.general",
                    "Each browser asks for it once. Empty: no PIN. The players' pages never ask.",
                ),
                placeholder=_tr("settings.general", "No PIN"),
            ),
        )
        self.AddPage(
            "web-pages", _tr("settings", "Web pages & PIN"), "assets/icons/globe.svg", page
        )

        # ---------------- On stream ----------------
        self.Heading(_tr("settings", "On stream"))

        # Scoreboard settings are stored under general, where they were
        # before they got their own page
        page = SettingsPage(
            _tr("settings", "Scoreboard"),
            _tr(
                "settings",
                "How sets load onto the scoreboards and stay up to date while they're played.",
            ),
        )
        group = page.AddGroup(_tr("settings", "Set updates"))
        autoUpdate = Setting(
            "general.disable_autoupdate",
            TYPE_TOGGLE,
            False,
            _tr("settings.disable_autoupdate", "Update the loaded set automatically"),
            _tr(
                "settings.disable_autoupdate",
                "Games, characters and stages from start.gg or parry.gg while the set is played",
            ),
            invert=True,
        )
        interval = Setting(
            "general.scoreboard_auto_update_interval",
            TYPE_NUMBER,
            SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
            _tr("settings.scoreboard_auto_update_interval", "Check every"),
            callback=lambda: Scheduler.instance.SetGroupInterval(
                SCOREBOARD_AUTO_UPDATE_GROUP,
                SettingsManager.Get(
                    "general.scoreboard_auto_update_interval",
                    SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS,
                )
                * 1000,
            ),
            minimum=SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS,
            suffix="s",
            indent=True,
        ).EnabledBy(autoUpdate)
        self.Rows(
            group,
            autoUpdate,
            interval,
            Setting(
                "general.disable_scoreupdate",
                TYPE_TOGGLE,
                False,
                _tr("settings.disable_scoreupdate", "Update the score automatically"),
                _tr(
                    "settings.disable_scoreupdate",
                    "Off: the score only changes when you or the stage striking app change it",
                ),
                invert=True,
            ),
            Setting(
                "general.force_no_mains_on_new_set_loads",
                TYPE_TOGGLE,
                False,
                _tr(
                    "settings.force_no_mains_on_new_set_loads",
                    "Fill in characters when a set loads",
                ),
                _tr(
                    "settings.force_no_mains_on_new_set_loads",
                    "From the players' mains and the set's games. Off: the characters picked stay",
                ),
                invert=True,
            ),
            Setting(
                "general.tracking_next_set_delay",
                TYPE_NUMBER,
                TRACKING_NEXT_SET_DEFAULT_DELAY_SECS,
                _tr(
                    "settings.tracking_next_set_delay",
                    "Wait before loading a tracked stream's next set",
                ),
                _tr(
                    "settings.tracking_next_set_delay",
                    "Holds it while the current set isn't over. 0 loads it at once.",
                ),
                minimum=0,
                suffix="s",
            ),
        )
        self.Rows(
            page.AddGroup(_tr("settings", "Stage striking app")),
            Setting(
                "general.control_score_from_stage_strike",
                TYPE_TOGGLE,
                True,
                _tr("settings.control_score_from_stage_strike", "Players can change the score"),
            ),
            # Sent to the stage strike page with its data (WebServerActions.ruleset)
            Setting(
                "general.stage_strike_ask_characters",
                TYPE_TOGGLE,
                True,
                _tr(
                    "settings.stage_strike_ask_characters",
                    "Ask for the next game's characters after each game",
                ),
            ),
        )
        self.Rows(
            page.AddGroup(_tr("settings", "Player info")),
            Setting(
                "general.local_player_data",
                TYPE_TOGGLE,
                False,
                _tr(
                    "settings.local_player_data",
                    "Use the local player database for socials, pronouns and location",
                ),
                _tr(
                    "settings.local_player_data",
                    "Sets, the stream queue and station sets load without them. Players not in the database yet are looked up once and saved to it.",
                ),
            ),
            Setting(
                "general.disable_overwrite",
                TYPE_TOGGLE,
                False,
                _tr("settings.disable_overwrite", "Keep values already in the player database"),
                _tr(
                    "settings.disable_overwrite",
                    "Off: loading a set updates saved players with the newest info",
                ),
                restart=True,
            ),
        )
        self.AddPage(
            "scoreboard", _tr("settings", "Scoreboard"), "assets/icons/scoreboard.svg", page
        )

        page = SettingsPage(
            _tr("settings", "Player cards"),
            _tr("settings", "What new player and commentator cards show. Each card can change it."),
        )
        shown = [
            ("show_name", _tr("settings.show_name", "Real name")),
            ("show_social", _tr("settings.show_social", "Social media")),
            ("show_seed", _tr("settings.show_seed", "Seed")),
            ("show_birthday", _tr("settings.show_birthday", "Birthday")),
            ("show_location", _tr("settings.show_location", "Location")),
            ("show_characters", _tr("settings.show_characters", "Characters")),
            ("show_pronouns", _tr("settings.show_pronouns", "Pronouns")),
            ("show_additional", _tr("settings.show_additional", "Additional info")),
        ]
        self.Rows(
            page.AddGroup(_tr("settings", "Show on new cards")),
            *[Setting("display_options." + key, TYPE_TOGGLE, True, title) for key, title in shown],
        )
        self.Rows(
            page.AddGroup(_tr("settings", "Compact cards")),
            Setting(
                "display_options.compact_players",
                TYPE_TOGGLE,
                False,
                _tr("settings.compact_players", "Compact player cards"),
            ),
            Setting(
                "display_options.compact_commentators",
                TYPE_TOGGLE,
                False,
                _tr("settings.compact_commentators", "Compact commentator cards"),
            ),
        )
        self.AddPage(
            "display-options", _tr("settings", "Player cards"), "assets/icons/person.svg", page
        )

        page = SettingsPage(
            _tr("settings", "Character select"),
            _tr("settings", "The rows above every character in the character grid."),
        )
        self.Rows(
            page.AddGroup(),
            Setting(
                "character_picker.show_mains",
                TYPE_TOGGLE,
                True,
                _tr("settings.character_picker", "Show the player's mains"),
            ),
            Setting(
                "character_picker.show_recent",
                TYPE_TOGGLE,
                True,
                _tr("settings.character_picker", "Show recently picked characters"),
            ),
        )
        self.AddPage(
            "character-select", _tr("settings", "Character select"), "assets/icons/grid.svg", page
        )

        page = SettingsPage(
            _tr("settings", "Crew battles"),
            _tr("settings", "What a new crew or team battle starts with."),
        )
        self.Rows(
            page.AddGroup(),
            Setting(
                "general.team_battle_default_stocks",
                TYPE_NUMBER,
                3,
                _tr("settings.team_battle_default_stocks", "Starting stocks per player"),
                _tr("settings.team_battle_default_stocks", "Stock Pool battles"),
            ),
            Setting(
                "general.team_battle_default_first_to",
                TYPE_NUMBER,
                2,
                _tr("settings.team_battle_default_first_to", "Games to win a matchup"),
                _tr("settings.team_battle_default_first_to", "First To battles"),
            ),
        )
        self.AddPage(
            "crew-battles", _tr("settings", "Crew battles"), "assets/icons/people.svg", page
        )

        page = SettingsPage(
            _tr("settings", "Match & phase names"),
            _tr(
                "settings",
                "Rename the match and phase names of the scoreboard's dropdowns and of sets loaded from start.gg, and add your own.",
            ),
        )
        page.AddWidget(Embedded(TournamentTermsSettings()), 1)
        self.AddPage(
            "match-names", _tr("settings", "Match & phase names"), "assets/icons/list.svg", page
        )

        page = SettingsPage(_tr("settings", "Pronouns"))
        page.AddWidget(Embedded(PronounSettings()), 1)
        self.AddPage("pronouns", _tr("settings", "Pronouns"), "assets/icons/chat.svg", page)

        # ---------------- Connections ----------------
        self.Heading(_tr("settings", "Connections"))

        plainText = _tr(
            "settings.api_keys", "Keys are saved as plain text in user_data/settings.json."
        )
        page = SettingsPage(_tr("settings", "API keys"), plainText)
        self.Rows(
            page.AddGroup(),
            self.ParryKey(),
            self.StartggKey(),
            self.TwitchKey(),
        )
        self.AddPage("api-keys", _tr("settings", "API keys"), "assets/icons/key.svg", page)

        page = SettingsPage(
            _tr("settings", "start.gg reporting"),
            _tr(
                "settings",
                "Reporting sets to start.gg from the scoreboard's Games window. Needs the start.gg token of API keys.",
            ),
        )
        self.Rows(
            page.AddGroup(),
            Setting(
                "startgg_reporting.live_updates",
                TYPE_TOGGLE,
                True,
                _tr("settings.startgg_reporting", "Send each game to start.gg as it's played"),
                _tr(
                    "settings.startgg_reporting",
                    "Lets viewers follow the set on start.gg. Off: games are sent when the set is reported. Uses one request per change.",
                ),
            ),
            Setting(
                "startgg_reporting.mark_in_progress",
                TYPE_TOGGLE,
                True,
                _tr(
                    "settings.startgg_reporting",
                    "Mark sets as in progress when they're loaded on a scoreboard",
                ),
            ),
            Setting(
                "startgg_reporting.confirm_report",
                TYPE_TOGGLE,
                True,
                _tr("settings.startgg_reporting", "Ask before reporting a set"),
            ),
        )
        self.AddPage(
            "startgg-reporting",
            _tr("settings", "start.gg reporting"),
            "assets/icons/startgg.svg",
            page,
        )

        # Reporting sets from the web pages, see src/WebReporting.py
        page = SettingsPage(
            _tr("settings", "Web reporting"),
            _tr(
                "settings",
                "Players report their sets' results from /report, for an admin to approve.",
            ),
        )
        stations = Setting(
            "web_reporting.stations_enabled",
            TYPE_TOGGLE,
            True,
            _tr("settings.web_reporting", "Accept results from player reporting stations"),
            _tr(
                "settings.web_reporting",
                "Players' results wait on the Approval page until an admin approves them.",
            ),
        )
        self.Rows(
            page.AddGroup(),
            stations,
            Setting(
                "web_reporting.station_pin",
                TYPE_PASSWORD,
                "",
                _tr("settings.web_reporting", "Reporting station PIN"),
                _tr(
                    "settings.web_reporting",
                    "Asked once by each reporting station. Empty: no PIN. The admin pages use the web dashboard PIN.",
                ),
                indent=True,
                placeholder=_tr("settings.web_reporting", "No PIN"),
            ).EnabledBy(stations),
            Setting(
                "web_reporting.refresh_interval",
                TYPE_NUMBER,
                30,
                _tr("settings.web_reporting", "Get the sets from start.gg every"),
                _tr("settings.web_reporting", "While a reporting page is open"),
                minimum=10,
                suffix="s",
            ),
        )
        self.AddPage(
            "web-reporting", _tr("settings", "Web reporting"), "assets/icons/station.svg", page
        )

        # Twitch predictions for the set on stream, see src/TwitchPredictions.py
        page = SettingsPage(
            _tr("settings", "Twitch predictions"),
            _tr(
                "settings",
                "Lets viewers bet channel points on the set on stream. Needs a channel that's a Twitch affiliate or partner.",
            ),
        )
        self.Rows(page.AddGroup(), self.TwitchKey())
        group = page.AddGroup(_tr("settings.twitch_predictions", "When to run them"))
        enabled = Setting(
            "twitch_predictions.enabled",
            TYPE_TOGGLE,
            False,
            _tr("settings.twitch_predictions", "Run predictions for the set on stream"),
        )
        self.Rows(
            group,
            enabled,
            Setting(
                "twitch_predictions.scoreboard",
                TYPE_NUMBER,
                1,
                _tr("settings.twitch_predictions", "Scoreboard on stream"),
                _tr("settings.twitch_predictions", "The number of the scoreboard of the stream"),
                indent=True,
            ).EnabledBy(enabled),
            Setting(
                "twitch_predictions.auto_start",
                TYPE_TOGGLE,
                True,
                _tr("settings.twitch_predictions", "Start one when a set loads"),
                indent=True,
            ).EnabledBy(enabled),
            Setting(
                "twitch_predictions.auto_resolve",
                TYPE_TOGGLE,
                True,
                _tr("settings.twitch_predictions", "Pay out to the winner when the set ends"),
                indent=True,
            ).EnabledBy(enabled),
        )
        self.Rows(
            page.AddGroup(_tr("settings.twitch_predictions", "The prediction")),
            Setting(
                "twitch_predictions.title",
                TYPE_TEMPLATE,
                "Who wins {round}?",
                _tr("settings.twitch_predictions", "Title"),
                _tr(
                    "settings.twitch_predictions",
                    "The placeholders are replaced with the set's teams and round. Twitch allows 45 characters.",
                ),
                tokens=["{team1}", "{team2}", "{round}"],
            ).EnabledBy(enabled),
            Setting(
                "twitch_predictions.window",
                TYPE_NUMBER,
                180,
                _tr("settings.twitch_predictions", "Time viewers have to predict"),
                _tr("settings.twitch_predictions", "30 s to 30 min"),
                minimum=30,
                maximum=1800,
                suffix="s",
            ).EnabledBy(enabled),
        )
        self.AddPage(
            "twitch-predictions",
            _tr("settings", "Twitch predictions"),
            "assets/icons/twitch.svg",
            page,
        )

        # ---------------- Advanced ----------------
        self.Heading(_tr("settings", "Advanced"))

        page = SettingsPage(
            _tr("settings", "Data & file export"),
            _tr("settings", "The data HyperDrive sends to the layouts and writes to files."),
        )
        self.Rows(
            page.AddGroup(),
            Setting(
                "general.custom_player_export",
                TYPE_TOGGLE,
                True,
                _tr("settings.custom_player_export", "Send custom player data to the layouts"),
                _tr(
                    "settings.custom_player_export",
                    "The files in user_data/custom_player_export, in a folder named after a player's tag (or sponsor and tag). Changes show up on stream within a second.",
                ),
                DynamicExport.SettingChanged,
            ),
            Setting(
                "general.disable_export",
                TYPE_TOGGLE,
                False,
                _tr("settings.disable_export", "Write the layouts' data to the out folder"),
                _tr(
                    "settings.disable_export",
                    "For other software that reads HyperDrive's files. The layouts don't need it.",
                ),
                invert=True,
            ),
            Setting(
                "general.statemanager_logging",
                TYPE_TOGGLE,
                False,
                _tr("settings.general", "Log every change of the layouts' data"),
                _tr("settings.general", "For troubleshooting. Makes the log much longer."),
            ),
        )
        self.AddPage("data", _tr("settings", "Data & file export"), "assets/icons/db.svg", page)

    # The API keys, on their page and on the pages that need them
    def ParryKey(self):
        return Setting(
            "api_keys.parrygg",
            TYPE_PASSWORD,
            "",
            _tr("settings.api_keys", "parry.gg"),
            _tr(
                "settings.api_keys",
                "For loading parry.gg tournaments. Get one at parry.gg/api-keys.",
            ),
            status=True,
        )

    def StartggKey(self):
        return Setting(
            "api_keys.startgg",
            TYPE_PASSWORD,
            "",
            _tr("settings.api_keys", "start.gg token"),
            _tr(
                "settings.api_keys",
                "For reporting sets, calling them and assigning streams. Create one at start.gg > Developer Settings, with an account that's an admin of the tournament.",
            ),
            status=True,
        )

    def TwitchKey(self):
        return Setting(
            "api_keys.twitch",
            TYPE_PASSWORD,
            "",
            _tr("settings.api_keys", "Twitch token"),
            _tr(
                "settings.api_keys",
                "For Twitch predictions: a user access token of your channel with the channel:manage:predictions scope.",
            ),
            status=True,
        )

    # =====================================================
    # PAGES
    # =====================================================
    def Open(self, key=None):
        """Shows the window, on the page with that key if given (e.g. "api-keys",
        used by the guide's links)"""
        item = self.pageKeys.get(PAGE_ALIASES.get(key, key))
        if item is not None:
            self.search.clear()
            self.nav.setCurrentItem(item)
        self.show()
        self.raise_()
        self.activateWindow()

    def PageSelected(self, item, previous=None):
        if item is None:
            return
        page = item.data(PAGE_ROLE)
        if page is not None:
            self.stack.setCurrentWidget(page)

    def CurrentPage(self):
        return self.stack.currentWidget()

    # =====================================================
    # SEARCH
    # =====================================================
    def FocusSearch(self):
        self.search.setFocus()
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if (
            obj is self.search
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and self.search.text()
        ):
            self.search.clear()
            return True
        if (
            obj is self.search
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Down
            and self.results.count()
        ):
            self.results.setFocus()
            self.results.setCurrentRow(0)
            return True
        return super().eventFilter(obj, event)

    def Search(self, text):
        words = text.lower().split()
        if not words:
            self.navStack.setCurrentWidget(self.nav)
            return
        self.results.clear()
        for key, title, page in self.pages:
            pageText = " ".join((title, getattr(page, "descriptionText", ""))).lower()
            if all(word in pageText for word in words):
                self.AddResult(title, _tr("settings", "Page"), page, None)
            if isinstance(page, SettingsPage):
                for row in page.Rows():
                    if all(word in row.SearchText() for word in words):
                        self.AddResult(row.title, title, page, row)
            if self.results.count() >= MAX_RESULTS:
                break
        if not self.results.count():
            item = QListWidgetItem(_tr("settings", "No settings match"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        self.navStack.setCurrentWidget(self.results)

    def AddResult(self, title, where, page, row):
        item = QListWidgetItem()
        item.setData(PAGE_ROLE, page)
        item.setData(ROW_ROLE, row)
        item.setToolTip(f"{where} › {title}")
        # The title, and where it is in muted text under it
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(1)
        layout.addWidget(QLabel(title))
        whereLabel = Description(where)
        whereLabel.setWordWrap(False)
        layout.addWidget(whereLabel)
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.results.addItem(item)
        # Measured from the font: the widget's own size hint is taken before
        # the style sheet's padding applies
        item.setSizeHint(QSize(0, self.results.fontMetrics().lineSpacing() * 2 + 16))
        self.results.setItemWidget(item, widget)

    def OpenResult(self, item):
        page = item.data(PAGE_ROLE)
        if page is None:
            return
        for key, title, p in self.pages:
            if p is page:
                self.nav.setCurrentItem(self.pageKeys[key])
        row = item.data(ROW_ROLE)
        if row is not None:
            page.ShowRow(row)

    def OpenFirstResult(self):
        if self.navStack.currentWidget() is self.results and self.results.count():
            self.OpenResult(self.results.item(0))

    # =====================================================
    # RESTART
    # =====================================================
    def UpdateRestartBanner(self):
        changed = sum(1 for s in self.restartSettings if s.Value() != s.startValue)
        if not changed:
            self.restartBanner.hide()
            return
        if changed == 1:
            text = _tr("settings", "1 change takes effect after HyperDrive restarts.")
        else:
            text = _tr("settings", "{0} changes take effect after HyperDrive restarts.").format(
                changed
            )
        self.restartBanner.SetText(text)
        self.restartBanner.show()
