import asyncio
import html
import json
import logging
import mimetypes
import os
import socket
import threading
import traceback

import orjson
import socketio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from sqladmin import Admin, ModelView
from starlette.concurrency import run_in_threadpool
from starlette.convertors import Convertor, register_url_convertor

from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TSHCommentaryWidget import TSHCommentaryWidget
from .TSHPlayerDB import TSHPlayerDB
from .TSHPlayerDBModels import GetEngine, Player
from .TSHScoreboardManager import TSHScoreboardManager
from .TSHWebServerActions import ScoreboardNotAvailable, WebServerActions

log = logging.getLogger("socketio.server")
log.setLevel(logging.ERROR)


class SocketioJson:
    def default(obj):
        if isinstance(obj, type(int)):
            return str(obj)
        return obj

    def dumps(obj, **kwargs):
        # Socket.IO only asks for compact JSON, which orjson writes several
        # times faster than json (this encodes every state update).
        if kwargs.get("separators", (",", ":")) == (",", ":") and set(kwargs) <= {"separators"}:
            try:
                return orjson.dumps(
                    obj, default=SocketioJson.default, option=orjson.OPT_NON_STR_KEYS
                ).decode()
            except TypeError:
                pass
        return json.dumps(obj, **kwargs, default=SocketioJson.default)

    def loads(*args, **kwargs):
        return json.loads(*args, **kwargs)


class SegmentConvertor(Convertor):
    """Part of a path segment without "-": routes like
    /scoreboard{n}-team{team}-scoreup split their segment on dashes, so
    /scoreboard1-load-set can't match /scoreboard{n}-set with n = "1-load"."""

    regex = "[^/-]+"

    def convert(self, value):
        return value

    def to_string(self, value):
        return str(value)


register_url_convertor("seg", SegmentConvertor())


def respond(result):
    """Turns what an action returns into a response, like Flask did: text is
    HTML, dicts and lists are JSON and (body, status) tuples set the status."""
    status = 200
    if isinstance(result, tuple):
        result, status = result
    if isinstance(result, Response):
        return result
    if result is None:
        return Response(status_code=status)
    if isinstance(result, str):
        return HTMLResponse(result, status_code=status)
    return Response(
        orjson.dumps(result, default=SocketioJson.default, option=orjson.OPT_NON_STR_KEYS),
        status_code=status,
        media_type="application/json",
    )


async def call(fn, *args, **kwargs):
    """Runs an action in a worker thread (they wait on the GUI thread) and
    returns its response."""
    return respond(await run_in_threadpool(fn, *args, **kwargs))


def parse_message(message):
    if isinstance(message, (str, bytes)):
        try:
            message = orjson.loads(message) if message else {}
        except orjson.JSONDecodeError:
            return {}
    return message if isinstance(message, dict) else {}


def load_message(message):
    """Socket messages are JSON strings, or already decoded by the client."""
    return orjson.loads(message) if isinstance(message, (str, bytes)) else message


api = FastAPI(title="HyperDrive", docs_url="/api/docs", redoc_url=None)
api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    json=SocketioJson,
    # Accept the connection before the connect handler runs, so it can send
    # the program state to the new client
    always_connect=True,
    # Uncomment to enable SocketIO logging (As logging is unuseful, we'll make this a dev flag)
    # logger=True,
)

# The socket.io client of the socket event being handled in this thread
_client = threading.local()


def on(event):
    """Registers a socket event handler. Handlers run in a worker thread,
    where WebServer.ws_emit answers the client that sent the event."""

    def decorator(fn):
        def run(sid, message):
            _client.sid = sid
            try:
                return fn(message)
            except Exception:
                logger.error(traceback.format_exc())
            finally:
                _client.sid = None

        async def handler(sid, message=None, *args):
            return await run_in_threadpool(run, sid, message)

        sio.on(event, handler)
        return fn

    return decorator


@api.middleware("http")
async def log_requests(request: Request, call_next):
    client = request.client.host if request.client else None
    logger.info(f"[HTTP] → {request.method} {request.url.path} from {client}")
    response = await call_next(request)
    logger.info(f"[HTTP] ← {request.method} {request.url.path} [{response.status_code}]")
    return response


@api.exception_handler(ScoreboardNotAvailable)
async def handle_scoreboard_not_available(request: Request, e: ScoreboardNotAvailable):
    return HTMLResponse(str(e), status_code=503)


class PlayerAdmin(ModelView, model=Player):
    name = "Player"
    name_plural = "Players"
    icon = "fa-solid fa-user"
    column_list = [
        Player.tag,
        Player.name,
        Player.twitter,
        Player.country_code,
        Player.state_code,
        Player.pronoun,
    ]
    column_searchable_list = [Player.tag, Player.name, Player.twitter]
    column_sortable_list = [Player.tag, Player.name, Player.country_code]
    column_default_sort = "tag"
    # Made from prefix and gamerTag when saving
    form_excluded_columns = [Player.tag]
    page_size = 50

    # The program keeps the players in memory: load them again after a change
    async def after_model_change(self, data, model, is_created, request):
        await run_in_threadpool(TSHPlayerDB.ReloadDB)

    async def after_model_delete(self, model, request):
        await run_in_threadpool(TSHPlayerDB.ReloadDB)


