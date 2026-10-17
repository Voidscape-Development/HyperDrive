# Checks the games pop-ups: the one-game pop-up a games tracker square opens
# (picking the winner, going through the games, the characters a game takes,
# offering to report the set once it's won) and the sheet of every game the
# Games button opens (rows updated in place, games the set won't need, the
# report button saying what it reports).
# Run from the repository root: python test/test_games_popup.py
# (with an optional folder to save screenshots of the pop-ups to)
import contextlib
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)

repoDir = os.path.abspath(".")
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
os.chdir(workDir)
# Theme reads the icons from the repository
os.symlink(os.path.join(repoDir, "assets"), os.path.join(workDir, "assets"))

CHARACTERS = ["Diddy Kong", "Byleth", "Pyra", "Sonic"]


# The asset manager loads games on import; the pop-ups need its models
class FakeAssetSignals(QObject):
    onLoad = Signal()


class FakeAssetManager:
    instance = None

    def __init__(self):
        self.signals = FakeAssetSignals()
        self.selectedGame = {"codename": "fake"}
        self.characters = {c: {"display_name": c} for c in CHARACTERS}
        self.stockIcons = {}
        self.skinModels = {}
        self.characterModel = QStandardItemModel()
        self.characterModel.appendRow(QStandardItem(""))
        for name in CHARACTERS:
            item = QStandardItem(name)
            item.setData({"en_name": name, "display_name": name}, Qt.ItemDataRole.UserRole)
            self.characterModel.appendRow(item)
        self.stageModelWithBlank = QStandardItemModel()

    def GetStartGGCharacterId(self, key):
        return CHARACTERS.index(key) + 1 if key in CHARACTERS else None

    def GetStartGGStageId(self, codename):
        return None


FakeAssetManager.instance = FakeAssetManager()
module = types.ModuleType("src.GameAssetManager")
module.GameAssetManager = FakeAssetManager
sys.modules["src.GameAssetManager"] = module


class FakeState:
    data = {}

    @staticmethod
    def Get(key, default=None):
        return FakeState.data.get(key, default)

    @staticmethod
    def Set(key, value):
        FakeState.data[key] = value

    @staticmethod
    @contextlib.contextmanager
    def SaveBlock():
        yield


module = types.ModuleType("src.StateManager")
module.StateManager = FakeState
sys.modules["src.StateManager"] = module


class FakeReporterSignals(QObject):
    status_changed = Signal(int)
    set_reported = Signal(int, str)


class FakeReporter:
    instance = None
    token = False

    def __init__(self):
        self.signals = FakeReporterSignals()
        self.submitted = []

    def Status(self, number):
        return {}

    def Busy(self, number):
        return False

    def Clear(self, number):
        pass

    def Submit(self, number, kind, setId, variables=None):
        self.submitted.append((kind, setId))


FakeReporter.instance = FakeReporter()
module = types.ModuleType("src.StartGGReporter")
module.StartGGReporter = FakeReporter
module.HasToken = lambda: FakeReporter.token
module.IsReportableSetId = lambda setId: setId is not None and str(setId).isdigit()
for constant in ["KIND_START", "KIND_UPDATE", "KIND_REPORT", "KIND_RESET"]:
    setattr(module, constant, constant)
for constant in [
    "STATUS_PENDING",
    "STATUS_SENDING",
    "STATUS_SYNCED",
    "STATUS_REPORTED",
    "STATUS_RETRYING",
    "STATUS_ERROR",
]:
    setattr(module, constant, constant)
sys.modules["src.StartGGReporter"] = module

from src.GameReport import UNDECIDED
from src.GameReportController import GameReportController
from src.GamesPopup import GamePopup, GamesSheetPopup


class FakeColorButton:
    def __init__(self, color):
        self._color = color

    def color(self):
        return self._color


class FakeScoreboard(QWidget):
    def __init__(self):
        super().__init__()
        self.scoreboardNumber = 1
        self.team1playerWidgets = [None]
        self.colorButton1 = FakeColorButton("#d93a3a")
        self.colorButton2 = FakeColorButton("#2e6fe0")


