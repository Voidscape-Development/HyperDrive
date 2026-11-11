"""The web server's actions, declared once.

Each Action below names a method of WebServerActions, the parameters it
takes, the thread it runs on, and how clients reach it: its HTTP routes and
its socket.io event. WebServer makes the routes and the event handlers from
this table, so both read the same parameters and call the same method
through run_action, which every action a client asks for passes through.

Parameters are read by name from where the request has them: the path, the
query string, or the JSON body (which for a socket.io event is its message).
"""

import html
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

import orjson

from .WebServerActions import ActionError, run_on_gui_thread


# =====================================================
# WHERE PARAMETERS COME FROM
# =====================================================
class Source(NamedTuple):
    """A request's parameters. A socket.io message only has a body."""

    path: Mapping
    query: Mapping
    body: Mapping


def parse_message(message):
    """A JSON body or socket message as a dict ({} when it isn't one).
    Socket messages are JSON strings, or already decoded by the client."""
    if isinstance(message, (str, bytes)):
        try:
            message = orjson.loads(message) if message else {}
        except orjson.JSONDecodeError:
            return {}
    return message if isinstance(message, dict) else {}


def socket_source(message):
    return Source({}, {}, parse_message(message))


# =====================================================
# PARAMETER TYPES
# =====================================================
# Each turns what the client sent into the value the action gets, or raises
# ActionError. They get the WebServerActions too, which knows the scoreboards.
def Scoreboard(actions, value):
    """The number of an existing scoreboard (404 otherwise), as an int."""
    return actions.scoreboard_number(1 if value == "" else value)


def Team(actions, value):
    if str(value) not in ("1", "2"):
        raise ActionError("team must be 1 or 2")
    return int(value)


def WholeNumber(actions, value):
    if isinstance(value, str):
        value = value.strip()
    if isinstance(value, (bool, float)) or not isinstance(value, (int, str)):
        raise ActionError(f"{value} is not a whole number")
    try:
        return int(value)
    except ValueError:
        raise ActionError(f"{value} is not a whole number")


def Flag(actions, value):
    """True when the parameter is there, whatever its value (?no-mains),
    other than false in JSON."""
    return value is not False


def Bool(actions, value):
    return value if isinstance(value, bool) else str(value).lower() != "false"


def HexColor(actions, value):
    """A color sent without its "#"."""
    return "#" + str(value)


def Tag(actions, value):
    return html.unescape(str(value))


# =====================================================
# PARAMETERS
# =====================================================
@dataclass(frozen=True)
class Param:
    name: str
    # The placeholder in the HTTP path
    path: str | None = None
    # Keys in the query string
    query: tuple[str, ...] = ()
    # Keys in the JSON body or socket message
    body: tuple[str, ...] = ()
    # The whole JSON body or socket message instead of one of its keys
    whole: bool = False
    # One of the types above
    parse: Callable[[Any, Any], Any] | None = None
    default: Any = None
    required: bool = False

    def read(self, actions, source: Source):
        value = self._find(source)
        if value is None:
            value = self.default
        if value is None:
            if self.required:
                raise ActionError(f"{self.name} not specified")
            return None
        return self.parse(actions, value) if self.parse else value

    def _find(self, source: Source):
        if self.whole:
            return source.body
        places = (
            (source.path, (self.path,) if self.path else ()),
            (source.query, self.query),
            (source.body, self.body),
        )
        for values, keys in places:
            for key in keys:
                if values.get(key) is not None:
                    return values.get(key)
        return None


def InPath(name, **options):
    """A parameter in the path, and under the same name in a JSON body /
    socket message."""
    return Param(name, path=name, body=(name,), **options)


def InQuery(name, *aliases, **options):
    """A parameter in the query string, or the JSON body / socket message."""
    return Param(name, query=(name, *aliases), body=(name, *aliases), **options)


def InBody(name, **options):
    """A key of the JSON body / socket message."""
    return Param(name, body=(name,), **options)


