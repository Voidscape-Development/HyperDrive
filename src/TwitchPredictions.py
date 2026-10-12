# Twitch predictions for the set on stream: one opens when a set is loaded
# on the chosen scoreboard ("Who wins?", with a team for each outcome), and
# it's resolved with the winner once the set is over. Predictions can also
# be started, locked, resolved or cancelled by hand (/twitch/prediction/...
# on the web server, e.g. from a Stream Deck).
#
# It needs a Twitch user access token of the channel, with the
# channel:manage:predictions scope (Settings > Twitch Predictions). The
# channel has to be a Twitch affiliate or partner to have predictions.
#
# PredictionManager has no Qt in it, so it can be tested on its own with a
# fake API; TwitchPredictionsHook connects it to the scoreboards.
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

import requests
from loguru import logger

HELIX_URL = "https://api.twitch.tv/helix"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
TIMEOUT_SECS = 15
SCOPE = "channel:manage:predictions"

# Twitch's limits
TITLE_MAX = 45
OUTCOME_MAX = 25
WINDOW_MIN_SECS = 30
WINDOW_MAX_SECS = 1800

DEFAULT_TITLE = "Who wins {round}?"
DEFAULT_WINDOW_SECS = 180

STATUS_ACTIVE = "ACTIVE"
STATUS_LOCKED = "LOCKED"
STATUS_RESOLVED = "RESOLVED"
STATUS_CANCELED = "CANCELED"


class TwitchError(Exception):
    pass


def Shorten(text, limit):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def PredictionTitle(template, team1, team2, roundName=""):
    """The prediction's title from a template with {team1}, {team2} and
    {round}, within Twitch's limit. Without a round, "Who wins {round}?"
    becomes "Who wins?"."""
    template = template or DEFAULT_TITLE
    values = {"team1": team1 or "", "team2": team2 or "", "round": roundName or ""}
    try:
        title = template.format(**values)
    except (KeyError, IndexError, ValueError):
        title = DEFAULT_TITLE.format(**values)
    # "Who wins ?" when the round is unknown
    title = " ".join(title.replace(" ?", "?").split())
    return Shorten(title, TITLE_MAX)


def OutcomeTitles(team1, team2):
    """Twitch needs two distinct outcome titles."""
    a = Shorten(team1 or "Team 1", OUTCOME_MAX)
    b = Shorten(team2 or "Team 2", OUTCOME_MAX)
    if a.lower() == b.lower():
        a = Shorten(f"{a} (1)", OUTCOME_MAX)
        b = Shorten(f"{b} (2)", OUTCOME_MAX)
    return a, b


class TwitchApi:
    """The few Helix calls predictions need."""

    def __init__(self, token, clientId=None):
        self.token = (token or "").strip()
        if self.token.lower().startswith("oauth:"):
            self.token = self.token[6:]
        self.clientId = clientId
        self.broadcasterId = None

    def Validate(self):
        """Checks the token: {client_id, login, user_id, scopes}."""
        if not self.token:
            raise TwitchError("No Twitch token. Set one in Settings > Twitch Predictions.")
        try:
            response = requests.get(
                VALIDATE_URL,
                headers={"Authorization": f"OAuth {self.token}"},
                timeout=TIMEOUT_SECS,
            )
        except requests.RequestException as e:
            raise TwitchError(str(e))
        if response.status_code != 200:
            raise TwitchError("Twitch refused the token (expired or revoked?)")
        info = response.json()
        if SCOPE not in (info.get("scopes") or []):
            raise TwitchError(f"The Twitch token doesn't have the {SCOPE} scope")
        self.clientId = info.get("client_id")
        self.broadcasterId = info.get("user_id")
        return info

    def _Request(self, method, path, body):
        if not self.broadcasterId:
            self.Validate()
        try:
            response = requests.request(
                method,
                HELIX_URL + path,
                json=dict(body, broadcaster_id=self.broadcasterId),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Client-Id": self.clientId or "",
                },
                timeout=TIMEOUT_SECS,
            )
        except requests.RequestException as e:
            raise TwitchError(str(e))
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 300:
            raise TwitchError(data.get("message") or f"Twitch answered {response.status_code}")
        return (data.get("data") or [{}])[0]

    def Create(self, title, outcomes, window):
        """Returns {id, outcomes: [{id, title}]}."""
        return self._Request(
            "POST",
            "/predictions",
            {
                "title": title,
                "outcomes": [{"title": o} for o in outcomes],
                "prediction_window": window,
            },
        )

    def End(self, predictionId, status, winningOutcomeId=None):
        body = {"id": predictionId, "status": status}
        if winningOutcomeId:
            body["winning_outcome_id"] = winningOutcomeId
        return self._Request("PATCH", "/predictions", body)


