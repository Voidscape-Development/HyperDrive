# Checks the Ruleset tab: loading a start.gg ruleset into it (its stages in
# their order, strike order, bans by best-of, stage clause), changing stages
# from the grid, the strike order's validation, saving, reverting and what
# it sends to the scoreboards.
# Run from the repository root: python test/test_ruleset_widget.py
# (with an optional folder to save screenshots of the tab to)
import contextlib
import json
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

from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtGui import QColor, QPixmap, QStandardItem, QStandardItemModel
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

screenshots = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None
repoDir = os.path.abspath(".")
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
os.chdir(workDir)
# Theme reads the icons from the repository
os.symlink(os.path.join(repoDir, "assets"), os.path.join(workDir, "assets"))

# (name, start.gg id, color)
STAGES = [
    ("Battlefield", 311, "#2b3a55"),
    ("Small Battlefield", 484, "#31406a"),
    ("Final Destination", 328, "#2a2140"),
    ("Pokémon Stadium 2", 378, "#20453f"),
    ("Smashville", 387, "#3d4a2a"),
    ("Town and City", 397, "#4a3a28"),
    ("Hollow Bastion", 497, "#3a2a45"),
    ("Kalos Pokémon League", 348, "#2a3f4f"),
    ("Yoshi's Story", 407, "#4a2f3a"),
    ("Lylat Cruise", 359, "#23324a"),
    ("Northern Cave", 513, "#2f2f3a"),
    ("Yoshi's Island", 408, "#3e4a2a"),
]


def Codename(name):
    return name.lower().replace(" ", "_").replace("'", "").replace("é", "e")


stageImages = os.path.join(workDir, "stages")
os.makedirs(stageImages)
stageToCodename = {}
for name, smashggId, color in STAGES:
    image = QPixmap(320, 180)
    image.fill(QColor(color))
    path = os.path.join(stageImages, Codename(name) + ".png")
    image.save(path)
    stageToCodename[name] = {
        "name": name,
        "en_name": name,
        "display_name": name,
        "codename": Codename(name),
        "smashgg_id": smashggId,
        "path": path,
    }


class FakeAssetSignals(QObject):
    onLoad = Signal()


class FakeAssetManager:
    instance = None

    def __init__(self):
        self.signals = FakeAssetSignals()
        self.selectedGame = {
            "codename": "ssbu",
            "smashgg_game_id": 1386,
            "stage_to_codename": stageToCodename,
        }
        self.stageModel = QStandardItemModel()
        for stage in stageToCodename.values():
            item = QStandardItem(stage["display_name"])
            item.setData(stage, Qt.ItemDataRole.UserRole)
            self.stageModel.appendRow(item)


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


class FakeScoreboardSignals(QObject):
    ScoreboardAdded = Signal(int)
    ScoreboardRemoved = Signal(int)
    TabNamesChanged = Signal()


class FakeGameReport:
    def SetStage(self, index, codename):
        pass


class FakeScoreboard:
    def __init__(self):
        self.gameReport = FakeGameReport()


class FakeScoreboardManager:
    instance = None

    def __init__(self):
        self.signals = FakeScoreboardSignals()
        self.numbers = [1, 2]
        self.scoreboardholder = [FakeScoreboard(), FakeScoreboard()]

    def GetScoreboardNumbers(self):
        return list(self.numbers)

    def GetTabName(self, number):
        return ["Main stream", "Side stream"][number - 1]

    def GetScoreboard(self, number):
        return self.scoreboardholder[number - 1]


FakeScoreboardManager.instance = FakeScoreboardManager()
module = types.ModuleType("src.ScoreboardManager")
module.ScoreboardManager = FakeScoreboardManager
sys.modules["src.ScoreboardManager"] = module

from src.ScoreboardStageWidget import ScoreboardStageWidget  # noqa: E402
from src.Theme import Theme  # noqa: E402

