"""Talks to start.gg's API: one HTTPS session kept alive for every request,
retries while start.gg is rate limiting or having server trouble, fetching
the pages of a paged query in parallel, and the queries
(StartGG<name>Query.txt). StartGGDataProvider turns what it answers into
HyperDrive's data."""

import time
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import DefaultCookiePolicy

import orjson
import requests
import requests.adapters
from loguru import logger

from ..Helpers.DictHelper import deep_get
from ..Helpers.DirHelper import ResolvePath

GQL_URL = "https://www.start.gg/api/-/gql"

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


class StartGGClient:
    # Status codes worth trying again: rate limiting and server-side errors.
    # Anything else (bad query, auth, not found) fails the same way every time.
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_RETRY_DELAY_SECS = 8.0

    def __init__(self, timeoutSecs=20.0, session=None, sleep=time.sleep):
        self.timeoutSecs = timeoutSecs
        # The shared session, or another one (tests)
        self.session = session or _session
        self.sleep = sleep

    # =====================================================
    # REQUESTS
    # =====================================================
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
        """Sends a request (type: requests.get or requests.post, or a
        function sending it) and returns its JSON, retrying (with backoff)
        while start.gg is rate limiting or having server trouble. {} when it
        failed."""
        try:
            data = None
            headers = dict(headers or {})
            headers.update(
                {
                    "client-version": "20",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                }
            )
            method = _SESSION_METHODS.get(type)
            send = (
                (lambda url, **kwargs: self.session.request(method, url, **kwargs))
                if method
                else type
            )
            for attempt in range(retries + 1):
                lastAttempt = attempt == retries
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
                        raise
                    self.sleep(min(0.5 * 2**attempt, self.MAX_RETRY_DELAY_SECS))
                    continue

                if (
                    data.status_code == 200
                    or data.status_code not in self.RETRY_STATUS_CODES
                    or lastAttempt
                ):
                    break

                delay = min(0.5 * 2**attempt, self.MAX_RETRY_DELAY_SECS)
                retryAfter = data.headers.get("Retry-After")
                if retryAfter:
                    try:
                        delay = min(float(retryAfter), self.MAX_RETRY_DELAY_SECS * 2)
                    except ValueError:
                        pass
                logger.warning(
                    f"start.gg {(jsonParams or {}).get('operationName', url)} returned {data.status_code}, retrying in {delay}s"
                )
                self.sleep(delay)

            if data.status_code != 200:
                logger.warning(
                    f"start.gg {(jsonParams or {}).get('operationName', url)} returned {data.status_code}"
                )
            data = orjson.loads(data.text)
            # Callers read it as a dict: a null or a list (an error page,
            # a proxy) counts as a failed request
            if not isinstance(data, dict):
                logger.warning(
                    f"start.gg {(jsonParams or {}).get('operationName', url)} returned {data.__class__.__name__}"
                )
                return {}
            # GraphQL errors (e.g. the complexity cap) come back as a 200,
            # so they'd otherwise look like an empty result
            if isinstance(data, dict) and data.get("errors"):
                logger.warning(
                    f"start.gg {(jsonParams or {}).get('operationName', url)} returned errors: {data.get('errors')}"
                )
            return data
        except Exception as e:
            # `type` is the request-method parameter here, not the builtin
            logger.error(f"{e.__class__.__name__}: {e}")
            return {}

    @staticmethod
    def FetchAllPages(fetchPage, totalPagesPath, cancel_event=None):
        """[fetchPage(1), fetchPage(2)...]. Page 1 tells us how many pages
        there are (at totalPagesPath); the rest are fetched in parallel
        instead of one after another. Results stay in page order."""
        first = fetchPage(1)
        pages = [first]
        totalPages = deep_get(first, totalPagesPath, 1) or 1

        if totalPages > 1 and (cancel_event is None or not cancel_event.is_set()):
            # Keep the worker count low so start.gg doesn't start rate limiting us
            with ThreadPoolExecutor(max_workers=4) as executor:
                pages.extend(executor.map(fetchPage, range(2, totalPages + 1)))

        return pages
