# Checks the games tracker under the score: a square per game in the color
# of the team that won it (both for a draw, none for a game not played), and
# clicking a square opens that game.
# Run from the repository root: python test/test_games_tracker.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QColor
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.GameReport import DRAW, UNDECIDED, GameReport
from src.GamesTracker import SQUARE, GamesTracker

RED = "#e53935"
BLUE = "#1e88e5"


def Tracker(winners, width=300):
    report = GameReport()
    report.SetBestOf(len(winners))
    for i, winner in enumerate(winners):
        report.SetWinner(i, winner)
    tracker = GamesTracker(tooltip=lambda i: f"Game {i + 1}")
    tracker.resize(width, 40)
    tracker.SetColors(RED, BLUE)
    tracker.SetGames(report.games, report.CurrentGameIndex())
    tracker.show()
    app.processEvents()
    return tracker, report


def Pixel(image, point):
    return QColor(image.pixel(point))


def Close(color, expected):
    expected = QColor(expected)
    return all(
        abs(a - b) <= 12
        for a, b in [
            (color.red(), expected.red()),
            (color.green(), expected.green()),
            (color.blue(), expected.blue()),
        ]
    )


def TestColors():
    tracker, report = Tracker([1, 2, DRAW, UNDECIDED, UNDECIDED])
    rects = tracker.Rects()
    assert len(rects) == 5
    # Centered in one row
    assert len({r.top() for r in rects}) == 1
    assert abs(rects[0].left() - (tracker.width() - rects[-1].right())) <= 2
    image = tracker.grab().toImage()
    corner = QPoint(5, 5)
    assert Close(Pixel(image, rects[0].topLeft() + corner), RED)
    assert Close(Pixel(image, rects[1].topLeft() + corner), BLUE)
    # A draw: team 1's color top left, team 2's bottom right
    assert Close(Pixel(image, rects[2].topLeft() + corner), RED)
    assert Close(Pixel(image, rects[2].bottomRight() - corner), BLUE)
    # Not played: neither
    empty = Pixel(image, rects[3].topLeft() + corner)
    assert not Close(empty, RED) and not Close(empty, BLUE)
    assert tracker.current == 3
    print("TestColors: OK")


def TestWrapsAndHides():
    tracker, report = Tracker([UNDECIDED] * 7, width=3 * SQUARE + 20)
    rows = {r.top() for r in tracker.Rects()}
    assert len(rows) == 3, rows
    assert tracker.height() == tracker.heightForWidth(tracker.width())
    tracker.SetGames([], 0)
    assert not tracker.isVisible()
    print("TestWrapsAndHides: OK")


def TestClick():
    tracker, report = Tracker([1, UNDECIDED, UNDECIDED])
    clicked = []
    tracker.gameClicked.connect(clicked.append)
    QTest.mouseClick(tracker, Qt.MouseButton.LeftButton, pos=tracker.Rects()[2].center())
    # Between squares: nothing
    between = QPoint(tracker.Rects()[0].right() + 3, tracker.Rects()[0].center().y())
    QTest.mouseClick(tracker, Qt.MouseButton.LeftButton, pos=between)
    assert clicked == [2], clicked
    assert tracker.IndexAt(tracker.Rects()[1].center()) == 1
    assert tracker.tooltip(1) == "Game 2"
    print("TestClick: OK")


if __name__ == "__main__":
    TestColors()
    TestWrapsAndHides()
    TestClick()
    print("OK")
