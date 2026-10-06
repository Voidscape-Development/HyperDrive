import os
import traceback

import orjson
from loguru import logger
from qtpy.QtCore import QObject, Signal

from .TSHPlayerDB import TSHPlayerDB


class TSHSeedManagerSignals(QObject):
    # A player's seed changed. Empty tag when every seed may have changed.
    seed_changed = Signal(str)


class TSHSeedManager:
    """Seeds set by hand, on top of the ones imported with the entrants.

    Imported seeds live in the player DB entries ("seed") and aren't saved.
    Seeds set here are saved to user_data/seeds.json with the event they were
    made for, and are dropped when a different event is loaded. With no event
    loaded they are kept, so everything can be seeded by hand.
    """

    signals = TSHSeedManagerSignals()
    path = "./user_data/seeds.json"
    # tag (prefix + gamerTag) -> seed. 0 means "no seed".
    overrides = {}
    # URL of the event the seeds were set for, "" for none
    event = ""

    @staticmethod
    def Load():
        try:
            if os.path.exists(TSHSeedManager.path):
                with open(TSHSeedManager.path, "rb") as f:
                    data = orjson.loads(f.read())
                TSHSeedManager.event = data.get("event") or ""
                TSHSeedManager.overrides = {
                    str(tag): int(seed) for tag, seed in (data.get("seeds") or {}).items()
                }
        except Exception:
            logger.error(traceback.format_exc())
            TSHSeedManager.overrides = {}

    @staticmethod
    def Save():
        try:
            with open(TSHSeedManager.path, "wb") as f:
                f.write(
                    orjson.dumps(
                        {"event": TSHSeedManager.event, "seeds": TSHSeedManager.overrides},
                        option=orjson.OPT_INDENT_2,
                    )
                )
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def GetImportedSeed(tag):
        player = TSHPlayerDB.database.get(tag)
        if player is None:
            return None
        seed = player.get("seed")
        try:
            return int(seed) if seed is not None else None
        except TypeError, ValueError:
            return None

    @staticmethod
    def GetOverride(tag):
        return TSHSeedManager.overrides.get(tag)

    @staticmethod
    def GetSeed(tag):
        """The seed to show for a player: the one set by hand, else the imported one."""
        override = TSHSeedManager.overrides.get(tag)
        if override is not None:
            return override
        return TSHSeedManager.GetImportedSeed(tag)

    @staticmethod
    def SetSeed(tag, seed):
        if not tag:
            return
        TSHSeedManager.overrides[tag] = max(0, int(seed))
        TSHSeedManager.Save()
        TSHSeedManager.signals.seed_changed.emit(tag)

    @staticmethod
    def ResetSeed(tag):
        """Goes back to the imported seed."""
        if TSHSeedManager.overrides.pop(tag, None) is not None:
            TSHSeedManager.Save()
            TSHSeedManager.signals.seed_changed.emit(tag)

    @staticmethod
    def RenamePlayer(oldTag, newTag):
        if oldTag == newTag or oldTag not in TSHSeedManager.overrides:
            return
        TSHSeedManager.overrides[newTag] = TSHSeedManager.overrides.pop(oldTag)
        TSHSeedManager.Save()
        TSHSeedManager.signals.seed_changed.emit(newTag)

    @staticmethod
    def ClearAll():
        TSHSeedManager.overrides = {}
        TSHSeedManager.Save()
        TSHSeedManager.signals.seed_changed.emit("")

    @staticmethod
    def EventLoaded(url):
        """Drops the seeds set for another event. Unsetting the event keeps them."""
        url = url or ""
        if not url or url == TSHSeedManager.event:
            return
        hadSeeds = len(TSHSeedManager.overrides) > 0
        if hadSeeds:
            logger.info("Another event was loaded, clearing the seeds set by hand")
        TSHSeedManager.overrides = {}
        TSHSeedManager.event = url
        TSHSeedManager.Save()
        if hadSeeds:
            TSHSeedManager.signals.seed_changed.emit("")


TSHSeedManager.Load()
