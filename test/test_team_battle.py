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

from qtpy.QtWidgets import QApplication

app = QApplication(sys.argv)

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None
SettingsManager.Set("general.team_battle_default_stocks", 3)
SettingsManager.Set("general.team_battle_default_first_to", 2)

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

if failures:
    print(f"{failures} check(s) failed")
    sys.exit(1)
print("All team battle checks passed")
