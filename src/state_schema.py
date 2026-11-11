"""The shape of the program state: what HyperDrive sends its clients (the
layouts, the web app, the Stream Deck plugin) in `program_state`, and writes
to out/program_state.json.

This is the one description of that contract. From it,
scripts/gen_state_types.py writes layout/include/state.d.ts (the types
layout/include/hd.d.ts and the other clients use), and
test/test_state_schema.py checks it against the sample state the previews
are rendered with (scripts/previews/sample_state.json) and against the keys
the application sets (the StateManager.Set / Unset calls in src/).

Nothing here is used at run time: StateManager doesn't validate what it is
given. No Qt, and nothing of the application, is imported.

How to read it:
- Every key is optional: the state fills up as the application starts and
  as tournaments, sets and players are loaded, and `null` stands for "none"
  in many places. A model says what a key holds when it is there.
- Every object is open: keys that aren't described are allowed. The
  application adds some from user data (see `Player.custom`), and layouts
  must not break on new ones.
- `Loose` marks what is free-form, or whose shape isn't pinned down here:
  typed as any JSON object rather than guessed at. `Any` is the same for a
  single value.
- Objects with numbered keys ("1", "2"...) are `dict[str, X]`: JSON has no
  number keys, and layouts index them with numbers all the same.

When a key is added to the state: add it here, run
`python scripts/gen_state_types.py`, and document it in docs/layout-data.md
if layouts are meant to use it.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LooseMarker:
    """Marks a type as free-form, for the generated types."""


# A JSON object that is free-form, or not described here
Loose = Annotated[dict[str, Any], LooseMarker]

# Ids come from the tournament providers: numbers (start.gg) or text (parry.gg)
Id = int | str


def F(description):
    """An optional key, with what it holds."""
    return Field(None, description=description)


class StateModel(BaseModel):
    """A JSON object of the state: every key optional, others allowed."""

    # strict: a number isn't text, a boolean isn't a number
    model_config = ConfigDict(extra="allow", strict=True)


# ---------------------------------------------------------------------------
# Shared pieces


class Point(StateModel):
    x: float | None = None
    y: float | None = None


class Asset(StateModel):
    """One image of a character or stage, from the game's asset pack."""

    asset: str | None = F("The file's path, from HyperDrive's folder")
    type: list[str] | None = F('What the image is: `["icon"]`, `["full"]`, `["portrait"]`...')
    image_size: Point | None = None
    average_size: Point | None = F("Average size of the pack's images of this type")
    eyesight: Point | None = F("Where the character's eyes are, to center on")
    rescaling_factor: Any | None = None
    uncropped_edge: list[str] | None = None
    metadata: Any | None = None


class Character(StateModel):
    """A character picked by a player (`character`), or one of their mains
    (`mains`). An empty slot has an empty `name`."""

    name: str | None = F("Name in the user's language")
    en_name: str | None = None
    display_name: str | None = None
    codename: str | None = None
    skin: Id | None = F("The skin's number (`-1` for a main without one)")
    variant: Loose | None = F("The variant picked, in games that have them")
    modded: bool | None = None
    assets: dict[str, Asset] | None = F(
        "The skin's images, by asset pack (`full`, `base_files/icon`...)"
    )


class Country(StateModel):
    name: str | None = None
    en_name: str | None = None
    display_name: str | None = None
    code: str | None = F("ISO 3166-1 alpha-2")
    asset: str | None = F("The flag's path")
    latitude: str | None = None
    longitude: str | None = None


class Region(StateModel):
    """A state or province."""

    name: str | None = None
    code: str | None = None
    original_code: str | None = None
    asset: str | None = F("The flag's path")
    latitude: str | None = None
    longitude: str | None = None


