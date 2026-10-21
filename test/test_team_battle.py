# Checks the Crew/Team Battle widget: active players, auto advance, taking
# stocks in Stock Pool, eliminations in First To, and undoing them.
# Run from the repository root: python test/test_team_battle.py
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtWidgets import QApplication, QLineEdit

app = QApplication(sys.argv)

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None
SettingsManager.Set("general.team_battle_default_stocks", 3)
SettingsManager.Set("general.team_battle_default_first_to", 2)
SettingsManager.Set("team_battle.first_player_starts", True)

from src.StateManager import StateManager
from src.TeamBattleModeEnum import TeamBattleModeEnum
from src.TeamBattleWidget import TeamBattleWidget

failures = 0


def check(condition, message):
    global failures
    if not condition:
        failures += 1
        print(f"FAIL: {message}")


w = TeamBattleWidget()


def stocks(team):
    return [p.GetSpinnerValue() for p in w.Players(team)]


def eliminated(team):
    return [p.IsEliminated() for p in w.Players(team)]


def active(team):
    return [p.IsActive() for p in w.Players(team)]


# Stock Pool
w.autoAdvance.setChecked(True)
check(w.battleMode is TeamBattleModeEnum.STOCK_POOL, "starts in Stock Pool")
check(w.livesNumber.value() == 3, "starts with the stocks from the settings")
w.playerNumber.setValue(3)
check(stocks(1) == [3, 3, 3] and stocks(2) == [3, 3, 3], "new players get the stocks")
check(active(1) == [True, False, False], "a team starts with their first player")
check(StateManager.Get("team_battle.team.1.active_player") == 1, "exports the active player")
check(StateManager.Get("team_battle.team1_spinner-total") == 9, "exports the stocks left")
check(StateManager.Get("team_battle.battle_value") == 3, "exports the stocks players start with")

for _ in range(3):
    w.signals.team1_stock_up.emit()
check(stocks(2) == [0, 3, 3], "team 1 scoring takes team 2's stocks")
check(eliminated(2) == [True, False, False], "no stocks left eliminates")
check(active(2) == [False, True, False], "auto advance brings in the next player")

w.signals.team1_stock_down.emit()
check(stocks(2) == [1, 3, 3], "undo gives the stock back to the eliminated player")
check(eliminated(2) == [False] * 3 and active(2) == [True, False, False], "undo brings them back")

w.signals.team1_stock_up.emit()
w.signals.team1_stock_up.emit()
w.signals.team1_stock_down.emit()
check(stocks(2) == [0, 3, 3], "undo after the next player lost a stock is theirs")

w.signals.team2_next_active_player.emit()
check(active(2) == [False, False, True], "next player")
w.signals.team2_next_active_player.emit()
check(active(2) == [False, True, False], "next player wraps around past eliminated players")

w.signals.team1_set_active_player.emit(2)
check(active(1) == [False, False, True], "one active player per team")

w.signals.team1_set_active_player.emit(0)
w.MovePlayer(1, w.team1playerWidgets[0], 1)
check(active(1) == [False, True, False], "the active player stays active when moved")
check(w.currentActiveIndexTeam1 == 1, "moving the active player moves the active index")

w.autoAdvance.setChecked(False)
for _ in range(3):
    w.signals.team1_stock_up.emit()
check(eliminated(2)[1] and active(2) == [False, True, False], "auto advance can be turned off")
w.autoAdvance.setChecked(True)

w.ResetAllStocks()
check(stocks(2) == [3, 3, 3] and eliminated(2) == [False] * 3, "reset stocks")

w.team1playerWidgets[0].Clear()
check(stocks(1)[0] == 3 and not eliminated(1)[0], "clearing a player doesn't eliminate them")

# First To
w.modeCombo.setCurrentIndex(1)
check(w.battleMode is TeamBattleModeEnum.FIRST_TO, "switches to First To")
check(w.livesNumber.value() == 2, "uses the First To amount from the settings")
check(StateManager.Get("team_battle.battle_value") == 2, "exports the First To amount")
check(stocks(1) == [0, 0, 0] and eliminated(2) == [False] * 3, "switching resets the players")

w.ResetEverything()
check(active(1) == [True, False, False], "reset everything starts with the first players")

w.autoAdvance.setChecked(False)
w.signals.team1_stock_up.emit()
w.signals.team1_stock_up.emit()
check(stocks(1)[0] == 2, "team 1 scoring wins a game")
check(eliminated(2) == [True, False, False], "reaching First To eliminates the opponent")
w.signals.team1_stock_down.emit()
check(eliminated(2) == [False] * 3, "undo brings the opponent back")
w.signals.team1_stock_up.emit()
w.signals.team2_next_active_player.emit()
check(stocks(1)[0] == 0, "the winner starts over when the next opponent comes in")

w.autoAdvance.setChecked(True)
w.signals.team1_stock_up.emit()
w.signals.team1_stock_up.emit()
check(active(2) == [False, False, True] and stocks(1)[0] == 0, "auto advance in First To")

w.playerNumber.setValue(2)
check(len(w.Players(1)) == 2, "removes players")
check("3" not in StateManager.Get("team_battle.team.1.player"), "removed players' data")


# Plays: only some of the players play, the others wait on deck
def status(team):
    return [StateManager.Get(f"team_battle.team.{team}.player.{i + 1}.status") for i in range(7)]