class _Immediate:
    """Runs submitted functions right away (for tests)."""

    def submit(self, fn, *args):
        fn(*args)


class PredictionManager:
    """Keeps track of the prediction for the set on stream. Every call to
    Twitch runs, in order, on one background thread (or the executor
    given), and so does everything that touches the prediction."""

    def __init__(self, api_factory, settings, executor=None, on_change=None):
        # api_factory() returns a TwitchApi (or a fake), settings(key,
        # default) reads a setting of the twitch_predictions section
        self.api_factory = api_factory
        self.settings = settings
        self.executor = executor or ThreadPoolExecutor(max_workers=1)
        self.on_change = on_change or (lambda state: None)
        self.api = None
        self.apiToken = None
        # {id, setId, title, outcomes: {1: outcome id, 2: ...}, names, status}
        self.prediction = None
        self.lastError = ""
        self.lock = threading.Lock()

    def Enabled(self):
        return bool(self.settings("enabled", False))

    def State(self):
        with self.lock:
            prediction = dict(self.prediction) if self.prediction else None
        return {"enabled": self.Enabled(), "prediction": prediction, "error": self.lastError}

    def _Api(self):
        api = self.api_factory()
        # A new token means a new API client
        if self.api is None or getattr(api, "token", None) != self.apiToken:
            self.api = api
            self.apiToken = getattr(api, "token", None)
        return self.api

    def _Run(self, fn, *args):
        def Task():
            try:
                fn(*args)
                self.lastError = ""
            except Exception as e:
                if not isinstance(e, TwitchError):
                    logger.error(traceback.format_exc())
                self.lastError = str(e)
                logger.error(f"Twitch prediction: {e}")
            self.on_change(self.State())

        self.executor.submit(Task)

    # From the scoreboard

    def SetLoaded(self, setId, team1, team2, roundName=""):
        """A set was loaded on the scoreboard: the open prediction of
        another set is cancelled and one is opened for this one."""
        if not self.Enabled() or not self.settings("auto_start", True):
            return
        if not (team1 and team2):
            return
        self._Run(self._Start, setId, team1, team2, roundName)

    def SetFinished(self, setId, winnerTeam):
        """The set is over: its prediction is resolved, or cancelled if
        there's no winner (e.g. a draw)."""
        if not self.Enabled() or not self.settings("auto_resolve", True):
            return
        self._Run(self._Finish, setId, winnerTeam)

    # By hand

    def Start(self, setId, team1, team2, roundName=""):
        self._Run(self._Start, setId, team1, team2, roundName)

    def Lock(self):
        self._Run(self._End, STATUS_LOCKED, None)

    def Resolve(self, team):
        self._Run(self._End, STATUS_RESOLVED, int(team))

    def Cancel(self):
        self._Run(self._End, STATUS_CANCELED, None)

    # On the background thread

    def _Open(self):
        with self.lock:
            p = self.prediction
            return p if p and p["status"] in (STATUS_ACTIVE, STATUS_LOCKED) else None

    def _Start(self, setId, team1, team2, roundName):
        current = self._Open()
        if current and setId is not None and str(current.get("setId")) == str(setId):
            # Already open for this set (e.g. it was loaded again)
            return
        if current:
            self._End(STATUS_CANCELED, None)
        api = self._Api()
        title = PredictionTitle(self.settings("title", DEFAULT_TITLE), team1, team2, roundName)
        outcomes = OutcomeTitles(team1, team2)
        window = int(self.settings("window", DEFAULT_WINDOW_SECS) or DEFAULT_WINDOW_SECS)
        window = max(WINDOW_MIN_SECS, min(WINDOW_MAX_SECS, window))
        result = api.Create(title, list(outcomes), window)
        ids = [o.get("id") for o in result.get("outcomes") or []]
        with self.lock:
            self.prediction = {
                "id": result.get("id"),
                "setId": setId,
                "title": title,
                "names": {1: outcomes[0], 2: outcomes[1]},
                "outcomes": {1: ids[0] if ids else None, 2: ids[1] if len(ids) > 1 else None},
                "status": STATUS_ACTIVE,
            }
        logger.info(f"Twitch prediction started: {title}")

    def _Finish(self, setId, winnerTeam):
        current = self._Open()
        if not current:
            return
        if setId is not None and str(current.get("setId")) != str(setId):
            return
        if winnerTeam in (1, 2):
            self._End(STATUS_RESOLVED, winnerTeam)
        else:
            self._End(STATUS_CANCELED, None)

    def _End(self, status, team):
        current = self._Open()
        if not current:
            return
        if status == STATUS_LOCKED and current["status"] == STATUS_LOCKED:
            return
        outcome = None
        if status == STATUS_RESOLVED:
            outcome = current["outcomes"].get(team)
            if not outcome:
                raise TwitchError(f"No outcome for team {team}")
        self._Api().End(current["id"], status, outcome)
        with self.lock:
            current["status"] = status
            if status == STATUS_RESOLVED:
                current["winner"] = team
        logger.info(f"Twitch prediction {status.lower()}: {current['title']}")