class Player(StateModel):
    """A person: a scoreboard player, a commentator, a player of a player
    list or of a team battle team. Which keys are there depends on where."""

    name: str | None = F("Tag, without the sponsor")
    team: str | None = F("Sponsor / team prefix")
    mergedName: str | None = F("Sponsor and tag: `HD | Azure`")
    mergedOnlyName: str | None = F("The tag alone")
    real_name: str | None = None
    pronoun: str | None = None
    twitter: str | None = F("Twitter handle (also `socials.twitter`)")
    socials: dict[str, str] | None = F(
        "Social media handles by platform: `{twitter, twitch, youtube...}`, without the ones they don't have"
    )
    country: Country | None = F("`{}` when not set")
    state: Region | None = F("`{}` when not set")
    city: str | None = None
    seed: int | None = None
    birthday: bool | None = None
    id: Any | None = F("The player's ids at the tournament provider, for stats lookups")
    character: dict[str, Character] | None = F("Characters picked, by number")
    mains: dict[str, Character] | None = F("Mains from the player database, by number")
    avatar: str | None = F("Path of the avatar in user_data/player_avatar/, or `null`")
    online_avatar: str | None = F("URL of the provider profile's avatar")
    sponsor_logo: str | None = F("Path of the sponsor's logo in user_data/sponsor_logo/")
    sponsor_logos: dict[str, str] | None = F("A logo per sponsor, when there are several")
    custom: Loose | None = F(
        "Files of the player's folder in user_data/custom_player_export/, by name. Free-form."
    )
    custom_textbox: str | None = F("Scoreboard: the player's free text box")
    wins: int | None = F("Scoreboard: wins in the event")
    losses: int | None = None
    winPercentage: float | None = None
    # Team battle
    dynamic_spinner: int | None = F(
        "Team battle: stocks left, or games won against the current opponent"
    )
    active: bool | None = F("Team battle: the one playing")
    dead: bool | None = F("Team battle: eliminated")
    status: Literal["playing", "out", "on_deck", "unused"] | None = F("Team battle")
    play_order: int | None = F("Team battle: place in the order the team's players came in")


class Stage(StateModel):
    name: str | None = F("Name in the user's language")
    en_name: str | None = None
    display_name: str | None = None
    codename: str | None = None
    path: str | None = F("The stage's image")
    locale: dict[str, str] | None = F("Names by language")
    smashgg_id: Id | None = None
    parrygg_slug: str | None = None


class Ruleset(StateModel):
    """A stage striking ruleset."""

    name: str | None = None
    videogame: str | None = None
    neutralStages: list[Any] | None = None
    counterpickStages: list[Any] | None = None
    banByMaxGames: dict[str, Any] | None = F("Bans by best of")
    banCount: int | None = None
    strikeOrder: list[int] | None = None
    useDSR: bool | None = None
    useMDSR: bool | None = None
    errors: list[Any] | None = None


# ---------------------------------------------------------------------------
# score


class Team(StateModel):
    """A side of a scoreboard. Team 1 is the left side: the players move
    when the teams are swapped."""

    teamName: str | None = F("The team's name (doubles and up), may be empty")
    mergedTeamName: str | None = None
    score: int | None = None
    losers: bool | None = F("In the losers side of a grand final")
    losersIndicator: str | None = F('`"[L]"` or `""`')
    color: str | None = F("`#rrggbb`")
    logo: str | None = F("Path of the team's logo in user_data/team_logo/, or `null`")
    player: dict[str, Player] | None = F("The players, by number")


class Game(StateModel):
    """A game of the set on a scoreboard (`score.N.games`)."""

    game: int | None = F("Game number")
    winner: int | None = F("`1` or `2` for the team that won, `0` for a draw, `null` if not played")
    stage: str | None = F("The stage's codename")
    stageData: Stage | None = None
    characters: dict[str, list[str | None]] | None = F("Character names by team, by player")
    characterData: dict[str, list[Character | None]] | None = F(
        "The same characters with their data, default skin"
    )
    scoreAfter: dict[str, int] | None = F("The set's score once this game was played, by team")
    current: bool | None = F("The game being played")


