# Checks StartGGDataProvider against recorded start.gg responses (made with
# scripts/record_startgg_fixtures.py, anonymized), offline:
# - Contract: every method's result has the keys and types the app uses.
#   These are what the provider promises today, including where methods
#   disagree with each other (a player's tag is gamerTag in sets, name in
#   future sets and gamertag in completed sets).
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startgg_harness as H

EXPECTED = os.path.join(H.FIXTURE_DIR, "expected.json")

NONE = type(None)
INT_OR_NONE = (int, NONE)
STR_OR_NONE = (str, NONE)


class Optional:
    """A key that's only there when there's a value for it"""

    def __init__(self, types):
        self.types = types


# =====================================================
# CONTRACT
# =====================================================
# {key: type or (types)}: the keys a result must have, with their types
TOURNAMENT_DATA = {
    "tournamentName": str,
    "eventName": str,
    "numEntrants": int,
    "startAt": int,
    "endAt": int,
    "eventStartAt": int,
    "address": str,
    "logo": str,
    "banner": str,
    "shortLink": str,
}
PHASE = {"id": int, "name": str, "groups": list}
PHASE_GROUP_ITEM = {"id": int, "name": str, "bracketType": str}
BRACKET_SET = {
    "id": str,
    "identifier": str,
    "name": str,
    "round": int,
    "score": list,
    "finished": bool,
    "winnerSlot": INT_OR_NONE,
    "slots": list,
}
BRACKET_SLOT = {
    "prereqType": str,
    "prereqId": STR_OR_NONE,
    "entrantId": STR_OR_NONE,
    "player": INT_OR_NONE,
    "placement": INT_OR_NONE,
}
BRACKET_SET_RESULT = {
    "id": str,
    "score": list,
    "finished": bool,
    "winnerSlot": INT_OR_NONE,
    "slots": list,
}
PLAYER = {
    "gamerTag": str,
    "prefix": STR_OR_NONE,
    "name": STR_OR_NONE,
    "id": list,
    "socials": dict,
    "avatar": Optional(str),
    "twitter": Optional(str),
    "pronoun": Optional(str),
    "state_code": Optional(str),
}
SET_LIST_ITEM = {
    "id": int,
    "round": int,
    "round_name": str,
    "tournament_phase": str,
    "bracket_type": str,
    "state": int,
    "p1_name": str,
    "p2_name": str,
    "team1score": int,
    "team2score": int,
    "entrants": list,
    "entrant_ids": list,
    "games": list,
    "isPools": bool,
    "station": (int, str),
    "stream": STR_OR_NONE,
}
SET = {
    **SET_LIST_ITEM,
    "station": str,
    "p1_seed": int,
    "p2_seed": int,
    "isOnline": bool,
    "has_selection_data": Optional(bool),
    "team1losers": bool,
    "team2losers": bool,
    "bestOf": INT_OR_NONE,
    "ruleset": dict,
    "stage_strike": dict,
    "strikedBy": list,
    "currPlayer": int,
}
SET_PLAYER = {**PLAYER, "seed": int, "mains": Optional(list), "city": Optional(str)}
GAME = {"winner": INT_OR_NONE, "stage": STR_OR_NONE, "characters": list}
FUTURE_SET = {
    "id": int,
    "match": str,
    "phase": str,
    "event": str,
    "best_of": int,
    "best_of_text": str,
    "state": int,
    "station": INT_OR_NONE,
    "isCurrentEvent": bool,
    "team": dict,
}
FUTURE_TEAM = {"teamName": str, "seed": INT_OR_NONE, "losers": bool, "player": dict}
FUTURE_PLAYER = {
    "name": str,
    "team": STR_OR_NONE,
    "mergedName": str,
    "real_name": STR_OR_NONE,
    "id": list,
    "twitter": str,
    "pronoun": str,
    "socials": dict,
    "country": dict,
    "state": dict,
    "online_avatar": str,
}
STATION = {"id": int, "identifier": (int, str), "type": str, "stream": str}
COMPLETED_SET = {
    "phase_id": str,
    "phase_name": str,
    "round_name": str,
    "bracket_type": str,
    "winner_score": int,
    "loser_score": int,
    "winner_seed": INT_OR_NONE,
    "loser_seed": INT_OR_NONE,
    "winner_team_name": str,
    "loser_team_name": str,
    "winner_team": dict,
    "loser_team": dict,
    "upset_factor": int,
}
COMPLETED_PLAYER = {
    "gamertag": str,
    "sponsor": str,
    "country": dict,
    "state": dict,
    "characters": dict,
}
SET_DURATION = {
    "id": int,
    "startedAt": INT_OR_NONE,
    "completedAt": INT_OR_NONE,
    "totalGames": INT_OR_NONE,
    "dq": bool,
}
STANDING = {"wins": int, "losses": int, "winPercentage": str, "players": list}
STANDING_PLAYER = {**PLAYER, "seed": int, "mains": dict, "startggMains": list}
LAST_SET = {
    "phase_id": str,
    "phase_name": str,
    "round_name": str,
    "player1_name": str,
    "player1_team": str,
    "player1_score": int,
    "player1_seed": INT_OR_NONE,
    "player2_name": str,
    "player2_team": STR_OR_NONE,
    "player2_score": int,
    "player2_seed": INT_OR_NONE,
    "player_char": dict,
    "oponent_char": dict,
}
HISTORY_SET = {
    "placement": int,
    "seed": INT_OR_NONE,
    "entrants": int,
    "event_name": str,
    "tournament_name": str,
    "tournament_picture": str,
    "event_date": int,
    "bracket_type": str,
}
RECENT_SET = {
    "id": int,
    "tournament": str,
    "event": str,
    "phase_id": str,
    "phase_name": str,
    "round": str,
    "score": list,
    "winner": int,
    "online": bool,
    "timestamp": int,
    "p1_char": dict,
    "p2_char": dict,
}
ENTRANT = {**PLAYER, "seed": int, "startgg_user_slug": str}

