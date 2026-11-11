# Checks the web server's actions (src/WebActionRegistry.py): an action's HTTP
# route and its socket.io event call the same method with the same arguments,
# on the thread the registry says; every route reaches its own action; a
# scoreboard number that doesn't exist is answered with 404 before anything
# is changed; events are answered on the events clients listen to; a busy GUI
# thread is a 503; and slow work (the bracket, a game's assets) is kept off
# the GUI thread. The program's widgets are replaced by fakes.
# Run from the repository root: python test/test_web_actions.py
import asyncio
import json
import os
import re
import sys
import threading
import types
import urllib.parse

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from src import WebServer as WebServerModule
from src import WebServerActions as ActionsModule
from src.Helpers import QtHelper
from src.ScoreboardManager import ScoreboardManager
from src.StateManager import StateManager
from src.WebActionRegistry import ACTIONS, ACTIONS_BY_NAME
from src.WebServer import WebServer, api, sio
from src.WebServerActions import WebServerActions

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURE = os.path.join(FIXTURE, "web_server_surface.json")

# Adds the file route, which matches every path, after the actions' routes
server = WebServer()


# =====================================================
# REQUESTS
# =====================================================
class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.text = body.decode()

    def json(self):
        return json.loads(self.text)


def Http(method, url, body=None):
    """Sends an HTTP request to the server's app, with body as JSON."""
    path, _, query = url.partition("?")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": urllib.parse.unquote(path),
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": urllib.parse.quote(query, safe="=&%").encode(),
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 5500),
    }
    received = []
    sent = [json.dumps(body).encode() if body is not None else b""]

    async def receive():
        if sent:
            return {"type": "http.request", "body": sent.pop(), "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        received.append(message)

    asyncio.run(api(scope, receive, send))
    status = next(m["status"] for m in received if m["type"] == "http.response.start")
    content = b"".join(m.get("body", b"") for m in received if m["type"] == "http.response.body")
    return Response(status, content)


class client:
    get = staticmethod(lambda url: Http("GET", url))
    post = staticmethod(lambda url, json=None: Http("POST", url, json))


# =====================================================
# FAKES
# =====================================================
class Executor:
    """Stands for the GUI thread: runs the calls inline and counts them."""

    def __init__(self):
        self.calls = 0
        self.inside = False
        self.busy = False

    def run_sync(self, fn, timeout=None):
        assert timeout is not None, "calls from the web server must not wait forever"
        if self.busy:
            raise TimeoutError("busy")
        self.calls += 1
        self.inside = True
        try:
            return fn()
        finally:
            self.inside = False


class FakeSignal:
    def __init__(self, executor=None):
        self.emitted = []
        self.executor = executor

    def emit(self, *args):
        self.emitted.append((args, self.executor.inside if self.executor else None))


class FakeStats:
    def __init__(self):
        self.signals = types.SimpleNamespace(
            RecentSetsSignal=FakeSignal(), UpsetFactorCalculation=FakeSignal()
        )


class FakeScoreboard:
    def __init__(self, number):
        self.scoreboardNumber = number
        self.stats = FakeStats()
        self.cleared = 0

    def ClearScore(self):
        self.cleared += 1


class FakeManager:
    """Stands for ScoreboardManager, with two scoreboards."""

    def __init__(self):
        self.scoreboardholder = [FakeScoreboard(1), FakeScoreboard(2)]

    def GetScoreboardNumbers(self):
        return [1, 2]

    def GetScoreboard(self, number):
        return ScoreboardManager.GetScoreboard(self, number)


class Recorder:
    """Stands for WebServerActions: records the calls instead of doing them."""

    scoreboard_number = WebServerActions.scoreboard_number

    def __init__(self):
        self.scoreboard = FakeManager()
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args):
            self.calls.append((name, args, threading.current_thread()))
            return "OK"

        return method


def RealActions():
    actions = WebServerActions.__new__(WebServerActions)
    actions.scoreboard = FakeManager()
    actions.commentaryWidget = types.SimpleNamespace(LoadCommFromTagSignal=FakeSignal())
    return actions


