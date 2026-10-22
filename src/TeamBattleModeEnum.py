from enum import Enum

from qtpy.QtWidgets import *


# Enum for Selecting Widget Mode (Mainly for dropdown and switch/if statements)
class TeamBattleModeEnum(Enum):
    # STOCK POOL
    # Each player will have an active checkbox, an "eliminated" checkbox, a spinner with X number of stocks
    # remaining (automatically controlled by dynamic spinner in the top bar).
    # As each stock decreases, the system will export the total pool of stocks remaining and total "score".
    # When a player hits 0 remaining stocks, the system will automatically declare them as "eliminated" (toggleable).
    STOCK_POOL = "Stock Pool (Platformers)"

    # FIRST TO
    # Each player will have an active checkbox, an "eliminated" checkbox, a spinner with X current score of a player to the "First To" amount.
    # When increasing player score, if the "First To" amount is reached, the system will reset the player's points
    # and declare the other player "eliminated" (toggleable).
    # [Easiest way to do it without needing to handle for other cases, and can be handled through signal calls]
    FIRST_TO = "First To (First To X Team Individuals)"

    # LIMITED PLAYS
    # The same as the mode they're named after, but only a set number of each team's players play:
    # the others wait on deck until the team picks them, and a team is out once that many are eliminated.
    STOCK_POOL_LIMITED = "Stock Pool (Limited Plays)"
    FIRST_TO_LIMITED = "First To (Limited Plays)"

    @property
    def base(self) -> "TeamBattleModeEnum":
        """The mode the scoring follows: STOCK_POOL or FIRST_TO."""
        if self is TeamBattleModeEnum.STOCK_POOL_LIMITED:
            return TeamBattleModeEnum.STOCK_POOL
        if self is TeamBattleModeEnum.FIRST_TO_LIMITED:
            return TeamBattleModeEnum.FIRST_TO
        return self

    @property
    def limited(self) -> bool:
        """Whether only some of each team's players play."""
        return self in (TeamBattleModeEnum.STOCK_POOL_LIMITED, TeamBattleModeEnum.FIRST_TO_LIMITED)

    def WithLimited(self, limited: bool) -> "TeamBattleModeEnum":
        """The mode with the same scoring, with or without limited plays."""
        if not limited:
            return self.base
        if self.base is TeamBattleModeEnum.FIRST_TO:
            return TeamBattleModeEnum.FIRST_TO_LIMITED
        return TeamBattleModeEnum.STOCK_POOL_LIMITED

    def translated(self):
        return QApplication.translate("app", self.value)

    # Allows matching the current spinbox value to the enum to allow easier matching in code.
    # Also works across the language barrier thanks to using the translations for values :D
    # Ex. "Stock Pool (Smash)" will match to STOCK_POOL
    def MatchToMode(battleMode: str):
        return next(
            (mode for mode in TeamBattleModeEnum if mode.translated() == battleMode),
            TeamBattleModeEnum.STOCK_POOL,
        )
