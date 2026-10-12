# Checks what the event's completed sets add up to: how long sets take and
# when the stream queue's sets should start, characters and stages played,
# upsets, over- and underperformers, and the schedule.
# Run from the repository root: python test/test_event_stats.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.EventStats import (
    BuildEventStats,
    BuildSchedule,
    Durations,
    EstimateStarts,
    Performers,
    SetSeconds,
    Upsets,
    Usage,
)
from src.Helpers.SeedPerformance import DOUBLE_ELIMINATION
from src.StreamQueue import StreamQueueModel

MIN = 60


def Entrant(id, name, seed):
    return {"id": id, "name": name, "seed": seed, "players": [{"id": id, "gamertag": name}]}


def StatsSet(id, winner, seeds, games=(), dq=False, minutes=20, bestOf=3):
    """A set between entrants named A and B, won by slot `winner`."""
    return {
        "id": id,
        "started_at": 1000,
        "completed_at": 1000 + minutes * MIN,
        "total_games": bestOf,
        "round_name": "Winners Round 1",
        "phase_name": "Pools",
        "phase_id": "A1",
        "bracket_type": DOUBLE_ELIMINATION,
        "winner": winner,
        "scores": [-1, 0] if dq else ([2, 1] if winner == 0 else [1, 2]),
        "dq": dq,
        "entrants": [Entrant(10 + id, "A", seeds[0]), Entrant(20 + id, "B", seeds[1])],
        "games": list(games),
    }


def Game(winner, chars, stage=None):
    return {
        "winner": winner,
        "stage_id": stage,
        "stage_name": f"Stage {stage}" if stage else "",
        "selections": [{"slot": slot, "character_id": c} for slot, c in enumerate(chars)],
    }


def Character(id):
    return {"key": f"c{id}", "name": f"Char {id}"}


def TestDurations():
    sets = [
        {"startedAt": 0, "completedAt": 10 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 12 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 14 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 30 * MIN, "totalGames": 5},
        # Left out: a DQ, a set with no start, one reported hours later
        {"startedAt": 0, "completedAt": 5 * MIN, "totalGames": 3, "dq": True},
        {"startedAt": None, "completedAt": 5 * MIN, "totalGames": 3},
        {"startedAt": 0, "completedAt": 10 * 60 * MIN, "totalGames": 3},
    ]
    durations = Durations(sets)
    assert sorted(durations[None]) == [10 * MIN, 12 * MIN, 14 * MIN, 30 * MIN]
    assert SetSeconds(durations, 3) == 12 * MIN
    # Not enough best of 5s yet: every set's
    assert SetSeconds(durations, 5) == 13 * MIN
    assert SetSeconds(durations) == 13 * MIN
    assert SetSeconds({}, 3) is None
    # The event stats sets' keys work too
    assert Durations([StatsSet(1, 0, (1, 2), minutes=15)])[3] == [15 * MIN]


def TestEstimateStarts():
    durations = {None: [10 * MIN] * 3, 3: [10 * MIN] * 3, 5: [20 * MIN] * 3}
    now = 100000
    sets = [
        # Started 4 minutes ago: 6 minutes left
        {"state": 2, "best_of": 3, "started_at": now - 4 * MIN},
        {"state": 1, "best_of": 3},
        {"state": 3, "best_of": 3},
        {"state": 1, "best_of": 5},
        {"state": 1, "best_of": 3},
    ]
    result = EstimateStarts(sets, durations, now)
    assert result[0] == (now - 4 * MIN, 0)
    assert result[1] == (now + 6 * MIN, 6)
    # Finished sets have no start time and take no time
    assert result[2] == (None, None)
    assert result[3] == (now + 16 * MIN, 16)
    assert result[4] == (now + 36 * MIN, 36)
    # Without data, nothing can be told
    assert EstimateStarts(sets[1:2], {}, now) == [(None, None)]


def TestStreamQueueEta():
    model = StreamQueueModel()
    model.SetProviderQueues(
        {"main": [{"id": 1, "state": 1, "best_of": 3}, {"id": 2, "state": 1, "best_of": 3}]}
    )
    durations = {None: [10 * MIN] * 3}
    exported = model.Export(onStream={"main": 1}, durations=durations, now=1000)
    main = exported["byName"]["main"]
    # The set on the stream's scoreboard is being played
    assert main[0]["eta_minutes"] == 0
    assert main[0]["state"] == 1
    assert main[1]["eta_minutes"] == 10
    assert exported["average_set_minutes"] == 10
    # Without durations, no times
    assert model.Export()["byName"]["main"][1]["eta"] is None


