# Checks StartGGClient, which sends every start.gg request: retrying rate
# limits and server errors with backoff (or as long as Retry-After says),
# not retrying what would fail again, retrying dropped connections but not
# timeouts, and paging. With a stand-in session: no network, no waiting.
# Run from the repository root: python test/test_startgg_client.py
import json
import os
import sys
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

from src.TournamentDataProvider.StartGGClient import GQL_URL, ReadQuery, StartGGClient

QUERY = {"operationName": "Q", "variables": {}, "query": "{ a }"}


class Response:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self.text = json.dumps(body if body is not None else {"data": {"status": status}})
        self.headers = headers or {}


class Session:
    """Answers each request with the next of answers (a Response, or an
    exception to raise), and records them"""

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


def TestAnswer():
    client, session, slept = Client(Response(200, {"data": {"a": 1}}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {"data": {"a": 1}}
    method, url, kwargs = session.requests[0]
    assert (method, url) == ("POST", GQL_URL)
    assert kwargs["json"] == QUERY and kwargs["timeout"] == 20.0
    assert kwargs["headers"]["client-version"] == "20"
    assert slept == []

    # GET, with its own timeout
    client, session, _ = Client(Response(200))
    client.Request("https://x", requests.get, params={"p": 1}, timeout=3)
    assert session.requests[0][0] == "GET" and session.requests[0][2]["timeout"] == 3


def TestRetries():
    # Rate limiting and server errors: retried with backoff
    client, session, slept = Client(Response(429), Response(503), Response(200, {"data": 1}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {"data": 1}
    assert len(session.requests) == 3 and slept == [0.5, 1.0], slept

    # Retry-After wins, up to twice the longest backoff
    client, _, slept = Client(
        Response(429, headers={"Retry-After": "3"}),
        Response(429, headers={"Retry-After": "60"}),
        Response(429, headers={"Retry-After": "soon"}),
        Response(200),
    )
    client.Request(GQL_URL, requests.post, jsonParams=QUERY)
    assert slept == [3.0, 16.0, 2.0], slept

    # The backoff stops growing
    client, _, slept = Client(*[Response(500)] * 6)
    client.Request(GQL_URL, requests.post, jsonParams=QUERY)
    assert slept == [0.5, 1.0, 2.0, 4.0, 8.0], slept


def TestNoRetries():
    # What fails the same way every time: one request
    client, session, slept = Client(Response(400, {"errors": ["bad"]}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {"errors": ["bad"]}
    assert len(session.requests) == 1 and slept == []

    # Out of retries: the last answer
    client, session, _ = Client(Response(502), Response(502, {"data": "last"}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY, retries=1) == {"data": "last"}
    assert len(session.requests) == 2

    # GraphQL errors come back as a 200, and aren't retried
    client, session, _ = Client(Response(200, {"errors": [{"message": "complexity"}]}))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY)["errors"]
    assert len(session.requests) == 1


def TestConnections():
    # A dropped connection is tried again
    client, session, slept = Client(requests.exceptions.ConnectionError("reset"), Response(200))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {"data": {"status": 200}}
    assert len(session.requests) == 2 and slept == [0.5]

    # A timeout already waited long enough: {}
    client, session, slept = Client(requests.exceptions.ConnectTimeout("slow"), Response(200))
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {}
    assert len(session.requests) == 1 and slept == []

    # Dropped every time: {}
    client, session, _ = Client(*[requests.exceptions.ConnectionError("reset")] * 3)
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY, retries=2) == {}
    assert len(session.requests) == 3

    # Not JSON: {}
    client, _, _ = Client(Response(200))
    client.session.answers[0].text = "<html>"
    assert client.Request(GQL_URL, requests.post, jsonParams=QUERY) == {}


def TestPaging():
    asked = []

    def page(n):
        asked.append(n)
        return {"data": {"page": n, "info": {"total": 4}}}

    pages = StartGGClient.FetchAllPages(page, "data.info.total")
    assert [p["data"]["page"] for p in pages] == [1, 2, 3, 4] and sorted(asked) == [1, 2, 3, 4]

    class Cancelled:
        def is_set(self):
            return True

    asked.clear()
    pages = StartGGClient.FetchAllPages(page, "data.info.total", Cancelled())
    assert asked == [1] and len(pages) == 1


def TestQueries():
    assert "query" in ReadQuery("TournamentData")


if __name__ == "__main__":
    for test in [TestAnswer, TestRetries, TestNoRetries, TestConnections, TestPaging, TestQueries]:
        test()
        print(f"{test.__name__}: OK")
    print("All start.gg client checks passed")