BODY = Param("body", whole=True)

# /scoreboard<N>-..., or "scoreboardNumber" in a socket message (1 without)
SCOREBOARD = Param(
    "scoreboard", path="scoreboardNumber", body=("scoreboardNumber",), parse=Scoreboard, default=1
)
TEAM = InPath("team", parse=Team, required=True)
PLAYER = InPath("player", parse=WholeNumber, required=True)

# Stage striking is per scoreboard. HTTP requests pick it with
# ?scoreboard=<n> or a "scoreboardNumber" field in their JSON body, and
# socket messages with a "scoreboardNumber" field. Both default to 1.
STRIKE_SCOREBOARD = Param(
    "scoreboard", query=("scoreboard",), body=("scoreboardNumber",), parse=Scoreboard, default=1
)
# Pages for one team (?team=<1|2>) may only strike on their turn, undo
# their own actions, and need the other team to confirm a game's winner
STRIKE_TEAM = InQuery("team")

# /update-commentary-<caster>, or "commentator" in a socket message
COMMENTATOR = Param(
    "commentator", path="caster", body=("commentator",), parse=WholeNumber, required=True
)
NO_MAINS = InQuery("no-mains", parse=Flag, default=False)


# =====================================================
# ACTIONS
# =====================================================
class Route(NamedTuple):
    path: str
    methods: tuple[str, ...]


def GET(path):
    return Route(path, ("GET",))


def POST(path):
    return Route(path, ("POST",))


def LINK(path):
    """An action that works as a plain link (GET), e.g. for a Stream Deck's
    "open a website" button, and takes POST too."""
    return Route(path, ("GET", "POST"))


@dataclass(frozen=True)
class Action:
    # The method of WebServerActions it calls with the params, in order
    name: str
    params: tuple[Param, ...] = ()
    # Whether it runs on the GUI thread (it uses widgets), or in the
    # request's worker thread (it may take a while, e.g. it uses the network)
    gui: bool = False
    http: tuple[Route, ...] = ()
    # The socket.io event that runs it
    socket: str | None = None
    # The events it's answered with: the same one, unless given
    replies: tuple[str, ...] | None = None
    doc: str = ""

    def __post_init__(self):
        if self.replies is None:
            object.__setattr__(self, "replies", (self.socket,) if self.socket else ())


def run_action(actions, action: Action, source: Source):
    """Runs an action for a client and returns what it returned. Raises
    ActionError (with the HTTP status that tells why) when a parameter isn't
    valid, before anything is changed, or when the GUI thread is too busy."""
    args = [param.read(actions, source) for param in action.params]
    method = getattr(actions, action.name)
    if action.gui:
        return run_on_gui_thread(lambda: method(*args))
    return method(*args)


