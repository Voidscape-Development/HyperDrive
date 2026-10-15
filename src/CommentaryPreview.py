import threading
import time
from concurrent.futures import ThreadPoolExecutor

import orjson
from loguru import logger

from .Helpers.DynamicExport import DynamicExport
from .Helpers.MediaHelper import MediaHelper
from .StateManager import StateManager
from .StatsUtil import StatsUtil
from .TournamentDataManager import TournamentDataManager


class _Result:
    """Stands in for the Qt signal the providers' stats functions emit their
    result on, so they can be called and waited on from a web request."""

    def __init__(self):
        self.value = None

    def emit(self, value):
        self.value = value


class CommentaryPreview:
    """What the commentary dashboard (/commentary-dashboard) shows about the
    players of a set that isn't on a scoreboard, e.g. the stream queue's next
    one: their avatar and custom data, and the stats the scoreboard gets for
    its players (their last sets in the event, their past events and their
    head-to-head), from the tournament's provider.

    Stats take a few seconds to come from the provider and every commentator's
    page asks for them, so they're kept for a few minutes."""

    CACHE_SECONDS = 300
    _cache: dict[str, tuple[float, object]] = {}
    _lock = threading.Lock()

    # =====================================================
    # PREVIEW
    # =====================================================
    def Preview(teams: list) -> dict:
        """teams: the set's two teams, each a list of players as in the stream
        queue ({name, team, id...}). Stats are only looked up for 1v1
        sets, like on the scoreboard."""
        teams = [[p for p in (team or []) if isinstance(p, dict)] for team in (teams or [])[:2]]
        provider = (
            TournamentDataManager.instance.provider if TournamentDataManager.instance else None
        )
        stats = provider is not None and provider.SUPPORTS_STATS
        singles = len(teams) == 2 and all(len(team) == 1 for team in teams)

        result = {
            "stats": stats and singles,
            "teams": [[CommentaryPreview._Media(p) for p in team] for team in teams],
            "recent_sets": None,
        }
        if not result["stats"]:
            return result

        ids = [CommentaryPreview._Id(team[0]) for team in teams]
        videogame = StateManager.Get("provider_videogame.id")

        with ThreadPoolExecutor(max_workers=5) as executor:
            jobs = {}
            for t, playerId in enumerate(ids):
                if playerId:
                    jobs[(t, "last_sets")] = executor.submit(
                        CommentaryPreview._LastSets, provider, playerId
                    )
                    if videogame:
                        jobs[(t, "history_sets")] = executor.submit(
                            CommentaryPreview._HistorySets, provider, playerId, videogame
                        )
            if all(ids) and ids[0] != ids[1] and videogame:
                jobs[(None, "recent_sets")] = executor.submit(
                    CommentaryPreview._RecentSets, provider, ids[0], ids[1], videogame
                )

            for (t, key), job in jobs.items():
                try:
                    value = job.result()
                except Exception:
                    logger.exception(f"Commentary preview: couldn't get {key}")
                    value = None
                if t is None:
                    result[key] = value
                else:
                    result["teams"][t][0][key] = value

        return result

    # =====================================================
    # PLAYER LOOKUPS
    # =====================================================
    def _Media(player: dict) -> dict:
        # The stream queue's players have their tag as name and sponsor as team
        name = player.get("gamerTag") or player.get("name") or ""
        team = player.get("prefix") or player.get("team") or ""
        return {
            "avatar": MediaHelper.FindAvatar(team, name),
            "custom": DynamicExport.CustomData(name, team),
        }

    def _Id(player: dict):
        playerId = player.get("id")
        if isinstance(playerId, list) and playerId and playerId[0]:
            return playerId
        return None

    # =====================================================
    # CACHE
    # =====================================================
    def _Cached(key: str, fetch):
        now = time.time()
        with CommentaryPreview._lock:
            hit = CommentaryPreview._cache.get(key)
            if hit and now - hit[0] < CommentaryPreview.CACHE_SECONDS:
                return hit[1]
            # Drop what's expired, so the cache doesn't grow all day
            for k, (t, _) in list(CommentaryPreview._cache.items()):
                if now - t >= CommentaryPreview.CACHE_SECONDS:
                    del CommentaryPreview._cache[k]

        value = fetch()
        with CommentaryPreview._lock:
            CommentaryPreview._cache[key] = (time.time(), value)
        return value

    def _Key(*parts) -> str:
        return orjson.dumps(parts).decode()

    # =====================================================
    # SETS
    # =====================================================
    def _LastSets(provider, playerId):
        def fetch():
            result = _Result()
            provider.GetLastSets(
                playerID=playerId[0],
                playerNumber="1",
                callback=result,
                progress_callback=None,
                cancel_event=None,
            )
            sets = (result.value or {}).get("last_sets") or []
            return [StatsUtil.LastSetEntry(s) for s in sets]

        return CommentaryPreview._Cached(
            CommentaryPreview._Key("last_sets", provider.url, playerId), fetch
        )

    def _HistorySets(provider, playerId, videogame):
        def fetch():
            result = _Result()
            provider.GetPlayerHistoryStandings(
                playerID=playerId[0],
                playerNumber="1",
                gameType=videogame,
                callback=result,
                progress_callback=None,
                cancel_event=None,
            )
            sets = (result.value or {}).get("history_sets") or []
            return [StatsUtil.HistorySetEntry(s) for s in sets]

        return CommentaryPreview._Cached(
            CommentaryPreview._Key("history_sets", playerId, videogame), fetch
        )

    def _RecentSets(provider, id1, id2, videogame):
        def fetch():
            result = _Result()
            provider.GetRecentSets(
                id1=id1,
                id2=id2,
                videogame=videogame,
                callback=result,
                requestTime=time.time_ns(),
                progress_callback=None,
                cancel_event=None,
            )
            return (result.value or {}).get("sets") or []

        return CommentaryPreview._Cached(
            CommentaryPreview._Key("recent_sets", id1, id2, videogame), fetch
        )