def Setup(actions=None):
    QtHelper.gui_executor = Executor()
    WebServer.actions = actions or Recorder()
    return WebServer.actions


def Emit(event, message=None, sid="client"):
    """Sends a socket.io event like a client would. Returns what the server
    emitted, as [(event, data, to)], and the acknowledgement."""
    sent = []

    async def emit(event, data=None, to=None, **kwargs):
        sent.append((event, data, to))

    real = sio.emit
    sio.emit = emit
    try:
        ack = asyncio.run(sio.handlers["/"][event](sid, message))
    finally:
        sio.emit = real
    return sent, ack


# =====================================================
# HTTP AND SOCKET.IO CALL THE SAME
# =====================================================
# action: (HTTP method, URL, JSON body), socket message, the arguments both
# must call the action with. None where the action doesn't have one of them.
BODY = {"scoreboardNumber": 2, "team": 1, "player": 1, "commentator": 2, "codename": "bf"}
SCORE = {"scoreboard": 2, "team1score": 3}
SB2 = {"scoreboardNumber": "2"}
CASES = {
    "ruleset": (("GET", "/ruleset?scoreboard=2"), SB2, ("2",)),
    "stage_clicked": (("POST", "/stage_strike_stage_clicked", BODY), BODY, (BODY, 2, 1)),
    "confirm_clicked": (("POST", "/stage_strike_confirm_clicked", BODY), BODY, (2, 1)),
    "report_characters": (("POST", "/stage_strike_report_characters", BODY), BODY, (BODY, 2, 1)),
    "character_select_report": (("POST", "/character_select_report", BODY), None, (BODY, 2, 1)),
    "rps_win": (("POST", "/stage_strike_rps_win", {"winner": 1}), {"winner": 1}, (1, 1, None)),
    "match_win": (("POST", "/stage_strike_match_win", {"winner": 0}), {"winner": 0}, (0, 1, None)),
    "set_gentlemans": (
        ("POST", "/stage_strike_set_gentlemans?team=2", {"value": True}),
        {"value": True, "team": "2"},
        (True, 1, "2"),
    ),
    "stage_strike_undo": (("POST", "/stage_strike_undo?scoreboard=2"), SB2, (2, None)),
    "stage_strike_redo": (("POST", "/stage_strike_redo", {}), {}, (1, None)),
    "reset": (("POST", "/stage_strike_reset"), {}, (1, None)),
    "post_score": (("POST", "/score", SCORE), json.dumps(SCORE), (2, SCORE)),
    "team_scoreup": (("GET", "/scoreboard2-team1-scoreup"), BODY, (2, 1)),
    "team_scoredown": (("GET", "/scoreboard1-team2-scoredown"), {"team": "2"}, (1, 2)),
    "team_color": (
        ("GET", "/scoreboard1-team2-color-fe3636"),
        {"team": 2, "color": "fe3636"},
        (1, 2, "#fe3636"),
    ),
    "team_info": (("POST", "/scoreboard2-team1-info", BODY), BODY, (2, 1, BODY)),
    "team_battle_scoreup": (("GET", "/team-battle-team1-scoreup"), {"team": "1"}, ("1",)),
    "team_battle_scoredown": (("GET", "/team-battle-team2-scoredown"), {"team": "2"}, ("2",)),
    "team_battle_next_player": (("GET", "/team-battle-team1-next-player"), {"team": "1"}, ("1",)),
    "team_battle_set_active": (
        ("GET", "/team-battle-team2-player3-active"),
        {"team": "2", "player": "3"},
        ("2", "3"),
    ),
    "team_battle_reset_stocks": (("GET", "/team-battle-reset-stocks"), None, ()),
    "team_battle_reset": (("GET", "/team-battle-reset"), {}, ()),
    "get_team_battle": (("GET", "/team-battle-get"), None, ()),
    "get_scoreboard": (("GET", "/scoreboard2-get"), None, (2,)),
    "set_route": (
        (
            "GET",
            "/scoreboard2-set?best-of=5&phase=Top 8&match=&players=2&characters=1&losers=false&team=1",
        ),
        {
            "scoreboardNumber": 2,
            "best_of": 5,
            "phase": "Top 8",
            "match": "",
            "players": 2,
            "characters": "1",
            "losers": False,
            "team": "1",
        },
        (2, 5, "Top 8", "", 2, 1, False, "1"),
    ),
    "set_team_data": (("POST", "/scoreboard2-update-team-1-1", BODY), BODY, (2, 1, 1, BODY)),
    "set_commentary_data": (("POST", "/update-commentary-2", BODY), BODY, (2, BODY)),
    "set_game": (("POST", "/update-game", BODY), BODY, (BODY,)),
    "get_games": (("GET", "/games"), None, ()),
    "get_current_game": (("GET", "/current-game"), None, ()),
    "get_match_names": (("GET", "/match-names"), None, ()),
    "get_characters": (("GET", "/characters"), None, ()),
    "get_variants": (("GET", "/variants"), None, ()),
    "swap_teams": (("GET", "/scoreboard2-swap-teams"), SB2, (2,)),
    "get_swap": (("GET", "/scoreboard2-get-swap"), SB2, (2,)),
    "open_sets": (("GET", "/scoreboard2-open-set"), SB2, (2,)),
    "pull_stream_set": (("GET", "/scoreboard2-pull-stream"), SB2, (2,)),
    "stats_recent_sets": (("GET", "/scoreboard2-stats-recent-sets"), SB2, (2,)),
    "stats_upset_factor": (("GET", "/scoreboard2-stats-upset-factor"), SB2, (2,)),
    "stats_last_sets": (
        ("GET", "/scoreboard1-stats-last-sets-both"),
        {"player": "both"},
        (1, "both"),
    ),
    "stats_history_sets": (
        ("GET", "/scoreboard1-stats-history-sets-1"),
        {"player": "1"},
        (1, "1"),
    ),
    "stats_refresh": (("GET", "/scoreboard2-stats-refresh"), None, (2,)),
    "commentary_preview": (("POST", "/commentary-preview", BODY), None, (BODY,)),
    "reset_scores": (("GET", "/scoreboard2-reset-scores"), SB2, (2,)),
    "reset_match": (("GET", "/scoreboard2-reset-match"), SB2, (2,)),
    "reset_players": (("GET", "/scoreboard2-reset-players"), SB2, (2,)),
    "clear_all": (("GET", "/scoreboard2-clear-all"), SB2, (2,)),
    "get_sets": (("GET", "/get-sets?getFinished"), {"getFinished": True}, (True,)),
    "get_match": (("GET", "/get-match-42"), {"setId": 42}, (42,)),
    "get_comms": (("GET", "/get-comms"), None, ()),
    "load_set": (
        ("GET", "/scoreboard1-load-set?set=99&no-mains"),
        {"set": "99", "no-mains": True},
        (1, "99", True),
    ),
    "get_set": (("GET", "/scoreboard2-get-set"), SB2, (2,)),
    "get_playerdb": (("GET", "/playerdb"), None, ()),
    "update_bracket": (("GET", "/update-bracket"), None, ()),
    "update_bracket_sets": (("GET", "/update-bracket-sets"), None, ()),
    "stream_queue": (("GET", "/stream-queue"), None, ()),
    "stream_queue_refresh": (("GET", "/stream-queue/refresh"), None, ()),
    "stream_queue_load_next": (
        ("GET", "/stream-queue/load-next?stream=main"),
        None,
        ("main", None),
    ),
    "bracket_focus": (("GET", "/bracket-focus?channel=side"), {"channel": "side"}, ("side",)),
    "bracket_focus_set": (
        ("POST", "/bracket-focus", {"move": 1}),
        {"move": 1},
        ({"move": 1}, None),
    ),
    "display_state": (("GET", "/display/state"), None, ()),
    "display_all": (("GET", "/display/all/hide"), None, ("hide",)),
    "display": (
        ("GET", "/display/folder/scoreboard/toggle"),
        None,
        ("folder", "scoreboard", "toggle"),
    ),
    "display_register": (None, {"groups": ["main"]}, (["main"],)),
    "load_player_from_tag": (
        ("GET", "/scoreboard2-load-player-from-tag-1-2?tag=A%26amp%3BB"),
        {"scoreboardNumber": 2, "tag": "A&amp;B", "team": 1, "player": 2},
        (2, "A&B", 1, 2, False),
    ),
    "load_commentator_from_tag": (
        ("GET", "/load-commentator-from-tag-1?tag=X&no-mains"),
        {"commentator": 1, "tag": "X", "no-mains": 1},
        (1, "X", True),
    ),
    "load_tournament": (
        ("GET", "/set-tournament?url=start.gg/t"),
        {"url": "start.gg/t"},
        ("start.gg/t",),
    ),
    "get_tournament_events": (
        ("GET", "/tournament-events?url=start.gg/t"),
        {"url": "start.gg/t"},
        ("start.gg/t",),
    ),
    "get_states": (("GET", "/states?countryCode=BR"), {"countryCode": "BR"}, ("BR",)),
    "set_current_stage": (("POST", "/scoreboard2-set-current-stage", BODY), BODY, (2, "bf")),
}


