"""What tournament data providers return: the contract every provider
(start.gg, parry.gg, ...) follows, so the rest of the app doesn't depend on
which one is in use. TournamentDataProvider's methods are annotated with
these, and test/test_startgg_provider.py checks start.gg's results against
them.

They describe the shapes as they are, including where methods disagree on
the same thing (a player's tag is gamerTag in a Set, name in a FutureSet and
gamertag in a CompletedSet). Many of these reach the layouts through the
program state, so renaming a key can break layouts.

Keys a provider leaves out when it has no value (a player without a Twitter
account has no "twitter") are in a total=False base class: Python 3.10,
which the Windows build uses, has no NotRequired.
"""

from typing import TypedDict

# =====================================================
# PLAYERS
# =====================================================


class _PlayerOptional(TypedDict, total=False):
    avatar: str
    twitter: str
    pronoun: str
    state_code: str


class Player(_PlayerOptional):
    """A player as the sets, brackets and standings give them"""

    gamerTag: str
    prefix: str | None
    # Their real name, when they share it
    name: str | None
    # [start.gg player id, start.gg user id]
    id: list
    # {platform: handle}, see Helpers/SocialsHelper.py
    socials: dict


class Entrant(Player):
    """An entrant, as added to the player database"""

    seed: int
    startgg_user_slug: str


class CharacterExport(TypedDict):
    """A character, as the layouts get it"""

    name: str
    codename: str
    assets: dict


class _CharacterWithSkin(CharacterExport, total=False):
    en_name: str
    skin: int
    variant: dict


class CharacterSlot(TypedDict):
    """A player's characters: {"1": character, "2": ...}"""

    character: dict[str, _CharacterWithSkin]


# =====================================================
# TOURNAMENT
# =====================================================


class TournamentData(TypedDict):
    tournamentName: str
    eventName: str
    numEntrants: int
    # Unix timestamps
    startAt: int
    endAt: int
    eventStartAt: int
    address: str
    # The venue's city and state (or province, region...) alone and together
    city: str
    state: str
    cityState: str
    logo: str
    banner: str
    shortLink: str


# =====================================================
# PHASES AND BRACKETS
# =====================================================


class PhaseGroupRef(TypedDict):
    id: int
    name: str
    bracketType: str


class Phase(TypedDict):
    id: int
    name: str
    groups: list[PhaseGroupRef]


class BracketSlotResult(TypedDict):
    # "seed", "set" or "bye"
    prereqType: str
    entrantId: str | None


class BracketSlot(BracketSlotResult):
    prereqId: str | None
    # The slot's player, as an index in PhaseGroup.entrants
    player: int | None
    placement: int | None


class _BracketSetBase(TypedDict):
    id: str
    score: list
    finished: bool
    # 0 or 1, None if undecided
    winnerSlot: int | None


class BracketSetResult(_BracketSetBase):
    slots: list[BracketSlotResult]


class BracketSet(_BracketSetBase):
    slots: list[BracketSlot]
    # The set's letters, like start.gg's
    identifier: str
    name: str
    # Winners rounds are 1, 2..., losers rounds -1, -2...
    round: int


class PhaseGroupEntrant(TypedDict):
    players: list[Player]


class PhaseGroup(TypedDict):
    entrants: list[PhaseGroupEntrant]
    entrantIds: list
    sets: list[BracketSet]
    progressionsIn: int
    progressionsOut: int


class PhaseGroupSets(TypedDict):
    """Only the results, to refresh a bracket already loaded"""

    sets: list[BracketSetResult]


# =====================================================
# SETS
# =====================================================


class Game(TypedDict):
    # 0 or 1, None if undecided
    winner: int | None
    # The stage's codename, None if not reported
    stage: str | None
    # [[character name], ...] per slot
    characters: list


class _SetPlayerOptional(TypedDict, total=False):
    # [character name, skin]
    mains: list
    city: str


class SetPlayer(Player, _SetPlayerOptional):
    seed: int
    wins: int
    losses: int
    winPercentage: str


class SetListPlayer(TypedDict):
    """A player of a SetListItem: fewer fields than a Player, and wins and
    losses as text"""

    gamerTag: str
    prefix: str | None
    name: str | None
    id: list
    wins: str
    losses: str
    winPercentage: str


class _SetBase(TypedDict):
    """What SetListItem and Set have in common"""

    id: int
    round: int
    round_name: str
    tournament_phase: str
    bracket_type: str
    # start.gg's set state: 1 waiting, 2 in progress, 3 finished
    state: int
    p1_name: str
    p2_name: str
    team1score: int
    team2score: int
    entrant_ids: list
    games: list[Game]
    isPools: bool
    stream: str | None


class _SetListItemOptional(TypedDict, total=False):
    p1_seed: int | None
    p2_seed: int | None
    isOnline: bool | None


