# Checks that a failed request isn't taken for an empty answer:
# - StartGGClient.Query raises typed errors (ProviderErrors.py): the network,
#   rate limiting, a refused token, something that isn't there
# - the provider's methods raise them inside RaiseProviderErrors, and return
#   something empty outside of it, as they always did
# - the stream queue, the standings, the set list and the entrants fail as a
#   whole when one of their requests fails, and stay empty when start.gg says
#   there's nothing
# - paged lists are checked against start.gg's count
# - every request waits on one rate limiter, and a 429 holds them all back
# Run from the repository root: python test/test_provider_errors.py
import json
import os
import sys
import threading
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

import requests

from src.TournamentDataProvider import StartGGClient as clientModule
from src.TournamentDataProvider.ProviderContext import AppContext
from src.TournamentDataProvider.ProviderErrors import (
    KIND_AUTH,
    KIND_NOT_FOUND,
    KIND_RATE_LIMITED,
    KIND_TRANSIENT,
    AuthError,
    Failed,
    NotFoundError,
    ProviderError,
    RaiseProviderErrors,
    Raising,
    RateLimitedError,
    TransientError,
)
from src.TournamentDataProvider.StartGGClient import GQL_URL, RateLimiter, StartGGClient
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider

QUERY = {"operationName": "Q", "variables": {}, "query": "{ a }"}


class Response:
    def __init__(self, status, body=None, headers=None, text=None):
        self.status_code = status
        self.text = text if text is not None else json.dumps(body if body is not None else {})
        self.headers = headers or {}


class Session:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def Client(*answers):
    slept = []
    session = Session(*answers)
    return StartGGClient(session=session, sleep=slept.append), session, slept


def Raises(fn, kind):
    try:
        fn()
    except ProviderError as e:
        assert e.kind == kind, f"{e.kind} ({e}), expected {kind}"
        return e
    raise AssertionError(f"no ProviderError ({kind} expected)")


# =====================================================
# THE CLIENT
# =====================================================
def TestClientErrors():
    def Query(*answers, retries=0):
        client, _, _ = Client(*answers)
        return lambda: client.Query(GQL_URL, requests.post, jsonParams=QUERY, retries=retries)

    # An answer, even one start.gg refused part of
    assert Query(Response(200, {"data": {"a": 1}}))() == {"data": {"a": 1}}
    assert Query(Response(200, {"errors": ["complexity"]}))() == {"errors": ["complexity"]}
    assert Query(Response(400, {"errors": ["bad query"]}))() == {"errors": ["bad query"]}

    # What failed, and how
    Raises(Query(requests.exceptions.ConnectionError("reset")), KIND_TRANSIENT)
    Raises(Query(requests.exceptions.ReadTimeout("slow")), KIND_TRANSIENT)
    Raises(Query(Response(503, text="<html>down</html>")), KIND_TRANSIENT)
    Raises(Query(Response(200, text="<html>")), KIND_TRANSIENT)
    Raises(Query(Response(200, text="null")), KIND_TRANSIENT)
    Raises(Query(Response(200, text="[]")), KIND_TRANSIENT)
    Raises(Query(Response(401, {"message": "Invalid authentication token"})), KIND_AUTH)
    Raises(Query(Response(403, {})), KIND_AUTH)
    Raises(Query(Response(404, {})), KIND_NOT_FOUND)
    error = Raises(
        Query(Response(429, {"message": "Rate limit"}, {"Retry-After": "7"})), KIND_RATE_LIMITED
    )
    assert (
        error.retryAfter == 7.0 and error.retryable and error.response == {"message": "Rate limit"}
    )
    assert isinstance(error, RateLimitedError)
    assert not AuthError("no").retryable and not NotFoundError("no").retryable
    assert TransientError("net").retryable

    # Request keeps answering {} (or what start.gg sent) for its callers
    client, _, _ = Client(requests.exceptions.ReadTimeout("slow"), Response(502, {"data": "x"}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {}
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY, retries=0) == {"data": "x"}


def TestRaisingOrNot():
    error = TransientError("net")
    assert not Raising()
    assert Failed(error, []) == []
    with RaiseProviderErrors():
        assert Raising()
        with RaiseProviderErrors():
            pass
        assert Raising()
        assert Raises(lambda: Failed(error, []), KIND_TRANSIENT) is error
    assert not Raising()

    # Only on the thread that asked for it
    seen = []
    with RaiseProviderErrors():
        thread = threading.Thread(target=lambda: seen.append(Raising()))
        thread.start()
        thread.join()
    assert seen == [False]


# =====================================================
# THE RATE LIMITER
# =====================================================
class Clock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 6))
        self.now += seconds


