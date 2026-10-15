# Checks StartGGDataProvider against recorded start.gg responses (made with
# scripts/record_startgg_fixtures.py, anonymized), offline:
# - Contract: every method's result has the shape its type in
#   src/TournamentDataProvider/ResultTypes.py says, all the way down.
# - Behavior: things the recorded event has, like DQs, stages and a grand
#   final reset, come through.
# - Expected results: every result is the same as in
#   test/fixtures/startgg/expected.json, so refactoring the provider can't
#   change what the app gets without this failing. After an intended change:
#   python test/test_startgg_provider.py --update
# Run from the repository root: python test/test_startgg_provider.py
import json
import os
import sys
from types import UnionType
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startgg_harness as H

from src.TournamentDataProvider import ResultTypes as R

EXPECTED = os.path.join(H.FIXTURE_DIR, "expected.json")
NONE = type(None)

failures = []


# =====================================================
# CONTRACT
# =====================================================
def Conforms(value, tp, path, errors):
    """Adds to errors where value doesn't have the shape tp (a ResultTypes
    TypedDict, list[...], dict[str, ...], a union or a plain type) says.
    Keys a TypedDict doesn't list are allowed."""
    origin = get_origin(tp)
    if tp is NONE:
        if value is not None:
            errors.append(f"{path}: {value!r}, expected None")
    elif origin in (Union, UnionType):
        for option in get_args(tp):
            found = []
            Conforms(value, option, path, found)
            if not found:
                return
        errors.append(f"{path}: {type(value).__name__} matches none of {tp}")
    elif is_typeddict(tp):
        if not isinstance(value, dict):
            errors.append(f"{path}: {type(value).__name__}, expected {tp.__name__}")
            return
        for key in sorted(tp.__required_keys__ - value.keys()):
            errors.append(f"{path}: no {key} ({tp.__name__})")
        for key, keyType in get_type_hints(tp).items():
            if key in value:
                Conforms(value[key], keyType, f"{path}.{key}", errors)
    elif origin is list:
        if not isinstance(value, list):
            errors.append(f"{path}: {type(value).__name__}, expected a list")
            return
        (itemType,) = get_args(tp)
        for i, item in enumerate(value):
            Conforms(item, itemType, f"{path}[{i}]", errors)
    elif origin is dict:
        if not isinstance(value, dict):
            errors.append(f"{path}: {type(value).__name__}, expected a dict")
            return
        _, valueType = get_args(tp)
        for key, item in value.items():
            Conforms(item, valueType, f"{path}.{key}", errors)
    elif tp is int and isinstance(value, bool) or not isinstance(value, tp):
        errors.append(f"{path}: {type(value).__name__} {value!r:.40}, expected {tp.__name__}")


# What each result of the scenario is
CONTRACT = {
    "tournament_data": R.TournamentData,
    "icon_url": str,
    "streams_and_stations": R.StreamsAndStations,
    "phases": list[R.Phase],
    "phase_group": R.PhaseGroup,
    "phase_group_sets": R.PhaseGroupSets,
    "matches_open": list[R.SetListItem],
    "matches_all": list[R.SetListItem],
    "match": dict[str, R.Set],
    "future_match": dict[str, R.FutureSet],
    "future_matches_list": dict[str, R.FutureSet | None],
    "stations": list[R.Station],
    "stream_queue": dict[str, dict[str, R.FutureSet]],
    "stream_match": dict[str, R.FutureSet | None],
    "station_matches": dict[str, list[dict]],
    "completed_sets": list[R.CompletedSet],
    "set_durations": list[R.SetDuration],
    "standings": list[R.Standing],
    "last_sets_1": R.LastSets,
    "last_sets_2": R.LastSets,
    "history_sets_1": R.HistorySets,
    "history_sets_2": R.HistorySets,
    "recent_sets": R.RecentSets,
    "entrants_result": NONE,
    "entrants_added": list[R.Entrant],
    # {user slug: {game codename: [[character name], ...]}}
    "user_mains": dict[str, dict[str, list]],
}

# Results the recorded event has some of: a contract check of an empty list
# would pass whatever the items' shape
NOT_EMPTY = [
    "phases",
    "phase_group.sets",
    "phase_group.entrants",
    "matches_all",
    "match",
    "future_match",
    "future_matches_list",
    "stations",
    "streams_and_stations.streams",
    "completed_sets",
    "set_durations",
    "standings",
    "last_sets_1.last_sets",
    "history_sets_1.history_sets",
    "recent_sets.sets",
    "entrants_added",
    "user_mains",
]


