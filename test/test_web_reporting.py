# Checks reporting sets from the web pages: the sets read from start.gg, the
# results players submit from a reporting station and their approval, the
# Admin page's actions, and the station PIN. start.gg is replaced by fakes.
# Run from the repository root: python test/test_web_reporting.py
import os
import shutil
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from src import WebReporting
from src.GameReport import MARK_SET_CALLED, REPORT_DQ, REPORT_SET, RESET_SET, UPDATE_SET
from src.ReportingStore import *
from src.SettingsManager import SettingsManager
from src.StartGGReporter import ReportError, RetryableError

SLUG = "tournament/test/event/singles"


def Node(id, state=1, entrants=("e1", "e2"), updatedAt=100, games=None, **extra):
    node = {
        "id": int(id),
        "identifier": "A",
        "round": 1,
        "fullRoundText": "Winners Round 1",
        "state": state,
        "totalGames": 3,
        "updatedAt": updatedAt,
        "slots": [{"entrant": {"id": e, "name": f"Player {e}"} if e else None} for e in entrants],
        "phaseGroup": {"id": 7, "displayIdentifier": "A1", "phase": {"id": 8, "name": "Pools"}},
        "event": {"slug": SLUG},
        **extra,
    }
    if games is not None:
        node["games"] = games
    return node


class FakeFetcher:
    def __init__(self, nodes):
        self.nodes = {str(n["id"]): n for n in nodes}
        self.calls = []
        self.down = False

    def Sets(self, eventSlug, updatedAfter=None):
        self.calls.append(("sets", updatedAfter))
        if self.down:
            return None
        return [n for n in self.nodes.values() if not updatedAfter or n["updatedAt"] > updatedAfter]

    def Set(self, setId):
        if self.down:
            return None
        return self.nodes.get(str(setId), {})

    def StationsAndStreams(self, eventSlug):
        return {
            "stations": [{"id": "s5", "number": 5, "stream": ""}],
            "streams": [{"id": "t1", "name": "main"}],
        }


class FakeSend:
    def __init__(self):
        self.sent = []
        self.error = None

    def __call__(self, query, variables):
        if self.error:
            raise self.error
        self.sent.append((query, variables))
        return {}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def Games(*winners, characters=False):
    return [
        {
            "winner": w,
            "stage": "bf" if characters else None,
            "characters": {"1": ["Mario"], "2": ["Fox"]} if characters else {},
        }
        for w in winners
    ]


def Setup(nodes):
    folder = tempfile.mkdtemp()
    clock = Clock()
    fetcher = FakeFetcher(nodes)
    send = FakeSend()
    reporting = WebReporting.Reporting(
        store=ReportingStore(os.path.join(folder, "web_reporting.json"), clock),
        fetcher=fetcher,
        send=send,
        clock=clock,
    )
    reporting.EventSlug = lambda: SLUG
    reporting.HasToken = lambda: True
    reporting.CharacterId = {"Mario": 1302, "Fox": 1279}.get
    reporting.StageId = {"bf": 311}.get
    SettingsManager.settings = {}
    return reporting, fetcher, send, clock, folder


def Status(result):
    return result[1] if isinstance(result, tuple) else 200


def Error(result):
    return result[0]["error"] if isinstance(result, tuple) else None


# =====================================================
# SETS AND GAMES
# =====================================================
def TestParseSet():
    set = ParseSet(Node(5, state=6, station={"id": 3, "number": 12}))
    assert set["id"] == "5" and set["state"] == CALLED
    assert set["entrants"] == [{"id": "e1", "name": "Player e1"}, {"id": "e2", "name": "Player e2"}]
    assert set["station"] == {"id": "3", "number": 12}
    assert set["stream"] is None
    assert set["phase"] == "Pools" and set["phaseGroup"] == "A1"
    assert IsOpen(set)
    # A player still to come
    waiting = ParseSet(Node(6, entrants=("e1", None)))
    assert waiting["entrants"][1] == {"id": None, "name": ""}
    assert not IsOpen(waiting)
    assert not IsOpen(ParseSet(Node(7, state=COMPLETED)))