def TestRateLimiter():
    # 80 a minute, 4 at once: the fifth waits for a token (0.75s each)
    clock = Clock()
    limiter = RateLimiter(rate=80, per=60, burst=4, clock=clock, sleep=clock.sleep, reserve=0)
    for _ in range(4):
        limiter.Acquire()
    assert clock.slept == []
    limiter.Acquire()
    limiter.Acquire()
    assert clock.slept == [0.75, 0.75], clock.slept
    # A quiet while fills the bucket again, and no more than that
    clock.now += 1000
    clock.slept.clear()
    for _ in range(5):
        limiter.Acquire()
    assert clock.slept == [0.75], clock.slept

    # A 429 holds everyone back, whoever got it
    clock = Clock()
    limiter = RateLimiter(rate=80, per=60, burst=10, clock=clock, sleep=clock.sleep, reserve=0)
    limiter.Acquire()
    limiter.BackOff(5)
    limiter.Acquire()
    assert clock.slept == [5.0], clock.slept
    limiter.Acquire()
    assert clock.slept == [5.0]
    # The longest back-off asked for counts
    limiter.BackOff(3)
    limiter.BackOff(1)
    limiter.Acquire()
    assert clock.slept == [5.0, 3.0], clock.slept

    # Background requests are spaced out and leave the reserve alone
    clock = Clock()
    limiter = RateLimiter(
        rate=80, per=60, burst=10, clock=clock, sleep=clock.sleep, backgroundInterval=1.5, reserve=4
    )
    with limiter.Background():
        limiter.Acquire()
        limiter.Acquire()
        limiter.Acquire()
    assert clock.slept == [1.5, 1.5], clock.slept
    limiter.Acquire()
    assert clock.slept == [1.5, 1.5], "not a background request anymore"
    # With the bucket down to the reserve, background waits, the user doesn't
    clock = Clock()
    limiter = RateLimiter(
        rate=80, per=60, burst=10, clock=clock, sleep=clock.sleep, backgroundInterval=0, reserve=4
    )
    for _ in range(6):
        limiter.Acquire()
    assert clock.slept == []
    limiter.Acquire(background=True)
    assert clock.slept == [0.75], clock.slept
    for _ in range(3):
        limiter.Acquire()
    assert clock.slept == [0.75], clock.slept


def TestClientsShareTheLimiter():
    # Every client of the app waits on the same limiter...
    assert StartGGClient().limiter is StartGGClient().limiter is clientModule._limiter
    # ...whichever thread pool sends the request (FetchAllPages, the
    # standings, the entrants): it's taken in Query itself
    acquired = []

    class Counting(RateLimiter):
        def Acquire(self, background=None):
            acquired.append(threading.get_ident())
            return 0

    session = Session(*[Response(200, {"data": {"info": {"totalPages": 5}}}) for _ in range(5)])
    session.lock = threading.Lock()
    real = session.request

    def request(method, url, **kwargs):
        with session.lock:
            return real(method, url, **kwargs)

    session.request = request
    client = StartGGClient(session=session, limiter=Counting())
    pages = StartGGClient.FetchAllPages(
        lambda page: client.Query(GQL_URL, requests.post, jsonParams=QUERY),
        "data.info.totalPages",
    )
    assert len(pages) == 5 and len(acquired) == 5, acquired

    # A 429 backs the shared limiter off, for the others too
    clock = Clock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    first = StartGGClient(
        session=Session(Response(429, headers={"Retry-After": "4"}), Response(200, {"data": 1})),
        sleep=clock.sleep,
        limiter=limiter,
    )
    other = StartGGClient(session=Session(Response(200, {"data": 2})), limiter=limiter)
    assert first.Query(GQL_URL, requests.post, jsonParams=QUERY) == {"data": 1}
    assert clock.slept == [4.0], clock.slept
    limiter.BackOff(2)
    assert other.Query(GQL_URL, requests.post, jsonParams=QUERY) == {"data": 2}
    assert clock.slept == [4.0, 2.0], clock.slept

    # Out of retries on a 429: the others still wait
    clock = Clock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    client = StartGGClient(
        session=Session(Response(429, {}, {"Retry-After": "6"})), sleep=clock.sleep, limiter=limiter
    )
    Raises(
        lambda: client.Query(GQL_URL, requests.post, jsonParams=QUERY, retries=0), KIND_RATE_LIMITED
    )
    limiter.Acquire()
    assert clock.slept == [6.0], clock.slept


