import os
import re
import threading
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed, wait

import requests
import requests.adapters
from loguru import logger
from qtpy.QtCore import QT_TRANSLATE_NOOP

from ..Helpers import CompletedSetsHelper
from ..Helpers.CompletedSetsHelper import AddCharacterKey
from ..Helpers.CountryHelper import CountryHelper
from ..Helpers.DictHelper import as_dict, as_list, deep_clone, deep_get
from ..Helpers.LocaleHelper import LocaleHelper
from ..Helpers.SeedPerformance import EventBracketType
from ..PlayerDBModels import MakeTag
from . import StartGGConvert
from .StartGGClient import ReadQuery, StartGGClient
from .TournamentDataProvider import TournamentDataProvider

# A YouTube channel's id: "UC" and 22 more letters, digits, - or _
YOUTUBE_CHANNEL_ID = re.compile(r"^UC[\w-]{22}$")


class StartGGDataProvider(TournamentDataProvider):
    NAME = "StartGG"
    HOST = "start.gg"
    GAME_ID_KIND = "startgg"
    ICON = "./assets/icons/startgg.svg"
    ICON_THEMED = True
    COMPLETED_SETS_BUTTON = QT_TRANSLATE_NOOP("app", "Pull Latest Completed Sets from StartGG")
    # parry.gg names its rounds like start.gg does
    TranslateRoundName = staticmethod(StartGGConvert.TranslateRoundName)

    # GetTournamentPhaseGroup returns the phase group's sets and how they
    # connect, which the bracket widget builds every bracket type from
    SUPPORTS_BRACKETS = True
    SUPPORTS_STATS = True
    SUPPORTS_COMPLETED_SETS = True
    SUPPORTS_SET_ACTIONS = True
    SUPPORTS_MAINS_PREFETCH = True

    CompletedSetsQuery = None
    EntrantsQuery = None
    # request for a single set with only info relevant for a set that is yet to be played
    FutureSetQuery = None
    HistorySetsQuery = None
    LastSetsQuery = None
    HeadToHeadQuery = None
    SetQuery = None
    SetsQuery = None
    StationsQuery = None
    StationSetsQuery = None
    StreamSetsQuery = None
    StreamQueueQuery = None
    TournamentDataQuery = None
    TournamentPhasesQuery = None
    TournamentPhaseGroupSeedsQuery = None
    TournamentPhaseGroupSetsQuery = None
    TournamentStandingsQuery = None
    UserSetQuery = None
    UserMainsQuery = None
    UserProfileQuery = None
    _request_timeout_secs = 20.0

    player_seeds = {}

    # Head-to-head: the 100 most recent sets between two players, 20 a
    # request, keeping each under start.gg's complexity cap of 1000 objects
    # (a best of 5 costs ~30)
    _recent_sets_per_page = 20
    _recent_sets_max_sets = 100

    # The fields that come from the local player DB instead of start.gg with
    # the general.local_player_data setting: the set queries leave them out
    LOCAL_PROFILE_FIELDS = ["twitter", "socials", "pronoun", "country_code", "state_code"]

    def __init__(self, url, threadpool, dataManager, api_key=None, context=None) -> None:
        super().__init__(url, threadpool, dataManager, context=context)
        self.client = StartGGClient()
        # {MainsKey: mains}, see FetchMains
        self._mains_cache = {}
        # {start.gg user id: profile fields}, for players looked up because
        # they weren't in the local DB (see FillFromLocalDB)
        self._profile_cache = {}
        self._profileLock = threading.Lock()

    # =====================================================
    # REQUESTS
    # =====================================================
    # Queries the provided URL, retrying (with backoff) while start.gg is rate
    # limiting us or having server trouble
    def QueryRequests(
        self,
        url=None,
        type=None,
        headers=None,
        jsonParams=None,
        params=None,
        retries=5,
        timeout=None,
    ):
        """See StartGGClient.Request"""
        return self.client.Request(
            url, type, headers, jsonParams, params, retries, timeout or self._request_timeout_secs
        )

    def _FetchAllPages(self, fetchPage, totalPagesPath, cancel_event=None):
        return StartGGClient.FetchAllPages(fetchPage, totalPagesPath, cancel_event)

    # =====================================================
    # TOURNAMENT
    # =====================================================
    def GetTournamentData(self, progress_callback=None, cancel_event=None):
        finalData = {}

        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentDataQuery",
                    "variables": {"eventSlug": self.url.split("start.gg/")[1]},
                    "query": StartGGDataProvider.TournamentDataQuery,
                },
            )

            videogame = deep_get(data, "data.event.videogame.id", None)
            if videogame:
                self.videogame = videogame
                self.videogameFound = videogame

            finalData["tournamentName"] = deep_get(data, "data.event.tournament.name", "")
            finalData["eventName"] = deep_get(data, "data.event.name", "")
            finalData["numEntrants"] = deep_get(data, "data.event.numEntrants", 0)
            finalData["address"] = deep_get(data, "data.event.tournament.venueAddress", "")
            finalData["shortLink"] = deep_get(data, "data.event.tournament.shortSlug", "")
            finalData["startAt"] = deep_get(data, "data.event.tournament.startAt", "")
            finalData["endAt"] = deep_get(data, "data.event.tournament.endAt", "")
            finalData["eventStartAt"] = deep_get(data, "data.event.startAt", "")
            finalData["eventEndAt"] = deep_get(data, "data.event.endAt", "")
            # The tournament's square logo and wide banner, for layouts to brand themselves
            images = deep_get(data, "data.event.tournament.images", []) or []
            finalData["logo"] = StartGGConvert.ImageUrl(images, "profile")
            finalData["banner"] = StartGGConvert.ImageUrl(images, "banner")
        except:
            logger.error(traceback.format_exc())

        return finalData

    def GetIconURL(self):
        url = None

        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentIconQuery",
                    "variables": {"eventSlug": self.url.split("start.gg/")[1]},
                    "query": """
                        query TournamentIconQuery($eventSlug: String!) {
                            event(slug: $eventSlug) {
                                tournament{
                                    images(type: "profile") {
                                        type
                                        url
                                    }
                                }
                            }
                        }
                    """,
                },
            )

            images = as_list(deep_get(data, "data.event.tournament.images"))

            if len(images) > 0:
                url = as_dict(images[0]).get("url")
        except:
            logger.error(traceback.format_exc())

        return url

    def GetRealEventURL(self, url):
        matches = re.match(".*start.gg/admin/tournament/[^/]*/brackets/([^/]*)", url)
        if matches:
            try:
                data = self.QueryRequests(
                    "https://www.start.gg/api/-/gql",
                    type=requests.post,
                    jsonParams={
                        "operationName": "TournamentSlugQuery",
                        "variables": {"id": matches.group(1)},
                        "query": StartGGDataProvider.TournamentSlugQuery,
                    },
                )

                slug = deep_get(data, "data.event.slug", None)
                if slug:
                    url = "https://www.start.gg/" + slug
                else:
                    logger.error(f"No event found for {url}")
            except:
                logger.error(traceback.format_exc())
        self.url = url
        return url

    def _EventSlug(self):
        return self.url.split("start.gg/")[1]

    # =====================================================
    # PHASES AND BRACKETS
    # =====================================================
    def GetTournamentPhases(self, progress_callback=None, cancel_event=None):
        phases = []

        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentPhasesQuery",
                    "variables": {"eventSlug": self.url.split("start.gg/")[1]},
                    "query": StartGGDataProvider.TournamentPhasesQuery,
                },
            )

            logger.info(data)

            for phase in as_list(deep_get(data, "data.event.phases")):
                phaseObj = {"id": phase.get("id"), "name": phase.get("name"), "groups": []}

                for phaseGroup in as_list(deep_get(phase, "phaseGroups.nodes")):
                    phaseObj["groups"].append(
                        {
                            "id": phaseGroup.get("id"),
                            "name": LocaleHelper.phaseNames.get("group").format(
                                phaseGroup.get("displayIdentifier")
                            ),
                            "bracketType": phaseGroup.get("bracketType"),
                        }
                    )

                phases.append(phaseObj)
        except:
            logger.error(traceback.format_exc())

        return phases

    def _FetchPhaseGroupSeeds(self, id, progress_callback=None, cancel_event=None):
        def fetchPage(page):
            seedsData = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentPhaseGroupSeedsQuery",
                    "variables": {"id": id, "page": page, "perPage": 100},
                    "query": StartGGDataProvider.TournamentPhaseGroupSeedsQuery,
                },
            )

            if seedsData.get("errors"):
                logger.error(
                    f"TournamentPhaseGroupSeedsQuery errors (page {page}): {seedsData.get('errors')}"
                )

            if deep_get(seedsData, "data.phaseGroup") is None:
                logger.warning(
                    f"TournamentPhaseGroupSeedsQuery returned no phaseGroup for id {id} (page {page}): {seedsData}"
                )

            return seedsData

        pages = self._FetchAllPages(
            fetchPage, "data.phaseGroup.seeds.pageInfo.totalPages", cancel_event
        )

        seeds = []
        for seedsData in pages:
            seeds.extend(deep_get(seedsData, "data.phaseGroup.seeds.nodes", []) or [])

        return {
            "seeds": seeds,
            "progressionsOut": deep_get(pages[0], "data.phaseGroup.progressionsOut"),
        }

    def _FetchPhaseGroupSets(self, id, progress_callback=None, cancel_event=None):
        # Sorted by round and identifier, which doesn't change between page
        # requests. CALL_ORDER does (sets get called, ties have no fixed
        # order), so a set could move from one page to another while the
        # pages were fetched and be missed entirely.
        sortType = "ROUND"

        def fetchPage(page):
            setsData = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentPhaseGroupSetsQuery",
                    "variables": {"id": id, "page": page, "perPage": 100, "sortType": sortType},
                    "query": StartGGDataProvider.TournamentPhaseGroupSetsQuery,
                },
            )

            if setsData.get("errors"):
                logger.error(
                    f"TournamentPhaseGroupSetsQuery errors (page {page}): {setsData.get('errors')}"
                )

            if deep_get(setsData, "data.phaseGroup") is None:
                logger.warning(
                    f"TournamentPhaseGroupSetsQuery returned no phaseGroup for id {id} (page {page}): {setsData}"
                )

            return setsData

        def fetchAll():
            pages = self._FetchAllPages(
                fetchPage, "data.phaseGroup.sets.pageInfo.totalPages", cancel_event
            )
            total = deep_get(pages[0], "data.phaseGroup.sets.pageInfo.total")
            nodes = []
            for setsData in pages:
                nodes.extend(deep_get(setsData, "data.phaseGroup.sets.nodes", []) or [])
            return pages[0], total, nodes

        first, total, nodes = fetchAll()

        if deep_get(first, "data.phaseGroup") is None and first.get("errors"):
            logger.warning(
                f"Retrying TournamentPhaseGroupSetsQuery sorted by CALL_ORDER instead of {sortType}"
            )
            sortType = "CALL_ORDER"
            first, total, nodes = fetchAll()

        sets = {}

        def merge(nodes):
            for s in nodes:
                if s and s.get("id") is not None:
                    sets.setdefault(str(s.get("id")), s)

        merge(nodes)

        # A set missing from the pages leaves a hole in the bracket, so fetch
        # again until we have every set start.gg says the group has
        for _ in range(2):
            if total is None or len(sets) >= total:
                break
            if cancel_event is not None and cancel_event.is_set():
                break
            logger.warning(f"Phase group {id}: got {len(sets)} of {total} sets, fetching again")
            _first, _total, nodes = fetchAll()
            merge(nodes)

        if total is not None and len(sets) < total:
            logger.error(f"Phase group {id}: only got {len(sets)} of {total} sets")

        return {"sets": list(sets.values())}

    def GetTournamentPhaseGroup(self, id, progress_callback=None, cancel_event=None):
        """The phase group's entrants (by seed) and its sets, in the bracket
        model's format (BracketModel.FromProviderSets)."""
        finalData = {}

        try:
            # Seeds and sets are independent of each other, so fetch them
            # concurrently rather than one after another. This runs on a
            # worker of the shared thread pool, so use a separate executor:
            # waiting on jobs queued behind us in the same pool could leave
            # them stuck waiting for a free thread.
            with ThreadPoolExecutor(max_workers=2) as executor:
                fetchSeeds = executor.submit(
                    self._FetchPhaseGroupSeeds, id, cancel_event=cancel_event
                )
                fetchSets = executor.submit(
                    self._FetchPhaseGroupSets, id, cancel_event=cancel_event
                )

                def result(future):
                    try:
                        return future.result()
                    except Exception:
                        logger.error(traceback.format_exc())
                        return {}

                seedsResult = result(fetchSeeds)
                setsResult = result(fetchSets)

            seeds = as_list((seedsResult or {}).get("seeds"))
            progressionsOut = (seedsResult or {}).get("progressionsOut")
            sets = as_list((setsResult or {}).get("sets"))

            seeds.sort(key=lambda s: s.get("seedNum") or 0)

            teams = []

            for seed in seeds:
                team = {}
                participants = deep_get(seed, "entrant.participants")

                if isinstance(participants, list):
                    participants = as_list(participants)
                    if len(participants) > 1:
                        team["name"] = deep_get(seed, "entrant.name")

                    team["players"] = []

                    for entrant in participants:
                        team["players"].append(
                            StartGGConvert.ProcessEntrantData(
                                entrant,
                                deep_get(seed, "entrant.paginatedSets.nodes"),
                                gameAssets=self.context.games,
                            )
                        )

                teams.append(team)

            finalData["entrants"] = teams
            # Places players start.gg pairs after the phase group was loaded
            # (swiss rounds)
            finalData["entrantIds"] = [
                str(deep_get(seed, "entrant.id"))
                if deep_get(seed, "entrant.id") is not None
                else None
                for seed in seeds
            ]
            finalData["sets"] = StartGGConvert.BuildGraphSets(seeds, sets)
            finalData["progressionsIn"] = len(
                [s for s in seeds if deep_get(s, "progressionSource.originPhaseGroup.id")]
            )
            finalData["progressionsOut"] = len(progressionsOut or [])
        except:
            logger.error(traceback.format_exc())

        return finalData

    def GetTournamentPhaseGroupSets(self, id, progress_callback=None, cancel_event=None):
        """Only the results of the phase group's sets, and who plays them
        (swiss rounds are paired after the phase group was loaded)."""
        try:
            sets = (self._FetchPhaseGroupSets(id, cancel_event=cancel_event) or {}).get("sets", [])

            return {
                "sets": [
                    {
                        "id": str(s.get("id")),
                        "score": [s.get("entrant1Score"), s.get("entrant2Score")],
                        "finished": s.get("state", 0) == 3,
                        "winnerSlot": StartGGConvert.SetWinnerSlot(s),
                        "slots": [
                            {
                                "prereqType": as_dict(slot).get("prereqType"),
                                "entrantId": str(deep_get(slot, "entrant.id"))
                                if deep_get(slot, "entrant.id") is not None
                                else None,
                            }
                            for slot in (s.get("slots") or [])
                        ],
                    }
                    for s in sets
                ]
            }
        except Exception:
            logger.error(traceback.format_exc())
            return {}

    # =====================================================
    # SETS
    # =====================================================
    def GetMatch(self, setId, progress_callback=None, cancel_event=None):
        finalResult = None

        try:
            result = {}

            # Both APIs at once. One that takes too long counts as {}, and
            # isn't waited for; one that failed as None.
            executor = ThreadPoolExecutor(max_workers=2)
            args = {"progress_callback": None, "cancel_event": None, "setId": setId}
            fetchOld = executor.submit(self._GetMatchTasks, **args)
            fetchNew = executor.submit(self._GetMatchNewApi, **args)
            done, _ = wait([fetchOld, fetchNew], timeout=self._request_timeout_secs)
            executor.shutdown(wait=False)

            def outcome(fetch):
                if fetch not in done:
                    return {}
                if fetch.exception() is not None:
                    logger.error("".join(traceback.format_exception(fetch.exception())))
                    return None
                return fetch.result()

            result.update({"new": outcome(fetchNew)})
            result.update({"old": outcome(fetchOld)})

            # logger.debug(result)

            # A failed or slow one counts as having nothing
            result = {key: as_dict(value) for key, value in result.items()}

            finalResult = {}
            finalResult.update(result["new"])
            finalResult.update(result["old"])

            winnerProgression = result["old"].get("winnerProgression", None)
            if winnerProgression:
                indicator = "qualifier_winners_indicator"

                if int(finalResult.get("round") or 0) < 0:
                    indicator = "qualifier_losers_indicator"

                indicator = LocaleHelper.matchNames.get(indicator)

                winnerProgression = re.sub(r"\s*[\(\{\[].*?[\)\}\]]", "", winnerProgression).strip()
                qualifier = LocaleHelper.matchNames.get("qualifier")
                if qualifier:
                    finalResult["round_name"] = qualifier.format(winnerProgression, indicator)

            if result.get("new", {}).get("isOnline") == False:
                finalResult["bestOf"] = None

            finalResult["entrants"] = result["new"].get("entrants") or []

            for t, team in enumerate(result["old"].get("entrants") or []):
                for p, player in enumerate(team or []):
                    if as_dict(player).get("mains"):
                        try:
                            finalResult["entrants"][t][p]["mains"] = player["mains"]
                            finalResult["has_selection_data"] = True
                        except:
                            logger.debug(traceback.format_exc())

            # logger.debug(f"Final result: {finalResult}")

        except Exception as e:
            logger.error(traceback.format_exc())
        return finalResult

    def _GetMatchTasks(self, setId, progress_callback, cancel_event):
        if "preview" in str(setId):
            return StartGGConvert.ParseMatchDataOldApi({}, self.context.games)

        try:
            data = self.QueryRequests(
                f'https://www.start.gg/api/-/gg_api./set/{setId};bustCache=true;expand=["setTask"];fetchMostRecentCached=true',
                type=requests.get,
                params={
                    "extensions": {"cacheControl": {"version": 1, "noCache": True}},
                    "cacheControl": {"version": 1, "noCache": True},
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            return StartGGConvert.ParseMatchDataOldApi(data, self.context.games)
        except Exception as e:
            logger.error(traceback.format_exc())
            return {}

    def _GetMatchNewApi(self, setId, progress_callback, cancel_event):
        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "SetQuery",
                    "variables": {"id": setId, "profile": not self.UseLocalPlayerData()},
                    "query": StartGGDataProvider.SetQuery,
                },
            )
            # logger.debug(data.get("data", {}).get("set", {}))
            _set = deep_get(data, "data.set")
            if not _set:
                logger.error(f"start.gg sent no set {setId}: {data.get('errors')}")
                return {}
            return self.ParseMatchDataNewApi(_set)
        except Exception as e:
            logger.error(traceback.format_exc())
            return {}

    def _FetchMatchesPage(self, states, page, cancel_event=None):
        if cancel_event is not None and cancel_event.is_set():
            return {}
        return self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "EventMatchListQuery",
                "variables": {
                    "filters": {"state": states, "hideEmpty": True},
                    "eventSlug": self.url.split("start.gg/")[1],
                    "page": page,
                    "perPage": 32,
                },
                "query": StartGGDataProvider.SetsQuery,
            },
        )

    def GetMatches(self, getFinished=False, progress_callback=None, cancel_event=None):
        final_data = []
        try:
            logger.info(f"Get matches (getFinished={getFinished})")
            states = [1, 6, 2]

            if getFinished:
                states.append(3)

            logger.info("Fetching sets")

            firstPage = self._FetchMatchesPage(states, 1, cancel_event)
            totalPages = deep_get(firstPage, "data.event.sets.pageInfo.totalPages", 1)

            pagesDone = 1
            if progress_callback:
                progress_callback(pagesDone, totalPages)
            logger.info(f"Fetching sets... {pagesDone}/{totalPages}")

            pages = {1: firstPage}
            if totalPages > 1:
                # Keep the worker count low so start.gg doesn't start rate limiting us
                with ThreadPoolExecutor(max_workers=6) as executor:
                    futures = {
                        executor.submit(self._FetchMatchesPage, states, p, cancel_event): p
                        for p in range(2, totalPages + 1)
                    }
                    for future in as_completed(futures):
                        pages[futures[future]] = future.result()
                        pagesDone += 1
                        if progress_callback:
                            progress_callback(pagesDone, totalPages)
                        logger.info(f"Fetching sets... {pagesDone}/{totalPages}")

            # Parse in page order so the result matches the old sequential order
            for p in sorted(pages):
                for _set in deep_get(pages[p], "data.event.sets.nodes", []) or []:
                    final_data.append(self.ParseMatchDataNewApi(_set))
            return final_data
        except Exception as e:
            logger.error(traceback.format_exc())
            return final_data

    # =====================================================
    # PARSING SETS
    # =====================================================

    @staticmethod
    def ParseStream(stream):
        """A set's stream (start.gg's Streams) as (url, name to show). A
        YouTube stream's streamName is usually the channel's name, with its
        id in streamId, but is the id itself for some, with a name in
        shortName."""
        stream = as_dict(stream)
        name = stream.get("streamName") or ""
        source = stream.get("streamSource")
        if not name:
            return "", ""
        if source == "TWITCH":
            return "https://twitch.tv/" + name, name
        if source == "YOUTUBE":
            channel = next(
                (c for c in [stream.get("streamId"), name] if c and YOUTUBE_CHANNEL_ID.match(c)),
                None,
            )
            if YOUTUBE_CHANNEL_ID.match(name):
                name = stream.get("shortName") or name
            url = (
                "https://youtube.com/channel/" + channel
                if channel
                else "https://youtube.com/" + name
            )
            return url, name
        return name, name

    def ParseMatchDataNewApi(self, _set):
        try:
            slots = deep_get(_set, "slots") or []
            p1 = as_dict(slots[0] if len(slots) > 0 else None)
            p2 = as_dict(slots[1] if len(slots) > 1 else None)

            # Add Pool identifier if phase has multiple Pools
            phase_name = deep_get(_set, "phaseGroup.phase.name")
            round_name = StartGGConvert.TranslateRoundName(_set.get("fullRoundText"))

            if deep_get(_set, "phaseGroup.phase.bracketType") == "MATCHMAKING":
                round_name = ""

            bracket_type = deep_get(_set, "phaseGroup.phase.bracketType", "")

            isPools = (deep_get(_set, "phaseGroup.phase.groupCount") or 0) > 1
            if isPools:
                phase_name = (
                    (phase_name or "")
                    + " - "
                    + LocaleHelper.phaseNames.get("group").format(
                        deep_get(_set, "phaseGroup.displayIdentifier")
                    )
                )

            streamUrl, streamName = StartGGDataProvider.ParseStream(_set.get("stream"))

            setData = {
                "id": _set.get("id"),
                "round": _set.get("round"),
                "groupCount": deep_get(_set, "phaseGroup.phase.groupCount"),
                "numSeeds": deep_get(_set, "phaseGroup.phase.numSeeds", -1),
                "team1score": _set.get("entrant1Score", 0),
                "team2score": _set.get("entrant2Score", 0),
                "round_name": round_name,
                "tournament_phase": phase_name,
                "bracket_type": bracket_type,
                "p1_name": p1.get("entrant", {}).get("name", "")
                if p1 and p1.get("entrant") != None
                else "",
                "p2_name": p2.get("entrant", {}).get("name", "")
                if p2 and p2.get("entrant") != None
                else "",
                "p1_seed": p1.get("entrant", {}).get("initialSeedNum", None)
                if p1 and p1.get("entrant")
                else None,
                "p2_seed": p2.get("entrant", {}).get("initialSeedNum", None)
                if p2 and p2.get("entrant")
                else None,
                "stream": streamUrl,
                "stream_name": streamName,
                "station": _set.get("station", {}).get("number", "")
                if _set.get("station", {}) != None
                else "",
                "isOnline": deep_get(_set, "event.isOnline"),
                "isPools": isPools,
            }

            # What reporting the set needs: its state, the entrants by slot
            # and the games already reported
            setData["state"] = _set.get("state")
            setData["entrant_ids"] = [
                str(deep_get(p1, "entrant.id")) if deep_get(p1, "entrant.id") is not None else None,
                str(deep_get(p2, "entrant.id")) if deep_get(p2, "entrant.id") is not None else None,
            ]
            setData["games"] = StartGGConvert.ParseSetGames(
                _set, setData["entrant_ids"], gameAssets=self.context.games
            )

            players = [[], []]

            entrants = [
                as_list(deep_get(p1, "entrant.participants")),
                as_list(deep_get(p2, "entrant.participants")),
            ]

            for i, team in enumerate(entrants):
                for j, entrant in enumerate(team):
                    player = entrant.get("player")
                    user = entrant.get("user")

                    playerData = {}

                    if player:
                        playerData["prefix"] = player.get("prefix")
                        playerData["gamerTag"] = player.get("gamerTag")
                        playerData["name"] = player.get("name")

                    if user:
                        StartGGConvert.ParseUserSocials(user, playerData)

                        if user.get("genderPronoun"):
                            playerData["pronoun"] = user.get("genderPronoun")

                        if user.get("images") and len(user.get("images")) > 0:
                            playerData["avatar"] = user.get("images")[0].get("url")

                        if user.get("id"):
                            playerData["id"] = [as_dict(player).get("id"), user.get("id")]

                        if user.get("location"):
                            # Country to country code
                            if user.get("location").get("country"):
                                for country in CountryHelper.countries.values():
                                    if user.get("location").get("country") == country.get(
                                        "en_name"
                                    ):
                                        playerData["country_code"] = country.get("code")
                                        break

                            # State -- direct
                            if user.get("location").get("state"):
                                stateCode = user.get("location").get("state")
                                if stateCode:
                                    playerData["state_code"] = user.get("location").get("state")
                            # State -- from city
                            elif user.get("location").get("city") and playerData.get(
                                "country_code"
                            ):
                                stateCode = CountryHelper.FindState(
                                    playerData["country_code"], user.get("location").get("city")
                                )
                                if stateCode:
                                    playerData["state_code"] = stateCode
                            if user.get("location").get("city"):
                                playerData["city"] = user.get("location").get("city")

                    if "id" not in playerData:
                        playerData["id"] = [as_dict(player).get("id"), 0]
                    if playerData.get("id") and len(playerData.get("id")) > 0:
                        if playerData["id"][0] is not None:
                            playerData["seed"] = self.player_seeds.get(playerData["id"][0])

                    if setData.get(f"p{i + 1}_seed"):
                        playerData["seed"] = setData.get(f"p{i + 1}_seed")

                    if i == 0:
                        standings = as_dict(deep_get(p1, "entrant.standing.setRecordWithoutByes"))
                        playerData["wins"] = standings.get("wins", "0")
                        playerData["losses"] = standings.get("losses", "0")
                        playerData["winPercentage"] = standings.get("winPercentage", "N/A")
                    else:
                        standings = as_dict(deep_get(p2, "entrant.standing.setRecordWithoutByes"))
                        playerData["wins"] = standings.get("wins", "0")
                        playerData["losses"] = standings.get("losses", "0")
                        playerData["winPercentage"] = standings.get("winPercentage", "N/A")

                    if self.UseLocalPlayerData():
                        self.FillFromLocalDB(playerData)

                    players[i].append(playerData)

            setData["entrants"] = players

            return setData
        except Exception as e:
            logger.error(traceback.format_exc())
            return {}

    # =====================================================
    # FUTURE SETS
    # =====================================================
    def ProcessFutureSet(self, _set, eventSlug):
        phase_name = deep_get(_set, "phaseGroup.phase.name")
        if (deep_get(_set, "phaseGroup.phase.groupCount") or 0) > 1:
            phase_name = (
                (phase_name or "")
                + " - "
                + LocaleHelper.phaseNames.get("group").format(
                    deep_get(_set, "phaseGroup.displayIdentifier")
                )
            )

        frt = _set.get("fullRoundText") or ""
        total_games = _set.get("totalGames") or 0
        seteventSlug = deep_get(_set, "event.slug", "")

        setData = {
            "id": _set.get("id"),
            "match": StartGGConvert.TranslateRoundName(frt),
            "phase": phase_name,
            "best_of": total_games,
            "best_of_text": LocaleHelper.matchNames.get("best_of").format(total_games)
            if total_games > 0
            else "",
            "state": _set.get("state"),
            # When it was started, if it was (for the stream queue's estimated times)
            "started_at": _set.get("startedAt"),
            "team": {},
            "station": deep_get(_set, "station.number", -1),
            "event": seteventSlug,
            "isCurrentEvent": seteventSlug == eventSlug,
        }

        for teamIndex, slot in enumerate(_set.get("slots") or []):
            entrant = as_dict(slot).get("entrant")
            if entrant:
                losers = False
                if "Gran" in frt:
                    if teamIndex == 1 or "Reset" in frt:
                        losers = True

                teamData = {
                    "teamName": entrant.get("name", ""),
                    "losers": losers,
                    "seed": entrant.get("initialSeed", 889977666),
                    "player": {},
                }

                # TODO : pull the state data

                for playerIndex, participant in enumerate(as_list(entrant.get("participants"))):
                    playerData = StartGGConvert.ProcessEntrantData(
                        participant, gameAssets=self.context.games
                    )
                    if self.UseLocalPlayerData():
                        self.FillFromLocalDB(playerData)
                    playerName = playerData.get("gamerTag") or ""
                    team = playerData.get("prefix", "")

                    countryCode = playerData.get("country_code", "")
                    stateCode = playerData.get("state_code", "")
                    countryData = CountryHelper.countries.get(countryCode)
                    stateData = {}
                    if countryData:
                        states = countryData.get("states")
                        if states and stateCode and states.get(stateCode):
                            # A copy: the countries' data is shared
                            stateData = dict(states[stateCode])

                            path = f"./assets/state_flag/{countryCode}/{'_CON' if stateCode == 'CON' else stateCode}.png"
                            if not os.path.exists(path):
                                path = None

                            stateData.update({"asset": path})

                    playerData = {
                        "country": CountryHelper.GetBasicCountryInfo(countryCode),
                        "state": stateData,
                        "name": playerName,
                        "team": team,
                        "mergedName": team + "|" + playerName
                        if isinstance(team, str) and team != ""
                        else playerName,
                        "pronoun": playerData.get("pronoun", ""),
                        "real_name": playerData.get("name", ""),
                        "online_avatar": playerData.get("avatar", ""),
                        "twitter": playerData.get("twitter", ""),
                        "socials": playerData.get("socials", {}),
                        # For the commentary dashboard's stats of the players
                        "id": playerData.get("id"),
                    }

                    teamData["player"][str(playerIndex + 1)] = playerData

                setData["team"][str(teamIndex + 1)] = teamData
        return setData

    def GetFutureMatch(self, matchId, progress_callback=None, cancel_event=None):
        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "FutureSetQuery",
                "variables": {"id": matchId, "profile": not self.UseLocalPlayerData()},
                "query": StartGGDataProvider.FutureSetQuery,
            },
        )

        data = deep_get(data, "data.set", None)

        if not data:
            return {}

        data = self.ProcessFutureSet(data, self.url.split("start.gg/")[1])

        return data

    def GetFutureMatchesList(self, setsId, progress_callback, cancel_event):
        """The future-set data of each set, {"1": set, "2": ...} in the same
        order, None for a set that couldn't be fetched"""

        def fetch(set):
            try:
                return self.GetFutureMatch(set.get("id")) or None
            except Exception:
                logger.error(traceback.format_exc())
                return None

        if not setsId:
            return {}
        # Fetched in parallel; map keeps them in order
        with ThreadPoolExecutor(max_workers=4) as executor:
            sets = list(executor.map(fetch, setsId))
        return {str(index + 1): set for index, set in enumerate(sets)}

    # =====================================================
    # STREAMS AND STATIONS
    # =====================================================
    def GetStations(self, progress_callback=None, cancel_event=None):
        try:
            logger.info("Get stations")

            final_data = []

            logger.info("Fetching stations")

            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "Stations",
                    "variables": {
                        "eventSlug": self.url.split("start.gg/")[1],
                    },
                    "query": StartGGDataProvider.StationsQuery,
                },
            )

            stations = as_list(deep_get(data, "data.event.stations.nodes"))
            queues = as_list(deep_get(data, "data.event.tournament.streamQueue"))

            if stations:
                for station in stations:
                    stream = ""

                    if queues is not None:
                        stream = next(
                            (
                                deep_get(s, "stream.streamName", None)
                                for s in queues
                                if str(deep_get(s, "stream.id", None))
                                == str(station.get("streamId"))
                            ),
                            "",
                        )

                    final_data.append(
                        {
                            "id": station.get("id"),
                            "identifier": station.get("number"),
                            "type": "station",
                            "stream": stream,
                        }
                    )

            if queues:
                for queue in queues:
                    if queue.get("stream") is not None:
                        stream = queue.get("stream")
                        final_data.append(
                            {
                                "id": stream.get("id"),
                                "identifier": stream.get("streamName"),
                                "type": "stream",
                            }
                        )

            return final_data
        except Exception as e:
            logger.error(traceback.format_exc())
            return final_data
        return []

    def GetStreamQueue(self, progress_callback=None, cancel_event=None):
        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "StreamQueueQuery",
                    "variables": {
                        "slug": self.url.split("start.gg/")[1],
                        "profile": not self.UseLocalPlayerData(),
                    },
                    "query": StartGGDataProvider.StreamQueueQuery,
                },
            )
            logger.info("Stream queue loaded from StartGG")

            eventSlug = deep_get(data, "data.event.slug", "")
            queues = deep_get(data, "data.event.tournament.streamQueue", [])

            finalData = {}

            if not queues:
                logger.info("(No stream queue was found)")
                return finalData

            for q in as_list(queues):
                streamName = deep_get(q, "stream.streamName") or ""
                queueData = {}
                for _set in as_list(q.get("sets")):
                    try:
                        setData = self.ProcessFutureSet(_set, eventSlug)
                    except Exception:
                        # One set start.gg sent half of doesn't empty the queue
                        logger.error(traceback.format_exc())
                        continue
                    queueData[str(len(queueData) + 1)] = setData

                finalData[streamName] = queueData

            return finalData

            """
            if queues:
                lStreamName = streamName.lower()
                queue = next(
                    (q for q in queues if q and q.get("stream", {}).get("streamName", "").lower() == lStreamName),
                    {}
                )

                return queue
            """

        except Exception as e:
            logger.error(traceback.format_exc())

        return {}

    def GetStreamMatchId(self, streamName):
        # Accept either a bare identifier string or the station dict produced
        # by GetStations (parry's multi-capacity streams need the dict for slot
        # context; start.gg streams are always capacity 1, so just use the
        # identifier).
        if isinstance(streamName, dict):
            streamName = streamName.get("identifier", "")
        streamSet = None

        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "StreamSetsQuery",
                    "variables": {"eventSlug": self.url.split("start.gg/")[1]},
                    "query": StartGGDataProvider.StreamSetsQuery,
                },
            )

            eventId = deep_get(data, "data.event.id", None)

            queues = as_list(deep_get(data, "data.event.tournament.streamQueue"))

            if queues:
                lStreamName = (streamName or "").lower()  # """performance"""
                queue = next(
                    (
                        q
                        for q in queues
                        if (deep_get(q, "stream.streamName") or "").lower() == lStreamName
                    ),
                    None,
                )

                if queue and as_list(queue.get("sets")):
                    queueSets = [
                        s for s in as_list(queue.get("sets")) if deep_get(s, "event.id") == eventId
                    ]
                    if len(queueSets) > 0:
                        streamSet = queueSets[0]
        except Exception as e:
            logger.error(traceback.format_exc())

        return streamSet

    def GetStationMatchsId(self, stationId):
        sets = None

        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "StationSetsQuery",
                    "variables": {
                        "eventSlug": self.url.split("start.gg/")[1],
                        "filters": {"state": [1, 2, 4, 5, 6], "hideEmpty": True},
                    },
                    "query": StartGGDataProvider.StationSetsQuery,
                },
            )

            sets = as_list(deep_get(data, "data.event.sets.nodes"))

            sets = [s for s in sets if str(deep_get(s, "station.id", "-1")) == str(stationId)]

        except Exception as e:
            logger.error(traceback.format_exc())

        return sets

    def GetStationMatchId(self, stationId):
        sets = self.GetStationMatchsId(stationId)

        return sets[0] if sets else None

    def GetStreamsAndStations(self, progress_callback=None, cancel_event=None):
        """The tournament's streams and the event's stations, with the ids
        start.gg's assignStream / assignStation take: {"streams": [{id,
        name}], "stations": [{id, number, stream}]}."""
        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "StreamsStationsQuery",
                "variables": {"eventSlug": self._EventSlug()},
                "query": StartGGDataProvider.StreamsStationsQuery,
            },
        )
        streams = [
            {"id": s.get("id"), "name": s.get("streamName") or ""}
            for s in deep_get(data, "data.event.tournament.streams", []) or []
            if s and s.get("id") is not None and s.get("enabled") is not False
        ]
        streamNames = {str(s["id"]): s["name"] for s in streams}
        stations = [
            {
                "id": s.get("id"),
                "number": s.get("number"),
                "stream": streamNames.get(str(s.get("streamId")), ""),
            }
            for s in deep_get(data, "data.event.stations.nodes", []) or []
            if s and s.get("id") is not None and s.get("enabled") is not False
        ]
        stations.sort(key=lambda s: s.get("number") or 0)
        return {"streams": streams, "stations": stations}

    # =====================================================
    # SET HISTORY
    # =====================================================
    def GetLastSets(self, playerID, playerNumber, callback, progress_callback, cancel_event):
        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "PlayerLastSetsQuery",
                    "variables": {
                        "eventSlug": self.url.split("start.gg/")[1],
                        "playerID": playerID,
                    },
                    "query": StartGGDataProvider.LastSetsQuery,
                },
            )

            sets = as_list(deep_get(data, "data.event.sets.nodes"))

            set_data = []

            for set in sets:
                if not set.get("winnerId"):
                    continue
                if len(set.get("slots") or []) < 2:
                    continue

                phaseName = ""
                phaseIdentifier = ""

                # This is because a display identifier at a major (Ex. Pools C12) will return C12,
                # otherwise startgg will just return a string containing "1"
                if deep_get(set, "phaseGroup.displayIdentifier") != "1":
                    phaseIdentifier = deep_get(set, "phaseGroup.displayIdentifier")
                phaseName = deep_get(set, "phaseGroup.phase.name")

                slot0 = as_dict(set["slots"][0])
                slot1 = as_dict(set["slots"][1])

                def FirstPlayer(slot):
                    participants = as_list(deep_get(slot, "entrant.participants"))
                    return as_dict(participants[0].get("player")) if participants else {}

                player1Info = FirstPlayer(slot0)
                player1Seed = slot0.get("initialSeedNum", 0)
                slot0_entrant_id = deep_get(slot0, "entrant.id")

                player2Info = FirstPlayer(slot1)
                player2Seed = slot1.get("initialSeedNum", 0)
                slot1_entrant_id = deep_get(slot1, "entrant.id")

                # Count character selections per entrant from game data
                chars_by_entrant = {
                    slot0_entrant_id: Counter(),
                    slot1_entrant_id: Counter(),
                }
                for game in as_list(set.get("games")):
                    for selection in as_list(game.get("selections")):
                        eid = deep_get(selection, "entrant.id")
                        char_id = selection.get("selectionValue")
                        if eid in chars_by_entrant and char_id:
                            chars_by_entrant[eid][char_id] += 1

                def _resolve_char_dict(entrant_id):
                    result = {}
                    for idx, (char_id, _) in enumerate(
                        chars_by_entrant.get(entrant_id, Counter()).most_common(), 1
                    ):
                        char = self.context.games.GetCharacterFromStartGGId(char_id)
                        if not char:
                            continue
                        _key, char_info = char
                        codename = char_info.get("codename", _key)
                        assets = self.context.games.GetCharacterAssets(codename, 0)
                        result[str(idx)] = {
                            "name": char_info.get("display_name", codename),
                            "codename": codename,
                            "assets": assets,
                            "skin": 0,
                            "variant": {},
                        }
                    return result

                players = ["1", "2"]
                if player1Info.get("id") != playerID:
                    players.reverse()

                # focused player is in players[0], opponent in players[1]
                focused_entrant = (
                    slot0_entrant_id if player1Info.get("id") == playerID else slot1_entrant_id
                )
                oponent_entrant = (
                    slot1_entrant_id if player1Info.get("id") == playerID else slot0_entrant_id
                )

                player_set = {
                    "phase_id": phaseIdentifier,
                    "phase_name": phaseName,
                    "round_name": StartGGConvert.TranslateRoundName(set.get("fullRoundText")),
                    f"player{players[0]}_score": set.get("entrant1Score")
                    if set.get("entrant1Score") is not None
                    else "0",
                    f"player{players[0]}_seed": player1Seed,
                    f"player{players[0]}_team": player1Info.get("prefix"),
                    f"player{players[0]}_name": player1Info.get("gamerTag"),
                    f"player{players[1]}_score": set.get("entrant2Score")
                    if set.get("entrant2Score") is not None
                    else "0",
                    f"player{players[1]}_seed": player2Seed,
                    f"player{players[1]}_team": player2Info.get("prefix"),
                    f"player{players[1]}_name": player2Info.get("gamerTag"),
                    "player_char": {"character": _resolve_char_dict(focused_entrant)},
                    "oponent_char": {"character": _resolve_char_dict(oponent_entrant)},
                }

                set_data.append(player_set)

            callback.emit({"playerNumber": playerNumber, "last_sets": set_data})
        except Exception as e:
            logger.error(traceback.format_exc())
            callback.emit({"playerNumber": playerNumber, "last_sets": []})

    def GetCompletedSets(self, progress_callback, cancel_event):
        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "CompletedSetsQuery",
                    "variables": {"eventSlug": self.url.split("start.gg/")[1]},
                    "query": StartGGDataProvider.CompletedSetsQuery,
                },
            )

            sets = as_list(deep_get(data, "data.event.sets.nodes"))

            set_data = []

            for set in sets:
                if not set.get("winnerId"):
                    continue
                if len(set.get("slots") or []) < 2:
                    continue

                phaseName = ""
                phaseIdentifier = ""

                # This is because a display identifier at a major (Ex. Pools C12) will return C12,
                # otherwise startgg will just return a string containing "1"
                if deep_get(set, "phaseGroup.displayIdentifier") != "1":
                    phaseIdentifier = deep_get(set, "phaseGroup.displayIdentifier")
                phaseName = deep_get(set, "phaseGroup.phase.name")

                slots = set.get("slots") or []
                p1 = as_dict(slots[0] if len(slots) > 0 else None)
                p2 = as_dict(slots[1] if len(slots) > 1 else None)

                # Pulls "Team" names, only useful if more than 1 player on a team
                # Else it'll display as "ABC | TestPlayer"
                t1Name = deep_get(p1, "entrant.name", "")
                t2Name = deep_get(p2, "entrant.name", "")

                # Seed Info for Team/Player
                team1Seed = deep_get(p1, "entrant.initialSeedNum", 0)
                team2Seed = deep_get(p2, "entrant.initialSeedNum", 0)

                winnerId = deep_get(p1, "entrant.id", 0)

                # Characters played, by participant. A selection without a
                # participant goes to its entrant's only participant.
                characters = {}
                participantsByEntrant = {
                    deep_get(slot, "entrant.id"): as_list(deep_get(slot, "entrant.participants"))
                    for slot in slots
                }
                for game in as_list(set.get("games")):
                    for selection in as_list(game.get("selections")):
                        participantId = deep_get(selection, "participant.id")
                        if participantId is None:
                            participants = participantsByEntrant.get(
                                deep_get(selection, "entrant.id"), []
                            )
                            if len(participants) != 1:
                                continue
                            participantId = participants[0].get("id")
                        char = self.context.games.GetCharacterFromStartGGId(
                            selection.get("selectionValue")
                        )
                        if char:
                            AddCharacterKey(characters.setdefault(participantId, []), char[0])

                def TeamInfo(slot):
                    team = []
                    for participant in as_list(deep_get(slot, "entrant.participants")):
                        player = participant.get("player") or {}
                        countryCode, stateCode = StartGGConvert.LocationCodes(
                            deep_get(participant, "user.location")
                        )
                        team.append(
                            {
                                "sponsor": player.get("prefix", ""),
                                "gamertag": player.get("gamerTag"),
                                "country_code": countryCode,
                                "state_code": stateCode,
                                "character_keys": characters.get(participant.get("id"), []),
                            }
                        )
                    return team

                team1 = TeamInfo(p1)
                team2 = TeamInfo(p2)

                # Setting Correct Winner Info
                players = ["winner", "loser"]

                if winnerId != set.get("winnerId"):
                    players.reverse()

                # Compiling Set Data for display
                set = {
                    "phase_id": phaseIdentifier,
                    "phase_name": phaseName,
                    "round_name": StartGGConvert.TranslateRoundName(set.get("fullRoundText")),
                    f"{players[0]}_score": set.get("entrant1Score")
                    if set.get("entrant1Score") is not None
                    else "0",
                    f"{players[0]}_seed": team1Seed,
                    f"{players[0]}_team": {index + 1: player for index, player in enumerate(team1)},
                    f"{players[0]}_team_name": t1Name,
                    f"{players[1]}_score": set.get("entrant2Score")
                    if set.get("entrant2Score") is not None
                    else "0",
                    f"{players[1]}_seed": team2Seed,
                    f"{players[1]}_team": {index + 1: player for index, player in enumerate(team2)},
                    f"{players[1]}_team_name": t2Name,
                    "bracket_type": deep_get(set, "phaseGroup.phase.bracketType"),
                }

                set_data.append(set)

            return CompletedSetsHelper.Finish(set_data, self.context)
        except Exception as e:
            logger.error(traceback.format_exc())
            return []

    def GetPlayerHistoryStandings(
        self, playerID, playerNumber, gameType, callback, progress_callback, cancel_event
    ):
        try:
            data = self.QueryRequests(
                "https://www.start.gg/api/-/gql",
                type=requests.post,
                jsonParams={
                    "operationName": "TournamentHistoryDataQuery",
                    "variables": {"playerID": playerID, "gameID": gameType},
                    "query": StartGGDataProvider.HistorySetsQuery,
                },
            )

            standings = as_list(deep_get(data, "data.player.recentStandings"))

            set_data = []

            for standing in standings:
                if not standing.get("placement"):
                    continue
                try:
                    entry = self._ParseHistoryStanding(standing)
                except Exception:
                    logger.error(traceback.format_exc())
                    entry = None
                if entry:
                    set_data.append(entry)

            callback.emit({"playerNumber": playerNumber, "history_sets": set_data})
        except Exception as e:
            logger.error(traceback.format_exc())
            callback.emit({"playerNumber": playerNumber, "history_sets": []})

    def _ParseHistoryStanding(self, standing):
        """A placement of the player's tournament history, None when start.gg
        sent it without its event (deleted or hidden events)"""
        event = as_dict(deep_get(standing, "entrant.event"))
        if not event:
            logger.warning(f"Tournament history: placement without an event: {standing}")
            return None
        tournament = as_dict(event.get("tournament"))

        images = as_list(tournament.get("images"))
        tournamentPicture = as_dict(images[0]).get("url") if images else None
        if not tournamentPicture:
            logger.info(f"No logo for {tournament.get('name') or '?'} - {event.get('name') or '?'}")

        return {
            "placement": standing.get("placement"),
            "event_name": event.get("name"),
            "tournament_name": tournament.get("name"),
            "tournament_picture": tournamentPicture,
            "entrants": event.get("numEntrants"),
            "event_date": event.get("startAt"),
            "seed": deep_get(standing, "entrant.initialSeedNum"),
            "bracket_type": EventBracketType(
                [phase.get("bracketType") for phase in as_list(event.get("phases"))]
            ),
        }

    def GetSetDurations(self, count=40, progress_callback=None, cancel_event=None):
        """The event's last completed sets, for how long sets take:
        [{id, startedAt, completedAt, totalGames, dq}]."""
        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "SetDurationsQuery",
                "variables": {"eventSlug": self._EventSlug(), "perPage": count},
                "query": StartGGDataProvider.SetDurationsQuery,
            },
        )
        return [
            {
                "id": s.get("id"),
                "startedAt": s.get("startedAt"),
                "completedAt": s.get("completedAt"),
                "totalGames": s.get("totalGames"),
                "dq": -1 in (s.get("entrant1Score"), s.get("entrant2Score")),
            }
            for s in deep_get(data, "data.event.sets.nodes", []) or []
            if s
        ]

    def GetRecentSets(
        self, id1, id2, videogame, callback, requestTime, progress_callback, cancel_event
    ):
        try:
            pid1, pid2 = str(id1[0]), str(id2[0])

            logger.info("Get recent sets start")

            def cancelled():
                return cancel_event is not None and cancel_event.is_set()

            # start.gg gives a player's sets against an opponent (opponentId),
            # most recent first. It can't be combined with a videogame filter,
            # so sets of other games are left out here.
            perPage = self._recent_sets_per_page
            first = self._FetchHeadToHeadPage(pid1, pid2, 1, perPage)
            if cancelled():
                return

            totalPages = min(first["totalPages"], self._recent_sets_max_sets // perPage)
            nodes = list(first["nodes"])
            if totalPages > 1:
                # Keep the worker count low so start.gg doesn't start rate limiting us
                with ThreadPoolExecutor(max_workers=4) as executor:
                    for page in executor.map(
                        lambda page: self._FetchHeadToHeadPage(pid1, pid2, page, perPage),
                        range(2, totalPages + 1),
                    ):
                        nodes.extend(page["nodes"])

            if cancelled():
                return

            recentSets = []
            seen = set()
            for _set in nodes:
                if not _set or _set.get("id") in seen:
                    continue
                seen.add(_set.get("id"))
                event = _set.get("event") or {}
                if str(deep_get(event, "videogame.id")) != str(videogame):
                    continue
                entry = self._ParseRecentSet(_set, event, pid1, pid2)
                if entry:
                    recentSets.append(entry)

            # Sets of the same event keep start.gg's order
            recentSets.sort(key=lambda s: s.get("timestamp") or 0, reverse=True)
            logger.info(f"Recent sets size: {len(recentSets)}")
            callback.emit({"sets": recentSets, "request_time": requestTime})
        except Exception as e:
            logger.error(traceback.format_exc())
            callback.emit({"sets": [], "request_time": requestTime})

    def _FetchHeadToHeadPage(self, pid1, pid2, page, perPage):
        # A page of pid1's sets against pid2: {"totalPages", "nodes"}. If
        # start.gg refuses it (the complexity cap, e.g. sets with many games),
        # it's asked for again as two pages of half the size.
        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "HeadToHeadQuery",
                "variables": {"pid1": pid1, "pid2": pid2, "page": page, "perPage": perPage},
                "query": StartGGDataProvider.HeadToHeadQuery,
            },
        )
        sets = deep_get(data, "data.player.sets")
        if sets is None and (data or {}).get("errors") and perPage > 1 and perPage % 2 == 0:
            half = perPage // 2
            pages = [
                self._FetchHeadToHeadPage(pid1, pid2, p, half) for p in (page * 2 - 1, page * 2)
            ]
            return {
                "totalPages": (pages[0]["totalPages"] + 1) // 2,
                "nodes": pages[0]["nodes"] + pages[1]["nodes"],
            }
        return {
            "totalPages": deep_get(sets, "pageInfo.totalPages", 1) or 1,
            "nodes": deep_get(sets, "nodes", []) or [],
        }

    def _ParseRecentSet(self, _set, event, pid1, pid2):
        try:
            p1Slot = StartGGConvert.RecentSetPlayer1Slot(_set, pid1, pid2)
            if p1Slot is None or not event:
                return None

            # DQs
            if _set.get("entrant1Score") == -1 or _set.get("entrant2Score") == -1:
                return None

            phaseName = ""
            phaseIdentifier = ""

            # This is because a display identifier at a major (Ex. Pools C12) will return C12,
            # otherwise startgg will just return a string containing "1"
            if deep_get(_set, "phaseGroup.displayIdentifier") != "1":
                phaseIdentifier = deep_get(_set, "phaseGroup.displayIdentifier")
            phaseName = deep_get(_set, "phaseGroup.phase.name")

            entrantIds = [str(deep_get(slot, "entrant.id") or "") for slot in _set.get("slots")]
            p1Entrant = entrantIds[p1Slot]
            p2Entrant = entrantIds[1 - p1Slot]

            winner = 0 if str(_set.get("winnerId")) == p1Entrant else 1

            scores = [_set.get("entrant1Score"), _set.get("entrant2Score")]
            if scores[0] is not None and scores[1] is not None:
                score = [scores[p1Slot], scores[1 - p1Slot]]
            else:
                score = ["W", "L"] if winner == 0 else ["L", "W"]

            # Count characters per entrant from game selections
            chars_by_entrant = {p1Entrant: Counter(), p2Entrant: Counter()}
            for game in _set.get("games") or []:
                for selection in game.get("selections") or []:
                    eid = str(deep_get(selection, "entrant.id") or "")
                    char_id = selection.get("selectionValue")
                    if eid in chars_by_entrant and char_id:
                        chars_by_entrant[eid][char_id] += 1

            def _resolve_char_dict_recent(eid):
                result = {}
                for idx, (char_id, _) in enumerate(
                    chars_by_entrant.get(eid, Counter()).most_common(), 1
                ):
                    char = self.context.games.GetCharacterFromStartGGId(char_id)
                    if not char:
                        continue
                    _key, char_info = char
                    codename = char_info.get("codename", _key)
                    assets = self.context.games.GetCharacterAssets(codename, 0)
                    result[str(idx)] = {
                        "name": char_info.get("display_name", codename),
                        "codename": codename,
                        "assets": assets,
                        "skin": 0,
                        "variant": {},
                    }
                return result

            return {
                "id": _set.get("id"),
                "tournament": deep_get(event, "tournament.name"),
                "event": event.get("name"),
                "online": event.get("isOnline"),
                "score": score,
                "timestamp": event.get("startAt"),
                "winner": winner,
                "round": StartGGConvert.TranslateRoundName(_set.get("fullRoundText")),
                "phase_name": phaseName,
                "phase_id": phaseIdentifier,
                "p1_char": {"character": _resolve_char_dict_recent(p1Entrant)},
                "p2_char": {"character": _resolve_char_dict_recent(p2Entrant)},
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            return None

    # =====================================================
    # ENTRANTS AND PLAYERS
    # =====================================================
    def _FetchEntrantsPage(self, eventSlug, page):
        return self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "EventEntrantsListQuery",
                "variables": {
                    "eventSlug": eventSlug,
                    "page": page,
                },
                "query": StartGGDataProvider.EntrantsQuery,
            },
        )

    def FetchEntrants(self, progress_callback=None, cancel_event=None):
        players = []
        try:
            eventSlug = self.url.split("start.gg/")[1]
            logger.info("Starting Entrant Import")
            firstPage = self._FetchEntrantsPage(eventSlug, 1)
            totalPages = deep_get(firstPage, "data.event.entrants.pageInfo.totalPages") or 0
            logger.info(f"Entrant pages: {totalPages}")

            # Page 1 tells us how many pages there are; fetch the rest in
            # parallel. executor.map keeps results in page order.
            pages = [firstPage]
            if totalPages > 1:
                # Keep the worker count low so start.gg doesn't start rate limiting us
                with ThreadPoolExecutor(max_workers=6) as executor:
                    pages.extend(
                        executor.map(
                            lambda p: self._FetchEntrantsPage(eventSlug, p),
                            range(2, totalPages + 1),
                        )
                    )

            if cancel_event is not None and cancel_event.is_set():
                return []

            for data in pages:
                for team in as_list(deep_get(data, "data.event.entrants.nodes")):
                    seed = team.get("initialSeedNum", 0)
                    for entrant in as_list(team.get("participants")):
                        playerData = StartGGConvert.ProcessEntrantData(
                            entrant, gameAssets=self.context.games
                        )
                        playerData["seed"] = seed
                        self.player_seeds[playerData["id"][0]] = seed
                        players.append(playerData)

            logger.info(f"Entrants processed: {len(players)}")
        except Exception as e:
            logger.error(traceback.format_exc())
        return players

    def UseLocalPlayerData(self):
        return self.context.UseLocalPlayerData()

    def FillFromLocalDB(self, playerData):
        """Fills playerData's profile fields (LOCAL_PROFILE_FIELDS) from the
        local player DB. A player not in it yet is looked up on start.gg
        once and saved to it, so the next sets find them there."""
        tag = MakeTag(playerData.get("prefix"), playerData.get("gamerTag"))
        if not tag:
            return playerData

        saved = self.context.GetSavedPlayer(tag)
        if saved is not None:
            for field in StartGGDataProvider.LOCAL_PROFILE_FIELDS:
                if saved.get(field) and not playerData.get(field):
                    playerData[field] = saved[field]
            return playerData

        ids = playerData.get("id") or []
        userId = ids[1] if len(ids) > 1 else None
        profile = self.GetUserProfile(userId) if userId else None
        if profile:
            playerData.update(profile)
            self.context.SavePlayers(
                [
                    {
                        "prefix": playerData.get("prefix"),
                        "gamerTag": playerData.get("gamerTag"),
                        **deep_clone(profile),
                    }
                ]
            )
        return playerData

    def GetUserProfile(self, userId):
        """The LOCAL_PROFILE_FIELDS of a start.gg user, {} when they have
        none, or None when the request failed. Kept for the session."""
        with self._profileLock:
            if userId in self._profile_cache:
                return self._profile_cache[userId]

        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "UserProfileQuery",
                "variables": {"id": userId},
                "query": StartGGDataProvider.UserProfileQuery,
            },
        )
        user = deep_get(data, "data.user")
        if not user:
            # A failed request isn't cached, so it's tried again next time
            return None if not data or data.get("errors") else {}

        parsed = StartGGConvert.ProcessEntrantData(
            {"player": {}, "user": user}, gameAssets=self.context.games
        )
        profile = {
            field: parsed[field]
            for field in StartGGDataProvider.LOCAL_PROFILE_FIELDS
            if parsed.get(field)
        }
        with self._profileLock:
            self._profile_cache[userId] = profile
        return profile

    def EnrichPlayerData(self, playerData, blocking=True):
        # Lazy mains fill for entrants loaded via GetTournamentPhaseGroup.
        # That query no longer embeds the per-entrant sets->games->selections
        # lookup (it single-handedly pushed StartGG's GraphQL complexity
        # budget over the 1000-object cap on larger brackets), so mains are
        # fetched here per-player instead, same as ParryGGDataProvider does
        # for linked accounts. Without blocking, only cached ones (the
        # manager fetches the others in the background, see PlayerMains.py).
        if not playerData or playerData.get("mains"):
            return playerData
        key = self.MainsKey(playerData)
        if key is None:
            return playerData
        if self.IsMainsCached(key):
            mains = self._mains_cache[key]
        elif not blocking:
            return playerData
        else:
            mains = self.FetchMains(key)
        if mains:
            playerData["mains"] = mains
        return playerData

    # =====================================================
    # PLAYER MAINS
    # =====================================================
    def MainsKey(self, playerData):
        """What a player's mains are cached by: their start.gg user and the
        game, None if either is unknown"""
        slug = (playerData or {}).get("startgg_user_slug")
        videogameId = (self.context.games.selectedGame or {}).get("smashgg_game_id")
        if not slug or not videogameId:
            return None
        return (slug, videogameId)

    def IsMainsCached(self, key):
        return key in self._mains_cache

    def FetchMains(self, key):
        """A player's mains (by MainsKey), cached for the event. None if the
        request failed: that isn't cached, so it's retried next time."""
        if key in self._mains_cache:
            return self._mains_cache[key]
        mains = self._FetchUserMains(*key)
        if mains is not None:
            self._mains_cache[key] = mains
        return mains

    def GetCachedMains(self, playerData):
        key = self.MainsKey(playerData)
        return self._mains_cache.get(key) if key else None

    def GetUserMains(self, slug, videogameId):
        # Per-user mains lookup (no other code path fetches mains for a
        # user in isolation — see ProcessEntrantData/GetMatch which only
        # populate mains as a side effect of an event-scoped query).
        # Reuses ProcessEntrantData's selection-counting via a synthesized
        # entrant, then runs the character-ID → HyperDrive-codename mapping
        # locally (the mapping is normally inside ProcessEntrantData's
        # `if user:` branch, which doesn't apply to a user-only synthesis).
        # Returns ({gameCodename: [[char_name], ...]}) or {}.
        return self._FetchUserMains(slug, videogameId) or {}

    def _FetchUserMains(self, slug, videogameId):
        # Same as GetUserMains, but returns None when the request itself
        # failed so callers can tell "no mains" apart from "try again".
        if not slug or not videogameId:
            return {}
        data = self.QueryRequests(
            "https://www.start.gg/api/-/gql",
            type=requests.post,
            jsonParams={
                "operationName": "UserMainsQuery",
                "variables": {"userSlug": slug, "videogameId": videogameId},
                "query": StartGGDataProvider.UserMainsQuery,
            },
        )
        if not data or data.get("errors") or not data.get("data"):
            return None
        player = deep_get(data, "data.user.player")
        if not player:
            return {}
        startgg_mains = (
            StartGGConvert.ProcessEntrantData(
                {"player": player}, gameAssets=self.context.games
            ).get("startggMains")
            or []
        )
        selected = self.context.games.selectedGame or {}
        gameCodename = selected.get("codename")
        if not gameCodename:
            return {}
        mains = []
        for sggmain in startgg_mains:
            mapped = self.context.games.GetCharacterFromStartGGId(sggmain[0])
            if mapped:
                mains.append([mapped[0]])
        return {gameCodename: mains} if mains else {}

    # =====================================================
    # STANDINGS
    # =====================================================
    def GetStandings(self, playerNumber, progress_callback, cancel_event):
        try:
            eventSlug = self.url.split("start.gg/")[1]

            def cancelled():
                return cancel_event is not None and cancel_event.is_set()

            # Each placement is its own page: an entrant's sets (for their
            # mains) are too heavy to ask for several entrants at once
            # without going over the complexity cap
            def fetchPlacement(placement):
                if cancelled():
                    return None
                return self.QueryRequests(
                    "https://www.start.gg/api/-/gql",
                    type=requests.post,
                    jsonParams={
                        "operationName": "TournamentStandingsQuery",
                        "variables": {"playerNumber": placement, "eventSlug": eventSlug},
                        "query": StartGGDataProvider.TournamentStandingsQuery,
                    },
                )

            # Page 1 says how many entrants there are, so no requests are
            # sent for placements past the last one
            first = fetchPlacement(1)
            if cancelled():
                return []
            total = deep_get(first, "data.event.standings.pageInfo.total")
            count = min(playerNumber, total) if isinstance(total, int) else playerNumber

            pages = {1: first}
            done = 1
            if progress_callback:
                progress_callback(done, count)

            # Keep the worker count low so start.gg doesn't start rate limiting us
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {
                    executor.submit(fetchPlacement, placement): placement
                    for placement in range(2, count + 1)
                }
                for future in as_completed(futures):
                    pages[futures[future]] = future.result()
                    done += 1
                    if progress_callback:
                        progress_callback(done, count)
                    if cancelled():
                        for f in futures:
                            f.cancel()
                        return []

            standings = []
            for placement in range(1, count + 1):
                standings.extend(
                    deep_get(pages.get(placement), "data.event.standings.nodes", []) or []
                )

            teams = []

            for standing in standings:
                team = {}

                participants = as_list(deep_get(standing, "entrant.participants"))

                if len(participants) > 1:
                    team["name"] = deep_get(standing, "entrant.name")

                team["players"] = []
                team["wins"] = deep_get(standing, "setRecordWithoutByes.wins", 0)
                team["losses"] = deep_get(standing, "setRecordWithoutByes.losses", 0)
                team["winPercentage"] = deep_get(
                    standing, "setRecordWithoutByes.winPercentage", "N/A"
                )

                sets = deep_get(standing, "entrant.paginatedSets.nodes")
                seed = deep_get(standing, "entrant.initialSeedNum")
                for entrant in participants:
                    playerData = StartGGConvert.ProcessEntrantData(
                        entrant, sets, gameAssets=self.context.games
                    )
                    if isinstance(seed, int):
                        playerData["seed"] = seed
                    team["players"].append(playerData)

                teams.append(team)
            return teams
        except Exception as e:
            logger.error(traceback.format_exc())
            return []


