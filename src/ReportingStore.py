# What the web reporting pages work with (see src/WebReporting.py): the
# event's sets as start.gg has them, the results players submit from a
# reporting station until an admin approves or rejects them, and a log of
# everything reported from the web pages.
#
# Submissions and the log are kept in user_data/web_reporting.json, so they
# survive a restart.
#
# A set's teams are its start.gg slots: team 1 is the first slot, team 2 the
# second, in the games' format of GameReport.ToDict().
#
# Nothing in here depends on Qt, so it can be tested on its own.
import os
import threading
import time
import uuid

import orjson

from .GameReport import BuildGameData, GameReport, SetWinnerEntrant

# start.gg's set states
NOT_STARTED = 1
IN_PROGRESS = 2
COMPLETED = 3
CALLED = 6
OPEN_STATES = (NOT_STARTED, IN_PROGRESS, CALLED)

# Submission statuses
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
# Another submission of the same set was approved
SUPERSEDED = "superseded"

# What may be wrong with a pending submission, see Conflicts()
CONFLICT_COMPLETED = "completed"
CONFLICT_ENTRANTS = "entrants_changed"
CONFLICT_DUPLICATE = "duplicate"
CONFLICT_UPDATED = "updated"
CONFLICT_MISSING = "missing"

MAX_GAMES = 15
MAX_CHARACTERS = 8
MAX_TEXT = 64
# Resolved submissions and log entries kept
MAX_RESOLVED = 500
MAX_LOG = 1000


# =====================================================
# SETS
# =====================================================
def _Id(value):
    return None if value is None else str(value)


def ParseSet(node):
    """A start.gg set (StartGGReportingSet(s)Query) as the pages use it."""
    node = node or {}
    entrants = []
    for slot in (node.get("slots") or [])[:2]:
        entrant = (slot or {}).get("entrant") or {}
        entrants.append({"id": _Id(entrant.get("id")), "name": entrant.get("name") or ""})
    while len(entrants) < 2:
        entrants.append({"id": None, "name": ""})
    station = node.get("station") or {}
    stream = node.get("stream") or {}
    group = node.get("phaseGroup") or {}
    phase = group.get("phase") or {}
    return {
        "id": _Id(node.get("id")),
        "identifier": node.get("identifier") or "",
        "round": node.get("round"),
        "roundText": node.get("fullRoundText") or "",
        "phase": phase.get("name") or "",
        "phaseId": _Id(phase.get("id")),
        "phaseGroup": group.get("displayIdentifier") or "",
        "phaseGroupId": _Id(group.get("id")),
        "state": int(node.get("state") or NOT_STARTED),
        "bestOf": node.get("totalGames"),
        "entrants": entrants,
        "scores": [node.get("entrant1Score"), node.get("entrant2Score")],
        "winnerId": _Id(node.get("winnerId")),
        "station": (
            {"id": _Id(station.get("id")), "number": station.get("number")}
            if station.get("id") is not None
            else None
        ),
        "stream": (
            {"id": _Id(stream.get("id")), "name": stream.get("streamName") or ""}
            if stream.get("id") is not None
            else None
        ),
        "startedAt": node.get("startedAt"),
        "completedAt": node.get("completedAt"),
        "updatedAt": node.get("updatedAt"),
    }


def IsReady(set):
    """Both players are known: the set can be played and reported."""
    return all(e.get("id") for e in set.get("entrants") or [])


def IsOpen(set):
    """A set players can report: both players known, not finished."""
    return IsReady(set) and set.get("state") in OPEN_STATES


def SetName(set):
    names = [e.get("name") or "?" for e in set.get("entrants") or []]
    return " vs ".join(names) or set.get("id") or ""


# =====================================================
# GAMES
# =====================================================
def _Text(value):
    return str(value)[:MAX_TEXT] if value not in (None, "") else None


def NormalizeGames(games):
    """Games sent by a page, checked: [{"winner": 1, 2 or None, "stage":
    codename or None, "characters": {"1": [en_name], "2": [en_name]}}]."""
    if not isinstance(games, list):
        raise ValueError("games must be a list")
    result = []
    for game in games[:MAX_GAMES]:
        game = game if isinstance(game, dict) else {}
        winner = game.get("winner")
        try:
            winner = int(winner) if winner is not None else None
        except (TypeError, ValueError):
            winner = None
        characters = game.get("characters") if isinstance(game.get("characters"), dict) else {}
        result.append(
            {
                "winner": winner if winner in (1, 2) else None,
                "stage": _Text(game.get("stage")),
                "characters": {
                    team: [
                        _Text(c)
                        for c in (characters.get(team) or characters.get(int(team)) or [])[
                            :MAX_CHARACTERS
                        ]
                        if _Text(c)
                    ]
                    for team in ("1", "2")
                },
            }
        )
    # Games after the last one played aren't needed
    while result and result[-1]["winner"] is None:
        result.pop()
    return result


