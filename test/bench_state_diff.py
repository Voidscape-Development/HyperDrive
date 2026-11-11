# Times StateManager's saves on big changes of the state (a whole bracket,
# the teams' stats swapping), where finding what changed is most of the work.
# Not a test: run by hand, from the repository root, when changing how the
# state is compared.
#   python test/bench_state_diff.py [--files] [--sets=N] [--only=text] [StateManager.py]
# --files also exports the files of out/ (most of the time, when on), --sets
# is how many sets the bracket and each team's stats have (1000 if not
# given), --only=text runs the lines with text in their name. With another
# StateManager.py (e.g. an older one) that one is timed instead.
import copy
import importlib.util
import os
import statistics
import sys
import tempfile
import time
import types

os.environ.setdefault("QT_API", "PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = os.path.abspath(".")
sys.path.insert(0, REPO)
package = types.ModuleType("src")
package.__path__ = [os.path.join(REPO, "src")]
sys.modules["src"] = package

args = [a for a in sys.argv[1:] if not a.startswith("--")]
ONLY = next((a[7:] for a in sys.argv[1:] if a.startswith("--only=")), "")
SETS = int(next((a[7:] for a in sys.argv[1:] if a.startswith("--sets=")), 1000))
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data")

if args:
    spec = importlib.util.spec_from_file_location("src.StateManager", os.path.abspath(args[0]))
    module = importlib.util.module_from_spec(spec)
    sys.modules["src.StateManager"] = module
    spec.loader.exec_module(module)

from loguru import logger

from src.SettingsManager import SettingsManager
from src.StateManager import StateManager

logger.remove()
SettingsManager.SaveSettings = lambda: None
FILES = "--files" in sys.argv
SettingsManager.settings = {"general": {"disable_export": not FILES}}

sent = []
StateManager.signals.state_updated.connect(lambda message: sent.append(len(message["delta"])))
StateManager.signals.state_big_change.connect(lambda: sent.append("whole state"))


def Player(seed):
    return {
        "name": f"Player {seed}",
        "team": f"T{seed % 7}",
        "country": {"code": "BR", "name": "Brazil", "flag": f"flag{seed % 5}"},
        "character": {"1": {"name": f"Char {seed % 30}", "skin": seed % 8, "icon": f"i{seed}"}},
        "seed": seed,
        "online_avatar": None,
    }


def Bracket(sets, offset=0, ids=0):
    """About 30 values a set."""
    return {
        "name": "Top 8",
        "phase": "Bracket",
        "rounds": {str(r): {"name": f"Round {r}", "best_of": 3 + offset} for r in range(12)},
        "sets": {
            str(i + ids): {
                "round": i % 12,
                "state": offset % 3,
                "score": [offset, (i + offset) % 3],
                "stream": None,
                "players": {"1": Player(i + offset), "2": Player(i * 3 + offset)},
            }
            for i in range(sets)
        },
    }


def Stats(side, count):
    """About 14 values a set."""
    return {
        "name": f"Team {side}",
        "last_sets": {
            str(i): {
                "round_name": f"Round {i}",
                "tournament": {"name": f"Tournament {i % 40}", "picture": None},
                "player": {"name": f"P{side}", "score": (i * side) % 4},
                "opponent": {"name": f"Opponent {i * side}", "score": i % 3, "seed": i + side},
                "characters": {"1": {"name": f"C{i % 20 + side}", "skin": side}},
                "online": side == 1,
            }
            for i in range(count)
        },
    }


def Count(value):
    if isinstance(value, dict):
        return sum(Count(v) for v in value.values())
    return 1


def Prepare():
    with StateManager.lock:
        StateManager.state = {
            "game": {"stages": {str(i): {"name": f"Stage {i}", "id": i} for i in range(300)}},
            "bracket": Bracket(SETS),
            "score": {"1": {"team": {"1": Stats(1, SETS), "2": Stats(2, SETS)}}},
            "commentary": {str(i): Player(i) for i in range(4)},
        }
        StateManager.lastSavedState = copy.deepcopy(StateManager.state)
        StateManager.changedPaths = []
        if hasattr(StateManager, "replacedPaths"):
            StateManager.replacedPaths = set()


def Time(name, change, repeat=5):
    if ONLY not in name:
        return
    times = []
    for _ in range(repeat):
        Prepare()
        sent.clear()
        StateManager.BlockSaving()
        values = change()
        if FILES and hasattr(os, "sync"):
            # As when time went by since the files were last written. Some
            # file systems (ext4) are much slower to write over a file
            # that isn't on the disk yet, which isn't what's measured here.
            os.sync()
        start = time.perf_counter()
        StateManager.ReleaseSaving()
        times.append(time.perf_counter() - start)
        assert StateManager.changedPaths == []
    ms = statistics.median(times) * 1000
    print(f"{name:<58}{values:>8} values {ms:>9.1f} ms   sent: {sent or 'nothing'}")


def WholeBracket():
    value = Bracket(SETS, offset=1)
    StateManager.Set("bracket", value)
    return Count(value)


def OtherBracket():
    value = Bracket(SETS, offset=1, ids=SETS * 5)
    StateManager.Set("bracket", value)
    return Count(value)


def BracketOneScore():
    value = copy.deepcopy(StateManager.Get("bracket"))
    value["sets"][str(SETS // 2)]["score"] = [2, 1]
    StateManager.Set("bracket", value)
    return Count(value)


def BracketUnchanged():
    value = copy.deepcopy(StateManager.Get("bracket"))
    StateManager.Set("bracket", value)
    return Count(value)


def BracketSetBySet():
    value = Bracket(SETS, offset=1)
    for key, bracketSet in value["sets"].items():
        StateManager.Set(f"bracket.sets.{key}", bracketSet)
    return Count(value["sets"])


def Swap(replace):
    team1 = StateManager.Get("score.1.team.1")
    team2 = StateManager.Get("score.1.team.2")
    StateManager.Set("score.1.team.1", team2, replace=replace)
    StateManager.Set("score.1.team.2", team1, replace=replace)
    return Count(team1) + Count(team2)


def OneScore():
    StateManager.Set("score.1.team.1.name", "Another")
    return 1


def Nothing():
    return 0


if __name__ == "__main__":
    Prepare()
    print(
        f"{args[0] if args else 'src/StateManager.py'}, state of {Count(StateManager.state)} values"
    )
    Time("Another bracket, same sets (every value changes)", WholeBracket)
    Time("Another bracket, other sets (removed and added)", OtherBracket)
    Time("The bracket set again with one score changed", BracketOneScore)
    Time("The bracket set again, unchanged", BracketUnchanged)
    Time("Every set of the bracket set on its own", BracketSetBySet)
    Time("The teams' stats swapped, replace=True", lambda: Swap(True))
    Time("The teams' stats swapped, replace=False", lambda: Swap(False))
    Time("One value set", OneScore)
    Time("Save with nothing set (whole state compared)", Nothing)