# =====================================================
# THE PROVIDER
# =====================================================
def Provider(answer):
    """A start.gg provider whose requests are answered by answer(operation,
    variables): a dict, or an exception to raise"""
    provider = StartGGDataProvider(
        "https://www.start.gg/tournament/t/event/e", None, None, context=AppContext()
    )
    provider.asked = []
    lock = threading.Lock()

    def query(url=None, type=None, headers=None, jsonParams=None, params=None, **kwargs):
        operation = (jsonParams or {}).get("operationName")
        variables = (jsonParams or {}).get("variables") or {}
        with lock:
            provider.asked.append((operation, variables))
        result = answer(operation, variables)
        if isinstance(result, Exception):
            raise result
        return result

    provider.QueryRequests = query
    return provider


def Strict(fn, *args, **kwargs):
    with RaiseProviderErrors():
        return fn(*args, **kwargs)


FAILURES = [
    TransientError("no network"),
    RateLimitedError("slow down"),
    AuthError("refused"),
    # What a request that failed used to look like, and still does in tests
    {},
]


def TestStreamQueue():
    def Queue(sets):
        return {
            "data": {
                "event": {
                    "slug": "tournament/t/event/e",
                    "tournament": {
                        "streamQueue": [{"stream": {"streamName": "main"}, "sets": sets}]
                    },
                }
            }
        }

    aSet = {"id": 1, "fullRoundText": "Winners Final", "slots": [], "event": {"slug": "x"}}
    provider = Provider(lambda operation, variables: Queue([aSet]))
    queue = Strict(provider.GetStreamQueue)
    assert list(queue) == ["main"] and queue["main"]["1"]["id"] == 1, queue

    # Nothing queued is an answer: {}
    for empty in [
        {"data": {"event": {"slug": "s", "tournament": {"streamQueue": None}}}},
        {"data": {"event": {"slug": "s", "tournament": {"streamQueue": []}}}},
    ]:
        provider = Provider(lambda operation, variables: empty)
        assert Strict(provider.GetStreamQueue) == {}
        assert provider.GetStreamQueue() == {}

    # A failed request isn't
    for failure in FAILURES:
        provider = Provider(lambda operation, variables: failure)
        error = Raises(
            lambda: Strict(provider.GetStreamQueue), getattr(failure, "kind", "transient")
        )
        assert isinstance(error, ProviderError)
        # ...unless it's called the old way
        assert provider.GetStreamQueue() == {}

    # start.gg refusing the query, or not knowing the event
    provider = Provider(lambda operation, variables: {"data": None, "errors": [{"message": "x"}]})
    Raises(lambda: Strict(provider.GetStreamQueue), KIND_TRANSIENT)
    provider = Provider(lambda operation, variables: {"data": {"event": None}})
    Raises(lambda: Strict(provider.GetStreamQueue), KIND_NOT_FOUND)


def Standing(placement, total):
    return {
        "data": {
            "event": {
                "standings": {
                    "pageInfo": {"total": total},
                    "nodes": [
                        {
                            "entrant": {
                                "name": f"E{placement}",
                                "initialSeedNum": placement,
                                "participants": [
                                    {"player": {"id": placement, "gamerTag": f"P{placement}"}}
                                ],
                            }
                        }
                    ],
                }
            }
        }
    }


