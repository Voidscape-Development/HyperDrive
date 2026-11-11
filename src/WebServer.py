import asyncio
import json
import logging
import mimetypes
import os
import re
import socket
import threading
import traceback

import orjson
import socketio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from sqladmin import Admin, ModelView
from starlette.concurrency import run_in_threadpool
from starlette.convertors import Convertor, register_url_convertor

from . import WebDashboard
from .CommentaryWidget import CommentaryWidget
from .LayoutList import ListLayouts
from .PlayerDB import PlayerDB
from .PlayerDBModels import GetEngine, Player
from .ScoreboardManager import ScoreboardManager
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .WebActionRegistry import (
    ACTIONS,
    ACTIONS_BY_NAME,
    Action,
    Route,
    Source,
    parse_message,
    run_action,
    socket_source,
)
from .WebServerActions import ActionError, WebServerActions
from .Wiki import HOME_PAGE, WebPage, WebSearchPage

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

# The socket.io client whose event a handler made with on() is handling in
# this thread
_client = threading.local()

# Clients that asked for part of the program state, when connecting with
# auth {"state_keys": [top-level keys]}: sid -> those keys. They're in a room
# per set of keys, so each filtered message is encoded once. The rest get the
# whole state.
_subscriptions: dict[str, frozenset] = {}


def state_keys(auth):
    """The top-level keys a client subscribes to, or None for all."""
    keys = auth.get("state_keys") if isinstance(auth, dict) else None
    if not isinstance(keys, list) or not keys or len(keys) > 64:
        return None
    return frozenset(str(k) for k in keys)


def keys_room(keys):
    return "state:" + ",".join(sorted(keys))


def encode_program_state():
    """The program_state message as JSON. The state is read and encoded under
    StateManager's lock, so it can't change meanwhile (the GUI thread changes
    it in place) and the delta index is the one of that state."""
    with StateManager.lock:
        return SocketioJson.dumps(
            {"state": StateManager.state, "delta_index": StateManager.deltaIndex}
        ).encode()


def program_state_message():
    """The program_state message, as a copy of the state that's safe to
    filter and send from another thread."""
    return orjson.loads(encode_program_state())


def filter_state(message, keys):
    """A program_state message with only the keys."""
    state = message["state"]
    return {**message, "state": {k: state[k] for k in keys if k in state}}


def filter_update(message, keys):
    """A program_state_update message with the deltas under the keys. It's
    sent even when none are, so delta numbers stay one by one."""
    delta = [d for d in message["delta"] if str(d["path"][0]) in keys]
    return {**message, "delta": delta}


def on(event):
    """Registers a socket event handler written by hand (the actions' are
    made from WebActionRegistry, see below). Handlers run in a worker thread,
    where ws_emit answers the client that sent the event."""

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


# A parameter that isn't valid (400), a scoreboard that doesn't exist (404),
# or the GUI thread not getting to the action in time (503)
@api.exception_handler(ActionError)
async def handle_action_error(request: Request, e: ActionError):
    return HTMLResponse(str(e), status_code=e.status)