# No downloading start.gg's rulesets: one like theirs is given below
ScoreboardStageWidget.LoadStartggRulesets = lambda self: None
Theme.Apply()

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
        print("FAIL:", message)


def shot(widget, name):
    if screenshots:
        os.makedirs(screenshots, exist_ok=True)
        app.processEvents()
        widget.grab().save(os.path.join(screenshots, name))


widget = ScoreboardStageWidget()
widget.resize(1280, 940)
widget.show()
FakeAssetManager.instance.signals.onLoad.emit()
app.processEvents()

grid = widget.stageGrid
check(grid.model().rowCount() == len(STAGES), "every stage is in the grid")
check(widget.validationPill.text().endswith("No stages yet"), "empty ruleset has no stages")

# A start.gg ruleset
widget.startggRulesets = [
    {
        "videogameId": 1386,
        "name": "Genesis",
        "settings": {
            "stages": {
                # Not in alphabetical order: the order is kept
                "neutral": [378, 311, 328, 484, 387],
                "counterpick": [397, 497, 348, 407],
            },
            "strikeOrder": None,
            "additionalFlags": {"banCountByMaxGames": {"3": 3, "5": 2}, "useDSR": True},
        },
    }
]
widget.signals.rulesets_changed.emit()
index = widget.rulesetsBox.findText("Genesis")
check(index > 0, "start.gg ruleset listed")
widget.rulesetsBox.setCurrentIndex(index)
widget.rulesetsBox.activated.emit(index)
app.processEvents()

check(
    grid.neutral
    == [
        "pokemon_stadium_2",
        "battlefield",
        "final_destination",
        "small_battlefield",
        "smashville",
    ],
    "neutral stages loaded in their order",
)
check(len(grid.counterpick) == 4, "counterpick stages loaded")
check(widget.strikeEditor.Order() == [1, 2, 1], "no strike order gives 1,2,1")
check(widget.clause.Value() == "dsr", "DSR loaded")
check(widget.banEditor.mode.Value() == "bestOf", "bans by best-of loaded")
check(widget.banEditor.Values() == (0, {"3": 3, "5": 2}), "bans by best-of values")
check(not widget.dirty and widget.dirtyLabel.isHidden(), "a loaded ruleset has no changes")
check(widget.validationPill.property("status") == "ok", "loaded ruleset is valid")
check(widget.stageCounts["neutral"].text() == "5 neutral", "neutral count shown")
check(widget.stageCounts["off"].text() == "3 not used", "unused count shown")

shared = FakeState.data["score.ruleset"]
check(shared["useDSR"] and shared["strikeOrder"] == [1, 2, 1], "shared ruleset exported")
check(
    [s["codename"] for s in shared["neutralStages"]][0] == "pokemon_stadium_2",
    "exported stages keep their order",
)
check(FakeState.data.get("score.1.ruleset") is not None, "scoreboards get the ruleset")
shot(widget, "ruleset.png")

# Clicking a tile cycles it: not used → neutral
lylat = next(
    grid.model().index(row, 0)
    for row in range(grid.model().rowCount())
    if grid.model().index(row, 0).data() == "Lylat Cruise"
)
QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(lylat).center())
app.processEvents()
check(grid.StateOf("lylat_cruise") == "neutral", "clicked tile becomes neutral")
# Like the lists before: adding a stage sorts them by name
check(grid.neutral[:2] == ["battlefield", "final_destination"], "list sorted by name on adding")
check(widget.dirty and not widget.dirtyLabel.isHidden(), "a change shows unsaved changes")
check(widget.validationPill.property("status") == "bad", "6 neutral stages with 1,2,1 is wrong")
check("Strike 1 more" in widget.strikeEditor.message.text(), "strike message says what to do")
check(widget.strikeEditor.pips.pips[-2:] == ["left", "play"], "pips show the missing strike")
shot(widget, "ruleset_issue.png")

