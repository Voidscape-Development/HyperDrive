from copy import deepcopy

from loguru import logger
from qtpy.QtCore import QObject, Signal

from .ScoreboardManager import ScoreboardManager
from .StateManager import StateManager


class StageStrikeStateSignals(QObject):
    state_updated = Signal()


class StageStrikeState:
    def __init__(self) -> None:
        self.currGame = 0
        self.currPlayer = -1
        self.currStep = 0
        self.strikedStages = [[]]
        self.strikedBy = [[], []]
        self.stagesWon = [[], []]
        self.stagesPicked = []
        self.selectedStage = None
        self.lastWinner = -1
        self.playerNames = []
        self.phase = None
        self.match = None
        self.bestOf = None
        self.timestamp = 0
        self.serverTimestamp = 0
        self.gentlemans = False
        # HyperDrive team number (1 or 2) of the page whose action made this
        # state, None for HyperDrive itself or a page for both teams
        self.actor = None

    def Clone(self):
        clone = StageStrikeState()
        clone.__dict__ = deepcopy(self.__dict__)
        return clone


class StageStrikeLogic:
    def __init__(self, scoreboardNumber=1) -> None:
        # Each scoreboard strikes on its own
        self.scoreboardNumber = int(scoreboardNumber)
        self.ruleset = None
        self.history: list(StageStrikeState) = [StageStrikeState()]
        self.historyIndex = 0
        self.signals = StageStrikeStateSignals()
        # Characters picked for the next game, applied to the scoreboard
        # once both teams sent theirs, so neither sees the other's first.
        # {"game": currGame it's for, "teams": {1: picks or None, 2: ...}}
        # Kept out of the history, as undoing can't take back a pick
        self.characterSelect = None
        # Team acting right now, stamped on the states it makes so a team's
        # page can only undo its own actions. Set by the web server.
        self.actor = None
        # A game result reported by one team's page, waiting for the other
        # team to confirm it: {"winner": 0 or 1, "team": 1 or 2}
        self.pendingWinner = None
        # Characters picked on the character select page, where each team
        # picks once per score: {"score": [team 1, team 2], "teams": {1:
        # picked, 2: picked}}. A new score lets them pick again.
        self.characterLock = None

    def AddHistory(self, state, justOverwrite=False):
        self.history = self.history[: self.historyIndex + 1]
        state.actor = self.actor
        # Anything happening drops an unconfirmed result
        self.pendingWinner = None

        if justOverwrite:
            self.history[self.historyIndex] = state
        else:
            self.history.append(state)
            self.historyIndex += 1

        if len(self.history) > 10:
            self.history.pop(0)
            self.historyIndex -= 1

        self.ExportState()

    def CanUndo(self, team=None):
        # A team's page can only undo what that team did
        if self.historyIndex <= 0:
            return False
        return team is None or getattr(self.CurrentState(), "actor", None) == team

    def CanRedo(self, team=None):
        if self.historyIndex >= len(self.history) - 1:
            return False
        return team is None or getattr(self.history[self.historyIndex + 1], "actor", None) == team

    def Undo(self):
        self.pendingWinner = None
        self.historyIndex -= 1
        if self.historyIndex < 0:
            self.historyIndex = 0
        self.ExportState()

    def Redo(self):
        self.pendingWinner = None
        self.historyIndex += 1
        if self.historyIndex > len(self.history) - 1:
            self.historyIndex = len(self.history) - 1
        self.ExportState()

    def ExportState(self):
        # Undoing the game result also undoes asking for characters
        if (
            self.characterSelect is not None
            and self.characterSelect["game"] > self.CurrentState().currGame
        ):
            self.characterSelect = None
        if not self.CurrentState().selectedStage:
            self.pendingWinner = None
        nextState = (
            self.history[self.historyIndex + 1]
            if self.historyIndex < len(self.history) - 1
            else None
        )

        codename = self.CurrentState().selectedStage
        stage_data = StateManager.Get(f"game.stages.{codename}") if codename else None

        StateManager.Set(
            f"score.{self.scoreboardNumber}.stage_strike",
            {
                "currGame": self.CurrentState().currGame,
                "currPlayer": self.CurrentState().currPlayer,
                "currStep": self.CurrentState().currStep,
                "strikedStages": self.CurrentState().strikedStages,
                "strikedBy": self.CurrentState().strikedBy,
                "stagesWon": self.CurrentState().stagesWon,
                "stagesPicked": self.CurrentState().stagesPicked,
                "selectedStage": codename,
                "selectedStageData": stage_data,
                "lastWinner": self.CurrentState().lastWinner,
                "gentlemans": self.CurrentState().gentlemans,
                "characterSelect": self.GetCharacterSelectState(),
                "characterLock": self.CharacterLockState(self.CurrentScore()),
                "pendingWinner": self.pendingWinner,
                # Teams whose pages may undo / redo, None for HyperDrive or both teams
                "lastActor": getattr(self.CurrentState(), "actor", None),
                "nextActor": getattr(nextState, "actor", None) if nextState else None,
                "canUndo": self.historyIndex > 0,
                "canRedo": self.historyIndex < len(self.history) - 1,
            },
        )
        self.signals.state_updated.emit()

        if len(self.history) > 1:
            try:
                last_known_state = self.history[-1]
                if self.scoreboardNumber > len(ScoreboardManager.instance.scoreboardholder):
                    raise IndexError()
                sb_widget = ScoreboardManager.instance.GetScoreboard(self.scoreboardNumber)
                # stagesPicked holds the stage of each game played so far
                for i, stage in enumerate(last_known_state.stagesPicked):
                    sb_widget.gameReport.SetStage(i, stage)
                # Also update the current game's slot with the selected stage
                if last_known_state.selectedStage:
                    sb_widget.gameReport.SetStage(
                        last_known_state.currGame, last_known_state.selectedStage
                    )
            except IndexError as e:
                logger.warning(
                    f"Could not find scoreboard {self.scoreboardNumber} when piloting the stage history!"
                )

    def SetRuleset(self, ruleset):
        self.ruleset = ruleset
        self.Initialize()

    def Initialize(self, resetStreamScore=False):
        logger.info(f"Stage Strike Logic Initialize (scoreboard {self.scoreboardNumber})")
        self.characterSelect = None
        self.AddHistory(StageStrikeState())
        self.ExportState()

    def CurrentState(self) -> StageStrikeState:
        return self.history[self.historyIndex]

    def RpsResult(self, player):
        # Only decides who starts. Once someone's striking, a late or second
        # report (e.g. both teams' pages tapping at once) would switch the
        # player in the middle of their strikes.
        if self.CurrentState().currPlayer != -1:
            logger.info("RPS already decided, ignoring")
            return
        logger.info("RPS won by " + str(player + 1))
        newState = self.CurrentState().Clone()
        newState.lastWinner = player
        newState.currPlayer = player
        self.AddHistory(newState)

    def IsStageStriked(self, stage, previously=False):
        for i in range(len(self.CurrentState().strikedStages)):
            if i == len(self.CurrentState().strikedStages) - 1 and previously:
                continue
            round = self.CurrentState().strikedStages[i]
            if stage in round:
                return True
        return False

    def GetBannedStages(self):
        banList = []

        if self.ruleset.useDSR:
            banList = self.CurrentState().stagesPicked
        elif self.ruleset.useMDSR and self.CurrentState().lastWinner != -1:
            banList = self.CurrentState().stagesWon[(self.CurrentState().lastWinner + 1) % 2]

        return banList

    def IsStageBanned(self, stage):
        banList = self.GetBannedStages()

        found = next((i for i, e in enumerate(banList) if e == stage), None)
        if found != None:
            return True
        return False

    def GetStrikeNumber(self):
        # For game 1, follow strike order (1, 2, 1...)
        if self.CurrentState().currGame == 0:
            strikeOrder = self.ruleset.strikeOrder or []
            if self.CurrentState().currStep >= len(strikeOrder):
                # Game 1's strikes are done
                return 0
            return strikeOrder[self.CurrentState().currStep]
        # For other games
        else:
            # Fixed ban count
            if self.ruleset.banCount != 0:
                return self.ruleset.banCount
            # Ban by max games
            elif self.ruleset.banByMaxGames and str(self.GetBestOf()) in self.ruleset.banByMaxGames:
                return self.ruleset.banByMaxGames[str(self.GetBestOf())]
            else:
                return 0

    def GetBestOf(self):
        # The set's best of comes from its scoreboard
        return (
            StateManager.Get(f"score.{self.scoreboardNumber}.best_of") or self.CurrentState().bestOf
        )

    def IsPicking(self):
        """Whether the current player picks a stage instead of striking"""
        state = self.CurrentState()
        if state.gentlemans:
            return True
        if state.currGame > 0:
            return state.currStep > 0
        # Game 1's stage is the one left once the strikes are done. A ruleset
        # striking too few leaves more than one, then the next player picks.
        return state.currStep >= len(self.ruleset.strikeOrder or [])

    def StageClicked(self, stage):
        codename = stage.get("codename")
        logger.info(f"Clicked on stage {codename}")
        state = self.CurrentState()

        # Nobody strikes or picks before RPS (a gentleman's pick needs no RPS)
        if state.currPlayer == -1 and not state.gentlemans:
            return

        if self.IsPicking():
            if not state.gentlemans:
                if self.IsStageBanned(codename) or self.IsStageStriked(codename):
                    return
                # Game 1 is played on a starter
                if state.currGame == 0 and not any(
                    s.get("codename") == codename for s in self.ruleset.neutralStages
                ):
                    return
            newState = state.Clone()
            newState.selectedStage = codename
            logger.info("Stage picked")
            self.AddHistory(newState)
        elif not self.IsStageStriked(codename, True) and not self.IsStageBanned(codename):
            # we're banning
            striked = state.strikedStages[state.currStep]

            if codename not in striked:
                if len(striked) < self.GetStrikeNumber():
                    logger.info("Stage banned")
                    newState = state.Clone()
                    newState.strikedStages[newState.currStep].append(codename)
                    newState.strikedBy[newState.currPlayer].append(codename)
                    self.AddHistory(newState)
            else:
                logger.info("Stage unbanned")

                newState = state.Clone()
                newState.strikedStages[newState.currStep].remove(codename)
                # Whoever struck it, so an unban always takes effect
                for strikes in newState.strikedBy:
                    if codename in strikes:
                        strikes.remove(codename)
                        break
                self.AddHistory(newState)

    def ConfirmClicked(self, justOverwrite=False):
        state = self.CurrentState()
        # Nothing to confirm before RPS, once the stage is decided, or while picking
        if state.currPlayer == -1 or state.selectedStage or self.IsPicking():
            return
        # The player should have struck the right number of stages
        if len(state.strikedStages[state.currStep]) != self.GetStrikeNumber():
            return

        newState = state.Clone()
        newState.currStep += 1
        newState.currPlayer = (newState.currPlayer + 1) % 2
        newState.strikedStages.append([])

        # For game 1, once every strike is done the stage left is the one played
        if newState.currGame == 0 and newState.currStep >= len(self.ruleset.strikeOrder or []):
            remaining = [
                s.get("codename")
                for s in self.ruleset.neutralStages
                if not any(s.get("codename") in strikes for strikes in newState.strikedStages)
            ]
            if len(remaining) == 1:
                newState.selectedStage = remaining[0]

        self.AddHistory(newState, justOverwrite=justOverwrite)

    def initNewState(self, newState):
        newState.strikedStages = [[]]
        newState.selectedStage = None
        newState.strikedBy = [[], []]
        newState.gentlemans = False

    def MatchWinner(self, id):
        newState = self.CurrentState().Clone()
        newState.currGame += 1
        newState.currStep = 0

        newState.stagesWon[id].append(newState.selectedStage)
        newState.stagesPicked.append(newState.selectedStage)

        newState.currPlayer = id
        self.initNewState(newState)

        newState.lastWinner = id

        # Players may change characters for the next game
        self.characterSelect = {"game": newState.currGame, "teams": {1: None, 2: None}}

        self.AddHistory(newState)

        # If next step has no bans, skip it
        if self.GetStrikeNumber() == 0:
            self.ConfirmClicked(justOverwrite=True)

    def SetGentlemans(self, value):
        logger.info(f"Setting gentlemans to {value}")
        newState = self.CurrentState().Clone()

        newState.gentlemans = value

        newState.currPlayer = newState.lastWinner
        newState.currStep = 0
        newState.strikedStages = [[]]
        newState.strikedBy = [[], []]
        newState.selectedStage = None

        self.AddHistory(newState)

        # Back to striking, skip the bans like MatchWinner does if there are none
        if not value and newState.currGame > 0 and self.GetStrikeNumber() == 0:
            self.ConfirmClicked(justOverwrite=True)

    def ReportWinner(self, winner, team=None):
        """A game's winner (0 or 1) reported by a team's page, or by HyperDrive or a
        page for both teams with team None.

        A team's report waits for the other team to report the same winner.
        winner -1 takes back the team's own report. Returns whether the
        result was applied.
        """
        winner = int(winner)
        if winner not in (0, 1) and not (winner == -1 and team is not None):
            return False
        if team is None:
            self.MatchWinner(winner)
            return True

        pending = self.pendingWinner
        if winner == -1:
            if pending is not None and pending["team"] == team:
                self.pendingWinner = None
                self.ExportState()
            return False

        if not self.CurrentState().selectedStage:
            return False

        if pending is not None and pending["team"] != team and pending["winner"] == winner:
            # Both teams agree; the result belongs to neither team alone
            self.actor = None
            self.MatchWinner(winner)
            return True

        # A first report, or one disagreeing with the other team's
        self.pendingWinner = {"winner": winner, "team": team}
        self.ExportState()
        return False

    def GetCharacterSelectState(self):
        # Only who sent their characters, not what they picked
        if self.characterSelect is None:
            return {"active": False, "game": None, "submitted": {"1": False, "2": False}}
        return {
            "active": True,
            "game": self.characterSelect["game"],
            "submitted": {
                str(t): picks is not None for t, picks in self.characterSelect["teams"].items()
            },
        }

    def CurrentScore(self):
        """The scoreboard's score, [team 1, team 2]."""
        return [
            _Int(StateManager.Get(f"score.{self.scoreboardNumber}.team.{t}.score")) for t in (1, 2)
        ]

    def CharacterLockState(self, score):
        """Which teams already picked their characters for this score on the
        character select page: {"score": [...], "locked": {"1": bool, "2": bool}}"""
        score = [_Int(s) for s in score]
        if self.characterLock is None or self.characterLock["score"] != score:
            return {"score": score, "locked": {"1": False, "2": False}}
        return {
            "score": score,
            "locked": {str(t): picked for t, picked in self.characterLock["teams"].items()},
        }

    def CharactersLocked(self, score, team):
        return self.CharacterLockState(score)["locked"].get(str(team), False)

    def LockCharacters(self, score, teams):
        """Marks teams as having picked for this score."""
        score = [_Int(s) for s in score]
        if self.characterLock is None or self.characterLock["score"] != score:
            self.characterLock = {"score": score, "teams": {1: False, 2: False}}
        for t in teams:
            if t in (1, 2):
                self.characterLock["teams"][t] = True

    def SelectCharacters(self, picks, team=None):
        """Characters picked on the character select page: like
        ReportCharacters, but each team picks once per score. Returns
        (accepted, ready): accepted is False if the team(s) already picked
        for this score, ready as ReportCharacters'."""
        score = self.CurrentScore()
        teams = [int(team)] if team is not None else [1, 2]
        if any(self.CharactersLocked(score, t) for t in teams):
            return False, None

        # Picks still waiting from an earlier score were for a game that's over
        if self.characterSelect is not None and self.characterSelect.get("score") not in (
            None,
            score,
        ):
            self.characterSelect = None

        self.LockCharacters(score, teams)
        ready = self.ReportCharacters(picks, team)
        if self.characterSelect is not None:
            self.characterSelect["score"] = score
        self.ExportState()
        return True, ready

    def ReportCharacters(self, picks, team=None):
        """Takes the characters picked by a team, or by both with team None.

        picks is {team: {player: [[character, skin], ...]}}. With a team,
        only its picks are taken and they wait for the other team's. Returns
        the picks to apply to the scoreboard, once every team sent theirs.
        """
        teams = [int(team)] if team is not None else [int(t) for t in picks.keys()]

        if team is None and self.characterSelect is None:
            # One device for both teams, outside of a character select
            return {int(t): picks[t] for t in picks.keys()}

        if self.characterSelect is None:
            # A team picking first (e.g. a blind pick for game 1) starts one
            self.characterSelect = {
                "game": self.CurrentState().currGame,
                "teams": {1: None, 2: None},
            }

        for t in teams:
            if t in (1, 2):
                self.characterSelect["teams"][t] = picks.get(str(t), picks.get(t)) or {}

        ready = None
        if all(p is not None for p in self.characterSelect["teams"].values()):
            ready = self.characterSelect["teams"]
            self.characterSelect = None

        self.ExportState()
        return ready


def _Int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