def TestHttpAndSocketCallTheSame():
    assert set(CASES) == set(ACTIONS_BY_NAME), set(CASES) ^ set(ACTIONS_BY_NAME)
    assert len(ACTIONS_BY_NAME) == len(ACTIONS), "two actions with the same name"

    for action in ACTIONS:
        request, message, expected = CASES[action.name]
        assert (request is None) == (not action.http), action.name
        calls = []

        if request is not None:
            actions = Setup()
            response = Http(*request)
            assert response.status_code == 200 and response.text == "OK", (
                action.name,
                response.status_code,
                response.text,
            )
            calls.append(("HTTP", actions, QtHelper.gui_executor))

        # No message is the same as an empty one
        if action.socket and (message is not None or not action.params):
            actions = Setup()
            sent, ack = Emit(action.socket, message)
            assert sent == [(reply, "OK", "client") for reply in action.replies], (
                action.name,
                sent,
            )
            assert ack == "OK", (action.name, ack)
            calls.append(("socket", actions, QtHelper.gui_executor))
        elif action.socket:
            raise AssertionError(f"{action.name} has no socket message to test with")

        for transport, actions, executor in calls:
            assert [c[:2] for c in actions.calls] == [(action.name, expected)], (
                transport,
                action.name,
                actions.calls,
            )
            # On the GUI thread or off it, as the registry says, and never on
            # the server's own thread
            assert executor.calls == (1 if action.gui else 0), (transport, action.name)
            assert actions.calls[0][2] is not threading.main_thread(), (transport, action.name)
    print("TestHttpAndSocketCallTheSame: OK")


