# Checks that every tournament data provider keeps the contract of
# TournamentDataProvider:
# - its public methods take what the base class' take (same parameters, same
#   defaults), so a caller written for one provider works with the others
# - what they return has the shapes of ResultTypes.py. start.gg's are checked
#   against a recorded event in test_startgg_provider.py; parry.gg's here,
#   against a made-up parry.gg (parrygg_harness.py)
# - when the provider can't be asked, every method raises a ProviderError
#   inside RaiseProviderErrors, and returns something empty outside of it
# and how parry.gg's provider connects and caches.
# Run from the repository root: python test/test_provider_contract.py
import inspect
import os
import sys
import types
from types import UnionType
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("test"))
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

import grpc
import parrygg_harness as P
import startgg_harness as H

from src.TournamentDataProvider import ResultTypes as R
from src.TournamentDataProvider.ParryGGDataProvider import ParryGGDataProvider
from src.TournamentDataProvider.ProviderErrors import (
    KIND_AUTH,
    KIND_NOT_FOUND,
    KIND_RATE_LIMITED,
    KIND_TRANSIENT,
    ProviderError,
    RaiseProviderErrors,
    TransientError,
)
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider
from src.TournamentDataProvider.TournamentDataProvider import TournamentDataProvider

PROVIDERS = [StartGGDataProvider, ParryGGDataProvider]
NONE = type(None)


def ContractMethods():
    """The base class' own public methods"""
    return sorted(
        name
        for name, value in vars(TournamentDataProvider).items()
        if inspect.isfunction(value) and not name.startswith("_")
    )


def Parameters(function):
    return [
        (p.name, p.kind, p.default)
        for p in inspect.signature(function).parameters.values()
        if p.name != "self"
    ]


# =====================================================
# SIGNATURES
# =====================================================
def TestSignatures():
    methods = ContractMethods()
    assert "GetFutureMatch" in methods and "GetStandings" in methods, methods
    assert "Connect" in methods

    problems = []
    for provider in PROVIDERS:
        for name in methods:
            expected = Parameters(getattr(TournamentDataProvider, name))
            got = Parameters(getattr(provider, name))
            if got != expected:
                problems.append(
                    f"{provider.__name__}.{name}{inspect.signature(getattr(provider, name))}"
                    f" != {inspect.signature(getattr(TournamentDataProvider, name))}"
                )
    assert not problems, "\n" + "\n".join(problems)

    # What a Worker passes is optional everywhere, so a method can be called
    # directly too (the stream queue calls GetFutureMatch(setId))
    for name in methods:
        parameters = inspect.signature(getattr(TournamentDataProvider, name)).parameters
        for extra in ("progress_callback", "cancel_event"):
            if extra in parameters:
                assert parameters[extra].default is None, f"{name}: {extra} has no default"


# =====================================================
# SHAPES
# =====================================================
def Conforms(value, tp, path, missing, types):
    """Where value doesn't have the shape tp (a ResultTypes TypedDict,
    list[...], dict[str, ...], a union or a plain type) says: keys that
    aren't there go to missing, values of another type to types. Keys a
    TypedDict doesn't list are allowed."""
    origin = get_origin(tp)
    if tp is NONE:
        if value is not None:
            types.append(f"{path}: {type(value).__name__}, expected None")
    elif origin in (Union, UnionType):
        for option in get_args(tp):
            foundMissing, foundTypes = [], []
            Conforms(value, option, path, foundMissing, foundTypes)
            if not foundMissing and not foundTypes:
                return
        types.append(f"{path}: {type(value).__name__} matches none of {tp}")
    elif is_typeddict(tp):
        if not isinstance(value, dict):
            types.append(f"{path}: {type(value).__name__}, expected {tp.__name__}")
            return
        for key in sorted(tp.__required_keys__ - value.keys()):
            missing.append(f"{path}: no {key} ({tp.__name__})")
        for key, keyType in get_type_hints(tp).items():
            if key in value:
                Conforms(value[key], keyType, f"{path}.{key}", missing, types)
    elif origin is list:
        if not isinstance(value, list):
            types.append(f"{path}: {type(value).__name__}, expected a list")
            return
        (itemType,) = get_args(tp)
        for i, item in enumerate(value):
            Conforms(item, itemType, f"{path}[]", missing, types)
    elif origin is dict:
        if not isinstance(value, dict):
            types.append(f"{path}: {type(value).__name__}, expected a dict")
            return
        _, valueType = get_args(tp)
        for item in value.values():
            Conforms(item, valueType, f"{path}.*", missing, types)
    elif tp is int and isinstance(value, bool) or not isinstance(value, tp):
        types.append(f"{path}: {type(value).__name__}, expected {tp.__name__}")