def _Lookup(lookup, value):
    if value is None:
        return None
    try:
        return lookup(value)
    except Exception:
        # The game's assets aren't loaded, or don't know it
        return None


def ProviderGames(node, entrantIds, stageCodename=lambda id: None, characterName=lambda id: None):
    """A start.gg set's games (its "games" field), in the pages' format.
    Stages and characters the game's assets don't know are left out."""
    entrantIds = [str(i) for i in entrantIds]
    games = []
    for game in sorted((node or {}).get("games") or [], key=lambda g: g.get("orderNum") or 0):
        winner = str(game.get("winnerId")) if game.get("winnerId") is not None else None
        characters = {"1": [], "2": []}
        for selection in game.get("selections") or []:
            entrant = str(((selection or {}).get("entrant") or {}).get("id"))
            if entrant in entrantIds:
                name = _Lookup(characterName, selection.get("selectionValue"))
                if name:
                    characters[str(entrantIds.index(entrant) + 1)].append(name)
        games.append(
            {
                "winner": entrantIds.index(winner) + 1 if winner in entrantIds else None,
                "stage": _Lookup(stageCodename, (game.get("stage") or {}).get("id")),
                "characters": characters,
            }
        )
    return games


def Report(games):
    return GameReport.FromDict({"bestOf": 0, "games": games})


def Score(games):
    return list(Report(games).Score())


def WinnerTeam(games):
    """1 or 2, or None while the score is tied."""
    return Report(games).SetWinnerTeam()


def EntrantIds(set):
    return [e.get("id") for e in set.get("entrants") or []]


def Variables(set, games, final, characterId=lambda c: None, stageId=lambda s: None):
    """start.gg's variables to report (final) or update the set's games."""
    report = Report(games)
    entrantIds = EntrantIds(set)
    variables = {"gameData": BuildGameData(report, entrantIds, False, characterId, stageId)}
    if final:
        variables["winnerId"] = SetWinnerEntrant(report, entrantIds, False)
    return variables


def DQVariables(set, winnerTeam):
    """start.gg's variables to report a DQ won by team 1 or 2."""
    return {"winnerId": EntrantIds(set)[int(winnerTeam) - 1]}


# =====================================================
# SUBMISSIONS
# =====================================================
def Conflicts(submission, current, pendingCount=1):
    """Why a pending submission may not be right anymore, from the set as
    start.gg has it now (None if it's not found)."""
    if current is None:
        return [CONFLICT_MISSING]
    conflicts = []
    if current.get("state") == COMPLETED:
        conflicts.append(CONFLICT_COMPLETED)
    if EntrantIds(current) != EntrantIds(submission.get("set") or {}):
        conflicts.append(CONFLICT_ENTRANTS)
    if pendingCount > 1:
        conflicts.append(CONFLICT_DUPLICATE)
    updated = current.get("updatedAt") or 0
    if (
        CONFLICT_COMPLETED not in conflicts
        and updated
        and updated > (submission.get("createdAt") or 0)
        and current.get("state") != (submission.get("set") or {}).get("state")
    ):
        conflicts.append(CONFLICT_UPDATED)
    return conflicts


