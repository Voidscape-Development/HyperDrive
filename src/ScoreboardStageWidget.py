import copy
import json
import socket
import time
import traceback

import orjson
import requests
from loguru import logger
from qtpy import uic
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.StageStrikeLogic import StageStrikeLogic

from .GameAssetManager import GameAssetManager
from .Helpers.DictHelper import deep_get
from .Helpers.DirHelper import ResolvePath
from .ScoreboardManager import ScoreboardManager
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import ThemedIcon


class ScoreboardStageWidgetSignals(QObject):
    rulesets_changed = Signal()
    # A scoreboard's stage strike state changed, with its number
    strike_state_updated = Signal(int)


class Ruleset:
    def __init__(self) -> None:
        self.name = ""
        self.neutralStages = []
        self.counterpickStages = []
        self.banByMaxGames = {}
        self.useDSR = False
        self.useMDSR = False
        self.banCount = 0
        self.strikeOrder = []
        self.videogame = ""
        self.errors = []

    def Signature(self):
        # What changes the stage strike rules, to tell if it must restart
        return json.dumps(
            {
                "neutral": [
                    s.get("codename") if isinstance(s, dict) else s for s in self.neutralStages
                ],
                "counterpick": [
                    s.get("codename") if isinstance(s, dict) else s for s in self.counterpickStages
                ],
                "banByMaxGames": self.banByMaxGames,
                "useDSR": self.useDSR,
                "useMDSR": self.useMDSR,
                "banCount": self.banCount,
                "strikeOrder": self.strikeOrder,
            },
            sort_keys=True,
            default=str,
        )


