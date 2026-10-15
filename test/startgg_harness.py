# Runs StartGGDataProvider against recorded start.gg responses, for
# test_startgg_provider.py, and records them (scripts/record_startgg_fixtures.py).
# The app around the provider is replaced with small stand-ins: a made-up
# Super Smash Bros. Ultimate game with start.gg's real character ids, an empty
# player database and default settings, so the results don't depend on the
# machine the tests run on.
import gzip
import hashlib
import json
import os
import re
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE_DIR = os.path.join(ROOT, "test", "fixtures", "startgg")
RECORDING = os.path.join(FIXTURE_DIR, "test_event.json.gz")
ULTIMATE_ID = 1386

os.chdir(ROOT)
sys.path.insert(0, ROOT)
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [os.path.join(ROOT, path)]
        sys.modules[name] = package

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.GameAssetManager import GameAssetManager
from src.Helpers.LocaleHelper import LocaleHelper
from src.PlayerDB import PlayerDB
from src.SettingsManager import SettingsManager
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider


# =====================================================
# REQUEST KEYS
# =====================================================
def RequestKey(url, jsonParams=None, params=None):
    """What identifies a request in a recording. The query's text is hashed,
    so a changed query needs a new recording."""
    body = jsonParams or {}
    return json.dumps(
        {
            "url": url,
            "operation": body.get("operationName"),
            "query": hashlib.sha1((body.get("query") or "").encode()).hexdigest()[:12],
            "variables": body.get("variables"),
            "params": params,
        },
        sort_keys=True,
    )


