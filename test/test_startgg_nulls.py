# Checks StartGGDataProvider with answers missing parts: start.gg sends null
# for objects it doesn't have (a deleted event, a set without a station, an
# entrant without a user...). A placement, set or player with a null in it
# is left out or filled in with blanks, without losing the rest of the list.
# Also how head-to-head sets are paged and filtered.
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
    assert s["station"] == "" and s["stream"] == "" and s["stream_name"] == ""
    assert s["entrants"][0] == [] and len(s["entrants"][1]) == 1
    assert s["entrants"][1][0]["id"] == [None, 0]

    # Pools without a phase name
    s = provider.ParseMatchDataNewApi(
        {"id": 2, "phaseGroup": {"displayIdentifier": "A1", "phase": {"groupCount": 4}}}
    )
    assert s["isPools"] and s["tournament_phase"].endswith("A1"), s

    # A set start.gg didn't send isn't a set
    assert Provider({"SetQuery": {"data": {"set": None}}})._GetMatchNewApi(1, None, None) == {}


def TestStreams():
    parse = H.StartGGDataProvider.ParseStream
    assert parse(None) == parse({}) == ("", "")
    assert parse({"streamName": "mainstage", "streamSource": "TWITCH"}) == (
        "https://twitch.tv/mainstage",
        "mainstage",
    )
    # YouTube: the channel's name, with its id in streamId
    channel = "UCiHOK00jVASaoM7WPgi-hyg"
    assert parse({"streamName": "Smash Club", "streamSource": "YOUTUBE", "streamId": channel}) == (
        "https://youtube.com/channel/" + channel,
        "Smash Club",
    )
    # Or the id as its name, with a name in shortName, if any
    stream = {"streamName": channel, "streamSource": "YOUTUBE", "streamId": "71418924"}
    assert parse(dict(stream, shortName="GQ Youtube")) == (
        "https://youtube.com/channel/" + channel,
        "GQ Youtube",
    )
    assert parse(dict(stream, shortName=None))[1] == channel
    # A name without an id
    assert parse({"streamName": "Club", "streamSource": "YOUTUBE"}) == (
        "https://youtube.com/Club",
        "Club",
    )
    assert parse({"streamName": "https://x.tv/a", "streamSource": "OTHER"})[0] == "https://x.tv/a"

    s = Provider({}).ParseMatchDataNewApi(
        {"id": 4, "stream": dict(stream, shortName="GQ Youtube"), "slots": []}
    )
    assert s["stream_name"] == "GQ Youtube" and s["stream"].endswith(channel), s


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


# =====================================================
# HEAD TO HEAD
# =====================================================
def H2HSet(id, startAt, game=H.ULTIMATE_ID, players=("1", "2"), scores=(2, 1)):
    return {
        "id": id,
        "slots": [
            {"entrant": {"id": f"e{p}", "participants": [{"player": {"id": p}}]}} for p in players
        ],
        "games": None,
        "entrant1Score": scores[0],
        "entrant2Score": scores[1],
        "winnerId": f"e{players[0]}",
        "fullRoundText": "Winners Final",
        "phaseGroup": None,
        "event": {
            "id": startAt,
            "name": "Singles",
            "isOnline": False,
            "startAt": startAt,
            "videogame": {"id": game},
            "tournament": {"name": "Weekly"},
        },
    }


def TestHeadToHead():
    # Most recent first, the way start.gg sends them
    sets = [H2HSet(i, 1000 - i) for i in range(30)]
    sets[3] = H2HSet(3, 997, game=1)  # Another game
    sets[4] = H2HSet(4, 996, players=("1", "3"))  # Not between the two
    sets[5] = H2HSet(5, 995, scores=(-1, 0))  # A DQ
    sets[6] = None
    asked = []

    provider = H.NewProvider(EVENT, H.SetUpApp())

    def query(url=None, type=None, headers=None, jsonParams=None, params=None, **kwargs):
        v = jsonParams["variables"]
        assert jsonParams["operationName"] == "HeadToHeadQuery"
        assert (v["pid1"], v["pid2"]) == ("1", "2")
        asked.append((v["page"], v["perPage"]))
        # Pages of 20 go over the complexity cap
        if v["perPage"] > 10:
            return {"errors": [{"message": "Your query complexity is too high."}]}
        start = (v["page"] - 1) * v["perPage"]
        page = sets[start : start + v["perPage"]]
        totalPages = -(-len(sets) // v["perPage"])
        return {
            "data": {"player": {"sets": {"pageInfo": {"totalPages": totalPages}, "nodes": page}}}
        }

    provider.QueryRequests = query
    callback = H.Callback()
    provider.GetRecentSets(["1", "u1"], ["2", "u2"], H.ULTIMATE_ID, callback, 7, None, None)

    assert callback.value["request_time"] == 7
    ids = [s["id"] for s in callback.value["sets"]]
    assert ids == [i for i in range(30) if i not in (3, 4, 5, 6)], ids
    # Refused pages of 20 are asked for again as pages of 10
    assert sorted(asked) == [(1, 10), (1, 20), (2, 10), (2, 20), (3, 10), (4, 10)], asked
    first = callback.value["sets"][0]
    assert first["winner"] == 0 and first["score"] == [2, 1] and first["tournament"] == "Weekly"

    # No more than the most recent 100 sets
    sets = [H2HSet(i, 1000 - i) for i in range(150)]
    asked.clear()
    provider.GetRecentSets(["1", "u1"], ["2", "u2"], H.ULTIMATE_ID, callback, 0, None, None)
    assert [s["id"] for s in callback.value["sets"]] == list(range(100))

    # A failed request: no sets
    provider.QueryRequests = lambda *args, **kwargs: {}
    provider.GetRecentSets(["1", "u1"], ["2", "u2"], H.ULTIMATE_ID, callback, 0, None, None)
    assert callback.value["sets"] == []


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print("All start.gg null checks passed")