def TestChecker():
    """Conforms finds what it should, so passing checks mean something"""
    station = {"id": 1, "identifier": "Main", "type": "stream", "stream": ""}
    for value, tp, expectMissing, expectTypes in [
        (station, R.Station, False, False),
        ({k: v for k, v in station.items() if k != "type"}, R.Station, True, False),
        (dict(station, id="uuid"), R.Station, False, True),
        ([station, None], list[R.Station], False, True),
        ({"1": None}, dict[str, R.Station | None], False, False),
    ]:
        missing, wrong = [], []
        Conforms(value, tp, "case", missing, wrong)
        assert bool(missing) == expectMissing and bool(wrong) == expectTypes, (
            value,
            missing,
            wrong,
        )


def Scenario(provider):
    """Every method the app calls, and what each returns"""

    def Emitted(fn, **kwargs):
        callback = H.Callback()
        fn(callback=callback, **kwargs)
        return callback.value

    out = {}
    out["tournament_data"] = provider.GetTournamentData()
    out["icon_url"] = provider.GetIconURL()
    out["phases"] = provider.GetTournamentPhases()
    groupId = out["phases"][0]["groups"][0]["id"]
    out["phase_group"] = provider.GetTournamentPhaseGroup(groupId)
    out["phase_group_sets"] = provider.GetTournamentPhaseGroupSets(groupId)
    out["matches_open"] = provider.GetMatches(getFinished=False)
    out["matches_all"] = provider.GetMatches(getFinished=True)
    setIds = [m["id"] for m in out["matches_all"]]
    out["match"] = {str(id): provider.GetMatch(id) for id in setIds}
    out["future_match"] = {str(id): provider.GetFutureMatch(id) for id in setIds}
    out["future_matches_list"] = provider.GetFutureMatchesList([{"id": id} for id in setIds])
    out["stations"] = provider.GetStations()
    out["stream_queue"] = provider.GetStreamQueue()
    out["stream_match"] = {
        str(s["identifier"]): provider.GetStreamMatchId(s)
        for s in out["stations"]
        if s["type"] == "stream"
    }
    out["station_matches"] = {
        str(s["id"]): provider.GetStationMatchsId(s["id"]) for s in out["stations"]
    }
    out["station_match"] = provider.GetStationMatchId(out["stations"][0]["id"])
    out["streams_and_stations"] = provider.GetStreamsAndStations()
    out["completed_sets"] = provider.GetCompletedSets()
    out["set_durations"] = provider.GetSetDurations()
    out["standings"] = provider.GetStandings(8)
    # The first and the last of them: they played each other in the first round
    players = [team["players"][0] for team in out["standings"]]
    players = [players[0], players[-1]]
    out["last_sets"] = Emitted(provider.GetLastSets, playerID=players[0]["id"][0], playerNumber="1")
    out["history_sets"] = Emitted(
        provider.GetPlayerHistoryStandings,
        playerID=players[0]["id"][0],
        playerNumber="1",
        gameType=H.ULTIMATE_ID,
    )
    out["recent_sets"] = Emitted(
        provider.GetRecentSets,
        id1=players[0]["id"],
        id2=players[1]["id"],
        videogame=H.ULTIMATE_ID,
        requestTime=0,
    )
    out["entrants"] = provider.FetchEntrants()
    return out


CONTRACT = {
    "tournament_data": R.TournamentData,
    "icon_url": str,
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
    "station_match": dict | None,
    "streams_and_stations": R.StreamsAndStations | None,
    "completed_sets": list[R.CompletedSet],
    "set_durations": list[R.SetDuration] | None,
    "standings": list[R.Standing],
    "last_sets": R.LastSets,
    "history_sets": R.HistorySets,
    "recent_sets": R.RecentSets,
    "entrants": list[R.Entrant],
}

