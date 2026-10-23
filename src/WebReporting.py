# Reporting sets to start.gg from the web pages (see ReportingStore):
#
# - Admin (/report-admin, the dashboard's Reporting section): every set of the
#   loaded event, by state or by station, reported, updated, DQ'd, called,
#   started, reset or assigned on start.gg right away.
# - Approval (/report-approval, the dashboard's Approval section): the results
#   players submitted from a reporting station, approved (reported to
#   start.gg), edited first, or rejected.
# - Player reporting station (/report): players find their set and submit its
#   result, which waits for an admin's approval.
#
# The admin pages are behind the dashboard's PIN (WebDashboard), the station
# behind its own PIN (Settings > Web Reporting), traded for a token sent in
# the X-Station-Token header. Reports use the start.gg API token of Settings
# > API Keys, like the scoreboard's reporting (StartGGReporter).
#
# The event's sets are read from start.gg's site API, like the rest of
# HyperDrive's tournament data: all of them now and then, and in between only
# the ones updated since.
import base64
import hashlib
import hmac
import os
import threading
import time

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger

from .GameReport import (
    ASSIGN_STATION,
    ASSIGN_STREAM,
    MARK_IN_PROGRESS,
    MARK_SET_CALLED,
    REPORT_DQ,
    REPORT_SET,
    RESET_SET,
    UPDATE_SET,
)
from .ReportingStore import (
    APPROVED,
    CALLED,
    COMPLETED,
    IN_PROGRESS,
    NOT_STARTED,
    PENDING,
    REJECTED,
    Conflicts,
    DQVariables,
    EntrantIds,
    IsOpen,
    NormalizeGames,
    ParseSet,
    ProviderGames,
    ReportingStore,
    Score,
    Variables,
    WinnerTeam,
)
from .SettingsManager import SettingsManager
from .StartGGReporter import HasToken, ReportError, RetryableError, SendRetrying, Token
from .TournamentDataProvider.StartGGClient import GQL_URL, ReadQuery, StartGGClient
from .WebDashboard import (
    PinAttempts,
    RequirePin,
    body,
    call,
    respond,
)

STATION_PIN_SETTING = "web_reporting.station_pin"
STATIONS_ENABLED_SETTING = "web_reporting.stations_enabled"
REFRESH_SETTING = "web_reporting.refresh_interval"
STATION_HEADER = "X-Station-Token"

DEFAULT_REFRESH_SECS = 30
MIN_REFRESH_SECS = 10
# Every set is fetched again this often, the ones updated in between otherwise
FULL_REFRESH_SECS = 600
# Sets updated this long before the last one seen are fetched again, in case
# start.gg's clock or cache lags
UPDATED_MARGIN_SECS = 120
# Sets per page: each costs about 9 of the 1000 start.gg allows a request
SETS_PER_PAGE = 80
# A set changed from here keeps its change while start.gg's site API, which
# caches for up to a minute, may still answer the old one
LOCAL_CHANGE_SECS = 90
# Retries when start.gg can't be reached, while the page waits for the answer
SEND_DELAYS = [2, 5]
# Pending results a set can have at once
MAX_PENDING_PER_SET = 5

ACTION_QUERIES = {
    "call": MARK_SET_CALLED,
    "start": MARK_IN_PROGRESS,
    "reset": RESET_SET,
    "report": REPORT_SET,
    "update": UPDATE_SET,
    "dq": REPORT_DQ,
    "assign_station": ASSIGN_STATION,
    "assign_stream": ASSIGN_STREAM,
}


def StationPin():
    return str(SettingsManager.Get(STATION_PIN_SETTING, "") or "").strip()


def StationsEnabled():
    return bool(SettingsManager.Get(STATIONS_ENABLED_SETTING, True))


def RefreshSecs():
    try:
        secs = int(SettingsManager.Get(REFRESH_SETTING, DEFAULT_REFRESH_SECS))
    except (TypeError, ValueError):
        secs = DEFAULT_REFRESH_SECS
    return max(MIN_REFRESH_SECS, secs)