StartGGDataProvider.CompletedSetsQuery = ReadQuery("CompletedSets")
StartGGDataProvider.EntrantsQuery = ReadQuery("Entrants")
StartGGDataProvider.FutureSetQuery = ReadQuery("FutureSet")
StartGGDataProvider.HistorySetsQuery = ReadQuery("PlayerTournamentHistory")
StartGGDataProvider.LastSetsQuery = ReadQuery("PlayerLastSets")
StartGGDataProvider.HeadToHeadQuery = ReadQuery("HeadToHead")
StartGGDataProvider.SetQuery = ReadQuery("Set")
StartGGDataProvider.SetsQuery = ReadQuery("Sets")
StartGGDataProvider.StationsQuery = ReadQuery("Stations")
StartGGDataProvider.StationSetsQuery = ReadQuery("StationSets")
StartGGDataProvider.StreamQueueQuery = ReadQuery("StreamQueue")
StartGGDataProvider.StreamSetsQuery = ReadQuery("StreamSets")
StartGGDataProvider.TournamentDataQuery = ReadQuery("TournamentData")
StartGGDataProvider.TournamentPhasesQuery = ReadQuery("TournamentPhases")
StartGGDataProvider.TournamentPhaseGroupSeedsQuery = ReadQuery("TournamentPhaseGroupSeeds")
StartGGDataProvider.TournamentPhaseGroupSetsQuery = ReadQuery("TournamentPhaseGroupSets")
StartGGDataProvider.TournamentStandingsQuery = ReadQuery("TournamentStandings")
StartGGDataProvider.UserSetQuery = ReadQuery("UserSet")
StartGGDataProvider.UserMainsQuery = ReadQuery("UserMains")
StartGGDataProvider.UserProfileQuery = ReadQuery("UserProfile")
StartGGDataProvider.TournamentSlugQuery = ReadQuery("TournamentSlug")
StartGGDataProvider.StreamsStationsQuery = ReadQuery("StreamsStations")
StartGGDataProvider.SetDurationsQuery = ReadQuery("SetDurations")