def TestStandings():
    def Answer(failing=None, failure=None):
        def answer(operation, variables):
            placement = variables["playerNumber"]
            return failure if placement == failing else Standing(placement, 8)

        return answer

    provider = Provider(Answer())
    teams = Strict(provider.GetStandings, 8)
    assert [t["players"][0]["gamerTag"] for t in teams] == [f"P{i}" for i in range(1, 9)]

    # A placement that fails: no standings, not the others moved up a place
    for failing in (1, 3, 8):
        for failure in FAILURES:
            provider = Provider(Answer(failing, failure))
            Raises(lambda: Strict(provider.GetStandings, 8), getattr(failure, "kind", "transient"))
            assert provider.GetStandings(8) == [], "the old way: no standings"

    # An event without standings yet: empty, not failed
    none = {"data": {"event": {"standings": {"pageInfo": {"total": 0}, "nodes": []}}}}
    provider = Provider(lambda operation, variables: none)
    assert Strict(provider.GetStandings, 8) == []


def SetsPage(page, perPage, ids, total=None):
    start = (page - 1) * perPage
    return {
        "data": {
            "event": {
                "sets": {
                    "pageInfo": {
                        "total": len(ids) if total is None else total,
                        "totalPages": max(1, -(-len(ids) // perPage)),
                    },
                    "nodes": [{"id": id, "slots": []} for id in ids[start : start + perPage]],
                }
            }
        }
    }


def TestSetList():
    ids = list(range(1, 101))
    provider = Provider(lambda operation, variables: SetsPage(variables["page"], 32, ids))
    progress = []
    sets = Strict(provider.GetMatches, progress_callback=lambda n, t: progress.append((n, t)))
    assert [s["id"] for s in sets] == ids, "every set, in page order"
    assert sorted(progress) == [(1, 4), (2, 4), (3, 4), (4, 4)], progress

    # A page that fails: no list, not one missing 32 sets
    for failing in (1, 2, 4):
        for failure in FAILURES:
            provider = Provider(
                lambda operation, variables: (
                    failure
                    if variables["page"] == failing
                    else SetsPage(variables["page"], 32, ids)
                )
            )
            Raises(lambda: Strict(provider.GetMatches), getattr(failure, "kind", "transient"))
            assert provider.GetMatches() == []

    # A page without its list (start.gg refused it) fails it too
    broken = {"data": {"event": {"sets": None}}, "errors": [{"message": "complexity"}]}
    provider = Provider(
        lambda operation, variables: (
            broken if variables["page"] == 3 else SetsPage(variables["page"], 32, ids)
        )
    )
    Raises(lambda: Strict(provider.GetMatches), KIND_TRANSIENT)

    # No sets at all is an answer
    provider = Provider(lambda operation, variables: SetsPage(1, 32, []))
    assert Strict(provider.GetMatches) == []

    # Sets that moved between pages while they were fetched: start.gg's
    # count says some are missing, so the pages are fetched again
    rounds = []

    def moving(operation, variables):
        page = variables["page"]
        if page == 1:
            rounds.append(1)
        # The first time, set 33 has slipped from page 2 to page 1's end
        if len(rounds) == 1 and page == 2:
            return SetsPage(1, 32, list(range(34, 66)), total=100) | {}
        return SetsPage(page, 32, ids)

    provider = Provider(moving)
    sets = Strict(provider.GetMatches)
    assert sorted(s["id"] for s in sets) == ids and len(rounds) == 2, (len(sets), rounds)


def EntrantsPage(page, perPage, count):
    ids = list(range(1, count + 1))
    start = (page - 1) * perPage
    return {
        "data": {
            "event": {
                "entrants": {
                    "pageInfo": {"total": count, "totalPages": max(1, -(-count // perPage))},
                    "nodes": [
                        {
                            "id": id,
                            "initialSeedNum": id,
                            "participants": [{"player": {"id": id, "gamerTag": f"P{id}"}}],
                        }
                        for id in ids[start : start + perPage]
                    ],
                }
            }
        }
    }


def TestEntrants():
    provider = Provider(lambda operation, variables: EntrantsPage(variables["page"], 64, 150))
    players = Strict(provider.FetchEntrants)
    assert [p["gamerTag"] for p in players] == [f"P{i}" for i in range(1, 151)]
    assert provider.player_seeds[150] == 150

    for failure in FAILURES:
        provider = Provider(
            lambda operation, variables: (
                failure if variables["page"] == 2 else EntrantsPage(variables["page"], 64, 150)
            )
        )
        Raises(lambda: Strict(provider.FetchEntrants), getattr(failure, "kind", "transient"))
        assert provider.FetchEntrants() == []
        assert provider.player_seeds == {}, "no seeds from a list that wasn't complete"


def TestOtherMethods():
    """What else tells failed from empty, and what a failure doesn't stop"""
    failing = Provider(lambda operation, variables: TransientError("no network"))
    for method, args, empty in [
        (failing.GetTournamentData, (), {}),
        (failing.GetTournamentPhases, (), []),
        (failing.GetTournamentPhaseGroup, (1,), {}),
        (failing.GetTournamentPhaseGroupSets, (1,), {}),
        (failing.GetStations, (), []),
        (failing.GetStreamMatchId, ("main",), None),
        (failing.GetStationMatchsId, (1,), None),
        (failing.GetFutureMatch, (1,), {}),
        (failing.GetCompletedSets, (), []),
        (failing.GetSetDurations, (), []),
    ]:
        Raises(lambda: Strict(method, *args), KIND_TRANSIENT)
        assert method(*args) == empty, method.__name__
    assert failing.GetStreamsAndStations() == {"streams": [], "stations": []}

    # Each set of a queue is fetched on its own: one that fails is None
    assert Strict(failing.GetFutureMatchesList, [{"id": 1}, {"id": 2}]) == {"1": None, "2": None}
    # Lookups on the side don't fail what they're a detail of
    assert failing.GetUserProfile(5) is None and failing._FetchUserMains("user/x", 1) is None
    assert failing.GetIconURL() is None

    # The event doesn't exist
    missing = Provider(lambda operation, variables: {"data": {"event": None}})
    Raises(lambda: Strict(missing.GetTournamentData), KIND_NOT_FOUND)
    Raises(lambda: Strict(missing.GetTournamentPhases), KIND_NOT_FOUND)

    # An admin link that can't be resolved
    admin = "https://www.start.gg/admin/tournament/t/brackets/123"
    provider = Provider(
        lambda operation, variables: {"data": {"event": {"slug": "tournament/t/event/e"}}}
    )
    provider.url = admin
    assert provider.Connect() == "https://www.start.gg/tournament/t/event/e" == provider.url
    provider = Provider(lambda operation, variables: {"data": {"event": None}})
    provider.url = admin
    Raises(provider.Connect, KIND_NOT_FOUND)
    provider = Provider(lambda operation, variables: TransientError("no network"))
    provider.url = admin
    Raises(provider.Connect, KIND_TRANSIENT)
    # An event link needs no request
    provider = Provider(lambda operation, variables: TransientError("no network"))
    assert provider.Connect() == provider.url and provider.asked == []


def TestGetMatch():
    aSet = {"data": {"set": {"id": 7, "slots": [], "fullRoundText": "Winners Final"}}}

    def answer(operation, variables):
        return aSet

    provider = Provider(answer)
    provider._GetMatchTasks = lambda setId, progress_callback, cancel_event: {}
    assert Strict(provider.GetMatch, 7)["id"] == 7

    # The set couldn't be asked for
    provider = Provider(lambda operation, variables: TransientError("no network"))
    provider._GetMatchTasks = lambda setId, progress_callback, cancel_event: {}
    Raises(lambda: Strict(provider.GetMatch, 7), KIND_TRANSIENT)
    # The old way: a set with nothing in it, which the scoreboard ignores
    assert not (provider.GetMatch(7) or {}).get("id")


if __name__ == "__main__":
    for test in [
        TestClientErrors,
        TestRaisingOrNot,
        TestRateLimiter,
        TestClientsShareTheLimiter,
        TestStreamQueue,
        TestStandings,
        TestSetList,
        TestEntrants,
        TestOtherMethods,
        TestGetMatch,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All provider error checks passed")