class Report(StateModel):
    """Reporting the scoreboard's set to the provider."""

    setId: Id | None = None
    status: (
        Literal["idle", "pending", "sending", "synced", "reported", "retrying", "error"] | None
    ) = None
    message: str | None = None
    liveUpdates: bool | None = None


class CharacterSelect(StateModel):
    active: bool | None = None
    game: int | None = None
    submitted: dict[str, bool] | None = F("By team")


class CharacterLock(StateModel):
    score: list[int] | None = F("`[team 1, team 2]`: the score the picks are for")
    locked: dict[str, bool] | None = F("By team")


class StageStrike(StateModel):
    """Stage striking of the set on a scoreboard (see src/StageStrikeLogic.py)."""

    currGame: int | None = None
    currPlayer: int | None = None
    currStep: int | None = None
    strikedStages: list[list[str]] | None = F("Codenames striked, by step")
    strikedBy: list[list[str]] | None = F("Codenames striked, by team")
    stagesWon: list[list[str]] | None = F("By team")
    stagesPicked: list[str] | None = None
    selectedStage: str | None = F("Codename")
    selectedStageData: Stage | None = None
    lastWinner: int | None = None
    gentlemans: bool | None = None
    characterSelect: CharacterSelect | None = None
    characterLock: CharacterLock | None = None
    pendingWinner: Any | None = None
    lastActor: Any | None = F("Team whose page may undo, `null` for HyperDrive or both")
    nextActor: Any | None = None
    canUndo: bool | None = None
    canRedo: bool | None = None


class LastSet(StateModel):
    """A set a team played before in the event (`score.N.last_sets.T`).
    The keys are spelled this way."""

    phase_id: Id | None = None
    phase_name: str | None = None
    round_name: str | None = None
    player_name: str | None = None
    player_team: str | None = None
    player_score: int | None = None
    player_seed: int | None = None
    player_char: Loose | None = None
    oponent_name: str | None = None
    oponent_team: str | None = None
    oponent_score: int | None = None
    oponent_seed: int | None = None
    oponent_char: Loose | None = None


class HistorySet(StateModel):
    """A past tournament of a player (`score.N.history_sets.T`)."""

    tournament_name: str | None = None
    tournament_picture: str | None = None
    event_name: str | None = None
    event_date_day: str | None = None
    event_date_month: str | None = None
    event_date_year: str | None = None
    placement: int | None = None
    entrants: int | None = None
    seed: int | None = None
    spr: int | None = None
    bracket_type: str | None = None


class RecentSet(StateModel):
    id: Id | None = None
    tournament: str | None = None
    event: str | None = None
    phase_id: Id | None = None
    phase_name: str | None = None
    round: str | None = None
    score: list[int] | None = F("`[team 1, team 2]`")
    winner: int | None = F("`0` or `1`")
    online: bool | None = None
    timestamp: int | None = None


class RecentSets(StateModel):
    """Sets the scoreboard's two players played against each other."""

    state: str | None = F("`loading` or `done`")
    sets: list[RecentSet] | None = None
    request_time: float | None = None


class Scoreboard(StateModel):
    """One scoreboard: `score.1`, `score.2`..."""

    team: dict[str, Team] | None = F('`{"1": left side, "2": right side}`')
    teamsSwapped: bool | None = None
    phase: str | None = None
    match: str | None = F("The round's name")
    round: Any | None = None
    best_of: int | None = F("`0` when not set")
    best_of_text: str | None = None
    best_of_short_text: str | None = None
    first_to: int | None = None
    first_to_text: str | None = None
    first_to_short_text: str | None = None
    top_n: Any | None = None
    phase_size: Any | None = None
    num_groups: Any | None = None
    upset_factor: int | None = None
    set_id: Id | None = F("The provider's id of the set loaded")
    station: Any | None = F("The station tracked, with auto update")
    auto_update: str | None = F("`set`, `stream`, `station` or `null`")
    station_queue: Loose | None = F("Sets of the station tracked, as the provider gives them")
    games: dict[str, Game] | None = F("The set's games, by number")
    report: Report | None = None
    ruleset: Ruleset | None = None
    stage_strike: StageStrike | None = None
    last_sets: dict[str, dict[str, LastSet]] | None = F(
        "By team, then by number, most recent first"
    )
    history_sets: dict[str, dict[str, HistorySet]] | None = F("By team, then by number")
    recent_sets: RecentSets | None = None


