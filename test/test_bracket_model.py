# Checks the bracket widget's bracket model: generated brackets of every
# type and size, brackets loaded from start.gg's sets, results, placements,
# editing by hand and phases linked to each other.
# Run from the repository root: python test/test_bracket_model.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

localeHelper = types.ModuleType("src.Helpers.LocaleHelper")


class LocaleHelper:
    matchNames = {}


localeHelper.LocaleHelper = LocaleHelper
helpers = types.ModuleType("src.Helpers")
helpers.__path__ = [os.path.abspath("src/Helpers")]
sys.modules["src.Helpers"] = helpers
sys.modules["src.Helpers.LocaleHelper"] = localeHelper

from src.BracketModel import *


def Play(bracket, better=lambda a, b: a < b):
    """Plays every match in play order, the better player (lower id by
    default) winning 2-0, until nothing is left to play."""
    for _ in range(len(bracket.matches) + 1):
        played = False
        for m in bracket.order:
            p1, p2 = m.players
            if m.finished or m.isBye or m.notNeeded or p1 <= 0 or p2 <= 0:
                continue
            m.score = [2, 0] if better(p1, p2) else [0, 2]
            m.finished = True
            bracket.Resolve()
            played = True
            break
        if not played:
            return


def Visible(bracket, side):
    return [len(column) for column in bracket.Columns(side)]


def TestSingleEliminationSizes():
    for n in range(2, 40):
        bracket = GenerateBracket(TYPE_SINGLE_ELIMINATION, list(range(1, n + 1)))
        real = [m for m in bracket.matches.values() if not m.isBye]
        # One match per player knocked out
        assert len(real) == n - 1, (n, len(real))
        Play(bracket)
        results = bracket.Results()
        assert results[0] == 1, (n, results)
        assert sorted(results) == list(range(1, n + 1)), (n, results)
        # No match against a bye is shown
        assert all(not m.isBye for column in bracket.Columns(SIDE_WINNERS) for m in column)


def TestDoubleEliminationSizes():
    for n in range(2, 40):
        bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, n + 1)))
        real = [m for m in bracket.matches.values() if not m.isBye]
        # Everyone but the champion loses twice, plus the grand final
        # (reset left out)
        assert len(real) == 2 * (n - 1) + 1 - 1 + 1, (n, len(real))
        Play(bracket)
        results = bracket.Results()
        assert results[:2] == [1, 2], (n, results)
        assert sorted(results) == list(range(1, n + 1)), (n, results)
        # Grand final won by the winners side player: no reset
        reset = next(m for m in bracket.matches.values() if m.isReset)
        assert reset.notNeeded


def TestDoubleEliminationNoEarlyRematches():
    # Lower seeds win: nobody plays someone again before the losers final,
    # except when the losers side is too small to avoid it
    for n in (8, 16, 32, 64):
        bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, n + 1)))
        Play(bracket)
        seen = {}
        for m in bracket.order:
            if m.isBye or m.players[0] <= 0 or m.players[1] <= 0:
                continue
            pair = frozenset(m.players)
            if (
                pair in seen
                and m.side == SIDE_LOSERS
                and m.column < len(bracket.Columns(SIDE_LOSERS)) - 1
            ):
                raise AssertionError(f"{n}: rematch {sorted(pair)} in losers round {m.column}")
            seen[pair] = m


def TestGrandFinalReset():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, [1, 2, 3, 4])
    # The losers side player wins the grand final
    Play(bracket, better=lambda a, b: a < b)
    gf = next(m for m in bracket.matches.values() if m.isGrandFinal)
    reset = next(m for m in bracket.matches.values() if m.isReset)
    assert gf.players == [1, 2]
    gf.score = [1, 3]
    bracket.Resolve()
    assert not reset.notNeeded
    assert reset.players == [1, 2]
    reset.score = [3, 2]
    reset.finished = True
    bracket.Resolve()
    assert bracket.Results()[:2] == [1, 2]
    assert bracket.Champion() == 1

    # Without a reset
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, [1, 2, 3, 4], grandFinalReset=False)
    assert not any(m.isReset for m in bracket.matches.values())
    Play(bracket, better=lambda a, b: a > b)
    assert bracket.Results()[:2] == [4, 3], bracket.Results()


