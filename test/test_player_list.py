# Checks the player list's folding: slots collapse to their title row
# (place, team name and score), players fold their details, and both are
# kept in the settings for next time, unless "start slots collapsed" is on.
# Run from the repository root: python test/test_player_list.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QLineEdit

app = QApplication.instance() or QApplication(sys.argv)

from src.PlayerList import PlayerList


def Settle():
    for _ in range(5):
        app.processEvents()


def List(base="player_list", startCollapsed=False, slots=3, players=2):
    playerList = PlayerList(base=base, startCollapsed=startCollapsed)
    playerList.SetSlotNumber(slots)
    playerList.SetPlayersPerTeam(players)
    playerList.resize(900, 600)
    playerList.show()
    Settle()
    return playerList


def Folds(base="player_list"):
    return SettingsManager.settings["player_list_folds"][base]


def TestTitleRow():
    SettingsManager.settings = {}
    playerList = List()
    slot = playerList.slotWidgets[0]
    playerList.SetScoresVisible(Qt.CheckState.Checked)
    Settle()
    # The score is on the team name's row
    assert slot.scoreWidget.isVisible()
    nameY = slot.slotName.geometry().center().y()
    assert abs(slot.scoreWidget.geometry().center().y() - nameY) < 6
    # Without a team name, the players' tags hint at who is in the slot
    assert slot.slotName.placeholderText() == "Team Name"
    for pw, tag in zip(slot.playerWidgets, ["Alice", "Bob"]):
        name = pw.findChild(QLineEdit, "name")
        name.setText(tag)
        name.editingFinished.emit()
    assert slot.slotName.placeholderText() == "Alice / Bob"
    # Slots made after the scores are shown have one too
    playerList.SetSlotNumber(4)
    Settle()
    assert playerList.slotWidgets[3].scoreWidget.isVisible()


def TestCollapse():
    SettingsManager.settings = {}
    playerList = List()
    slot = playerList.slotWidgets[1]
    assert not slot.collapsed and slot.list.isVisible()
    slot.collapseButton.click()
    Settle()
    assert slot.collapsed and not slot.list.isVisible()
    assert slot.slotName.isVisible()
    assert Folds()["slots"] == {"2": True}

    playerList.SetAllCollapsed(True)
    assert all(s.collapsed for s in playerList.slotWidgets)
    playerList.SetAllCollapsed(False)
    assert not any(s.collapsed for s in playerList.slotWidgets)
    assert Folds()["slots"] == {"1": False, "2": False, "3": False}


def TestPlayerDetails():
    SettingsManager.settings = {}
    playerList = List()
    player = playerList.slotWidgets[0].playerWidgets[1]
    player.detailsButton.click()
    assert not player.detailsShown
    assert Folds()["players"] == {"1-2": False}

    playerList.SetCompactPlayers(True)
    shown = [p.detailsShown for s in playerList.slotWidgets for p in s.playerWidgets]
    assert not any(shown)
    # New players follow "compact players"
    playerList.SetPlayersPerTeam(3)
    assert not playerList.slotWidgets[0].playerWidgets[2].detailsShown


def TestRemembered():
    SettingsManager.settings = {}
    playerList = List()
    playerList.slotWidgets[2].collapseButton.click()
    playerList.slotWidgets[0].playerWidgets[0].detailsButton.click()

    # Opened again, as they were left
    again = List()
    assert [s.collapsed for s in again.slotWidgets] == [False, False, True]
    assert not again.slotWidgets[0].playerWidgets[0].detailsShown
    assert again.slotWidgets[0].playerWidgets[1].detailsShown

    # "Start slots collapsed" collapses them all, and new slots too
    again.SetStartCollapsed(True)
    collapsed = List(slots=4)
    assert all(s.collapsed for s in collapsed.slotWidgets)


def TestDefaultsAndKeys():
    SettingsManager.settings = {}
    # The player list window's slots start collapsed, the bracket's don't
    assert all(s.collapsed for s in List(startCollapsed=True).slotWidgets)
    roster = List(base="bracket.rosters.local")
    assert not any(s.collapsed for s in roster.slotWidgets)
    roster.slotWidgets[0].collapseButton.click()
    # A base with dots is one settings key
    assert Folds("bracket_rosters_local")["slots"] == {"1": True}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