def TestParameterNames():
    # Both spellings of best of, on both sides
    actions = Setup()
    assert Http("GET", "/scoreboard1-set?best_of=3").status_code == 200
    Emit("set", {"best-of": "3"})
    assert [c[1][:2] for c in actions.calls] == [(1, 3), (1, 3)]

    # The query string picks the stage strike's scoreboard and team over the body
    actions = Setup()
    Http("POST", "/stage_strike_undo?scoreboard=2&team=2", {"scoreboardNumber": 1, "team": 1})
    assert actions.calls[0][1] == (2, "2")

    # The links take POST too, with their parameters in a JSON body
    actions = Setup()
    assert Http("POST", "/scoreboard2-load-set", {"set": "7"}).status_code == 200
    assert actions.calls[0][:2] == ("load_set", (2, "7", False))

    # Parameters that aren't what they should be are refused before the action
    actions = Setup()
    for url in (
        "/scoreboard1-team3-scoreup",
        "/scoreboard1-set?best-of=many",
        "/get-match-abc",
        "/update-commentary-first",
    ):
        method = "POST" if "commentary" in url else "GET"
        assert Http(method, url).status_code == 400, url
    sent, ack = Emit("team_color", {"team": 1})
    assert sent == [("team_color", {"error": "color not specified", "status": 400}, "client")]
    assert actions.calls == []
    print("TestParameterNames: OK")