def TestPlacements():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 17)))
    places = sorted(
        {m.loserPlacement for m in bracket.matches.values() if m.loserPlacement is not None}
    )
    assert places == [2, 3, 4, 5, 7, 9, 13], places

    bracket = GenerateBracket(TYPE_SINGLE_ELIMINATION, list(range(1, 9)), thirdPlace=True)
    third = next(m for m in bracket.matches.values() if m.side == SIDE_THIRD_PLACE)
    Play(bracket)
    assert sorted(third.players) == [3, 4], third.players
    assert bracket.Results() == [1, 2, 3, 4, 5, 6, 7, 8], bracket.Results()

    # 6 players: byes don't take placements
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 7)))
    places = sorted(
        {
            m.loserPlacement
            for m in bracket.matches.values()
            if m.loserPlacement is not None and not m.isBye
        }
    )
    assert places == [2, 3, 4, 5], places


def TestTopN():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 33)))
    top8 = [m for m in bracket.matches.values() if bracket.InTopN(m, 8) and not m.isBye]
    # Winners semis (2) and final, losers rounds for 7th (2), 5th (2), 4th
    # and 3rd, grand final and reset
    assert len(top8) == 2 + 1 + 2 + 2 + 1 + 1 + 2, len(top8)


def TestProgressionsOut():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 17)), progressionsOut=4)
    assert not any(m.side == SIDE_GRAND_FINAL for m in bracket.matches.values())
    Play(bracket)
    results = bracket.Results()
    assert len(results) == 4 and sorted(results) == [1, 2, 3, 4], results

    bracket = GenerateBracket(TYPE_SINGLE_ELIMINATION, list(range(1, 17)), progressionsOut=4)
    Play(bracket)
    assert sorted(bracket.Results()) == [1, 2, 3, 4], bracket.Results()


def TestLosersSeeds():
    # Top 8 from pools: 4 start in winners, 4 in losers
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, [1, 2, 3, 4], losersSeeds=[5, 6, 7, 8])
    assert Visible(bracket, SIDE_WINNERS) == [2, 1], Visible(bracket, SIDE_WINNERS)
    assert Visible(bracket, SIDE_LOSERS) == [2, 2, 1, 1], Visible(bracket, SIDE_LOSERS)
    firstLosers = bracket.Columns(SIDE_LOSERS)[0]
    assert sorted(p for m in firstLosers for p in m.players) == [5, 6, 7, 8]
    Play(bracket)
    assert bracket.Results()[:2] == [1, 2]
    assert sorted(bracket.Results()) == list(range(1, 9))


def TestRoundNames():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 9)))
    winners = [bracket.RoundName(SIDE_WINNERS, c[0].column) for c in bracket.Columns(SIDE_WINNERS)]
    assert winners == ["Winners Quarter-Final", "Winners Semi-Final", "Winners Final"], winners
    losers = [bracket.RoundName(SIDE_LOSERS, c[0].column) for c in bracket.Columns(SIDE_LOSERS)]
    assert losers[-3:] == ["Losers Quarter-Final", "Losers Semi-Final", "Losers Final"], losers
    gf = [
        bracket.RoundName(SIDE_GRAND_FINAL, c[0].column)
        for c in bracket.Columns(SIDE_GRAND_FINAL, includeHidden=True)
    ]
    assert gf == ["Grand Final", "Grand Final Reset"], gf

    bracket.roundNames[Bracket.RoundKey(SIDE_WINNERS, 1)] = "Top 8"
    assert bracket.RoundName(SIDE_WINNERS, 1) == "Top 8"

    # 5 players: the first winners round only has one real set, and losers
    # round 1 is all byes so it isn't shown or counted
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 6)))
    losers = [bracket.RoundName(SIDE_LOSERS, c[0].column) for c in bracket.Columns(SIDE_LOSERS)]
    assert losers[0] in ("Losers Round 1", "Losers Quarter-Final"), losers


def TestEditing():
    bracket = GenerateBracket(TYPE_SINGLE_ELIMINATION, [1, 2, 3, 4])
    first = bracket.Columns(SIDE_WINNERS)[0]
    a, b = first
    assert a.players == [1, 4] and b.players == [2, 3]

    # Winner set by hand without a score
    bracket.SetWinner(a.id, 1)
    final = bracket.Columns(SIDE_WINNERS)[1][0]
    assert final.players[0] == 4

    # Swap two players
    bracket.SwapSlots(a.id, 0, b.id, 0)
    assert a.players == [2, 4] and b.players == [1, 3]
    assert bracket.HasOverrides()
    bracket.ClearOverrides()
    assert a.players == [1, 4]

    # Put a player in by hand
    bracket.SetSlotPlayer(final.id, 1, 3)
    assert final.players == [4, 3]

    # DQ loses
    bracket.SetScore(b.id, 0, -1)
    bracket.SetFinished(b.id, True)
    assert b.winnerSlot == 1

    bracket.ClearResult(a.id)
    assert a.winnerSlot is None and final.players[0] == PENDING


