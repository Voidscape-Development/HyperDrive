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
from qtpy.QtGui import QColor, QIcon, QPixmap, QStandardItem, QStandardItemModel
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

app = QApplication.instance() or QApplication(sys.argv)

repoDir = os.path.abspath(".")
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
os.chdir(workDir)
# Theme reads the icons from the repository
os.symlink(os.path.join(repoDir, "assets"), os.path.join(workDir, "assets"))

CHARACTERS = ["Diddy Kong", "Byleth", "Pyra", "Sonic", "Pikachu", "Mr. Game & Watch", "Steve"]
COLORS = ["#8d6e63", "#26a69a", "#e53935", "#1e88e5", "#fdd835", "#424242", "#7cb342"]
# A tag game's, four characters a player
TAG_CHARACTERS = [
    "Iron Man",
    "Storm",
    "Ms. Marvel",
    "Doctor Doom",
    "Ryu",
    "Chun-Li",
    "Ken",
    "Akuma",
]
TAG_COLORS = [
    "#c62828",
    "#eceff1",
    "#3949ab",
    "#2e7d32",
    "#f5f5f5",
    "#1565c0",
    "#ef6c00",
    "#4a148c",
]
CHARACTERS += TAG_CHARACTERS
COLORS += TAG_COLORS


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
        for name, color in zip(CHARACTERS, COLORS):
            icon = QPixmap(24, 24)
            icon.fill(QColor(color))
            item = QStandardItem(QIcon(icon), name)
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
from src.GamesPopup import (
    WINNER_NAME_WIDTH,
    BoldMetrics,
    GamePopup,
    GamesSheetPopup,
    IconCharacterCombo,
)


class FakeColorButton:
    def __init__(self, color):
        self._color = color

    def color(self):
        return self._color


class FakeSpin:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class FakeScoreboard(QWidget):
    def __init__(self, players=1, characters=1):
        super().__init__()
        self.scoreboardNumber = 1
        self.team1playerWidgets = [None] * players
        self.charNumber = FakeSpin(characters)
        self.colorButton1 = FakeColorButton("#d93a3a")
        self.colorButton2 = FakeColorButton("#2e6fe0")


