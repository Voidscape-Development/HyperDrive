# Checks StartGGDataProvider with answers missing parts: start.gg sends null
# for objects it doesn't have (a deleted event, a set without a station, an
# entrant without a user...). A placement, set or player with a null in it
# is left out or filled in with blanks, without losing the rest of the list.
# Run from the repository root: python test/test_startgg_nulls.py
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
import startgg_harness as H

from src.TournamentDataProvider import StartGGConvert
from src.TournamentDataProvider.StartGGClient import StartGGClient

EVENT = "https://www.start.gg/tournament/test/event/singles"


def Provider(answers):
    """A provider answering each operation with answers[operationName]"""
    provider = H.NewProvider(EVENT, H.SetUpApp())

    def query(url=None, type=None, headers=None, jsonParams=None, params=None, **kwargs):
        return json.loads(json.dumps(answers.get((jsonParams or {}).get("operationName"), {})))

    provider.QueryRequests = query
    return provider


def Participant(tag, id):
    return {"id": id, "player": {"id": id, "gamerTag": tag, "prefix": None}, "user": None}


# =====================================================
# TOURNAMENT HISTORY
# =====================================================
def TestHistory():
    good = {
        "placement": 3,
        "entrant": {
            "initialSeedNum": 5,
            "event": {
                "name": "Singles",
                "numEntrants": 64,
                "startAt": 1700000000,
                "phases": [None, {"bracketType": "DOUBLE_ELIMINATION"}],
                "tournament": {"name": "Weekly", "images": None},
            },
        },
    }
    answers = {
        "TournamentHistoryDataQuery": {
            "data": {
                "player": {
                    "recentStandings": [
                        None,
                        # The event start.gg didn't send
                        {"placement": 1, "entrant": {"initialSeedNum": 1, "event": None}},
                        {"placement": 2, "entrant": None},
                        good,
                        # An event without its tournament
                        {
                            "placement": 9,
                            "entrant": {"event": {"name": "Side", "tournament": None}},
                        },
                    ]
                }
            }
        }
    }
    history = H.WithCallback(
        Provider(answers).GetPlayerHistoryStandings, playerID=1, playerNumber=1, gameType=1386
    )["history_sets"]
    assert [h["placement"] for h in history] == [3, 9], history
    assert history[0]["tournament_name"] == "Weekly" and history[0]["tournament_picture"] is None
    assert history[1]["tournament_name"] is None and history[1]["event_name"] == "Side"

    # No standings at all
    answers = {"TournamentHistoryDataQuery": {"data": {"player": {"recentStandings": None}}}}
    history = H.WithCallback(
        Provider(answers).GetPlayerHistoryStandings, playerID=1, playerNumber=1, gameType=1386
    )
    assert history == {"playerNumber": 1, "history_sets": []}


# =====================================================
# SETS
# =====================================================
def TestSet():
    provider = Provider({})
    s = provider.ParseMatchDataNewApi(
        {
            "id": 1,
            "phaseGroup": {"phase": {"name": None, "groupCount": None}},
            "stream": {"streamName": None, "streamSource": "TWITCH"},
            "station": None,
            "slots": [
                None,
                {
                    "entrant": {
                        "id": 7,
                        "name": "Pell",
                        "participants": [None, {"player": None, "user": None}],
                        "standing": {"setRecordWithoutByes": None},
                    }
                },
            ],
        }
    )
    assert s["id"] == 1 and s["p1_name"] == "" and s["p2_name"] == "Pell", s
    assert s["station"] == "" and s["stream"] is None
    assert s["entrants"][0] == [] and len(s["entrants"][1]) == 1
    assert s["entrants"][1][0]["id"] == [None, 0]

    # Pools without a phase name
    s = provider.ParseMatchDataNewApi(
        {"id": 2, "phaseGroup": {"displayIdentifier": "A1", "phase": {"groupCount": 4}}}
    )
    assert s["isPools"] and s["tournament_phase"].endswith("A1"), s

    # A set start.gg didn't send isn't a set
    assert Provider({"SetQuery": {"data": {"set": None}}})._GetMatchNewApi(1, None, None) == {}


def TestFutureSet():
    s = Provider({}).ProcessFutureSet(
        {
            "id": 3,
            "fullRoundText": None,
            "totalGames": None,
            "phaseGroup": {"phase": {"name": None, "groupCount": 2}, "displayIdentifier": "B"},
            "slots": [
                None,
                {
                    "entrant": {
                        "name": "Rook",
                        "participants": [
                            None,
                            {
                                "player": {"gamerTag": None},
                                "user": {"location": {"country": "Japan", "state": "XX"}},
                            },
                        ],
                    }
                },
            ],
        },
        "tournament/test/event/singles",
    )
    assert s["best_of"] == 0 and s["match"] == "" and s["phase"].endswith("B"), s
    assert list(s["team"]) == ["2"] and s["team"]["2"]["player"]["1"]["name"] == ""
    # A state the country doesn't have
    assert s["team"]["2"]["player"]["1"]["state"] == {}


