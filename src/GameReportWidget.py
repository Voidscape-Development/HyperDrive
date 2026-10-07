# The scoreboard's Games window: the result, stage and characters of each game
# of the set, which the scoreboard's score follows, and reporting the set to
# start.gg (see StartGGReporter).
#
# Games can be sent to start.gg as they're played, so the set shows live on
# start.gg, or only when the set is reported (Settings > start.gg Reporting).
import time
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .GameAssetManager import GameAssetManager
from .GameReport import *
from .SettingsManager import SettingsManager
from .StartGGReporter import *
from .StateManager import StateManager


def LiveUpdates():
    return SettingsManager.Get("startgg_reporting.live_updates", True)


def MarkInProgress():
    return SettingsManager.Get("startgg_reporting.mark_in_progress", True)


def ConfirmReport():
    return SettingsManager.Get("startgg_reporting.confirm_report", True)


def CharacterIndex(combo, key):
    """Row of a character in the character model, by its key."""
    if not key:
        return 0
    for i in range(1, combo.count()):
        data = combo.itemData(i, Qt.ItemDataRole.UserRole) or {}
        if data.get("en_name") == key:
            return i
    return 0


class GameReportSignals(QObject):
    # Team 1's and team 2's score, from the games
    scoreChanged = Signal(int, int)
    # The set was reported to start.gg (set id)
    setReported = Signal(str)


