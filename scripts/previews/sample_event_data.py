"""Sample event_stats, schedule, league and stream_queue for the layout
previews, built with the same code HyperDrive uses (src/EventStats.py,
src/StreamQueue.py) from made up sets between the sample players. Used by
gen_sample_state.py."""

from src.EventStats import BuildEventStats, BuildSchedule, Durations, Numbered
from src.StreamQueue import StreamQueueModel

GAME = "ssbu"
STAGES = [
    "BattleFieldS",
    "Poke_Stadium2",
    "BattleField",
    "Poke_Kalos",
    "Animal_City",
    "Yoshi_Story",
]
# 18:00 on a Friday, UTC
START = 1781892000
HOUR = 3600


def _Entrant(players, index):
    p = players[index - 1]
    return {
        "id": index,
        "name": f"{p['prefix']} | {p['gamerTag']}" if p.get("prefix") else p["gamerTag"],
        "seed": index,
        "players": [{"id": index, "gamertag": p["gamerTag"], "sponsor": p.get("prefix") or ""}],
    }


def _Main(players, index):
    mains = players[index - 1]["mains"].get(GAME) or [[None]]
    return mains[0][0]


def _Sets(players):
    """Every pair of neighbouring seeds plays, the better seed winning
    but for a few upsets."""
    sets = []
    upsets = {(3, 14), (6, 11), (8, 9), (5, 12)}
    count = len(players)
    pairs = [(i, count + 1 - i) for i in range(1, count // 2 + 1)]
    pairs += [(i, i + 1) for i in range(1, count, 2)]
    pairs += [(i, i + 2) for i in range(1, count - 1, 3)]
    for n, (a, b) in enumerate(pairs):
        winner = 1 if (a, b) in upsets else 0
        games = []
        wins = [0, 0]
        g = 0
        while max(wins) < 2:
            # The set's loser takes one game in every other set
            gameWinner = winner if (n + g) % 3 or wins[1 - winner] else 1 - winner
            wins[gameWinner] += 1
            games.append(
                {
                    "winner": gameWinner,
                    "stage_id": STAGES[(n + g * 2) % len(STAGES)],
                    "stage_name": "",
                    "selections": [
                        {"slot": 0, "character_id": _Main(players, a)},
                        {"slot": 1, "character_id": _Main(players, b)},
                    ],
                }
            )
            g += 1
        sets.append(
            {
                "id": n + 1,
                "started_at": START + n * 600,
                "completed_at": START + n * 600 + (14 + n % 6) * 60,
                "total_games": 3,
                "round_name": "Winners Round 1" if n < count // 2 else "Losers Round 1",
                "phase_name": "Pools",
                "phase_id": "A1" if n % 2 else "B1",
                "bracket_type": "DOUBLE_ELIMINATION",
                "winner": winner,
                "scores": wins,
                "dq": False,
                "entrants": [_Entrant(players, a), _Entrant(players, b)],
                "games": games,
            }
        )
    return sets


def _Standings(players):
    placements = [1, 2, 3, 4, 5, 5, 7, 7, 9, 9, 9, 9, 13, 13, 13, 13]
    # Final placements, by seed: a few players far from their seed
    order = [1, 3, 2, 14, 4, 6, 11, 5, 7, 8, 9, 10, 12, 13, 15, 16]
    return {
        "bracket_type": "DOUBLE_ELIMINATION",
        "completed": False,
        "standings": [
            dict(_Entrant(players, seed), placement=placements[i], final=True)
            for i, seed in enumerate(order[: len(players)])
        ],
    }


def _Schedule():
    phases = [
        {"id": 1, "name": "Round 1 Pools", "order": 1, "state": "COMPLETED", "groupCount": 8},
        {"id": 2, "name": "Round 2 Pools", "order": 2, "state": "ACTIVE", "groupCount": 4},
        {"id": 3, "name": "Top 24", "order": 3, "state": "CREATED", "groupCount": 1},
        {"id": 4, "name": "Top 8", "order": 4, "state": "CREATED", "groupCount": 1},
    ]
    groups = []
    for i, wave in enumerate("ABCD"):
        for pool in (1, 2):
            groups.append(
                {
                    "phaseId": 1,
                    "identifier": f"{wave}{pool}",
                    "state": 3,
                    "wave": wave,
                    "waveStartAt": START + i * HOUR,
                }
            )
    for i, wave in enumerate("EF"):
        for pool in (1, 2):
            groups.append(
                {
                    "phaseId": 2,
                    "identifier": f"{wave}{pool}",
                    "state": 2 if wave == "E" else 1,
                    "wave": wave,
                    "waveStartAt": START + (4 + i) * HOUR,
                }
            )
    groups.append({"phaseId": 3, "identifier": "1", "state": 1, "startAt": START + 7 * HOUR})
    groups.append({"phaseId": 4, "identifier": "1", "state": 1, "startAt": START + 24 * HOUR})
    return {"startAt": START, "phases": phases, "groups": groups}


def _League(players):
    points = [920, 845, 790, 640, 615, 560, 470, 455, 430, 380, 345, 300, 260, 220, 190, 150]
    order = [2, 1, 4, 3, 7, 5, 6, 10, 8, 9, 12, 11, 14, 13, 16, 15]
    return {
        "name": "HyperDrive Circuit 2026",
        "slug": "tournament/hyperdrive-circuit-2026",
        "logo": "",
        "banner": "",
        "players": 128,
        "standings": Numbered(
            [
                {
                    "placement": i + 1,
                    "points": points[i],
                    "player_id": index,
                    "gamertag": players[index - 1]["gamerTag"],
                    "sponsor": players[index - 1].get("prefix") or "",
                }
                for i, index in enumerate(order[: len(players)])
            ]
        ),
    }


def Build(players, character, stage):
    """{event_stats, schedule, league}. character(key) gives the layout data of
    a character of the sample game by its key, stage(codename) a stage's."""

    def Character(key):
        data = character(key) if key else None
        return dict(data, key=key) if data else None

    def Stage(codename, name):
        data = stage(codename)
        return dict(data, key=codename) if data else None

    sets = _Sets(players)
    # Shown as "now" by the schedule, in the middle of Round 2 Pools
    now = START + 4 * HOUR + 1200
    return {
        "event_stats": BuildEventStats(sets, _Standings(players), Character, Stage, now=now),
        "schedule": BuildSchedule(_Schedule(), now=now),
        "league": _League(players),
    }


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
