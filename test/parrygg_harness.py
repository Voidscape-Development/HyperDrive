# A made-up parry.gg for the provider's tests: a small tournament (one event,
# one double elimination bracket of four players, one stream with a set on
# it) answered by fake gRPC services, so ParryGGDataProvider can be run
# without the network. The services can be told to fail.
import grpc
from parrygg.models.bracket_pb2 import (
    Bracket,
    BracketType,
    Match,
    MatchContext,
    MatchState,
    Round,
    Seed,
    Slot,
    SlotState,
)
from parrygg.models.entrant_pb2 import Entrant, EventEntrant
from parrygg.models.event_pb2 import Event, LocationType, Placement
from parrygg.models.hierarchy_pb2 import Hierarchy, Path, PathType
from parrygg.models.phase_pb2 import Phase
from parrygg.models.stream_pb2 import (
    Stream,
    StreamPlatform,
    StreamQueueEntry,
    StreamQueueEntryStatus,
)
from parrygg.models.tournament_pb2 import Tournament
from parrygg.models.user_pb2 import User
from parrygg.services.bracket_service_pb2 import GetBracketResponse
from parrygg.services.event_service_pb2 import (
    GetEventEntrantsResponse,
    GetEventPlacementsResponse,
    GetEventResponse,
)
from parrygg.services.match_service_pb2 import GetMatchesResponse, GetMatchResponse
from parrygg.services.stream_service_pb2 import (
    GetStreamQueueResponse,
    GetTournamentStreamsResponse,
)
from parrygg.services.tournament_service_pb2 import (
    GetTournamentResponse,
    GetTournamentsResponse,
)
from parrygg.services.user_service_pb2 import GetUserPlacementsResponse, GetUserResponse

from src.TournamentDataProvider.ParryGGDataProvider import ParryGGDataProvider

URL = "https://parry.gg/weekly/singles"
TOURNAMENT_ID, EVENT_ID, PHASE_ID, BRACKET_ID, STREAM_ID = "t1", "e1", "ph1", "br1", "st1"
PLAYERS = ["Ana", "Bo", "Cy", "Di"]


class RpcError(grpc.RpcError):
    def __init__(self, code, details="made up"):
        super().__init__(details)
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def UserOf(index):
    return User(
        id=f"u{index + 1}",
        gamer_tag=PLAYERS[index],
        first_name=PLAYERS[index],
        last_name="Doe",
        sponsor_name="TSM" if index == 0 else "",
        pronouns="they/them",
        location_country="US",
        location_state="CA",
    )


def EntrantOf(index):
    return EventEntrant(
        id=f"ee{index + 1}",
        event_id=EVENT_ID,
        seed=index + 1,
        entrant=Entrant(id=f"en{index + 1}", users=[UserOf(index)]),
    )


def SeedOf(index):
    return Seed(id=f"s{index + 1}", seed=index + 1, event_entrant=EntrantOf(index))


def MatchOf(id, round, players, scores=None, winners=True, state=None):
    match = Match(
        id=id,
        identifier=id.upper(),
        round=round,
        winners_side=winners,
        state=state
        if state is not None
        else (MatchState.MATCH_STATE_COMPLETED if scores else MatchState.MATCH_STATE_READY),
    )
    for slot, player in enumerate(players):
        match.slots.append(
            Slot(
                slot=slot,
                seed_id=f"s{player + 1}",
                score=(scores or [0, 0])[slot],
                state=SlotState.SLOT_STATE_NUMERIC,
            )
        )
    if scores:
        match.ended_at.seconds = 1700000000 + round
    return match


