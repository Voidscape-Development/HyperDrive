# Checks StartGGDataProvider.GetStandings: placements are fetched in parallel,
# come back in placement order with their seeds, and nothing past the last
# entrant is asked for.
# Run from the repository root: python test/test_startgg_standings.py
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

from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider


def Standing(placement, total):
    return {
        "data": {
            "event": {
                "standings": {
                    "pageInfo": {"total": total},
                    "nodes": [
                        {
                            "setRecordWithoutByes": {
                                "wins": placement,
                                "losses": 1,
                                "winPercentage": 50,
                            },
                            "entrant": {
                                "name": f"Entrant {placement}",
                                "initialSeedNum": placement + 10,
                                "participants": [
                                    {"player": {"id": placement, "gamerTag": f"P{placement}"}}
                                ],
                                "paginatedSets": {"nodes": []},
                            },
                        }
                    ],
                }
            }
        }
    }


def Provider(total):
    provider = StartGGDataProvider.__new__(StartGGDataProvider)
    provider.url = "https://www.start.gg/tournament/t/event/e"
    provider.asked = []
    lock = threading.Lock()

    def query(url, type=None, jsonParams=None, **kwargs):
        placement = jsonParams["variables"]["playerNumber"]
        with lock:
            provider.asked.append(placement)
        if placement > total:
            return {"data": {"event": {"standings": {"pageInfo": {"total": total}, "nodes": []}}}}
        return Standing(placement, total)

    provider.QueryRequests = query
    return provider


def TestOrderAndProgress():
    provider = Provider(total=40)
    progress = []
    teams = provider.GetStandings(16, lambda n, t: progress.append((n, t)), None)
    assert [t["players"][0]["gamerTag"] for t in teams] == [f"P{i}" for i in range(1, 17)]
    assert [t["wins"] for t in teams] == list(range(1, 17))
    assert [t["players"][0]["seed"] for t in teams] == list(range(11, 27))
    assert sorted(provider.asked) == list(range(1, 17))
    assert progress[-1] == (16, 16) and len(progress) == 16
    print("TestOrderAndProgress: OK")


def TestStopsAtLastEntrant():
    provider = Provider(total=5)
    teams = provider.GetStandings(32, None, None)
    assert len(teams) == 5
    assert sorted(provider.asked) == [1, 2, 3, 4, 5], provider.asked
    print("TestStopsAtLastEntrant: OK")


def TestCancelled():
    provider = Provider(total=40)
    cancel = threading.Event()
    cancel.set()
    assert provider.GetStandings(16, None, cancel) == []
    print("TestCancelled: OK")


def TestErrorReturnsEmpty():
    provider = Provider(total=5)
    provider.url = "not a start.gg link"
    assert provider.GetStandings(8, None, None) == []
    print("TestErrorReturnsEmpty: OK")


TestOrderAndProgress()
TestStopsAtLastEntrant()
TestCancelled()
TestErrorReturnsEmpty()