# Results the made-up event has some of: an empty list would pass whatever
# its items' shape
NOT_EMPTY = [
    "phases",
    "matches_open",
    "matches_all",
    "match",
    "future_match",
    "stations",
    "stream_queue",
    "completed_sets",
    "standings",
    "last_sets.last_sets",
    "recent_sets.sets",
    "entrants",
]

# Where parry.gg's results aren't what ResultTypes.py says, known and lived
# with: its ids are UUID strings where start.gg's are numbers, and it leaves
# out what it doesn't have. Anything else that shows up is a regression (or
# a deviation to fix, or to add here knowingly).
PARRY_KNOWN_MISSING = [
    "entrants[]: no socials (Entrant)",
    "entrants[]: no startgg_user_slug (Entrant)",
    "last_sets.last_sets[]: no oponent_char (LastSet)",
    "last_sets.last_sets[]: no player_char (LastSet)",
    "match.*.entrants[][]: no losses (SetPlayer)",
    "match.*.entrants[][]: no seed (SetPlayer)",
    "match.*.entrants[][]: no socials (SetPlayer)",
    "match.*.entrants[][]: no winPercentage (SetPlayer)",
    "match.*.entrants[][]: no wins (SetPlayer)",
    "match.*: no bestOf (Set)",
    "match.*: no currPlayer (Set)",
    "match.*: no entrant_ids (Set)",
    "match.*: no games (Set)",
    "match.*: no ruleset (Set)",
    "match.*: no stage_strike (Set)",
    "match.*: no state (Set)",
    "match.*: no strikedBy (Set)",
    "match.*: no team1losers (Set)",
    "match.*: no team2losers (Set)",
    "matches_all[].entrants[][]: no losses (SetListPlayer)",
    "matches_all[].entrants[][]: no winPercentage (SetListPlayer)",
    "matches_all[].entrants[][]: no wins (SetListPlayer)",
    "matches_all[]: no entrant_ids (SetListItem)",
    "matches_all[]: no games (SetListItem)",
    "matches_open[].entrants[][]: no losses (SetListPlayer)",
    "matches_open[].entrants[][]: no winPercentage (SetListPlayer)",
    "matches_open[].entrants[][]: no wins (SetListPlayer)",
    "matches_open[]: no entrant_ids (SetListItem)",
    "matches_open[]: no games (SetListItem)",
    "phase_group.entrants[].players[]: no socials (Player)",
    "phase_group: no entrantIds (PhaseGroup)",
    "recent_sets.sets[]: no p1_char (RecentSet)",
    "recent_sets.sets[]: no p2_char (RecentSet)",
    "standings[].players[]: no mains (StandingPlayer)",
    "standings[].players[]: no socials (StandingPlayer)",
    "standings[].players[]: no startggMains (StandingPlayer)",
    "standings[]: no losses (Standing)",
    "standings[]: no winPercentage (Standing)",
    "standings[]: no wins (Standing)",
    "tournament_data: no banner (TournamentData)",
    "tournament_data: no logo (TournamentData)",
    "tournament_data: no shortLink (TournamentData)",
]
PARRY_KNOWN_TYPES = [
    "future_match.*.id: str, expected int",
    "future_match.*.station: str matches none of int | None",
    "future_matches_list.*: dict matches none of src.TournamentDataProvider.ResultTypes.FutureSet | None",
    "match.*.id: str, expected int",
    "matches_all[].id: str, expected int",
    "matches_open[].id: str, expected int",
    "phase_group.progressionsIn: list, expected int",
    "phase_group.progressionsOut: list, expected int",
    "phase_group.sets: dict, expected a list",
    "phase_group_sets.sets: dict, expected a list",
    "phases[].groups[].id: str, expected int",
    "phases[].id: str, expected int",
    "recent_sets.sets[].id: str, expected int",
    "stations[].id: str, expected int",
    "stream_match.*: dict matches none of src.TournamentDataProvider.ResultTypes.FutureSet | None",
    "stream_queue.*.*.id: str, expected int",
    "stream_queue.*.*.station: str matches none of int | None",
]


