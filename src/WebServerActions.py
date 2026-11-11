import logging
import os

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketWidget import BracketWidget
from .CommentaryPreview import CommentaryPreview
from .CommentaryWidget import CommentaryWidget
from .GameAssetManager import GameAssetManager
from .Helpers import QtHelper
from .Helpers.CountryHelper import CountryHelper
from .Helpers.LocaleHelper import LocaleHelper
from .PlayerDB import PlayerDB
from .ScoreboardWidget import ScoreboardWidget
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TeamBattleWidget import TeamBattleWidget
from .TournamentDataManager import TournamentDataManager
from .TournamentDataProvider.TournamentEventLookup import (
    FetchTournamentEvents,
    NormalizeEventURL,
    ParseTournamentInput,
    TournamentLookupError,
)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# How long (seconds) a request waits for the GUI thread to run its action,
# before it's answered with 503. The action may still run afterwards.
GUI_TIMEOUT = 10
# How long (seconds) a request waits for a game's assets to load
GAME_LOAD_TIMEOUT = 120


class ActionError(Exception):
    """An action can't be done as asked. status is the HTTP status that
    tells why (400: a parameter isn't valid)."""

    status = 400

    def __init__(self, message, status=None):
        super().__init__(message)
        if status is not None:
            self.status = status


def run_on_gui_thread(fn):
    """Runs fn on the GUI thread and returns what it returns. Raises
    ActionError (503 GUI_BUSY) if the GUI thread doesn't get to it within
    GUI_TIMEOUT."""
    try:
        return QtHelper.gui_executor.run_sync(fn, timeout=GUI_TIMEOUT)
    except TimeoutError as e:
        raise ActionError("GUI_BUSY", 503) from e


class ScoreboardNotAvailable(ActionError):
    """Raised when a scoreboard is requested but not yet initialized."""

    status = 503


class ScoreboardNotFound(ActionError):
    """Raised when a scoreboard number isn't one of the scoreboards."""

    status = 404