class Score(StateModel):
    """The scoreboards by number, and a few keys of the first one's own."""

    # The numbered keys
    __pydantic_extra__: dict[str, Scoreboard]

    ruleset: Ruleset | None = F("The ruleset picked in the Ruleset tab")
    bracket_type: str | None = None
    upset_factor: int | None = None


# ---------------------------------------------------------------------------
# tournamentInfo, game


class TournamentInfo(StateModel):
    tournamentName: str | None = None
    eventName: str | None = None
    tagline: str | None = F("Text the user typed, not from the tournament")
    startAt: int | str | None = F(
        'The tournament\'s start, seconds since the epoch (`""` when not known)'
    )
    endAt: int | str | None = None
    eventStartAt: int | str | None = F("The event's own")
    eventEndAt: int | str | None = None
    timezone: str | None = F('e.g. `"America/New_York"`, `""` when not known')
    numEntrants: int | None = F("In the event")
    numAttendees: int | None = F("At the tournament, in every event")
    locationType: str | None = F('`"offline"`, `"online"`, `"hybrid"` or `""`')
    address: str | None = None
    cityState: str | None = F('City and state together: `"Springfield, IL"`')
    city: str | None = None
    state: str | None = None
    shortLink: str | None = None
    hashtag: str | None = F("Without its #")
    discord: str | None = None
    logo: str | None = F('URL of the tournament\'s square logo, `""` without one')
    banner: str | None = F("URL of its wide banner")
    initial_load: bool | None = None


class GameInfo(StateModel):
    """The game picked."""

    name: str | None = None
    codename: str | None = F("The asset pack's folder in user_data/games/")
    logo: str | None = None
    smashgg_id: Id | None = None
    igdb_id: Id | None = None
    challonge_game_id: Id | None = None
    parrygg_slug: str | None = None
    has_stages: bool | None = None
    has_variants: bool | None = None
    has_colors: bool | None = None
    has_modded_content: bool | None = None
    mods_active: bool | None = None
    stages: dict[str, Stage] | None = F("The game's stages, by codename")
    defaults: Loose | None = F(
        "The pack's defaults: `{players_per_team, characters_per_player...}`"
    )


class ProviderVideogame(StateModel):
    id: Id | None = F("The provider's id of the event's game")


# ---------------------------------------------------------------------------
# bracket


class BracketColumn(StateModel):
    key: str | None = F("`winners:2`...")
    name: str | None = None
    sets: list[str] | None = F("Set ids, top to bottom")


class BracketSetPlayer(StateModel):
    id: Id | None = F("The player's slot in the player list")
    seed: int | None = None
    name: str | None = None
    bye: bool | None = None
    pending: bool | None = None
    source: str | None = F('What a pending slot waits for: "Winner of C"')
    manual: bool | None = F("Put there by hand")


class BracketNext(StateModel):
    set: str | None = None
    slot: int | None = None


class BracketSet(StateModel):
    id: str | None = None
    identifier: str | None = F("Its letter: A, B...")
    side: str | None = F("`winners`, `losers`, `grand_final`, `third_place` or `pool`")
    column: int | None = None
    row: int | None = None
    roundName: str | None = None
    players: list[BracketSetPlayer] | None = F("Its two slots")
    score: list[int] | None = F("`[a, b]`; `-1` is a DQ")
    completed: bool | None = None
    winner: int | str | None = F('`0` or `1` for the slot that won, `"draw"`, or `null`')
    nextWin: BracketNext | None = None
    nextLose: BracketNext | None = None
    loserPlacement: int | None = None
    isGrandFinal: bool | None = None
    isReset: bool | None = None
    resetNeeded: bool | None = None
    startggId: Id | None = None