failures = []


def Check(name, value, shape):
    if not isinstance(value, dict):
        failures.append(f"{name}: expected an object, got {type(value).__name__}")
        return
    for key, types in shape.items():
        optional = isinstance(types, Optional)
        types = types.types if optional else types
        if key not in value:
            if not optional:
                failures.append(f"{name}: no {key}")
        elif not isinstance(value[key], types):
            failures.append(f"{name}.{key}: {type(value[key]).__name__}, expected {types}")


def CheckAll(name, values, shape, atLeast=1):
    values = list(values)
    if len(values) < atLeast:
        failures.append(f"{name}: {len(values)} results, expected at least {atLeast}")
    for i, value in enumerate(values):
        Check(f"{name}[{i}]", value, shape)


def CheckContract(out):
    Check("tournament_data", out["tournament_data"], TOURNAMENT_DATA)
    if not isinstance(out["icon_url"], str) or not out["icon_url"].startswith("https://"):
        failures.append(f"icon_url: {out['icon_url']!r}")

    CheckAll("phases", out["phases"], PHASE)
    CheckAll("phases.groups", [g for p in out["phases"] for g in p["groups"]], PHASE_GROUP_ITEM)
    group = out["phase_group"]
    CheckAll("phase_group.sets", group["sets"], BRACKET_SET)
    CheckAll("phase_group.slots", [s for x in group["sets"] for s in x["slots"]], BRACKET_SLOT)
    CheckAll("phase_group.players", [p for e in group["entrants"] for p in e["players"]], PLAYER)
    CheckAll("phase_group_sets", out["phase_group_sets"]["sets"], BRACKET_SET_RESULT)

    CheckAll("matches_all", out["matches_all"], SET_LIST_ITEM)
    if out["matches_open"] != []:
        failures.append("matches_open: the event is over, expected no open sets")
    matches = list(out["match"].values())
    CheckAll("match", matches, SET)
    CheckAll("match.players", [p for m in matches for e in m["entrants"] for p in e], SET_PLAYER)
    CheckAll("match.games", [g for m in matches for g in m["games"]], GAME)

    futures = list(out["future_match"].values())
    CheckAll("future_match", futures, FUTURE_SET)
    CheckAll("future_match.team", [t for f in futures for t in f["team"].values()], FUTURE_TEAM)
    CheckAll(
        "future_match.player",
        [p for f in futures for t in f["team"].values() for p in t["player"].values()],
        FUTURE_PLAYER,
    )
    CheckAll("future_matches_list", out["future_matches_list"].values(), FUTURE_SET)

    CheckAll("stations", out["stations"], STATION)
    streams = out["streams_and_stations"]
    CheckAll("streams_and_stations.streams", streams["streams"], {"id": int, "name": str})
    CheckAll(
        "streams_and_stations.stations",
        streams["stations"],
        {"id": int, "number": int, "stream": str},
    )

    CheckAll("completed_sets", out["completed_sets"], COMPLETED_SET)
    CheckAll(
        "completed_sets.players",
        [p for c in out["completed_sets"] for p in c["winner_team"].values()],
        COMPLETED_PLAYER,
    )
    CheckAll("set_durations", out["set_durations"], SET_DURATION)
    CheckAll("standings", out["standings"], STANDING)
    CheckAll(
        "standings.players", [p for t in out["standings"] for p in t["players"]], STANDING_PLAYER
    )

    for n in (1, 2):
        Check(f"last_sets_{n}", out[f"last_sets_{n}"], {"playerNumber": str, "last_sets": list})
        CheckAll(f"last_sets_{n}.sets", out[f"last_sets_{n}"]["last_sets"], LAST_SET)
        Check(
            f"history_sets_{n}",
            out[f"history_sets_{n}"],
            {"playerNumber": str, "history_sets": list},
        )
        CheckAll(f"history_sets_{n}.sets", out[f"history_sets_{n}"]["history_sets"], HISTORY_SET)
    Check("recent_sets", out["recent_sets"], {"sets": list, "request_time": int})
    CheckAll("recent_sets.sets", out["recent_sets"]["sets"], RECENT_SET)

    CheckAll("entrants_added", out["entrants_added"], ENTRANT)
    for slug, mains in out["user_mains"].items():
        if not mains.get("ssbu"):
            failures.append(f"user_mains[{slug}]: no Ultimate mains")


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