# The routes are matched in this order
ACTIONS: tuple[Action, ...] = (
    # =====================================================
    # STAGE STRIKING
    # =====================================================
    Action(
        "ruleset",
        # Not checked: the page may still ask for a scoreboard that was
        # removed, and gets scoreboard 1's. The event carries the scoreboard
        # it is for in "scoreboard"
        (Param("scoreboard", query=("scoreboard",), body=("scoreboardNumber",), default=1),),
        gui=True,
        http=(GET("/ruleset"),),
        socket="ruleset",
        doc="The stage strike page's data: ruleset, teams, score and strikes",
    ),
    Action(
        "stage_clicked",
        (BODY, STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_stage_clicked"),),
        socket="stage_strike_stage_clicked",
    ),
    Action(
        "confirm_clicked",
        (STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_confirm_clicked"),),
        socket="stage_strike_confirm_clicked",
    ),
    Action(
        "report_characters",
        (BODY, STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_report_characters"),),
        socket="stage_strike_report_characters",
        doc="Characters picked for the next game: "
        '{"characters": {team: {player: [[character, skin], ...]}}}',
    ),
    Action(
        "character_select_report",
        (BODY, STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/character_select_report"),),
        doc="The character select page's picks: like stage_strike_report_characters, "
        "but each team picks once per score (409 ALREADY_PICKED until the score changes)",
    ),
    Action(
        "rps_win",
        (InBody("winner"), STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_rps_win"),),
        socket="stage_strike_rps_win",
    ),
    Action(
        "match_win",
        (InBody("winner"), STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_match_win"),),
        socket="stage_strike_match_win",
    ),
    Action(
        "set_gentlemans",
        (InBody("value"), STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_set_gentlemans"),),
        socket="stage_strike_set_gentlemans",
    ),
    Action(
        "stage_strike_undo",
        (STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_undo"),),
        socket="stage_strike_undo",
    ),
    Action(
        "stage_strike_redo",
        (STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_redo"),),
        socket="stage_strike_redo",
    ),
    Action(
        "reset",
        (STRIKE_SCOREBOARD, STRIKE_TEAM),
        gui=True,
        http=(POST("/stage_strike_reset"),),
        socket="stage_strike_reset",
    ),
    # =====================================================
    # SCOREBOARD SCORE AND TEAMS
    # =====================================================
    Action(
        "post_score",
        (InBody("scoreboard", parse=Scoreboard, default=1), BODY),
        gui=True,
        http=(POST("/score"),),
        socket="score",
        doc='Sets the score, e.g. {"scoreboard": 1, "team1score": 2, "team2score": 0}',
    ),
    Action(
        "team_scoreup",
        (SCOREBOARD, TEAM),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-team{team:seg}-scoreup"),),
        socket="team_scoreup",
        doc="Ticks score of Team specified up by 1 point",
    ),
    Action(
        "team_scoredown",
        (SCOREBOARD, TEAM),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-team{team:seg}-scoredown"),),
        socket="team_scoredown",
        doc="Ticks score of Team specified down by 1 point",
    ),
    Action(
        "team_color",
        (SCOREBOARD, TEAM, InPath("color", parse=HexColor, required=True)),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-team{team:seg}-color-{color:seg}"),),
        socket="team_color",
        doc="Set color of team, as hex without the #",
    ),
    Action(
        "team_info",
        (SCOREBOARD, TEAM, BODY),
        gui=True,
        http=(POST("/scoreboard{scoreboardNumber:seg}-team{team:seg}-info"),),
        socket="team_info",
        doc="Sets a team's name, losers state and/or color. "
        'Ex. POST /scoreboard1-team2-info {"name": "Team B", "losers": true, "color": "#2e89ff"}',
    ),
    # =====================================================
    # CREW/TEAM BATTLE
    # =====================================================
    Action(
        "team_battle_scoreup",
        (InPath("team"),),
        gui=True,
        http=(LINK("/team-battle-team{team:seg}-scoreup"),),
        socket="team_battle_scoreup",
        doc="A team scores: in Stock Pool the other team's active player loses a stock, "
        "in First To the team's active player wins a game",
    ),
    Action(
        "team_battle_scoredown",
        (InPath("team"),),
        gui=True,
        http=(LINK("/team-battle-team{team:seg}-scoredown"),),
        socket="team_battle_scoredown",
        doc="Undoes a team's last point",
    ),
    Action(
        "team_battle_next_player",
        (InPath("team"),),
        gui=True,
        http=(LINK("/team-battle-team{team:seg}-next-player"),),
        socket="team_battle_next_player",
        doc="Makes the team's next player in line who isn't eliminated active",
    ),
    Action(
        "team_battle_set_active",
        (InPath("team"), InPath("player")),
        gui=True,
        http=(LINK("/team-battle-team{team:seg}-player{player:seg}-active"),),
        socket="team_battle_set_active",
        doc="Makes a player active, by their number in the team (from 1)",
    ),
    Action(
        "team_battle_reset_stocks",
        gui=True,
        http=(LINK("/team-battle-reset-stocks"),),
        socket="team_battle_reset_stocks",
        doc="Resets every player's stocks/games",
    ),
    Action(
        "team_battle_reset",
        gui=True,
        http=(LINK("/team-battle-reset"),),
        socket="team_battle_reset",
        doc="Clears the players and starts the battle over",
    ),
    Action("get_team_battle", http=(GET("/team-battle-get"),)),
    # =====================================================
    # SCOREBOARD DATA
    # =====================================================
    Action("get_scoreboard", (SCOREBOARD,), http=(GET("/scoreboard{scoreboardNumber:seg}-get"),)),
    Action(
        "set_route",
        (
            SCOREBOARD,
            InQuery("best-of", "best_of", parse=WholeNumber),
            InQuery("phase"),
            InQuery("match"),
            InQuery("players", parse=WholeNumber),
            InQuery("characters", parse=WholeNumber),
            InQuery("losers", parse=Bool),
            InQuery("team"),
        ),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-set"),),
        socket="set",
        doc="Sets any of the set's information. "
        "Ex. /scoreboard1-set?best-of=5&phase=Top 32&match=Winners Finals, "
        "or losers=<true/false>&team=<team>",
    ),
    Action(
        "set_team_data",
        (SCOREBOARD, TEAM, PLAYER, BODY),
        http=(POST("/scoreboard{scoreboardNumber:seg}-update-team-{team:seg}-{player:seg}"),),
        socket="update_team",
        doc="Set player data",
    ),
    Action(
        "set_commentary_data",
        (COMMENTATOR, BODY),
        http=(POST("/update-commentary-{caster}"),),
        socket="update_commentary",
    ),
    Action(
        "set_game",
        (BODY,),
        http=(POST("/update-game"),),
        socket="update_game",
        doc='Set game: {"codename": <game>, "mods_active": <bool>}',
    ),
    # =====================================================
    # GAMES AND CHARACTERS
    # =====================================================
    Action("get_games", http=(GET("/games"),), socket="games", doc="Get games"),
    Action(
        "get_current_game",
        http=(GET("/current-game"),),
        socket="current_game",
        # It used to be answered with get_current_game only
        replies=("current_game", "get_current_game"),
        doc="Get current game",
    ),
    Action(
        "get_match_names",
        http=(GET("/match-names"),),
        socket="match_names",
        doc="Get match and phase names",
    ),
    Action(
        "get_characters",
        gui=True,
        http=(GET("/characters"),),
        socket="characters",
        doc="Get characters",
    ),
    Action(
        "get_variants", gui=True, http=(GET("/variants"),), socket="variants", doc="Get variants"
    ),
    # =====================================================
    # SWAPPING AND LOADING SETS
    # =====================================================
    Action(
        "swap_teams",
        (SCOREBOARD,),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-swap-teams"),),
        socket="swap_teams",
        doc="Swaps teams",
    ),
    Action(
        "get_swap",
        (SCOREBOARD,),
        http=(GET("/scoreboard{scoreboardNumber:seg}-get-swap"),),
        socket="get_swap",
        doc="Are the teams currently swapped?",
    ),
    Action(
        "open_sets",
        (SCOREBOARD,),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-open-set"),),
        socket="open_set",
        doc="Opens Set Selector Window",
    ),
    Action(
        "pull_stream_set",
        (SCOREBOARD,),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-pull-stream"),),
        socket="pull_stream",
        doc="Pulls Current Stream Set",
    ),
    # =====================================================
    # PLAYER STATS
    # =====================================================
    Action(
        "stats_recent_sets",
        (SCOREBOARD,),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-stats-recent-sets"),),
        socket="stats_recent_sets",
        doc="Resubmits Call for Recent Sets",
    ),
    Action(
        "stats_upset_factor",
        (SCOREBOARD,),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-stats-upset-factor"),),
        socket="stats_upset_factor",
        doc="Resubmits Call for Upset Factor",
    ),
    Action(
        "stats_last_sets",
        (SCOREBOARD, InPath("player")),
        http=(LINK("/scoreboard{scoreboardNumber:seg}-stats-last-sets-{player}"),),
        socket="stats_last_sets",
        doc="Resubmits Call for Last Sets (player: 1, 2 or both)",
    ),
    Action(
        "stats_history_sets",
        (SCOREBOARD, InPath("player")),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-stats-history-sets-{player}"),),
        socket="stats_history_sets",
        doc="Resubmits Call for History Sets (player: 1, 2 or both)",
    ),
    Action(
        "stats_refresh",
        (SCOREBOARD,),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-stats-refresh"),),
        doc="Gets all of the scoreboard's player stats again",
    ),
    Action(
        "commentary_preview",
        (BODY,),
        http=(POST("/commentary-preview"),),
        doc="The players of a set that isn't on a scoreboard, for the commentary "
        'dashboard: {"teams": [[player...], [player...]]}',
    ),
    # =====================================================
    # RESETTING
    # =====================================================
    Action(
        "reset_scores",
        (SCOREBOARD,),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-reset-scores"),),
        socket="reset_scores",
        doc="Resets scores",
    ),
    Action(
        "reset_match",
        (SCOREBOARD,),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-reset-match"),),
        socket="reset_match",
        doc="Resets scores, match, phase, and losers status",
    ),
    Action(
        "reset_players",
        (SCOREBOARD,),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-reset-players"),),
        socket="reset_players",
        doc="Resets the players",
    ),
    Action(
        "clear_all",
        (SCOREBOARD,),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-clear-all"),),
        socket="clear_all",
        doc="Resets all values",
    ),
    # =====================================================
    # SETS AND COMMENTATORS
    # =====================================================
    Action(
        "get_sets",
        (InQuery("getFinished", parse=Flag, default=False),),
        http=(GET("/get-sets"),),
        socket="get_sets",
        doc="Get the sets to be played, or the finished ones with getFinished",
    ),
    Action(
        "get_match",
        (InPath("setId", parse=WholeNumber, required=True),),
        http=(GET("/get-match-{setId}"),),
        socket="get_match",
        doc="Loads info on a match",
    ),
    Action("get_comms", http=(GET("/get-comms"),), socket="get_comms", doc="Get the commentators"),
    Action(
        "load_set",
        (SCOREBOARD, InQuery("set"), NO_MAINS),
        gui=True,
        http=(LINK("/scoreboard{scoreboardNumber:seg}-load-set"),),
        socket="load_set",
        doc="Loads a set remotely by providing a set ID to pull from the data provider",
    ),
    Action(
        "get_set",
        (SCOREBOARD,),
        http=(GET("/scoreboard{scoreboardNumber:seg}-get-set"),),
        socket="get_set",
        doc="The ID of the set loaded in the scoreboard",
    ),
    # =====================================================
    # PLAYER DATABASE
    # =====================================================
    Action("get_playerdb", http=(GET("/playerdb"),), socket="playerdb"),
    # =====================================================
    # BRACKET
    # =====================================================
    Action(
        "update_bracket",
        http=(LINK("/update-bracket"),),
        socket="update_bracket",
        doc="Update bracket",
    ),
    Action(
        "update_bracket_sets",
        gui=True,
        http=(LINK("/update-bracket-sets"),),
        socket="update_bracket_sets",
        doc="Update only the set results of the loaded bracket, keeping its players",
    ),
    # =====================================================
    # STREAM QUEUE
    # =====================================================
    Action(
        "stream_queue",
        gui=True,
        http=(GET("/stream-queue"),),
        doc="The stream queues, as sent to the layouts",
    ),
    Action("stream_queue_refresh", gui=True, http=(LINK("/stream-queue/refresh"),)),
    Action(
        "stream_queue_load_next",
        (InQuery("stream"), InQuery("scoreboard")),
        gui=True,
        http=(LINK("/stream-queue/load-next"),),
        doc="Loads a stream's next set into its scoreboard: "
        "/stream-queue/load-next?stream=<name> or ?scoreboard=<number>",
    ),
    # =====================================================
    # BRACKET FOCUS
    # =====================================================
    # What the bracket focus layout zooms to (see docs/layout-data.md), for
    # a focus channel with ?channel=<name> ("main" without)
    Action(
        "bracket_focus",
        (InQuery("channel"),),
        gui=True,
        http=(GET("/bracket-focus"),),
        socket="bracket_focus",
        doc="What's in focus and what can be picked",
    ),
    Action(
        "bracket_focus_set",
        # A socket message has its channel in the request itself
        (BODY, Param("channel", query=("channel",))),
        gui=True,
        http=(POST("/bracket-focus"),),
        socket="bracket_focus_set",
        replies=("bracket_focus",),
        doc='A focus request, e.g. {"mode": "sets", "sets": ["m1"]}, '
        'or {"move": 1} for the next round',
    ),
    # =====================================================
    # DISPLAY CONTROLS
    # =====================================================
    # Display Controls, as links for a Stream Deck, with show, hide or
    # toggle as the action (or none, to get whether it's shown)
    Action(
        "display_state",
        gui=True,
        http=(GET("/display/state"),),
        socket="display_state",
        doc="Everything that's shown or hidden",
    ),
    Action("display_all", (InPath("action"),), gui=True, http=(LINK("/display/all/{action}"),)),
    Action(
        "display",
        (InPath("kind"), InPath("name"), InPath("action")),
        gui=True,
        http=(GET("/display/{kind}/{name}"), LINK("/display/{kind}/{name}/{action}")),
        doc="A folder's or a group's layouts: /display/folder/<folder>/<action> "
        "and /display/group/<group>/<action>",
    ),
    Action(
        "display_register",
        (InBody("groups"),),
        gui=True,
        socket="display_register",
        replies=(),
        doc="Layouts send the groups in their ?display= so they're listed",
    ),
    # =====================================================
    # LOADING PLAYERS FROM TAGS
    # =====================================================
    Action(
        "load_player_from_tag",
        (SCOREBOARD, InQuery("tag", parse=Tag), TEAM, PLAYER, NO_MAINS),
        gui=True,
        http=(
            LINK("/scoreboard{scoreboardNumber:seg}-load-player-from-tag-{team:seg}-{player:seg}"),
        ),
        socket="load_player_from_tag",
        doc="Load player from tag",
    ),
    Action(
        "load_commentator_from_tag",
        (COMMENTATOR, InQuery("tag", parse=Tag), NO_MAINS),
        http=(LINK("/load-commentator-from-tag-{caster}"),),
        socket="load_commentator_from_tag",
    ),
    # =====================================================
    # TOURNAMENT
    # =====================================================
    Action(
        "load_tournament",
        (InQuery("url"),),
        http=(LINK("/set-tournament"),),
        socket="set_tournament",
        doc="Loads an event by its URL, or unloads the tournament without one",
    ),
    Action(
        "get_tournament_events",
        (InQuery("url"),),
        http=(GET("/tournament-events"),),
        socket="get_tournament_events",
        doc="List a tournament's events, to pick one for set-tournament",
    ),
    # =====================================================
    # STATES AND STAGES
    # =====================================================
    Action(
        "get_states",
        (InQuery("countryCode"),),
        gui=True,
        http=(GET("/states"),),
        socket="states",
        # Answered through the event's acknowledgement callback
        replies=(),
    ),
    Action(
        "set_current_stage",
        (SCOREBOARD, InBody("codename")),
        gui=True,
        http=(POST("/scoreboard{scoreboardNumber:seg}-set-current-stage"),),
        socket="set_current_stage",
        doc="Set the current ingame stage (selectedStage in stage_strike state)",
    ),
)

ACTIONS_BY_NAME = {action.name: action for action in ACTIONS}
