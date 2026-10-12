"""Sample stream_queue for the layout previews, built with the same code
HyperDrive uses (src/SetDurations.py, src/StreamQueue.py) from made up sets
between the sample players. Used by gen_sample_state.py."""

from src.SetDurations import Durations
from src.StreamQueue import StreamQueueModel

# 18:00 on a Friday, UTC
START = 1781892000


def _Sets(players):
    """The event's completed sets, as the provider's GetSetDurations gives
    them: every pair of neighbouring seeds plays a best of 3."""
    count = len(players)
    pairs = count // 2 + len(range(1, count, 2)) + len(range(1, count - 1, 3))
    return [
        {
            "id": n + 1,
            "startedAt": START + n * 600,
            "completedAt": START + n * 600 + (14 + n % 6) * 60,
            "totalGames": 3,
            "dq": False,
        }
        for n in range(pairs)
    ]


STREAMS = {
    # Stream name: (scoreboard showing it, [(round, phase, seed 1, seed 2, best of)])
    "hyperdrive_tv": (
        1,
        [
            ("Winners Semi-Final", "Top 24", 1, 4, 5),
            ("Winners Semi-Final", "Top 24", 2, 3, 5),
            ("Losers Round 3", "Top 24", 6, 9, 3),
            ("Losers Round 3", "Top 24", 5, 10, 3),
        ],
    ),
    "hyperdrive_tv2": (
        None,
        [
            ("Losers Round 2", "Top 24", 11, 14, 3),
            ("Losers Round 2", "Top 24", 12, 13, 3),
            ("Losers Round 2", "Top 24", 15, 8, 3),
        ],
    ),
}


def _QueueTeam(players, index, location):
    p = players[index - 1]
    country, state = location(p)
    tag = p["gamerTag"]
    team = p.get("prefix") or ""
    return {
        "teamName": f"{team} | {tag}" if team else tag,
        "losers": False,
        "seed": index,
        "player": {
            "1": {
                "country": country or {},
                "state": state or {},
                "name": tag,
                "team": team,
                "mergedName": f"{team}|{tag}" if team else tag,
                "pronoun": p.get("pronoun") or "",
                "real_name": p.get("name") or "",
                "online_avatar": "",
                "twitter": p.get("twitter") or "",
                "socials": {},
            }
        },
    }


def StreamQueues(players, location):
    """start.gg's stream queues: {stream name: [set]}, as the provider gives
    them. location(player) gives the sample player's (country, state)."""
    queues = {}
    setId = 1000
    for name, (_, sets) in STREAMS.items():
        queue = []
        for roundName, phase, a, b, bestOf in sets:
            setId += 1
            queue.append(
                {
                    "id": setId,
                    "match": roundName,
                    "phase": phase,
                    "best_of": bestOf,
                    "best_of_text": f"Best of {bestOf}",
                    "state": 1,
                    "started_at": None,
                    "station": -1,
                    "event": "tournament/hyperdrive-invitational-42/event/ultimate-singles",
                    "isCurrentEvent": True,
                    "team": {
                        "1": _QueueTeam(players, a, location),
                        "2": _QueueTeam(players, b, location),
                    },
                }
            )
        queues[name] = queue
    return queues


def SetDurations(players):
    """How long the sample sets took, for when the queued sets should start"""
    return Durations(_Sets(players))


def LoadStreamQueue(model, players, location):
    """Fills a StreamQueueModel with the sample queues, each stream linked to
    its scoreboard."""
    model.SetProviderQueues(StreamQueues(players, location))
    for name, (scoreboard, _) in STREAMS.items():
        model.GetStream(name).scoreboard = scoreboard


def StreamQueue(players, location, now):
    """What the Stream Queue widget sends."""
    model = StreamQueueModel()
    LoadStreamQueue(model, players, location)
    model.lastUpdated = now
    return model.Export(durations=SetDurations(players), now=now)