class SetListItem(_SetBase, _SetListItemOptional):
    """A set in the list to pick a set from"""

    # Per team, its players
    entrants: list[list[SetListPlayer]]
    # The station's number (an int), or "" without one
    station: int | str


class _SetOptional(TypedDict, total=False):
    has_selection_data: bool


class Set(_SetBase, _SetOptional):
    """A set loaded into a scoreboard"""

    entrants: list[list[SetPlayer]]
    # The station's number as text, "" without one
    station: str
    p1_seed: int
    p2_seed: int
    isOnline: bool
    team1losers: bool
    team2losers: bool
    bestOf: int | None
    ruleset: dict
    stage_strike: dict
    strikedBy: list
    currPlayer: int


class FuturePlayer(TypedDict):
    """A player of a FutureSet. Their tag is "name", their sponsor "team"."""

    name: str
    team: str | None
    mergedName: str
    real_name: str | None
    id: list
    twitter: str
    pronoun: str
    socials: dict
    country: dict
    state: dict
    online_avatar: str


class FutureTeam(TypedDict):
    teamName: str
    seed: int | None
    losers: bool
    # {"1": player, ...}
    player: dict[str, FuturePlayer]


class FutureSet(TypedDict):
    """A set in a stream's or station's queue"""

    id: int
    match: str
    phase: str
    event: str
    best_of: int
    best_of_text: str
    state: int
    station: int | None
    isCurrentEvent: bool
    # {"1": team, "2": team}
    team: dict[str, FutureTeam]


# =====================================================
# STREAMS AND STATIONS
# =====================================================


class Station(TypedDict):
    """A station or a stream to load sets from"""

    id: int
    # The station's number, or the stream's name
    identifier: int | str
    # "station" or "stream"
    type: str
    stream: str


class StreamRef(TypedDict):
    id: int
    name: str


class StationRef(TypedDict):
    id: int
    number: int
    # The name of the stream it's on, "" if none
    stream: str


class StreamsAndStations(TypedDict):
    streams: list[StreamRef]
    stations: list[StationRef]


# =====================================================
# SET HISTORY
# =====================================================


class CompletedPlayer(TypedDict):
    """A player of a CompletedSet. Their tag is "gamertag"."""

    gamertag: str
    sponsor: str | None
    country: dict
    state: dict
    # {"1": character, ...}
    characters: dict[str, CharacterExport]


class CompletedSet(TypedDict):
    phase_id: str
    phase_name: str
    round_name: str
    bracket_type: str
    winner_score: int
    loser_score: int
    winner_seed: int | None
    loser_seed: int | None
    winner_team_name: str
    loser_team_name: str
    # {"1": player, ...}
    winner_team: dict[str, CompletedPlayer]
    loser_team: dict[str, CompletedPlayer]
    # Placement rounds the winner was expected to finish below the loser
    upset_factor: int


class SetDuration(TypedDict):
    id: int
    # Unix timestamps
    startedAt: int | None
    completedAt: int | None
    totalGames: int | None
    dq: bool


class LastSet(TypedDict):
    """A set of a player's last sets in the event"""

    phase_id: str
    phase_name: str
    round_name: str
    player1_name: str
    player1_team: str | None
    player1_score: int
    player1_seed: int | None
    player2_name: str
    player2_team: str | None
    player2_score: int
    player2_seed: int | None
    player_char: CharacterSlot
    # (sic)
    oponent_char: CharacterSlot


class LastSets(TypedDict):
    """What GetLastSets emits"""

    playerNumber: str
    last_sets: list[LastSet]


class HistorySet(TypedDict):
    """A player's placement in a past event"""

    placement: int
    seed: int | None
    entrants: int
    event_name: str
    tournament_name: str
    tournament_picture: str
    event_date: int
    bracket_type: str


class HistorySets(TypedDict):
    """What GetPlayerHistoryStandings emits"""

    playerNumber: str
    history_sets: list[HistorySet]


class RecentSet(TypedDict):
    """A set two players played against each other"""

    id: int
    tournament: str
    event: str
    phase_id: str
    phase_name: str
    round: str
    score: list
    # 0 or 1
    winner: int
    online: bool
    timestamp: int
    p1_char: CharacterSlot
    p2_char: CharacterSlot


class RecentSets(TypedDict):
    """What GetRecentSets emits"""

    sets: list[RecentSet]
    # The request's requestTime, to drop answers to older requests
    request_time: int


# =====================================================
# STANDINGS
# =====================================================


class StandingPlayer(Player):
    seed: int
    # {game codename: [[character name], ...]}
    mains: dict
    # [[start.gg character id, games played], ...]
    startggMains: list


class Standing(TypedDict):
    wins: int
    losses: int
    winPercentage: str
    players: list[StandingPlayer]
