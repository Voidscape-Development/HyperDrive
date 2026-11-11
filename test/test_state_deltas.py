# Checks that the state deltas sent to the layouts, the web app and the
# Stream Deck plugin (DiffStates() of src/StateManager.py) turn the old state
# into the new one when applied the way they apply them: setting or removing
# keys, never inserting into or removing from lists. Random states with
# lists in them.
# Run from the repository root: python test/test_state_deltas.py
import copy
import os
import random
import sys

sys.path.insert(0, os.path.abspath("test"))
from state_harness import CLIENTS, RunTests, Wire

from src.StateManager import REMOVED, DiffStates


def Deltas(old, new):
    """The deltas as the clients get them."""
    deltas = []
    for path, action, _, value in DiffStates(old, new)[1]:
        delta = {"path": list(path), "action": action}
        if action != REMOVED:
            delta["value"] = value
        deltas.append(delta)
    return Wire(deltas)


def CheckApplied(old, new):
    deltas = Deltas(old, new)
    for apply in CLIENTS:
        applied = copy.deepcopy(old)
        for delta in deltas:
            apply(applied, delta)
        assert applied == new, (apply.__name__, old, new, deltas)
    return deltas


def RandomScalar():
    # 1, 1.0 and True: DeepDiff's deltas of one becoming another had no value
    return random.choice(["a", "b", "c", "m1", "m2", 1, 2, 3, 1.0, True, None])


def RandomValue(depth=0):
    roll = random.random()
    if depth > 2 or roll < 0.4:
        return RandomScalar()
    if roll < 0.7:
        return [RandomValue(depth + 1) for _ in range(random.randint(0, 5))]
    return {k: RandomValue(depth + 1) for k in random.sample("wxyz", random.randint(0, 4))}


def Mutate(value, depth=0):
    """A changed copy: items added, removed, reordered or changed."""
    if isinstance(value, list):
        value = [Mutate(v, depth + 1) if random.random() < 0.3 else v for v in value]
        roll = random.random()
        if roll < 0.25 and value:
            del value[random.randrange(len(value))]
        elif roll < 0.5:
            value.insert(random.randint(0, len(value)), RandomValue(depth + 1))
        elif roll < 0.6:
            random.shuffle(value)
        return value
    if isinstance(value, dict):
        value = {k: Mutate(v, depth + 1) if random.random() < 0.4 else v for k, v in value.items()}
        if random.random() < 0.2 and value:
            del value[random.choice(list(value))]
        if random.random() < 0.2:
            value[random.choice("wxyz")] = RandomValue(depth + 1)
        return value
    return RandomValue(depth) if random.random() < 0.5 else value


def TestRandom(iterations=5000, seed=0):
    random.seed(seed)
    for _ in range(iterations):
        old = {"bracket": {"focus": RandomValue(), "x": RandomValue()}}
        # The state's top keys stay
        new = {"bracket": {k: Mutate(v) for k, v in copy.deepcopy(old["bracket"]).items()}}
        for delta in CheckApplied(old, new):
            # Nothing is done inside a list: it's set whole
            assert all(isinstance(key, str) for key in delta["path"]), delta


def TestFocusLists():
    old = {"bracket": {"focus": {"sets": ["m1", "m2", "m3", "m4"], "rounds": ["w:1"]}}}
    new = {"bracket": {"focus": {"sets": ["m1", "m3"], "rounds": []}}}
    deltas = CheckApplied(old, new)
    assert deltas == [
        {"path": ["bracket", "focus", "sets"], "action": "values_changed", "value": ["m1", "m3"]},
        {"path": ["bracket", "focus", "rounds"], "action": "values_changed", "value": []},
    ], deltas


if __name__ == "__main__":
    RunTests(globals())
