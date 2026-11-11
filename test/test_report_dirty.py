# Checks when a scoreboard's games stop being "changed here" (dirty), which
# keeps start.gg's older games from replacing them (GameReportController with
# the real StartGGReporter, start.gg itself faked):
# - only once start.gg took the request carrying them, not when it's queued
# - not when start.gg refused it or the reporter gave up on it
# - not when the games changed again since it was sent
# - a report of the set that was on the scoreboard before, finishing late,
#   doesn't make the set loaded since look reported
# Run from the repository root: python test/test_report_dirty.py
import contextlib
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QObject, Signal
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication(sys.argv)


class FakeAssetSignals(QObject):
    onLoad = Signal()


class FakeAssetManager:
    instance = None

    def __init__(self):
        self.signals = FakeAssetSignals()
        self.characters = {}
        self.characterModel = QStandardItemModel()
        self.characterModel.appendRow(QStandardItem(""))

    def GetStartGGCharacterId(self, key):
        return None

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


class FakeSettings:
    data = {"api_keys.startgg": "token"}

    @staticmethod
    def Get(key, default=None):
        return FakeSettings.data.get(key, default)


module = types.ModuleType("src.SettingsManager")
module.SettingsManager = FakeSettings
sys.modules["src.SettingsManager"] = module

import src.StartGGReporter as reporterModule
from src.GameReportController import GameReportController
from src.StartGGReporter import (
    KIND_REPORT,
    KIND_UPDATE,
    STATUS_ERROR,
    STATUS_REPORTED,
    ReportError,
    RetryableError,
    StartGGReporter,
)


class HeldPool:
    """Runs the workers when told to, like requests start.gg takes a while
    to answer"""

    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)

    def RunNext(self):
        self.workers.pop(0).run()


# What start.gg answers the next requests with: data, or an error to raise
answers = []
sent = []


def FakeSend(query, variables, token=None):
    sent.append(variables)
    answer = answers.pop(0) if answers else {}
    if isinstance(answer, Exception):
        raise answer
    return answer


reporterModule.Send = FakeSend
# Given up on at the first network failure
reporterModule.RETRY_DELAYS[:] = []


class FakeScoreboard(QWidget):
    def __init__(self):
        super().__init__()
        self.scoreboardNumber = 1
        self.team1playerWidgets = [None]


def Setup(setId="100"):
    answers.clear()
    sent.clear()
    reporter = StartGGReporter.instance
    reporter.threadPool = HeldPool()
    reporter.queues.clear()
    reporter.sending.clear()
    reporter.status.clear()
    controller = GameReportController(FakeScoreboard())
    controller.SetBestOf(5)
    controller.NewSet(setId)
    # start.gg's set: no games yet (state 2: already in progress)
    controller.ApplySetData({"id": setId, "entrant_ids": ["11", "22"], "state": 2, "games": []})
    assert controller.CanSend() == (True, ""), controller.CanSend()
    return controller, reporter


def ProviderGames(controller, winners):
    """start.gg's games arrive for the set, as a refresh brings them"""
    controller.ApplySetData(
        {
            "id": controller.setId,
            "entrant_ids": ["11", "22"],
            "state": 2,
            "games": [{"winner": w, "stage": None, "characters": [[], []]} for w in winners],
        }
    )


def Winners(controller):
    return [g["winner"] for g in controller.report.games if g["winner"] is not None]


def TestDirtyUntilStartGGTakesIt():
    controller, reporter = Setup()
    controller.SetWinner(0, 1)
    assert controller.dirty
    controller.liveTimer.stop()
    controller.SendLiveUpdate()
    # Queued, not taken yet: still dirty
    assert len(reporter.threadPool.workers) == 1
    assert controller.dirty, "dirty was cleared when the update was only queued"

    reporter.threadPool.RunNext()
    assert sent[-1]["gameData"][0]["winnerId"] == "11"
    assert not controller.dirty, "start.gg took the games: not dirty anymore"


def TestDirtyWhenGivenUp():
    for failure in [ReportError("not an admin"), RetryableError("no network")]:
        controller, reporter = Setup()
        controller.SetWinner(0, 1)
        controller.liveTimer.stop()
        answers.append(failure)
        controller.SendLiveUpdate()
        reporter.threadPool.RunNext()
        assert reporter.Status(1)["state"] == STATUS_ERROR, reporter.Status(1)
        assert controller.dirty, f"{failure!r}: the games never reached start.gg"

        # A refresh brings start.gg's games (none): the ones here are kept,
        # even once the grace period after sending is over
        controller.lastSent = 0
        assert controller.HoldProviderResults()
        ProviderGames(controller, [1])
        assert Winners(controller) == [1], Winners(controller)

        # Retried, and taken this time
        assert controller.CanRetry()
        controller.RetryLast()
        reporter.threadPool.RunNext()
        assert not controller.dirty


def TestDirtyWhenChangedSinceSent():
    controller, reporter = Setup()
    controller.SetWinner(0, 1)
    controller.liveTimer.stop()
    controller.SendLiveUpdate()
    # Another game while the first update is on its way
    controller.SetWinner(1, 2)
    controller.liveTimer.stop()
    reporter.threadPool.RunNext()
    assert controller.dirty, "the second game isn't on start.gg yet"

    controller.SendLiveUpdate()
    reporter.threadPool.RunNext()
    assert len(sent[-1]["gameData"]) == 2
    assert not controller.dirty


def TestReportClearsDirty():
    controller, reporter = Setup()
    FakeSettings.data["startgg_reporting.confirm_report"] = False
    controller.SetWinner(0, 1)
    controller.SetWinner(1, 1)
    controller.SetWinner(2, 1)
    controller.liveTimer.stop()
    controller.ReportSet()
    assert controller.dirty
    reporter.threadPool.RunNext()
    assert not controller.dirty and controller.Reported()
    assert "winnerId" in sent[-1]


def TestLateReportOfThePreviousSet():
    controller, reporter = Setup("100")
    FakeSettings.data["startgg_reporting.confirm_report"] = False
    for game in range(3):
        controller.SetWinner(game, 1)
    controller.liveTimer.stop()
    controller.ReportSet()

    # The next set is loaded before start.gg answered
    controller.NewSet("200")
    controller.ApplySetData({"id": "200", "entrant_ids": ["33", "44"], "state": 2, "games": []})
    reporter.threadPool.RunNext()
    status = reporter.Status(1)
    assert status["state"] == STATUS_REPORTED and str(status["setId"]) == "100", status

    # Set 100's report says nothing about set 200
    assert not controller.Reported(), "set 200 looks reported"
    assert controller.Status()[0] != "Reported to start.gg", controller.Status()
    assert not controller.dirty

    # ...and its games are still sent
    controller.SetWinner(0, 2)
    controller.liveTimer.stop()
    controller.SendLiveUpdate()
    assert len(reporter.threadPool.workers) == 1, "set 200's games weren't sent"
    reporter.threadPool.RunNext()
    assert sent[-1]["setId"] == "200" and sent[-1]["gameData"][0]["winnerId"] == "44"
    assert not controller.dirty

    assert KIND_UPDATE and KIND_REPORT


if __name__ == "__main__":
    TestDirtyUntilStartGGTakesIt()
    TestDirtyWhenGivenUp()
    TestDirtyWhenChangedSinceSent()
    TestReportClearsDirty()
    TestLateReportOfThePreviousSet()
    print("OK")