def TestParryShapes():
    context = H.SetUpApp()
    provider = P.NewProvider(P.World(), context)
    out = Scenario(provider)

    for path in NOT_EMPTY:
        value = out
        for key in path.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        assert value, f"{path}: empty, expected some ({out.get(path.split('.')[0])})"

    missing, wrong = [], []
    for name, tp in CONTRACT.items():
        Conforms(out[name], tp, name, missing, wrong)
    missing, wrong = sorted(set(missing)), sorted(set(wrong))
    if "--show" in sys.argv:
        print("MISSING = [\n" + "".join(f'    "{m}",\n' for m in missing) + "]")
        print("TYPES = [\n" + "".join(f'    "{m}",\n' for m in wrong) + "]")
    newMissing = sorted(set(missing) - set(PARRY_KNOWN_MISSING))
    newTypes = sorted(set(wrong) - set(PARRY_KNOWN_TYPES))
    assert not newMissing, "keys parry.gg's results lost:\n" + "\n".join(newMissing)
    assert not newTypes, "values of parry.gg's results that changed type:\n" + "\n".join(newTypes)
    # The lists above only hold what's still true
    gone = sorted((set(PARRY_KNOWN_MISSING) - set(missing)) | (set(PARRY_KNOWN_TYPES) - set(wrong)))
    assert not gone, "fixed, to remove from the known deviations:\n" + "\n".join(gone)

    # What the scenario found
    assert out["tournament_data"]["tournamentName"] == "Weekly"
    assert out["tournament_data"]["eventName"] == "Singles"
    assert [m["id"] for m in out["matches_open"]] == ["m3"]
    assert sorted(m["id"] for m in out["matches_all"]) == ["m1", "m2", "m3"]
    assert out["match"]["m3"]["round_name"] == "Winners Final"
    assert out["match"]["m3"]["stream"] == "https://www.twitch.tv/weeklytv"
    assert list(out["stream_queue"]) == ["Weekly TV"]
    assert out["stream_queue"]["Weekly TV"]["1"]["id"] == "m3"
    assert out["stream_match"]["Weekly TV"]["id"] == "m3"
    assert out["station_matches"][P.STREAM_ID] == [{"id": "m3"}]
    assert out["future_matches_list"]["3"]["id"] == "m3"
    assert [t["players"][0]["gamerTag"] for t in out["standings"]] == P.PLAYERS
    assert [p["gamerTag"] for p in out["entrants"]] == P.PLAYERS
    assert len(out["completed_sets"]) == 2
    # Ana beat Di 2-0: one set between them, played offline
    sets = out["recent_sets"]["sets"]
    assert len(out["last_sets"]["last_sets"]) == 1
    assert [(s["id"], s["score"], s["winner"], s["online"]) for s in sets] == [
        ("m1", [2, 0], 0, False)
    ], sets


# =====================================================
# FAILED IS NOT EMPTY
# =====================================================
# Every method that asks the provider something, how it's called, and what
# it returns when it can't and isn't asked to raise
def Calls(provider, setId, stationId):
    callback = H.Callback()
    return [
        ("GetTournamentData", lambda: provider.GetTournamentData(), {}),
        ("GetTournamentPhases", lambda: provider.GetTournamentPhases(), []),
        ("GetTournamentPhaseGroup", lambda: provider.GetTournamentPhaseGroup("br1"), {}),
        ("GetTournamentPhaseGroupSets", lambda: provider.GetTournamentPhaseGroupSets("br1"), {}),
        ("GetMatch", lambda: provider.GetMatch(setId), None),
        ("GetMatches", lambda: provider.GetMatches(), []),
        ("GetFutureMatch", lambda: provider.GetFutureMatch(setId), {}),
        ("GetStations", lambda: provider.GetStations(), []),
        ("GetStreamQueue", lambda: provider.GetStreamQueue(), {}),
        (
            "GetStreamMatchId",
            lambda: provider.GetStreamMatchId({"id": stationId, "identifier": "Main", "slot": 0}),
            None,
        ),
        ("GetCompletedSets", lambda: provider.GetCompletedSets(), []),
        ("FetchEntrants", lambda: provider.FetchEntrants(), []),
        ("GetStandings", lambda: provider.GetStandings(8), []),
    ], callback


