# The web dashboard's API, under /dashboard-api: what the browser needs to
# run the event that isn't already in the program state, and the changes it
# makes. Changes go through the desktop app's own widgets, so the window,
# its saved settings and the layouts all follow.
#
# The dashboard can be locked with a PIN (Settings > General). The browser
# trades the PIN for a token, sent with every request in the
# X-Dashboard-Token header. Without a PIN set, every request is let in.
import base64
import hashlib
import hmac
import os
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from starlette.concurrency import run_in_threadpool

from .Helpers.AltTextHelper import (
    default_templates,
    generate_alt_text,
    load_options,
    load_program_state,
    save_options,
)
from .Helpers.QtHelper import gui_thread_sync
from .ScoreboardManager import ScoreboardManager
from .SettingsManager import SettingsManager

PIN_SETTING = "general.dashboard_pin"
TOKEN_HEADER = "X-Dashboard-Token"

# Wrong PINs from one address before it has to wait, and how long
MAX_PIN_ATTEMPTS = 5
PIN_LOCKOUT_SECS = 30

# Values of the stream queue's "after a set" option
AFTER_SET_MODES = ("nothing", "ask", "load_next")


def Pin():
    return str(SettingsManager.Get(PIN_SETTING, "") or "").strip()


def TokenFor(pin):
    """The token a browser keeps once it has the PIN. It changes with the
    PIN, so changing the PIN locks every browser out."""
    digest = hmac.new(pin.encode(), b"hyperdrive-dashboard", hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def TokenValid(token):
    pin = Pin()
    if not pin:
        return True
    return bool(token) and hmac.compare_digest(str(token), TokenFor(pin))


class PinAttempts:
    """Wrong PINs per address, so a PIN can't be guessed quickly."""

    def __init__(self):
        self.lock = threading.Lock()
        self.failures = {}

    def LockedFor(self, address):
        with self.lock:
            count, last = self.failures.get(address, (0, 0))
            if count < MAX_PIN_ATTEMPTS:
                return 0
            return max(0, PIN_LOCKOUT_SECS - (time.time() - last))

    def Failed(self, address):
        with self.lock:
            count, last = self.failures.get(address, (0, 0))
            if time.time() - last > PIN_LOCKOUT_SECS:
                count = 0
            self.failures[address] = (count + 1, time.time())

    def Succeeded(self, address):
        with self.lock:
            self.failures.pop(address, None)


attempts = PinAttempts()


def RequirePin(request: Request):
    if not TokenValid(request.headers.get(TOKEN_HEADER)):
        raise HTTPException(status_code=401, detail="PIN_REQUIRED")


def respond(result):
    # The web server's own response rules: text, JSON or (body, status)
    from .WebServer import respond as serverRespond

    return serverRespond(result)


async def call(fn, *args, **kwargs):
    return respond(await run_in_threadpool(fn, *args, **kwargs))


async def body(request: Request):
    from .WebServer import parse_message

    return parse_message(await request.body())


def Number(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# =====================================================
# ACTIONS
# =====================================================
class DashboardActions:
    """The changes the dashboard makes, run on the GUI thread."""

    window = None

    # Widgets
    def _Widget(self, cls):
        if self.window is None:
            return None
        found = self.window.findChildren(cls)
        return found[0] if found else None

    # Theme
    @gui_thread_sync
    def theme(self):
        from .Theme import Theme

        colors = Theme.Colors()
        return {
            "dark": Theme.IsDark(),
            "radius": Theme.Radius(),
            "colors": {key: color.name() for key, color in colors.items()},
        }

    # Status
    @gui_thread_sync
    def status(self):
        """What the sidebar and the pages show besides the program state."""
        from .Scheduler import Scheduler
        from .TournamentDataManager import TournamentDataManager

        provider = TournamentDataManager.instance.provider
        scheduler = Scheduler.instance
        window = self.window

        def job(name):
            if name not in scheduler.jobs:
                return {"enabled": False, "running": False, "remainingMs": None}
            return {
                "enabled": scheduler.IsEnabled(name),
                "running": scheduler.IsRunning(name),
                "remainingMs": scheduler.RemainingMs(name),
            }

        return {
            "tournament": {
                "loaded": provider is not None,
                "url": getattr(provider, "url", None) if provider else None,
                "host": getattr(provider, "HOST", None) if provider else None,
                "provider": getattr(provider, "NAME", None) if provider else None,
            },
            "completedSets": {
                **job("completed_sets"),
                "supported": provider is not None and provider.SUPPORTS_COMPLETED_SETS,
                "autoPull": bool(
                    window is not None and window.autoPullCompletedSetsAction.isChecked()
                ),
            },
            "scoreboards": [
                {"number": n, "name": ScoreboardManager.instance.GetTabName(n)}
                for n in ScoreboardManager.instance.GetScoreboardNumbers()
            ],
            "pinSet": bool(Pin()),
        }

    # Tournament
    def tournament_events(self, url=None):
        """The events of a tournament, from its link or one of its events'
        (the loaded event's without a link), to pick one to load. Not on the
        GUI thread: it asks start.gg or parry.gg."""
        from .TournamentDataManager import TournamentDataManager
        from .TournamentDataProvider.TournamentEventLookup import (
            FetchTournamentEvents,
            ParseTournamentLink,
            TournamentLookupError,
        )

        if not url:
            provider = TournamentDataManager.instance.provider
            url = getattr(provider, "url", None) or SettingsManager.Get("TOURNAMENT_URL")
        parsed = ParseTournamentLink(url) if url else None
        if parsed is None:
            return {"error": "invalid_url", "message": "Not a tournament or event link"}
        try:
            result = FetchTournamentEvents(parsed, SettingsManager.Get("api_keys.parrygg"))
        except TournamentLookupError as e:
            return {"error": e.code, "message": str(e)}
        return {**result, "selectedEventUrl": parsed.get("eventUrl")}

    @gui_thread_sync
    def unload_tournament(self):
        from .TournamentDataManager import TournamentDataManager

        TournamentDataManager.instance.SetTournament(None)
        return "OK"

    @gui_thread_sync
    def repull_entrants(self):
        from .TournamentDataManager import TournamentDataManager

        if TournamentDataManager.instance.provider is None:
            return "NO_TOURNAMENT", 409
        TournamentDataManager.instance.RepullEntrants()
        return "OK"

    # Completed sets
    @gui_thread_sync
    def completed_sets_auto(self, enabled):
        # Through the window's menu, so it shows the change too
        self.window.autoPullCompletedSetsAction.setChecked(bool(enabled))
        return "OK"

    @gui_thread_sync
    def completed_sets_pull(self):
        from .Scheduler import Scheduler

        if not self.window._CompletedSetsSupported():
            return "NO_TOURNAMENT", 409
        Scheduler.instance.TriggerNow("completed_sets")
        return "OK"

    # Scoreboards
    @gui_thread_sync
    def scoreboard_amount(self, offset):
        window = self.window
        window.SetScoreboardAmount(ScoreboardManager.instance.GetTabAmount() + offset)
        return {"amount": ScoreboardManager.instance.GetTabAmount()}

    @gui_thread_sync
    def scoreboard_name(self, number, name):
        number = Number(number)
        if number is None or not 1 <= number <= ScoreboardManager.instance.GetTabAmount():
            return "NO_SCOREBOARD", 404
        ScoreboardManager.instance.SetTabName(number, str(name or "").strip())
        return "OK"

    @gui_thread_sync
    def scoreboard_stop_tracking(self, number):
        scoreboard = ScoreboardManager.instance.GetScoreboard(Number(number, 1))
        if scoreboard is None:
            return "NO_SCOREBOARD", 404
        scoreboard.StopAutoUpdate()
        return "OK"

    # Display controls
    @gui_thread_sync
    def display_add_group(self, name):
        from .DisplayControls import DisplayControls

        DisplayControls.instance.AddGroups([name])
        return "OK"

    @gui_thread_sync
    def display_remove_group(self, name):
        from .DisplayControls import DisplayControls

        DisplayControls.instance.RemoveGroup(name)
        return "OK"

    @gui_thread_sync
    def display_refresh_folders(self):
        from .DisplayControls import DisplayControls

        DisplayControls.instance.RefreshFolders()
        return "OK"

    # Stream queue
    def _Queue(self):
        from .StreamQueueWidget import StreamQueueWidget

        return StreamQueueWidget.instance

    @gui_thread_sync
    def stream_queue_options(self):
        widget = self._Queue()
        if widget is None:
            return "NO_STREAM_QUEUE", 404
        return {
            "afterSet": widget.model.afterSet,
            "autoAdd": widget.model.autoAddStreams,
            "autoRefresh": widget.autoRefresh.isChecked(),
            "interval": widget.interval.value(),
            "lastUpdated": widget.model.lastUpdated,
        }

    @gui_thread_sync
    def stream_queue_set_options(self, data):
        widget = self._Queue()
        if widget is None:
            return "NO_STREAM_QUEUE", 404
        # Through the widget's own controls, which save and apply them
        if data.get("afterSet") in AFTER_SET_MODES:
            index = widget.afterSet.findData(data["afterSet"])
            if index >= 0:
                widget.afterSet.setCurrentIndex(index)
        if "autoAdd" in data:
            widget.autoAddAction.setChecked(bool(data["autoAdd"]))
        if "autoRefresh" in data:
            widget.autoRefresh.setChecked(bool(data["autoRefresh"]))
        if Number(data.get("interval")) is not None:
            widget.interval.setValue(Number(data["interval"]))
        return "OK"

    @gui_thread_sync
    def stream_queue_add_stream(self, name):
        widget = self._Queue()
        name = str(name or "").strip()
        if widget is None or not name:
            return "NO_NAME", 400
        widget.model.AddStream(name)
        widget.Changed()
        return "OK"

    @gui_thread_sync
    def stream_queue_remove_stream(self, name):
        widget = self._Queue()
        if widget is None or widget.model.GetStream(name) is None:
            return "NO_STREAM", 404
        widget.model.RemoveStream(name)
        widget.Changed()
        return "OK"

    @gui_thread_sync
    def stream_queue_set_scoreboard(self, name, number):
        widget = self._Queue()
        config = widget.model.GetStream(name) if widget else None
        if config is None:
            return "NO_STREAM", 404
        number = Number(number)
        # A scoreboard shows one stream
        for other in widget.model.streams:
            if other is not config and number is not None and str(other.scoreboard) == str(number):
                other.scoreboard = None
        config.scoreboard = number
        widget.Changed()
        return "OK"

    @gui_thread_sync
    def stream_queue_edit(self, name, action, data):
        """Changes one stream's queue: move, move_to, remove, reset,
        add_set, add_custom or load."""
        widget = self._Queue()
        config = widget.model.GetStream(name) if widget else None
        if config is None:
            return "NO_STREAM", 404
        model = widget.model
        key = data.get("key")
        if action == "move":
            model.Move(name, key, 1 if Number(data.get("offset"), 1) >= 0 else -1)
        elif action == "move_to":
            model.MoveTo(name, key, max(0, Number(data.get("index"), 0)))
        elif action == "remove":
            model.Remove(name, key)
        elif action == "reset":
            model.ResetOrder(name)
        elif action == "add_set":
            setId = data.get("setId")
            if setId is None:
                return "NO_SET", 400
            model.AddStartggSet(name, setId)
            widget.Changed()
            # Get its players and round
            widget.Refresh()
            return "OK"
        elif action == "add_custom":
            team1 = str(data.get("team1") or "").strip()
            team2 = str(data.get("team2") or "").strip()
            if not team1 and not team2:
                return "NO_PLAYERS", 400
            model.AddCustomSet(name, team1, team2, match=str(data.get("match") or "").strip())
        elif action == "load":
            entry = next((e for e in model.Queue(name) if e["key"] == key), None)
            if entry is None:
                return "NO_SET", 404
            number = Number(data.get("scoreboard"), config.scoreboard)
            if number is None:
                return "NO_SCOREBOARD", 409
            widget.LoadEntry(entry, number)
            return "OK"
        elif action == "load_next":
            if config.scoreboard is None:
                return "NO_SCOREBOARD", 409
            widget.LoadNext(name)
            return "OK"
        else:
            return "UNKNOWN_ACTION", 400
        widget.Changed()
        return "OK"

    @gui_thread_sync
    def stream_queue_refresh(self):
        widget = self._Queue()
        if widget is None:
            return "NO_STREAM_QUEUE", 404
        widget.Refresh()
        return "OK"

    # Tournament info
    def _TournamentInfo(self):
        from .TournamentInfoWidget import TournamentInfoWidget

        return self._Widget(TournamentInfoWidget)

    @gui_thread_sync
    def tournament_info_set(self, data):
        widget = self._TournamentInfo()
        if widget is None:
            return "NO_TOURNAMENT_INFO", 404
        for key, value in (data or {}).items():
            field = widget.findChild(QWidget, str(key))
            if isinstance(field, QSpinBox):
                field.setValue(Number(value, 0))
            elif isinstance(field, QDateEdit):
                # From the browser's date picker: yyyy-mm-dd
                date = QDate.fromString(str(value or ""), "yyyy-MM-dd")
                if date.isValid():
                    field.setDate(date)
            elif isinstance(field, QLineEdit):
                field.setText(str(value or ""))
                field.editingFinished.emit()
        return "OK"

    @gui_thread_sync
    def tournament_info_action(self, action):
        from .TournamentDataManager import TournamentDataManager

        widget = self._TournamentInfo()
        if widget is None:
            return "NO_TOURNAMENT_INFO", 404
        if action == "load":
            if TournamentDataManager.instance.provider is None:
                return "NO_TOURNAMENT", 409
            TournamentDataManager.instance.GetTournamentData()
        elif action == "clear":
            widget.UpdateData({})
        elif action == "download_icon":
            if TournamentDataManager.instance.provider is None:
                return "NO_TOURNAMENT", 409
            widget.DownloadIcon()
        elif action == "default_icon":
            widget.SetDefaultIcon()
        else:
            return "UNKNOWN_ACTION", 400
        return "OK"

    # Commentary
    def _Commentary(self):
        from .CommentaryWidget import CommentaryWidget

        return self._Widget(CommentaryWidget)

    @gui_thread_sync
    def commentary_options(self):
        widget = self._Commentary()
        if widget is None:
            return "NO_COMMENTARY", 404
        return {
            "commentators": widget.commentatorNumber.value(),
            "characters": widget.characterNumber.value(),
        }

    @gui_thread_sync
    def commentary_set_options(self, data):
        widget = self._Commentary()
        if widget is None:
            return "NO_COMMENTARY", 404
        if Number(data.get("commentators")) is not None:
            widget.commentatorNumber.setValue(max(1, Number(data["commentators"])))
        if Number(data.get("characters")) is not None:
            widget.characterNumber.setValue(max(0, Number(data["characters"])))
        return "OK"

    # Player list
    def _PlayerList(self):
        from .PlayerListWidget import PlayerListWidget

        return self._Widget(PlayerListWidget)

    @gui_thread_sync
    def player_list_options(self):
        widget = self._PlayerList()
        if widget is None:
            return "NO_PLAYER_LIST", 404
        return {
            "slots": widget.slotNumber.value(),
            "playersPerSlot": widget.playerPerTeam.value(),
            "charactersPerPlayer": widget.charNumber.value(),
            "showScores": widget.showScoresCheckbox.isChecked(),
        }

    @gui_thread_sync
    def player_list_set_options(self, data):
        widget = self._PlayerList()
        if widget is None:
            return "NO_PLAYER_LIST", 404
        for key, control in (
            ("slots", widget.slotNumber),
            ("playersPerSlot", widget.playerPerTeam),
            ("charactersPerPlayer", widget.charNumber),
        ):
            if Number(data.get(key)) is not None:
                control.setValue(Number(data[key]))
        if "showScores" in data:
            widget.showScoresCheckbox.setChecked(bool(data["showScores"]))
        return "OK"

    @gui_thread_sync
    def player_list_load_standings(self):
        from .TournamentDataManager import TournamentDataManager

        widget = self._PlayerList()
        if widget is None:
            return "NO_PLAYER_LIST", 404
        if TournamentDataManager.instance.provider is None:
            return "NO_TOURNAMENT", 409
        widget.LoadFromStandingsClicked()
        return "OK"

    def _Slot(self, number):
        widget = self._PlayerList()
        if widget is None:
            return None
        slots = widget.playerList.slotWidgets
        number = Number(number)
        if number is None or not 1 <= number <= len(slots):
            return None
        return slots[number - 1]

    @gui_thread_sync
    def player_list_set_slot(self, number, data):
        slot = self._Slot(number)
        if slot is None:
            return "NO_SLOT", 404
        if "name" in data:
            slot.slotName.setText(str(data.get("name") or ""))
            slot.slotName.editingFinished.emit()
        if Number(data.get("score")) is not None:
            score = slot.scoreWidget.findChild(QSpinBox)
            score.setValue(Number(data["score"]))
            score.editingFinished.emit()
        return "OK"

    @gui_thread_sync
    def player_list_set_player(self, number, player, data):
        slot = self._Slot(number)
        player = Number(player)
        if slot is None or player is None or not 1 <= player <= len(slot.playerWidgets):
            return "NO_PLAYER", 404
        slot.playerWidgets[player - 1].SetData(data, False, False)
        return "OK"

    def player_list_results(self, mode=None):
        options = load_options()
        if mode in ("simple", "template"):
            options["mode"] = mode
        try:
            data = load_program_state()
        except Exception:
            data = {}
        text = generate_alt_text(
            data, options, bracket_link=SettingsManager.Get("TOURNAMENT_URL", "") or ""
        )
        return {"text": text, "options": options}

    def player_list_set_results_options(self, data):
        options = load_options()
        if data.get("resetTemplates"):
            for part, text in default_templates().items():
                options[f"template_{part}"] = text
        for key, value in (data.get("options") or {}).items():
            # Only the options the results text has
            if key in options or key.startswith("template_") or key.startswith("show_"):
                options[key] = value
        save_options(options)
        return "OK"

    # Team battle
    def _TeamBattle(self):
        from .TeamBattleWidget import TeamBattleWidget

        return TeamBattleWidget.instance

    @gui_thread_sync
    def team_battle_options(self):
        widget = self._TeamBattle()
        if widget is None:
            return "NO_TEAM_BATTLE", 404
        from .TeamBattleModeEnum import TeamBattleModeEnum

        mode = TeamBattleModeEnum.MatchToMode(widget.modeCombo.currentText())
        return {
            # The scoring mode, and whether only some players play
            "mode": mode.base.name,
            "limited": mode.limited,
            "plays": widget.playsNumber.value(),
            "players": widget.playerNumber.value(),
            "characters": widget.characterNumber.value(),
            "battleValue": widget.livesNumber.value(),
            "autoAdvance": widget.autoAdvance.isChecked(),
        }

    @gui_thread_sync
    def team_battle_set_options(self, data):
        widget = self._TeamBattle()
        if widget is None:
            return "NO_TEAM_BATTLE", 404
        from .TeamBattleModeEnum import TeamBattleModeEnum

        mode = TeamBattleModeEnum.MatchToMode(widget.modeCombo.currentText())
        if data.get("mode") in TeamBattleModeEnum.__members__:
            # A scoring mode keeps limited plays unless "limited" says otherwise
            mode = TeamBattleModeEnum[data["mode"]].WithLimited(mode.limited)
        if "limited" in data:
            mode = mode.WithLimited(bool(data["limited"]))
        widget.modeCombo.setCurrentIndex(list(TeamBattleModeEnum).index(mode))
        if Number(data.get("players")) is not None:
            widget.playerNumber.setValue(max(1, Number(data["players"])))
        if Number(data.get("plays")) is not None:
            widget.playsNumber.setValue(max(1, Number(data["plays"])))
        if Number(data.get("characters")) is not None:
            widget.characterNumber.setValue(max(0, Number(data["characters"])))
        if Number(data.get("battleValue")) is not None:
            widget.SetBattleValue(max(1, Number(data["battleValue"])))
        if "autoAdvance" in data:
            widget.autoAdvance.setChecked(bool(data["autoAdvance"]))
        return "OK"

    @gui_thread_sync
    def team_battle_set_team(self, team, data):
        widget = self._TeamBattle()
        team = Number(team)
        if widget is None or team not in (1, 2):
            return "NO_TEAM", 404
        if "name" in data:
            name = widget.TeamColumn(team).findChild(QLineEdit, "teamName")
            name.setText(str(data.get("name") or ""))
            name.editingFinished.emit()
        return "OK"

    @gui_thread_sync
    def team_battle_set_player(self, team, player, data):
        widget = self._TeamBattle()
        team, player = Number(team), Number(player)
        if widget is None or team not in (1, 2):
            return "NO_TEAM", 404
        players = widget.Players(team)
        if player is None or not 1 <= player <= len(players):
            return "NO_PLAYER", 404
        players[player - 1].SetData(data)
        return "OK"

    # Bracket
    def _Bracket(self):
        from .BracketWidget import BracketWidget

        return BracketWidget.instance

    @gui_thread_sync
    def bracket_options(self):
        from .BracketFocus import BracketFocus
        from .Scheduler import Scheduler

        widget = self._Bracket()
        focus = BracketFocus.instance
        if widget is None or focus is None:
            return "NO_BRACKET", 404
        scheduler = Scheduler.instance
        sources = []
        for i in range(1, widget.phaseSelection.count()):
            phase = widget.phaseSelection.itemData(i) or {}
            sources.append(
                {
                    "index": i,
                    "name": phase.get("name") or "",
                    "groups": [
                        {
                            "index": g,
                            "name": group.get("name") or "",
                            "bracketType": group.get("bracketType"),
                        }
                        for g, group in enumerate(phase.get("groups") or [])
                    ],
                }
            )
        return {
            "channels": [
                {"name": name, "phase": channel.phase, "limit": channel.limit}
                for name, channel in focus.channels.items()
            ],
            "phases": [
                {
                    "id": phase.id,
                    "name": phase.name,
                    "type": phase.type,
                    "fromProvider": phase.providerPhaseGroupId is not None,
                }
                for phase in widget.tournament.phases
            ],
            "sources": sources,
            "loaded": bool(widget.ProviderPhases()),
            "fetching": bool(widget.fetching),
            "autoUpdate": {
                "enabled": widget.cbAutoUpdateSets.isChecked(),
                "running": "bracket_sets" in scheduler.jobs and scheduler.IsRunning("bracket_sets"),
                "remainingMs": scheduler.RemainingMs("bracket_sets")
                if "bracket_sets" in scheduler.jobs
                else None,
            },
        }

    @gui_thread_sync
    def bracket_set_channel(self, name, data):
        from .BracketFocus import BracketFocus

        channel = BracketFocus.instance.Channel(name) if BracketFocus.instance else None
        if channel is None:
            return "NO_CHANNEL", 404
        if "phase" in data:
            if not BracketFocus.instance.HasPhase(data["phase"]):
                return "NO_PHASE", 404
            channel.SetPhase(data["phase"])
        if "limit" in data:
            limit = Number(data["limit"])
            channel.SetLimit(limit if limit and limit > 0 else None)
        return "OK"

    @gui_thread_sync
    def bracket_update_sets(self):
        widget = self._Bracket()
        if widget is None:
            return "NO_BRACKET", 404
        return widget.RefreshSets()

    @gui_thread_sync
    def bracket_auto_update(self, enabled):
        widget = self._Bracket()
        if widget is None:
            return "NO_BRACKET", 404
        widget.cbAutoUpdateSets.setChecked(bool(enabled))
        return "OK"

    @gui_thread_sync
    def bracket_load(self, phaseIndex, groupIndex):
        """Loads a phase group from start.gg into the current channel, like
        the source menu's Load."""
        from .TournamentDataManager import TournamentDataManager

        widget = self._Bracket()
        if widget is None:
            return "NO_BRACKET", 404
        if TournamentDataManager.instance.provider is None:
            return "NO_TOURNAMENT", 409
        phaseIndex, groupIndex = Number(phaseIndex), Number(groupIndex)
        if phaseIndex is None or not 1 <= phaseIndex < widget.phaseSelection.count():
            return "NO_PHASE", 404
        widget.phaseSelection.setCurrentIndex(phaseIndex)
        if groupIndex is None or not 0 <= groupIndex < widget.phaseGroupSelection.count():
            return "NO_PHASE_GROUP", 404
        widget.phaseGroupSelection.setCurrentIndex(groupIndex)
        widget.PhaseGroupChanged()
        return "OK"


actions = DashboardActions()


# =====================================================
# ROUTES
# =====================================================
# Unlocking, and what a locked browser may know
public = APIRouter(prefix="/dashboard-api")
router = APIRouter(prefix="/dashboard-api", dependencies=[Depends(RequirePin)])
# The dashboard's pages, all the same single page app
pages = APIRouter()


@public.get("/session")
async def session(request: Request):
    return {"pinRequired": bool(Pin()), "unlocked": TokenValid(request.headers.get(TOKEN_HEADER))}


@public.post("/unlock")
async def unlock(request: Request):
    address = request.client.host if request.client else "?"
    wait = attempts.LockedFor(address)
    if wait > 0:
        return respond(({"error": "TOO_MANY_ATTEMPTS", "retryAfter": round(wait)}, 429))
    pin = Pin()
    given = str((await body(request)).get("pin") or "").strip()
    if pin and not hmac.compare_digest(given, pin):
        attempts.Failed(address)
        logger.warning(f"Wrong dashboard PIN from {address}")
        return respond(({"error": "WRONG_PIN"}, 401))
    attempts.Succeeded(address)
    return {"token": TokenFor(pin) if pin else ""}


# The theme decides the page's colors before it's unlocked
@public.get("/theme")
async def theme():
    return await call(actions.theme)


@router.get("/status")
async def status():
    return await call(actions.status)


# Tournament and game
@router.post("/tournament/load")
async def tournament_load(request: Request):
    from .WebServer import WebServer

    return await call(WebServer.actions.load_tournament, (await body(request)).get("url"))


@router.get("/tournament/events")
async def tournament_events(request: Request):
    return await call(actions.tournament_events, request.query_params.get("url"))


@router.post("/tournament/unload")
async def tournament_unload():
    return await call(actions.unload_tournament)


@router.post("/tournament/repull")
async def tournament_repull():
    return await call(actions.repull_entrants)


@router.post("/game")
async def game(request: Request):
    from .WebServer import WebServer

    return await call(WebServer.actions.set_game, await body(request))


# Completed sets
@router.post("/completed-sets/auto")
async def completed_sets_auto(request: Request):
    return await call(actions.completed_sets_auto, (await body(request)).get("enabled"))


@router.post("/completed-sets/pull")
async def completed_sets_pull():
    return await call(actions.completed_sets_pull)


# Scoreboards
@router.post("/scoreboards/add")
async def scoreboards_add():
    return await call(actions.scoreboard_amount, 1)


@router.post("/scoreboards/remove")
async def scoreboards_remove():
    return await call(actions.scoreboard_amount, -1)


@router.post("/scoreboards/{number}/name")
async def scoreboard_name(number: str, request: Request):
    return await call(actions.scoreboard_name, number, (await body(request)).get("name"))


@router.post("/scoreboards/{number}/stop-tracking")
async def scoreboard_stop_tracking(number: str):
    return await call(actions.scoreboard_stop_tracking, number)


# Display controls (showing and hiding is /display/..., as for a Stream Deck)
@router.post("/display/groups")
async def display_add_group(request: Request):
    return await call(actions.display_add_group, (await body(request)).get("name"))


@router.delete("/display/groups/{name}")
async def display_remove_group(name: str):
    return await call(actions.display_remove_group, name)


@router.post("/display/refresh-folders")
async def display_refresh_folders():
    return await call(actions.display_refresh_folders)


# Stream queue
@router.get("/stream-queue/options")
async def stream_queue_options():
    return await call(actions.stream_queue_options)


@router.post("/stream-queue/options")
async def stream_queue_set_options(request: Request):
    return await call(actions.stream_queue_set_options, await body(request))


@router.post("/stream-queue/refresh")
async def stream_queue_refresh():
    return await call(actions.stream_queue_refresh)


@router.post("/stream-queue/streams")
async def stream_queue_add_stream(request: Request):
    return await call(actions.stream_queue_add_stream, (await body(request)).get("name"))


@router.delete("/stream-queue/streams/{name}")
async def stream_queue_remove_stream(name: str):
    return await call(actions.stream_queue_remove_stream, name)


@router.post("/stream-queue/streams/{name}/scoreboard")
async def stream_queue_set_scoreboard(name: str, request: Request):
    return await call(
        actions.stream_queue_set_scoreboard, name, (await body(request)).get("scoreboard")
    )


@router.post("/stream-queue/streams/{name}/{action}")
async def stream_queue_edit(name: str, action: str, request: Request):
    return await call(
        actions.stream_queue_edit, name, action.replace("-", "_"), await body(request)
    )


# Tournament info
@router.post("/tournament-info")
async def tournament_info_set(request: Request):
    return await call(actions.tournament_info_set, await body(request))


@router.post("/tournament-info/{action}")
async def tournament_info_action(action: str):
    return await call(actions.tournament_info_action, action.replace("-", "_"))


# Commentary (commentators' data is /update-commentary-<n>, as before)
@router.get("/commentary/options")
async def commentary_options():
    return await call(actions.commentary_options)


@router.post("/commentary/options")
async def commentary_set_options(request: Request):
    return await call(actions.commentary_set_options, await body(request))


# Player list
@router.get("/player-list/options")
async def player_list_options():
    return await call(actions.player_list_options)


@router.post("/player-list/options")
async def player_list_set_options(request: Request):
    return await call(actions.player_list_set_options, await body(request))


@router.post("/player-list/load-standings")
async def player_list_load_standings():
    return await call(actions.player_list_load_standings)


@router.post("/player-list/slots/{number}")
async def player_list_set_slot(number: str, request: Request):
    return await call(actions.player_list_set_slot, number, await body(request))


@router.post("/player-list/slots/{number}/players/{player}")
async def player_list_set_player(number: str, player: str, request: Request):
    return await call(actions.player_list_set_player, number, player, await body(request))


@router.get("/player-list/results")
async def player_list_results(request: Request):
    return await call(actions.player_list_results, request.query_params.get("mode"))


@router.post("/player-list/results")
async def player_list_set_results_options(request: Request):
    return await call(actions.player_list_set_results_options, await body(request))


# Team battle (scores and the active player are /team-battle-..., as before)
@router.get("/team-battle/options")
async def team_battle_options():
    return await call(actions.team_battle_options)


@router.post("/team-battle/options")
async def team_battle_set_options(request: Request):
    return await call(actions.team_battle_set_options, await body(request))


@router.post("/team-battle/teams/{team}")
async def team_battle_set_team(team: str, request: Request):
    return await call(actions.team_battle_set_team, team, await body(request))


@router.post("/team-battle/teams/{team}/players/{player}")
async def team_battle_set_player(team: str, player: str, request: Request):
    return await call(actions.team_battle_set_player, team, player, await body(request))


# Bracket
@router.get("/bracket/options")
async def bracket_options():
    return await call(actions.bracket_options)


@router.post("/bracket/channels/{name}")
async def bracket_set_channel(name: str, request: Request):
    return await call(actions.bracket_set_channel, name, await body(request))


@router.post("/bracket/update-sets")
async def bracket_update_sets():
    return await call(actions.bracket_update_sets)


@router.post("/bracket/auto-update")
async def bracket_auto_update(request: Request):
    return await call(actions.bracket_auto_update, (await body(request)).get("enabled"))


@router.post("/bracket/load")
async def bracket_load(request: Request):
    data = await body(request)
    return await call(actions.bracket_load, data.get("phase"), data.get("group"))


@pages.get("/dashboard")
@pages.get("/dashboard/{path:path}")
async def dashboard_page(path: str = ""):
    return FileResponse(
        os.path.join(os.path.abspath("."), "stage_strike_app/build/index.html"),
        headers={"Cache-Control": "no-cache"},
    )


def Setup(api, window):
    """Adds the dashboard's routes to the web server. Before its catch-all
    file route, which would take them."""
    actions.window = window
    api.include_router(public)
    api.include_router(router)
    api.include_router(pages)