def Setup(bestOf=5, scoreboardCharacters=(None, None), names=("Tweek", "MkLeo"), characters=1):
    """scoreboardCharacters: each team's character, or list of characters
    (one per player) for doubles. characters: characters a player, each
    player's in a row in the lists."""
    FakeState.data = {
        "score.1.team.1.mergedTeamName": names[0],
        "score.1.team.2.mergedTeamName": names[1],
    }
    players = 1
    perPlayer = characters
    for team, characters in enumerate(scoreboardCharacters, start=1):
        if not isinstance(characters, (list, tuple)):
            characters = [characters]
        players = max(players, len(characters) // perPlayer)
        for i, character in enumerate(characters):
            p, c = divmod(i, perPlayer)
            if character:
                FakeState.data[f"score.1.team.{team}.player.{p + 1}.character.{c + 1}"] = {
                    "en_name": character
                }
    FakeReporter.token = False
    scoreboard = FakeScoreboard(players, perPlayer)
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
    # The buttons say "Won": the columns' headers name the teams
    assert [b.text() for b in popup.rows[0]["winners"].values()] == ["Won", "Won"]
    assert popup.rows[0]["winners"][2].toolTip() == "Won by MkLeo"
    assert popup.teamHeaders[1].text() == "Tweek"
    # One player a team: dropdowns with the characters' names
    assert not isinstance(popup.rows[0]["characters"][1].combos[0], IconCharacterCombo)

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


def TestDoubles():
    scoreboard, controller = Setup(
        scoreboardCharacters=(["Pyra", "Mr. Game & Watch"], ["Byleth", "Steve"]),
        names=("Tweek / Sparg0 / Somebody", "MkLeo / Light"),
    )
    sheet = GamesSheetPopup(controller, scoreboard)
    sheet.Open(Anchor())
    # Only the characters' icons, named in their tooltips
    combos = sheet.rows[0]["characters"][1].combos
    assert len(combos) == 2 and all(isinstance(c, IconCharacterCombo) for c in combos)
    assert combos[1].toolTip() == "Mr. Game & Watch" and combos[1].dimmed
    assert combos[1].width() < 80
    assert sheet.width() < 600, sheet.width()
    sheet.rows[0]["winners"][1].click()
    game = controller.report.games[0]
    assert game["characters"][1] == ["Pyra", "Mr. Game & Watch"]
    assert not combos[1].dimmed
    sheet.close()

    popup = GamePopup(controller, 1, scoreboard)
    popup.Open(Anchor())
    # One under the other, under the team's button
    combos = popup.characters[1].combos
    assert isinstance(popup.characters[1].layout(), QVBoxLayout)
    assert combos[1].y() > combos[0].y() and combos[1].x() == combos[0].x()
    # A long name ends in …, the whole name in the tooltip
    button = popup.winnerButtons[1]
    assert button.text().endswith("…") and button.toolTip() == "Tweek / Sparg0 / Somebody"
    assert BoldMetrics(button).horizontalAdvance(button.text()) <= WINNER_NAME_WIDTH
    assert popup.winnerButtons[2].text() == "MkLeo / Light"
    assert popup.width() <= 420, popup.width()
    popup.close()
    print("TestDoubles: OK")


def TestCharactersPerPlayer():
    scoreboard, controller = Setup(
        scoreboardCharacters=(TAG_CHARACTERS[:4], TAG_CHARACTERS[4:]),
        names=("Justin Wong", "Daigo"),
        characters=4,
    )
    assert controller.CharactersPerTeam() == 4
    assert controller.ScoreboardCharacters(1) == TAG_CHARACTERS[:4]

    sheet = GamesSheetPopup(controller, scoreboard)
    sheet.Open(Anchor())
    combos = sheet.rows[0]["characters"][2].combos
    assert len(combos) == 4 and all(isinstance(c, IconCharacterCombo) for c in combos)
    assert [c.toolTip() for c in combos] == TAG_CHARACTERS[4:]
    assert sheet.width() < 600, sheet.width()
    # The game takes all four, and start.gg gets them all for the player
    sheet.rows[0]["winners"][2].click()
    assert controller.report.games[0]["characters"][2] == TAG_CHARACTERS[4:]
    sheet.close()

    popup = GamePopup(controller, 1, scoreboard)
    popup.Open(Anchor())
    assert len(popup.characters[1].combos) == 4
    assert ComboName(popup.characters[1].combos[3]) == "Doctor Doom"
    assert popup.width() <= 420, popup.width()
    popup.close()
    print("TestCharactersPerPlayer: OK")


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

    scoreboard, controller = Setup(
        scoreboardCharacters=(["Pyra", "Mr. Game & Watch"], ["Byleth", "Steve"]),
        names=("Tweek / Sparg0", "MkLeo / Light"),
    )
    for i, (winner, c1, c2) in enumerate(
        [
            (1, ["Diddy Kong", "Pikachu"], ["Byleth", "Sonic"]),
            (2, ["Diddy Kong", "Pikachu"], ["Byleth", "Steve"]),
        ]
    ):
        controller.report.SetCharacters(i, 1, c1)
        controller.report.SetCharacters(i, 2, c2)
        controller.SetWinner(i, winner)
    popup = GamesSheetPopup(controller, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "games_sheet_doubles.png"))
    popup.close()
    popup = GamePopup(controller, 2, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "game_popup_doubles.png"))
    popup.close()

    scoreboard, controller = Setup(
        scoreboardCharacters=(TAG_CHARACTERS[:4], TAG_CHARACTERS[4:]),
        names=("Justin Wong", "Daigo"),
        characters=4,
    )
    for i, winner in enumerate([1, 2]):
        controller.SetWinner(i, winner)
    popup = GamesSheetPopup(controller, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "games_sheet_tag.png"))
    popup.close()
    popup = GamePopup(controller, 2, scoreboard)
    popup.Open(Anchor())
    app.processEvents()
    popup.grab().save(os.path.join(folder, "game_popup_tag.png"))
    popup.close()


screenshots = os.path.abspath(os.path.join(repoDir, sys.argv[1])) if len(sys.argv) > 1 else None
TestSheetRows()
TestSheetSetWon()
TestGamePopup()
TestGamePopupCarriesLastGame()
TestGamePopupOffersReport()
TestDoubles()
TestCharactersPerPlayer()
if screenshots:
    SaveScreenshots(screenshots)
print("OK")
