"""Players' mains from the event's provider, fetched in the background: ahead
of time for the event's entrants, and for players a bulk load (e.g. the
bracket) shows without them. They're saved to the player database in
batches, so later loads find them there.

Only for providers with SUPPORTS_MAINS_PREFETCH. The provider fetches and
caches each player's mains (MainsKey, IsMainsCached, FetchMains); this
decides when, paces the requests and saves what they find."""

import threading
import time
import traceback
from collections import deque

import orjson
from loguru import logger

from .GameAssetManager import GameAssetManager
from .PlayerDB import PlayerDB


class PlayerMains:
    # Spacing between requests, keeping well under start.gg's 80
    # requests/minute so interactive queries still have room
    INTERVAL_SECS = 1.5
    # Players saved to the player database at once
    PREWARM_BATCH = 25
    QUEUE_BATCH = 8

    def __init__(self, provider, isCurrent, onUpdated):
        """isCurrent(): whether provider is still the event's. onUpdated():
        called (from a background thread) when queued mains were saved."""
        self.provider = provider
        self.isCurrent = isCurrent
        self.onUpdated = onUpdated
        self.lock = threading.Lock()
        self.queue = deque()
        self.queued = set()
        self.queueThread = None

    # =====================================================
    # WHAT NEEDS FETCHING
    # =====================================================
    def _GameCodename(self):
        return (GameAssetManager.instance.selectedGame or {}).get("codename")

    def _Saved(self, player, gameCodename):
        """The player database already has their mains for the game"""
        tag = (
            player.get("prefix") + " " + player.get("gamerTag")
            if player.get("prefix")
            else player.get("gamerTag")
        )
        try:
            saved = (PlayerDB.database.get(tag) or {}).get("mains") or {}
            if isinstance(saved, str):
                saved = orjson.loads(saved)
            return bool(gameCodename and saved.get(gameCodename))
        except Exception:
            return False

    def _Entry(self, player, mains):
        return {
            "prefix": player.get("prefix"),
            "gamerTag": player.get("gamerTag"),
            "mains": {g: [list(m) for m in ms] for g, ms in mains.items()},
        }

    # =====================================================
    # AHEAD OF TIME
    # =====================================================
    def Prewarm(self, players):
        """Fetches the mains of the event's entrants, in a background thread"""
        threading.Thread(
            target=self._Prewarm, args=(players,), name="MainsPrewarm", daemon=True
        ).start()

    def _Prewarm(self, players):
        try:
            gameCodename = self._GameCodename()
            if not gameCodename:
                return

            todo = []
            for player in players:
                key = self.provider.MainsKey(player)
                if key is None or self.provider.IsMainsCached(key):
                    continue
                if self._Saved(player, gameCodename):
                    continue
                todo.append((key, player))

            logger.info(f"Pre-warming mains for {len(todo)} players")

            found = []
            for key, player in todo:
                # Players a bulk load is waiting on go first; both loops
                # share the same request budget
                while self.queue:
                    time.sleep(self.INTERVAL_SECS)

                # Stop if the user switched tournament or game meanwhile
                if not self.isCurrent() or self._GameCodename() != gameCodename:
                    break
                if self.provider.IsMainsCached(key):
                    continue

                mains = self.provider.FetchMains(key)
                if mains:
                    found.append(self._Entry(player, mains))
                # Save in batches so progress survives a closed app
                if len(found) >= self.PREWARM_BATCH:
                    PlayerDB.AddPlayers(found)
                    found = []
                time.sleep(self.INTERVAL_SECS)

            if found:
                PlayerDB.AddPlayers(found)
            logger.info("Mains pre-warm finished")
        except Exception:
            logger.error(traceback.format_exc())

    # =====================================================
    # WHEN A BULK LOAD NEEDS THEM
    # =====================================================
    def Queue(self, player):
        """Fetches a player's mains in the background, unless they're
        already known. onUpdated() says when they arrive."""
        key = self.provider.MainsKey(player)
        if key is None or self.provider.IsMainsCached(key):
            return
        # Players that already have mains saved for this game don't need them
        if self._Saved(player, self._GameCodename()):
            return

        with self.lock:
            if key in self.queued:
                return
            self.queued.add(key)
            self.queue.append(
                (key, {"prefix": player.get("prefix"), "gamerTag": player.get("gamerTag")})
            )

            if self.queueThread is None:
                self.queueThread = threading.Thread(
                    target=self._QueueWorker, name="MainsQueue", daemon=True
                )
                self.queueThread.start()

    def _QueueWorker(self):
        found = []
        fetched = 0
        while True:
            with self.lock:
                if not self.queue:
                    self.queueThread = None
                    break
                key, player = self.queue.popleft()

            try:
                if not self.provider.IsMainsCached(key):
                    mains = self.provider.FetchMains(key)
                    if mains:
                        found.append(self._Entry(player, mains))
                    fetched += 1
                    time.sleep(self.INTERVAL_SECS)
            except Exception:
                logger.error(traceback.format_exc())
            finally:
                with self.lock:
                    self.queued.discard(key)

            # Let whoever is waiting on these pick them up in batches
            if fetched >= self.QUEUE_BATCH or not self.queue:
                fetched = 0
                try:
                    if found:
                        PlayerDB.AddPlayers(found)
                        found = []
                    self.onUpdated()
                except Exception:
                    logger.error(traceback.format_exc())
