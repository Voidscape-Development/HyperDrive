# Placement math shared by the Upset Factor and the Seed Performance Rating
# (SPR). Both count the "placement rounds" a seed or a placement is worth: the
# number of distinct placements above it in a bracket of that type (in double
# elimination 1st, 2nd, 3rd, 4th, 5th, 7th, 9th, 13th... are 0, 1, 2, 3, 4,
# 5, 6, 7...). A seed is worth the rounds of the placement it's expected to
# get, so comparing the two tells how far a player out- or under-performed.
import math

SINGLE_ELIMINATION = "SINGLE_ELIMINATION"
DOUBLE_ELIMINATION = "DOUBLE_ELIMINATION"


def PlacementRounds(bracket_type, x):
    """Placement rounds above seed or placement `x` in a bracket of that type
    (0 for types the math doesn't cover, e.g. round robin)."""
    # Due to how the logs work, the first seed/placement is always 0
    if x <= 1:
        return 0

    single_elim_calc = math.floor(math.log2(x - 1))
    double_elim_calc = math.ceil(math.log2((2 * x) / 3))

    if bracket_type == DOUBLE_ELIMINATION:
        return single_elim_calc + double_elim_calc
    elif bracket_type == SINGLE_ELIMINATION:
        return single_elim_calc
    else:
        return 0


def EventBracketType(phase_types):
    """The bracket type to rate an event's placements with, from the types of
    its phases. Double elimination if any phase is, single elimination if a
    phase is and none is double, and double elimination otherwise (unknown,
    or only phases like round robin that SPR has no math for)."""
    phase_types = [t for t in phase_types or [] if t]
    if DOUBLE_ELIMINATION in phase_types:
        return DOUBLE_ELIMINATION
    if SINGLE_ELIMINATION in phase_types:
        return SINGLE_ELIMINATION
    return DOUBLE_ELIMINATION


def SeedPerformanceRating(bracket_type, seed, placement):
    """How many placement rounds better (positive) or worse (negative) than
    their seed a player placed, or None without a seed and a placement."""
    try:
        seed = int(seed)
        placement = int(placement)
    except (TypeError, ValueError):
        return None
    if seed < 1 or placement < 1:
        return None
    if bracket_type not in (SINGLE_ELIMINATION, DOUBLE_ELIMINATION):
        bracket_type = DOUBLE_ELIMINATION
    return PlacementRounds(bracket_type, seed) - PlacementRounds(bracket_type, placement)