class World:
    """parry.gg's data, and its services. fail: the gRPC status code every
    call fails with, or {method name: code}; None when they work."""

    def __init__(self):
        self.fail = None
        self.calls = []

        self.matches = {
            "m1": MatchOf("m1", 1, [0, 3], [2, 0]),
            "m2": MatchOf("m2", 1, [1, 2], [2, 1]),
            "m3": MatchOf("m3", 2, [0, 1]),
        }
        self.matches["m3"].stream_queue_entry.CopyFrom(
            StreamQueueEntry(
                id="q1",
                stream_id=STREAM_ID,
                match_id="m3",
                position=1,
                status=StreamQueueEntryStatus.STREAM_QUEUE_ENTRY_STATUS_ONSTREAM,
            )
        )
        self.rounds = [
            Round(number=1, winners_side=True, label="Winners Semi-Final"),
            Round(number=2, winners_side=True, label="Winners Final"),
        ]
        self.seeds = [SeedOf(i) for i in range(4)]
        self.bracket = Bracket(
            id=BRACKET_ID,
            name="Bracket",
            index=0,
            type=BracketType.BRACKET_TYPE_DOUBLE_ELIMINATION,
            matches=list(self.matches.values()),
            seeds=self.seeds,
            rounds=self.rounds,
        )
        self.phase = Phase(
            id=PHASE_ID,
            name="Top 4",
            bracket_type=BracketType.BRACKET_TYPE_DOUBLE_ELIMINATION,
            brackets=[Bracket(id=BRACKET_ID, name="Bracket", index=0)],
        )
        self.event = Event(
            id=EVENT_ID,
            tournament_id=TOURNAMENT_ID,
            name="Singles",
            slug="singles",
            entrant_count=4,
            entrant_size=1,
            location_type=LocationType.LOCATION_TYPE_OFFLINE,
            phases=[self.phase],
        )
        self.event.game.slug = "super-smash-bros-ultimate"
        self.event.game.name = "Super Smash Bros. Ultimate"
        self.event.start_date.seconds = 1700000000
        self.tournament = Tournament(
            id=TOURNAMENT_ID,
            name="Weekly",
            venue_address="1 Main St",
            num_attendees=4,
            time_zone="America/New_York",
            location_type=LocationType.LOCATION_TYPE_OFFLINE,
            events=[self.event],
        )
        self.tournament.start_date.seconds = 1700000000
        self.tournament.end_date.seconds = 1700003600
        self.stream = Stream(
            id=STREAM_ID,
            tournament_id=TOURNAMENT_ID,
            platform=StreamPlatform.STREAM_PLATFORM_TWITCH,
            channel="weeklytv",
            display_name="Weekly TV",
            capacity=1,
        )

    # =====================================================
    # ANSWERS
    # =====================================================
    def Hierarchy(self):
        return Hierarchy(
            paths=[
                Path(id=TOURNAMENT_ID, type=PathType.PATH_TYPE_TOURNAMENT, name="Weekly"),
                Path(id=EVENT_ID, type=PathType.PATH_TYPE_EVENT, name="Singles"),
                Path(id=PHASE_ID, type=PathType.PATH_TYPE_PHASE, name="Top 4"),
                Path(id=BRACKET_ID, type=PathType.PATH_TYPE_BRACKET, name="Bracket"),
            ]
        )

    def Context(self, match):
        seeds = {s.id: s for s in self.seeds}
        round = next(r for r in self.rounds if r.number == match.round)
        return MatchContext(
            match=match,
            hierarchy=self.Hierarchy(),
            seeds=[seeds[slot.seed_id] for slot in match.slots],
            round=round,
        )

    def GetTournament(self, request):
        if request.tournament_slug != "weekly":
            raise RpcError(grpc.StatusCode.NOT_FOUND)
        return GetTournamentResponse(tournament=self.tournament)

    def GetTournaments(self, request):
        return GetTournamentsResponse(tournaments=[self.tournament])

    def GetEvent(self, request):
        return GetEventResponse(event=self.event)

    def GetEventEntrants(self, request):
        return GetEventEntrantsResponse(event_entrants=[EntrantOf(i) for i in range(4)])

    def GetEventPlacements(self, request):
        return GetEventPlacementsResponse(
            placements=[
                Placement(event_entrant=EntrantOf(i), placement=i + 1, seed=i + 1) for i in range(4)
            ]
        )

    def GetBracket(self, request):
        return GetBracketResponse(bracket=self.bracket)

    def GetMatch(self, request):
        if request.id not in self.matches:
            raise RpcError(grpc.StatusCode.NOT_FOUND)
        return GetMatchResponse(match=self.Context(self.matches[request.id]))

    def GetMatches(self, request):
        return GetMatchesResponse(matches=[self.Context(m) for m in self.matches.values()])

    def GetTournamentStreams(self, request):
        return GetTournamentStreamsResponse(streams=[self.stream])

    def GetStreamQueue(self, request):
        return GetStreamQueueResponse(entries=[self.matches["m3"].stream_queue_entry])

    def GetUser(self, request):
        return GetUserResponse(user=UserOf(int(request.id[1:]) - 1))

    def GetUserPlacements(self, request):
        return GetUserPlacementsResponse()


class Service:
    """Every parry.gg service at once: its methods are the world's"""

    def __init__(self, world):
        self.world = world

    def __getattr__(self, name):
        answer = getattr(self.world, name)

        def call(request, metadata=None, timeout=None):
            self.world.calls.append(name)
            fail = self.world.fail
            code = fail.get(name) if isinstance(fail, dict) else fail
            if code is not None:
                raise RpcError(code)
            return answer(request)

        call.__name__ = name
        return call


class Channel:
    def close(self):
        pass


def NewProvider(world, context, url=URL, connect=True):
    """A parry.gg provider asking the made-up world instead of parry.gg"""
    provider = ParryGGDataProvider(url, None, None, "key", context=context)
    service = Service(world)
    provider.channel = Channel()
    for name in [
        "tournament",
        "event",
        "phase",
        "bracket",
        "match",
        "matchgame",
        "entrant",
        "user",
        "game",
        "stream",
    ]:
        setattr(provider, f"{name}_service", service)
    if connect:
        provider.Connect()
    return provider