def TestSaveAndLoad():
    bracket = GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 11)))
    Play(bracket)
    bracket.roundNames["winners:1"] = "Pools"
    copy = Bracket.FromDict(bracket.ToDict())
    assert copy.Results() == bracket.Results()
    assert copy.roundNames == bracket.roundNames
    assert [m.identifier for m in copy.order] == [m.identifier for m in bracket.order]


# start.gg sets


def Seed(player):
    return {"prereqType": "seed", "prereqId": f"seed{player}", "player": player}


def Winner(setId):
    return {"prereqType": "set", "prereqId": setId, "placement": 1}


def Loser(setId):
    return {"prereqType": "set", "prereqId": setId, "placement": 2}


def Set(
    id, round, identifier, slots, score=(None, None), finished=False, name=None, winnerSlot=None
):
    return {
        "id": id,
        "round": round,
        "identifier": identifier,
        "name": name,
        "slots": slots,
        "score": list(score),
        "finished": finished,
        "winnerSlot": winnerSlot,
    }


def DoubleElim4(a1=Seed(1), a2=Seed(4)):
    # start.gg puts both grand final sets in the same round. The ids are in
    # a different order than the bracket on purpose.
    return [
        Set("90", 1, "B", [Seed(2), Seed(3)], (0, 2), True, "Winners Semi-Final"),
        Set("95", 1, "A", [a1, a2], (2, 0), True, "Winners Semi-Final"),
        Set("80", 2, "C", [Winner("95"), Winner("90")], (2, 1), True, "Winners Final"),
        Set("70", -1, "D", [Loser("95"), Loser("90")], (0, 2), True, "Losers Semi-Final"),
        Set("60", -2, "E", [Loser("80"), Winner("70")], (0, 2), True, "Losers Final"),
        Set("50", 3, "F", [Winner("80"), Winner("60")], name="Grand Final"),
        Set("51", 3, "G", [Winner("50"), Loser("50")], name="Grand Final Reset"),
    ]


def ByProvider(bracket, id):
    return next(m for m in bracket.matches.values() if m.providerId == id)


def TestProviderDoubleElimination():
    bracket = FromProviderSets(TYPE_DOUBLE_ELIMINATION, DoubleElim4(), 4)
    assert bracket.fromProvider
    assert Visible(bracket, SIDE_WINNERS) == [2, 1]
    assert Visible(bracket, SIDE_LOSERS) == [1, 1]
    # Ordered by where they lead, not by id
    assert [m.players for m in bracket.Columns(SIDE_WINNERS)[0]] == [[1, 4], [2, 3]]
    assert ByProvider(bracket, "80").players == [1, 3]
    assert ByProvider(bracket, "70").players == [4, 2]
    assert ByProvider(bracket, "60").players == [3, 2]
    gf = ByProvider(bracket, "50")
    reset = ByProvider(bracket, "51")
    assert gf.isGrandFinal and reset.isReset
    assert gf.players == [1, 2]
    assert gf.nextWin[0] == reset.id
    assert bracket.RoundName(SIDE_GRAND_FINAL, gf.column) == "Grand Final"
    assert bracket.RoundName(SIDE_LOSERS, 2) == "Losers Final"

    gf.score = [1, 3]
    gf.finished = True
    bracket.Resolve()
    assert reset.players == [1, 2] and not reset.notNeeded

    # Refreshing the results
    assert ApplyProviderUpdate(bracket, [{"id": "51", "score": [3, 0], "finished": True}])
    assert bracket.Results()[:2] == [1, 2]
    assert not ApplyProviderUpdate(bracket, [{"id": "new", "score": [0, 0]}])


def TestProviderByesAndMissingSets():
    bracket = FromProviderSets(TYPE_DOUBLE_ELIMINATION, DoubleElim4(a2={"prereqType": "bye"}), 3)
    assert ByProvider(bracket, "95").players == [1, BYE]
    assert ByProvider(bracket, "70").players == [BYE, 2]
    assert ByProvider(bracket, "60").players == [3, 2]
    assert ByProvider(bracket, "80").players == [1, 3]

    bracket = FromProviderSets(
        TYPE_DOUBLE_ELIMINATION,
        [
            Set("1", 1, "A", [Winner("missing"), Seed(1)]),
            Set("2", -1, "B", [Loser("missing"), Seed(2)]),
        ],
        2,
    )
    assert ByProvider(bracket, "1").players == [PENDING, 1]
    assert ByProvider(bracket, "2").players == [BYE, 2]