def CheckFailures(name, NewFailing, setId, stationId, kinds):
    """NewFailing(kind): a provider that can't be asked anything, for that
    kind of error"""
    for kind in kinds:
        provider = NewFailing(kind)
        calls, callback = Calls(provider, setId, stationId)
        for method, call, empty in calls:
            # Asked to raise (TournamentDataManager.Run): the kind of error
            try:
                with RaiseProviderErrors():
                    result = call()
            except ProviderError as e:
                assert e.kind == kind, f"{name}.{method}: {e.kind}, expected {kind} ({e})"
            else:
                raise AssertionError(f"{name}.{method} returned {result!r} for a failed request")
            # Called directly (the web server's actions): empty, never raises
            result = call()
            if method == "GetMatch":
                # A set without an id, which the scoreboard ignores
                result = (result or {}).get("id")
            assert not result, f"{name}.{method}: {result!r} for a failed request"
            if empty is not None:
                assert result == empty, f"{name}.{method}: {result!r}, expected {empty!r}"

        # Each set of a queue on its own: None for the ones that failed
        with RaiseProviderErrors():
            assert provider.GetFutureMatchesList([{"id": setId}]) == {"1": None}, name
        # Players' stats emit nothing found, as they did
        with RaiseProviderErrors():
            provider.GetLastSets(playerID="u1", playerNumber="1", callback=callback)
        assert callback.value == {"playerNumber": "1", "last_sets": []}, (name, callback.value)


def TestFailedIsNotEmpty():
    context = H.SetUpApp()

    # parry.gg: every gRPC call fails
    codes = {
        KIND_TRANSIENT: grpc.StatusCode.UNAVAILABLE,
        KIND_AUTH: grpc.StatusCode.UNAUTHENTICATED,
        KIND_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        KIND_RATE_LIMITED: grpc.StatusCode.RESOURCE_EXHAUSTED,
    }

    def FailingParry(kind):
        world = P.World()
        provider = P.NewProvider(world, context)
        world.fail = codes[kind]
        return provider

    CheckFailures("parry.gg", FailingParry, "m3", P.STREAM_ID, list(codes))

    # start.gg: every request fails
    def FailingStartGG(kind):
        provider = H.NewProvider("https://www.start.gg/tournament/t/event/e", context)

        def query(*args, **kwargs):
            raise ProviderError("made up", kind)

        provider.QueryRequests = query
        return provider

    CheckFailures("start.gg", FailingStartGG, 123, 1, list(codes))

    # An answer that isn't one (what a failed request used to look like)
    def NoAnswer(kind):
        provider = H.NewProvider("https://www.start.gg/tournament/t/event/e", context)
        provider.QueryRequests = lambda *args, **kwargs: {}
        return provider

    CheckFailures("start.gg", NoAnswer, 123, 1, [KIND_TRANSIENT])
    assert TransientError("x").kind == KIND_TRANSIENT


# =====================================================
# PARRY.GG: CONNECTING AND CACHING
# =====================================================
def Raises(fn, kind):
    try:
        fn()
    except ProviderError as e:
        assert e.kind == kind, f"{e.kind} ({e}), expected {kind}"
        return e
    raise AssertionError(f"no ProviderError ({kind} expected)")


def TestParryConnect():
    context = H.SetUpApp()
    world = P.World()

    # Making it asks nothing; Connect finds the tournament's and event's ids
    provider = P.NewProvider(world, context, connect=False)
    assert world.calls == [] and provider.event_id is None
    assert provider.Connect() == P.URL
    assert (provider.tournament_id, provider.event_id) == (P.TOURNAMENT_ID, P.EVENT_ID)
    assert world.calls == ["GetTournament"]

    # What can go wrong, by kind
    for code, kind in [
        (grpc.StatusCode.UNAUTHENTICATED, KIND_AUTH),
        (grpc.StatusCode.PERMISSION_DENIED, KIND_AUTH),
        (grpc.StatusCode.NOT_FOUND, KIND_NOT_FOUND),
        (grpc.StatusCode.UNAVAILABLE, KIND_TRANSIENT),
        (grpc.StatusCode.DEADLINE_EXCEEDED, KIND_TRANSIENT),
    ]:
        world.fail = code
        provider = P.NewProvider(world, context, connect=False)
        Raises(provider.Connect, kind)
        # ...and it can be tried again
        world.fail = None
        assert provider.Connect() == P.URL and provider.event_id == P.EVENT_ID

    # A tournament that isn't there, an event that isn't in the tournament
    provider = P.NewProvider(world, context, url="https://parry.gg/nope/singles", connect=False)
    Raises(provider.Connect, KIND_NOT_FOUND)
    provider = P.NewProvider(world, context, url="https://parry.gg/weekly/doubles", connect=False)
    error = Raises(provider.Connect, KIND_NOT_FOUND)
    assert "doubles" in str(error) and provider.event_id is None
    # An admin link is its event's
    provider = P.NewProvider(
        world, context, url="https://parry.gg/weekly/_manage/singles/main/bracket", connect=False
    )
    provider.Connect()
    assert provider.event_id == P.EVENT_ID


