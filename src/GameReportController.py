# A scoreboard's games: the result, stage and characters of each game of the
# set, which the scoreboard's score follows, and reporting the set to start.gg
# (see StartGGReporter). The games tracker under the score and the games
# pop-ups (GamesPopup) show and edit them.
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

# Kinds of status, for its color
STATUS_KIND_NONE = "none"
STATUS_KIND_MUTED = "muted"
STATUS_KIND_OK = "ok"
STATUS_KIND_ERROR = "error"


def LiveUpdates():
    return SettingsManager.Get("startgg_reporting.live_updates", True)


def MarkInProgress():
    return SettingsManager.Get("startgg_reporting.mark_in_progress", True)


def ConfirmReport():
    return SettingsManager.Get("startgg_reporting.confirm_report", True)


class GameReportSignals(QObject):
    # Team 1's and team 2's score, from the games
    scoreChanged = Signal(int, int)
    # The set was reported to start.gg (set id)
    setReported = Signal(str)
    # The games changed (results, stages, characters, how many), or what
    # they're shown with (the teams' names and colors, the game's assets)
    gamesChanged = Signal()
    # What's being sent to start.gg, or why the set can't be reported
    statusChanged = Signal()


class GameReportController(QObject):
    # Seconds after sending games during which start.gg's may not have them yet
    SEND_GRACE_SECS = 15

    def __init__(self, scoreboard):
        super().__init__(scoreboard)
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
        self.builtNames = None

        self.liveTimer = QTimer(self)
        self.liveTimer.setSingleShot(True)
        self.liveTimer.setInterval(1500)
        self.liveTimer.timeout.connect(self.SendLiveUpdate)

        StartGGReporter.instance.signals.status_changed.connect(self.ReporterStatusChanged)
        StartGGReporter.instance.signals.set_reported.connect(self.ReporterSetReported)
        GameAssetManager.instance.signals.onLoad.connect(self.signals.gamesChanged.emit)

    # =====================================================
    # SHOWING THE GAMES
    # =====================================================
    def PlayersPerTeam(self):
        return max(1, len(getattr(self.scoreboard, "team1playerWidgets", []) or [1]))

    def HasStages(self):
        return bool(StateManager.Get("game.has_stages", False))

    def HasCharacters(self):
        return GameAssetManager.instance.characterModel.rowCount() > 1

    def TeamName(self, team):
        name = StateManager.Get(f"score.{self.number}.team.{team}.mergedTeamName") or ""
        name = name.replace("[L]", "").strip()
        return name or QApplication.translate("app", "Team {0}").format(team)

    def TeamColor(self, team):
        button = getattr(self.scoreboard, f"colorButton{team}", None)
        if button is not None:
            return QColor(button.color())
        return QColor("#fe3636" if team == 1 else "#2e89ff")

    def CharacterName(self, en_name):
        characters = GameAssetManager.instance.characters or {}
        return (characters.get(en_name) or {}).get("display_name") or en_name

    def StageName(self, codename):
        stage = StateManager.Get(f"game.stages.{codename}") or {}
        return stage.get("display_name") or stage.get("name") or codename

    def SetWinsNeeded(self):
        """Wins that take the set (3 in a best of 5), or None without a best of."""
        if self.report.bestOf <= 0:
            return None
        return self.report.bestOf // 2 + 1

    def SetDecided(self):
        """The team that won the set by reaching the wins it needs, or None."""
        needed = self.SetWinsNeeded()
        if needed is None:
            return None
        t1, t2 = self.report.Score()
        if t1 >= needed and t1 > t2:
            return 1
        if t2 >= needed and t2 > t1:
            return 2
        return None

    def GameNeeded(self, index):
        """False for a game after the set was won that wasn't played."""
        if self.SetDecided() is None:
            return True
        if self.report.games[index]["winner"] is not UNDECIDED:
            return True
        last = max(i for i, g in enumerate(self.report.games) if g["winner"] is not UNDECIDED)
        return index < last

    def ScoreboardCharacters(self, team):
        result = []
        for p in range(1, self.PlayersPerTeam() + 1):
            character = (
                StateManager.Get(f"score.{self.number}.team.{team}.player.{p}.character.1") or {}
            )
            result.append(character.get("en_name"))
        return result

    def CarriedCharacters(self, index, team):
        """The characters a game without any is shown with: the scoreboard's,
        the ones being played, else the last game's with some. (characters,
        where they're from: a game's index, or None for the scoreboard)"""
        chars = self.ScoreboardCharacters(team)
        if any(chars):
            return chars, None
        for i in range(index - 1, -1, -1):
            chars = self.report.games[i]["characters"].get(team) or []
            if any(chars):
                return chars, i
        return [], None

    def FillCharacters(self, index):
        """Takes the characters a game without any is shown with, once it
        has a result."""
        game = self.report.games[index]
        for team in (1, 2):
            if not any(game["characters"].get(team) or []):
                chars, _ = self.CarriedCharacters(index, team)
                if any(chars):
                    self.report.SetCharacters(index, team, chars)

    def GameTooltip(self, index):
        """Who won a game, its stage and characters, for the games tracker."""
        if not 0 <= index < len(self.report.games):
            return ""
        game = self.report.games[index]
        winner = game["winner"]
        if winner in (1, 2):
            result = QApplication.translate("app", "Won by {0}").format(self.TeamName(winner))
        elif winner == DRAW:
            result = QApplication.translate("app", "Draw")
        else:
            result = QApplication.translate("app", "Not played")
        lines = [f"<b>{QApplication.translate('app', 'Game {0}').format(index + 1)}</b>: {result}"]
        if game.get("stage"):
            lines.append(
                QApplication.translate("app", "Stage: {0}").format(self.StageName(game["stage"]))
            )
        for team in (1, 2):
            names = [self.CharacterName(c) for c in (game["characters"].get(team) or []) if c]
            if names:
                lines.append(f"{self.TeamName(team)}: {', '.join(names)}")
        lines.append(
            "<i>"
            + QApplication.translate("app", "Click to edit, right-click to set the winner")
            + "</i>"
        )
        return "<br>".join(lines)

    # =====================================================
    # EDITING GAMES
    # =====================================================
    def SetWinner(self, index, winner):
        """1 or 2 for the team that won, DRAW, or UNDECIDED to clear it."""
        self.report.SetWinner(index, winner)
        if winner is not UNDECIDED:
            self.FillCharacters(index)
        self.Edited()

    def SetCharacters(self, index, team, characters):
        self.report.SetCharacters(index, team, characters)
        self.Edited()

    def Edited(self, fromScoreboard=False):
        """The games were changed here."""
        self.dirty = True
        self.Export()
        if not fromScoreboard:
            self.signals.scoreChanged.emit(*self.report.Score())
        if LiveUpdates() and self.CanSend()[0]:
            self.liveTimer.start()
        self.signals.statusChanged.emit()

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

    def ClearGames(self, parent=None):
        if (
            self.report.HasResults()
            and QMessageBox.question(
                parent or self.scoreboard,
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

    # =====================================================
    # SCOREBOARD SYNC
    # =====================================================
    # Called by the scoreboard
    def SetBestOf(self, bestOf):
        self.report.SetBestOf(bestOf)
        self.Export()

    def ScoreChanged(self, team, value):
        """The scoreboard's score was changed (team 0 or 1)."""
        before = [g["winner"] for g in self.report.games]
        if self.report.SetScore(team + 1, value):
            for i, game in enumerate(self.report.games):
                if game["winner"] is not UNDECIDED and (i >= len(before) or before[i] is UNDECIDED):
                    self.FillCharacters(i)
            if getattr(self.scoreboard, "applyingProviderData", False):
                self.Export()
            else:
                self.Edited(fromScoreboard=True)

    def Swap(self):
        self.report.Swap()
        self.Export()

    def Swapped(self):
        return bool(getattr(self.scoreboard, "teamsSwapped", False))

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
        self.Export()
        self.signals.statusChanged.emit()

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
        exported = False
        if games and not self.HoldProviderResults():
            before = self.report.ToDict()
            self.report.SetFromProvider(games, self.Swapped())
            if self.report.ToDict() != before:
                self.Export()
                exported = True
                self.signals.scoreChanged.emit(*self.report.Score())

        # The players' names are on the winner buttons
        names = [self.TeamName(1), self.TeamName(2)]
        if self.builtNames != names:
            self.builtNames = names
            if not exported:
                self.signals.gamesChanged.emit()

        if (
            self.setState in (1, 6)
            and MarkInProgress()
            and HasToken()
            and IsReportableSetId(self.setId)
            and str(self.setId) not in self.markedInProgress
        ):
            self.markedInProgress.add(str(self.setId))
            StartGGReporter.instance.Submit(self.number, KIND_START, self.setId)

        self.signals.statusChanged.emit()

    def HoldProviderResults(self):
        """start.gg's score and games for the set are behind what's here:
        changes made here are waiting to be sent, being sent, or were just
        sent. Only when reporting from here."""
        if not HasToken():
            return False
        return (
            self.dirty
            or StartGGReporter.instance.Busy(self.number)
            or time.time() - self.lastSent < GameReportController.SEND_GRACE_SECS
        )

    # =====================================================
    # REPORTING TO START.GG
    # =====================================================
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

    def Reporting(self):
        """Whether the set can be reported from here at all: a token, and a
        set from start.gg loaded. Without them, there's nothing about
        start.gg to show."""
        return HasToken() and self.setId is not None

    def Sending(self):
        state = StartGGReporter.instance.Status(self.number).get("state")
        return state in (STATUS_PENDING, STATUS_SENDING, STATUS_RETRYING)

    def Reported(self):
        state = StartGGReporter.instance.Status(self.number).get("state")
        return state == STATUS_REPORTED or self.setState == 3

    def CanRetry(self):
        state = StartGGReporter.instance.Status(self.number).get("state")
        return state == STATUS_ERROR and self.lastRequest is not None

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

    def ReportSet(self, parent=None):
        parent = parent or self.scoreboard
        ok, why = self.CanSend()
        if not ok:
            QMessageBox.warning(parent, QApplication.translate("app", "Report set"), why)
            return
        variables = self.Variables(final=True)
        if variables.get("winnerId") is None:
            QMessageBox.warning(
                parent,
                QApplication.translate("app", "Report set"),
                QApplication.translate("app", "The set has no winner yet: the score is tied."),
            )
            return
        t1, t2 = self.report.Score()
        if ConfirmReport():
            answer = QMessageBox.question(
                parent,
                QApplication.translate("app", "Report set"),
                QApplication.translate("app", "Report {0} {1} - {2} {3} to start.gg?").format(
                    self.TeamName(1), t1, t2, self.TeamName(2)
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

    def ResetSet(self, parent=None):
        parent = parent or self.scoreboard
        ok, why = self.CanSend()
        if not ok:
            QMessageBox.warning(parent, QApplication.translate("app", "Reset set"), why)
            return
        answer = QMessageBox.question(
            parent,
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

    def CheckToken(self, parent=None):
        parent = parent or self.scoreboard
        if not HasToken():
            QMessageBox.warning(
                parent,
                QApplication.translate("app", "start.gg API token"),
                QApplication.translate(
                    "app", "Set a start.gg API token in Settings > API Keys to report sets"
                ),
            )
            return

        def Done(ok, message):
            if ok:
                QMessageBox.information(
                    parent,
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
                    parent,
                    QApplication.translate("app", "start.gg API token"),
                    QApplication.translate("app", "The token doesn't work: {0}").format(message),
                )

        StartGGReporter.instance.TestToken(Done)

    def ReporterStatusChanged(self, number):
        if number == self.number:
            self.Export()
            self.signals.statusChanged.emit()

    def ReporterSetReported(self, number, setId):
        if number != self.number or str(setId) != str(self.setId):
            return
        self.setState = 3
        self.signals.setReported.emit(str(setId))
        self.signals.statusChanged.emit()

    def Status(self):
        """What's being sent to start.gg, or why the set can't be reported:
        (text, STATUS_KIND_*)."""
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
        if not ok:
            return why, STATUS_KIND_MUTED
        if state in texts:
            text = texts[state]
            if status.get("message"):
                text += " " + status.get("message")
            if state in (STATUS_ERROR, STATUS_RETRYING):
                return text, STATUS_KIND_ERROR
            if state in (STATUS_SYNCED, STATUS_REPORTED):
                return text, STATUS_KIND_OK
            return text, STATUS_KIND_NONE
        if self.setState == 3:
            return QApplication.translate("app", "This set is finished on start.gg"), STATUS_KIND_OK
        if self.dirty and not LiveUpdates():
            return (
                QApplication.translate("app", "Games are sent when the set is reported"),
                STATUS_KIND_MUTED,
            )
        if LiveUpdates():
            return QApplication.translate("app", "Live on start.gg"), STATUS_KIND_OK
        return status.get("message") or "", STATUS_KIND_NONE

    # =====================================================
    # EXPORTS
    # =====================================================
    # Layouts
    @staticmethod
    def CharacterData(en_name):
        """A character's data for the layouts, like a player's character:
        names, codename and the default skin's assets. None if not found."""
        if not en_name:
            return None
        manager = GameAssetManager.instance
        character = (getattr(manager, "characters", None) or {}).get(en_name)
        if character is None:
            return None
        assets = {}
        skins = (getattr(manager, "skinModels", None) or {}).get(en_name)
        if skins is not None and skins.rowCount() > 0:
            assets = (skins.item(0).data(Qt.ItemDataRole.UserRole) or {}).get("assets") or {}
        return {
            "name": character.get("export_name"),
            "en_name": en_name,
            "display_name": character.get("display_name"),
            "codename": character.get("codename"),
            "assets": assets,
        }

    def Export(self):
        try:
            games = {}
            for i, g in enumerate(self.report.games):
                stage = StateManager.Get(f"game.stages.{g['stage']}") if g.get("stage") else None
                scoreAfter = self.report.ScoreAfter(i)
                games[str(i + 1)] = {
                    "game": i + 1,
                    # 1 or 2 for the team that won, 0 for a draw, None if not played
                    "winner": g["winner"],
                    "stage": g.get("stage"),
                    "stageData": stage,
                    "characters": {
                        str(team): [c for c in (g["characters"].get(team) or [])] for team in (1, 2)
                    },
                    # The same characters with their names and images
                    "characterData": {
                        str(team): [
                            self.CharacterData(c) for c in (g["characters"].get(team) or [])
                        ]
                        for team in (1, 2)
                    },
                    # The set's score once this game was played, None before
                    "scoreAfter": {"1": scoreAfter[0], "2": scoreAfter[1]} if scoreAfter else None,
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
        self.signals.gamesChanged.emit()