# =====================================================
# ROUTES
# =====================================================
SAMPLE = {
    "scoreboardNumber": "1",
    "team": "1",
    "player": "1",
    "caster": "1",
    "setId": "5",
    "color": "ff0000",
    "kind": "folder",
    "name": "x",
    "action": "show",
}


def TestEveryRouteReachesItsAction():
    # A route registered before another could take its requests
    for action in ACTIONS:
        for route in action.http:
            url = re.sub(r"{(\w+)(:\w+)?}", lambda m: SAMPLE[m.group(1)], route.path)
            for method in route.methods:
                actions = Setup()
                response = Http(method, url)
                assert response.status_code == 200, (method, url, response.status_code)
                assert [c[0] for c in actions.calls] == [action.name], (method, url, actions.calls)

    # The pages and files still come after them
    Setup()
    assert client.get("/wiki/search?q=x").status_code == 200
    assert client.get("/no-such-file").status_code == 404
    assert client.get("/user_data/settings.json").status_code == 403

    # The list of endpoints, with their parameters
    paths = client.get("/openapi.json").json()["paths"]
    link = paths["/scoreboard{scoreboardNumber}-load-set"]
    assert {p["name"] for p in link["get"]["parameters"]} == {"scoreboardNumber", "set", "no-mains"}
    assert "requestBody" in link["post"] and "requestBody" not in link["get"]
    print("TestEveryRouteReachesItsAction: OK")


def TestReplyEvents():
    # The events each action answers with, as clients listen to them
    with open(FIXTURE, encoding="utf-8") as f:
        expected = json.load(f)["replies"]
    actual = {action.socket: list(action.replies) for action in ACTIONS if action.socket}
    for event, replies in expected.items():
        assert actual.get(event) == replies, (event, actual.get(event), replies)

    Setup()
    assert [s[0] for s in Emit("team_color", {"team": 1, "color": "fff"})[0]] == ["team_color"]
    assert [s[0] for s in Emit("current_game")[0]] == ["current_game", "get_current_game"]
    assert [s[0] for s in Emit("bracket_focus_set", {"move": 1})[0]] == ["bracket_focus"]
    # Answered through the acknowledgement only
    assert Emit("states", {"countryCode": "BR"}) == ([], "OK")
    assert Emit("display_register", {"groups": []})[0] == []
    print("TestReplyEvents: OK")


def TestHandWrittenRequests():
    # They run registry actions too
    actions = Setup()
    assert client.get("/bracket-focus/next-round?channel=side").status_code == 200
    assert actions.calls[0][:2] == ("bracket_focus_set", ({"move": 1}, "side"))
    assert client.get("/bracket-focus/nope").status_code == 404

    actions = Setup()
    WebServerModule._client.sid = None
    emitted = []
    real = WebServerModule.ws_emit
    WebServerModule.ws_emit = lambda event, *args: emitted.append((event, *args))
    try:
        asyncio.run(sio.handlers["/"]["display"]("client", {"group": "main", "action": "hide"}))
        assert actions.calls[0][:2] == ("display", ("group", "main", "hide"))
        assert emitted == [("display", "OK")]

        # What the program sends to every client (see HyperDrive.py)
        del emitted[:]
        actions = Setup()
        WebServer.ws_ruleset({"scoreboardNumber": 2})
        WebServer.ws_get_characters()
        server.ws_playerdb()
        assert [c[:2] for c in actions.calls] == [
            ("ruleset", (2,)),
            ("get_characters", ()),
            ("get_playerdb", ()),
        ]
        assert emitted == [("ruleset", "OK"), ("characters", "OK"), ("playerdb", "OK")]
    finally:
        WebServerModule.ws_emit = real
    print("TestHandWrittenRequests: OK")


