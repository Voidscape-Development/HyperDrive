# Checks dragging players: dropping on a player of the same team puts the
# player there and shifts the others, on one of the other team swaps them,
# and a player's stats are asked for once.
# Run from the repository root: python test/test_player_drag.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt
from qtpy.QtGui import QDragEnterEvent, QDropEvent
from qtpy.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

app = QApplication.instance() or QApplication(sys.argv)

from src import PlayerDrag
from src.PlayerDrag import MIME_TYPE, PlayerDragBoard
from src.StateManager import StateManager


class FakePlayer(QGroupBox):
    """A player widget: a header and a name, swapped like the real ones."""

    def __init__(self, path, name):
        super().__init__()
        self.path = path
        self.idChanges = 0
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.setObjectName("titleContainer")
        layout.addLayout(header)
        self.label = QLabel()
        header.addWidget(self.label)
        self.SetName(name)

    def SetName(self, name):
        self.name = name
        self.label.setText(name)
        StateManager.Set(f"{self.path}.id", name)

    def SwapWith(self, other):
        mine, theirs = self.name, other.name
        self.SetName(theirs)
        other.SetName(mine)

    def EmitPlayerIdChanged(self):
        self.idChanges += 1


def Teams():
    team1 = [FakePlayer(f"drag.team.1.player.{i + 1}", n) for i, n in enumerate("ABCD")]
    team2 = [FakePlayer(f"drag.team.2.player.{i + 1}", n) for i, n in enumerate("WXYZ")]
    board = PlayerDragBoard(lambda: [team1, team2], lambda a, b: a.SwapWith(b))
    for p in team1 + team2:
        board.Register(p)
    return board, team1, team2


def Names(team):
    return "".join(p.name for p in team)


def TestMoveDown():
    board, team1, team2 = Teams()
    board.Move(team1[0], team1[2])
    assert Names(team1) == "BCAD", Names(team1)
    assert Names(team2) == "WXYZ"
    # Asked once for each player whose place changed, not once per swap
    assert [p.idChanges for p in team1] == [1, 1, 1, 0]
    print("TestMoveDown: OK")


def TestMoveUp():
    board, team1, team2 = Teams()
    board.Move(team1[3], team1[1])
    assert Names(team1) == "ADBC", Names(team1)
    print("TestMoveUp: OK")


def TestAcrossTeamsSwaps():
    board, team1, team2 = Teams()
    board.Move(team1[1], team2[3])
    assert Names(team1) == "AZCD" and Names(team2) == "WXYB"
    print("TestAcrossTeamsSwaps: OK")


def TestCanDropAndGrip():
    board, team1, team2 = Teams()
    stranger = FakePlayer("drag.other", "Q")
    assert board.CanDrop(team1[0], team2[0])
    assert not board.CanDrop(team1[0], team1[0])
    assert not board.CanDrop(stranger, team1[0])
    assert not board.CanDrop(None, team1[0])
    # The grip is first in the header
    header = team1[0].findChild(QHBoxLayout, "titleContainer")
    assert header.itemAt(0).widget() is team1[0].dragGrip
    assert team1[0].acceptDrops()
    print("TestCanDropAndGrip: OK")


def Drop(target, data, action=Qt.DropAction.MoveAction):
    """Drags data over target and drops it. Returns if each was taken: Qt
    only drops on a widget that took the drag entering it."""
    enter = QDragEnterEvent(
        QPoint(5, 5), action, data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(target, enter)
    if not enter.isAccepted():
        return False, False
    event = QDropEvent(
        QPointF(5, 5), action, data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(target, event)
    return True, event.isAccepted()


def TestDrop():
    board, team1, team2 = Teams()
    data = QMimeData()
    data.setData(MIME_TYPE, QByteArray())
    PlayerDrag._dragged = team1[0]
    try:
        assert Drop(team1[3], data) == (True, True)
        # Not on the player being dragged
        assert Drop(team1[0], data) == (False, False)
    finally:
        PlayerDrag._dragged = None
    # The move happens once the drag is over
    app.processEvents()
    assert Names(team1) == "BCDA", Names(team1)

    # Other drags (text from a field) aren't taken
    text = QMimeData()
    text.setText("hello")
    assert Drop(team1[0], text, Qt.DropAction.CopyAction) == (False, False)
    app.processEvents()
    assert Names(team1) == "BCDA"
    print("TestDrop: OK")


if __name__ == "__main__":
    TestMoveDown()
    TestMoveUp()
    TestAcrossTeamsSwaps()
    TestCanDropAndGrip()
    TestDrop()
    print("OK")