def order(team):
    return [
        StateManager.Get(f"team_battle.team.{team}.player.{i + 1}.play_order") for i in range(7)
    ]


def kill(team):
    # The other team scores until the team's active player is out
    for _ in range(3):
        w.signals.team1_stock_up.emit() if team == 2 else w.signals.team2_stock_up.emit()


w.modeCombo.setCurrentIndex(0)
w.playerNumber.setValue(7)
check(w.playsNumber.value() == 7 and not w.IsLimited(), "plays follows the players")
w.playsNumber.setValue(4)
check(w.IsLimited(), "fewer plays than players")
check(StateManager.Get("team_battle.plays") == 4, "exports the plays")
w.ResetEverything()
check(status(2) == ["playing"] + ["on_deck"] * 6, "the others are on deck")
check(StateManager.Get("team_battle.team2_spinner-total") == 12, "only the plays' stocks count")
check(StateManager.Get("team_battle.team.2.plays_left") == 4, "exports the plays left")
check(order(2) == [1] + [None] * 6, "exports the order players came in")
check(w.team2playerWidgets[1].playStatusLabel.text() == "ON DECK", "shows on deck in the window")

w.autoAdvance.setChecked(True)
kill(2)
check(eliminated(2)[0] and active(2)[0], "nobody comes in on their own, the team picks")
check(status(2)[:2] == ["out", "on_deck"], "eliminated players are out")
check(StateManager.Get("team_battle.team2_spinner-total") == 9, "an eliminated player's stocks")
w.signals.team2_next_active_player.emit()
check(active(2)[1], "next player still works when asked for")
w.signals.team1_stock_down.emit()
check(active(2)[0] and not eliminated(2)[0] and stocks(2)[0] == 1, "undo brings back the player")
check(order(2)[1] is None, "a pick that's undone goes back on deck")

w.signals.team1_stock_up.emit()
w.signals.team2_set_active_player.emit(4)
check(active(2)[4] and order(2)[4] == 2, "the team picks their next player")
w.signals.team1_stock_up.emit()
check(stocks(2)[4] == 2, "the picked player loses stocks")
for pick in [5, 6]:
    kill(2)
    w.signals.team2_set_active_player.emit(pick)
kill(2)
check(w.TeamIsOut(2), "the team is out after the plays are used")
check(status(2) == ["out", "unused", "unused", "unused", "out", "out", "out"], "didn't play")
check(StateManager.Get("team_battle.team2_spinner-total") == 0, "no stocks left")
check(not w.NextActivePlayer(2), "nobody else comes in once the team is out")
check(w.team2playerWidgets[1].playStatusLabel.text() == "DIDN'T PLAY", "shows didn't play")

w.playsNumber.setValue(7)
check(not w.IsLimited() and status(2)[1] == "on_deck", "everyone plays again")
check(not w.team2playerWidgets[1].playStatusLabel.isVisibleTo(w), "no status in the window")
w.playerNumber.setValue(5)
check(w.playsNumber.value() == 5, "plays keeps following the players")
w.playsNumber.setValue(3)
w.playerNumber.setValue(6)
check(w.playsNumber.value() == 3, "set plays stay when players are added")

# Without "First player starts", nobody plays until the team picks
w.firstPlayerStarts.setChecked(False)
w.ResetEverything()
check(not any(active(2)) and w.ActivePlayer(2) is None, "nobody plays after a reset")
check(status(2)[:6] == ["on_deck"] * 6, "everyone is on deck")
check(StateManager.Get("team_battle.team.2.active_player") is None, "no active player exported")
w.signals.team1_stock_up.emit()
check(stocks(2) == [3] * 6, "scoring does nothing before the team picks")
w.signals.team2_set_active_player.emit(2)
check(active(2)[2] and status(2)[2] == "playing", "the team picks their first player")
w.signals.team1_stock_up.emit()
check(stocks(2)[2] == 2, "the picked player loses stocks")
w.firstPlayerStarts.setChecked(True)
w.ResetEverything()
check(active(2)[0], "with First player starts, the first player plays after a reset")

w.modeCombo.setCurrentIndex(1)
w.ResetEverything()
w.signals.team1_stock_up.emit()
w.signals.team1_stock_up.emit()
check(eliminated(2)[0] and active(2)[0], "First To: the team picks too")
w.signals.team2_set_active_player.emit(3)
check(stocks(1)[0] == 0, "First To: the winner starts over against the picked player")
w.playsNumber.setValue(6)
w.playerNumber.setValue(2)

# Team name and logo
teamName = w.team1column.findChild(QLineEdit, "teamName")
teamName.setText("No Logo Team")
teamName.editingFinished.emit()
check(StateManager.Get("team_battle.team.1.sponsor") == "No Logo Team", "exports the team name")
check(StateManager.Get("team_battle.team.1.logo") is None, "no logo for a team without one")
os.makedirs("./user_data/team_logo", exist_ok=True)
logo = "./user_data/team_logo/test battle team.png"
with open(logo, "wb") as f:
    f.write(b"")
try:
    teamName.setText("Test Battle Team")
    teamName.editingFinished.emit()
    check(StateManager.Get("team_battle.team.1.logo") == logo, "exports the team logo")
finally:
    os.remove(logo)
w.RefreshTeamLogos()
check(StateManager.Get("team_battle.team.1.logo") is None, "a removed logo is unset")

if failures:
    print(f"{failures} check(s) failed")
    sys.exit(1)
print("All team battle checks passed")