# =====================================================
# SCOREBOARD NUMBERS
# =====================================================
def TestInvalidScoreboard():
    # There are scoreboards 1 and 2
    manager = FakeManager()
    assert manager.GetScoreboard(2) is manager.scoreboardholder[1]
    for number in (0, 3, 7, -1, "x", None):
        assert manager.GetScoreboard(number) is None, number

    state = json.dumps(StateManager.state, sort_keys=True, default=str)
    for actions in (Setup(), Setup(RealActions())):
        for number in ("7", "0", "-1", "1.team", "abc", "1.0", "²"):
            for method, url, body in (
                ("GET", f"/scoreboard{number}-clear-all", None),
                ("GET", f"/scoreboard{number}-team1-scoreup", None),
                ("GET", f"/scoreboard{number}-get", None),
                ("POST", f"/scoreboard{number}-set-current-stage", {"codename": "bf"}),
                ("POST", f"/stage_strike_undo?scoreboard={number}", None),
                ("POST", "/stage_strike_reset", {"scoreboardNumber": number}),
                ("POST", "/score", {"scoreboard": number, "team1score": 1}),
            ):
                response = Http(method, url, body)
                assert response.status_code == 404, (method, url, body, response.status_code)

            for event, message in (
                ("clear_all", {"scoreboardNumber": number}),
                ("set_current_stage", {"scoreboardNumber": number, "codename": "bf"}),
                ("stage_strike_undo", {"scoreboardNumber": number}),
                ("score", {"scoreboard": number}),
            ):
                sent, ack = Emit(event, message)
                assert [s[0] for s in sent] == [event] and sent[0][1]["status"] == 404, sent
                assert ack == sent[0][1]

        # Nothing was called, cleared or written to the state
        if isinstance(actions, Recorder):
            assert actions.calls == []
        assert [s.cleared for s in actions.scoreboard.scoreboardholder] == [0, 0]
        assert json.dumps(StateManager.state, sort_keys=True, default=str) == state

    # 503 while the program has no scoreboard yet
    actions = Setup()
    actions.scoreboard.GetScoreboardNumbers = lambda: []
    assert client.get("/scoreboard1-clear-all").status_code == 503
    print("TestInvalidScoreboard: OK")


# =====================================================
# THE ACTIONS THEMSELVES
# =====================================================
def TestStatsEventsReply():
    for event, signal in (
        ("stats_recent_sets", "RecentSetsSignal"),
        ("stats_upset_factor", "UpsetFactorCalculation"),
    ):
        actions = Setup(RealActions())
        # A player in the message, as the old handlers read, doesn't matter
        sent, ack = Emit(event, {"scoreboardNumber": 2, "player": 1})
        assert sent == [(event, "OK", "client")], sent
        first, second = actions.scoreboard.scoreboardholder
        assert len(getattr(second.stats.signals, signal).emitted) == 1
        assert len(getattr(first.stats.signals, signal).emitted) == 0

        url = "/scoreboard1-" + event.replace("_", "-")
        assert client.get(url).text == "OK"
        assert len(getattr(first.stats.signals, signal).emitted) == 1
    print("TestStatsEventsReply: OK")


def TestCommentatorFromTag():
    actions = Setup(RealActions())
    assert client.get("/load-commentator-from-tag-2?tag=Tag").text == "OK"
    assert actions.commentaryWidget.LoadCommFromTagSignal.emitted[0][0] == (1, "Tag", False)
    assert client.get("/load-commentator-from-tag-2").text == "No tag provided"
    assert Emit("load_commentator_from_tag", {"commentator": 1})[0][0][1] == "No tag provided"
    print("TestCommentatorFromTag: OK")


def TestGuiTimeout():
    Setup()
    QtHelper.gui_executor.busy = True
    response = client.get("/scoreboard1-clear-all")
    assert (response.status_code, response.text) == (503, "GUI_BUSY")
    sent, ack = Emit("clear_all", {})
    assert sent == [("clear_all", {"error": "GUI_BUSY", "status": 503}, "client")]
    # Actions that don't need the GUI thread still answer
    assert client.get("/games").status_code == 200
    print("TestGuiTimeout: OK")