class PlayerAdmin(ModelView, model=Player):
    name = "Player"
    name_plural = "Players"
    icon = "fa-solid fa-user"
    column_list = [
        Player.tag,
        Player.name,
        Player.twitter,
        Player.socials,
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
        await run_in_threadpool(PlayerDB.ReloadDB)

    async def after_model_delete(self, model, request):
        await run_in_threadpool(PlayerDB.ReloadDB)


# =====================================================
# SOCKET MESSAGES AND PROGRAM STATE
# =====================================================
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
    return Response(await run_in_threadpool(encode_program_state), media_type="application/json")


# The layout pages and their previews, e.g. for the OBS plugin's layout
# source (see src/LayoutList.py)
@api.get("/layouts")
async def layouts():
    return await run_in_threadpool(ListLayouts)


def ws_emit_state(event, message, filter, broadcast=False):
    """Sends a state message: whole to the clients that subscribed to
    nothing, and filter(message, keys) to each set of keys subscribed to.
    In a socket event handler it answers that client alone, unless
    broadcast is set."""
    loop = WebServer.loop
    if loop is None or loop.is_closed():
        return None
    sid = None if broadcast else getattr(_client, "sid", None)

    async def send():
        if sid is not None:
            keys = _subscriptions.get(sid)
            await sio.emit(event, message if keys is None else filter(message, keys), to=sid)
            return
        await sio.emit(event, message, skip_sid=list(_subscriptions))
        for keys in set(_subscriptions.values()):
            await sio.emit(event, filter(message, keys), room=keys_room(keys))

    return asyncio.run_coroutine_threadsafe(send(), loop)


@on("program-state-update")
def ws_program_state_update(message=None):
    # Manual trigger to push full state to all clients
    ws_program_state()


def on_program_state_update(changes):
    """StateManager's state_updated, called by the thread that saved (see
    the connection in WebServer.__init__): always for every client, also
    when that thread is answering one client's socket event."""
    if len(changes) > 0:
        future = ws_emit_state("program_state_update", changes, filter_update, broadcast=True)
        if future is not None:
            future.add_done_callback(_check_state_update_sent)


def _check_state_update_sent(future):
    if isinstance(future.exception(), (TypeError, ValueError)):
        logger.warning("Unserializable program state update")

        # If we can't emit a diff, fall back to emitting the whole program
        # state. Well-behaved listeners should discard their existing state
        # and re-sync with us that way.
        ws_program_state()


@sio.on("connect")
async def ws_connect(sid, environ, auth=None):
    # Subscribed first, so updates meanwhile are filtered too
    keys = state_keys(auth)
    if keys is not None:
        _subscriptions[sid] = keys
        await sio.enter_room(sid, keys_room(keys))
    message = await run_in_threadpool(program_state_message)
    await sio.emit(
        "program_state", message if keys is None else filter_state(message, keys), to=sid
    )


@sio.on("disconnect")
async def ws_disconnect(sid, *args):
    _subscriptions.pop(sid, None)


# Also connected to signals of the program, to send the state to every client
@on("program_state")
def ws_program_state(message=None):
    ws_emit_state("program_state", program_state_message(), filter_state)


def on_program_state_big_change():
    """StateManager's state_big_change: the whole state, for every client"""
    ws_emit_state("program_state", program_state_message(), filter_state, broadcast=True)


# =====================================================
# ACTIONS
# =====================================================
# Every action in WebActionRegistry gets its HTTP routes and its socket.io
# event from here. Both read the action's parameters into a Source and hand
# it to run_action, in a worker thread.
def action_endpoint(action: Action):
    async def endpoint(request: Request):
        body = parse_message(await request.body()) if request.method == "POST" else {}
        source = Source(request.path_params, request.query_params, body)
        return respond(await run_in_threadpool(run_action, WebServer.actions, action, source))

    return endpoint


def action_docs(action: Action, route: Route, method):
    """The route's parameters for /api/docs, which can't tell them from the
    endpoint's signature."""
    inPath = re.findall(r"{(\w+)", route.path)
    parameters = [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in inPath
    ]
    fields = {}
    wholeBody = False
    for param in action.params:
        if param.path in inPath:
            continue
        wholeBody = wholeBody or param.whole
        if param.query:
            parameters.append({"name": param.query[0], "in": "query", "schema": {"type": "string"}})
        if param.body:
            fields[param.body[0]] = {}
    docs = {"parameters": parameters}
    if method == "POST" and (fields or wholeBody):
        schema = {"type": "object", "properties": fields}
        docs["requestBody"] = {"content": {"application/json": {"schema": schema}}}
    return docs


def action_handler(action: Action):
    """The socket.io handler of an action: it's answered with the action's
    reply events, and through the event's acknowledgement if the client asked
    for one. When the action can't be done as asked (e.g. there's no such
    scoreboard), the answer is {"error": <why>, "status": <HTTP status>}."""

    async def handler(sid, message=None, *args):
        source = socket_source(message)
        try:
            result = await run_in_threadpool(run_action, WebServer.actions, action, source)
        except ActionError as e:
            logger.warning(f"[Socket] {action.socket}: {e}")
            result = {"error": str(e), "status": e.status}
        except Exception:
            logger.error(traceback.format_exc())
            return None
        for event in action.replies:
            await sio.emit(event, result, to=sid)
        return result

    return handler


for _action in ACTIONS:
    for _route in _action.http:
        for _method in _route.methods:
            api.add_api_route(
                _route.path,
                action_endpoint(_action),
                methods=[_method],
                name=_action.name,
                description=_action.doc or None,
                openapi_extra=action_docs(_action, _route, _method),
            )
    if _action.socket:
        sio.on(_action.socket, action_handler(_action))


def broadcast_action(name, message=None):
    """Runs an action and sends its answer to every client, for the program
    to tell them about a change (e.g. the characters, once the game changed)."""
    action = ACTIONS_BY_NAME[name]
    try:
        result = run_action(WebServer.actions, action, socket_source(message))
    except Exception:
        logger.error(traceback.format_exc())
        return
    for event in action.replies:
        ws_emit(event, result)


# Connected to signals of the program (see HyperDrive.py), so they take and
# ignore whatever the signal sends
def ws_get_characters(message=None):
    broadcast_action("get_characters")


def ws_playerdb(message=None):
    broadcast_action("get_playerdb")


# {"scoreboardNumber": <n>}: the stage strike page's data of that scoreboard
def ws_ruleset(message=None):
    broadcast_action("ruleset", message)


# =====================================================
# ACTIONS WITH THEIR OWN REQUEST FORMAT
# =====================================================
# These don't name the action's parameters like the registry does, so
# they're written by hand: they make the action's Source and run it like
# the ones above.
#
# Display Controls over socket.io: {"folder": <name>} or {"group": <name>}
# or {"all": true}, with "action": show, hide or toggle (without it, answers
# whether it's shown)
@on("display")
def ws_display(message=None):
    info = parse_message(message)
    kind = next((k for k in ("folder", "group", "all") if k in info), None)
    source = Source({"kind": kind, "name": info.get(kind), "action": info.get("action")}, {}, {})
    try:
        result = run_action(WebServer.actions, ACTIONS_BY_NAME["display"], source)
    except ActionError as e:
        result = {"error": str(e)}
    if isinstance(result, tuple):
        result = {"error": result[0]}
    ws_emit("display", result)


def ws_broadcast_display_state():
    """Sends display_state to every client when something is shown or hidden."""
    loop = WebServer.loop
    if loop is None or loop.is_closed():
        return
    from .DisplayControls import DisplayControls

    if DisplayControls.instance is None:
        return
    controls = DisplayControls.instance
    state = {"kind": "all", "shown": controls.AllShown(), **controls.State()}
    asyncio.run_coroutine_threadsafe(sio.emit("display_state", state), loop)


# Bracket focus requests as links, e.g. for a Stream Deck: /bracket-focus/all,
# /bracket-focus/next-round, /bracket-focus/previous-round,
# /bracket-focus/winners, /bracket-focus/losers (a side),
# /bracket-focus/follow?scoreboard=<n>, /bracket-focus/tour?interval=<s>
# /bracket-focus/player?id=<player slot> and /bracket-focus/phase?phase=<id>
# (a phase of the bracket widget the channel shows), each with
# &channel=<name>
@api.get("/bracket-focus/{action}")
async def bracket_focus_action(action: str, request: Request):
    args = request.query_params
    body = {
        "all": {"mode": "all"},
        "next-round": {"move": 1},
        "previous-round": {"move": -1},
        "winners": {"mode": "side", "side": "winners"},
        "losers": {"mode": "side", "side": "losers"},
        "follow": {"mode": "follow", "scoreboard": args.get("scoreboard", 1)},
        "tour": {"mode": "tour", "interval": args.get("interval")},
        "player": {"mode": "player", "player": args.get("id")},
        "phase": {"phase": args.get("phase", "")},
    }.get(action)
    if body is None:
        return HTMLResponse("Unknown action", status_code=404)
    source = Source({}, args, body)
    return respond(
        await run_in_threadpool(
            run_action, WebServer.actions, ACTIONS_BY_NAME["bracket_focus_set"], source
        )
    )


# =====================================================
# PAGES AND FILES
# =====================================================
@api.get("/")
@api.get("/scoreboard")
@api.get("/stage-strike-app")
@api.get("/character-select")
@api.get("/bracket-focus-app")
@api.get("/commentary-dashboard")
async def stage_strike_app():
    return FileResponse(
        os.path.join(os.path.abspath("."), "stage_strike_app/build/index.html"),
        headers={"Cache-Control": "no-cache"},
    )


# Browsers ask for it on pages without an icon of their own, and would
# keep showing TournamentStreamHelper's from the same address otherwise
@api.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(
        os.path.join(os.path.abspath("."), "assets/icons/icon.ico"),
        media_type="image/x-icon",
        headers={"Cache-Control": "no-cache"},
    )


# The in-app guide (docs/wiki), for a phone or a second screen
@api.get("/wiki", response_class=HTMLResponse)
async def wiki_home():
    content = WebPage(HOME_PAGE)
    if content is None:
        return HTMLResponse("The guide wasn't found", status_code=404)
    return HTMLResponse(content)


@api.get("/wiki/search", response_class=HTMLResponse)
async def wiki_search(q: str = ""):
    return HTMLResponse(WebSearchPage(q))


@api.get("/wiki/{page}", response_class=HTMLResponse)
async def wiki_page(page: str):
    content = WebPage(page)
    if content is None:
        return HTMLResponse(WebSearchPage(page.replace("-", " ")), status_code=404)
    return HTMLResponse(content)


# Registered last by WebServer.__init__, as it matches every path
async def file_request(filename: str):
    filename = filename or "stage_strike_app/build/index.html"
    # The settings hold API keys and passwords (e.g. the start.gg
    # token used to report sets), and web reporting's file the addresses
    # of the devices that reported, so they're never served
    normalized = os.path.normcase(os.path.normpath(filename)).replace("\\", "/").lstrip("./")
    if os.path.basename(normalized).startswith(
        ("settings.json", "web_reporting.json")
    ) and normalized.startswith("user_data/"):
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


class WebServer(QThread):
    api = api
    sio = sio
    app = socketio.ASGIApp(sio, other_asgi_app=api)
    actions: WebServerActions | None = None
    # The server's event loop, set while it runs
    loop: asyncio.AbstractEventLoop | None = None
    routesAdded = False

    # For the program to send to every client (see HyperDrive.py)
    ws_program_state = staticmethod(ws_program_state)
    ws_get_characters = staticmethod(ws_get_characters)
    ws_playerdb = staticmethod(ws_playerdb)
    ws_ruleset = staticmethod(ws_ruleset)
    ws_broadcast_display_state = staticmethod(ws_broadcast_display_state)

    def __init__(
        self, parent=None, stageWidget=None, commentaryWidget: CommentaryWidget = None
    ) -> None:
        super().__init__(parent)
        WebServer.actions = WebServerActions(
            parent=parent,
            scoreboard=ScoreboardManager.instance,
            stageWidget=stageWidget,
            commentaryWidget=commentaryWidget,
        )

        # Direct: sent by the thread that saves, as it saves, so the clients
        # get the updates in the order of their delta_index. Queued, a save
        # made by a worker thread would be sent after the GUI thread's later
        # ones, and every client would fetch the whole state again.
        direct = Qt.ConnectionType.DirectConnection
        StateManager.signals.state_updated.connect(on_program_state_update, direct)
        StateManager.signals.state_big_change.connect(on_program_state_big_change, direct)

        self.host_name = "0.0.0.0"
        self.port = SettingsManager.Get("general.webserver_port", 5500)
        self.server: uvicorn.Server | None = None

        if not WebServer.routesAdded:
            WebServer.routesAdded = True
            # Before the file route below, which matches every path
            Admin(
                api,
                engine=GetEngine(),
                title="HyperDrive Player DB",
                logo_url="/assets/icons/icon.png",
                logo_width=32,
                logo_height=32,
                favicon_url="/favicon.ico",
            ).add_view(PlayerAdmin)
            # The admin mount only matches /admin/..., and the file route
            # would take /admin before Starlette's slash redirect
            api.add_api_route(
                "/admin", lambda: RedirectResponse("/admin/"), include_in_schema=False
            )
            # The web dashboard's API and pages
            WebDashboard.Setup(api, parent)
            api.add_api_route("/{filename:path}", file_request, methods=["GET", "POST"])

    # =====================================================
    # RUNNING THE SERVER
    # =====================================================
    def run(self):
        try:
            logger.info(f"Starting HyperDrive Web Server at {self.GetIP()}:{self.port}")
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