def TestNormalizeGames():
    games = NormalizeGames(
        [
            {"winner": "1", "stage": "bf", "characters": {"1": ["Mario", ""], "2": ["Fox"]}},
            {"winner": 7, "characters": None},
            {"winner": 2},
            {"winner": None},
            "junk",
        ]
    )
    assert games == [
        {"winner": 1, "stage": "bf", "characters": {"1": ["Mario"], "2": ["Fox"]}},
        {"winner": None, "stage": None, "characters": {"1": [], "2": []}},
        {"winner": 2, "stage": None, "characters": {"1": [], "2": []}},
    ], games
    assert Score(games) == [1, 1] and WinnerTeam(games) is None
    try:
        NormalizeGames("2-0")
        raise AssertionError("not a list")
    except ValueError:
        pass


def TestVariables():
    set = ParseSet(Node(5))
    games = NormalizeGames(Games(1, 2, 1, characters=True))
    variables = Variables(set, games, True, {"Mario": 1302, "Fox": 1279}.get, {"bf": 311}.get)
    assert variables["winnerId"] == "e1"
    assert variables["gameData"][1] == {
        "gameNum": 2,
        "winnerId": "e2",
        "stageId": "311",
        "selections": [
            {"entrantId": "e1", "characterId": 1302},
            {"entrantId": "e2", "characterId": 1279},
        ],
    }
    assert "winnerId" not in Variables(set, games, False)
    assert DQVariables(set, 2) == {"winnerId": "e2"}


def TestProviderGames():
    node = Node(
        5,
        games=[
            {
                "orderNum": 2,
                "winnerId": "e2",
                "stage": None,
                "selections": [{"entrant": {"id": "e2"}, "selectionValue": 9}],
            },
            {
                "orderNum": 1,
                "winnerId": "e1",
                "stage": {"id": 311},
                "selections": [{"entrant": {"id": "e1"}, "selectionValue": 1302}],
            },
        ],
    )

    def Broken(id):
        raise KeyError(id)

    games = ProviderGames(node, ["e1", "e2"], {311: "bf"}.get, Broken)
    assert games == [
        {"winner": 1, "stage": "bf", "characters": {"1": [], "2": []}},
        {"winner": 2, "stage": None, "characters": {"1": [], "2": []}},
    ], games


# =====================================================
# THE SETS' CACHE
# =====================================================
def TestSetCache():
    reporting, fetcher, send, clock, folder = Setup([Node(1), Node(2, updatedAt=200)])
    try:
        data = reporting.Sets()
        assert sorted(s["id"] for s in data["sets"]) == ["1", "2"]
        assert data["stations"][0]["number"] == 5 and data["hasToken"]
        assert fetcher.calls == [("sets", None)]

        # Fresh enough: not fetched again
        reporting.Sets()
        assert len(fetcher.calls) == 1

        # Then only the sets updated since the newest one seen
        clock.now += 60
        fetcher.nodes["1"] = Node(1, state=IN_PROGRESS, updatedAt=300)
        data = reporting.Sets()
        assert fetcher.calls[-1] == ("sets", 200 - WebReporting.UPDATED_MARGIN_SECS)
        assert {s["id"]: s["state"] for s in data["sets"]} == {"1": IN_PROGRESS, "2": 1}

        # start.gg down: the sets are kept, with the error
        clock.now += 60
        fetcher.down = True
        data = reporting.Sets()
        assert len(data["sets"]) == 2 and data["error"]
        fetcher.down = False

        # Changed from here: start.gg's older answer doesn't undo it
        reporting.cache.Put(dict(reporting.cache.Find("2"), state=CALLED))
        clock.now += 60
        reporting.Sets(force=True)
        assert reporting.cache.Find("2")["state"] == CALLED
        clock.now += WebReporting.LOCAL_CHANGE_SECS + 60
        reporting.Sets(force=True)
        assert reporting.cache.Find("2")["state"] == 1
    finally:
        shutil.rmtree(folder)