def TestLists():
    nodes = [
        None,
        # No participants: the set's still listed, without player names
        {
            "winnerId": 1,
            "slots": [{"entrant": {"id": 1, "participants": []}}, None],
            "games": [None, {"selections": [None]}],
        },
        {
            "winnerId": 2,
            "slots": [
                {"entrant": {"id": 1, "participants": [Participant("Ash", 10)]}},
                {"entrant": {"id": 2, "participants": None}},
            ],
            "games": None,
        },
    ]
    answers = {
        "PlayerLastSetsQuery": {"data": {"event": {"sets": {"nodes": nodes}}}},
        "CompletedSetsQuery": {"data": {"event": {"sets": {"nodes": nodes}}}},
    }
    provider = Provider(answers)
    last = H.WithCallback(provider.GetLastSets, playerID=10, playerNumber=1)["last_sets"]
    assert len(last) == 2, last
    assert len(provider.GetCompletedSets(None, None)) == 2

    # Stream queues with a null stream or set
    queue = {
        "data": {
            "event": {
                "slug": "tournament/test/event/singles",
                "id": 1,
                "tournament": {
                    "streamQueue": [
                        None,
                        {"stream": None, "sets": [None, {"id": 5, "slots": None}]},
                        {"stream": {"streamName": "main"}, "sets": None},
                    ]
                },
            }
        }
    }
    provider = Provider({"StreamQueueQuery": queue, "StreamSetsQuery": queue})
    queues = provider.GetStreamQueue()
    assert list(queues) == ["", "main"] and list(queues[""]) == ["1"], queues
    assert provider.GetStreamMatchId("main") is None
    assert provider.GetStreamMatchId(None) is None

    # Stations
    stations = {"data": {"event": {"sets": {"nodes": [None, {"id": 8, "station": {"id": 4}}]}}}}
    provider = Provider({"StationSetsQuery": stations})
    assert provider.GetStationMatchId(4) == {"id": 8, "station": {"id": 4}}
    assert Provider({}).GetStationMatchId(4) is None

    # Entrants
    entrants = {
        "data": {
            "event": {
                "entrants": {
                    "pageInfo": {"totalPages": None},
                    "nodes": [
                        None,
                        {"initialSeedNum": 1, "participants": [None, Participant("Ash", 10)]},
                    ],
                }
            }
        }
    }
    players = Provider({"EventEntrantsListQuery": entrants}).FetchEntrants()
    assert [p["gamerTag"] for p in players] == ["Ash"], players


def TestEntrantData():
    assert StartGGConvert.ProcessEntrantData(None)["id"] == [None, 0]
    data = StartGGConvert.ProcessEntrantData(
        {"player": None, "user": {"id": 3, "images": None, "location": None}}
    )
    assert data["id"] == [None, 3] and "avatar" not in data
    data = StartGGConvert.ProcessEntrantData(
        {"player": {"id": 4, "sets": {"nodes": [None, {"games": [{"selections": [None]}]}]}}}
    )
    assert data["id"] == [4, 0]


def TestOldApi():
    games = H.SetUpApp().games
    result = StartGGConvert.ParseMatchDataOldApi(
        {
            "entities": {
                "sets": {"entrant1Id": 1, "entrant2Id": 2, "isGF": True, "fullRoundText": None},
                "setTask": [
                    None,
                    {"action": "report", "metadata": None},
                    # A character the game's assets don't have
                    {"action": "setup_character", "metadata": {"charSelections": {"1": [999999]}}},
                ],
            }
        },
        games,
    )
    assert result["entrants"] == [[], []] and result["team2losers"], result
    assert StartGGConvert.ParseMatchDataOldApi({"entities": None}, games)["entrants"] == [[], []]


# =====================================================
# CLIENT
# =====================================================
class Answer:
    status_code = 200
    headers = {}

    def __init__(self, text):
        self.text = text


class Session:
    def __init__(self, text):
        self.text = text

    def request(self, method, url, **kwargs):
        return Answer(self.text)


def TestClient():
    # Anything but a JSON object counts as a failed request
    for text in ("null", "[1, 2]", '"text"'):
        client = StartGGClient(session=Session(text), sleep=lambda s: None)
        assert client.Request("https://www.start.gg/api/-/gql", type=requests.post) == {}
    # A JSON object is the answer
    client = StartGGClient(session=Session('{"data": {}}'), sleep=lambda s: None)
    assert client.Request("https://www.start.gg/api/-/gql", type=requests.post) == {"data": {}}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print("All start.gg null checks passed")