def TestUpdateBracketFetchesOffTheGuiThread():
    actions = Setup(RealActions())
    executor = QtHelper.gui_executor
    fetched = []

    class Provider:
        def GetTournamentPhases(self):
            fetched.append(executor.inside)
            return [{"name": "Bracket", "groups": [{"id": 5, "name": "A"}]}]

        def GetTournamentPhaseGroup(self, id):
            fetched.append(executor.inside)
            return {"id": id}

    updated = FakeSignal(executor)
    real = ActionsModule.TournamentDataManager.instance
    ActionsModule.TournamentDataManager.instance = types.SimpleNamespace(
        provider=Provider(), signals=types.SimpleNamespace(tournament_phasegroup_updated=updated)
    )
    bracket = StateManager.state.pop("bracket", None)
    try:
        assert client.get("/update-bracket").text == "OK"
    finally:
        ActionsModule.TournamentDataManager.instance = real
        if bracket is not None:
            StateManager.state["bracket"] = bracket
    # The provider's requests weren't made on the GUI thread, showing the
    # result was
    assert fetched == [False, False]
    assert updated.emitted == [(({"id": 5, "phaseGroupId": 5},), True)]
    print("TestUpdateBracketFetchesOffTheGuiThread: OK")


def TestSetGameLoadsOffTheGuiThread():
    Setup(RealActions())
    executor = QtHelper.gui_executor
    loads = []

    class Loader:
        def wait(self, ms):
            # The request waits for the assets outside the GUI thread
            loads.append(("wait", executor.inside))
            return True

    class Manager:
        games = {"ssbu": {}, "sf6": {}}
        assetsLoaderThread = None

        def LoadGameAssets(self, game, **options):
            # Started like the program does: its loader thread loads them
            assert "async_mode" not in options
            loads.append((game, options, executor.inside))
            self.assetsLoaderThread = Loader()

    real = ActionsModule.GameAssetManager.instance
    ActionsModule.GameAssetManager.instance = Manager()
    try:
        assert client.post("/update-game", json={"codename": "sf6"}).text == "OK"
        assert loads == [
            (2, {"mods_active": False, "mods_reload_mode": True}, True),
            ("wait", False),
        ]
        assert (
            client.post("/update-game", json={"codename": "nope"}).text
            == "Could not find game nope"
        )
    finally:
        ActionsModule.GameAssetManager.instance = real
    print("TestSetGameLoadsOffTheGuiThread: OK")


# =====================================================
# PROGRAM STATE
# =====================================================
def TestProgramStateIsReadUnderTheLock():
    class Lock:
        def __init__(self, lock):
            self.lock = lock
            self.held = 0
            self.entered = 0

        def __enter__(self):
            self.lock.acquire()
            self.held += 1
            self.entered += 1

        def __exit__(self, *args):
            self.held -= 1
            self.lock.release()

    realLock, realState, realIndex = StateManager.lock, StateManager.state, StateManager.deltaIndex
    lock = Lock(realLock)
    StateManager.lock = lock
    StateManager.state = {"score": {"1": {"best_of": 3}}, "game": {"name": "x"}}
    StateManager.deltaIndex = 12
    try:
        response = client.get("/program-state")
        assert response.json() == {"state": StateManager.state, "delta_index": 12}
        assert lock.entered == 1 and lock.held == 0

        # The message for socket clients is a copy, read under the lock too
        message = WebServerModule.program_state_message()
        assert message == {"state": StateManager.state, "delta_index": 12}
        assert message["state"] is not StateManager.state
        assert message["state"]["score"] is not StateManager.state["score"]
        assert lock.entered == 2 and lock.held == 0
    finally:
        StateManager.lock, StateManager.state, StateManager.deltaIndex = (
            realLock,
            realState,
            realIndex,
        )
    print("TestProgramStateIsReadUnderTheLock: OK")


if __name__ == "__main__":
    realExecutor, realActions = QtHelper.gui_executor, WebServer.actions
    try:
        TestHttpAndSocketCallTheSame()
        TestParameterNames()
        TestEveryRouteReachesItsAction()
        TestReplyEvents()
        TestHandWrittenRequests()
        TestInvalidScoreboard()
        TestStatsEventsReply()
        TestCommentatorFromTag()
        TestGuiTimeout()
        TestUpdateBracketFetchesOffTheGuiThread()
        TestSetGameLoadsOffTheGuiThread()
        TestProgramStateIsReadUnderTheLock()
    finally:
        QtHelper.gui_executor, WebServer.actions = realExecutor, realActions
