import copy
import json
import socket
import time
import traceback

import orjson
import requests
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.StageStrikeLogic import StageStrikeLogic

from .GameAssetManager import GameAssetManager
from .Helpers.DictHelper import deep_get
from .RulesetEditor import (
    STAGE_COUNTERPICK,
    STAGE_NEUTRAL,
    TILE_GAP,
    TILE_HEIGHT,
    BanEditor,
    CounterpickColor,
    ErrorColor,
    Repolish,
    SegmentedControl,
    StageGrid,
    StrikeOrderEditor,
)
from .ScoreboardManager import ScoreboardManager
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import STATUS_OK_COLOR, Theme, ThemedIcon

# Below this width, the rules column goes under the stages
NARROW_WIDTH = 1000


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
        # The form was changed since its ruleset was loaded or saved
        self.dirty = False
        self.ready = False

        self.userRulesets = []
        self.startggRulesets = []

        self.stagesModel = QStandardItemModel()

        self.BuildUI()

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

        self.rulesetName.textChanged.connect(self.UpdateBottomButtons)
        self.btSave.clicked.connect(self.SaveRuleset)
        self.btDelete.clicked.connect(self.DeleteRuleset)
        self.btClear.clicked.connect(self.ClearRuleset)

        self.ready = True
        self.ApplyStyle()
        self.UpdateBottomButtons()
        self.SetDirty(False)
        # TournamentDataManager.instance.signals.tournament_changed.connect()
        # load tournament ruleset

    # =====================================================
    # BUILDING
    # =====================================================
    def Card(self, title, note=None):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        row.addWidget(label)
        if note:
            noteLabel = QLabel(note)
            noteLabel.setObjectName("muted")
            row.addWidget(noteLabel)
        row.addStretch(1)
        layout.addLayout(row)
        return card, layout, row

    def BuildUI(self):
        outer = QVBoxLayout(self.innerWidget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Applies to: which scoreboards the ruleset is for (filled in by
        # SetupScoreboardSelect)
        self.scopeBar = QFrame()
        self.scopeBar.setObjectName("bar")
        self.scopeRow = QHBoxLayout(self.scopeBar)
        self.scopeRow.setContentsMargins(16, 8, 16, 8)
        self.scopeRow.setSpacing(10)
        outer.addWidget(self.scopeBar)

        # The ruleset: a saved or start.gg one, its name and saving it
        rulesetBar = QFrame()
        rulesetBar.setObjectName("bar")
        row = QHBoxLayout(rulesetBar)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(10)
        label = QLabel(QApplication.translate("app", "Ruleset"))
        label.setObjectName("fieldLabel")
        row.addWidget(label)
        self.rulesetsBox = QComboBox()
        self.rulesetsBox.setObjectName("rulesetSelect")
        self.rulesetsBox.setMinimumWidth(220)
        self.rulesetsBox.setToolTip(
            QApplication.translate(
                "app", "Load one of your saved rulesets or one of start.gg's for the game"
            )
        )
        self.rulesetsBox.activated.connect(self.LoadRuleset)
        label.setBuddy(self.rulesetsBox)
        row.addWidget(self.rulesetsBox)
        nameLabel = QLabel(QApplication.translate("app", "Name"))
        nameLabel.setObjectName("fieldLabel")
        row.addSpacing(6)
        row.addWidget(nameLabel)
        self.rulesetName = QLineEdit()
        self.rulesetName.setObjectName("rulesetName")
        self.rulesetName.setPlaceholderText(QApplication.translate("app", "Ruleset Name"))
        self.rulesetName.textEdited.connect(self.FormEdited)
        nameLabel.setBuddy(self.rulesetName)
        row.addWidget(self.rulesetName, 1)
        self.dirtyLabel = QLabel("● " + QApplication.translate("app", "Unsaved changes"))
        self.dirtyLabel.setObjectName("dirtyLabel")
        row.addWidget(self.dirtyLabel)
        self.btClear = QPushButton(QApplication.translate("app", "Revert"))
        self.btClear.setObjectName("btClear")
        self.btClear.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.btClear.setAutoDefault(False)
        self.btClear.setToolTip(
            QApplication.translate("app", "Load the selected ruleset again, dropping your changes")
        )
        row.addWidget(self.btClear)
        self.btDelete = QPushButton(QApplication.translate("app", "Delete"))
        self.btDelete.setObjectName("btDelete")
        self.btDelete.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.btDelete.setAutoDefault(False)
        self.btDelete.setToolTip(QApplication.translate("app", "Delete the saved ruleset"))
        row.addWidget(self.btDelete)
        self.btSave = QPushButton(QApplication.translate("app", "Save new"))
        self.btSave.setObjectName("btSave")
        self.btSave.setIcon(ThemedIcon("assets/icons/save.svg"))
        self.btSave.setDefault(True)
        self.btSave.setAutoDefault(False)
        row.addWidget(self.btSave)
        outer.addWidget(rulesetBar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)
        body = QWidget()
        self.bodyLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight, body)
        self.bodyLayout.setContentsMargins(16, 14, 16, 14)
        self.bodyLayout.setSpacing(14)
        scroll.setWidget(body)

        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(self.BuildStagesCard(), 1)
        left.addWidget(self.BuildWebappCard())
        self.bodyLayout.addLayout(left, 1)

        self.rail = QWidget()
        rail = QVBoxLayout(self.rail)
        rail.setContentsMargins(0, 0, 0, 0)
        rail.setSpacing(14)

        card, layout, _ = self.Card(
            QApplication.translate("app", "Game 1 striking"),
            QApplication.translate("app", "strike order"),
        )
        self.strikeEditor = StrikeOrderEditor()
        self.strikeEditor.changed.connect(self.FormEdited)
        layout.addWidget(self.strikeEditor)
        rail.addWidget(card)

        card, layout, _ = self.Card(
            QApplication.translate("app", "Bans after each game"),
            QApplication.translate("app", "by the game's winner"),
        )
        self.banEditor = BanEditor()
        self.banEditor.changed.connect(self.FormEdited)
        layout.addWidget(self.banEditor)
        rail.addWidget(card)

        card, layout, _ = self.Card(QApplication.translate("app", "Stage clause"))
        self.clause = SegmentedControl(
            [
                ("none", QApplication.translate("app", "No DSR")),
                ("dsr", QApplication.translate("app", "DSR")),
                ("mdsr", QApplication.translate("app", "MDSR")),
            ]
        )
        self.clause.changed.connect(lambda _: [self.UpdateClauseHelp(), self.FormEdited()])
        layout.addWidget(self.clause)
        self.clauseHelp = QLabel()
        self.clauseHelp.setObjectName("muted")
        self.clauseHelp.setWordWrap(True)
        layout.addWidget(self.clauseHelp)
        rail.addWidget(card)
        rail.addStretch(1)
        self.bodyLayout.addWidget(self.rail)
        self.UpdateClauseHelp()

    def BuildStagesCard(self):
        card, layout, title = self.Card(QApplication.translate("app", "Stages"))
        self.stageCounts = {}
        for state in (STAGE_NEUTRAL, STAGE_COUNTERPICK, "off"):
            count = QLabel()
            count.setObjectName("muted" if state == "off" else "countLabel")
            title.insertWidget(title.count() - 1, count)
            self.stageCounts[state] = count

        self.stageSearch = QLineEdit()
        self.stageSearch.setPlaceholderText(QApplication.translate("app", "Search stages"))
        self.stageSearch.setClearButtonEnabled(True)
        self.stageSearch.setMaximumWidth(200)
        title.addWidget(self.stageSearch)
        self.stageFilter = SegmentedControl(
            [
                ("all", QApplication.translate("app", "All stages")),
                ("in", QApplication.translate("app", "In ruleset")),
            ]
        )
        title.addWidget(self.stageFilter)

        hint = QLabel(
            QApplication.translate(
                "app",
                "Click a stage to change it: not used → neutral (game 1) → counterpick (the following games). Right-click to pick one.",
            )
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.stageGrid = StageGrid()
        self.stageGrid.stagesChanged.connect(self.FormEdited)
        self.stageSearch.textChanged.connect(self.stageGrid.proxy.SetText)
        self.stageFilter.changed.connect(
            lambda key: self.stageGrid.proxy.SetInRulesetOnly(key == "in")
        )
        layout.addWidget(self.stageGrid, 1)
        return card

    def BuildWebappCard(self):
        card, layout, _ = self.Card(
            QApplication.translate("app", "Stage strike page"),
            QApplication.translate("app", "Open it on a phone or tablet on the same network."),
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        self.webappLinks = []
        for row, title in enumerate(
            [
                QApplication.translate("app", "Stage strike"),
                QApplication.translate("app", "Characters only"),
            ]
        ):
            label = QLabel(title)
            label.setObjectName("muted")
            grid.addWidget(label, row, 0)
            link = QLabel()
            link.setOpenExternalLinks(True)
            link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            link.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid.addWidget(link, row, 1)
            copy = QToolButton()
            copy.setIcon(ThemedIcon("assets/icons/copy.svg"))
            copy.setIconSize(QSize(14, 14))
            copy.setToolTip(QApplication.translate("app", "Copy the link"))
            copy.setAccessibleName(copy.toolTip())
            grid.addWidget(copy, row, 2)
            self.webappLinks.append((link, copy))
        layout.addLayout(grid)
        self.webappLinks[0][1].clicked.connect(
            lambda: QApplication.clipboard().setText(self.webappUrls[0])
        )
        self.webappLinks[1][1].clicked.connect(
            lambda: QApplication.clipboard().setText(self.webappUrls[1])
        )
        self.webappUrls = ["", ""]
        return card

    def UpdateClauseHelp(self):
        self.clauseHelp.setText(
            {
                "none": QApplication.translate(
                    "app", "Any stage can be picked again during the set."
                ),
                "dsr": QApplication.translate(
                    "app", "DSR: a stage already played in the set can't be picked again."
                ),
                "mdsr": QApplication.translate(
                    "app", "MDSR: the player picking can't pick a stage they already won on."
                ),
            }[self.clause.Value()]
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < NARROW_WIDTH
        self.bodyLayout.setDirection(
            QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        )
        if narrow:
            self.rail.setMinimumWidth(0)
            self.rail.setMaximumWidth(16777215)
        else:
            self.rail.setFixedWidth(370)
        # Stacked, the page scrolls: room for more rows of stages
        self.stageGrid.setMinimumHeight((TILE_HEIGHT + TILE_GAP) * (3 if narrow else 2))

    # =====================================================
    # STYLE
    # =====================================================
    def ApplyStyle(self):
        colors = Theme.Colors()
        c = {k: v.name() for k, v in colors.items()}
        r = Theme.Radius()
        ok = STATUS_OK_COLOR
        error = ErrorColor(colors).name()
        counterpick = CounterpickColor(colors).name()
        self.innerWidget.setStyleSheet(
            f"""
            QFrame#bar {{ border-bottom: 1px solid {c["raised"]}; }}
            QFrame#card {{
                background: {c["surface"]}; border: 1px solid {c["raised"]};
                border-radius: {r + 4}px;
            }}
            QLabel#cardTitle {{ font-weight: bold; }}
            QLabel#fieldLabel {{ font-weight: bold; color: {c["muted"]}; }}
            QLabel#muted {{ color: {c["muted"]}; }}
            QLabel#countLabel {{ font-weight: bold; }}
            QLabel#dirtyLabel {{ color: {c["accentText"]}; }}
            QLabel#validationPill {{
                border-radius: 12px; font-weight: bold;
                border: 1px solid {c["border"]}; color: {c["muted"]};
            }}
            QLabel#validationPill[status="ok"] {{ border-color: {ok}; color: {ok}; }}
            QLabel#validationPill[status="bad"] {{ border-color: {error}; color: {error}; }}
            QFrame#segmented {{
                background: {c["window"]}; border: 1px solid {c["raised"]};
                border-radius: {r + 2}px;
            }}
            QPushButton#segment {{
                background: transparent; border: 1px solid transparent; color: {c["muted"]};
                font-weight: bold; padding: 3px 10px;
            }}
            QPushButton#segment:hover {{ color: {c["text"]}; }}
            QPushButton#segment:checked {{
                background: {c["raised"]}; border-color: {c["border"]}; color: {c["text"]};
            }}
            QFrame#strikeRow {{
                background: {c["window"]}; border: 1px solid {c["raised"]};
                border-radius: {r + 2}px;
            }}
            QLabel#strikerA {{
                background: {c["text"]}; color: {c["window"]}; border-radius: 5px;
                font-weight: bold;
            }}
            QLabel#strikerB {{
                background: {c["raised"]}; color: {c["text"]}; border: 1px solid {c["muted"]};
                border-radius: 5px; font-weight: bold;
            }}
            QLabel#stepValue {{ font-weight: bold; }}
            QToolButton#stepButton {{ min-width: 18px; font-weight: bold; }}
            QToolButton#flatButton {{ background: transparent; border: 1px solid transparent; }}
            QToolButton#flatButton:hover {{ border-color: {c["border"]}; }}
            QPushButton#dashedButton {{
                background: transparent; border: 1px dashed {c["border"]}; color: {c["muted"]};
            }}
            QPushButton#dashedButton:hover {{ border-color: {c["accent"]}; color: {c["text"]}; }}
            QListView {{ background: transparent; border: none; }}
            """
        )
        self.stageCounts[STAGE_NEUTRAL].setStyleSheet(f"color: {c['accentText']};")
        self.stageCounts[STAGE_COUNTERPICK].setStyleSheet(f"color: {counterpick};")
        self.stageGrid.SetColors(colors)
        self.strikeEditor.Refresh()
        self.UpdateWebappLabel()

    def changeEvent(self, event):
        # The theme changed
        if event.type() == QEvent.Type.PaletteChange and getattr(self, "ready", False):
            self.ApplyStyle()
        super().changeEvent(event)

    # =====================================================
    # STAGE STRIKE LOGIC
    # =====================================================
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

    # =====================================================
    # =====================================================
    # SCOREBOARD TARGETS
    # =====================================================
    def SetupScoreboardSelect(self):
        row = self.scopeRow

        label = QLabel(QApplication.translate("app", "Applies to"))
        label.setObjectName("fieldLabel")
        row.addWidget(label)

        self.scoreboardSelect = QComboBox()
        self.scoreboardSelect.setMinimumWidth(200)
        self.scoreboardSelect.setToolTip(QApplication.translate("app", "Edit ruleset for"))
        self.scoreboardSelect.activated.connect(
            lambda _: self.SetEditTarget(self.scoreboardSelect.currentData() or 0)
        )
        label.setBuddy(self.scoreboardSelect)
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

        self.editingLabel = QLabel()
        self.editingLabel.setObjectName("muted")
        self.editingLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.editingLabel, 1)

        self.validationPill = QLabel()
        self.validationPill.setObjectName("validationPill")
        self.validationPill.setContentsMargins(12, 3, 12, 3)
        row.addWidget(self.validationPill)

        self.resetStrikeBt = QPushButton(QApplication.translate("app", "Restart stage strike"))
        self.resetStrikeBt.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.resetStrikeBt.setAutoDefault(False)
        self.resetStrikeBt.clicked.connect(self.ResetStrike)
        row.addWidget(self.resetStrikeBt)

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
        self.editingLabel.setToolTip(text)
        self.UpdateWebappLabel()

    def SetEditTarget(self, number):
        self.editTarget = int(number)
        index = self.scoreboardSelect.findData(self.editTarget)
        if index >= 0 and index != self.scoreboardSelect.currentIndex():
            self.scoreboardSelect.setCurrentIndex(index)
        ruleset = self.RulesetFor(self.editTarget) if self.editTarget else self.sharedRuleset
        self.LoadRulesetIntoForm(ruleset)
        self.ValidateRuleset(ruleset)
        self.SetDirty(False)
        self.UpdateTargetWidgets()

    def ScoreboardAdded(self, number):
        self.customRulesets.pop(number, None)
        old = self.stageStrikeLogics.pop(number, None)
        if old is not None:
            try:
                old.signals.state_updated.disconnect()
            except (RuntimeError, TypeError):
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
            except (RuntimeError, TypeError):
                pass
        self.UpdateScoreboardSelect()

    # =====================================================
    # WEB APP
    # =====================================================
    def UpdateWebappLabel(self):
        base = f"http://{self.GetIP()}:{SettingsManager.Get('general.webserver_port', 5500)}"
        url = base
        if self.editTarget:
            url += f"/stage-strike-app?scoreboard={self.editTarget}"
        # Character selection only: each team picks once per score (add
        # &team=1 or &team=2 for one team's page)
        charactersUrl = f"{base}/character-select?scoreboard={self.editTarget or 1}"
        self.webappUrls = [url, charactersUrl]
        for (link, _), target in zip(self.webappLinks, self.webappUrls):
            link.setText(f"<a href='{target}'>{target}</a>")
            link.setToolTip(target)

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

    # =====================================================
    # EDITING THE RULESET
    # =====================================================
    def SetupOptions(self):
        self.rulesetsBox.clear()

        # Their stages were the previous game's
        self.customRulesets = {}
        self.editTarget = 0

        self.stagesModel = GameAssetManager.instance.stageModel
        self.stagesModel.sort(0)
        self.stageGrid.SetSourceModel(self.stagesModel)

        self.UpdateScoreboardSelect()

        self.ClearRuleset()
        self.LoadRulesets()

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
        self.btSave.setEnabled(bool(self.rulesetName.text().strip()))

    def FormEdited(self, *args):
        if self.loadingForm:
            return
        self.SetDirty(True)
        self.ExportCurrentRuleset()

    def SetDirty(self, dirty):
        self.dirty = dirty
        self.dirtyLabel.setVisible(dirty)
        self.btClear.setEnabled(dirty)

    def FindStageInModel(self, codename: str):
        for row in range(self.stagesModel.rowCount()):
            item = self.stagesModel.item(row)
            if item.data(Qt.ItemDataRole.UserRole).get("codename") == codename:
                return item

    def ClearRuleset(self):
        self.LoadRuleset()

    # =====================================================
    # SAVED RULESETS
    # =====================================================
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
        # The saved ruleset is the one selected: reverting goes back to it
        index = self.rulesetsBox.findText(self.rulesetName.text())
        if index >= 0:
            self.rulesetsBox.setCurrentIndex(index)
        self.SetDirty(False)

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

    def LoadRulesets(self):
        selected = self.rulesetsBox.currentText()
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

        # Update list, keeping the selected ruleset
        self.rulesetsBox.setModel(rulesetsModel)
        index = self.rulesetsBox.findText(selected) if selected else -1
        self.rulesetsBox.setCurrentIndex(max(index, 0))

    def LoadRuleset(self):
        data = self.rulesetsBox.currentData()

        if data == None:
            data = Ruleset()

        self.LoadRulesetIntoForm(data)
        self.ExportCurrentRuleset()
        self.SetDirty(False)

    def LoadRulesetIntoForm(self, data: Ruleset):
        # Setting the fields would export the half loaded ruleset otherwise
        self.loadingForm = True
        try:
            self._LoadRulesetIntoForm(data)
        finally:
            self.loadingForm = False

    def _LoadRulesetIntoForm(self, data: Ruleset):
        self.rulesetName.setText(data.name or "")

        if data.useDSR:
            self.clause.SetValue("dsr")
        elif data.useMDSR:
            self.clause.SetValue("mdsr")
        else:
            self.clause.SetValue("none")
        self.UpdateClauseHelp()

        # Without one, the usual 1,2,1
        self.strikeEditor.SetOrder(
            [int(s) for s in data.strikeOrder] if data.strikeOrder else [1, 2, 1]
        )

        self.banEditor.SetValues(data.banCount or 0, data.banByMaxGames or {})

        def codenames(stages):
            found = []
            for stage in stages or []:
                codename = stage.get("codename") if isinstance(stage, dict) else None
                if self.FindStageInModel(codename) is not None:
                    found.append(codename)
            return found

        self.stageGrid.SetStages(codenames(data.neutralStages), codenames(data.counterpickStages))

    # =====================================================
    # CURRENT RULESET
    # =====================================================
    def GetCurrentRuleset(self, forSaving=False):
        ruleset = Ruleset()

        ruleset.videogame = GameAssetManager.instance.selectedGame.get("codename")
        ruleset.name = self.rulesetName.text()

        def stages(codenames):
            found = []
            for codename in codenames:
                item = self.FindStageInModel(codename)
                if item is not None:
                    data = item.data(Qt.ItemDataRole.UserRole)
                    found.append(data.get("en_name") if forSaving else data)
            return found

        ruleset.neutralStages = stages(self.stageGrid.neutral)
        ruleset.counterpickStages = stages(self.stageGrid.counterpick)

        clause = self.clause.Value()
        ruleset.useDSR = clause == "dsr"
        ruleset.useMDSR = clause == "mdsr"

        ruleset.banCount, ruleset.banByMaxGames = self.banEditor.Values()

        ruleset.strikeOrder = self.strikeEditor.Order()

        return ruleset

    def ValidateRuleset(self, ruleset: Ruleset):
        neutral = len(ruleset.neutralStages)
        counterpick = len(ruleset.counterpickStages)
        self.stageCounts[STAGE_NEUTRAL].setText(
            QApplication.translate("app", "{0} neutral").format(neutral)
        )
        self.stageCounts[STAGE_COUNTERPICK].setText(
            QApplication.translate("app", "{0} counterpick").format(counterpick)
        )
        self.stageCounts["off"].setText(
            QApplication.translate("app", "{0} not used").format(
                max(self.stagesModel.rowCount() - neutral - counterpick, 0)
            )
        )

        self.strikeEditor.SetNeutralCount(neutral)
        issues = []

        # Validate bans
        issue = self.strikeEditor.Issue()
        if issue:
            issues.append(issue)

        # Add errors
        for error in ruleset.errors:
            issues.append(error)

        if issues:
            status = "bad"
            text = (
                QApplication.translate("app", "1 issue to fix")
                if len(issues) == 1
                else QApplication.translate("app", "{0} issues to fix").format(len(issues))
            )
        elif neutral == 0 and counterpick == 0:
            status = ""
            text = QApplication.translate("app", "No stages yet")
        else:
            status = "ok"
            text = QApplication.translate("app", "The current ruleset is valid!")
        self.validationPill.setText("● " + text)
        self.validationPill.setToolTip("\n".join(issues))
        self.validationPill.setProperty("status", status)
        Repolish(self.validationPill)

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

    # =====================================================
    # START.GG RULESETS
    # =====================================================
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