def TestUpsets():
    sets = [
        StatsSet(1, 1, (1, 12)),  # 12 beat 1
        StatsSet(2, 0, (9, 8)),  # 9 beat 8
        StatsSet(3, 0, (1, 2)),  # not an upset
        StatsSet(4, 1, (1, 30), dq=True),  # DQs don't count
    ]
    upsets = Upsets(sets)
    assert [u["winner"]["seed"] for u in upsets] == [12, 9]
    first = upsets[0]
    assert first["winner"]["name"] == "B" and first["loser"]["seed"] == 1
    assert first["winner_score"] == 2 and first["loser_score"] == 1
    assert first["upset_factor"] > upsets[1]["upset_factor"] > 0
    assert Upsets(sets, top=1) == upsets[:1]


def TestPerformers():
    standings = [
        {"placement": 1, "seed": 12, "final": True, "name": "Zomba", "players": []},
        {"placement": 2, "seed": 1, "final": True, "name": "Sonix", "players": []},
        {"placement": 17, "seed": 2, "final": True, "name": "Miya", "players": []},
        # Still playing: placement isn't final
        {"placement": 33, "seed": 3, "final": False, "name": "Sparg0", "players": []},
    ]
    over, under = Performers(standings, DOUBLE_ELIMINATION)
    assert [p["name"] for p in over] == ["Zomba"]
    assert over[0]["spr"] > 0
    assert [p["name"] for p in under] == ["Miya", "Sonix"]
    assert under[0]["spr"] < under[1]["spr"] < 0


def TestUsage():
    sets = [
        StatsSet(1, 0, (1, 2), games=[Game(0, (1, 2), stage=7), Game(0, (1, 2), stage=7)]),
        StatsSet(2, 1, (3, 4), games=[Game(1, (1, 3), stage=8)]),
        StatsSet(3, 1, (5, 6), games=[Game(1, (1, 1))]),  # a ditto
        StatsSet(4, 1, (5, 6), games=[Game(1, (9, 9))], dq=True),
    ]

    def Stage(id, name):
        return {"key": f"s{id}", "name": name, "codename": f"s{id}"} if id == 7 else None

    characters, stages = Usage(sets, Character, Stage)
    first = characters[0]
    assert first["name"] == "Char 1"
    # 2 games in set 1, 1 in set 2, both sides of the ditto
    assert first["games"] == 5 and first["wins"] == 3 and first["win_rate"] == 60
    assert first["sets"] == 3
    assert "key" not in first
    assert [c["name"] for c in characters] == ["Char 1", "Char 2", "Char 3"]
    assert sum(c["play_rate"] for c in characters) in (99, 100, 101)
    # Stages the game doesn't know keep start.gg's name
    assert [(s["name"], s["games"]) for s in stages] == [("Stage 7", 2), ("Stage 8", 1)]
    assert stages[0]["codename"] == "s7"

    stats = BuildEventStats(sets, None, Character, Stage, now=5)
    assert stats["sets"] == 3 and stats["dqs"] == 1 and stats["games"] == 4
    assert stats["characters"]["1"]["name"] == "Char 1"
    assert stats["average_set_minutes"] == 20
    assert stats["updated"] == 5
    assert stats["overperformers"] == {}


def TestSchedule():
    schedule = {
        "startAt": 1000,
        "phases": [
            {"id": 2, "name": "Top 8", "order": 2, "state": "CREATED", "groupCount": 1},
            {"id": 1, "name": "Pools", "order": 1, "state": "ACTIVE", "groupCount": 2},
        ],
        "groups": [
            {"phaseId": 1, "identifier": "A1", "state": 3, "wave": "A", "waveStartAt": 1000},
            {"phaseId": 1, "identifier": "B1", "state": 1, "wave": "B", "waveStartAt": 4600},
            {"phaseId": 2, "identifier": "1", "state": 1, "startAt": 9000},
        ],
    }
    result = BuildSchedule(schedule, now=3400)
    phases = result["phases"]
    assert [phases["1"]["name"], phases["2"]["name"]] == ["Pools", "Top 8"]
    assert phases["1"]["state"] == "active" and phases["1"]["start_at"] == 1000
    assert phases["1"]["waves"] == ["A", "B"]
    assert phases["2"]["state"] == "upcoming" and phases["2"]["start_at"] == 9000
    waves = result["waves"]
    assert [waves["1"]["identifier"], waves["2"]["identifier"]] == ["A", "B"]
    assert waves["1"]["state"] == "completed" and waves["2"]["phases"] == ["Pools"]
    # Wave B is next, in 20 minutes
    assert result["next"]["identifier"] == "B" and result["next"]["minutes"] == 20
    assert phases["1"]["time"] and result["event_start"]["start_at"] == 1000
    assert BuildSchedule(None)["phases"] == {}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