class WebServer(QThread):
    api = api
    sio = sio
    app = socketio.ASGIApp(sio, other_asgi_app=api)
    actions = None
    # The server's event loop, set while it runs
    loop: asyncio.AbstractEventLoop | None = None
    routesAdded = False

    def __init__(
        self, parent=None, stageWidget=None, commentaryWidget: TSHCommentaryWidget = None
    ) -> None:
        super().__init__(parent)
        WebServer.actions = WebServerActions(
            parent=parent,
            scoreboard=TSHScoreboardManager.instance,
            stageWidget=stageWidget,
            commentaryWidget=commentaryWidget,
        )

        StateManager.signals.state_updated.connect(WebServer.on_program_state_update)
        StateManager.signals.state_big_change.connect(WebServer.ws_program_state)

        self.host_name = "0.0.0.0"
        self.port = SettingsManager.Get("general.webserver_port", 5500)
        self.server: uvicorn.Server | None = None

        if not WebServer.routesAdded:
            WebServer.routesAdded = True
            # Before the file route below, which matches every path
            Admin(api, engine=GetEngine(), title="HyperDrive Player DB").add_view(PlayerAdmin)
            api.add_api_route("/{filename:path}", WebServer.file_request, methods=["GET", "POST"])

    # Don't override the QObject emit() method
    def ws_emit(event, *args, **kwargs):
        """Sends a socket event. In a socket event handler it answers the
        client that sent the event, anywhere else it goes to every client.
        Returns a concurrent.futures.Future, or None if the server isn't
        running."""
        loop = WebServer.loop
        if loop is None or loop.is_closed():
            return None
        sid = getattr(_client, "sid", None)
        data = args[0] if args else None
        return asyncio.run_coroutine_threadsafe(sio.emit(event, data, to=sid), loop)

    @api.get("/program-state")
    async def program_state():
        # orjson encodes the whole state many times faster than json
        return await call(WebServer.actions.program_state)

    @on("program-state-update")
    def ws_program_state_update(message=None):
        # Manual trigger to push full state to all clients
        WebServer.ws_program_state()

    def on_program_state_update(changes):
        if len(changes) > 0:
            future = WebServer.ws_emit("program_state_update", changes)
            if future is not None:
                future.add_done_callback(WebServer._check_state_update_sent)

    def _check_state_update_sent(future):
        if isinstance(future.exception(), (TypeError, ValueError)):
            logger.warning("Unserializable program state update")

            # If we can't emit a diff, fall back to emitting the whole program
            # state. Well-behaved listeners should discard their existing state
            # and re-sync with us that way.
            WebServer.ws_program_state()

    @sio.on("connect")
    async def ws_connect(sid, environ, auth=None):
        await sio.emit(
            "program_state", await run_in_threadpool(WebServer.actions.program_state), to=sid
        )

    @on("program_state")
    def ws_program_state(message=None):
        WebServer.ws_emit("program_state", WebServer.actions.program_state())

    # Stage striking is per scoreboard. HTTP requests pick it with
    # ?scoreboard=<n> or a "scoreboardNumber" field in their JSON body, and
    # socket messages with a "scoreboardNumber" field. Both default to 1.
    parse_message = staticmethod(parse_message)

    def request_scoreboard(request: Request, body=None):
        if request.query_params.get("scoreboard"):
            return request.query_params.get("scoreboard")
        return (body or {}).get("scoreboardNumber", 1)

    async def request_body(request: Request):
        return parse_message(await request.body())

    # Pages for one team (?team=<1|2>) may only strike on their turn, undo
    # their own actions, and need the other team to confirm a game's winner
    def request_team(request: Request, body=None):
        return request.query_params.get("team") or (body or {}).get("team")

    @api.get("/ruleset")
    async def ruleset(request: Request):
        return await call(WebServer.actions.ruleset, WebServer.request_scoreboard(request))

    # The "ruleset" event carries the scoreboard it is for in "scoreboard"
    @on("ruleset")
    def ws_ruleset(message=None):
        info = parse_message(message)
        WebServer.ws_emit("ruleset", WebServer.actions.ruleset(info.get("scoreboardNumber", 1)))

    @api.post("/stage_strike_stage_clicked")
    async def stage_clicked(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.stage_clicked,
            body,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_stage_clicked")
    def ws_stage_clicked(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_stage_clicked",
            WebServer.actions.stage_clicked(
                info, info.get("scoreboardNumber", 1), info.get("team")
            ),
        )

    @api.post("/stage_strike_confirm_clicked")
    async def confirm_clicked(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.confirm_clicked,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_confirm_clicked")
    def ws_confirm_clicked(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_confirm_clicked",
            WebServer.actions.confirm_clicked(info.get("scoreboardNumber", 1), info.get("team")),
        )

    # Characters picked for the next game:
    # {"characters": {team: {player: [[character, skin], ...]}}}
    @api.post("/stage_strike_report_characters")
    async def report_characters(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.report_characters,
            body,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_report_characters")
    def ws_report_characters(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_report_characters",
            WebServer.actions.report_characters(
                info, info.get("scoreboardNumber", 1), info.get("team")
            ),
        )

    # The character select page's picks: like the above, but each team picks
    # once per score (409 ALREADY_PICKED until the score changes)
    @api.post("/character_select_report")
    async def character_select_report(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.character_select_report,
            body,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @api.post("/stage_strike_rps_win")
    async def rps_win(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.rps_win,
            body.get("winner"),
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_rps_win")
    def ws_rps_win(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_rps_win",
            WebServer.actions.rps_win(
                info.get("winner"), info.get("scoreboardNumber", 1), info.get("team")
            ),
        )

    @api.post("/stage_strike_match_win")
    async def match_win(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.match_win,
            body.get("winner"),
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_match_win")
    def ws_match_win(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_match_win",
            WebServer.actions.match_win(
                info.get("winner"), info.get("scoreboardNumber", 1), info.get("team")
            ),
        )

    @api.post("/stage_strike_set_gentlemans")
    async def set_gentlemans(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.set_gentlemans,
            body.get("value"),
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_set_gentlemans")
    def ws_set_gentlemans(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_set_gentlemans",
            WebServer.actions.set_gentlemans(
                info.get("value"), info.get("scoreboardNumber", 1), info.get("team")
            ),
        )

    @api.post("/stage_strike_undo")
    async def stage_strike_undo(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.stage_strike_undo,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_undo")
    def ws_stage_strike_undo(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_undo",
            WebServer.actions.stage_strike_undo(info.get("scoreboardNumber", 1), info.get("team")),
        )

    @api.post("/stage_strike_redo")
    async def stage_strike_redo(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.stage_strike_redo,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_redo")
    def ws_stage_strike_redo(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_redo",
            WebServer.actions.stage_strike_redo(info.get("scoreboardNumber", 1), info.get("team")),
        )

    @api.post("/stage_strike_reset")
    async def reset(request: Request):
        body = await WebServer.request_body(request)
        return await call(
            WebServer.actions.reset,
            WebServer.request_scoreboard(request, body),
            WebServer.request_team(request, body),
        )

    @on("stage_strike_reset")
    def ws_reset(message=None):
        info = parse_message(message)
        WebServer.ws_emit(
            "stage_strike_reset",
            WebServer.actions.reset(info.get("scoreboardNumber", 1), info.get("team")),
        )

    @api.post("/score")
    async def post_score(request: Request):
        return await call(WebServer.actions.post_score, await request.body())

    @on("score")
    def ws_post_score(message=None):
        WebServer.ws_emit("score", WebServer.actions.post_score(message))

    # Ticks score of Team specified up by 1 point
    @api.get("/scoreboard{scoreboardNumber:seg}-team{team:seg}-scoreup")
    async def team_scoreup(scoreboardNumber: str, team: str):
        return await call(WebServer.actions.team_scoreup, scoreboardNumber, team)

    @on("team_scoreup")
    def ws_team_scoreup(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "team_scoreup",
            WebServer.actions.team_scoreup(info.get("scoreboardNumber", "1"), info.get("team")),
        )

    # Ticks score of Team specified down by 1 point
    @api.get("/scoreboard{scoreboardNumber:seg}-team{team:seg}-scoredown")
    async def team_scoredown(scoreboardNumber: str, team: str):
        return await call(WebServer.actions.team_scoredown, scoreboardNumber, team)

    @on("team_scoredown")
    def ws_team_scoredown(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "team_scoredown",
            WebServer.actions.team_scoredown(info.get("scoreboardNumber", "1"), info.get("team")),
        )

    # Set color of team
    @api.get("/scoreboard{scoreboardNumber:seg}-team{team:seg}-color-{color:seg}")
    async def team_color(scoreboardNumber: str, team: str, color: str):
        return await call(WebServer.actions.team_color, scoreboardNumber, team, "#" + color)

    @on("team_color")
    def ws_team_color(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "team_scoredown",
            WebServer.actions.team_color(
                info.get("scoreboardNumber", "1"), info.get("team"), "#" + info.get("color")
            ),
        )

    # Sets a team's name, losers state and/or color
    # Ex. POST /scoreboard1-team2-info {"name": "Team B", "losers": true, "color": "#2e89ff"}
    @api.post("/scoreboard{scoreboardNumber:seg}-team{team:seg}-info")
    async def team_info(scoreboardNumber: str, team: str, request: Request):
        body = await WebServer.request_body(request)
        return await call(WebServer.actions.team_info, scoreboardNumber, team, body)

    @on("team_info")
    def ws_team_info(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "team_info",
            WebServer.actions.team_info(info.get("scoreboardNumber", "1"), info.get("team"), info),
        )

    # Crew/Team Battle
    # A team scores: in Stock Pool the other team's active player loses a
    # stock, in First To the team's active player wins a game
    @api.get("/team-battle-team{team:seg}-scoreup")
    async def team_battle_scoreup(team: str):
        return await call(WebServer.actions.team_battle_scoreup, team)

    @on("team_battle_scoreup")
    def ws_team_battle_scoreup(message=None):
        info = load_message(message) or {}
        WebServer.ws_emit(
            "team_battle_scoreup", WebServer.actions.team_battle_scoreup(info.get("team"))
        )

    # Undoes a team's last point
    @api.get("/team-battle-team{team:seg}-scoredown")
    async def team_battle_scoredown(team: str):
        return await call(WebServer.actions.team_battle_scoredown, team)

    @on("team_battle_scoredown")
    def ws_team_battle_scoredown(message=None):
        info = load_message(message) or {}
        WebServer.ws_emit(
            "team_battle_scoredown", WebServer.actions.team_battle_scoredown(info.get("team"))
        )

    # Makes the team's next player in line who isn't eliminated active
    @api.get("/team-battle-team{team:seg}-next-player")
    async def team_battle_next_player(team: str):
        return await call(WebServer.actions.team_battle_next_player, team)

    @on("team_battle_next_player")
    def ws_team_battle_next_player(message=None):
        info = load_message(message) or {}
        WebServer.ws_emit(
            "team_battle_next_player", WebServer.actions.team_battle_next_player(info.get("team"))
        )

    # Makes a player active, by their number in the team (from 1)
    @api.get("/team-battle-team{team:seg}-player{player:seg}-active")
    async def team_battle_set_active(team: str, player: str):
        return await call(WebServer.actions.team_battle_set_active, team, player)

    @on("team_battle_set_active")
    def ws_team_battle_set_active(message=None):
        info = load_message(message) or {}
        WebServer.ws_emit(
            "team_battle_set_active",
            WebServer.actions.team_battle_set_active(info.get("team"), info.get("player")),
        )

    # Resets every player's stocks/games
    @api.get("/team-battle-reset-stocks")
    async def team_battle_reset_stocks():
        return await call(WebServer.actions.team_battle_reset_stocks)

    @on("team_battle_reset_stocks")
    def ws_team_battle_reset_stocks(message=None):
        WebServer.ws_emit("team_battle_reset_stocks", WebServer.actions.team_battle_reset_stocks())

    # Clears the players and starts the battle over
    @api.get("/team-battle-reset")
    async def team_battle_reset():
        return await call(WebServer.actions.team_battle_reset)

    @on("team_battle_reset")
    def ws_team_battle_reset(message=None):
        WebServer.ws_emit("team_battle_reset", WebServer.actions.team_battle_reset())

    @api.get("/team-battle-get")
    async def get_team_battle():
        return await call(WebServer.actions.get_team_battle)

    @api.get("/scoreboard{scoreboardNumber:seg}-get")
    async def get_route(scoreboardNumber: str):
        return await call(WebServer.actions.get_scoreboard, scoreboardNumber)

    # Dynamic endpoint to allow flexible sets of information
    # Ex. http://192.168.1.2:5000/set?best-of=5
    #
    # Test Scenario that was used
    # Ex. http://192.168.4.34:5000/set?best-of=5&phase=Top 32&match=Winners Finals
    @api.get("/scoreboard{scoreboardNumber:seg}-set")
    async def set_route(scoreboardNumber: str, request: Request):
        args = request.query_params
        return await call(
            WebServer.actions.set_route,
            scoreboardNumber,
            bestOf=args.get("best-of"),
            phase=args.get("phase"),
            match=args.get("match"),
            players=args.get("players"),
            characters=args.get("characters"),
            losers=args.get("losers"),
            team=args.get("team"),
        )

    @on("set")
    def ws_set_route(message=None):
        parsed = load_message(message)
        WebServer.ws_emit(
            "set",
            WebServer.actions.set_route(
                parsed.get("scoreboardNumber", "1"),
                bestOf=parsed.get("best_of"),
                phase=parsed.get("phase"),
                match=parsed.get("match"),
                players=parsed.get("players"),
                characters=parsed.get("characters"),
                losers=parsed.get("losers"),
                team=parsed.get("team"),
            ),
        )

    # Set player data
    @api.post("/scoreboard{scoreboardNumber:seg}-update-team-{team:seg}-{player:seg}")
    async def set_team_data(scoreboardNumber: str, team: str, player: str, request: Request):
        data = await WebServer.request_body(request)
        return await call(WebServer.actions.set_team_data, scoreboardNumber, team, player, data)

    @on("update_team")
    def ws_set_team_data(message=None):
        data = load_message(message)
        WebServer.ws_emit(
            "update_team",
            WebServer.actions.set_team_data(
                data.get("scoreboardNumber", "1"), data.get("team"), data.get("player"), data
            ),
        )

    @api.post("/update-commentary-{caster}")
    async def set_commentary_data(caster: str, request: Request):
        data = await WebServer.request_body(request)
        return await call(WebServer.actions.set_commentary_data, caster, data)

    @on("update_commentary")
    def ws_set_commentary_data(message=None):
        data = load_message(message)
        WebServer.ws_emit(
            "update_commentary",
            WebServer.actions.set_commentary_data(data.get("commentator"), data),
        )

    # Set game
    @api.post("/update-game")
    async def set_game(request: Request):
        data = await WebServer.request_body(request)
        return await call(WebServer.actions.set_game, data)

    @on("update_game")
    def ws_set_game_data(message=None):
        WebServer.ws_emit("update_game", WebServer.actions.set_game(load_message(message)))

    # Get games
    @api.get("/games")
    async def get_games():
        return await call(WebServer.actions.get_games)

    @on("games")
    def ws_get_games(message=None):
        WebServer.ws_emit("games", WebServer.actions.get_games())

    # Get current game
    @api.get("/current-game")
    async def get_current_game():
        return await call(WebServer.actions.get_current_game)

    @on("current_game")
    def ws_get_current_game(message=None):
        WebServer.ws_emit("get_current_game", WebServer.actions.get_current_game())

    # Get match and phase names
    @api.get("/match-names")
    async def get_match_names():
        return await call(WebServer.actions.get_match_names)

    @on("match_names")
    def ws_get_match_names(message=None):
        WebServer.ws_emit("match_names", WebServer.actions.get_match_names())

    # Get characters
    @api.get("/characters")
    async def get_characters():
        return await call(WebServer.actions.get_characters)

    @on("characters")
    def ws_get_characters(message=None):
        WebServer.ws_emit("characters", WebServer.actions.get_characters())

    # Get variants
    @api.get("/variants")
    async def get_variants():
        return await call(WebServer.actions.get_variants)

    @on("variants")
    def ws_get_variants(message=None):
        WebServer.ws_emit("variants", WebServer.actions.get_variants())

    # Swaps teams
    @api.get("/scoreboard{scoreboardNumber:seg}-swap-teams")
    async def swap_teams(scoreboardNumber: str):
        return await call(WebServer.actions.swap_teams, scoreboardNumber)

    @on("swap_teams")
    def ws_swap_teams(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "swap_teams", WebServer.actions.swap_teams(info.get("scoreboardNumber", "1"))
        )

    # Are the teams currently swapped?
    @api.get("/scoreboard{scoreboardNumber:seg}-get-swap")
    async def get_swap(scoreboardNumber: str):
        return await call(WebServer.actions.get_swap, scoreboardNumber)

    @on("get_swap")
    def ws_get_swap(message=None):
        info = load_message(message)
        WebServer.ws_emit("get_swap", WebServer.actions.get_swap(info.get("scoreboardNumber", "1")))

    # Opens Set Selector Window
    @api.get("/scoreboard{scoreboardNumber:seg}-open-set")
    async def open_sets(scoreboardNumber: str):
        return await call(WebServer.actions.open_sets, scoreboardNumber)

    @on("open_set")
    def ws_open_sets(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "open_set", WebServer.actions.open_sets(info.get("scoreboardNumber", "1"))
        )

    # Pulls Current Stream Set
    @api.get("/scoreboard{scoreboardNumber:seg}-pull-stream")
    async def pull_stream_set(scoreboardNumber: str):
        return await call(WebServer.actions.pull_stream_set, scoreboardNumber)

    @on("pull_stream")
    def ws_pull_stream_set(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "pull_stream", WebServer.actions.pull_stream_set(info.get("scoreboardNumber", "1"))
        )

    # Resubmits Call for Recent Sets
    @api.get("/scoreboard{scoreboardNumber:seg}-stats-recent-sets")
    async def stats_recent_sets(scoreboardNumber: str):
        return await call(WebServer.actions.stats_recent_sets, scoreboardNumber)

    @on("stats_recent_sets")
    def ws_stats_recent_sets(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "stats_recent_sets",
            WebServer.actions.stats_recent_sets(
                info.get("scoreboardNumber", "1"), info.get("player")
            ),
        )

    # Resubmits Call for Upset Factor
    @api.get("/scoreboard{scoreboardNumber:seg}-stats-upset-factor")
    async def stats_upset_factor(scoreboardNumber: str):
        return await call(WebServer.actions.stats_upset_factor, scoreboardNumber)

    @on("stats_upset_factor")
    def ws_stats_upset_factor(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "stats_upset_factor",
            WebServer.actions.stats_upset_factor(
                info.get("scoreboardNumber", "1"), info.get("player")
            ),
        )

    # Resubmits Call for Last Sets
    @api.get("/scoreboard{scoreboardNumber:seg}-stats-last-sets-{player}")
    async def stats_last_sets(scoreboardNumber: str, player: str):
        return await call(WebServer.actions.stats_last_sets, scoreboardNumber, player)

    @on("stats_last_sets")
    def ws_stats_last_sets(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "stats_last_sets",
            WebServer.actions.stats_last_sets(
                info.get("scoreboardNumber", "1"), info.get("player")
            ),
        )

    # Resubmits Call for History Sets
    @api.get("/scoreboard{scoreboardNumber:seg}-stats-history-sets-{player}")
    async def stats_history_sets(scoreboardNumber: str, player: str):
        return await call(WebServer.actions.stats_history_sets, scoreboardNumber, player)

    @on("stats_history_sets")
    def ws_stats_history_sets(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "stats_history_sets",
            WebServer.actions.stats_history_sets(
                info.get("scoreboardNumber", "1"), info.get("player")
            ),
        )

    # Resets scores
    @api.get("/scoreboard{scoreboardNumber:seg}-reset-scores")
    async def reset_scores(scoreboardNumber: str):
        return await call(WebServer.actions.reset_scores, scoreboardNumber)

    @on("reset_scores")
    def ws_reset_scores(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "reset_scores", WebServer.actions.reset_scores(info.get("scoreboardNumber", "1"))
        )

    # Resets scores, match, phase, and losers status
    @api.get("/scoreboard{scoreboardNumber:seg}-reset-match")
    async def reset_match(scoreboardNumber: str):
        return await call(WebServer.actions.reset_match, scoreboardNumber)

    @on("reset_match")
    def ws_reset_match(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "reset_match", WebServer.actions.reset_match(info.get("scoreboardNumber", "1"))
        )

    # Resets scores, match, phase, and losers status
    @api.get("/scoreboard{scoreboardNumber:seg}-reset-players")
    async def reset_players(scoreboardNumber: str):
        return await call(WebServer.actions.reset_players, scoreboardNumber)

    @on("reset_players")
    def ws_reset_players(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "reset_players", WebServer.actions.reset_players(info.get("scoreboardNumber", "1"))
        )

    # Resets all values
    @api.get("/scoreboard{scoreboardNumber:seg}-clear-all")
    async def clear_all(scoreboardNumber: str):
        return await call(WebServer.actions.clear_all, scoreboardNumber)

    @on("clear_all")
    def ws_clear_all(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "clear_all", WebServer.actions.clear_all(info.get("scoreboardNumber", "1"))
        )

    # Get thumbnail
    @api.get("/scoreboard{scoreboardNumber:seg}-get-thumbnail-{fileFormat}")
    async def get_thumbnail(scoreboardNumber: str, fileFormat: str):
        if fileFormat.lower() in ["png", "jpg"]:
            result = await run_in_threadpool(
                WebServer.actions.get_thumbnail, scoreboardNumber, fileFormat.lower()
            )
            if result:
                return FileResponse(result, media_type=f"image/{fileFormat.lower()}")
            else:
                return HTMLResponse(
                    "An error has occured, please check TSH logs for more information"
                )
        else:
            return HTMLResponse(f"File format {fileFormat} not recognized")

    # Get the sets to be played
    @api.get("/get-sets")
    async def get_sets(request: Request):
        return await call(WebServer.actions.get_sets, request.query_params)

    @on("get_sets")
    def ws_get_sets(message=None):
        WebServer.ws_emit("get_sets", WebServer.actions.get_sets(load_message(message)))

    # Loads info on a match
    @api.get("/get-match-{setId}")
    async def get_match(setId: str):
        return await call(WebServer.actions.get_match, setId)

    @on("get_match")
    def ws_get_match(message=None):
        info = load_message(message)
        WebServer.ws_emit("get_match", WebServer.actions.get_match(info.get("setId")))

    # Get the commentators
    @api.get("/get-comms")
    async def get_comms():
        return await call(WebServer.actions.get_comms)

    @on("get_comms")
    def ws_get_comms(message=None):
        WebServer.ws_emit("get_comms", WebServer.actions.get_comms())

    # Loads a set remotely by providing a set ID to pull from the data provider
    @api.get("/scoreboard{scoreboardNumber:seg}-load-set")
    async def load_set(scoreboardNumber: str, request: Request):
        args = request.query_params
        if args.get("no-mains") is not None:
            return await call(
                WebServer.actions.load_set, scoreboardNumber, args.get("set"), no_mains=True
            )
        else:
            return await call(WebServer.actions.load_set, scoreboardNumber, args.get("set"))

    @on("load_set")
    def ws_load_set(message=None):
        info = load_message(message)
        if info.get("no-mains") is not None:
            WebServer.ws_emit(
                "load_set",
                WebServer.actions.load_set(
                    info.get("scoreboardNumber", "1"), info.get("set"), no_mains=True
                ),
            )
        else:
            WebServer.ws_emit(
                "load_set",
                WebServer.actions.load_set(info.get("scoreboardNumber", "1"), info.get("set")),
            )

    # Loads a set remotely by providing a set ID to pull from the data provider
    @api.get("/scoreboard{scoreboardNumber:seg}-get-set")
    async def get_set(scoreboardNumber: str):
        return await call(WebServer.actions.get_set, scoreboardNumber)

    @on("get_set")
    def ws_get_set(message=None):
        WebServer.ws_emit(
            "get_set",
            WebServer.actions.get_set(load_message(message).get("scoreboardNumber", "1")),
        )

    @api.get("/playerdb")
    async def playerdb():
        return await call(WebServer.actions.get_playerdb)

    @on("playerdb")
    def ws_playerdb(message=None):
        logger.info("Emitting playerdb info.")
        WebServer.ws_emit("playerdb", WebServer.actions.get_playerdb())

    # Update bracket
    @api.get("/update-bracket")
    async def update_bracket():
        return await call(WebServer.actions.update_bracket)

    @on("update_bracket")
    def ws_update_bracket(message=None):
        WebServer.ws_emit("update_bracket", WebServer.actions.update_bracket())

    # Update only the set results of the loaded bracket, keeping its players
    @api.get("/update-bracket-sets")
    async def update_bracket_sets():
        return await call(WebServer.actions.update_bracket_sets)

    @on("update_bracket_sets")
    def ws_update_bracket_sets(message=None):
        WebServer.ws_emit("update_bracket_sets", WebServer.actions.update_bracket_sets())

    # The stream queues, as sent to the layouts
    @api.get("/stream-queue")
    async def stream_queue():
        return await call(WebServer.actions.stream_queue)

    @api.get("/stream-queue/refresh")
    async def stream_queue_refresh():
        return await call(WebServer.actions.stream_queue_refresh)

    # Loads a stream's next set into its scoreboard:
    # /stream-queue/load-next?stream=<name> or ?scoreboard=<number>
    @api.get("/stream-queue/load-next")
    async def stream_queue_load_next(request: Request):
        return await call(
            WebServer.actions.stream_queue_load_next,
            request.query_params.get("stream"),
            request.query_params.get("scoreboard"),
        )

    # What the bracket focus layout zooms to (see docs/layout-data.md):
    # GET answers what's in focus and what can be picked, POST a focus
    # request, e.g. {"mode": "sets", "sets": ["m1"]}, or {"move": 1} for the
    # next round. For a focus channel with ?channel=<name> ("main" without)
    @api.get("/bracket-focus")
    async def bracket_focus(request: Request):
        return await call(WebServer.actions.bracket_focus, request.query_params.get("channel"))

    @api.post("/bracket-focus")
    async def bracket_focus_set(request: Request):
        return await call(
            WebServer.actions.bracket_focus_set,
            await WebServer.request_body(request),
            request.query_params.get("channel"),
        )

    # {"channel": <name>}
    @on("bracket_focus")
    def ws_bracket_focus(message=None):
        WebServer.ws_emit(
            "bracket_focus",
            WebServer.actions.bracket_focus(parse_message(message).get("channel")),
        )

    @on("bracket_focus_set")
    def ws_bracket_focus_set(message=None):
        WebServer.ws_emit(
            "bracket_focus", WebServer.actions.bracket_focus_set(parse_message(message))
        )

    # The same as links, e.g. for a Stream Deck: /bracket-focus/all,
    # /bracket-focus/next-round, /bracket-focus/previous-round,
    # /bracket-focus/follow?scoreboard=<n>, /bracket-focus/tour?interval=<s>
    # and /bracket-focus/player?id=<player slot>, each with &channel=<name>
    @api.get("/bracket-focus/{action}")
    async def bracket_focus_action(action: str, request: Request):
        args = dict(request.query_params)
        body = {
            "all": {"mode": "all"},
            "next-round": {"move": 1},
            "previous-round": {"move": -1},
            "follow": {"mode": "follow", "scoreboard": args.get("scoreboard", 1)},
            "tour": {"mode": "tour", "interval": args.get("interval")},
            "player": {"mode": "player", "player": args.get("id")},
        }.get(action)
        if body is None:
            return HTMLResponse("Unknown action", status_code=404)
        return await call(WebServer.actions.bracket_focus_set, body, args.get("channel"))

    # Load player from tag
    @api.get("/scoreboard{scoreboardNumber:seg}-load-player-from-tag-{team:seg}-{player:seg}")
    async def load_player_from_tag(scoreboardNumber: str, team: str, player: str, request: Request):
        args = request.query_params
        if args.get("tag") is None:
            return HTMLResponse("No tag provided")
        no_mains = args.get("no-mains") is not None
        return await call(
            WebServer.actions.load_player_from_tag,
            scoreboardNumber,
            html.unescape(args.get("tag")),
            team,
            player,
            no_mains,
        )

    @on("load_player_from_tag")
    def ws_load_player_from_tag(message=None):
        args = load_message(message)
        if args.get("tag") is None:
            WebServer.ws_emit("load_player_from_tag", "No tag provided")
            return
        no_mains = args.get("no-mains") is not None
        team = args.get("team")
        player = args.get("player")
        scoreboardNumber = args.get("scoreboardNumber", "1")
        WebServer.ws_emit(
            "load_player_from_tag",
            WebServer.actions.load_player_from_tag(
                scoreboardNumber, html.unescape(args.get("tag")), team, player, no_mains
            ),
        )

    @api.get("/load-commentator-from-tag-{caster}")
    async def load_commentator_from_tag(caster: str, request: Request):
        args = request.query_params
        if args.get("tag") is None:
            return HTMLResponse("No tag provided")
        no_mains = args.get("no-mains") is not None
        return await call(
            WebServer.actions.load_commentator_from_tag,
            caster,
            html.unescape(args.get("tag")),
            no_mains,
        )

    @on("load_commentator_from_tag")
    def ws_load_commentator_from_tag(message=None):
        args = load_message(message)
        if args.get("tag") is None:
            WebServer.ws_emit("load_commentator_from_tag", "No tag provided")
            return
        no_mains = args.get("no-mains") is not None
        caster = args.get("commentator")
        WebServer.ws_emit(
            "load_commentator_from_tag",
            WebServer.actions.load_commentator_from_tag(
                caster, html.unescape(args.get("tag")), no_mains
            ),
        )

    # Update bracket
    @api.get("/set-tournament")
    async def set_tournament(request: Request):
        return await call(WebServer.actions.load_tournament, request.query_params.get("url"))

    @on("set_tournament")
    def ws_set_tournament(message=None):
        info = load_message(message)
        WebServer.ws_emit("set_tournament", WebServer.actions.load_tournament(info.get("url")))

    # List a tournament's events, to pick one for set-tournament
    @api.get("/tournament-events")
    async def tournament_events(request: Request):
        return await call(WebServer.actions.get_tournament_events, request.query_params.get("url"))

    @on("get_tournament_events")
    def ws_get_tournament_events(message=None):
        info = load_message(message)
        WebServer.ws_emit(
            "get_tournament_events", WebServer.actions.get_tournament_events(info.get("url"))
        )

    @api.get("/states")
    async def get_states(request: Request):
        countryCode = request.query_params.get("countryCode", None)
        if not countryCode:
            return HTMLResponse("countryCode not specified", status_code=400)

        return await call(WebServer.actions.get_states, countryCode)

    # Answered through the event's acknowledgement callback
    @on("states")
    def ws_get_states(message=None):
        args = load_message(message)
        return WebServer.actions.get_states(args.get("countryCode", ""))

    # Set the current ingame stage (selectedStage in stage_strike state)
    @api.post("/scoreboard{scoreboardNumber:seg}-set-current-stage")
    async def set_current_stage(scoreboardNumber: str, request: Request):
        data = await WebServer.request_body(request)
        return await call(
            WebServer.actions.set_current_stage, scoreboardNumber, data.get("codename")
        )

    @on("set_current_stage")
    def ws_set_current_stage(message=None):
        data = load_message(message)
        WebServer.ws_emit(
            "set_current_stage",
            WebServer.actions.set_current_stage(
                data.get("scoreboardNumber", "1"), data.get("codename")
            ),
        )

    @api.get("/")
    @api.get("/scoreboard")
    @api.get("/stage-strike-app")
    @api.get("/character-select")
    @api.get("/bracket-focus-app")
    async def stage_strike_app():
        return FileResponse(
            os.path.join(os.path.abspath("."), "stage_strike_app/build/index.html"),
            headers={"Cache-Control": "no-cache"},
        )

    # Registered last by __init__, as it matches every path
    async def file_request(filename: str):
        filename = filename or "stage_strike_app/build/index.html"
        # The settings hold API keys and passwords (e.g. the start.gg
        # token used to report sets), so they're never served
        normalized = os.path.normcase(os.path.normpath(filename)).replace("\\", "/").lstrip("./")
        if os.path.basename(normalized).startswith("settings.json") and normalized.startswith(
            "user_data/"
        ):
            return HTMLResponse("Not allowed", status_code=403)

        root = os.path.abspath(".")
        path = os.path.abspath(os.path.join(root, filename))
        try:
            inside = os.path.commonpath([root, path]) == root
        except ValueError:  # another drive on Windows
            inside = False
        if not inside or not os.path.isfile(path):
            logger.error(f"File not found: {filename}")
            return HTMLResponse("File not found", status_code=404)

        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if filename.endswith(".js"):
            mimetype = "text/javascript"
        if filename.lower().endswith(".png"):
            mimetype = "image/apng"
        if filename.lower().endswith(".svg"):
            mimetype = "image/svg+xml"

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ("html", "js", "css", "json"):
            cache = "no-cache, max-age=0"
        else:
            cache = "public, max-age=86400"

        return FileResponse(
            path,
            media_type=mimetype,
            headers={"Cache-Control": cache},
            filename=os.path.basename(path) if filename.endswith(".gz") else None,
        )

    def run(self):
        try:
            logger.info(f"Starting TSH Web Server at {self.GetIP()}:{self.port}")
            config = uvicorn.Config(
                WebServer.app,
                host=self.host_name,
                port=self.port,
                # Logged by the middleware above, through loguru
                access_log=False,
                log_config=None,
                log_level="warning",
                # Nothing to set up at startup
                lifespan="off",
            )
            self.server = uvicorn.Server(config)
            asyncio.run(self.Serve())
        except Exception:
            logger.error(traceback.format_exc())
        finally:
            WebServer.loop = None

    async def Serve(self):
        WebServer.loop = asyncio.get_running_loop()
        await self.server.serve()

    def Stop(self, timeout=5000):
        """Stops the server, waiting up to timeout ms for it to finish."""
        if self.server is not None:
            self.server.should_exit = True
        if not self.wait(timeout):
            logger.warning("The web server didn't stop in time, terminating it")
            self.terminate()
            self.wait(timeout)

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
