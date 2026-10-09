# Reports sets to start.gg through its official API, with the start.gg API
# token set in Settings > API Keys (from an account that's an admin of the
# tournament). Each scoreboard has its own queue of requests: they're sent
# one at a time, in order, newer game updates replace ones not sent yet, and
# requests that fail because of the network are retried.
import time
import traceback

import requests
from loguru import logger
from qtpy.QtCore import *

from .GameReport import CURRENT_USER, MARK_IN_PROGRESS, REPORT_SET, RESET_SET, UPDATE_SET
from .SettingsManager import SettingsManager
from .Workers import Worker

API_URL = "https://api.start.gg/gql/alpha"
TIMEOUT_SECS = 20
# Seconds before each retry
RETRY_DELAYS = [2, 5, 10, 20, 30]

KIND_START = "start"
KIND_UPDATE = "update"
KIND_REPORT = "report"
KIND_RESET = "reset"

STATUS_IDLE = "idle"
STATUS_PENDING = "pending"
STATUS_SENDING = "sending"
STATUS_SYNCED = "synced"
STATUS_REPORTED = "reported"
STATUS_ERROR = "error"
STATUS_RETRYING = "retrying"


class ReportError(Exception):
    """start.gg refused the request: retrying won't help."""


class RetryableError(Exception):
    """The network or start.gg failed: retrying might help."""


def Token():
    return (SettingsManager.Get("api_keys.startgg", "") or "").strip()


def HasToken():
    return bool(Token())


def IsReportableSetId(setId):
    # Sets of a bracket that hasn't started only have preview ids
    return setId is not None and str(setId).isdigit()


def Send(query, variables, token=None):
    """Runs a request on start.gg's API. Returns its data."""
    token = token or Token()
    if not token:
        raise ReportError("No start.gg API token. Set one in Settings > API Keys.")
    try:
        response = requests.post(
            API_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=TIMEOUT_SECS,
        )
    except requests.RequestException as e:
        raise RetryableError(str(e))

    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableError(f"start.gg answered {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise RetryableError(
            f"start.gg answered {response.status_code} with something that isn't JSON"
        )
    if response.status_code in (401, 403):
        raise ReportError(body.get("message") or "The start.gg API token was refused")
    if body.get("errors"):
        messages = [e.get("message") or str(e) for e in body.get("errors") or []]
        raise ReportError("; ".join(messages))
    if body.get("success") is False:
        raise ReportError(body.get("message") or "start.gg refused the request")
    return body.get("data") or {}


class StartGGReporterSignals(QObject):
    # Scoreboard number: its status changed
    status_changed = Signal(int)
    # Scoreboard number, set id: the set was reported
    set_reported = Signal(int, str)
    # Scoreboard number, set id: the set was reset on start.gg
    set_reset = Signal(int, str)