class ReportingStore:
    def __init__(self, path="./user_data/web_reporting.json", clock=time.time):
        self.path = path
        self.clock = clock
        self.lock = threading.RLock()
        self.submissions = []
        self.log = []
        self.loaded = False

    # =====================================================
    # SAVING
    # =====================================================
    def Load(self):
        with self.lock:
            self.loaded = True
            try:
                with open(self.path, "rb") as file:
                    data = orjson.loads(file.read())
            except FileNotFoundError:
                return
            except Exception:
                # A broken file is kept aside rather than overwritten
                try:
                    os.replace(self.path, self.path + ".broken")
                except OSError:
                    pass
                return
            self.submissions = [s for s in data.get("submissions") or [] if isinstance(s, dict)]
            self.log = [e for e in data.get("log") or [] if isinstance(e, dict)]

    def _Ensure(self):
        if not self.loaded:
            self.Load()

    def Save(self):
        with self.lock:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "wb") as file:
                file.write(
                    orjson.dumps(
                        {"submissions": self.submissions, "log": self.log},
                        option=orjson.OPT_INDENT_2,
                    )
                )
            os.replace(temp, self.path)

    def _Prune(self):
        resolved = [s for s in self.submissions if s.get("status") != PENDING]
        if len(resolved) > MAX_RESOLVED:
            drop = {id(s) for s in resolved[: len(resolved) - MAX_RESOLVED]}
            self.submissions = [s for s in self.submissions if id(s) not in drop]
        del self.log[:-MAX_LOG]

    # =====================================================
    # SUBMISSIONS
    # =====================================================
    def Add(self, set, games, station="", stationNumber=None, submitter="", address=""):
        """A result submitted from a reporting station, waiting for approval."""
        games = NormalizeGames(games)
        with self.lock:
            self._Ensure()
            submission = {
                "id": uuid.uuid4().hex[:12],
                "setId": set.get("id"),
                "set": set,
                "games": games,
                "score": Score(games),
                "winner": WinnerTeam(games),
                "station": _Text(station) or "",
                "stationNumber": stationNumber,
                "submitter": _Text(submitter) or "",
                "address": address or "",
                "createdAt": self.clock(),
                "status": PENDING,
                "resolvedAt": None,
                "resolvedBy": "",
                "message": "",
            }
            self.submissions.append(submission)
            self.AddLog(
                "submitted", set, by=self._StationName(submission), score=submission["score"]
            )
            return submission

    @staticmethod
    def _StationName(submission):
        return submission.get("station") or "Reporting station"

    def Get(self, id):
        with self.lock:
            self._Ensure()
            return next((s for s in self.submissions if s.get("id") == id), None)

    def Submissions(self, status=None):
        """Newest last."""
        with self.lock:
            self._Ensure()
            return [s for s in self.submissions if status is None or s.get("status") == status]

    def PendingCount(self):
        return len(self.Submissions(PENDING))

    def PendingBySet(self):
        counts = {}
        for s in self.Submissions(PENDING):
            counts[s.get("setId")] = counts.get(s.get("setId"), 0) + 1
        return counts

    def Resolve(self, id, status, by="Admin", message="", games=None):
        """Approves or rejects a pending submission. Approving one supersedes
        the set's other pending submissions."""
        with self.lock:
            submission = self.Get(id)
            if submission is None or submission.get("status") != PENDING:
                return None
            now = self.clock()
            if games is not None:
                games = NormalizeGames(games)
                if games != submission["games"]:
                    submission["originalGames"] = submission["games"]
                    submission["games"] = games
                    submission["score"] = Score(games)
                    submission["winner"] = WinnerTeam(games)
            submission.update(status=status, resolvedAt=now, resolvedBy=by, message=message or "")
            if status == APPROVED:
                for other in self.submissions:
                    if other is not submission and other.get("setId") == submission.get("setId"):
                        if other.get("status") == PENDING:
                            other.update(
                                status=SUPERSEDED,
                                resolvedAt=now,
                                resolvedBy=by,
                                message="Another result was approved",
                            )
            self.AddLog(
                "approved" if status == APPROVED else "rejected",
                submission.get("set") or {},
                by=by,
                score=submission["score"],
                message=message,
                submitter=self._StationName(submission),
            )
            return submission

    def SupersedePending(self, setId, by="Admin"):
        """The set was reported another way: its pending submissions are
        dropped. Returns how many."""
        with self.lock:
            count = 0
            for s in self.Submissions(PENDING):
                if s.get("setId") == setId:
                    s.update(
                        status=SUPERSEDED,
                        resolvedAt=self.clock(),
                        resolvedBy=by,
                        message="The set was reported from the Admin page",
                    )
                    count += 1
            if count:
                self.Save()
            return count

    # =====================================================
    # LOG
    # =====================================================
    def AddLog(self, action, set, by="", ok=True, message="", score=None, submitter=""):
        """Saves the store, with what happened."""
        with self.lock:
            self._Ensure()
            self.log.append(
                {
                    "time": self.clock(),
                    "action": action,
                    "setId": (set or {}).get("id"),
                    "setName": SetName(set or {}),
                    "round": (set or {}).get("roundText") or "",
                    "by": by or "",
                    "submitter": submitter or "",
                    "ok": bool(ok),
                    "message": message or "",
                    "score": score,
                }
            )
            self._Prune()
            self.Save()

    def Log(self, limit=200):
        """Newest first."""
        with self.lock:
            self._Ensure()
            return list(reversed(self.log[-limit:]))