# Fixing the strike order
widget.strikeEditor.AddStep()
check(widget.strikeEditor.Order() == [1, 2, 1, 1], "a step added")
check(widget.validationPill.property("status") == "ok", "1,2,1,1 fits 6 neutral stages")
check(FakeState.data["score.ruleset"]["strikeOrder"] == [1, 2, 1, 1], "strike order exported")

# Neutral → counterpick → not used
grid.Cycle("lylat_cruise")
check(grid.StateOf("lylat_cruise") == "counterpick", "neutral becomes counterpick")
grid.Cycle("lylat_cruise")
check(grid.StateOf("lylat_cruise") == "off", "counterpick becomes not used")
widget.strikeEditor.RemoveStep(3)
app.processEvents()
check(widget.validationPill.property("status") == "ok", "back to 1,2,1")

# Only the stages in the ruleset, and searching
widget.stageFilter.buttons["in"].click()
check(grid.model().rowCount() == 9, "in ruleset filter shows 9 stages")
widget.stageFilter.buttons["all"].click()
widget.stageSearch.setText("battle")
check(grid.model().rowCount() == 2, "search finds the battlefields")
widget.stageSearch.setText("")

# Bans: the same every set
widget.banEditor.mode.buttons["fixed"].click()
widget.banEditor.banCount.Step(1)
widget.banEditor.banCount.Step(1)
check(widget.banEditor.Values() == (2, {}), "fixed ban count")
check(FakeState.data["score.ruleset"]["banCount"] == 2, "ban count exported")

# MDSR
widget.clause.buttons["mdsr"].click()
ruleset = widget.GetCurrentRuleset()
check(ruleset.useMDSR and not ruleset.useDSR, "MDSR picked")
check("won on" in widget.clauseHelp.text(), "MDSR explained")

# Saving it as a new ruleset
widget.rulesetName.setText("My ruleset")
widget.rulesetName.textEdited.emit("My ruleset")
check(widget.btSave.text() == "Save new", "a new name saves a new ruleset")
widget.btSave.click()
saved = json.load(open("./user_data/rulesets.json", encoding="utf-8"))
check(len(saved) == 1 and saved[0]["name"] == "My ruleset", "ruleset saved")
check(saved[0]["neutralStages"][0] == "Battlefield", "saved with stage names, in order")
check(saved[0]["banCount"] == 2 and saved[0]["useMDSR"], "saved rules")
check(widget.rulesetsBox.currentText() == "My ruleset", "saved ruleset selected")
check(widget.btSave.text() == "Update" and widget.btDelete.isEnabled(), "saved can be updated")
check(not widget.dirty, "nothing unsaved after saving")

# Reverting goes back to the saved ruleset
grid.Cycle("northern_cave")
check(widget.btClear.isEnabled(), "revert is on with changes")
widget.btClear.click()
check(grid.StateOf("northern_cave") == "off", "revert drops the change")
check(grid.neutral[0] == "battlefield", "revert keeps the saved order")
check(widget.banEditor.Values() == (2, {}), "revert keeps the saved bans")
check(not widget.dirty and not widget.btClear.isEnabled(), "nothing to revert after reverting")

# A scoreboard with its own ruleset
widget.SetEditTarget(2)
widget.ownRuleset.click()
check(2 in widget.customRulesets, "scoreboard 2 has its own ruleset")
widget.clause.buttons["none"].click()
check(not widget.customRulesets[2].useMDSR, "its own ruleset changed")
check(widget.sharedRuleset.useMDSR, "the shared ruleset didn't change")
check("Side stream" in widget.editingLabel.text(), "says whose ruleset it is")
check("scoreboard=2" in widget.webappUrls[0], "stage strike link for scoreboard 2")
widget.SetEditTarget(0)

# Narrow: the rules go under the stages
widget.resize(760, 1200)
app.processEvents()
check(
    widget.bodyLayout.direction() == widget.bodyLayout.Direction.TopToBottom,
    "narrow tab stacks the rules column",
)
shot(widget, "ruleset_narrow.png")

if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("All ruleset checks passed")