class BracketResult(StateModel):
    order: int | None = None
    id: Id | None = None
    name: str | None = None


class Bracket(StateModel):
    """A phase's bracket, as a channel shows it."""

    type: str | None = F("`DOUBLE_ELIMINATION`, `SINGLE_ELIMINATION`, `ROUND_ROBIN` or `SWISS`")
    name: str | None = None
    fromStartgg: bool | None = None
    progressionsOut: int | None = None
    limitExportNumber: int | None = F("Top N when only the top is shown")
    sides: dict[str, list[BracketColumn]] | None = F("The columns, by side")
    sets: dict[str, BracketSet] | None = F("Every set shown, by id")
    results: list[BracketResult] | None = F("Elimination: players by finishing order")
    standings: list[Loose] | None = F(
        "Round robin and swiss: `[{rank, playerId, name, played, wins, draws, losses, points...}]`"
    )
    totalRounds: int | None = None
    byes: dict[str, list[Loose]] | None = F("Players sitting out, by round key")


class PlayerListSlot(StateModel):
    name: str | None = F("The team's name")
    player: dict[str, Player] | None = None
    score: Any | None = None
    wins: Any | None = None
    loses: Any | None = None
    winPercentage: Any | None = None


class PlayerList(StateModel):
    slot: dict[str, PlayerListSlot] | None = F("By slot number")


class BracketChannel(StateModel):
    bracket: Bracket | None = None
    phase: str | None = None
    phaseGroup: str | None = None
    phaseId: str | None = None
    playersPath: str | None = F("Where its player list is in the state")


class BracketFocus(StateModel):
    """What the bracket focus layout zooms to, for a channel."""

    mode: str | None = F("`all`, `sets`, `rounds`, `side`, `player`, `follow` or `tour`")
    sets: list[str] | None = F("Ids of the sets in focus. Empty: the whole bracket")
    rounds: list[str] | None = F("Keys of the rounds in focus")
    label: str | None = None
    side: str | None = None
    player: Id | None = None
    scoreboard: int | None = None
    interval: float | None = None
    step: int | None = None
    steps: int | None = None
    phase: str | None = F("Id of the phase the channel shows")