def Setup(bestOf=5, scoreboardCharacters=(None, None)):
    FakeState.data = {
        "score.1.team.1.mergedTeamName": "Tweek",
        "score.1.team.2.mergedTeamName": "MkLeo",
    }
    for team, character in enumerate(scoreboardCharacters, start=1):
        if character:
            FakeState.data[f"score.1.team.{team}.player.1.character.1"] = {"en_name": character}
    FakeReporter.token = False
    scoreboard = FakeScoreboard()
    controller = GameReportController(scoreboard)
    controller.SetBestOf(bestOf)
    return scoreboard, controller


def Anchor():
    return QRect(QPoint(200, 200), QSize(22, 22))


def ComboName(combo):
    return (combo.currentData() or {}).get("en_name")


def TestSheetRows():
    scoreboard, controller = Setup()
    popup = GamesSheetPopup(controller, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    assert len(popup.rows) == 5
    assert popup.rows[0]["highlight"].isVisible()
    assert [b.text() for b in popup.rows[0]["winners"].values()] == ["Tweek", "MkLeo"]

    # A winner click updates the rows in place, it doesn't build them again
    button = popup.rows[0]["winners"][1]
    button.click()
    app.processEvents()
    assert controller.report.games[0]["winner"] == 1
    assert popup.rows[0]["winners"][1] is button and button.isChecked()
    assert popup.rows[0]["score"].text() == "1–0"
    assert not popup.rows[0]["highlight"].isVisible()
    assert popup.rows[1]["highlight"].isVisible()

    # Clicking it again clears it
    button.click()
    assert controller.report.games[0]["winner"] is UNDECIDED

    # 1 / 2 pick the winner of the game being played
    QTest.keyClick(popup, Qt.Key.Key_2)
    QTest.keyClick(popup, Qt.Key.Key_1)
    assert [g["winner"] for g in controller.report.games[:3]] == [2, 1, UNDECIDED]
    assert popup.rows[1]["score"].text() == "1–1"

    # Without a token there's nothing about start.gg
    assert not popup.reportButton.isVisibleTo(popup)
    assert popup.status.text() == ""

    # A best of with more games builds the rows again
    controller.SetBestOf(7)
    assert len(popup.rows) == 7
    popup.close()
    print("TestSheetRows: OK")


def TestSheetSetWon():
    scoreboard, controller = Setup()
    FakeReporter.token = True
    controller.NewSet("123")
    controller.ApplySetData({"id": "123", "entrant_ids": [10, 20], "state": 2})
    popup = GamesSheetPopup(controller, scoreboard)
    popup.Open(Anchor())
    assert popup.reportButton.isVisibleTo(popup)
    assert not popup.reportButton.isEnabled()
    assert popup.reportButton.text() == "Report when the set ends"

    for winner in [1, 2, 1, 1]:
        controller.SetWinner(controller.CurrentGameIndex(), winner)
    assert controller.SetDecided() == 1
    assert popup.reportButton.isEnabled()
    assert popup.reportButton.text() == "Report 3–1 · Tweek wins"
    # Game 5 isn't needed
    assert popup.rows[4]["score"].text() == "Not needed"
    assert not popup.rows[4]["winners"][1].isEnabled()
    assert popup.rows[3]["winners"][1].isEnabled()
    assert not any(row["highlight"].isVisible() for row in popup.rows)
    popup.close()
    print("TestSheetSetWon: OK")


def TestGamePopup():
    scoreboard, controller = Setup(scoreboardCharacters=("Pyra", "Byleth"))
    popup = GamePopup(controller, 0, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    assert popup.title.text() == "Game 1"
    assert popup.nowBadge.isVisibleTo(popup)
    assert not popup.previousButton.isEnabled()

    # A game without characters shows the scoreboard's, in italics
    combo = popup.characters[1].combos[0]
    assert ComboName(combo) == "Pyra" and combo.font().italic()
    assert popup.carriedLabel.text() == "Characters from the scoreboard"

    # Picking the winner takes them
    QTest.keyClick(popup, Qt.Key.Key_2)
    game = controller.report.games[0]
    assert game["winner"] == 2
    assert game["characters"][1] == ["Pyra"] and game["characters"][2] == ["Byleth"]
    assert popup.winnerButtons[2].isChecked() and "Won" in popup.winnerButtons[2].text()
    assert not combo.font().italic()
    assert popup.scoreLabel.text() == "0–1"

    # Changing a character changes the game's
    combo.setCurrentIndex(CHARACTERS.index("Sonic") + 1)
    assert controller.report.games[0]["characters"][1] == ["Sonic"]

    # → goes to the next game
    QTest.keyClick(popup, Qt.Key.Key_Right)
    assert popup.index == 1 and popup.title.text() == "Game 2"
    assert popup.previousButton.isEnabled()
    QTest.keyClick(popup, Qt.Key.Key_Left)
    assert popup.index == 0
    popup.close()
    print("TestGamePopup: OK")


def TestGamePopupCarriesLastGame():
    scoreboard, controller = Setup()
    controller.report.SetCharacters(0, 1, ["Diddy Kong"])
    controller.report.SetCharacters(0, 2, ["Byleth"])
    controller.SetWinner(0, 1)
    popup = GamePopup(controller, 1, scoreboard)
    popup.Open(Anchor())
    assert ComboName(popup.characters[1].combos[0]) == "Diddy Kong"
    assert popup.carriedLabel.text() == "Characters from game 1"
    # Games after the one being played don't take any
    popup.Go(1)
    assert ComboName(popup.characters[1].combos[0]) is None
    assert not popup.carriedLabel.isVisibleTo(popup)
    popup.close()
    print("TestGamePopupCarriesLastGame: OK")


def TestGamePopupOffersReport():
    scoreboard, controller = Setup(bestOf=3)
    popup = GamePopup(controller, 0, scoreboard)
    popup.Open(Anchor())
    assert not popup.setOver.isVisibleTo(popup)
    QTest.keyClick(popup, Qt.Key.Key_1)
    QTest.keyClick(popup, Qt.Key.Key_Right)
    QTest.keyClick(popup, Qt.Key.Key_1)
    assert popup.setOver.isVisibleTo(popup)
    assert popup.setOverLabel.text() == "Tweek wins the set 2–0"
    # Without a token: only the result, nothing to report to
    assert not popup.setOverButtons.isVisibleTo(popup)
    # The third game isn't needed
    QTest.keyClick(popup, Qt.Key.Key_Right)
    assert popup.index == 2 and not popup.winnerButtons[1].isEnabled()
    QTest.keyClick(popup, Qt.Key.Key_1)
    assert controller.report.games[2]["winner"] is UNDECIDED
    popup.close()

    FakeReporter.token = True
    controller.NewSet("123")
    controller.ApplySetData({"id": "123", "entrant_ids": [10, 20], "state": 2})
    controller.SetWinner(0, 2)
    controller.SetWinner(1, 2)
    popup = GamePopup(controller, 1, scoreboard)
    popup.Open(Anchor())
    assert popup.setOverLabel.text() == "MkLeo wins the set 2–0"
    assert popup.setOverButtons.isVisibleTo(popup) and popup.reportButton.isEnabled()
    popup.close()
    print("TestGamePopupOffersReport: OK")


def SaveScreenshots(folder):
    from src.Theme import Theme

    Theme.Apply()
    scoreboard, controller = Setup(scoreboardCharacters=("Pyra", "Byleth"))
    FakeReporter.token = True
    controller.NewSet("123")
    controller.ApplySetData({"id": "123", "entrant_ids": [10, 20], "state": 2})
    for i, (winner, c1, c2) in enumerate(
        [(1, "Diddy Kong", "Byleth"), (2, "Diddy Kong", "Byleth"), (1, "Pyra", "Byleth")]
    ):
        controller.report.SetCharacters(i, 1, [c1])
        controller.report.SetCharacters(i, 2, [c2])
        controller.SetWinner(i, winner)
    popup = GamesSheetPopup(controller, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "games_sheet.png"))
    popup.close()
    popup = GamePopup(controller, 3, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "game_popup.png"))
    controller.SetWinner(3, 1)
    app.processEvents()
    popup.grab().save(os.path.join(folder, "game_popup_set_won.png"))
    popup.close()


screenshots = os.path.abspath(os.path.join(repoDir, sys.argv[1])) if len(sys.argv) > 1 else None
TestSheetRows()
TestSheetSetWon()
TestGamePopup()
TestGamePopupCarriesLastGame()
TestGamePopupOffersReport()
if screenshots:
    SaveScreenshots(screenshots)
print("OK")
