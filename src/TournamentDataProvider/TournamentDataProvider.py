import random
from urllib.parse import quote as urlencode

import orjson
import requests
from loguru import logger
from qtpy.QtCore import QObject

from .ResultTypes import (
    CompletedSet,
    FutureSet,
    Phase,
    PhaseGroup,
    PhaseGroupSets,
    Set,
    SetDuration,
    SetListItem,
    Standing,
    Station,
    StreamsAndStations,
    TournamentData,
)


class TournamentDataProvider(QObject):
    """What every tournament data provider (start.gg, parry.gg) can be asked.
    The results' shapes are in ResultTypes.py. Methods taking
    progress_callback and cancel_event run in a Worker thread, which passes
    them. Methods taking a callback emit their result to it (callback.emit)
    instead of returning it."""

    def __init__(self, url, threadpool, dataManager) -> None:
        super().__init__(None)

        self.name = ""
        self.url = url
        self.entrants = []
        self.tournamentData = {}
        self.threadpool = threadpool
        self.videogame = None
        self.dataManager = dataManager

    # =====================================================
    # TOURNAMENT
    # =====================================================
    def GetIconURL(self) -> str | None:
        """The tournament's icon"""
        pass

    def GetTournamentData(self, progress_callback=None, cancel_event=None) -> TournamentData:
        pass

    # =====================================================
    # PHASES AND BRACKETS
    # =====================================================
    def GetTournamentPhases(self, progress_callback=None, cancel_event=None) -> list[Phase]:
        pass

    def GetTournamentPhaseGroup(self, id, progress_callback=None, cancel_event=None) -> PhaseGroup:
        """The phase group's entrants (by seed) and its sets"""
        pass

    def GetTournamentPhaseGroupSets(
        self, id, progress_callback=None, cancel_event=None
    ) -> PhaseGroupSets:
        """Just the results of the phase group's sets, to refresh a bracket
        already loaded without loading its entrants again. By default, the
        whole phase group, whose sets have the results too."""
        return self.GetTournamentPhaseGroup(
            id, progress_callback=progress_callback, cancel_event=cancel_event
        )

    # =====================================================
    # SETS
    # =====================================================
    def GetMatch(self, setId, progress_callback=None, cancel_event=None) -> Set:
        """A set, to load into a scoreboard"""
        pass

    def GetMatches(
        self, getFinished=False, progress_callback=None, cancel_event=None
    ) -> list[SetListItem]:
        """The event's sets to pick one from: the ones not finished, or all"""
        pass

    # =====================================================
    # FUTURE SETS
    # =====================================================
    def GetFutureMatch(self, matchId, progress_callback=None, cancel_event=None) -> FutureSet:
        """A set in a queue, {} if it can't be found"""
        pass

    def GetFutureMatchesList(
        self, setsId: list[dict], progress_callback=None, cancel_event=None
    ) -> dict[str, FutureSet | None]:
        """GetFutureMatch of each set ({"id": ...}), as {"1": set, "2": ...}
        in the same order, None for a set that couldn't be fetched"""
        pass

    # =====================================================
    # STREAMS AND STATIONS
    # =====================================================
    def GetStations(self, progress_callback=None, cancel_event=None) -> list[Station]:
        """The stations and streams sets can be loaded from"""
        pass

    def GetStreamQueue(
        self, progress_callback=None, cancel_event=None
    ) -> dict[str, dict[str, FutureSet]]:
        """Each stream's queue: {stream name: {"1": set, "2": ...}}"""
        pass

    def GetStreamMatchId(self, station) -> FutureSet | None:
        """The set on a stream (or a station's slot) now, None if none"""
        # ``station`` is the dict produced by GetStations, but for backward
        # compatibility implementations should also accept a bare identifier
        # string (the legacy form). Providers without per-capacity slots may
        # ignore station["slot"] entirely.
        pass

    def GetStationMatchId(self, stationId):
        pass

    def GetStationMatchsId(self, stationId) -> list[dict]:
        """A station's sets, as the provider gives them (each with an
        "id"). The first one is loaded, the others go in its queue."""
        pass

    # What only some providers can do. None means the provider can't.
    def GetStreamsAndStations(
        self, progress_callback=None, cancel_event=None
    ) -> StreamsAndStations | None:
        return None

    def ConvertStreamUrl(self, stream):
        if "twitch.tv" in stream:
            stream = stream.split("twitch.tv/")[1].replace("/", "")
            stream = f"Twitch: {stream}"
        if "youtube.com" in stream or "youtu.be" in stream:
            if "youtu.be" in stream:  # Convert stream URL if shortened
                stream = stream.split("?")[0]
                stream = f"https://youtube.com/watch?v={stream.split('/')[-1]}"

            # Use 3rd Party Client to get YouTube info
            data_server_search = requests.get(
                "https://api.invidious.io/instances.json?pretty=1&sort_by=health"
            )
            if int(data_server_search.status_code) == 200:
                # Filter data servers which are up and reliable
                possible_data_server_list = []
                for data_server_info in orjson.loads(data_server_search.text):
                    if (
                        data_server_info[1].get("api")
                        and data_server_info[1].get("monitor")
                        and not data_server_info[1].get("monitor").get("down")
                        and data_server_info[1].get("monitor").get("uptime") == 100
                    ):
                        possible_data_server_list.append(data_server_info[1].get("uri"))
                possible_data_server_list = sorted(
                    possible_data_server_list, key=lambda x: random.random()
                )
                for data_server in possible_data_server_list:
                    logger.info(f"YouTube Data Info Server: {data_server}")
                    info = requests.get(f"{data_server}/api/v1/resolveurl?url={urlencode(stream)}")
                    logger.info(f"Youtube Stream Info request: {info.text}")
                    if int(info.status_code) == 200:
                        if orjson.loads(info.text).get("videoId"):
                            info = requests.get(
                                f"{data_server}/api/v1/videos/{info.json().get('videoId')}"
                            )
                            logger.info(f"Youtube Video Info request: {info.text}")
                            if int(info.status_code) == 200:
                                stream = f'"{orjson.loads(info.text).get("title")}"'
                                stream = f"YouTube: {stream}"
                                break
                        elif orjson.loads(info.text).get("ucid"):
                            info = requests.get(
                                f"{data_server}/api/v1/channels/{info.json().get('ucid')}"
                            )
                            logger.info(f"Youtube Channel Info request: {info.text}")
                            if int(info.status_code) == 200:
                                stream = orjson.loads(info.text).get("author")
                                stream = f"YouTube: {stream}"
                                break
        return stream

    # =====================================================
    # SET HISTORY
    # =====================================================
    def GetRecentSets(
        self, id1, id2, videogame, callback, requestTime, progress_callback, cancel_event
    ) -> None:
        """Emits the sets the two players (ids as in Player.id) played
        against each other: a RecentSets"""
        pass

    def GetLastSets(
        self, playerID, playerNumber, callback, progress_callback, cancel_event
    ) -> None:
        """Emits the player's last sets in the event: a LastSets"""
        pass

    def GetCompletedSets(self, progress_callback, cancel_event) -> list[CompletedSet]:
        """The event's last completed sets, most recent first"""
        pass

    def GetPlayerHistoryStandings(
        self, playerID, playerNumber, gameType, callback, progress_callback, cancel_event
    ) -> None:
        """Emits the player's placements in past events: a HistorySets"""
        pass

    def GetSetDurations(
        self, count=40, progress_callback=None, cancel_event=None
    ) -> list[SetDuration] | None:
        """The event's last completed sets, for how long sets take"""
        return None

    # =====================================================
    # ENTRANTS AND PLAYERS
    # =====================================================
    def GetEntrants(self) -> None:
        """Adds the event's entrants to the player database, in the
        background"""
        pass

    def EnrichPlayerData(self, playerData, blocking=True):
        # Hook for providers to lazily fill in fields when a player is
        # loaded into a slot (called from ScoreboardPlayerWidget.SetData
        # post-DB-merge). Default no-op; ParryGG overrides to fetch mains
        # from a linked start.gg account. With blocking=False, providers
        # must not do network requests here (it runs on the UI thread);
        # they should only use what they already have cached.
        return playerData

    def GetCachedMains(self, playerData):
        # Mains EnrichPlayerData would add for this player without doing a
        # request, or None if it doesn't have them (yet).
        return None

    # =====================================================
    # STANDINGS
    # =====================================================
    def GetStandings(self, playerNumber, progress_callback, cancel_event) -> list[Standing]:
        """The event's top playerNumber, in placement order"""
        pass
