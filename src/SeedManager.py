import os
import traceback

import orjson
from loguru import logger
from qtpy.QtCore import QObject, Signal

from .PlayerDB import PlayerDB


class SeedManagerSignals(QObject):
    # A player's seed changed. Empty tag when every seed may have changed.
    seed_changed = Signal(str)


class SeedManager:
    """Seeds set by hand, on top of the ones imported with the entrants.

    Imported seeds live in the player DB entries ("seed") and aren't saved.
    Seeds set here are saved to user_data/seeds.json with the event they were
    made for, and are dropped when a different event is loaded. With no event
    loaded they are kept, so everything can be seeded by hand.
    """

    signals = SeedManagerSignals()
    path = "./user_data/seeds.json"
    # tag (prefix + gamerTag) -> seed. 0 means "no seed".
    overrides = {}
    # URL of the event the seeds were set for, "" for none
    event = ""

    @staticmethod
    def Load():
        try:
            if os.path.exists(SeedManager.path):
                with open(SeedManager.path, "rb") as f:
                    data = orjson.loads(f.read())
                SeedManager.event = data.get("event") or ""
                SeedManager.overrides = {
                    str(tag): int(seed) for tag, seed in (data.get("seeds") or {}).items()
                }
        except Exception:
            logger.error(traceback.format_exc())
            SeedManager.overrides = {}

    @staticmethod
    def Save():
        try:
            with open(SeedManager.path, "wb") as f:
                f.write(
                    orjson.dumps(
                        {"event": SeedManager.event, "seeds": SeedManager.overrides},
                        option=orjson.OPT_INDENT_2,
                    )
                )
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def GetImportedSeed(tag):
        player = PlayerDB.database.get(tag)
        if player is None:
            return None
        seed = player.get("seed")
        try:
            return int(seed) if seed is not None else None
        except TypeError, ValueError:
            return None

    @staticmethod
    def GetOverride(tag):
        return SeedManager.overrides.get(tag)

    @staticmethod
    def GetSeed(tag):
        """The seed to show for a player: the one set by hand, else the imported one."""
        override = SeedManager.overrides.get(tag)
        if override is not None:
            return override
        return SeedManager.GetImportedSeed(tag)

    @staticmethod
    def SetSeed(tag, seed):
        if not tag:
            return
        SeedManager.overrides[tag] = max(0, int(seed))
        SeedManager.Save()
        SeedManager.signals.seed_changed.emit(tag)

    @staticmethod
    def ResetSeed(tag):
        """Goes back to the imported seed."""
        if SeedManager.overrides.pop(tag, None) is not None:
            SeedManager.Save()
            SeedManager.signals.seed_changed.emit(tag)

    @staticmethod
    def RenamePlayer(oldTag, newTag):
        if oldTag == newTag or oldTag not in SeedManager.overrides:
            return
        SeedManager.overrides[newTag] = SeedManager.overrides.pop(oldTag)
        SeedManager.Save()
        SeedManager.signals.seed_changed.emit(newTag)

    @staticmethod
    def ClearAll():
        SeedManager.overrides = {}
        SeedManager.Save()
        SeedManager.signals.seed_changed.emit("")

    @staticmethod
    def EventLoaded(url):
        """Drops the seeds set for another event. Unsetting the event keeps them."""
        url = url or ""
        if not url or url == SeedManager.event:
            return
        hadSeeds = len(SeedManager.overrides) > 0
        if hadSeeds:
            logger.info("Another event was loaded, clearing the seeds set by hand")
        SeedManager.overrides = {}
        SeedManager.event = url
        SeedManager.Save()
        if hadSeeds:
            SeedManager.signals.seed_changed.emit("")


SeedManager.Load()
