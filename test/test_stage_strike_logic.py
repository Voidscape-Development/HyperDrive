# Checks the stage strike rules of TSHStageStrikeLogic.
# Run from the repository root: python test/test_stage_strike_logic.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package


# The logic only needs the state and the scoreboards' game reports
class FakeStateManager:
    state = {}

    @staticmethod
    def Get(key, default=None):
        return FakeStateManager.state.get(key, default)

    @staticmethod
    def Set(key, value):
        FakeStateManager.state[key] = value


class FakeGameReport:
    def __init__(self):
        self.stages = {}

    def SetStage(self, index, codename):
        self.stages[index] = codename


class FakeScoreboard:
    def __init__(self):
        self.gameReport = FakeGameReport()


class FakeScoreboardManager:
    def __init__(self):
        self.scoreboardholder = [FakeScoreboard()]

    def GetScoreboard(self, number):
        return self.scoreboardholder[number - 1]


state_module = types.ModuleType("src.StateManager")
state_module.StateManager = FakeStateManager
sys.modules["src.StateManager"] = state_module

manager_module = types.ModuleType("src.TSHScoreboardManager")
manager_module.TSHScoreboardManager = FakeScoreboardManager
FakeScoreboardManager.instance = FakeScoreboardManager()
sys.modules["src.TSHScoreboardManager"] = manager_module

from src.TSHStageStrikeLogic import TSHStageStrikeLogic


class Ruleset:
    def __init__(
        self,
        neutral,
        counterpick=(),
        strikeOrder=(1, 2, 1),
        banCount=0,
        useDSR=False,
        useMDSR=False,
    ):
        self.neutralStages = [{"codename": s} for s in neutral]
        self.counterpickStages = [{"codename": s} for s in counterpick]
        self.strikeOrder = list(strikeOrder)
        self.banCount = banCount
        self.banByMaxGames = {}
        self.useDSR = useDSR
        self.useMDSR = useMDSR


STARTERS = ["bf", "fd", "sv", "ps2", "tc"]


def NewLogic(**kwargs):
    FakeScoreboardManager.instance = FakeScoreboardManager()
    FakeStateManager.state = {}
    logic = TSHStageStrikeLogic(1)
    logic.SetRuleset(Ruleset(STARTERS, **kwargs))
    return logic


def Click(logic, codename):
    logic.StageClicked({"codename": codename})


def StrikeGame1(logic, strikes=(["bf"], ["fd", "sv"], ["ps2"])):
    logic.RpsResult(0)
    for step in strikes:
        for stage in step:
            Click(logic, stage)
        logic.ConfirmClicked()


def GameReport():
    return FakeScoreboardManager.instance.scoreboardholder[0].gameReport.stages


def TestGame1LeavesOneStage():
    logic = NewLogic()
    StrikeGame1(logic)
    state = logic.CurrentState()
    assert state.selectedStage == "tc"
    # Only played games are in stagesPicked
    assert state.stagesPicked == []
    assert state.strikedBy == [["bf", "ps2"], ["fd", "sv"]]


def TestClicksAfterGame1StageDecided():
    logic = NewLogic()
    StrikeGame1(logic)
    before = len(logic.history)
    # Used to raise IndexError, as the strike order was over
    Click(logic, "bf")
    logic.ConfirmClicked()
    assert logic.CurrentState().selectedStage == "tc"
    assert len(logic.history) == before


def TestGameReportStages():
    logic = NewLogic(counterpick=["kalos"], banCount=2, useDSR=True)
    StrikeGame1(logic)
    logic.MatchWinner(0)
    assert logic.CurrentState().stagesPicked == ["tc"]

    # The winner bans two, the loser picks
    Click(logic, "bf")
    Click(logic, "fd")
    logic.ConfirmClicked()
    # DSR: game 1's stage can't be picked again
    Click(logic, "tc")
    assert logic.CurrentState().selectedStage is None
    Click(logic, "kalos")
    assert logic.CurrentState().selectedStage == "kalos"
    logic.MatchWinner(1)

    assert logic.CurrentState().stagesPicked == ["tc", "kalos"]
    assert GameReport() == {0: "tc", 1: "kalos"}


def TestGentlemansGame1KeepsGameReportInOrder():
    logic = NewLogic()
    logic.RpsResult(0)
    logic.SetGentlemans(True)
    Click(logic, "fd")
    logic.MatchWinner(0)
    logic.SetGentlemans(True)
    Click(logic, "sv")
    logic.MatchWinner(1)
    # Game 2's stage used to overwrite game 1's in the game report
    assert logic.CurrentState().stagesPicked == ["fd", "sv"]
    assert GameReport() == {0: "fd", 1: "sv"}


def TestGentlemansAfterStrikesDoesNotKeepUnplayedStage():
    logic = NewLogic(useDSR=True)
    StrikeGame1(logic)
    assert logic.CurrentState().selectedStage == "tc"
    logic.SetGentlemans(True)
    Click(logic, "bf")
    logic.MatchWinner(0)
    # tc was never played, so it isn't banned by DSR
    assert logic.CurrentState().stagesPicked == ["bf"]
    assert not logic.IsStageBanned("tc")


