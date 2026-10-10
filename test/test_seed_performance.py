# Checks the placement math behind the Upset Factor and the Seed Performance
# Rating (SPR), and how an event's bracket type is picked from its phases.
# Run from the repository root: python test/test_seed_performance.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.Helpers.SeedPerformance import (
    DOUBLE_ELIMINATION,
    SINGLE_ELIMINATION,
    EventBracketType,
    PlacementRounds,
    SeedPerformanceRating,
)


def TestPlacementRounds():
    # Each double elimination placement is one round below the previous one
    placements = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65]
    assert [PlacementRounds(DOUBLE_ELIMINATION, p) for p in placements] == list(
        range(len(placements))
    )
    # Seeds share the rounds of the placement they're expected to get
    assert PlacementRounds(DOUBLE_ELIMINATION, 6) == PlacementRounds(DOUBLE_ELIMINATION, 5)
    assert PlacementRounds(DOUBLE_ELIMINATION, 12) == PlacementRounds(DOUBLE_ELIMINATION, 9)
    # Single elimination: 1st, 2nd, 3rd, 5th, 9th, 17th...
    assert [PlacementRounds(SINGLE_ELIMINATION, p) for p in [1, 2, 3, 5, 9, 17]] == [
        0,
        0,
        1,
        2,
        3,
        4,
    ]
    assert PlacementRounds("ROUND_ROBIN", 9) == 0


def TestSeedPerformanceRating():
    # Placing as seeded
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 1, 1) == 0
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 6, 5) == 0
    # 9th seed placing 5th beat their seed by two rounds (9th -> 7th -> 5th)
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 9, 5) == 2
    # 1st seed placing 5th
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 1, 5) == -4
    # Single elimination counts fewer rounds
    assert SeedPerformanceRating(SINGLE_ELIMINATION, 9, 5) == 1
    # Unknown types fall back to double elimination
    assert SeedPerformanceRating("SWISS", 9, 5) == 2
    assert SeedPerformanceRating(None, 9, 5) == 2
    # Seeds and placements can come in as strings
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, "9", "5") == 2
    # No rating without a seed or a placement
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, None, 5) is None
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 0, 5) is None
    assert SeedPerformanceRating(DOUBLE_ELIMINATION, 9, None) is None


def TestEventBracketType():
    assert EventBracketType(["ROUND_ROBIN", "DOUBLE_ELIMINATION"]) == DOUBLE_ELIMINATION
    assert EventBracketType(["SINGLE_ELIMINATION", "DOUBLE_ELIMINATION"]) == DOUBLE_ELIMINATION
    assert EventBracketType(["ROUND_ROBIN", "SINGLE_ELIMINATION"]) == SINGLE_ELIMINATION
    assert EventBracketType(["SINGLE_ELIMINATION", None, ""]) == SINGLE_ELIMINATION
    assert EventBracketType(["ROUND_ROBIN"]) == DOUBLE_ELIMINATION
    assert EventBracketType([]) == DOUBLE_ELIMINATION
    assert EventBracketType(None) == DOUBLE_ELIMINATION


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