class StartGGReporter(QObject):
    instance: "StartGGReporter" = None

    def __init__(self):
        super().__init__()
        self.signals = StartGGReporterSignals()
        self.threadPool = QThreadPool()
        self.threadPool.setMaxThreadCount(4)
        # Scoreboard number -> [request], the first one being sent
        self.queues = {}
        self.sending = set()
        self.status = {}

    def Status(self, scoreboard):
        return self.status.get(scoreboard, {"state": STATUS_IDLE, "message": "", "setId": None})

    def _SetStatus(self, scoreboard, state, message="", setId=None):
        current = self.Status(scoreboard)
        self.status[scoreboard] = {
            "state": state,
            "message": message,
            "setId": setId if setId is not None else current.get("setId"),
            "time": time.time(),
        }
        self.signals.status_changed.emit(scoreboard)

    def Busy(self, scoreboard):
        return bool(self.queues.get(scoreboard))

    def Clear(self, scoreboard):
        """Drops requests not sent yet, e.g. another set was loaded."""
        queue = self.queues.get(scoreboard) or []
        self.queues[scoreboard] = queue[:1] if scoreboard in self.sending else []
        self._SetStatus(scoreboard, STATUS_IDLE, "", None)

    def Submit(self, scoreboard, kind, setId, variables=None):
        if not IsReportableSetId(setId):
            self._SetStatus(
                scoreboard,
                STATUS_ERROR,
                QCoreApplication.translate(
                    "app", "This set can't be reported: its bracket hasn't started on start.gg yet"
                ),
                setId,
            )
            return
        request = {
            "kind": kind,
            "setId": str(setId),
            "variables": dict(variables or {}, setId=str(setId)),
            "attempt": 0,
        }
        queue = self.queues.setdefault(scoreboard, [])
        if kind == KIND_UPDATE:
            # Only the latest games matter
            start = 1 if scoreboard in self.sending else 0
            queue[start:] = [r for r in queue[start:] if r["kind"] != KIND_UPDATE]
        queue.append(request)
        if scoreboard not in self.sending:
            self._SetStatus(scoreboard, STATUS_PENDING, "", setId)
            self._Next(scoreboard)

    def _Next(self, scoreboard):
        queue = self.queues.get(scoreboard) or []
        if not queue or scoreboard in self.sending:
            return
        request = queue[0]
        self.sending.add(scoreboard)
        self._SetStatus(scoreboard, STATUS_SENDING, "", request["setId"])
        query = {
            KIND_START: MARK_IN_PROGRESS,
            KIND_UPDATE: UPDATE_SET,
            KIND_REPORT: REPORT_SET,
            KIND_RESET: RESET_SET,
        }[request["kind"]]
        token = Token()

        def Run(progress_callback=None, cancel_event=None):
            try:
                return {"ok": True, "data": Send(query, request["variables"], token)}
            except RetryableError as e:
                return {"ok": False, "retry": True, "message": str(e)}
            except ReportError as e:
                return {"ok": False, "retry": False, "message": str(e)}
            except Exception as e:
                logger.error(traceback.format_exc())
                return {"ok": False, "retry": False, "message": str(e)}

        worker = Worker(Run)
        worker.signals.result.connect(lambda result: self._Done(scoreboard, request, result))
        self.threadPool.start(worker)

    def _Done(self, scoreboard, request, result):
        self.sending.discard(scoreboard)
        queue = self.queues.get(scoreboard) or []

        if result.get("ok"):
            if queue and queue[0] is request:
                queue.pop(0)
            logger.info(f"start.gg: {request['kind']} for set {request['setId']} done")
            if request["kind"] == KIND_REPORT:
                self._SetStatus(scoreboard, STATUS_REPORTED, "", request["setId"])
                self.signals.set_reported.emit(scoreboard, request["setId"])
            elif request["kind"] == KIND_RESET:
                self._SetStatus(
                    scoreboard,
                    STATUS_IDLE,
                    QCoreApplication.translate("app", "Set reset on start.gg"),
                    request["setId"],
                )
                self.signals.set_reset.emit(scoreboard, request["setId"])
            else:
                self._SetStatus(scoreboard, STATUS_SYNCED, "", request["setId"])
            self._Next(scoreboard)
            return

        message = result.get("message") or ""
        logger.error(f"start.gg: {request['kind']} for set {request['setId']} failed: {message}")
        if result.get("retry") and request["attempt"] < len(RETRY_DELAYS):
            delay = RETRY_DELAYS[request["attempt"]]
            request["attempt"] += 1
            self._SetStatus(
                scoreboard,
                STATUS_RETRYING,
                QCoreApplication.translate("app", "{0} Retrying in {1}s.").format(message, delay),
                request["setId"],
            )
            # Kept at the front of the queue, unless it was cleared meanwhile
            QTimer.singleShot(delay * 1000, lambda: self._Next(scoreboard))
            return

        # Given up: what's left can't go through without it
        if queue and queue[0] is request:
            queue.pop(0)
        if request["kind"] == KIND_START:
            # Not worth stopping the rest for
            self._SetStatus(scoreboard, STATUS_ERROR, message, request["setId"])
            self._Next(scoreboard)
            return
        self.queues[scoreboard] = [r for r in queue if r["kind"] in (KIND_RESET,)]
        self._SetStatus(scoreboard, STATUS_ERROR, message, request["setId"])
        self._Next(scoreboard)

    def Retry(self, scoreboard, request=None):
        """Sends again what failed last (given by the caller, as the games
        may have changed since)."""
        if request is not None:
            self.Submit(scoreboard, request["kind"], request["setId"], request.get("variables"))

    def TestToken(self, callback):
        """Calls callback(ok, message) with who the token belongs to."""
        token = Token()

        def Run(progress_callback=None, cancel_event=None):
            try:
                data = Send(CURRENT_USER, {}, token)
                user = data.get("currentUser") or {}
                name = (user.get("player") or {}).get("gamerTag") or user.get("slug") or ""
                return (True, name)
            except Exception as e:
                return (False, str(e))

        worker = Worker(Run)
        worker.signals.result.connect(lambda result: callback(*result))
        self.threadPool.start(worker)


StartGGReporter.instance = StartGGReporter()