class BracketPhase(StateModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    source: str | None = F("`local` or `startgg`")
    phaseGroupId: Id | None = None
    channels: list[str] | None = None
    current: bool | None = F("The main channel shows it")


class BracketSection(StateModel):
    bracket: Bracket | None = F("The main channel's bracket")
    players: PlayerList | None = F("The main channel's player list")
    phase: str | None = None
    phaseGroup: str | None = None
    channels: dict[str, BracketChannel] | None = F("By channel name; `main` is always there")
    rosters: dict[str, PlayerList] | None = F(
        "The player lists: `local`, and one per phase group loaded"
    )
    focus: dict[str, BracketFocus] | None = F("By channel name")
    phases: list[BracketPhase] | None = None


# ---------------------------------------------------------------------------
# stream_queue, completed_sets


class QueueTeam(StateModel):
    teamName: str | None = None
    losers: bool | None = None
    seed: int | None = None
    player: dict[str, Player] | None = None


class QueueSet(StateModel):
    """A set of a stream's queue: the provider's set data, and its place."""

    id: Id | None = None
    queueKey: str | None = None
    source: str | None = F("`startgg`, `added` or `custom`")
    position: int | None = F("1 for the next set")
    onStream: bool | None = None
    event: str | None = None
    isCurrentEvent: bool | None = None
    phase: str | None = None
    match: str | None = None
    best_of: int | None = None
    best_of_text: str | None = None
    state: int | None = None
    station: Id | None = None
    eta: float | None = F("When it should start, seconds since the epoch")
    eta_minutes: float | None = None
    started_at: float | None = None
    team: dict[str, QueueTeam] | None = None


class Stream(StateModel):
    name: str | None = None
    manual: bool | None = None
    scoreboard: int | None = F("The scoreboard showing the stream's sets, or `null`")
    sets: list[QueueSet] | None = None


class StreamQueue(StateModel):
    streams: list[Stream] | None = F("Every stream, in the widget's order")
    byName: dict[str, list[QueueSet]] | None = F("The same sets, by stream name")
    lastUpdated: float | None = None
    currentStream: str | None = None
    average_set_minutes: float | None = None


class CompletedSetPlayer(StateModel):
    gamertag: str | None = None
    sponsor: str | None = None
    country: Country | None = None
    state: Region | None = None
    characters: dict[str, Character] | None = None


class CompletedSet(StateModel):
    phase_name: str | None = None
    phase_id: Id | None = None
    round_name: str | None = None
    bracket_type: str | None = None
    upset_factor: int | None = None
    winner_score: int | None = F("`-1` is a DQ")
    winner_seed: int | None = None
    winner_team: dict[str, CompletedSetPlayer] | None = None
    winner_team_name: str | None = None
    loser_score: int | None = None
    loser_seed: int | None = None
    loser_team: dict[str, CompletedSetPlayer] | None = None
    loser_team_name: str | None = None


# ---------------------------------------------------------------------------
# team_battle


class BattleTeam(StateModel):
    sponsor: str | None = F("The team's name")
    short_name: str | None = None
    color: str | None = None
    logo: str | None = None
    sponsor_logo: str | None = None
    active_player: int | None = F("Number of the player playing")
    plays_left: int | None = None
    player: dict[str, Player] | None = None


class TeamBattle(StateModel):
    """The Crew/Team Battle window."""

    battle_mode: Literal["STOCK_POOL", "FIRST_TO"] | None = None
    limited: bool | None = F("A Limited Plays mode")
    battle_value: int | None = F("Stocks per player (Stock Pool), or games to win (First To)")
    plays: int | None = None
    phase: str | None = None
    match: str | None = None
    team: dict[str, BattleTeam] | None = None
    team1_spinner_total: int | None = Field(None, alias="team1_spinner-total")
    team2_spinner_total: int | None = Field(None, alias="team2_spinner-total")
    team1_total_score: int | None = Field(None, alias="team1_total-score")
    team2_total_score: int | None = Field(None, alias="team2_total-score")


# ---------------------------------------------------------------------------
# layout_theme, display


class LayoutTheme(StateModel):
    """The theme picked in Layout themes. globals.js applies it."""

    name: str | None = None
    values: dict[str, dict[str, Any]] | None = F(
        "Every field, by section (see LayoutThemeSchema() in src/LayoutOptions/LayoutThemes.py)"
    )
    css: dict[str, str] | None = F("The values as CSS custom properties")
    stylesheet: str | None = F("The same as a `:root { ... }` stylesheet")


class Display(StateModel):
    """What Display Controls has turned on and off."""

    folders: dict[str, bool] | None = F("By layout folder")
    groups: dict[str, bool] | None = F("By `?display=` group, lowercase")


# ---------------------------------------------------------------------------
# The state


class State(StateModel):
    """The program state."""

    score: Score | None = F("The scoreboards")
    tournamentInfo: TournamentInfo | None = None
    game: GameInfo | None = None
    provider_videogame: ProviderVideogame | None = None
    commentary: dict[str, Player] | None = F("The commentators, by number")
    bracket: BracketSection | None = None
    player_list: PlayerList | None = None
    stream_queue: StreamQueue | None = None
    completed_sets: dict[str, CompletedSet] | None = F(
        "The event's last completed sets, most recent first"
    )
    team_battle: TeamBattle | None = None
    layout_theme: LayoutTheme | None = None
    display: Display | None = None
    timestamp: float | None = F(
        "In out/program_state.json only: when it was written. Not sent over the socket"
    )


# The top-level keys, in order
SECTIONS = tuple(State.model_fields)
