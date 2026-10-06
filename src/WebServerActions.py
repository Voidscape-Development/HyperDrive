import logging
import os

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .BracketWidget import BracketWidget
from .CommentaryWidget import CommentaryWidget
from .GameAssetManager import GameAssetManager
from .Helpers.CountryHelper import CountryHelper
from .Helpers.LocaleHelper import LocaleHelper
from .Helpers.QtHelper import gui_thread_sync
from .PlayerDB import PlayerDB
from .ScoreboardWidget import ScoreboardWidget
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .StatsUtil import StatsUtil
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


class ScoreboardNotAvailable(Exception):
    """Raised when a scoreboard is requested but not yet initialized."""

    pass


class WebServerActions(QThread):
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
        self.threadPool = QThreadPool()

    def _get_scoreboard(self, number=1):
        """Get a scoreboard by number, raising ScoreboardNotAvailable if it doesn't exist."""
        sb = self.scoreboard.GetScoreboard(number)
        if sb is None:
            raise ScoreboardNotAvailable(f"Scoreboard {number} not available")
        return sb

    def program_state(self):
        return {"state": StateManager.state, "delta_index": StateManager.deltaIndex}

    def _scoreboard_number(self, number):
        """A scoreboard number for stage striking, raising ScoreboardNotAvailable if it doesn't exist."""
        try:
            number = int(number) if number not in (None, "") else 1
        except TypeError, ValueError:
            raise ScoreboardNotAvailable(f"Invalid scoreboard {number}")
        if number < 1 or number > self.scoreboard.GetTabAmount():
            raise ScoreboardNotAvailable(f"Scoreboard {number} not available")
        return number

    def _strike_logic(self, scoreboard):
        return self.stageWidget.GetLogic(self._scoreboard_number(scoreboard))

    def _team_number(self, team):
        """HyperDrive's team number (1 or 2) a stage strike page is for, or None for both."""
        try:
            team = int(team) if team not in (None, "") else None
        except TypeError, ValueError:
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

    @gui_thread_sync
    def ruleset(self, scoreboard=1):
        data = {}

        # Add webserver base path
        data.update({"basedir": os.path.abspath(".")})

        if self.scoreboard.GetTabAmount() < 1:
            data["ruleset"] = StateManager.Get("score.ruleset", {})
            return data

        try:
            n = self._scoreboard_number(scoreboard)
        except ScoreboardNotAvailable:
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

    @gui_thread_sync
    def stage_clicked(self, data, scoreboard=1, team=None):
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        stage = orjson.loads(data) if isinstance(data, (str, bytes)) else data
        self._act(scoreboard, team, lambda logic: logic.StageClicked(stage))
        return "OK"

    @gui_thread_sync
    def confirm_clicked(self, scoreboard=1, team=None):
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        self._act(scoreboard, team, lambda logic: logic.ConfirmClicked())
        return "OK"

    @gui_thread_sync
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

    @gui_thread_sync
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

    @gui_thread_sync
    def rps_win(self, winner, scoreboard=1, team=None):
        self._act(scoreboard, team, lambda logic: logic.RpsResult(int(winner)))
        return "OK"

    @gui_thread_sync
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

    @gui_thread_sync
    def set_gentlemans(self, value, scoreboard=1, team=None):
        # It clears the game's strikes, so a team's page can't do it on the
        # other team's turn
        if self._not_your_turn(scoreboard, team):
            return "NOT_YOUR_TURN", 409
        self._act(scoreboard, team, lambda logic: logic.SetGentlemans(value))
        return "OK"

    @gui_thread_sync
    def stage_strike_undo(self, scoreboard=1, team=None):
        logic = self._strike_logic(scoreboard)
        if not logic.CanUndo(self._team_number(team)):
            return "NOT_YOUR_ACTION", 409
        logic.Undo()
        self.UpdateScore(scoreboard)
        return "OK"

    @gui_thread_sync
    def stage_strike_redo(self, scoreboard=1, team=None):
        logic = self._strike_logic(scoreboard)
        if not logic.CanRedo(self._team_number(team)):
            return "NOT_YOUR_ACTION", 409
        logic.Redo()
        self.UpdateScore(scoreboard)
        return "OK"

    @gui_thread_sync
    def reset(self, scoreboard=1, team=None):
        # Restarting the whole set is left to the page for both teams
        if self._team_number(team) is not None:
            return "NOT_ALLOWED", 403
        n = self._scoreboard_number(scoreboard)
        self._strike_logic(n).Initialize()
        self.UpdateScore(n)
        self._get_scoreboard(n).gameReport.ResetAllStages()
        return "OK"

    @gui_thread_sync
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

    @gui_thread_sync
    def post_score(self, data):
        score = orjson.loads(data)
        scoreboard_number = 1

        if "scoreboard" in score:
            try:
                scoreboard_number = int(score["scoreboard"])
            except ValueError:
                logger.warning(
                    f"Couldn't parse scoreboard [${score['scoreboard']}] from /post_data as int, falling back to scoreboard 1"
                )
                scoreboard_number = 1

        # Scores from the web API are in on-screen order (team 1 is the left
        # side), like the score up/down and color endpoints
        score["as_displayed"] = True
        self._get_scoreboard(scoreboard_number).signals.ChangeSetData.emit(score)
        return "OK"

    @gui_thread_sync
    def team_scoreup(self, scoreboard, team):
        if str(team) == "1":
            self._get_scoreboard(scoreboard).CommandScoreChange(0, 1)
        else:
            self._get_scoreboard(scoreboard).CommandScoreChange(1, 1)
        return "OK"

    @gui_thread_sync
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

    @gui_thread_sync
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

    @gui_thread_sync
    def team_battle_scoreup(self, team):
        # Stock Pool: the other team's active player loses a stock
        # First To: the team's active player wins a game
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_stock_up if team == 1 else signals.team2_stock_up).emit()
        return "OK"

    @gui_thread_sync
    def team_battle_scoredown(self, team):
        # Undoes team_battle_scoreup
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_stock_down if team == 1 else signals.team2_stock_down).emit()
        return "OK"

    @gui_thread_sync
    def team_battle_next_player(self, team):
        team, error = self._team_battle_team(team)
        if error:
            return error
        signals = self._team_battle().signals
        (signals.team1_next_active_player if team == 1 else signals.team2_next_active_player).emit()
        return "OK"

    @gui_thread_sync
    def team_battle_set_active(self, team, player):
        # player: the player's number in the team, from 1
        team, error = self._team_battle_team(team)
        if error:
            return error
        widget = self._team_battle()
        try:
            index = int(player) - 1
        except TypeError, ValueError:
            index = -1
        if not 0 <= index < len(widget.Players(team)):
            return "ERROR : no such player", 400
        signals = widget.signals
        (signals.team1_set_active_player if team == 1 else signals.team2_set_active_player).emit(
            index
        )
        return "OK"

    @gui_thread_sync
    def team_battle_reset_stocks(self):
        self._team_battle().signals.reset_all_stocks.emit()
        return "OK"

    @gui_thread_sync
    def team_battle_reset(self):
        self._team_battle().signals.reset_everything.emit()
        return "OK"

    def get_team_battle(self):
        self._team_battle()
        return StateManager.Get("team_battle", {})

    def get_scoreboard(self, scoreboard):
        sb_widget: ScoreboardWidget = self._get_scoreboard(scoreboard)
        return StateManager.Get(f"score.{sb_widget.scoreboardNumber}")

    @gui_thread_sync
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
        # losers=<True/False>&team=<Team Number>
        if losers is not None:
            self._get_scoreboard(scoreboard).signals.ChangeSetData.emit(
                orjson.loads(
                    orjson.dumps(
                        {
                            "team" + str(team) + "losers": False
                            if losers.lower() == "false"
                            else True,
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

    @gui_thread_sync
    def set_game(self, data):
        # Not actually sure if this needs to be in the GUI thread but the asset manager is complex enough that it seems
        # worthwhile to dispatch it like this.
        set_codename = data.get("codename")
        found_game = False
        for i, codename in enumerate(GameAssetManager.instance.games.keys()):
            if codename == set_codename:
                # GameAssetManager.instance.selectedGame = GameAssetManager.instance.games[codename]
                # self.parent().SetGame()
                GameAssetManager.instance.LoadGameAssets(
                    i + 1,
                    async_mode=False,
                    mods_active=data.get("mods_active", False),
                    mods_reload_mode=True,
                )
                found_game = True
                break

        if not found_game:
            return f"Could not find game {set_codename}"

        return "OK"

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

    @gui_thread_sync
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

    @gui_thread_sync
    def get_variants(self):
        data = {}
        for row in range(GameAssetManager.instance.variantModel.rowCount()):
            item: QStandardItem = GameAssetManager.instance.variantModel.index(row, 0)
            item_data = item.data(Qt.ItemDataRole.UserRole)

            if item_data is not None:
                data[item_data.get("name")] = item_data
        return data

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

    def stats_recent_sets(self, scoreboard):
        StatsUtil.instance.signals.RecentSetsSignal.emit()
        return "OK"

    def stats_upset_factor(self, scoreboard):
        StatsUtil.instance.signals.UpsetFactorCalculation.emit()
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

    @gui_thread_sync
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

    @gui_thread_sync
    def reset_scores(self, scoreboard):
        self._get_scoreboard(scoreboard).ResetScore()
        return "OK"

    @gui_thread_sync
    def reset_match(self, scoreboard):
        self._get_scoreboard(scoreboard).ClearScore()
        self._get_scoreboard(scoreboard).scoreColumn.findChild(QSpinBox, "best_of").setValue(0)
        return "OK"

    @gui_thread_sync
    def reset_players(self, scoreboard):
        self._get_scoreboard(scoreboard).CommandClearAll()
        return "OK"

    @gui_thread_sync
    def clear_all(self, scoreboard):
        self._get_scoreboard(scoreboard).ClearScore()
        self._get_scoreboard(scoreboard).scoreColumn.findChild(QSpinBox, "best_of").setValue(0)
        self._get_scoreboard(scoreboard).playerNumber.setValue(1)
        self._get_scoreboard(scoreboard).charNumber.setValue(1)
        self._get_scoreboard(scoreboard).CommandClearAll()
        return "OK"

    @gui_thread_sync
    def update_bracket(self):
        phase_name = StateManager.Get("bracket.phase")
        group_name = StateManager.Get("bracket.phaseGroup")

        if phase_name == None or phase_name == "":
            group = TournamentDataManager.instance.provider.GetTournamentPhases()[0].get("groups")[
                0
            ]  # retaining old functionality just in case someone needs it
            data = self._fetch_phase_group(group)
            TournamentDataManager.instance.signals.tournament_phasegroup_updated.emit(data)
            return "OK"

        for phase in TournamentDataManager.instance.provider.GetTournamentPhases():
            if phase.get("name") == phase_name:
                selected_phase = phase
                break

        groups = selected_phase.get("groups")
        if len(groups) == 1:
            selected_group = groups[
                0
            ]  # oddly enough phases with only one group can end up with '' as the phase group
        else:
            for group in groups:
                if group.get("name") == group_name:
                    selected_group = group
                    break

        data = self._fetch_phase_group(selected_group)
        TournamentDataManager.instance.signals.tournament_phasegroup_updated.emit(data)
        return "OK"

    def _fetch_phase_group(self, group):
        phase_group_id = group.get("id")
        data = TournamentDataManager.instance.provider.GetTournamentPhaseGroup(phase_group_id)
        if data:
            # So the bracket widget knows which phase group (and bracket
            # type, e.g. round robin) it's loading
            data["phaseGroupId"] = phase_group_id
            if BracketWidget.instance is not None:
                BracketWidget.instance.phaseGroupTypes[str(phase_group_id)] = group.get(
                    "bracketType"
                )
        return data

    @gui_thread_sync
    def stream_queue(self):
        return StateManager.Get("stream_queue") or {}

    @gui_thread_sync
    def stream_queue_refresh(self):
        from .StreamQueueWidget import StreamQueueWidget

        if StreamQueueWidget.instance is None:
            return "NO_STREAM_QUEUE", 404
        StreamQueueWidget.instance.Refresh()
        return "OK"

    @gui_thread_sync
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

    @gui_thread_sync
    def update_bracket_sets(self):
        # Only the set results of the bracket loaded in the bracket widget,
        # without reloading its players. The sets are fetched in the
        # background, so this returns once the update has started.
        if BracketWidget.instance is None:
            return "NO_BRACKET"
        return BracketWidget.instance.RefreshSets()

    @gui_thread_sync
    def bracket_focus(self, channel=None):
        # A focus channel's state, "main" by default
        from .BracketFocus import BracketFocus

        focus = BracketFocus.instance
        if focus is None:
            return "NO_BRACKET", 404
        if focus.Channel(channel or "main") is None:
            return "NO_CHANNEL", 404
        return focus.State(channel or "main")

    @gui_thread_sync
    def bracket_focus_set(self, request, channel=None):
        # A focus request, or {"move": 1} for the next round (-1: previous),
        # for a channel ("channel" in the request, "main" by default)
        from .BracketFocus import BracketFocus

        focus = BracketFocus.instance
        if focus is None:
            return "NO_BRACKET", 404
        request = request if isinstance(request, dict) else {}
        channel = channel or request.get("channel") or "main"
        target = focus.Channel(channel)
        if target is None:
            return "NO_CHANNEL", 404
        if "move" in request:
            try:
                target.MoveRound(1 if int(request.get("move")) >= 0 else -1)
            except TypeError, ValueError:
                return "BAD_MOVE", 400
        else:
            target.Set(request)
        return focus.State(target.name)

    @gui_thread_sync
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

    def get_comms(self):
        return StateManager.Get("commentary")

    def get_set(self, scoreboard):
        if self._get_scoreboard(scoreboard).lastSetSelected is None:
            return "0"
        else:
            return str(self._get_scoreboard(scoreboard).lastSetSelected)

    def get_sets(self, args):
        provider = TournamentDataManager.instance.GetProvider()
        if provider is None:
            return []

        if args.get("getFinished") is not None:
            sets = provider.GetMatches(getFinished=True)
            return sets
        else:
            sets = provider.GetMatches(getFinished=False)
            return sets

    def get_playerdb(self):
        return PlayerDB.database

    def get_match(self, setId=None):
        provider = TournamentDataManager.instance.GetProvider()
        return provider.GetMatch(setId=int(setId))

    @gui_thread_sync
    def load_player_from_tag(self, scoreboard, tag, team, player, no_mains=False):
        result = self._get_scoreboard(scoreboard).LoadPlayerFromTag(
            str(tag), int(team), int(player), no_mains
        )
        if result == True:
            return "OK"
        else:
            return "ERROR"

    def load_commentator_from_tag(self, index, tag, no_mains=False):
        index = int(index) - 1
        if index < 0:
            return "ERROR : index can't be lower than 1"
        result = self.commentaryWidget.LoadCommFromTagSignal.emit(index, tag, no_mains)

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

    @gui_thread_sync
    def get_states(self, countryCode: str):
        return CountryHelper.GetStates(countryCode)

    @gui_thread_sync
    def set_current_stage(self, scoreboard, codename):
        stage_data = StateManager.Get(f"game.stages.{codename}") if codename else None
        with StateManager.SaveBlock():
            StateManager.Set(f"score.{scoreboard}.stage_strike.selectedStage", codename)
            StateManager.Set(f"score.{scoreboard}.stage_strike.selectedStageData", stage_data)
        sb = self._get_scoreboard(scoreboard)
        curr_game = sb.gameReport.CurrentGameIndex()
        if curr_game < 0:
            curr_game = 0
        sb.gameReport.SetStage(curr_game, codename)
        return "OK"