def TestUnbanAfterTurnSwitch():
    logic = NewLogic()
    logic.RpsResult(0)
    Click(logic, "bf")
    assert logic.CurrentState().strikedStages[0] == ["bf"]
    Click(logic, "bf")
    assert logic.CurrentState().strikedStages[0] == []
    assert logic.CurrentState().strikedBy == [[], []]


def TestNoStrikesBeforeRps():
    logic = NewLogic()
    Click(logic, "bf")
    logic.ConfirmClicked()
    assert logic.CurrentState().strikedStages == [[]]
    assert logic.CurrentState().currStep == 0


def TestSecondRpsIgnored():
    logic = NewLogic()
    logic.RpsResult(0)
    Click(logic, "bf")
    # The other page's report arriving late
    logic.RpsResult(1)
    state = logic.CurrentState()
    assert state.currPlayer == 0
    assert state.strikedBy == [["bf"], []]


def TestTooFewStrikesLetsNextPlayerPick():
    # 5 starters but only 2 strikes: 3 stages are left after striking
    logic = NewLogic(strikeOrder=[1, 1])
    StrikeGame1(logic, strikes=(["bf"], ["fd"]))
    state = logic.CurrentState()
    assert state.selectedStage is None
    assert logic.IsPicking()
    # Struck and counterpick stages can't be picked for game 1
    Click(logic, "bf")
    Click(logic, "kalos")
    assert logic.CurrentState().selectedStage is None
    Click(logic, "ps2")
    assert logic.CurrentState().selectedStage == "ps2"


def TestNoBansSkipsToPick():
    logic = NewLogic(banCount=0)
    StrikeGame1(logic)
    logic.MatchWinner(0)
    state = logic.CurrentState()
    assert state.currStep == 1 and state.currPlayer == 1

    # Ending a gentleman's pick goes back to the loser picking too
    logic.SetGentlemans(True)
    logic.SetGentlemans(False)
    state = logic.CurrentState()
    assert state.currStep == 1 and state.currPlayer == 1


def TestInvalidWinnerIgnored():
    logic = NewLogic()
    StrikeGame1(logic)
    assert logic.ReportWinner(2) is False
    assert logic.CurrentState().currGame == 0
    assert logic.ReportWinner(-1) is False
    assert logic.CurrentState().currGame == 0


def TestTeamsConfirmWinner():
    logic = NewLogic()
    StrikeGame1(logic)
    assert logic.ReportWinner(0, team=1) is False
    assert logic.pendingWinner == {"winner": 0, "team": 1}
    assert logic.ReportWinner(0, team=2) is True
    assert logic.CurrentState().stagesWon == [["tc"], []]


def SetScore(team1, team2):
    FakeStateManager.state["score.1.team.1.score"] = team1
    FakeStateManager.state["score.1.team.2.score"] = team2


PICK1 = {"1": {"1": [["Mario", 0]]}}
PICK2 = {"2": {"1": [["Fox", 2]]}}


def TestCharacterSelectOncePerScore():
    logic = NewLogic()
    SetScore(0, 0)
    assert logic.CharacterLockState(logic.CurrentScore())["locked"] == {"1": False, "2": False}

    # Team 1 picks: locked for this score, waiting for team 2
    assert logic.SelectCharacters(PICK1, team=1) == (True, None)
    assert logic.CharactersLocked([0, 0], 1) and not logic.CharactersLocked([0, 0], 2)
    assert logic.SelectCharacters(PICK1, team=1) == (False, None)
    assert FakeStateManager.state["score.1.stage_strike"]["characterLock"]["locked"] == {
        "1": True,
        "2": False,
    }

    # Team 2 picks: both teams' picks are ready together
    accepted, ready = logic.SelectCharacters(PICK2, team=2)
    assert accepted and ready == {1: PICK1["1"], 2: PICK2["2"]}
    assert logic.SelectCharacters(PICK2, team=2) == (False, None)

    # The next game unlocks both teams
    SetScore(1, 0)
    assert not logic.CharactersLocked(logic.CurrentScore(), 1)
    assert logic.SelectCharacters(PICK1, team=1) == (True, None)


def TestCharacterSelectBothTeams():
    logic = NewLogic()
    SetScore(0, 0)
    both = {**PICK1, **PICK2}
    accepted, ready = logic.SelectCharacters(both)
    assert accepted and ready == {1: PICK1["1"], 2: PICK2["2"]}
    # A page for both teams locks both, and a team's page too
    assert logic.SelectCharacters(both) == (False, None)
    assert logic.SelectCharacters(PICK1, team=1) == (False, None)


def TestCharacterSelectDropsPicksFromEarlierScore():
    logic = NewLogic()
    SetScore(0, 0)
    logic.SelectCharacters(PICK1, team=1)
    # The game ended before team 2 picked: team 1's old pick isn't used
    SetScore(0, 1)
    accepted, ready = logic.SelectCharacters(PICK2, team=2)
    assert accepted and ready is None
    assert logic.characterSelect["teams"] == {1: None, 2: PICK2["2"]}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