class WebServerActions(QObject):
    """What the web server's clients can do. WebActionRegistry lists the
    actions with their parameters and the thread each runs on: the ones it
    marks as gui use widgets and must be called on the GUI thread, the others
    from a worker thread (they may wait for the network or the GUI thread)."""

    def __init__(
        self,
        parent=None,
        scoreboard=None,
        stageWidget=None,
        commentaryWidget: CommentaryWidget = None,
    ) -> None:
        super().__init__(parent)
        self.scoreboard = scoreboard
        self.stageWidget = stageWidget
        self.commentaryWidget = commentaryWidget

    # =====================================================
    # SCOREBOARD AND STAGE STRIKE LOOKUPS
    # =====================================================
    def scoreboard_number(self, number):
        """The number of an existing scoreboard as an int. Raises
        ScoreboardNotFound if it isn't one (the numbers are whole, from 1), and
        ScoreboardNotAvailable while there are no scoreboards yet."""
        count = len(self.scoreboard.GetScoreboardNumbers())
        if count < 1:
            raise ScoreboardNotAvailable("No scoreboard available")
        if isinstance(number, str) and number.isascii() and number.isdigit():
            number = int(number)
        if type(number) is not int or not 1 <= number <= count:
            raise ScoreboardNotFound(f"Scoreboard {number} not found")
        return number

    def _get_scoreboard(self, number=1):
        """Get a scoreboard by number, raising ScoreboardNotFound if it doesn't exist."""
        number = self.scoreboard_number(number)
        sb = self.scoreboard.GetScoreboard(number)
        if sb is None:
            raise ScoreboardNotFound(f"Scoreboard {number} not found")
        return sb

    def _scoreboard_number(self, number):
        """A scoreboard number for stage striking, scoreboard 1 without one."""
        return self.scoreboard_number(1 if number in (None, "") else number)

    def _strike_logic(self, scoreboard):
        return self.stageWidget.GetLogic(self._scoreboard_number(scoreboard))

    def _team_number(self, team):
        """HyperDrive's team number (1 or 2) a stage strike page is for, or None for both."""
        try:
            team = int(team) if team not in (None, "") else None
        except (TypeError, ValueError):
            return None
        return team if team in (1, 2) else None

    def _team_strike_player(self, scoreboard, team):
        # The stage strike's players are the teams as shown, so swapped
        # teams strike as the other player
        if self._get_scoreboard(scoreboard).teamsSwapped:
            return 2 - team
        return team - 1

    def _not_your_turn(self, scoreboard, team):
        """Whether a page for one team tries to act on the other team's turn."""
        team = self._team_number(team)
        if team is None:
            return False
        logic = self._strike_logic(scoreboard)
        state = logic.CurrentState()
        return state.currPlayer != self._team_strike_player(logic.scoreboardNumber, team)

    # =====================================================
    # STAGE STRIKING
    # =====================================================
    def ruleset(self, scoreboard=1):
        data = {}

        # Add webserver base path
        data.update({"basedir": os.path.abspath(".")})

        if self.scoreboard.GetTabAmount() < 1:
            data["ruleset"] = StateManager.Get("score.ruleset", {})
            return data

        try:
            n = self._scoreboard_number(scoreboard)
        except ScoreboardNotFound:
            # The page may still ask for a scoreboard that was removed
            n = 1

        data["scoreboard"] = n
        data["scoreboards"] = [
            {"number": i, "name": self.scoreboard.GetTabName(i)}
            for i in self.scoreboard.GetScoreboardNumbers()
        ]
        data["ruleset"] = StateManager.Get(f"score.{n}.ruleset") or StateManager.Get(
            "score.ruleset", {}
        )
        data["game"] = StateManager.Get("game.codename")
        # Whether the page opens the character select once a game's winner is reported
        data["ask_characters"] = SettingsManager.Get("general.stage_strike_ask_characters", True)

        sb = self._get_scoreboard(n)
        data["characters_per_player"] = sb.charNumber.value()
        data["players_per_team"] = sb.playerNumber.value()

        # Add player names
        teams = [1, 2]
        if sb.teamsSwapped:
            teams.reverse()

        data["teams"] = [None, None]

        for i, t in enumerate(teams):
            if StateManager.Get(f"score.{n}.team.{i + 1}.teamName"):
                data.update({f"p{t}": StateManager.Get(f"score.{n}.team.{i + 1}.teamName")})
            else:
                names = [
                    p.get("name")
                    for p in StateManager.Get(f"score.{n}.team.{i + 1}.player", {}).values()
                    if p.get("name")
                ]

                data.update({f"p{t}": " / ".join(names)})

            # Country code of the first player on this team (for per-player language)
            player_1 = StateManager.Get(f"score.{n}.team.{i + 1}.player.1", {}) or {}
            country = player_1.get("country")
            data[f"p{t}_country"] = country.get("code") if isinstance(country, dict) else None

            # The team's players and their characters, for reporting characters.
            # "team" is the team number used by /scoreboard<n>-update-team-<team>-<player>
            players = []
            playerData = StateManager.Get(f"score.{n}.team.{i + 1}.player", {}) or {}
            for key in sorted(playerData.keys(), key=lambda k: int(k) if str(k).isdigit() else 0):
                player = playerData.get(key) or {}
                characters = []
                for charKey in sorted(
                    (player.get("character") or {}).keys(),
                    key=lambda k: int(k) if str(k).isdigit() else 0,
                ):
                    char = (player.get("character") or {}).get(charKey) or {}
                    if char.get("codename") or char.get("en_name"):
                        skin = char.get("skin")
                        characters.append(
                            {
                                # en_name may be a skin's, as some skins are other characters
                                "codename": char.get("codename"),
                                "en_name": char.get("en_name"),
                                "skin": skin if isinstance(skin, int) and skin >= 0 else 0,
                            }
                        )
                    else:
                        characters.append(None)
                players.append(
                    {
                        "player": int(key) if str(key).isdigit() else key,
                        "name": player.get("name") or "",
                        "team": player.get("team") or "",
                        "characters": characters,
                    }
                )
            data["teams"][t - 1] = {
                "team": i + 1,
                "name": StateManager.Get(f"score.{n}.team.{i + 1}.teamName") or "",
                "color": StateManager.Get(f"score.{n}.team.{i + 1}.color"),
                "players": players,
            }

        # Add set data
        data.update(
            {
                "best_of": StateManager.Get(f"score.{n}.best_of"),
                "match": StateManager.Get(f"score.{n}.match"),
                "phase": StateManager.Get(f"score.{n}.phase"),
                "state": StateManager.Get(f"score.{n}.stage_strike", {}),
            }
        )

        # The score, and who already picked their characters for it on the
        # character select page (team numbers as in "teams")
        logic = self._strike_logic(n)
        data["score"] = logic.CurrentScore()
        data["character_lock"] = logic.CharacterLockState(data["score"])

        return data

    def _act(self, scoreboard, team, action):
        """Runs a stage strike action, recording which team's page did it."""
        logic = self._strike_logic(scoreboard)
        logic.actor = self._team_number(team)
        try:
            return action(logic)
        finally:
            logic.actor = None

    def stage_clicked(self, data, scoreboard=1, team=None):
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        stage = orjson.loads(data) if isinstance(data, (str, bytes)) else data
        self._act(scoreboard, team, lambda logic: logic.StageClicked(stage))
        return "OK"

    def confirm_clicked(self, scoreboard=1, team=None):
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        self._act(scoreboard, team, lambda logic: logic.ConfirmClicked())
        return "OK"

    def report_characters(self, data, scoreboard=1, team=None):
        """Characters picked on a stage strike page.

        data["characters"] is {team: {player: [[character, skin], ...]}}.
        A page for one team (team set) only sends its own, and they reach
        the scoreboard once the other team sent theirs.
        """
        logic = self._strike_logic(scoreboard)
        team = self._team_number(team)
        self._apply_characters(
            logic, logic.ReportCharacters(self._character_picks(data, team), team)
        )
        return "OK"

    def character_select_report(self, data, scoreboard=1, team=None):
        """Characters picked on the character select page. Like
        report_characters, but each team picks once per score: picking again
        is refused until the score changes."""
        logic = self._strike_logic(scoreboard)
        team = self._team_number(team)
        accepted, ready = logic.SelectCharacters(self._character_picks(data, team), team)
        if not accepted:
            return "ALREADY_PICKED", 409
        self._apply_characters(logic, ready)
        return "OK"

    def _character_picks(self, data, team):
        # A page for one team only sends its own
        picks = data.get("characters") or {}
        if team is not None:
            picks = {str(team): picks.get(str(team), picks.get(team)) or {}}
        return picks

    def _apply_characters(self, logic, ready):
        # Puts the picks on the scoreboard, once every team sent theirs
        if not ready:
            return
        game = StateManager.Get("game.codename")
        for t, players in ready.items():
            for p, characters in (players or {}).items():
                self.set_team_data(
                    logic.scoreboardNumber,
                    int(t),
                    int(p),
                    {"mains": {game: [list(c) for c in characters if c]}},
                )
        logic.ExportState()

    def rps_win(self, winner, scoreboard=1, team=None):
        self._act(scoreboard, team, lambda logic: logic.RpsResult(int(winner)))
        return "OK"

    def match_win(self, winner, scoreboard=1, team=None):
        """A game's winner. From a team's page, it waits for the other team
        to report the same winner (-1 takes the report back)."""
        team = self._team_number(team)
        applied = self._act(scoreboard, team, lambda logic: logic.ReportWinner(int(winner), team))
        if not applied:
            return "WAITING_FOR_OTHER_TEAM"
        # Web server updating score here
        self.UpdateScore(scoreboard)
        return "OK"

    def set_gentlemans(self, value, scoreboard=1, team=None):
        # It clears the game's strikes, so a team's page can't do it on the
        # other team's turn
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        self._act(scoreboard, team, lambda logic: logic.SetGentlemans(value))
        return "OK"

    def stage_strike_undo(self, scoreboard=1, team=None):
        logic = self._strike_logic(scoreboard)
        if not logic.CanUndo(self._team_number(team)):
            return "NOT_YOUR_ACTION", 409
        logic.Undo()
        self.UpdateScore(scoreboard)
        return "OK"

    def stage_strike_redo(self, scoreboard=1, team=None):
        logic = self._strike_logic(scoreboard)
        if not logic.CanRedo(self._team_number(team)):
            return "NOT_YOUR_ACTION", 409
        logic.Redo()
        self.UpdateScore(scoreboard)
        return "OK"

    def reset(self, scoreboard=1, team=None):
        # Restarting the whole set is left to the page for both teams
        if self._team_number(team) is not None:
            return "NOT_ALLOWED", 403
        n = self._scoreboard_number(scoreboard)
        self._strike_logic(n).Initialize()
        self.UpdateScore(n)
        self._get_scoreboard(n).gameReport.ResetAllStages()
        return "OK"

    # =====================================================
    # SCOREBOARD SCORE AND TEAMS
    # =====================================================
    def UpdateScore(self, scoreboard=1):
        if not SettingsManager.Get("general.control_score_from_stage_strike", True):
            return

        logic = self._strike_logic(scoreboard)
        score = [
            len(logic.CurrentState().stagesWon[0]),
            len(logic.CurrentState().stagesWon[1]),
        ]

        logger.info(f"We're supposed to update the score {score}")

        self._get_scoreboard(logic.scoreboardNumber).signals.ChangeSetData.emit(
            {
                "team1score": score[0],
                "team2score": score[1],
            }
        )

    def post_score(self, scoreboard, score):
        scoreboard = self._get_scoreboard(scoreboard)

        # Scores from the web API are in on-screen order (team 1 is the left
        # side), like the score up/down and color endpoints
        score["as_displayed"] = True
        scoreboard.signals.ChangeSetData.emit(score)
        return "OK"

    def team_scoreup(self, scoreboard, team):
        if str(team) == "1":
            self._get_scoreboard(scoreboard).CommandScoreChange(0, 1)
        else:
            self._get_scoreboard(scoreboard).CommandScoreChange(1, 1)
        return "OK"

    def team_scoredown(self, scoreboard, team):
        if str(team) == "1":
            self._get_scoreboard(scoreboard).CommandScoreChange(0, -1)
        else:
            self._get_scoreboard(scoreboard).CommandScoreChange(1, -1)
        return "OK"

    def team_color(self, scoreboard, team, color):
        if str(team) == "1":
            self._get_scoreboard(scoreboard).signals.CommandTeamColor.emit(0, color)
        else:
            self._get_scoreboard(scoreboard).signals.CommandTeamColor.emit(1, color)
        return "OK"

    def team_info(self, scoreboard, team, data):
        # data: {"name"?: str, "losers"?: bool, "color"?: "#rrggbb"}
        if str(team) not in ("1", "2") or not isinstance(data, dict):
            return "ERROR : team must be 1 or 2"
        self._get_scoreboard(scoreboard).CommandTeamInfo(int(team) - 1, data)
        return "OK"

    # =====================================================
    # CREW/TEAM BATTLE
    # =====================================================
    def _team_battle(self):
        widget = TeamBattleWidget.instance
        if widget is None:
            raise ScoreboardNotAvailable("Crew/Team Battle not available")
        return widget

    def _team_battle_team(self, team):
        team = self._team_number(team)
        if team is None:
            return None, ("ERROR : team must be 1 or 2", 400)
        return team, None

    def team_battle_scoreup(self, team):
        # Stock Pool: the other team's active player loses a stock
        # First To: the team's active player wins a game
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_stock_up if team == 1 else signals.team2_stock_up).emit()
        return "OK"

    def team_battle_scoredown(self, team):
        # Undoes team_battle_scoreup
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_stock_down if team == 1 else signals.team2_stock_down).emit()
        return "OK"

    def team_battle_next_player(self, team):
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_next_active_player if team == 1 else signals.team2_next_active_player).emit()
        return "OK"

    def team_battle_set_active(self, team, player):
        # player: the player's number in the team, from 1
        team, error = self._team_battle_team(team)
        if error:
            return error
        widget = self._team_battle()
        try:
            index = int(player) - 1
        except (TypeError, ValueError):
            index = -1
        if not 0 <= index < len(widget.Players(team)):
            return "ERROR : no such player", 400
        signals = widget.signals
        (signals.team1_set_active_player if team == 1 else signals.team2_set_active_player).emit(
            index
        )
        return "OK"

    def team_battle_reset_stocks(self):
        self._team_battle().signals.reset_all_stocks.emit()
        return "OK"

    def team_battle_reset(self):
        self._team_battle().signals.reset_everything.emit()
        return "OK"

    def get_team_battle(self):
        self._team_battle()
        return StateManager.Get("team_battle", {})

    # =====================================================
    # SCOREBOARD DATA
    # =====================================================
    def get_scoreboard(self, scoreboard):
        sb_widget: ScoreboardWidget = self._get_scoreboard(scoreboard)
        return StateManager.Get(f"score.{sb_widget.scoreboardNumber}")

    def set_route(
        self,
        scoreboard,
        bestOf=None,
        phase=None,
        match=None,
        players=None,
        characters=None,
        losers=None,
        team=None,
    ):
        # Best Of argument
        # best-of=<Best Of Amount>
        if bestOf is not None:
            self._get_scoreboard(scoreboard).signals.ChangeSetData.emit(
                orjson.loads(orjson.dumps({"bestOf": int(bestOf)}))
            )

        # Phase argument
        # phase=<Phase Name>
        if phase == "":
            self._clear_score_field(scoreboard, "phase")
        elif phase is not None:
            self._get_scoreboard(scoreboard).signals.ChangeSetData.emit(
                orjson.loads(orjson.dumps({"tournament_phase": phase}))
            )

        # Match argument
        # match=<Match Name>
        if match == "":
            self._clear_score_field(scoreboard, "match")
        elif match is not None:
            self._get_scoreboard(scoreboard).signals.ChangeSetData.emit(
                orjson.loads(orjson.dumps({"round_name": match}))
            )

        # Players argument
        # players=<Amount of Players>
        if players is not None:
            self._get_scoreboard(scoreboard).playerNumber.setValue(int(players))

        # Characters argument
        # characters=<Amount of Characters>
        if characters is not None:
            self._get_scoreboard(scoreboard).charNumber.setValue(int(characters))

        # Losers argument
        # losers=<True/False>&team=<Team Number>, as a bool here
        if losers is not None:
            self._get_scoreboard(scoreboard).signals.ChangeSetData.emit(
                orjson.loads(
                    orjson.dumps(
                        {
                            "team" + str(team) + "losers": bool(losers),
                            "as_displayed": True,
                        }
                    )
                )
            )
        return "OK"

    def _clear_score_field(self, scoreboard, name):
        # ChangeSetData ignores empty phase/match names, so clear them here
        field = self._get_scoreboard(scoreboard).scoreColumn.findChild(QComboBox, name)
        if field is not None:
            field.setCurrentText("")
            field.lineEdit().editingFinished.emit()

    def _resolve_character_name(self, name: str) -> str:
        """Resolve a character identifier to its en_name.
        Checks codename first, then en_name. Returns the input unchanged if no match."""
        characters = GameAssetManager.instance.characters
        for en_name, char_data in characters.items():
            if char_data.get("codename") == name:
                return en_name
        return name

    def _resolve_mains(self, mains):
        """Resolve character codenames to en_names in a mains structure."""
        if isinstance(mains, list):
            return [
                [self._resolve_character_name(entry[0])] + list(entry[1:]) if entry else entry
                for entry in mains
            ]
        if isinstance(mains, dict):
            return {
                game: [
                    [self._resolve_character_name(entry[0])] + list(entry[1:]) if entry else entry
                    for entry in entries
                ]
                for game, entries in mains.items()
            }
        return mains

    def set_team_data(self, scoreboard, team, player, data):
        if data and "mains" in data:
            data = {**data, "mains": self._resolve_mains(data["mains"])}
        sb = self._get_scoreboard(scoreboard)
        sb.signals.ChangeSetData.emit({"team": team, "player": player, "data": data})
        return "OK"

    def set_commentary_data(self, index, data):
        logger.info(self.commentaryWidget)
        index = int(index) - 1
        if index < 0:
            return "ERROR : index can't be lower than 1"
        self.commentaryWidget.ChangeCommDataSignal.emit(index, data)

        return "OK"

    # =====================================================
    # GAMES AND CHARACTERS
    # =====================================================
    def set_game(self, data):
        # Runs in a worker thread: the assets are loaded by the asset
        # manager's own thread, like when picking a game in the program. The
        # GUI thread only starts it.
        set_codename = data.get("codename")
        mods_active = data.get("mods_active", False)
        loader = run_on_gui_thread(lambda: self._start_game_load(set_codename, mods_active))
        if loader is None:
            return f"Could not find game {set_codename}"
        if not loader.wait(GAME_LOAD_TIMEOUT * 1000):
            return "LOADING", 202
        return "OK"

    def _start_game_load(self, codename, mods_active):
        """Starts loading a game's assets and returns the thread doing it, or
        None if there's no such game."""
        manager = GameAssetManager.instance
        games = list(manager.games.keys())
        if codename not in games:
            return None
        manager.LoadGameAssets(
            games.index(codename) + 1, mods_active=mods_active, mods_reload_mode=True
        )
        return manager.assetsLoaderThread

    def get_games(self):
        data = {}
        for key in GameAssetManager.instance.games.keys():
            data[key] = {
                "name": GameAssetManager.instance.games[key].get("name"),
                "locale": GameAssetManager.instance.games[key].get("locale"),
                "smashgg_game_id": GameAssetManager.instance.games[key].get("smashgg_game_id"),
                "igdb_game_id": GameAssetManager.instance.games[key].get("igdb_game_id"),
                "has_stages": bool(GameAssetManager.instance.games[key].get("stage_to_codename")),
                "has_variants": bool(
                    GameAssetManager.instance.games[key].get("variant_to_codename")
                ),
                "has_colors": bool(GameAssetManager.instance.games[key].get("preset_colors")),
            }

        return data

    def get_current_game(self):
        return StateManager.Get("game")

    def get_match_names(self):
        response = {"match": LocaleHelper.matchNames, "phase": LocaleHelper.phaseNames}
        return response

    def get_characters(self):
        data = {}
        for row in range(GameAssetManager.instance.characterModel.rowCount()):
            item: QStandardItem = GameAssetManager.instance.characterModel.index(row, 0)
            item_data = item.data(Qt.ItemDataRole.UserRole)

            if item_data is not None:
                skin_models = GameAssetManager.instance.skinModels.get(item_data.get("en_name"))
                item_data["skins"] = []
                if skin_models is not None:
                    for skindex in range(skin_models.rowCount()):
                        item_data["skins"].append(
                            skin_models.index(skindex, 0).data(Qt.ItemDataRole.UserRole)
                        )
                data[item_data.get("name")] = item_data

        return data

    def get_variants(self):
        data = {}
        for row in range(GameAssetManager.instance.variantModel.rowCount()):
            item: QStandardItem = GameAssetManager.instance.variantModel.index(row, 0)
            item_data = item.data(Qt.ItemDataRole.UserRole)

            if item_data is not None:
                data[item_data.get("name")] = item_data
        return data

    # =====================================================
    # SWAPPING AND LOADING SETS
    # =====================================================
    def swap_teams(self, scoreboard):
        sb = self._get_scoreboard(scoreboard)
        sb.signals.SwapTeams.emit()
        return "OK"

    def get_swap(self, scoreboard):
        sb = self._get_scoreboard(scoreboard)
        return str(sb.teamsSwapped)

    def open_sets(self, scoreboard):
        self._get_scoreboard(scoreboard).signals.SetSelection.emit()
        return "OK"

    def pull_stream_set(self, scoreboard):
        self._get_scoreboard(scoreboard).signals.StreamSetSelection.emit()
        return "OK"

    def load_set(self, scoreboard, set=None, no_mains=False):
        if no_mains is False:
            no_mains = SettingsManager.Get("general.force_no_mains_on_new_set_loads", False)
        if set is not None:
            if not isinstance(set, str):
                set = "0"
            self._get_scoreboard(scoreboard).signals.NewSetSelected.emit(
                orjson.loads(orjson.dumps({"id": set, "auto_update": "set", "no_mains": no_mains}))
            )
        return "OK"

    # =====================================================
    # PLAYER STATS
    # =====================================================
    def stats_recent_sets(self, scoreboard):
        self._get_scoreboard(scoreboard).stats.signals.RecentSetsSignal.emit()
        return "OK"

    def stats_upset_factor(self, scoreboard):
        self._get_scoreboard(scoreboard).stats.signals.UpsetFactorCalculation.emit()
        return "OK"

    def stats_last_sets(self, scoreboard, player):
        if str(player) == "1":
            self._get_scoreboard(scoreboard).stats.signals.LastSetsP1Signal.emit()
        elif str(player) == "2":
            self._get_scoreboard(scoreboard).stats.signals.LastSetsP2Signal.emit()
        elif player == "both":
            self._get_scoreboard(scoreboard).stats.signals.LastSetsP1Signal.emit()
            self._get_scoreboard(scoreboard).stats.signals.LastSetsP2Signal.emit()
        else:
            logger.error(
                "[Last Sets] Unable to find player defined. Allowed values are: 1, 2, or both"
            )
        return "OK"

    def stats_history_sets(self, scoreboard, player):
        if str(player) == "1":
            self._get_scoreboard(scoreboard).stats.signals.PlayerHistoryStandingsP1Signal.emit()
        elif str(player) == "2":
            self._get_scoreboard(scoreboard).stats.signals.PlayerHistoryStandingsP2Signal.emit()
        elif player == "both":
            self._get_scoreboard(scoreboard).stats.signals.PlayerHistoryStandingsP1Signal.emit()
            self._get_scoreboard(scoreboard).stats.signals.PlayerHistoryStandingsP2Signal.emit()
        else:
            logger.error(
                "[History Standings] Unable to find player defined. Allowed values are: 1, 2, or both"
            )
        return "OK"

    def stats_refresh(self, scoreboard):
        """Gets all of the scoreboard's player stats again: the head-to-head,
        each player's last sets and past events, and the upset factor"""
        signals = self._get_scoreboard(scoreboard).stats.signals
        signals.RecentSetsSignal.emit()
        signals.LastSetsP1Signal.emit()
        signals.LastSetsP2Signal.emit()
        signals.PlayerHistoryStandingsP1Signal.emit()
        signals.PlayerHistoryStandingsP2Signal.emit()
        signals.UpsetFactorCalculation.emit()
        return "OK"

    def commentary_preview(self, data):
        """The players of a set that isn't on a scoreboard, for the commentary
        dashboard: {"teams": [[player...], [player...]]}"""
        return CommentaryPreview.Preview((data or {}).get("teams"))

    # =====================================================
    # RESETTING
    # =====================================================
    def reset_scores(self, scoreboard):
        self._get_scoreboard(scoreboard).ResetScore()
        return "OK"

    def reset_match(self, scoreboard):
        self._get_scoreboard(scoreboard).ClearScore()
        self._get_scoreboard(scoreboard).scoreColumn.findChild(QSpinBox, "best_of").setValue(0)
        return "OK"

    def reset_players(self, scoreboard):
        self._get_scoreboard(scoreboard).CommandClearAll()
        return "OK"

    def clear_all(self, scoreboard):
        self._get_scoreboard(scoreboard).ClearScore()
        self._get_scoreboard(scoreboard).scoreColumn.findChild(QSpinBox, "best_of").setValue(0)
        self._get_scoreboard(scoreboard).playerNumber.setValue(1)
        self._get_scoreboard(scoreboard).charNumber.setValue(1)
        self._get_scoreboard(scoreboard).CommandClearAll()
        return "OK"

    # =====================================================
    # SETS AND COMMENTATORS
    # =====================================================
    def get_sets(self, finished=False):
        provider = TournamentDataManager.instance.GetProvider()
        if provider is None:
            return []
        return provider.GetMatches(getFinished=bool(finished))

    def get_set(self, scoreboard):
        if self._get_scoreboard(scoreboard).lastSetSelected is None:
            return "0"
        else:
            return str(self._get_scoreboard(scoreboard).lastSetSelected)

    def get_match(self, setId=None):
        provider = TournamentDataManager.instance.GetProvider()
        return provider.GetMatch(setId=int(setId))

    def get_comms(self):
        return StateManager.Get("commentary")

    # =====================================================
    # PLAYER DATABASE
    # =====================================================
    def get_playerdb(self):
        return PlayerDB.database

    # =====================================================
    # BRACKET
    # =====================================================
    def update_bracket(self):
        # Runs in a worker thread: the provider's requests take a while. Only
        # showing the result (_show_phase_group) is done on the GUI thread.
        phase_name = StateManager.Get("bracket.phase")
        group_name = StateManager.Get("bracket.phaseGroup")
        provider = TournamentDataManager.instance.provider

        if phase_name == None or phase_name == "":
            group = provider.GetTournamentPhases()[0].get("groups")[
                0
            ]  # retaining old functionality just in case someone needs it
            data = self._fetch_phase_group(provider, group)
            run_on_gui_thread(lambda: self._show_phase_group(data, group))
            return "OK"

        # The main channel's phase, when it's one of start.gg's
        selected_phase = None
        for phase in provider.GetTournamentPhases():
            if phase.get("name") == phase_name:
                selected_phase = phase
                break
        if selected_phase is None:
            return "NO_PHASE_GROUP"

        groups = selected_phase.get("groups") or []
        selected_group = None
        if len(groups) == 1:
            selected_group = groups[
                0
            ]  # oddly enough phases with only one group can end up with '' as the phase group
        else:
            for group in groups:
                if group.get("name") == group_name:
                    selected_group = group
                    break
        if selected_group is None:
            return "NO_PHASE_GROUP"

        data = self._fetch_phase_group(provider, selected_group)
        run_on_gui_thread(lambda: self._show_phase_group(data, selected_group, selected_phase))
        return "OK"

    def _fetch_phase_group(self, provider, group):
        phase_group_id = group.get("id")
        data = provider.GetTournamentPhaseGroup(phase_group_id)
        if data:
            # So the bracket widget knows which phase group (its names and
            # bracket type, e.g. round robin) it's loading
            data["phaseGroupId"] = phase_group_id
        return data

    def _show_phase_group(self, data, group, phase=None):
        if data and BracketWidget.instance is not None:
            groups = (phase or {}).get("groups") or []
            BracketWidget.instance.phaseGroupInfo[str(group.get("id"))] = {
                "phase": (phase or {}).get("name") or "",
                "group": (group.get("name") or "") if len(groups) > 1 else "",
                "bracketType": group.get("bracketType"),
            }
        TournamentDataManager.instance.signals.tournament_phasegroup_updated.emit(data)

    def update_bracket_sets(self):
        # Only the set results of the bracket loaded in the bracket widget,
        # without reloading its players. The sets are fetched in the
        # background, so this returns once the update has started.
        if BracketWidget.instance is None:
            return "NO_BRACKET"
        return BracketWidget.instance.RefreshSets()

    # =====================================================
    # STREAM QUEUE
    # =====================================================
    def stream_queue(self):
        return StateManager.Get("stream_queue") or {}

    def stream_queue_refresh(self):
        from .StreamQueueWidget import StreamQueueWidget

        if StreamQueueWidget.instance is None:
            return "NO_STREAM_QUEUE", 404
        StreamQueueWidget.instance.Refresh()
        return "OK"

    def stream_queue_load_next(self, stream=None, scoreboard=None):
        # Loads the next set of a stream's queue into its scoreboard, by
        # stream name or by scoreboard number
        from .StreamQueueWidget import StreamQueueWidget

        widget = StreamQueueWidget.instance
        if widget is None:
            return "NO_STREAM_QUEUE", 404
        if stream:
            config = widget.model.GetStream(stream)
        else:
            config = widget.model.StreamOfScoreboard(scoreboard or 1)
        if config is None:
            return "NO_STREAM", 404
        if config.scoreboard is None:
            return "NO_SCOREBOARD", 409
        widget.LoadNext(config.name)
        return "OK"

    # =====================================================
    # BRACKET FOCUS
    # =====================================================
    def bracket_focus(self, channel=None):
        # A focus channel's state, "main" by default
        from .BracketFocus import BracketFocus

        focus = BracketFocus.instance
        if focus is None:
            return "NO_BRACKET", 404
        if focus.Channel(channel or "main") is None:
            return "NO_CHANNEL", 404
        return focus.State(channel or "main")

    def bracket_focus_set(self, request, channel=None):
        # A focus request, {"move": 1} for the next round (-1: previous) or
        # {"phase": <id>} for the phase of the bracket widget it shows, for
        # a channel ("channel" in the request, "main" by default)
        from .BracketFocus import BracketFocus

        focus = BracketFocus.instance
        if focus is None:
            return "NO_BRACKET", 404
        request = request if isinstance(request, dict) else {}
        channel = channel or request.get("channel") or "main"
        target = focus.Channel(channel)
        if target is None:
            return "NO_CHANNEL", 404
        if "phase" in request:
            if not focus.HasPhase(request.get("phase")):
                return "NO_PHASE", 404
            target.SetPhase(request.get("phase"))
        elif "move" in request:
            try:
                target.MoveRound(1 if int(request.get("move")) >= 0 else -1)
            except (TypeError, ValueError):
                return "BAD_MOVE", 400
        else:
            target.Set(request)
        return focus.State(target.name)

    # =====================================================
    # DISPLAY CONTROLS
    # =====================================================
    # Display Controls: kind is "folder", "group" or "all", action "show",
    # "hide", "toggle" or None to only answer whether it's shown
    def display(self, kind, name=None, action=None):
        from .DisplayControls import DisplayControls

        controls = DisplayControls.instance
        if controls is None:
            return "NO_DISPLAY_CONTROLS", 503
        if kind == "all":
            if action is None:
                return {"kind": "all", "shown": controls.AllShown(), **controls.State()}
            result = controls.SetAll(action)
        elif action is None:
            result = controls.Get(kind, name)
        else:
            result = controls.Set(kind, name, action)
        error = result.get("error")
        if error:
            return error, 400 if error in ("UNKNOWN_ACTION", "UNKNOWN_KIND") else 404
        return result

    def display_state(self):
        return self.display("all")

    def display_all(self, action):
        return self.display("all", None, action)

    def display_register(self, groups):
        from .DisplayControls import DisplayControls

        if DisplayControls.instance is not None and isinstance(groups, list):
            DisplayControls.instance.AddGroups(groups)

    # =====================================================
    # LOADING PLAYERS FROM TAGS
    # =====================================================
    def load_player_from_tag(self, scoreboard, tag, team, player, no_mains=False):
        if tag is None:
            return "No tag provided"
        result = self._get_scoreboard(scoreboard).LoadPlayerFromTag(
            str(tag), int(team), int(player), no_mains
        )
        if result == True:
            return "OK"
        else:
            return "ERROR"

    def load_commentator_from_tag(self, index, tag, no_mains=False):
        if tag is None:
            return "No tag provided"
        index = int(index) - 1
        if index < 0:
            return "ERROR : index can't be lower than 1"
        self.commentaryWidget.LoadCommFromTagSignal.emit(index, tag, no_mains)
        return "OK"

    # =====================================================
    # TOURNAMENT
    # =====================================================
    def load_tournament(self, url=None):
        logger.error(f"URL PROVIDED: {url}")
        if url is None or url == "":
            TournamentDataManager.instance.signals.tournament_url_update.emit(None)
            return "OK"
        else:
            parsed = ParseTournamentInput(url)
            if parsed and parsed["kind"] == "tournament":
                return "ERROR: This is a tournament, not an event. Get its events from /tournament-events and load one of their URLs"

            url = NormalizeEventURL(url)

            SettingsManager.Set("TOURNAMENT_URL", url)
            TournamentDataManager.instance.signals.tournament_url_update.emit(url)

            return "OK"

    def get_tournament_events(self, url=None):
        # Lists a tournament's events, so a client can pick one for load_tournament
        parsed = ParseTournamentInput(url)
        if parsed is None:
            return {"error": "invalid_url", "message": "Not a tournament or event URL"}
        if parsed["kind"] == "event":
            return {
                "error": "is_event",
                "message": "This is already an event URL; load it with /set-tournament",
                "url": parsed["url"],
            }
        try:
            return FetchTournamentEvents(parsed, SettingsManager.Get("api_keys.parrygg"))
        except TournamentLookupError as e:
            return {"error": e.code, "message": str(e)}

    # =====================================================
    # STATES AND STAGES
    # =====================================================
    def get_states(self, countryCode: str):
        if not countryCode:
            return "countryCode not specified", 400
        return CountryHelper.GetStates(countryCode)

    def set_current_stage(self, scoreboard, codename):
        sb = self._get_scoreboard(scoreboard)
        number = sb.scoreboardNumber
        stage_data = StateManager.Get(f"game.stages.{codename}") if codename else None
        with StateManager.SaveBlock():
            StateManager.Set(f"score.{number}.stage_strike.selectedStage", codename)
            StateManager.Set(f"score.{number}.stage_strike.selectedStageData", stage_data)
        curr_game = sb.gameReport.CurrentGameIndex()
        if curr_game < 0:
            curr_game = 0
        sb.gameReport.SetStage(curr_game, codename)
        return "OK"