def CheckChecker():
    """Conforms() finds what it should, so passing contract checks mean
    something"""
    player = {"name": "A", "team": None, "mergedName": "A", "real_name": None, "id": [1, 2]}
    player.update(twitter="", pronoun="", socials={}, country={}, state={}, online_avatar="")
    team = {"teamName": "A", "seed": 1, "losers": False, "player": {"1": player}}
    good = {"id": 1, "match": "", "phase": "", "event": "", "best_of": 3, "best_of_text": ""}
    good.update(state=1, station=None, isCurrentEvent=True, team={"1": team})
    noName = json.loads(json.dumps(good))
    del noName["team"]["1"]["player"]["1"]["name"]
    cases = [
        (good, R.FutureSet, False),
        (noName, R.FutureSet, "no name"),
        (dict(good, best_of=True), R.FutureSet, "best_of: bool"),
        (dict(good, station="1"), R.FutureSet, "matches none"),
        ([good, None], list[R.FutureSet], "[1]"),
        ({"1": None}, dict[str, R.FutureSet | None], False),
        (None, NONE, False),
        (0, NONE, "expected None"),
    ]
    for value, tp, expected in cases:
        errors = []
        Conforms(value, tp, "case", errors)
        if bool(errors) != bool(expected) or (expected and expected not in " ".join(errors)):
            failures.append(f"contract checker: expected {expected!r} for {tp}, got {errors}")


def CheckContract(out):
    CheckChecker()
    missing = sorted(CONTRACT.keys() ^ out.keys())
    if missing:
        failures.append(f"results without a contract, or missing: {missing}")
    for name, tp in CONTRACT.items():
        if name in out:
            Conforms(out[name], tp, name, failures)
    for path in NOT_EMPTY:
        value = out
        for key in path.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if not value:
            failures.append(f"{path}: empty, expected some")


# =====================================================
# BEHAVIOR
# =====================================================
def CheckBehavior(provider, out):
    def expect(ok, message):
        if not ok:
            failures.append(message)

    expect(not provider.misses, f"requests that weren't recorded: {provider.misses}")
    errors = [k for k, v in Flatten(out) if k.endswith(".exception")]
    expect(not errors, f"methods that raised: {errors}")

    matches = list(out["match"].values())
    expect(len(out["matches_all"]) == 49, f"{len(out['matches_all'])} sets, expected 49")
    expect(out["tournament_data"]["numEntrants"] == 25, "expected 25 entrants")
    expect(len(out["entrants_added"]) == 25, "all 25 entrants go to the player database")
    rounds = {m["round_name"] for m in matches}
    expect({"Grand Final", "Grand Final Reset"} <= rounds, f"no grand final and reset in {rounds}")
    expect(
        sum(1 for m in matches if any(g["stage"] for g in m["games"])) == 17,
        "17 sets have their stages reported",
    )
    expect(
        all(c for m in matches for g in m["games"] for c in g["characters"]),
        "every reported game has its characters",
    )
    expect(any(d["dq"] for d in out["set_durations"]), "a set was a DQ")
    expect(
        {s["type"] for s in out["stations"]} == {"station"},
        f"stations: {out['stations']}",
    )
    expect(
        len(out["streams_and_stations"]["streams"]) == 3,
        "the tournament has 3 streams",
    )
    futures = out["future_matches_list"]
    expect(
        [futures[str(i + 1)] for i in range(len(futures))]
        == [out["future_match"][k] for k in sorted(out["future_match"])],
        "GetFutureMatchesList: the same sets as GetFutureMatch, in order",
    )
    placements = [t["players"][0]["gamerTag"] for t in out["standings"]]
    expect(len(set(placements)) == 8, f"8 different players in the top 8: {placements}")


def Flatten(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from Flatten(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from Flatten(v, f"{path}[{i}]")
    else:
        yield path, value


# =====================================================
# EXPECTED RESULTS
# =====================================================
def CheckExpected(out, update):
    # The results as JSON would carry them (int keys become strings...)
    out = json.loads(json.dumps(out, sort_keys=True))
    if update:
        H.SaveJson(EXPECTED, out)
        print(f"Updated {os.path.relpath(EXPECTED)}")
        return
    with open(EXPECTED, encoding="utf-8") as f:
        expected = json.load(f)
    got, want = dict(Flatten(out)), dict(Flatten(expected))
    changed = sorted(
        k for k in got.keys() | want.keys() if got.get(k, "<missing>") != want.get(k, "<missing>")
    )
    for k in changed[:20]:
        failures.append(
            f"changed: {k}: {want.get(k, '<missing>')!r} -> {got.get(k, '<missing>')!r}"
        )
    if len(changed) > 20:
        failures.append(f"... and {len(changed) - 20} more changes")


def main():
    update = "--update" in sys.argv
    recording = H.LoadRecording()
    added = H.SetUpApp(H.StagesIn([r["response"] for r in recording["requests"]]))
    provider = H.ReplayProvider(recording)
    out = H.RunScenario(provider, added)

    for check in (lambda: CheckBehavior(provider, out), lambda: CheckContract(out)):
        try:
            check()
        except Exception as e:
            # A result too different to check further
            failures.append(f"checks stopped: {type(e).__name__}: {e}")
    if failures and update:
        sys.exit("Not updated, fix these first:\n" + "\n".join(failures))
    CheckExpected(out, update)

    if failures:
        print("\n".join(failures))
        sys.exit(f"{len(failures)} start.gg provider checks failed")
    print("All start.gg provider checks passed")


if __name__ == "__main__":
    main()