class GameReportWidget(QWidget):
    def __init__(self, scoreboard, *args):
        super().__init__(*args)
        self.scoreboard = scoreboard
        self.number = scoreboard.scoreboardNumber
        self.signals = GameReportSignals()

        self.report = GameReport()
        self.setId = None
        self.entrantIds = None
        self.setState = None
        # Changed here since start.gg's games were last taken
        self.dirty = False
        self.markedInProgress = set()
        self.lastRequest = None
        self.lastSent = 0
        self.rows = []
        self.rebuilding = False

        self.liveTimer = QTimer(self)
        self.liveTimer.setSingleShot(True)
        self.liveTimer.setInterval(1500)
        self.liveTimer.timeout.connect(self.SendLiveUpdate)

        self.setLayout(QVBoxLayout())

        info = QHBoxLayout()
        self.layout().addLayout(info)
        self.setLabel = QLabel()
        self.setLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.addWidget(self.setLabel)
        info.addStretch()
        self.statusLabel = QLabel()
        self.statusLabel.setWordWrap(True)
        info.addWidget(self.statusLabel, 1)

        self.gamesArea = QScrollArea()
        self.gamesArea.setWidgetResizable(True)
        self.gamesArea.setFrameShape(QFrame.Shape.NoFrame)
        self.layout().addWidget(self.gamesArea)

        buttons = QHBoxLayout()
        self.layout().addLayout(buttons)
        self.btReport = QPushButton(QApplication.translate("app", "Report set to start.gg"))
        self.btReport.setToolTip(
            QApplication.translate(
                "app", "Sends the set's result and its games to start.gg, ending the set"
            )
        )
        self.btReport.clicked.connect(self.ReportSet)
        buttons.addWidget(self.btReport)
        self.btRetry = QPushButton(QApplication.translate("app", "Retry"))
        self.btRetry.clicked.connect(self.RetryLast)
        buttons.addWidget(self.btRetry)
        self.btSendNow = QPushButton(QApplication.translate("app", "Send games now"))
        self.btSendNow.setToolTip(
            QApplication.translate(
                "app", "Sends the games played so far to start.gg without ending the set"
            )
        )
        self.btSendNow.clicked.connect(self.SendLiveUpdate)
        buttons.addWidget(self.btSendNow)
        buttons.addStretch()
        self.btCheckToken = QPushButton(QApplication.translate("app", "Check token"))
        self.btCheckToken.setToolTip(
            QApplication.translate(
                "app", "Checks the start.gg API token set in Settings > API Keys"
            )
        )
        self.btCheckToken.clicked.connect(self.CheckToken)
        buttons.addWidget(self.btCheckToken)
        self.btClear = QPushButton(QApplication.translate("app", "Clear games"))
        self.btClear.clicked.connect(self.ClearGames)
        buttons.addWidget(self.btClear)
        self.btReset = QPushButton(QApplication.translate("app", "Reset on start.gg"))
        self.btReset.setToolTip(
            QApplication.translate("app", "Resets the set on start.gg, so it can be reported again")
        )
        self.btReset.clicked.connect(self.ResetSet)
        buttons.addWidget(self.btReset)

        StartGGReporter.instance.signals.status_changed.connect(self.ReporterStatusChanged)
        StartGGReporter.instance.signals.set_reported.connect(self.ReporterSetReported)
        GameAssetManager.instance.signals.onLoad.connect(self.RebuildRows)

        self.RebuildRows()
        self.UpdateStatus()

    # Games UI

    def PlayersPerTeam(self):
        return max(1, len(getattr(self.scoreboard, "team1playerWidgets", []) or [1]))

    def RebuildRows(self):
        self.rebuilding = True
        try:
            container = QWidget()
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            container.setLayout(grid)
            self.rows = []

            hasStages = bool(StateManager.Get("game.has_stages", False))
            hasCharacters = GameAssetManager.instance.characterModel.rowCount() > 1
            players = self.PlayersPerTeam()

            header = [QApplication.translate("app", "Game")]
            if hasStages:
                header.append(QApplication.translate("app", "Stage"))
            header += [
                QApplication.translate("app", "Team 1"),
                "",
                "",
                "",
                QApplication.translate("app", "Team 2"),
            ]
            for c, text in enumerate(header):
                label = QLabel(text)
                font = label.font()
                font.setBold(True)
                label.setFont(font)
                grid.addWidget(label, 0, c)

            teamNames = [self.TeamName(1), self.TeamName(2)]
            self.builtNames = teamNames
            current = self.report.CurrentGameIndex()
            for i, game in enumerate(self.report.games):
                row = {"index": i}
                r = i + 1
                c = 0
                label = QLabel(QApplication.translate("app", "Game {0}").format(i + 1))
                if i == current:
                    font = label.font()
                    font.setBold(True)
                    label.setFont(font)
                grid.addWidget(label, r, c)
                c += 1

                if hasStages:
                    stage = QComboBox()
                    stage.setModel(GameAssetManager.instance.stageModelWithBlank)
                    stage.setMaximumWidth(220)
                    index = 0
                    if game.get("stage"):
                        for s in range(1, stage.count()):
                            data = stage.itemData(s, Qt.ItemDataRole.UserRole) or {}
                            if data.get("codename") == game["stage"]:
                                index = s
                                break
                    stage.setCurrentIndex(index)
                    stage.currentIndexChanged.connect(
                        lambda _x, i=i, stage=stage: self.StageChanged(i, stage)
                    )
                    grid.addWidget(stage, r, c)
                    row["stage"] = stage
                    c += 1

                row["characters"] = {}
                buttons = {}
                for team in (1, 2):
                    combos = []
                    box = QWidget()
                    box.setLayout(QHBoxLayout())
                    box.layout().setContentsMargins(0, 0, 0, 0)
                    if hasCharacters:
                        chars = game["characters"].get(team) or []
                        for p in range(players):
                            combo = QComboBox()
                            combo.setModel(GameAssetManager.instance.characterModel)
                            combo.setIconSize(QSize(24, 24))
                            combo.setMaximumWidth(200)
                            key = chars[p] if p < len(chars) else None
                            combo.setCurrentIndex(CharacterIndex(combo, key))
                            combo.currentIndexChanged.connect(
                                lambda _x, i=i, team=team: self.CharactersChanged(i, team)
                            )
                            box.layout().addWidget(combo)
                            combos.append(combo)
                    row["characters"][team] = combos
                    column = c if team == 1 else c + 4
                    grid.addWidget(box, r, column)

                for offset, (winner, text) in enumerate(
                    (
                        (1, teamNames[0]),
                        (DRAW, QApplication.translate("app", "Draw")),
                        (2, teamNames[1]),
                    )
                ):
                    button = QPushButton(text)
                    button.setCheckable(True)
                    button.setChecked(game["winner"] == winner)
                    button.clicked.connect(
                        lambda checked, i=i, winner=winner: self.WinnerClicked(i, winner, checked)
                    )
                    grid.addWidget(button, r, c + 1 + offset)
                    buttons[winner] = button
                row["winners"] = buttons
                self.rows.append(row)

            grid.setRowStretch(len(self.report.games) + 1, 1)
            grid.setColumnStretch(grid.columnCount(), 1)
            self.gamesArea.setWidget(container)
        finally:
            self.rebuilding = False
        self.UpdateStatus()

    def TeamName(self, team):
        name = StateManager.Get(f"score.{self.number}.team.{team}.mergedTeamName") or ""
        name = name.replace("[L]", "").strip()
        return name or QApplication.translate("app", "Team {0}").format(team)

    def ScoreboardCharacters(self, team):
        result = []
        for p in range(1, self.PlayersPerTeam() + 1):
            character = (
                StateManager.Get(f"score.{self.number}.team.{team}.player.{p}.character.1") or {}
            )
            result.append(character.get("en_name"))
        return result

    def FillCharacters(self, index):
        """Takes the characters on the scoreboard for a game without any."""
        game = self.report.games[index]
        for team in (1, 2):
            if not any(game["characters"].get(team) or []):
                chars = self.ScoreboardCharacters(team)
                if any(chars):
                    self.report.SetCharacters(index, team, chars)

    def WinnerClicked(self, index, winner, checked):
        self.report.SetWinner(index, winner if checked else UNDECIDED)
        if checked:
            self.FillCharacters(index)
        self.Edited()

    def StageChanged(self, index, combo):
        if self.rebuilding:
            return
        data = combo.currentData() or {}
        self.report.SetStage(index, data.get("codename"))
        self.Edited(rebuild=False)

    def CharactersChanged(self, index, team):
        if self.rebuilding:
            return
        row = self.rows[index]
        chars = []
        for combo in row["characters"][team]:
            data = combo.currentData() or {}
            chars.append(data.get("en_name") or None)
        self.report.SetCharacters(index, team, chars)
        self.Edited(rebuild=False)

    def Edited(self, rebuild=True, fromScoreboard=False):
        """The games were changed here."""
        self.dirty = True
        if rebuild:
            self.RebuildRows()
        self.Export()
        if not fromScoreboard:
            self.signals.scoreChanged.emit(*self.report.Score())
        if LiveUpdates() and self.CanSend()[0]:
            self.liveTimer.start()
        self.UpdateStatus()

    # Called by the scoreboard

    def SetBestOf(self, bestOf):
        self.report.SetBestOf(bestOf)
        self.RebuildRows()
        self.Export()

    def ScoreChanged(self, team, value):
        """The scoreboard's score was changed (team 0 or 1)."""
        before = [g["winner"] for g in self.report.games]
        if self.report.SetScore(team + 1, value):
            for i, game in enumerate(self.report.games):
                if game["winner"] is not UNDECIDED and (i >= len(before) or before[i] is UNDECIDED):
                    self.FillCharacters(i)
            if getattr(self.scoreboard, "applyingProviderData", False):
                self.RebuildRows()
                self.Export()
            else:
                self.Edited(fromScoreboard=True)

    def Swap(self):
        self.report.Swap()
        self.RebuildRows()
        self.Export()

    def SetStage(self, index, codename):
        if index < 0:
            index = 0
        if index < len(self.report.games) and self.report.games[index].get("stage") == (
            codename or None
        ):
            return
        self.report.SetStage(index, codename)
        self.Edited()

    def ResetAllStages(self):
        for i in range(len(self.report.games)):
            self.report.SetStage(i, None)
        self.Edited()

    def CurrentGameIndex(self):
        return self.report.CurrentGameIndex()

    def NewSet(self, setId):
        """Another set was loaded on the scoreboard (or none)."""
        self.liveTimer.stop()
        self.setId = setId
        self.entrantIds = None
        self.setState = None
        self.dirty = False
        self.lastRequest = None
        self.lastSent = 0
        self.report.Reset()
        StartGGReporter.instance.Clear(self.number)
        self.RebuildRows()
        self.Export()

    def ApplySetData(self, data):
        """The scoreboard got the set's data from start.gg."""
        if data.get("id") is None or str(data.get("id")) != str(self.setId):
            return
        if data.get("entrant_ids") and all(data.get("entrant_ids")):
            self.entrantIds = list(data.get("entrant_ids"))
        if data.get("state") is not None:
            self.setState = data.get("state")

        # Games reported on start.gg (by someone else, or by us earlier),
        # unless there are changes here that weren't sent yet
        games = data.get("games")
        if games and not self.HoldProviderResults():
            before = self.report.ToDict()
            self.report.SetFromProvider(games, self.Swapped())
            if self.report.ToDict() != before:
                self.RebuildRows()
                self.Export()
                self.signals.scoreChanged.emit(*self.report.Score())

        # The players' names are on the buttons
        if getattr(self, "builtNames", None) != [self.TeamName(1), self.TeamName(2)]:
            self.RebuildRows()

        if (
            self.setState in (1, 6)
            and MarkInProgress()
            and HasToken()
            and IsReportableSetId(self.setId)
            and str(self.setId) not in self.markedInProgress
        ):
            self.markedInProgress.add(str(self.setId))
            StartGGReporter.instance.Submit(self.number, KIND_START, self.setId)

        self.UpdateStatus()

    # Seconds after sending games during which start.gg's may not have them yet
    SEND_GRACE_SECS = 15

    def HoldProviderResults(self):
        """start.gg's score and games for the set are behind what's here:
        changes made here are waiting to be sent, being sent, or were just
        sent. Only when reporting from here."""
        if not HasToken():
            return False
        return (
            self.dirty
            or StartGGReporter.instance.Busy(self.number)
            or time.time() - self.lastSent < GameReportWidget.SEND_GRACE_SECS
        )

    def Swapped(self):
        return bool(getattr(self.scoreboard, "teamsSwapped", False))

    # Reporting

    def CanSend(self):
        """(True, "") or (False, why not)."""
        if not HasToken():
            return False, QApplication.translate(
                "app", "Set a start.gg API token in Settings > API Keys to report sets"
            )
        if self.setId is None:
            return False, QApplication.translate("app", "Load a set from start.gg to report it")
        if not IsReportableSetId(self.setId):
            return False, QApplication.translate(
                "app", "This set's bracket hasn't started on start.gg yet"
            )
        if not self.entrantIds:
            return False, QApplication.translate(
                "app", "Waiting for the set's players from start.gg"
            )
        return True, ""

    def Variables(self, final):
        gameAssets = GameAssetManager.instance
        gameData = BuildGameData(
            self.report,
            self.entrantIds,
            self.Swapped(),
            gameAssets.GetStartGGCharacterId,
            gameAssets.GetStartGGStageId,
        )
        variables = {"gameData": gameData}
        winner = SetWinnerEntrant(self.report, self.entrantIds, self.Swapped())
        if final:
            variables["winnerId"] = winner
        return variables

    def SendLiveUpdate(self):
        ok, _why = self.CanSend()
        if not ok or self.setState == 3:
            return
        if StartGGReporter.instance.Status(self.number).get("state") == STATUS_REPORTED:
            return
        variables = self.Variables(final=False)
        if not variables["gameData"]:
            return
        self.lastRequest = {"kind": KIND_UPDATE, "setId": self.setId, "variables": variables}
        StartGGReporter.instance.Submit(self.number, KIND_UPDATE, self.setId, variables)
        self.lastSent = time.time()
        self.dirty = False

    def ReportSet(self):
        ok, why = self.CanSend()
        if not ok:
            QMessageBox.warning(self, QApplication.translate("app", "Report set"), why)
            return
        variables = self.Variables(final=True)
        if variables.get("winnerId") is None:
            QMessageBox.warning(
                self,
                QApplication.translate("app", "Report set"),
                QApplication.translate("app", "The set has no winner yet: the score is tied."),
            )
            return
        t1, t2 = self.report.Score()
        team1 = StateManager.Get(
            f"score.{self.number}.team.1.mergedTeamName"
        ) or QApplication.translate("app", "Team 1")
        team2 = StateManager.Get(
            f"score.{self.number}.team.2.mergedTeamName"
        ) or QApplication.translate("app", "Team 2")
        if ConfirmReport():
            answer = QMessageBox.question(
                self,
                QApplication.translate("app", "Report set"),
                QApplication.translate("app", "Report {0} {1} - {2} {3} to start.gg?").format(
                    team1, t1, t2, team2
                )
                + "\n"
                + QApplication.translate(
                    "app", "{0} game(s) with their characters and stages will be sent."
                ).format(len(variables["gameData"])),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.liveTimer.stop()
        self.lastRequest = {"kind": KIND_REPORT, "setId": self.setId, "variables": variables}
        StartGGReporter.instance.Submit(self.number, KIND_REPORT, self.setId, variables)
        self.lastSent = time.time()
        self.dirty = False

    def ResetSet(self):
        ok, why = self.CanSend()
        if not ok:
            QMessageBox.warning(self, QApplication.translate("app", "Reset set"), why)
            return
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Reset set"),
            QApplication.translate(
                "app",
                "Reset this set on start.gg? Its result and games there are cleared (sets that depend on it too). The games here are kept.",
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.lastRequest = {"kind": KIND_RESET, "setId": self.setId, "variables": {}}
        self.setState = 1
        self.markedInProgress.discard(str(self.setId))
        StartGGReporter.instance.Submit(self.number, KIND_RESET, self.setId)

    def RetryLast(self):
        if self.lastRequest is None:
            return
        request = dict(self.lastRequest)
        if request["kind"] in (KIND_UPDATE, KIND_REPORT):
            # The games may have changed since
            request["variables"] = self.Variables(final=request["kind"] == KIND_REPORT)
        StartGGReporter.instance.Retry(self.number, request)

    def CheckToken(self):
        if not HasToken():
            QMessageBox.warning(
                self,
                QApplication.translate("app", "start.gg API token"),
                QApplication.translate(
                    "app", "Set a start.gg API token in Settings > API Keys to report sets"
                ),
            )
            return
        self.btCheckToken.setEnabled(False)

        def Done(ok, message):
            try:
                self.btCheckToken.setEnabled(True)
            except RuntimeError:
                return
            if ok:
                QMessageBox.information(
                    self,
                    QApplication.translate("app", "start.gg API token"),
                    QApplication.translate("app", "The token works. It belongs to {0}.").format(
                        message
                    )
                    + "\n"
                    + QApplication.translate(
                        "app",
                        "Sets can only be reported if this account is an admin of the tournament.",
                    ),
                )
            else:
                QMessageBox.warning(
                    self,
                    QApplication.translate("app", "start.gg API token"),
                    QApplication.translate("app", "The token doesn't work: {0}").format(message),
                )

        StartGGReporter.instance.TestToken(Done)

    def ClearGames(self):
        if (
            self.report.HasResults()
            and QMessageBox.question(
                self,
                QApplication.translate("app", "Clear games"),
                QApplication.translate(
                    "app", "Clear the results, stages and characters of every game?"
                ),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.report.Reset()
        self.Edited()

    def ReporterStatusChanged(self, number):
        if number == self.number:
            self.UpdateStatus()
            self.Export()

    def ReporterSetReported(self, number, setId):
        if number != self.number or str(setId) != str(self.setId):
            return
        self.setState = 3
        self.signals.setReported.emit(str(setId))

    def UpdateStatus(self):
        if self.setId is None:
            self.setLabel.setText(QApplication.translate("app", "No set loaded from start.gg"))
        else:
            self.setLabel.setText(
                QApplication.translate("app", "start.gg set {0}").format(self.setId)
            )

        ok, why = self.CanSend()
        status = StartGGReporter.instance.Status(self.number)
        state = status.get("state")
        texts = {
            STATUS_PENDING: QApplication.translate("app", "Waiting to send..."),
            STATUS_SENDING: QApplication.translate("app", "Sending to start.gg..."),
            STATUS_SYNCED: QApplication.translate("app", "Games sent to start.gg"),
            STATUS_REPORTED: QApplication.translate("app", "Reported to start.gg"),
            STATUS_RETRYING: QApplication.translate("app", "Couldn't reach start.gg."),
            STATUS_ERROR: QApplication.translate("app", "start.gg error:"),
        }
        palette = QApplication.palette()
        color = palette.color(QPalette.ColorRole.Text).name()
        if not ok:
            text = why
            color = palette.color(QPalette.ColorRole.PlaceholderText).name()
        elif state in texts:
            text = texts[state]
            if status.get("message"):
                text += " " + status.get("message")
            if state in (STATUS_ERROR, STATUS_RETRYING):
                color = "#e05252"
            elif state in (STATUS_SYNCED, STATUS_REPORTED):
                color = "#3fb950"
        elif self.setState == 3:
            text = QApplication.translate("app", "This set is finished on start.gg")
        elif self.dirty and not LiveUpdates():
            text = QApplication.translate("app", "Games are sent when the set is reported")
        else:
            text = status.get("message") or ""
        self.statusLabel.setText(text)
        self.statusLabel.setStyleSheet(f"color: {color};")

        sending = state in (STATUS_PENDING, STATUS_SENDING, STATUS_RETRYING)
        self.btReport.setEnabled(ok and not sending)
        self.btSendNow.setEnabled(ok and not sending)
        self.btSendNow.setVisible(not LiveUpdates())
        self.btReset.setEnabled(ok and not sending)
        self.btRetry.setVisible(state == STATUS_ERROR and self.lastRequest is not None)

    # Layouts

    def Export(self):
        try:
            games = {}
            for i, g in enumerate(self.report.games):
                stage = StateManager.Get(f"game.stages.{g['stage']}") if g.get("stage") else None
                games[str(i + 1)] = {
                    "game": i + 1,
                    # 1 or 2 for the team that won, 0 for a draw, None if not played
                    "winner": g["winner"],
                    "stage": g.get("stage"),
                    "stageData": stage,
                    "characters": {
                        str(team): [c for c in (g["characters"].get(team) or [])] for team in (1, 2)
                    },
                    "current": i == self.report.CurrentGameIndex(),
                }
            status = StartGGReporter.instance.Status(self.number)
            with StateManager.SaveBlock():
                StateManager.Set(f"score.{self.number}.games", games)
                StateManager.Set(
                    f"score.{self.number}.report",
                    {
                        "setId": self.setId,
                        "status": status.get("state"),
                        "message": status.get("message"),
                        "liveUpdates": LiveUpdates(),
                    },
                )
        except Exception:
            logger.error(traceback.format_exc())