def LoadRecording(path=RECORDING):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def SaveJson(path, data, compress=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if compress:
        # mtime=0: the same data always makes the same file
        with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as z:
            z.write(text.encode("utf-8"))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


# =====================================================
# STAND-INS FOR THE APP
# =====================================================
def Slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class FakeGame:
    """A loaded Ultimate with start.gg's characters and the stages the
    recording uses, and no asset files. The lookups are GameAssetManager's."""

    GetCharacterFromStartGGId = GameAssetManager.GetCharacterFromStartGGId
    GetStageFromStartGGId = GameAssetManager.GetStageFromStartGGId
    GetStartGGCharacterId = GameAssetManager.GetStartGGCharacterId
    GetStartGGStageId = GameAssetManager.GetStartGGStageId
    GetCharacterAssets = GameAssetManager.GetCharacterAssets

    def __init__(self, stages=()):
        with open(os.path.join(ROOT, "assets", "characters.json"), encoding="utf-8") as f:
            startgg = json.load(f)["entities"]["character"]
        self.startgg_id_to_character = {str(c["id"]): c for c in startgg}
        self.characters = {}
        for c in startgg:
            if c.get("videogameId") == ULTIMATE_ID:
                self.characters[c["name"]] = {
                    "codename": Slug(c["name"]),
                    "smashgg_name": c["name"],
                    "display_name": c["name"],
                    "en_name": c["name"],
                }
        self.stages = {
            Slug(name): {
                "smashgg_id": id,
                "name": name,
                "display_name": name,
                "en_name": name,
                "codename": Slug(name),
            }
            for id, name in stages
        }
        self.selectedGame = {
            "codename": "ssbu",
            "name": "Super Smash Bros. Ultimate",
            "smashgg_game_id": ULTIMATE_ID,
            "assets": {},
            "path": "./user_data/games/ssbu",
        }


def StagesIn(data):
    """(id, name) of every stage in start.gg responses. They only give ids,
    so the made-up game names them "Stage <id>"."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            stage = value.get("stage")
            if isinstance(stage, dict) and stage.get("id") is not None:
                found.add(stage["id"])
            if value.get("stageId") is not None:
                found.add(value["stageId"])
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(data)
    return [(id, f"Stage {id}") for id in sorted(found, key=str)]


class SyncPool:
    """Runs workers right away, in order, so results are deterministic"""

    def start(self, worker):
        worker.run()


class FakeSignal:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values[0] if len(values) == 1 else values)


class FakeManager:
    """The TournamentDataManager the provider emits signals on"""

    def __init__(self):
        self.signals = types.SimpleNamespace(
            game_changed=FakeSignal(), player_mains_updated=FakeSignal()
        )


class Callback:
    """What the provider's callback methods (GetLastSets...) emit to"""

    def __init__(self):
        self.value = None

    def emit(self, value):
        self.value = value


def SetUpApp(stages=()):
    """Default settings, English round names, an empty player database and
    the made-up game. Returns the players the provider adds to the DB."""
    SettingsManager.Get = staticmethod(lambda key, default=None: default)

    with open(
        os.path.join(ROOT, "src", "i18n", "tournament_term", "en.json"), encoding="utf-8"
    ) as f:
        terms = json.load(f)
    LocaleHelper.matchNames = dict(terms["match"])
    LocaleHelper.phaseNames = dict(terms["phase"])

    added = []
    PlayerDB.database = {}
    PlayerDB.AddPlayers = staticmethod(lambda players, *a, **k: added.extend(players))
    PlayerDB.GetPlayer = staticmethod(lambda tag: None)

    GameAssetManager.instance = FakeGame(stages)
    return added


# =====================================================
# PROVIDERS
# =====================================================
def NewProvider(url):
    return StartGGDataProvider(url, SyncPool(), FakeManager())


def ReplayProvider(recording):
    """A provider answering from the recording. Requests it doesn't have are
    kept in provider.misses (and answered with {}, like a failed request)."""
    responses = {r["key"]: r["response"] for r in recording["requests"]}
    provider = NewProvider(recording["event"])
    provider.misses = []

    def query(url=None, type=None, headers=None, jsonParams=None, params=None, **kwargs):
        key = RequestKey(url, jsonParams, params)
        if key not in responses:
            provider.misses.append(key)
            return {}
        return json.loads(json.dumps(responses[key]))

    provider.QueryRequests = query
    return provider


def RecordingProvider(url):
    """A provider querying start.gg for real, keeping every request and its
    response in provider.recorded."""
    provider = NewProvider(url)
    provider.recorded = {}
    real = provider.QueryRequests

    def query(url=None, type=None, headers=None, jsonParams=None, params=None, **kwargs):
        response = real(url, type, headers, jsonParams, params, **kwargs)
        key = RequestKey(url, jsonParams, params)
        provider.recorded[key] = {
            "key": key,
            "url": url,
            "operation": (jsonParams or {}).get("operationName"),
            "variables": (jsonParams or {}).get("variables"),
            "query": (jsonParams or {}).get("query"),
            "params": params,
            "response": response,
        }
        return response

    provider.QueryRequests = query
    return provider


# =====================================================
# SCENARIO
# =====================================================
# Every provider method the app calls, in one fixed order. Arguments (set
# ids, players, streams) come from earlier results, so the same calls are made
# when recording and when replaying the anonymized recording.
def Call(outputs, name, fn, *args, **kwargs):
    try:
        outputs[name] = fn(*args, **kwargs)
    except Exception as e:
        outputs[name] = {"exception": f"{type(e).__name__}: {e}"}
    return outputs[name]


def WithCallback(fn, **kwargs):
    callback = Callback()
    fn(callback=callback, progress_callback=None, cancel_event=None, **kwargs)
    return callback.value


def RunScenario(provider, added):
    out = {}
    Call(out, "tournament_data", provider.GetTournamentData)
    Call(out, "icon_url", provider.GetIconURL)
    Call(out, "streams_and_stations", provider.GetStreamsAndStations)

    phases = Call(out, "phases", provider.GetTournamentPhases) or []
    groupIds = [g["id"] for p in phases if isinstance(p, dict) for g in p.get("groups", [])]
    for groupId in groupIds[:1]:
        Call(out, "phase_group", provider.GetTournamentPhaseGroup, groupId)
        Call(out, "phase_group_sets", provider.GetTournamentPhaseGroupSets, groupId)

    Call(out, "matches_open", provider.GetMatches, getFinished=False)
    matches = Call(out, "matches_all", provider.GetMatches, getFinished=True) or []
    setIds = sorted(str(m["id"]) for m in matches if isinstance(m, dict) and m.get("id"))
    out["match"] = {}
    for setId in setIds:
        Call(out["match"], setId, provider.GetMatch, setId)
    out["future_match"] = {}
    for setId in setIds[:3]:
        Call(out["future_match"], setId, provider.GetFutureMatch, setId)
    Call(
        out,
        "future_matches_list",
        provider.GetFutureMatchesList,
        [{"id": i} for i in setIds[:3]],
        progress_callback=None,
        cancel_event=None,
    )

    stations = Call(out, "stations", provider.GetStations) or []
    Call(out, "stream_queue", provider.GetStreamQueue)
    out["stream_match"], out["station_matches"] = {}, {}
    for s in stations if isinstance(stations, list) else []:
        if s.get("type") == "stream":
            Call(out["stream_match"], str(s.get("identifier")), provider.GetStreamMatchId, s)
        else:
            Call(out["station_matches"], str(s.get("id")), provider.GetStationMatchsId, s.get("id"))

    Call(out, "completed_sets", provider.GetCompletedSets, None, None)
    Call(out, "set_durations", provider.GetSetDurations)
    standings = Call(out, "standings", provider.GetStandings, 8, None, None) or []

    # The top two players: their sets, past events and their head to head
    players = [
        t["players"][0]
        for t in standings
        if isinstance(t, dict) and t.get("players") and t["players"][0].get("id")
    ][:2]
    for n, p in enumerate(players, 1):
        Call(
            out,
            f"last_sets_{n}",
            WithCallback,
            provider.GetLastSets,
            playerID=p["id"][0],
            playerNumber=str(n),
        )
        Call(
            out,
            f"history_sets_{n}",
            WithCallback,
            provider.GetPlayerHistoryStandings,
            playerID=p["id"][0],
            playerNumber=str(n),
            gameType=ULTIMATE_ID,
        )
    if len(players) == 2:
        Call(
            out,
            "recent_sets",
            WithCallback,
            provider.GetRecentSets,
            id1=players[0]["id"],
            id2=players[1]["id"],
            videogame=ULTIMATE_ID,
            requestTime=0,
        )

    # Entrants, for the player database
    entrants = Call({}, "entrants", provider.FetchEntrants)
    out["entrants_added"] = sorted(entrants, key=lambda p: json.dumps(p, sort_keys=True))

    # The mains of the top two seeds, by their start.gg user
    seeded = sorted(
        (p for p in entrants if p.get("startgg_user_slug")), key=lambda p: p.get("seed") or 0
    )
    out["user_mains"] = {}
    for slug in [p["startgg_user_slug"] for p in seeded[:2]]:
        Call(out["user_mains"], slug, provider.GetUserMains, slug, ULTIMATE_ID)
    return out