# =====================================================
# STATIONS AND APPROVAL
# =====================================================
def TestStationSubmitAndApprove():
    reporting, fetcher, send, clock, folder = Setup(
        [Node(1, state=IN_PROGRESS), Node(2, state=COMPLETED), Node(3, entrants=("e1", None))]
    )
    try:
        sets = reporting.StationSets()["sets"]
        assert [s["id"] for s in sets] == ["1"], sets
        assert "updatedAt" not in sets[0]

        assert Error(reporting.Submit({"setId": "1", "games": Games(1, 2)})) == "TIED"
        assert Error(reporting.Submit({"setId": "2", "games": Games(1, 1)})) == "SET_COMPLETED"
        assert Error(reporting.Submit({"setId": "3", "games": Games(1, 1)})) == "NOT_READY"
        assert Error(reporting.Submit({"setId": "1", "games": "2-0"})) == "NO_GAMES"

        result = reporting.Submit(
            {"setId": "1", "games": Games(1, 2, 1, characters=True), "station": "Setup 5"},
            "10.0.0.9",
        )
        assert result["ok"] and result["score"] == [2, 1]
        assert reporting.store.PendingCount() == 1
        assert reporting.StationSets()["sets"][0]["pending"] == 1
        # Nothing sent to start.gg yet
        assert send.sent == []

        pending = reporting.Submissions()
        assert len(pending) == 1 and pending[0]["conflicts"] == []
        assert pending[0]["station"] == "Setup 5" and pending[0]["address"] == "10.0.0.9"

        assert reporting.Approve(result["id"], {}, "Admin")["ok"]
        query, variables = send.sent[-1]
        assert query == REPORT_SET
        assert variables["setId"] == "1" and variables["winnerId"] == "e1"
        assert len(variables["gameData"]) == 3
        assert reporting.store.PendingCount() == 0
        assert reporting.cache.Find("1")["state"] == COMPLETED
        assert reporting.cache.Find("1")["scores"] == [2, 1]
        # Can't be approved twice
        assert Error(reporting.Approve(result["id"], {})) == "RESOLVED"
        assert [e["action"] for e in reporting.store.Log()] == ["approved", "submitted"]
    finally:
        shutil.rmtree(folder)


def TestApproveEditedAndConflicts():
    reporting, fetcher, send, clock, folder = Setup([Node(1, state=IN_PROGRESS)])
    try:
        first = reporting.Submit({"setId": "1", "games": Games(1, 1)})["id"]
        second = reporting.Submit({"setId": "1", "games": Games(2, 2)})["id"]
        conflicts = {s["id"]: s["conflicts"] for s in reporting.Submissions()}
        assert conflicts == {first: [CONFLICT_DUPLICATE], second: [CONFLICT_DUPLICATE]}

        # Reported on start.gg meanwhile
        clock.now += 60
        fetcher.nodes["1"] = Node(1, state=COMPLETED, updatedAt=int(clock.now))
        reporting.Sets(force=True)
        assert CONFLICT_COMPLETED in reporting.Submissions()[0]["conflicts"]
        assert Error(reporting.Approve(second, {})) == "SET_COMPLETED"
        assert send.sent == []

        # Approved anyway, edited: reset then reported
        result = reporting.Approve(second, {"force": True, "games": Games(2, 1, 2)})
        assert result["ok"], result
        assert [q for q, _v in send.sent] == [RESET_SET, REPORT_SET]
        assert send.sent[1][1]["winnerId"] == "e2"
        approved = reporting.store.Get(second)
        assert approved["status"] == APPROVED and approved["score"] == [1, 2]
        assert approved["originalGames"] == NormalizeGames(Games(2, 2))
        # The other result for the set
        assert reporting.store.Get(first)["status"] == SUPERSEDED

        # Players changed on start.gg: can't be approved
        third = reporting.store.Add(ParseSet(Node(1)), Games(1, 1))["id"]
        fetcher.nodes["1"] = Node(1, entrants=("e1", "e9"))
        assert Error(reporting.Approve(third, {})) == "ENTRANTS_CHANGED"
        assert reporting.Reject(third, "wrong players")["ok"]
        assert reporting.store.Get(third)["message"] == "wrong players"
        assert Error(reporting.Reject(third)) == "RESOLVED"
    finally:
        shutil.rmtree(folder)


def TestStationsDisabled():
    reporting, fetcher, send, clock, folder = Setup([Node(1)])
    try:
        SettingsManager.settings = {"web_reporting": {"stations_enabled": False}}
        assert Status(reporting.StationSets()) == 403
        assert Error(reporting.Submit({"setId": "1", "games": Games(1, 1)})) == "STATIONS_DISABLED"
    finally:
        SettingsManager.settings = {}
        shutil.rmtree(folder)


def TestPersistence():
    reporting, fetcher, send, clock, folder = Setup([Node(1)])
    try:
        id = reporting.Submit({"setId": "1", "games": Games(1, 1), "submitter": "Tweek"})["id"]
        store = ReportingStore(reporting.store.path)
        assert store.Get(id)["submitter"] == "Tweek"
        assert store.PendingBySet() == {"1": 1}
        assert store.Log()[0]["action"] == "submitted"

        # A broken file is put aside, not lost
        with open(store.path, "w") as file:
            file.write("{not json")
        store = ReportingStore(store.path)
        assert store.Submissions() == []
        assert os.path.exists(store.path + ".broken")
    finally:
        shutil.rmtree(folder)