class ScoreboardStageWidget(QDockWidget):
    def __init__(self, *args):
        super().__init__(*args)

        self.setWindowTitle(QApplication.translate("app", "Ruleset"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFloating(True)
        self.setWindowFlags(Qt.WindowType.Window)

        self.innerWidget = QWidget()
        self.setWidget(self.innerWidget)

        self.signals = ScoreboardStageWidgetSignals()

        # Each scoreboard has its own stage strike, using the shared ruleset
        # unless it was given its own
        self.stageStrikeLogics = {}
        self.sharedRuleset = Ruleset()
        self.customRulesets = {}
        # Scoreboard whose ruleset the editor shows, 0 for the shared one
        self.editTarget = 0
        self.loadingForm = False

        uic.loadUi(ResolvePath("src/layout/ScoreboardStage.ui"), self.innerWidget)

        self.userRulesets = []
        self.startggRulesets = []

        self.stagesModel = QStandardItemModel()
        self.neutralModel = QStandardItemModel()
        self.counterpickModel = QStandardItemModel()

        self.rulesetsBox = self.findChild(QComboBox, "rulesetSelect")
        self.rulesetsBox.activated.connect(self.LoadRuleset)

        self.stagesView = self.findChild(QListView, "allStages")
        self.stagesView.setIconSize(QSize(64, 64))

        self.stagesNeutral = self.findChild(QListView, "neutralStages")
        self.stagesNeutral.setIconSize(QSize(64, 64))

        self.stagesCounterpick = self.findChild(QListView, "counterpickStages")
        self.stagesCounterpick.setIconSize(QSize(64, 64))

        self.rulesetName = self.findChild(QLineEdit, "rulesetName")
        self.rulesetName.textEdited.connect(self.ExportCurrentRuleset)

        self.btAddNeutral = self.findChild(QPushButton, "btAddNeutral")
        self.btAddNeutral.clicked.connect(
            lambda x=None, view=self.stagesNeutral: self.AddStage(view)
        )
        self.btAddNeutral.setIcon(ThemedIcon("./assets/icons/arrow_right.svg"))

        self.btRemoveNeutral = self.findChild(QPushButton, "btRemoveNeutral")
        self.btRemoveNeutral.clicked.connect(lambda: self.RemoveStage(self.stagesNeutral))
        self.btRemoveNeutral.setIcon(ThemedIcon("./assets/icons/arrow_left.svg"))

        self.btAddCounterpick = self.findChild(QPushButton, "btAddCounterpick")
        self.btAddCounterpick.clicked.connect(
            lambda x=None, view=self.stagesCounterpick: self.AddStage(view)
        )
        self.btAddCounterpick.setIcon(ThemedIcon("./assets/icons/arrow_right.svg"))

        self.btRemoveCounterpick = self.findChild(QPushButton, "btRemoveCounterpick")
        self.btRemoveCounterpick.clicked.connect(lambda: self.RemoveStage(self.stagesCounterpick))
        self.btRemoveCounterpick.setIcon(ThemedIcon("./assets/icons/arrow_left.svg"))

        self.noDSR = self.findChild(QRadioButton, "noDSR")
        self.noDSR.clicked.connect(self.ExportCurrentRuleset)
        self.DSR = self.findChild(QRadioButton, "DSR")
        self.DSR.clicked.connect(self.ExportCurrentRuleset)
        self.MDSR = self.findChild(QRadioButton, "MDSR")
        self.MDSR.clicked.connect(self.ExportCurrentRuleset)

        self.strikeOrder = self.findChild(QLineEdit, "strikeOrder")
        self.strikeOrder.textEdited.connect(self.ExportCurrentRuleset)

        self.fixedBanCount = self.findChild(QRadioButton, "fixedBanCount")
        self.fixedBanCount.clicked.connect(self.ExportCurrentRuleset)
        self.variableBanCount = self.findChild(QRadioButton, "variableBanCount")
        self.variableBanCount.clicked.connect(self.ExportCurrentRuleset)

        self.banCount = self.findChild(QSpinBox, "banCount")
        self.banCount.valueChanged.connect(self.ExportCurrentRuleset)

        self.banCountByMaxGames = self.findChild(QLineEdit, "banCountByMaxGames")
        self.banCountByMaxGames.textEdited.connect(self.ExportCurrentRuleset)

        self.webappLabel = self.findChild(QLabel, "labelIp")
        self.webappLabel.setOpenExternalLinks(True)
        self.UpdateWebappLabel()

        self.labelValidation = self.findChild(QLabel, "labelValidation")
        self.labelValidation.setText("")

        self.SetupScoreboardSelect()

        self.signals.rulesets_changed.connect(self.LoadRulesets)
        self.LoadStartggRulesets()
        self.LoadRuleset()

        GameAssetManager.instance.signals.onLoad.connect(self.SetupOptions)

        ScoreboardManager.instance.signals.ScoreboardAdded.connect(self.ScoreboardAdded)
        ScoreboardManager.instance.signals.ScoreboardRemoved.connect(self.ScoreboardRemoved)
        ScoreboardManager.instance.signals.TabNamesChanged.connect(self.UpdateScoreboardSelect)

        StateManager.Set("score.ruleset", None)
        self.ExportCurrentRuleset()

        self.btSave = self.findChild(QPushButton, "btSave")
        self.btSave.setIcon(ThemedIcon("assets/icons/save.svg"))
        self.btDelete = self.findChild(QPushButton, "btDelete")
        self.btDelete.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.btClear = self.findChild(QPushButton, "btClear")
        self.btClear.setIcon(ThemedIcon("assets/icons/undo.svg"))

        self.rulesetName.textChanged.connect(self.UpdateBottomButtons)
        self.btSave.clicked.connect(self.SaveRuleset)
        self.btDelete.clicked.connect(self.DeleteRuleset)
        self.btClear.clicked.connect(self.ClearRuleset)

        self.stagesModel.dataChanged.connect(
            lambda topLeft, bottomRight: self.update_cloned_items()
        )

        # TournamentDataManager.instance.signals.tournament_changed.connect()
        # load tournament ruleset

    @property
    def stageStrikeLogic(self):
        # Scoreboard 1's, for code from before striking was per scoreboard
        return self.GetLogic(1)

    def GetLogic(self, number=1) -> StageStrikeLogic:
        number = int(number)
        logic = self.stageStrikeLogics.get(number)
        if logic is None:
            logic = StageStrikeLogic(number)
            logic.signals.state_updated.connect(
                lambda n=number: self.signals.strike_state_updated.emit(n)
            )
            self.stageStrikeLogics[number] = logic
            logic.SetRuleset(self.RulesetFor(number))
        return logic

    def RulesetFor(self, number) -> Ruleset:
        return self.customRulesets.get(int(number), self.sharedRuleset)

    def ApplyRuleset(self, number):
        # Restarts the scoreboard's stage strike only if its rules changed
        ruleset = self.RulesetFor(number)
        logic = self.stageStrikeLogics.get(number)
        if logic is None:
            logic = self.GetLogic(number)
        elif logic.ruleset is None or logic.ruleset.Signature() != ruleset.Signature():
            logic.SetRuleset(ruleset)
        else:
            logic.ruleset = ruleset
        StateManager.Set(f"score.{number}.ruleset", vars(ruleset))
        self.signals.strike_state_updated.emit(number)

    def SetupScoreboardSelect(self):
        row = QHBoxLayout()

        row.addWidget(QLabel(QApplication.translate("app", "Edit ruleset for")))

        self.scoreboardSelect = QComboBox()
        self.scoreboardSelect.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.scoreboardSelect.activated.connect(
            lambda _: self.SetEditTarget(self.scoreboardSelect.currentData() or 0)
        )
        row.addWidget(self.scoreboardSelect)

        self.ownRuleset = QCheckBox(QApplication.translate("app", "Use its own ruleset"))
        self.ownRuleset.setToolTip(
            QApplication.translate(
                "app",
                "Give this scoreboard a ruleset of its own instead of the one shared by all scoreboards",
            )
        )
        self.ownRuleset.clicked.connect(self.SetOwnRuleset)
        row.addWidget(self.ownRuleset)

        self.resetStrikeBt = QPushButton(QApplication.translate("app", "Restart stage strike"))
        self.resetStrikeBt.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.resetStrikeBt.clicked.connect(self.ResetStrike)
        row.addWidget(self.resetStrikeBt)

        self.innerWidget.layout().insertLayout(0, row)

        self.editingLabel = QLabel()
        self.editingLabel.setWordWrap(True)
        self.innerWidget.layout().insertWidget(1, self.editingLabel)

        self.UpdateScoreboardSelect()

    def UpdateScoreboardSelect(self):
        self.scoreboardSelect.clear()
        self.scoreboardSelect.addItem(QApplication.translate("app", "All scoreboards"), 0)
        for number in ScoreboardManager.instance.GetScoreboardNumbers():
            name = ScoreboardManager.instance.GetTabName(number)
            if number in self.customRulesets:
                name += " (" + QApplication.translate("app", "own ruleset") + ")"
            self.scoreboardSelect.addItem(name, number)

        index = self.scoreboardSelect.findData(self.editTarget)
        if index < 0:
            index = 0
        self.scoreboardSelect.setCurrentIndex(index)
        if (self.scoreboardSelect.currentData() or 0) != self.editTarget:
            self.SetEditTarget(0)
        self.UpdateTargetWidgets()

    def UpdateTargetWidgets(self):
        target = self.editTarget
        self.ownRuleset.setEnabled(target != 0)
        self.ownRuleset.setChecked(target in self.customRulesets)
        self.resetStrikeBt.setEnabled(
            target != 0 or len(ScoreboardManager.instance.GetScoreboardNumbers()) > 0
        )

        if target == 0:
            text = QApplication.translate("app", "Editing the ruleset shared by all scoreboards.")
        elif target in self.customRulesets:
            text = QApplication.translate("app", "Editing {0}'s own ruleset.").format(
                ScoreboardManager.instance.GetTabName(target)
            )
        else:
            text = QApplication.translate(
                "app", "{0} uses the shared ruleset; changes apply to every scoreboard using it."
            ).format(ScoreboardManager.instance.GetTabName(target))
        self.editingLabel.setText(text)
        self.UpdateWebappLabel()

    def UpdateWebappLabel(self):
        base = f"http://{self.GetIP()}:{SettingsManager.Get('general.webserver_port', 5500)}"
        url = base
        if self.editTarget:
            url += f"/stage-strike-app?scoreboard={self.editTarget}"
        # Character selection only: each team picks once per score (add
        # &team=1 or &team=2 for one team's page)
        charactersUrl = f"{base}/character-select?scoreboard={self.editTarget or 1}"
        self.webappLabel.setText(
            QApplication.translate("app", "Open {0} in a browser to stage strike.").format(
                f"<a href='{url}'>{url}</a>"
            )
            + "<br>"
            + QApplication.translate("app", "Open {0} for character selection only.").format(
                f"<a href='{charactersUrl}'>{charactersUrl}</a>"
            )
        )

    def SetEditTarget(self, number):
        self.editTarget = int(number)
        index = self.scoreboardSelect.findData(self.editTarget)
        if index >= 0 and index != self.scoreboardSelect.currentIndex():
            self.scoreboardSelect.setCurrentIndex(index)
        ruleset = self.RulesetFor(self.editTarget) if self.editTarget else self.sharedRuleset
        self.LoadRulesetIntoForm(ruleset)
        self.ValidateRuleset(ruleset)
        self.UpdateTargetWidgets()

    def SetOwnRuleset(self, checked):
        target = self.editTarget
        if target == 0:
            return
        if checked:
            self.customRulesets[target] = copy.deepcopy(self.sharedRuleset)
        else:
            self.customRulesets.pop(target, None)
        self.ApplyRuleset(target)
        self.UpdateScoreboardSelect()
        self.SetEditTarget(target)

    def ResetStrike(self):
        targets = (
            [self.editTarget]
            if self.editTarget
            else ScoreboardManager.instance.GetScoreboardNumbers()
        )
        for number in targets:
            self.GetLogic(number).Initialize()

    def ScoreboardAdded(self, number):
        self.customRulesets.pop(number, None)
        old = self.stageStrikeLogics.pop(number, None)
        if old is not None:
            try:
                old.signals.state_updated.disconnect()
            except RuntimeError, TypeError:
                pass
        self.ApplyRuleset(number)
        self.UpdateScoreboardSelect()

        scoreboard = ScoreboardManager.instance.GetScoreboard(number)
        if scoreboard is not None:
            scoreboard.signals.NewSetLoaded.connect(lambda n=number: self.NewSetLoaded(n))

    def NewSetLoaded(self, number):
        # The previous set's strikes would come back on the next action
        if number in self.stageStrikeLogics:
            self.stageStrikeLogics[number].Initialize()

    def ScoreboardRemoved(self, number):
        self.customRulesets.pop(number, None)
        old = self.stageStrikeLogics.pop(number, None)
        if old is not None:
            try:
                old.signals.state_updated.disconnect()
            except RuntimeError, TypeError:
                pass
        self.UpdateScoreboardSelect()

    def update_cloned_items(self):
        neutralStages = []

        for rowNeutral in range(self.neutralModel.rowCount()):
            neutralItem = self.neutralModel.item(rowNeutral)

            for rowAll in range(self.stagesModel.rowCount()):
                stageItem = self.stagesModel.item(rowAll)

                if neutralItem.data(Qt.ItemDataRole.UserRole).get("codename") == stageItem.data(
                    Qt.ItemDataRole.UserRole
                ).get("codename"):
                    neutralStages.append(stageItem)

        self.neutralModel.clear()

        for s in neutralStages:
            self.neutralModel.appendRow(s.clone())

        counterpickStages = []

        for rowNeutral in range(self.counterpickModel.rowCount()):
            neutralItem = self.counterpickModel.item(rowNeutral)

            for rowAll in range(self.stagesModel.rowCount()):
                stageItem = self.stagesModel.item(rowAll)

                if neutralItem.data(Qt.ItemDataRole.UserRole).get("codename") == stageItem.data(
                    Qt.ItemDataRole.UserRole
                ).get("codename"):
                    counterpickStages.append(stageItem)

        self.counterpickModel.clear()

        for s in counterpickStages:
            self.counterpickModel.appendRow(s.clone())

    def GetIP(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = "127.0.0.1"
        finally:
            s.close()
        return IP

    def AddStage(self, view: QListView):
        selected = self.stagesView.selectedIndexes()

        if len(selected) == 1:
            data = selected[0].data(Qt.ItemDataRole.UserRole)

            for i in range(self.stagesNeutral.model().rowCount()):
                if self.stagesNeutral.model().item(i, 0).data(Qt.ItemDataRole.UserRole).get(
                    "codename"
                ) == data.get("codename"):
                    return

            for i in range(self.stagesCounterpick.model().rowCount()):
                if self.stagesCounterpick.model().item(i, 0).data(Qt.ItemDataRole.UserRole).get(
                    "codename"
                ) == data.get("codename"):
                    return

            item = self.stagesView.model().itemFromIndex(selected[0]).clone()
            view.model().appendRow(item)
            view.model().sort(0)
            self.ExportCurrentRuleset()

    def RemoveStage(self, view: QListView):
        selected = view.selectedIndexes()

        if len(selected) == 1:
            view.model().removeRow(selected[0].row())
            self.ExportCurrentRuleset()

    def UpdateBottomButtons(self):
        found = next(
            (
                ruleset
                for ruleset in self.userRulesets
                if ruleset.get("videogame")
                == GameAssetManager.instance.selectedGame.get("codename")
                and ruleset.get("name") == self.rulesetName.text()
            ),
            None,
        )

        if found:
            self.btSave.setText(QApplication.translate("app", "Update"))
            self.btDelete.setEnabled(True)
        else:
            self.btSave.setText(QApplication.translate("app", "Save new"))
            self.btDelete.setEnabled(False)

    def SaveRuleset(self):
        found = next(
            (
                ruleset
                for ruleset in self.userRulesets
                if ruleset.get("videogame")
                == GameAssetManager.instance.selectedGame.get("codename")
                and ruleset.get("name") == self.rulesetName.text()
            ),
            None,
        )

        if found:
            self.userRulesets.remove(found)

        self.userRulesets.append(vars(self.GetCurrentRuleset(True)))

        self.SaveRulesetsFile()

    def DeleteRuleset(self):
        found = next(
            (
                ruleset
                for ruleset in self.userRulesets
                if ruleset.get("videogame")
                == GameAssetManager.instance.selectedGame.get("codename")
                and ruleset.get("name") == self.rulesetName.text()
            ),
            None,
        )

        if found:
            self.userRulesets.remove(found)
            self.SaveRulesetsFile()

    def ClearRuleset(self):
        self.LoadRuleset()

    def SaveRulesetsFile(self):
        try:
            with open("./user_data/rulesets.json", "w", encoding="utf-8") as outfile:
                json.dump(self.userRulesets, outfile, indent=4, sort_keys=True)
        except FileNotFoundError:
            logger.debug("./user_data/rulesets.json not found")
        except Exception as e:
            logger.error(traceback.format_exc())

        self.LoadRulesets()
        self.UpdateBottomButtons()

    def SetupOptions(self):
        self.rulesetsBox.clear()

        # Their stages were the previous game's
        self.customRulesets = {}
        self.editTarget = 0
        self.UpdateScoreboardSelect()

        self.ClearRuleset()
        self.LoadRulesets()

        self.stagesModel = GameAssetManager.instance.stageModel
        self.stagesModel.dataChanged.connect(
            lambda topLeft, bottomRight: self.update_cloned_items()
        )
        self.stagesModel.sort(0)
        self.stagesView.setModel(self.stagesModel)

    def LoadRulesets(self):
        rulesetsModel = QStandardItemModel()

        rulesetsModel.appendRow(QStandardItem(""))

        # Load local rulesets
        try:
            self.userRulesets = orjson.loads(
                open("./user_data/rulesets.json", encoding="utf-8").read()
            )

            for ruleset in self.userRulesets:
                if ruleset.get("videogame") == GameAssetManager.instance.selectedGame.get(
                    "codename"
                ):
                    myRuleset = Ruleset()
                    myRuleset.__dict__.update(ruleset)

                    neutral = []
                    for neutralStage in myRuleset.neutralStages:
                        stage = GameAssetManager.instance.selectedGame.get("stage_to_codename").get(
                            neutralStage, {}
                        )
                        neutral.append(stage)
                    myRuleset.neutralStages = neutral

                    counterpick = []
                    for counterpickStage in myRuleset.counterpickStages:
                        stage = GameAssetManager.instance.selectedGame.get("stage_to_codename").get(
                            counterpickStage, {}
                        )
                        counterpick.append(stage)
                    myRuleset.counterpickStages = counterpick

                    item = QStandardItem(ruleset.get("name"))
                    item.setData(myRuleset, Qt.ItemDataRole.UserRole)
                    item.setIcon(ThemedIcon("./assets/icons/db.svg"))
                    rulesetsModel.appendRow(item)
        except FileNotFoundError:
            logger.warning("./user_data/rulesets.json not found, skipping import")
            self.userRulesets = []
        except:
            self.userRulesets = []
            logger.error(traceback.format_exc())

        # Load startgg rulesets
        for ruleset in self.startggRulesets:
            myRuleset = Ruleset()
            if str(ruleset.get("videogameId")) == str(
                GameAssetManager.instance.selectedGame.get("smashgg_game_id")
            ):
                if not ruleset.get("settings"):
                    ruleset["settings"] = {}
                if not ruleset.get("settings").get("stages"):
                    ruleset["settings"]["stages"] = {}
                if ruleset.get("settings") and ruleset.get("settings", {}).get("stages", {}).get(
                    "neutral"
                ):
                    neutral = []
                    for stage in ruleset["settings"]["stages"]["neutral"]:
                        stage = next(
                            (
                                s[1]
                                for s in GameAssetManager.instance.selectedGame.get(
                                    "stage_to_codename"
                                ).items()
                                if str(s[1].get("smashgg_id")) == str(stage)
                            ),
                            {"smashgg_id": stage},
                        )
                        neutral.append(stage)
                    myRuleset.neutralStages = neutral
                if ruleset.get("settings") and ruleset.get("settings", {}).get("stages", {}).get(
                    "counterpick"
                ):
                    counterpick = []
                    for stage in ruleset["settings"]["stages"]["counterpick"]:
                        stage = next(
                            (
                                s[1]
                                for s in GameAssetManager.instance.selectedGame.get(
                                    "stage_to_codename"
                                ).items()
                                if str(s[1].get("smashgg_id")) == str(stage)
                            ),
                            {"smashgg_id": stage},
                        )
                        counterpick.append(stage)
                    myRuleset.counterpickStages = counterpick
                myRuleset.name = ruleset.get("name")

                myRuleset.strikeOrder = ruleset.get("settings", {}).get("strikeOrder")

                if deep_get(ruleset, "settings.additionalFlags") and isinstance(
                    deep_get(ruleset, "settings.additionalFlags"), dict
                ):
                    myRuleset.useDSR = (
                        ruleset.get("settings", {}).get("additionalFlags", {}).get("useDSR", False)
                    )
                    myRuleset.useMDSR = (
                        ruleset.get("settings", {}).get("additionalFlags", {}).get("useMDSR", False)
                    )

                    myRuleset.banCount = (
                        ruleset.get("settings", {}).get("additionalFlags", {}).get("banCount", 0)
                    )

                    myRuleset.banByMaxGames = (
                        ruleset.get("settings", {})
                        .get("additionalFlags", {})
                        .get("banCountByMaxGames", 0)
                    )

                item = QStandardItem(ruleset.get("name"))
                item.setData(myRuleset, Qt.ItemDataRole.UserRole)
                item.setIcon(ThemedIcon("./assets/icons/startgg.svg"))
                rulesetsModel.appendRow(item)

        # Update list
        self.rulesetsBox.setModel(rulesetsModel)

    def FindStageInModel(self, codename: str):
        for row in range(self.stagesModel.rowCount()):
            item = self.stagesModel.item(row)
            if item.data(Qt.ItemDataRole.UserRole).get("codename") == codename:
                return item

    def LoadRuleset(self):
        data = self.rulesetsBox.currentData()

        if data == None:
            data = Ruleset()

        self.LoadRulesetIntoForm(data)
        self.ExportCurrentRuleset()

    def LoadRulesetIntoForm(self, data: Ruleset):
        # Setting the fields would export the half loaded ruleset otherwise
        self.loadingForm = True
        try:
            self._LoadRulesetIntoForm(data)
        finally:
            self.loadingForm = False

    def _LoadRulesetIntoForm(self, data: Ruleset):
        self.rulesetName.setText(data.name)

        if data.useDSR:
            self.DSR.setChecked(True)
        elif data.useMDSR:
            self.MDSR.setChecked(True)
        else:
            self.noDSR.setChecked(True)

        if data.strikeOrder:
            self.strikeOrder.setText(",".join([str(s) for s in data.strikeOrder]))
        else:
            self.strikeOrder.setText("")

        if data.banCount:
            self.fixedBanCount.setChecked(True)
            self.banCount.setValue(data.banCount)
            self.banCountByMaxGames.setText("")
        elif data.banByMaxGames:
            self.variableBanCount.setChecked(True)
            self.banCountByMaxGames.setText(
                ",".join([f"{k}:{v}" for k, v in data.banByMaxGames.items()])
            )
            self.banCount.setValue(0)
        else:
            self.fixedBanCount.setChecked(True)
            self.banCount.setValue(0)
            self.banCountByMaxGames.setText("")

        self.neutralModel = QStandardItemModel()
        if data.neutralStages:
            for stage in data.neutralStages:
                item = self.FindStageInModel(stage.get("codename"))
                if item is not None:
                    self.neutralModel.appendRow(item.clone())
        self.stagesNeutral.setModel(self.neutralModel)

        self.counterpickModel = QStandardItemModel()
        if data.counterpickStages:
            for stage in data.counterpickStages:
                item = self.FindStageInModel(stage.get("codename"))
                if item is not None:
                    self.counterpickModel.appendRow(item.clone())
        self.stagesCounterpick.setModel(self.counterpickModel)

    def ExportCurrentRuleset(self):
        if self.loadingForm:
            return
        try:
            ruleset = self.GetCurrentRuleset()
            self.ValidateRuleset(ruleset)

            if self.editTarget in self.customRulesets:
                self.customRulesets[self.editTarget] = ruleset
                self.ApplyRuleset(self.editTarget)
            else:
                self.sharedRuleset = ruleset
                StateManager.Set("score.ruleset", vars(ruleset))
                for number in ScoreboardManager.instance.GetScoreboardNumbers():
                    if number not in self.customRulesets:
                        self.ApplyRuleset(number)
        except:
            logger.error(traceback.format_exc())

    def ValidateRuleset(self, ruleset: Ruleset):
        issues = []

        # Validate bans
        if len(ruleset.neutralStages) > 0:
            if sum(ruleset.strikeOrder) != len(ruleset.neutralStages) - 1:
                remaining = (len(ruleset.neutralStages) - 1) - sum(ruleset.strikeOrder)
                issues.append(
                    QApplication.translate(
                        "app",
                        "Number striked stages does not match the number of neutral stages. Should strike {0} more stage(s).",
                    ).format(remaining)
                )

        # Add errors
        for error in ruleset.errors:
            issues.append(error)

        if len(issues) == 0:
            validText = QApplication.translate("app", "The current ruleset is valid!")
            self.labelValidation.setText(f"<span style='color: green'>{validText}</span>")
        else:
            issuesText = "\n".join(issues)
            self.labelValidation.setText(f'<span style="color: red">{issuesText}</span>')

    def GetCurrentRuleset(self, forSaving=False):
        ruleset = Ruleset()

        ruleset.videogame = GameAssetManager.instance.selectedGame.get("codename")
        ruleset.name = self.rulesetName.text()

        ruleset.neutralStages = []
        for i in range(self.stagesNeutral.model().rowCount()):
            if not forSaving:
                ruleset.neutralStages.append(
                    self.stagesNeutral.model().item(i, 0).data(Qt.ItemDataRole.UserRole)
                )
            else:
                ruleset.neutralStages.append(
                    self.stagesNeutral.model()
                    .item(i, 0)
                    .data(Qt.ItemDataRole.UserRole)
                    .get("en_name")
                )

        ruleset.counterpickStages = []
        for i in range(self.stagesCounterpick.model().rowCount()):
            if not forSaving:
                ruleset.counterpickStages.append(
                    self.stagesCounterpick.model().item(i, 0).data(Qt.ItemDataRole.UserRole)
                )
            else:
                ruleset.counterpickStages.append(
                    self.stagesCounterpick.model()
                    .item(i, 0)
                    .data(Qt.ItemDataRole.UserRole)
                    .get("en_name")
                )

        ruleset.useDSR = self.DSR.isChecked()
        ruleset.useMDSR = self.MDSR.isChecked()

        if self.fixedBanCount.isChecked():
            ruleset.banCount = self.banCount.value()

        if self.variableBanCount.isChecked():
            try:
                inputText: str = self.banCountByMaxGames.text()
                ruleset.banByMaxGames = {}

                for _set in inputText.split(","):
                    split = _set.split(":")

                    if len(split) == 2:
                        key, value = split
                        ruleset.banByMaxGames[key.strip()] = int(value.strip())
            except:
                ruleset.banByMaxGames = {}
                ruleset.errors.append(
                    QApplication.translate("app", "The text for banByMaxGames is invalid.")
                )
                logger.error(traceback.format_exc())

        ruleset.strikeOrder = [
            int(n.strip())
            for n in (
                self.strikeOrder.text().split(",")
                if self.strikeOrder.text() != ""
                else "1,2,1".split(",")
            )
            if n.strip() != ""
        ]

        return ruleset

    def QueryRequests(self, url=None, type=None, headers=None, jsonParams=None, params=None):
        # Retrying forever without a pause hammered start.gg and kept this
        # thread spinning for the whole session when it was down or rate
        # limiting, so give up after a few spaced out attempts.
        for attempt in range(5):
            if attempt > 0:
                time.sleep(2**attempt)
            data = type(url, headers=headers, json=jsonParams, params=params, timeout=20)
            if data.status_code == 200:
                return orjson.loads(data.text)
        raise Exception(f"{url} returned status {data.status_code}")

    def LoadStartggRulesets(self):
        try:

            class DownloadThread(QThread):
                query = self.QueryRequests

                def run(self):
                    # An exception escaping run() aborts the whole program
                    try:
                        data = self.query(
                            "https://www.start.gg/api/-/gg_api./rulesets", type=requests.get
                        )
                    except Exception:
                        logger.error(
                            "Could not download startgg rulesets: " + traceback.format_exc()
                        )
                        return
                    rulesets = deep_get(data, "entities.ruleset")
                    open("./assets/rulesets.json", "wb").write(
                        orjson.dumps(rulesets, option=orjson.OPT_INDENT_2)
                    )
                    self.parent().startggRulesets = rulesets
                    logger.info("startgg Rulesets downloaded from startgg")
                    self.parent().signals.rulesets_changed.emit()

            downloadThread = DownloadThread(self)
            downloadThread.start()
        except Exception as e:
            logger.error(traceback.format_exc())

        # https://www.start.gg/api/-/gg_api./rulesets
        # entities > ruleset[]

        # description: null
        # eventSettings: null
        # expand: []
        # gameMode: 1
        # id: 172
        # isDefault: false
        # name: "Community CUP"
        # settings: {gameSetup: true, stages: {neutral: [311, 328, 397, 378, 387], counterpick: [497, 484, 407, 348]},…}
        # type: "standard"
        # videogameId: 1386

        # "additionalFlags":{"banCountByMaxGames":{"3":3,"5":2},"useDSR":true}
        # "additionalFlags":{"banCount":2,"useDSR":true}
        # "additionalFlags":{"useMDSR":true,"banCount":1}

        # settings -> stages -> "strikeOrder":[1,2,1]
        # "strikeOrder":[1,1,1]
