"""Talks to start.gg's API: one HTTPS session kept alive for every request,
one rate limiter every request goes through, retries while start.gg is rate
limiting or having server trouble, typed errors when a request fails
(ProviderErrors.py), fetching the pages of a paged query in parallel, and
the queries (StartGG<name>Query.txt). StartGGDataProvider turns what it
answers into HyperDrive's data."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import DefaultCookiePolicy

import orjson
import requests
import requests.adapters
from loguru import logger

from ..Helpers.DictHelper import deep_get
from ..Helpers.DirHelper import ResolvePath
from .ProviderErrors import FromHttpStatus, ProviderError, TransientError

# start.gg's site API. Not the official one (api.start.gg/gql/alpha, which
# StartGGReporter uses to report sets): several of the queries here ask for
# fields the official API's schema doesn't have.
GQL_URL = "https://www.start.gg/api/-/gql"

# What every request is sent with
HEADERS = {
    "client-version": "20",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

_SESSION_METHODS = {requests.get: "GET", requests.post: "POST"}


def CreateSession():
    # Shared by every start.gg request so the HTTPS connection is kept alive,
    # instead of a new TCP + TLS handshake for every query.
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    # Like the plain requests.get/post calls this replaced, don't keep cookies
    session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
    return session


_session = CreateSession()


# =====================================================
# QUERIES
# =====================================================
QUERY_DIR = ResolvePath("src/TournamentDataProvider")


def ReadQuery(name):
    """The text of StartGG<name>Query.txt"""
    with open(f"{QUERY_DIR}/StartGG{name}Query.txt") as f:
        return f.read()


# =====================================================
# RATE LIMITING
# =====================================================
class RateLimiter:
    """What every start.gg request waits on before it's sent, whichever
    thread or thread pool sends it: a token bucket (`rate` requests every
    `per` seconds, `burst` at once after a quiet while), and a time before
    which nothing is sent, set when start.gg answers 429 so every caller
    backs off, not just the one that got it.

    Background requests (pre-fetching players' mains) are paced further:
    one every `backgroundInterval` seconds, and only while `reserve`
    requests are left for what the user is waiting for."""

    # start.gg allows 80 requests a minute
    RATE = 80
    PER_SECS = 60.0
    BURST = 60
    # Half the budget at most for background requests
    BACKGROUND_INTERVAL_SECS = 1.5
    RESERVE = 20

    def __init__(
        self,
        rate=RATE,
        per=PER_SECS,
        burst=BURST,
        clock=time.monotonic,
        sleep=time.sleep,
        backgroundInterval=BACKGROUND_INTERVAL_SECS,
        reserve=RESERVE,
    ):
        self.interval = per / rate
        self.burst = max(1, burst)
        self.clock = clock
        self.sleep = sleep
        self.backgroundInterval = backgroundInterval
        self.reserve = max(0, min(reserve, self.burst - 1))
        self.lock = threading.Lock()
        # When the bucket is full again (a token comes back every interval)
        self.fullAt = clock()
        self.blockedUntil = 0.0
        self.nextBackgroundAt = 0.0
        self._local = threading.local()

    def Acquire(self, background=None):
        """Waits until a request may be sent, and counts it. Requests are
        let through in the order they asked."""
        if background is None:
            background = getattr(self._local, "background", False)
        with self.lock:
            now = self.clock()
            # A request may go when the bucket, emptied by `burst` requests,
            # has a token back; background ones leave `reserve` in it
            keep = self.reserve if background else 0
            at = max(now, self.fullAt - (self.burst - 1 - keep) * self.interval, self.blockedUntil)
            if background:
                at = max(at, self.nextBackgroundAt)
                self.nextBackgroundAt = at + self.backgroundInterval
            self.fullAt = max(self.fullAt, at) + self.interval
        wait = at - now
        if wait > 0:
            self.sleep(wait)
            # start.gg said to back off while this one waited
            with self.lock:
                more = self.blockedUntil - at
            if more > 0:
                self.sleep(more)
        return max(0.0, wait)

    def BackOff(self, seconds):
        """start.gg is rate limiting: nothing is sent for `seconds`, by
        anyone"""
        with self.lock:
            self.blockedUntil = max(self.blockedUntil, self.clock() + max(0.0, seconds))

    def Background(self):
        """with limiter.Background(): the requests this thread sends inside
        are background ones"""
        return _Background(self._local)


class _Background:
    def __init__(self, local):
        self.local = local

    def __enter__(self):
        self.before = getattr(self.local, "background", False)
        self.local.background = True
        return self

    def __exit__(self, *args):
        self.local.background = self.before
        return False


class _SleptClock:
    """Time that only passes when slept, for a client given its own sleep
    (tests): its waits are then exactly the ones asked for"""

    def __init__(self, sleep):
        self._sleep = sleep
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self._sleep(seconds)
        self.now += seconds


# Shared by every client: start.gg counts the requests of the whole app
_limiter = RateLimiter()


class StartGGClient:
    # Status codes worth trying again: rate limiting and server-side errors.
    # Anything else (bad query, auth, not found) fails the same way every time.
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_RETRY_DELAY_SECS = 8.0
    # start.gg answers a query it refuses (the complexity cap, a field it
    # doesn't know) with these and its "errors": an answer, for the caller
    GRAPHQL_ERROR_STATUS_CODES = {400, 422}

    def __init__(self, timeoutSecs=20.0, session=None, sleep=time.sleep, limiter=None):
        self.timeoutSecs = timeoutSecs
        # The shared session, or another one (tests)
        self.session = session or _session
        self.sleep = sleep
        if limiter is None:
            if session is None and sleep is time.sleep:
                limiter = _limiter
            else:
                # Its own budget, on its own time
                clock = _SleptClock(sleep)
                self.sleep = clock.sleep
                limiter = RateLimiter(clock=clock, sleep=clock.sleep)
        self.limiter = limiter

    # =====================================================
    # REQUESTS
    # =====================================================
    def Query(
        self,
        url=None,
        type=None,
        headers=None,
        jsonParams=None,
        params=None,
        retries=5,
        timeout=None,
    ):
        """Sends a request (type: requests.get or requests.post, or a
        function sending it) and returns its JSON, a dict. Waits for the
        rate limiter first, and retries (with backoff) while start.gg is
        rate limiting or having server trouble.

        Raises a ProviderError when it failed: the network, a status that
        isn't a success, or an answer that isn't a JSON object. A query
        start.gg refused comes back with its "errors", like any answer."""
        name = (jsonParams or {}).get("operationName", url)
        headers = dict(headers or {})
        headers.update(HEADERS)
        method = _SESSION_METHODS.get(type)
        send = (
            (lambda url, **kwargs: self.session.request(method, url, **kwargs)) if method else type
        )

        data = None
        for attempt in range(retries + 1):
            lastAttempt = attempt == retries
            self.limiter.Acquire()
            try:
                data = send(
                    url,
                    timeout=timeout or self.timeoutSecs,
                    headers=headers,
                    json=jsonParams,
                    params=params,
                )
            except requests.exceptions.ConnectionError as e:
                # Dropped/refused connections are usually transient.
                # Timeouts aren't retried: each one already waited a while.
                if lastAttempt or isinstance(e, requests.exceptions.Timeout):
                    raise TransientError(f"start.gg {name}: {e.__class__.__name__}: {e}") from e
                self.sleep(min(0.5 * 2**attempt, self.MAX_RETRY_DELAY_SECS))
                continue
            except Exception as e:
                # `type` is the request-method parameter here, not the builtin
                raise TransientError(f"start.gg {name}: {e.__class__.__name__}: {e}") from e

            if (
                data.status_code == 200
                or data.status_code not in self.RETRY_STATUS_CODES
                or lastAttempt
            ):
                break

            delay = min(0.5 * 2**attempt, self.MAX_RETRY_DELAY_SECS)
            delay = self._RetryAfter(data, delay)
            logger.warning(f"start.gg {name} returned {data.status_code}, retrying in {delay}s")
            if data.status_code == 429:
                # Everyone waits, this request included (at its next Acquire)
                self.limiter.BackOff(delay)
            else:
                self.sleep(delay)

        status = data.status_code
        if status != 200:
            logger.warning(f"start.gg {name} returned {status}")
        if status == 429:
            # Out of retries: the others still shouldn't pile on
            self.limiter.BackOff(self._RetryAfter(data, self.MAX_RETRY_DELAY_SECS))

        try:
            body = orjson.loads(data.text)
        except Exception as e:
            if status != 200:
                raise FromHttpStatus(status, f"start.gg {name} returned {status}") from e
            raise TransientError(f"start.gg {name} didn't return JSON") from e

        # Callers read it as a dict: a null or a list (an error page, a
        # proxy) counts as a failed request
        if not isinstance(body, dict):
            logger.warning(f"start.gg {name} returned {body.__class__.__name__}")
            if status != 200:
                raise FromHttpStatus(status, f"start.gg {name} returned {status}")
            raise TransientError(f"start.gg {name} returned {body.__class__.__name__}")

        if status != 200 and not (status in self.GRAPHQL_ERROR_STATUS_CODES and body.get("errors")):
            retryAfter = None
            if status == 429:
                retryAfter = self._RetryAfter(data, None)
            message = body.get("message") or body.get("errors") or ""
            raise FromHttpStatus(
                status, f"start.gg {name} returned {status} {message}".strip(), body, retryAfter
            )

        # GraphQL errors (e.g. the complexity cap) come back as a 200,
        # so they'd otherwise look like an empty result
        if body.get("errors"):
            logger.warning(f"start.gg {name} returned errors: {body.get('errors')}")
        return body

    def _RetryAfter(self, response, default):
        """The seconds start.gg's Retry-After says to wait, up to twice the
        longest backoff, else default"""
        retryAfter = (getattr(response, "headers", None) or {}).get("Retry-After")
        if retryAfter:
            try:
                return min(float(retryAfter), self.MAX_RETRY_DELAY_SECS * 2)
            except ValueError:
                pass
        return default

    def Request(
        self,
        url=None,
        type=None,
        headers=None,
        jsonParams=None,
        params=None,
        retries=5,
        timeout=None,
    ):
        """Query(), for the callers that don't tell a failed request from an
        empty answer: what start.gg answered if it's a JSON object (whatever
        its status), else {}."""
        try:
            return self.Query(url, type, headers, jsonParams, params, retries, timeout)
        except ProviderError as e:
            logger.error(f"{e.__class__.__name__}: {e}")
            return e.response if isinstance(e.response, dict) else {}
        except Exception as e:
            logger.error(f"{e.__class__.__name__}: {e}")
            return {}

    @staticmethod
    def FetchAllPages(fetchPage, totalPagesPath, cancel_event=None):
        """[fetchPage(1), fetchPage(2)...]. Page 1 tells us how many pages
        there are (at totalPagesPath); the rest are fetched in parallel
        instead of one after another. Results stay in page order. A page
        that raises fails them all: fetchPage decides whether a failed
        request does (Query) or comes back empty (Request)."""
        first = fetchPage(1)
        pages = [first]
        totalPages = deep_get(first, totalPagesPath, 1) or 1

        if totalPages > 1 and (cancel_event is None or not cancel_event.is_set()):
            # A few at a time. How many are sent a minute is the rate
            # limiter's business, which every request goes through.
            with ThreadPoolExecutor(max_workers=4) as executor:
                pages.extend(executor.map(fetchPage, range(2, totalPages + 1)))

        return pages