# =====================================================
# ADMIN ACTIONS
# =====================================================
def TestAdminActions():
    reporting, fetcher, send, clock, folder = Setup([Node(1), Node(2, state=COMPLETED)])
    try:
        reporting.Sets()
        # A pending result is dropped once the set is reported from here
        reporting.Submit({"setId": "1", "games": Games(2, 2)})
        assert reporting.Action("1", "call", {})["set"]["state"] == CALLED
        assert send.sent[-1] == (MARK_SET_CALLED, {"setId": "1"})

        result = reporting.Action("1", "update", {"games": Games(1)})
        assert send.sent[-1][0] == UPDATE_SET and "winnerId" not in send.sent[-1][1]
        assert result["set"]["state"] == IN_PROGRESS and result["set"]["scores"] == [1, 0]
        assert Error(reporting.Action("1", "update", {"games": []})) == "NO_GAMES"

        assert reporting.Action("1", "report", {"games": Games(1, 2)})[1] == 400
        assert reporting.store.PendingCount() == 1
        assert reporting.Action("1", "report", {"games": Games(1)})["ok"]

        assert reporting.store.PendingCount() == 0
        assert reporting.Action("1", "dq", {"winner": 2})["ok"]
        assert send.sent[-1] == (REPORT_DQ, {"winnerId": "e2", "setId": "1"})
        assert reporting.store.PendingCount() == 0
        assert Error(reporting.Action("1", "dq", {})) == "NO_WINNER"

        # Completed: reported again only when forced, after a reset
        assert Error(reporting.Action("2", "report", {"games": Games(2, 2)})) == "SET_COMPLETED"
        sent = len(send.sent)
        assert reporting.Action("2", "report", {"games": Games(2, 2), "force": True})["ok"]
        assert [q for q, _v in send.sent[sent:]] == [RESET_SET, REPORT_SET]

        reset = reporting.Action("2", "reset", {})["set"]
        assert reset["state"] == NOT_STARTED and reset["winnerId"] is None

        station = reporting.Action("1", "assign_station", {"stationId": "s5"})["set"]["station"]
        assert station == {"id": "s5", "number": 5}
        stream = reporting.Action("1", "assign_stream", {"streamId": "t1"})
        assert stream["set"]["stream"] == {"id": "t1", "name": "main"}

        # start.gg refusing or unreachable
        send.error = ReportError("Set is not editable")
        result = reporting.Action("1", "start", {})
        assert Status(result) == 502 and result[0]["message"] == "Set is not editable"
        send.error = RetryableError("timeout")
        assert Status(reporting.Action("1", "start", {})) == 504
        assert reporting.store.Log()[0]["ok"] is False

        assert Error(reporting.Action("1", "explode", {})) == "UNKNOWN_ACTION"
        reporting.HasToken = lambda: False
        assert Error(reporting.Action("1", "call", {})) == "NO_TOKEN"
    finally:
        shutil.rmtree(folder)


def TestMissingSet():
    reporting, fetcher, send, clock, folder = Setup([Node(1)])
    try:
        result = WebReporting.Run(reporting.Action, "404", "call", {})
        assert Error(result) == "NO_SET" and Status(result) == 404
        fetcher.down = True
        assert Status(WebReporting.Run(reporting.Action, "1", "call", {})) == 504
        assert Error(WebReporting.Run(reporting.Approve, "nope", {"games": "x"})) == "NO_SUBMISSION"
    finally:
        shutil.rmtree(folder)


# =====================================================
# STATION PIN
# =====================================================
def TestStationPin():
    SettingsManager.settings = {}
    assert WebReporting.StationTokenValid(None)
    SettingsManager.settings = {"web_reporting": {"station_pin": "4321"}}
    token = WebReporting.StationTokenFor("4321")
    assert WebReporting.StationTokenValid(token)
    assert not WebReporting.StationTokenValid(None)
    assert not WebReporting.StationTokenValid(WebReporting.StationTokenFor("1234"))
    # Not the dashboard's token
    from src.WebDashboard import TokenFor

    assert not WebReporting.StationTokenValid(TokenFor("4321"))
    SettingsManager.settings = {}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