def TestProviderSingleEliminationThirdPlace():
    bracket = FromProviderSets(
        TYPE_SINGLE_ELIMINATION,
        [
            Set("1", 1, "A", [Seed(1), Seed(4)], (None, None), True, winnerSlot=1),
            Set("2", 1, "B", [Seed(2), Seed(3)], (3, 1), True),
            Set("3", 2, "D", [Loser("1"), Loser("2")], name="3rd Place Match"),
            Set("4", 2, "C", [Winner("1"), Winner("2")], name="Final"),
        ],
        4,
    )
    assert ByProvider(bracket, "3").side == SIDE_THIRD_PLACE
    assert ByProvider(bracket, "4").players == [4, 2]
    assert ByProvider(bracket, "3").players == [1, 3]


def TestProviderInvalid():
    for sets in [
        [],
        [Set("1", 0, "A", [Seed(1), Seed(2)])],
        [Set("1", 1, "A", [Winner("2"), Seed(1)]), Set("2", 1, "B", [Winner("1"), Seed(2)])],
    ]:
        try:
            FromProviderSets(TYPE_DOUBLE_ELIMINATION, sets, 2)
        except ValueError:
            continue
        raise AssertionError(f"Expected {sets} to be rejected")


# Round robin and swiss


def TestRoundRobin():
    for n in range(2, 10):
        bracket = GenerateBracket(TYPE_ROUND_ROBIN, list(range(1, n + 1)))
        pairs = [frozenset(m.players) for m in bracket.matches.values()]
        assert len(pairs) == n * (n - 1) // 2 and len(set(pairs)) == len(pairs), n
        Play(bracket)
        assert bracket.PoolFinished()
        assert bracket.Results() == list(range(1, n + 1)), (n, bracket.Results())


def TestSwiss():
    bracket = GenerateBracket(TYPE_SWISS, list(range(1, 10)), swissRounds=4)
    for _ in range(4):
        Play(bracket)
        if bracket.CanPairNextRound():
            bracket.PairNextRound()
    assert len(bracket.PoolRounds()) == 4
    pairs = [frozenset(m.players) for m in bracket.matches.values()]
    assert len(set(pairs)) == len(pairs), "rematch"
    # Each round, someone sits out
    assert all(len(b) == 1 for b in bracket.byes.values())
    assert bracket.Results()[0] == 1
    assert bracket.UnpairLastRound()
    assert len(bracket.PoolRounds()) == 3


def TestProviderPool():
    sets = [
        Set("1", 1, "A", [Seed(1), Seed(2)], (2, 0), True),
        Set("2", 1, "B", [Seed(3), {"prereqType": "bye"}]),
        Set("3", 2, "C", [Seed(1), Seed(3)], (1, 2), True),
        Set(
            "4",
            2,
            "D",
            [{"prereqType": "set", "prereqId": None}, {"prereqType": "set", "prereqId": None}],
        ),
    ]
    bracket = FromProviderSets(TYPE_SWISS, sets, 3, entrantIds=["e1", "e2", "e3"])
    assert len(bracket.matches) == 3
    assert bracket.byes == {"1": [3]}
    # Paired after being loaded
    assert ApplyProviderUpdate(
        bracket, [{"id": "4", "score": [0, 0], "slots": [{"entrantId": "e2"}, {"entrantId": "e3"}]}]
    )
    assert ByProvider(bracket, "4").players == [2, 3]


# Phases


def TestLinkedPhases():
    tournament = BracketTournament()
    pools = []
    for name, players in (("A", [1, 3, 5, 7]), ("B", [2, 4, 6, 8])):
        phase = BracketPhase(tournament.NewPhaseId(), name, TYPE_ROUND_ROBIN)
        phase.seedSources = [{"type": "player", "player": p} for p in players]
        phase.Generate(players)
        tournament.AddPhase(phase)
        pools.append(phase)

    top = BracketPhase(tournament.NewPhaseId(), "Top 4", TYPE_SINGLE_ELIMINATION)
    top.seedSources = SnakeSeeding([p.id for p in pools], 2)
    top.Generate(tournament.SeedPlayers(top))
    tournament.AddPhase(top)
    tournament.Resolve()
    assert top.bracket.seeds == [PENDING] * 4

    for pool in pools:
        Play(pool.bracket)
    tournament.Resolve()
    # 1st A, 1st B, 2nd B, 2nd A
    assert top.bracket.seeds == [1, 2, 4, 3], top.bracket.seeds
    Play(top.bracket)
    assert top.bracket.Results() == [1, 2, 3, 4] or top.bracket.Results()[:2] == [1, 2]

    assert tournament.DependsOn(top, pools[0])
    assert not tournament.DependsOn(pools[0], top)

    copy = BracketTournament.FromDict(tournament.ToDict())
    assert copy.GetPhase(top.id).bracket.seeds == [1, 2, 4, 3]

    tournament.RemovePhase(pools[0].id)
    assert top.seedSources[0] is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