class TwitchPredictionsHook:
    """Connects the scoreboard chosen in the settings to a
    PredictionManager. Set up once the scoreboards exist."""

    instance: "TwitchPredictionsHook" = None
    # Seconds to wait after a set is loaded, for its players to come in
    LOAD_DELAY_MS = 4000

    def __init__(self):
        from qtpy.QtCore import QTimer

        from .ScoreboardManager import ScoreboardManager
        from .SettingsManager import SettingsManager
        from .StateManager import StateManager

        self.StateManager = StateManager
        self.QTimer = QTimer

        def Setting(key, default=None):
            return SettingsManager.Get(f"twitch_predictions.{key}", default)

        self.Setting = Setting
        self.manager = PredictionManager(
            lambda: TwitchApi(SettingsManager.Get("api_keys.twitch", "")),
            Setting,
            on_change=self.Changed,
        )
        self.connected = set()
        ScoreboardManager.instance.signals.ScoreboardAdded.connect(self.Connect)
        for n in ScoreboardManager.instance.GetScoreboardNumbers():
            self.Connect(n)
        TwitchPredictionsHook.instance = self

    def Scoreboard(self):
        try:
            return int(self.Setting("scoreboard", 1) or 1)
        except (TypeError, ValueError):
            return 1

    def Connect(self, number):
        from .ScoreboardManager import ScoreboardManager

        scoreboard = ScoreboardManager.instance.GetScoreboard(number)
        if scoreboard is None or number in self.connected:
            return
        self.connected.add(number)
        scoreboard.signals.NewSetLoaded.connect(lambda number=number: self.SetLoaded(number))
        scoreboard.signals.SetFinished.connect(
            lambda setId, number=number: self.SetFinished(number, setId)
        )

    def Teams(self, number):
        """The names of the scoreboard's teams: the team name, else its
        players' names."""
        names = []
        for team in (1, 2):
            data = self.StateManager.Get(f"score.{number}.team.{team}", {}) or {}
            name = data.get("teamName") or ""
            if not name:
                players = [
                    (p or {}).get("name") or ""
                    for _, p in sorted((data.get("player") or {}).items())
                ]
                name = " / ".join(p for p in players if p)
            names.append(name)
        return names

    def SetLoaded(self, number):
        if number != self.Scoreboard() or not self.manager.Enabled():
            return

        def Later():
            team1, team2 = self.Teams(number)
            self.manager.SetLoaded(
                self.StateManager.Get(f"score.{number}.set_id"),
                team1,
                team2,
                self.StateManager.Get(f"score.{number}.match", "") or "",
            )

        self.QTimer.singleShot(self.LOAD_DELAY_MS, Later)

    def SetFinished(self, number, setId):
        if number != self.Scoreboard():
            return
        score1 = self.StateManager.Get(f"score.{number}.team.1.score", 0) or 0
        score2 = self.StateManager.Get(f"score.{number}.team.2.score", 0) or 0
        winner = None if score1 == score2 else (1 if score1 > score2 else 2)
        self.manager.SetFinished(setId, winner)

    def StartForScoreboard(self):
        number = self.Scoreboard()
        team1, team2 = self.Teams(number)
        if not (team1 and team2):
            return "NO_TEAMS", 400
        self.manager.Start(
            self.StateManager.Get(f"score.{number}.set_id"),
            team1,
            team2,
            self.StateManager.Get(f"score.{number}.match", "") or "",
        )
        return self.manager.State()

    def Changed(self, state):
        # From the background thread: the state manager takes care of it
        self.StateManager.Set("twitch_prediction", state.get("prediction") or {})
