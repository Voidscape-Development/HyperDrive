# Checks the Twitch predictions of the set on stream, with a fake Twitch API:
# one is opened when a set is loaded, resolved with the winner when it's over,
# and cancelled when another set is loaded first.
# Run from the repository root: python test/test_twitch_predictions.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.TwitchPredictions import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_LOCKED,
    STATUS_RESOLVED,
    OutcomeTitles,
    PredictionManager,
    PredictionTitle,
    TwitchError,
    _Immediate,
)


class FakeApi:
    def __init__(self):
        self.token = "token"
        self.calls = []
        self.next = 0
        self.fail = False

    def Create(self, title, outcomes, window):
        if self.fail:
            raise TwitchError("nope")
        self.next += 1
        self.calls.append(("create", title, tuple(outcomes), window))
        return {
            "id": f"p{self.next}",
            "outcomes": [{"id": f"p{self.next}-{i}", "title": o} for i, o in enumerate(outcomes)],
        }

    def End(self, predictionId, status, winningOutcomeId=None):
        self.calls.append(("end", predictionId, status, winningOutcomeId))
        return {}


def Manager(**settings):
    api = FakeApi()
    values = {"enabled": True, **settings}
    manager = PredictionManager(
        lambda: api, lambda key, default=None: values.get(key, default), executor=_Immediate()
    )
    return manager, api


def TestTitles():
    assert PredictionTitle("Who wins {round}?", "A", "B", "Grand Final") == "Who wins Grand Final?"
    assert PredictionTitle("Who wins {round}?", "A", "B", "") == "Who wins?"
    assert PredictionTitle("{team1} or {team2}?", "Sonix", "Zomba") == "Sonix or Zomba?"
    # A bad template falls back to the default one
    assert PredictionTitle("Who wins {nope}?", "A", "B", "GF") == "Who wins GF?"
    long = PredictionTitle("{team1} vs {team2}", "A" * 40, "B" * 40)
    assert len(long) <= 45 and long.endswith("…")
    assert OutcomeTitles("Sonix", "Zomba") == ("Sonix", "Zomba")
    # Twitch needs distinct outcomes
    assert OutcomeTitles("Same", "same") == ("Same (1)", "same (2)")
    assert len(OutcomeTitles("X" * 40, "Y")[0]) == 25


def TestLifecycle():
    manager, api = Manager(window=10)
    manager.SetLoaded(1, "Sonix", "Zomba", "Grand Final")
    assert api.calls == [("create", "Who wins Grand Final?", ("Sonix", "Zomba"), 30)]
    assert manager.prediction["status"] == STATUS_ACTIVE

    # Loaded again: still the same prediction
    manager.SetLoaded(1, "Sonix", "Zomba", "Grand Final")
    assert len(api.calls) == 1

    # Another set's end doesn't touch it
    manager.SetFinished(99, 1)
    assert len(api.calls) == 1

    manager.SetFinished(1, 2)
    assert api.calls[-1] == ("end", "p1", STATUS_RESOLVED, "p1-1")
    assert manager.prediction["status"] == STATUS_RESOLVED
    assert manager.prediction["winner"] == 2

    # Nothing left to resolve
    manager.SetFinished(1, 1)
    assert len(api.calls) == 2


def TestNewSetCancelsTheOpenOne():
    manager, api = Manager()
    manager.SetLoaded(1, "A", "B")
    manager.SetLoaded(2, "C", "D")
    assert [c[0] for c in api.calls] == ["create", "end", "create"]
    assert api.calls[1] == ("end", "p1", STATUS_CANCELED, None)
    assert manager.prediction["setId"] == 2

    # A draw cancels it
    manager.SetFinished(2, None)
    assert api.calls[-1] == ("end", "p2", STATUS_CANCELED, None)


def TestByHand():
    manager, api = Manager(auto_start=False)
    # Not started automatically
    manager.SetLoaded(1, "A", "B")
    assert api.calls == []
    manager.Start(1, "A", "B")
    manager.Lock()
    manager.Lock()
    assert [c[2] for c in api.calls if c[0] == "end"] == [STATUS_LOCKED]
    # A locked prediction can still be resolved
    manager.Resolve(1)
    assert api.calls[-1] == ("end", "p1", STATUS_RESOLVED, "p1-0")
    assert manager.State()["prediction"]["status"] == STATUS_RESOLVED


def TestDisabledAndErrors():
    manager, api = Manager(enabled=False)
    manager.SetLoaded(1, "A", "B")
    manager.SetFinished(1, 1)
    assert api.calls == []

    manager, api = Manager()
    # Without both teams there's nothing to predict
    manager.SetLoaded(1, "A", "")
    assert api.calls == []

    api.fail = True
    manager.SetLoaded(1, "A", "B")
    assert manager.prediction is None
    assert manager.State()["error"] == "nope"
    api.fail = False
    manager.SetLoaded(1, "A", "B")
    assert manager.State()["error"] == ""


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