def StationTokenFor(pin):
    """The token a station keeps once it has the PIN. It changes with the
    PIN, so changing the PIN locks every station out."""
    digest = hmac.new(pin.encode(), b"hyperdrive-reporting-station", hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def StationTokenValid(token):
    pin = StationPin()
    if not pin:
        return True
    return bool(token) and hmac.compare_digest(str(token), StationTokenFor(pin))


def RequireStation(request: Request):
    if not StationTokenValid(request.headers.get(STATION_HEADER)):
        raise HTTPException(status_code=401, detail="STATION_PIN_REQUIRED")


def Address(request: Request):
    return request.client.host if request.client else ""


class NotAvailable(Exception):
    """Reporting can't be done now (no start.gg event loaded, no token...)."""

    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code = code
        self.status = status


def Fail(code, message, status=409):
    return {"error": code, "message": message}, status


# =====================================================
# START.GG
# =====================================================
class Fetcher:
    """Reads sets, stations and streams from start.gg's site API. Each
    returns None when start.gg couldn't be reached."""

    def __init__(self):
        self.client = StartGGClient()
        self.setsQuery = ReadQuery("ReportingSets")
        self.setQuery = ReadQuery("ReportingSet")
        self.stationsQuery = ReadQuery("StreamsStations")

    def _Query(self, operation, query, variables):
        data = self.client.Request(
            GQL_URL,
            requests.post,
            jsonParams={"operationName": operation, "variables": variables, "query": query},
        )
        return data.get("data") if isinstance(data, dict) else None

    def Sets(self, eventSlug, updatedAfter=None):
        """[set node], or None if a page failed."""
        filters = {"hideEmpty": True}
        if updatedAfter:
            filters["updatedAfter"] = int(updatedAfter)

        def page(number):
            return self._Query(
                "ReportingSetsQuery",
                self.setsQuery,
                {
                    "eventSlug": eventSlug,
                    "page": number,
                    "perPage": SETS_PER_PAGE,
                    "filters": filters,
                },
            )

        pages = StartGGClient.FetchAllPages(page, "event.sets.pageInfo.totalPages")
        nodes = []
        for data in pages:
            sets = ((data or {}).get("event") or {}).get("sets")
            if sets is None:
                return None
            nodes.extend(n for n in sets.get("nodes") or [] if n)
        return nodes

    def Set(self, setId):
        """The set node with its games, {} if there's no such set."""
        data = self._Query("ReportingSetQuery", self.setQuery, {"id": str(setId)})
        if data is None:
            return None
        return data.get("set") or {}

    def StationsAndStreams(self, eventSlug):
        data = self._Query("StreamsStationsQuery", self.stationsQuery, {"eventSlug": eventSlug})
        if data is None:
            return None
        event = data.get("event") or {}
        streams = [
            {"id": str(s.get("id")), "name": s.get("streamName") or ""}
            for s in ((event.get("tournament") or {}).get("streams") or [])
            if s and s.get("id") is not None and s.get("enabled") is not False
        ]
        names = {s["id"]: s["name"] for s in streams}
        stations = [
            {
                "id": str(s.get("id")),
                "number": s.get("number"),
                "stream": names.get(str(s.get("streamId")), ""),
            }
            for s in ((event.get("stations") or {}).get("nodes") or [])
            if s and s.get("id") is not None and s.get("enabled") is not False
        ]
        stations.sort(key=lambda s: s.get("number") or 0)
        return {"stations": stations, "streams": streams}


class SetCache:
    """The event's sets, fetched again when they're older than asked."""

    def __init__(self, fetcher, clock=time.time):
        self.fetcher = fetcher
        self.clock = clock
        self.lock = threading.RLock()
        # One fetch at a time: pages asking meanwhile wait for it
        self.fetchLock = threading.Lock()
        self.Clear(None)

    def Clear(self, eventSlug):
        with self.lock:
            self.eventSlug = eventSlug
            self.sets = {}
            self.stations = []
            self.streams = []
            self.fetchedAt = 0
            self.fullAt = 0
            self.lastUpdated = 0
            self.error = ""
            # set id -> when it was changed from here
            self.localChanges = {}

    def Get(self, eventSlug, maxAge, force=False):
        """{"sets": [set], "stations", "streams", "updatedAt", "error"}."""
        with self.lock:
            if eventSlug != self.eventSlug:
                self.Clear(eventSlug)
            fresh = self.clock() - self.fetchedAt < maxAge
        if force or not fresh:
            with self.fetchLock:
                # Someone else may have fetched them while this waited
                if force or self.clock() - self.fetchedAt >= maxAge:
                    self._Fetch(eventSlug, full=force)
        with self.lock:
            return {
                "sets": list(self.sets.values()),
                "stations": list(self.stations),
                "streams": list(self.streams),
                "updatedAt": self.fetchedAt or None,
                "error": self.error,
            }

    def _Fetch(self, eventSlug, full=False):
        now = self.clock()
        full = full or not self.fullAt or now - self.fullAt > FULL_REFRESH_SECS
        updatedAfter = None if full else max(0, self.lastUpdated - UPDATED_MARGIN_SECS)
        nodes = self.fetcher.Sets(eventSlug, updatedAfter)
        places = self.fetcher.StationsAndStreams(eventSlug) if full else None
        with self.lock:
            if eventSlug != self.eventSlug:
                return
            if nodes is None:
                self.error = "start.gg couldn't be reached"
                # Not again right away
                self.fetchedAt = now
                return
            self.error = ""
            if full:
                kept = {id: s for id, s in self.sets.items() if self._Local(id, now)}
                self.sets = {}
                self.sets.update(kept)
            for node in nodes:
                self._Merge(ParseSet(node), now)
            if places is not None:
                self.stations = places["stations"]
                self.streams = places["streams"]
            self.fetchedAt = now
            if full:
                self.fullAt = now

    def _Local(self, setId, now):
        changed = self.localChanges.get(setId)
        return changed is not None and now - changed < LOCAL_CHANGE_SECS

    def _Merge(self, set, now):
        # Sets of a bracket that hasn't started only have preview ids, which
        # can't be reported
        if not str(set["id"] or "").isdigit():
            return
        self.lastUpdated = max(self.lastUpdated, set.get("updatedAt") or 0)
        changed = self.localChanges.get(set["id"])
        if (
            self._Local(set["id"], now)
            and set["id"] in self.sets
            and (set.get("updatedAt") or 0) < changed - 5
        ):
            return
        self.sets[set["id"]] = set

    def Find(self, setId):
        with self.lock:
            return self.sets.get(str(setId))

    def Put(self, set):
        """A set changed from here, as start.gg will have it."""
        with self.lock:
            if set.get("id") is None:
                return
            now = self.clock()
            self.localChanges[set["id"]] = now
            self.sets[set["id"]] = dict(set, updatedAt=max(set.get("updatedAt") or 0, int(now)))


def GameAssets():
    from .GameAssetManager import GameAssetManager

    return GameAssetManager.instance


def StageCodename(startggId):
    found = GameAssets().GetStageFromStartGGId(startggId)
    return found[1].get("codename") if found else None


def CharacterName(startggId):
    found = GameAssets().GetCharacterFromStartGGId(startggId)
    return found[0] if found else None


# =====================================================
# REPORTING
# =====================================================
class Reporting:
    def __init__(self, store=None, fetcher=None, send=None, clock=time.time):
        self.store = store or ReportingStore()
        self.fetcher = fetcher or Fetcher()
        self.cache = SetCache(self.fetcher, clock)
        # send(query, variables) -> data, raising ReportError or RetryableError
        self.send = send or (
            lambda query, variables: SendRetrying(query, variables, Token(), SEND_DELAYS)
        )
        self.clock = clock
        # Each set changed by one request at a time
        self.setLocks = {}
        self.setLocksLock = threading.Lock()

    # Things the tests replace
    def EventSlug(self):
        """The loaded start.gg event's slug, or raises NotAvailable."""
        from .TournamentDataManager import TournamentDataManager

        provider = TournamentDataManager.instance.provider
        if provider is None:
            raise NotAvailable("NO_TOURNAMENT", "No tournament is loaded in HyperDrive")
        if getattr(provider, "NAME", None) != "StartGG":
            raise NotAvailable(
                "NOT_STARTGG", "Reporting from the web pages only works with start.gg events"
            )
        return str(provider.url).split("start.gg/")[1]

    def CharacterId(self, character):
        return GameAssets().GetStartGGCharacterId(character)

    def StageId(self, codename):
        return GameAssets().GetStartGGStageId(codename)

    def HasToken(self):
        return HasToken()

    def _SetLock(self, setId):
        with self.setLocksLock:
            return self.setLocks.setdefault(str(setId), threading.Lock())

    # =====================================================
    # SETS
    # =====================================================
    def Sets(self, force=False):
        slug = self.EventSlug()
        data = self.cache.Get(slug, RefreshSecs(), force)
        pending = self.store.PendingBySet()
        for s in data["sets"]:
            s["pending"] = pending.get(s["id"], 0)
        return {
            **data,
            "eventSlug": slug,
            "hasToken": self.HasToken(),
            "refreshSecs": RefreshSecs(),
        }

    def FreshSet(self, setId):
        """The set as start.gg has it now, with its node (for its games)."""
        node = self.fetcher.Set(setId)
        if node is None:
            raise NotAvailable("STARTGG_UNREACHABLE", "start.gg couldn't be reached", 504)
        if not node:
            raise NotAvailable("NO_SET", "start.gg doesn't have this set", 404)
        set = ParseSet(node)
        slug = self.EventSlug()
        eventSlug = (node.get("event") or {}).get("slug")
        if eventSlug and not slug.startswith(str(eventSlug)):
            raise NotAvailable("OTHER_EVENT", "This set isn't in the loaded event", 404)
        return set, node

    def SetDetail(self, setId):
        set, node = self.FreshSet(setId)
        self.cache.Put(set)
        pending = self.store.PendingBySet().get(set["id"], 0)
        return {
            **set,
            "pending": pending,
            "games": ProviderGames(node, EntrantIds(set), StageCodename, CharacterName),
        }

    # =====================================================
    # ACTIONS
    # =====================================================
    def _Send(self, query, variables):
        try:
            return self.send(query, variables), None
        except RetryableError as e:
            return None, Fail("STARTGG_UNREACHABLE", f"start.gg couldn't be reached: {e}", 504)
        except ReportError as e:
            return None, Fail("STARTGG_REFUSED", str(e), 502)
        except Exception as e:
            logger.exception("Web reporting")
            return None, Fail("STARTGG_ERROR", str(e), 502)

    def _Report(self, set, games=None, dqWinner=None, force=False):
        """Reports the set (with its games, or as a DQ). A set already
        completed on start.gg is reset first when forced. Returns (set as
        start.gg will have it, error)."""
        if set["state"] == COMPLETED:
            if not force:
                return None, Fail(
                    "SET_COMPLETED",
                    "The set is already completed on start.gg. Reset it to report it again.",
                )
            _data, error = self._Send(RESET_SET, {"setId": set["id"]})
            if error:
                return None, error
        if dqWinner is not None:
            variables = DQVariables(set, dqWinner)
            query = REPORT_DQ
            winnerTeam = int(dqWinner)
            scores = [None, None]
        else:
            variables = Variables(set, games, True, self.CharacterId, self.StageId)
            if variables.get("winnerId") is None:
                return None, Fail("TIED", "The score is tied: the set has no winner yet", 400)
            query = REPORT_SET
            winnerTeam = WinnerTeam(games)
            scores = Score(games)
        _data, error = self._Send(query, dict(variables, setId=set["id"]))
        if error:
            return None, error
        return dict(
            set,
            state=COMPLETED,
            winnerId=EntrantIds(set)[winnerTeam - 1],
            scores=scores,
            completedAt=int(self.clock()),
        ), None

    def Action(self, setId, action, data, by="Admin"):
        """Changes a set on start.gg from the Admin page, right away."""
        if action not in ACTION_QUERIES:
            return Fail("UNKNOWN_ACTION", f"Unknown action {action}", 400)
        if not self.HasToken():
            return Fail("NO_TOKEN", "Set a start.gg API token in Settings > API Keys")
        with self._SetLock(setId):
            set, _node = self.FreshSet(setId)
            if action in ("report", "update", "dq", "start", "call") and not all(EntrantIds(set)):
                return Fail("NOT_READY", "The set's players aren't known yet")
            changed, error, score = None, None, None

            if action == "report" or action == "dq":
                games = NormalizeGames(data.get("games") or [])
                dqWinner = data.get("winner") if action == "dq" else None
                if action == "dq" and dqWinner not in (1, 2, "1", "2"):
                    return Fail("NO_WINNER", "Pick who wins by DQ", 400)
                changed, error = self._Report(set, games, dqWinner, bool(data.get("force")))
                score = changed["scores"] if changed else Score(games)
            elif action == "update":
                games = NormalizeGames(data.get("games") or [])
                if not games:
                    return Fail("NO_GAMES", "Set at least one game's winner", 400)
                if set["state"] == COMPLETED:
                    return Fail(
                        "SET_COMPLETED",
                        "The set is completed on start.gg: report it instead, which resets it first",
                    )
                variables = Variables(set, games, False, self.CharacterId, self.StageId)
                _data, error = self._Send(UPDATE_SET, dict(variables, setId=set["id"]))
                score = Score(games)
                changed = dict(set, state=IN_PROGRESS, scores=score)
            elif action == "assign_station":
                stationId = data.get("stationId")
                if not stationId:
                    return Fail("NO_STATION", "Pick a station", 400)
                _data, error = self._Send(
                    ASSIGN_STATION, {"setId": set["id"], "stationId": str(stationId)}
                )
                station = next(
                    (s for s in self.cache.stations if s["id"] == str(stationId)),
                    {"id": str(stationId), "number": None},
                )
                changed = dict(set, station={"id": station["id"], "number": station["number"]})
            elif action == "assign_stream":
                streamId = data.get("streamId")
                if not streamId:
                    return Fail("NO_STREAM", "Pick a stream", 400)
                _data, error = self._Send(
                    ASSIGN_STREAM, {"setId": set["id"], "streamId": str(streamId)}
                )
                stream = next(
                    (s for s in self.cache.streams if s["id"] == str(streamId)),
                    {"id": str(streamId), "name": ""},
                )
                changed = dict(set, stream={"id": stream["id"], "name": stream["name"]})
            else:
                state = {"call": CALLED, "start": IN_PROGRESS, "reset": NOT_STARTED}[action]
                _data, error = self._Send(ACTION_QUERIES[action], {"setId": set["id"]})
                changed = dict(set, state=state)
                if action == "reset":
                    changed.update(scores=[None, None], winnerId=None, completedAt=None)

            message = error[0]["message"] if error else ""
            self.store.AddLog(action, set, by=by, ok=error is None, message=message, score=score)
            if error:
                return error
            self.cache.Put(changed)
            if action in ("report", "dq"):
                self.store.SupersedePending(set["id"], by)
            return {"ok": True, "set": changed}

    # =====================================================
    # APPROVAL
    # =====================================================
    def Submissions(self, status=PENDING):
        """Submissions, newest first for the resolved ones and oldest first
        for the pending ones, with what may be wrong with the pending ones."""
        submissions = self.store.Submissions(status)
        if status == PENDING:
            counts = self.store.PendingBySet()
            try:
                slug = self.EventSlug()
                self.cache.Get(slug, RefreshSecs())
                available = True
            except NotAvailable:
                available = False
            result = []
            for s in submissions:
                current = self.cache.Find(s["setId"]) if available else s.get("set")
                result.append(
                    dict(
                        s,
                        current=current,
                        conflicts=Conflicts(s, current, counts.get(s["setId"], 0))
                        if available
                        else [],
                    )
                )
            return result
        return list(reversed(submissions))[:200]

    def Approve(self, id, data, by="Admin"):
        if not self.HasToken():
            return Fail("NO_TOKEN", "Set a start.gg API token in Settings > API Keys")
        submission = self.store.Get(id)
        if submission is None:
            return Fail("NO_SUBMISSION", "There's no such result", 404)
        with self._SetLock(submission["setId"]):
            if submission.get("status") != PENDING:
                return Fail("RESOLVED", f"This result was already {submission.get('status')}")
            set, _node = self.FreshSet(submission["setId"])
            if EntrantIds(set) != EntrantIds(submission["set"]):
                return Fail(
                    "ENTRANTS_CHANGED",
                    "The set's players changed on start.gg since this result was sent. Reject it.",
                )
            games = submission["games"]
            if data.get("games") is not None:
                games = NormalizeGames(data["games"])
            changed, error = self._Report(set, games, force=bool(data.get("force")))
            if error:
                if error[0]["error"] != "SET_COMPLETED":
                    self.store.AddLog(
                        "approved",
                        set,
                        by=by,
                        ok=False,
                        message=error[0]["message"],
                        score=Score(games),
                        submitter=submission.get("station") or "",
                    )
                return error
            self.store.Resolve(id, APPROVED, by, games=games)
            self.cache.Put(changed)
            return {"ok": True, "set": changed}

    def Reject(self, id, reason="", by="Admin"):
        submission = self.store.Resolve(id, REJECTED, by, message=str(reason or "")[:200])
        if submission is None:
            return Fail("RESOLVED", "This result was already approved or rejected")
        return {"ok": True}

    # =====================================================
    # STATIONS
    # =====================================================
    def StationSets(self):
        """The sets players can report: both players known, not finished."""
        if not StationsEnabled():
            return Fail("STATIONS_DISABLED", "Reporting stations are turned off", 403)
        data = self.Sets()
        sets = [{k: s.get(k) for k in STATION_FIELDS} for s in data["sets"] if IsOpen(s)]
        return {
            "sets": sets,
            "stations": data["stations"],
            "updatedAt": data["updatedAt"],
            "error": data["error"],
            "refreshSecs": data["refreshSecs"],
        }

    def Submit(self, data, address=""):
        if not StationsEnabled():
            return Fail("STATIONS_DISABLED", "Reporting stations are turned off", 403)
        setId = str(data.get("setId") or "")
        if not setId:
            return Fail("NO_SET", "Pick a set", 400)
        try:
            games = NormalizeGames(data.get("games"))
        except ValueError:
            return Fail("NO_GAMES", "Set who won each game", 400)
        if WinnerTeam(games) is None:
            return Fail("TIED", "The score is tied: who won the set?", 400)
        self.EventSlug()
        set = self.cache.Find(setId)
        if set is None:
            set, _node = self.FreshSet(setId)
        if set["state"] == COMPLETED:
            return Fail("SET_COMPLETED", "This set is already reported")
        if not IsOpen(set):
            return Fail("NOT_READY", "This set's players aren't known yet")
        if self.store.PendingBySet().get(setId, 0) >= MAX_PENDING_PER_SET:
            return Fail("TOO_MANY", "This set already has results waiting for approval", 429)
        submission = self.store.Add(
            {k: v for k, v in set.items() if k != "pending"},
            games,
            station=data.get("station") or "",
            stationNumber=data.get("stationNumber"),
            submitter=data.get("submitter") or "",
            address=address,
        )
        logger.info(f"Web reporting: result for set {setId} submitted from {address}")
        return {"ok": True, "id": submission["id"], "score": submission["score"]}


# What stations get of a set
STATION_FIELDS = [
    "id",
    "identifier",
    "roundText",
    "phase",
    "phaseGroup",
    "state",
    "bestOf",
    "entrants",
    "station",
    "stream",
    "pending",
]

reporting = Reporting()
stationAttempts = PinAttempts()


def Run(fn, *args, **kwargs):
    """fn's answer, or NotAvailable's."""
    try:
        return fn(*args, **kwargs)
    except NotAvailable as e:
        return Fail(e.code, str(e), e.status)
    except ValueError as e:
        return Fail("BAD_REQUEST", str(e), 400)


def Pending():
    try:
        return reporting.store.PendingCount()
    except Exception:
        return 0


# =====================================================
# ROUTES
# =====================================================
admin = APIRouter(prefix="/dashboard-api/reporting", dependencies=[Depends(RequirePin)])
stationPublic = APIRouter(prefix="/reporting-api")
station = APIRouter(prefix="/reporting-api", dependencies=[Depends(RequireStation)])
pages = APIRouter()


def By(request: Request, who="Admin"):
    address = Address(request)
    return f"{who} ({address})" if address else who


@admin.get("/sets")
async def admin_sets(request: Request):
    return await call(Run, reporting.Sets, request.query_params.get("refresh") == "1")


@admin.get("/sets/{setId}")
async def admin_set(setId: str):
    return await call(Run, reporting.SetDetail, setId)


@admin.post("/sets/{setId}/{action}")
async def admin_set_action(setId: str, action: str, request: Request):
    data = await body(request)
    return await call(Run, reporting.Action, setId, action.replace("-", "_"), data, By(request))


@admin.get("/submissions")
async def admin_submissions(request: Request):
    status = request.query_params.get("status") or PENDING
    return await call(
        Run, lambda: {"submissions": reporting.Submissions(None if status == "all" else status)}
    )


@admin.post("/submissions/{id}/approve")
async def admin_approve(id: str, request: Request):
    return await call(Run, reporting.Approve, id, await body(request), By(request))


@admin.post("/submissions/{id}/reject")
async def admin_reject(id: str, request: Request):
    data = await body(request)
    return await call(Run, reporting.Reject, id, data.get("reason"), By(request))


@admin.get("/log")
async def admin_log():
    return await call(lambda: {"log": reporting.store.Log()})


# The station page inside the dashboard, behind the dashboard's PIN
@admin.get("/station/sets")
async def admin_station_sets():
    return await call(Run, reporting.StationSets)


@admin.post("/station/submissions")
async def admin_station_submit(request: Request):
    return await call(Run, reporting.Submit, await body(request), Address(request))


@stationPublic.get("/session")
async def station_session(request: Request):
    return {
        "pinRequired": bool(StationPin()),
        "unlocked": StationTokenValid(request.headers.get(STATION_HEADER)),
        "enabled": StationsEnabled(),
    }


@stationPublic.post("/unlock")
async def station_unlock(request: Request):
    address = Address(request) or "?"
    wait = stationAttempts.LockedFor(address)
    if wait > 0:
        return respond(({"error": "TOO_MANY_ATTEMPTS", "retryAfter": round(wait)}, 429))
    pin = StationPin()
    given = str((await body(request)).get("pin") or "").strip()
    if pin and not hmac.compare_digest(given, pin):
        stationAttempts.Failed(address)
        logger.warning(f"Wrong reporting station PIN from {address}")
        return respond(({"error": "WRONG_PIN"}, 401))
    stationAttempts.Succeeded(address)
    return {"token": StationTokenFor(pin) if pin else ""}


@station.get("/sets")
async def station_sets():
    return await call(Run, reporting.StationSets)


@station.post("/submissions")
async def station_submit(request: Request):
    return await call(Run, reporting.Submit, await body(request), Address(request))


@pages.get("/report")
@pages.get("/report-admin")
@pages.get("/report-approval")
async def reporting_page():
    return FileResponse(
        os.path.join(os.path.abspath("."), "stage_strike_app/build/index.html"),
        headers={"Cache-Control": "no-cache"},
    )


def Setup(api):
    """Adds the routes to the web server, before its catch-all file route."""
    api.include_router(admin)
    api.include_router(stationPublic)
    api.include_router(station)
    api.include_router(pages)