def TestParryCaches():
    context = H.SetUpApp()
    world = P.World()
    provider = P.NewProvider(world, context)
    now = [1000.0]
    import src.TournamentDataProvider.ParryGGDataProvider as module

    realTime = module.time.monotonic
    module.time.monotonic = lambda: now[0]
    try:
        # Phases and streams are asked for once, then kept a minute
        world.calls.clear()
        assert list(provider._get_phases()) == [P.PHASE_ID]
        assert list(provider._get_streams()) == [P.STREAM_ID]
        provider._get_phases()
        provider._get_streams()
        assert world.calls == ["GetEvent", "GetTournamentStreams"], world.calls
        now[0] += provider.CACHE_SECS + 1
        world.stream.display_name = "Renamed"
        assert provider._get_streams()[P.STREAM_ID]["display_name"] == "Renamed"
        provider._get_phases()
        assert world.calls.count("GetEvent") == 2 and world.calls.count("GetTournamentStreams") == 2

        # A refresh that fails: the last ones loaded, and asked again next time
        now[0] += provider.CACHE_SECS + 1
        world.fail = grpc.StatusCode.UNAVAILABLE
        assert list(provider._get_phases(required=True)) == [P.PHASE_ID]
        assert provider._get_streams()[P.STREAM_ID]["display_name"] == "Renamed"
        world.fail = None
        world.calls.clear()
        provider._get_phases()
        provider._get_streams()
        assert world.calls == ["GetEvent", "GetTournamentStreams"], "the failure was cached"

        # Never loaded and failing: nothing is kept, so it's asked again
        fresh = P.NewProvider(world, context)
        world.fail = grpc.StatusCode.UNAVAILABLE
        assert fresh._get_phases() == {} and fresh._get_streams() == {}
        Raises(lambda: fresh._get_phases(required=True), KIND_TRANSIENT)
        Raises(lambda: fresh._get_streams(required=True), KIND_TRANSIENT)
        assert fresh.GetStations() == [] and fresh.GetMatches() == []
        world.fail = None
        assert list(fresh._get_phases()) == [P.PHASE_ID]
        assert [s["identifier"] for s in fresh.GetStations()] == ["Renamed"]
        assert len(fresh.GetMatches(getFinished=True)) == 3

        # A linked start.gg account that couldn't be asked for isn't "none"
        world.fail = {"GetUser": grpc.StatusCode.UNAVAILABLE}
        assert fresh._get_linked_startgg_account("u1") is None
        assert not fresh._linked_startgg_known("u1")
        assert fresh._fetch_startgg_mains("u1") == {}
        assert "u1" not in (fresh._startgg_mains_cache or {}), "a failure was cached as no mains"
        world.fail = None
        assert fresh._get_linked_startgg_account("u1") is None and fresh._linked_startgg_known("u1")
        assert fresh._fetch_startgg_mains("u1") == {}
        assert fresh._startgg_mains_cache == {"u1": {}}, "no linked account: no mains, kept"
    finally:
        module.time.monotonic = realTime


if __name__ == "__main__":
    for test in [
        TestSignatures,
        TestChecker,
        TestParryShapes,
        TestFailedIsNotEmpty,
        TestParryConnect,
        TestParryCaches,
    ]:
        test()
        print(f"{test.__name__}: OK")
    print("All provider contract checks passed")
