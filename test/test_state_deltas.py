# Checks that the state deltas sent to the layouts and the web app
# (StateManager.WholeListDeltas()) turn the old state into the new one when
# applied the way they apply them: setting or removing keys, never inserting
# into or removing from lists. Random states with lists in them.
# Run from the repository root: python test/test_state_deltas.py
import copy
import os
import random
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from deepdiff import DeepDiff, Delta

from src.StateManager import StateManager


def Apply(data, delta):
    """applyDelta() of layout/include/globals.js and stateDelta.js."""
    current = data
    for key in delta["path"][:-1]:
        if isinstance(current, dict) and key not in current:
            current[key] = {}
        current = current[key]
    last = delta["path"][-1]
    if delta["action"] == "dictionary_item_removed":
        current.pop(last, None)
    else:
        current[last] = delta["value"]


def RandomScalar():
    # No booleans: DeepDiff's delta of 1 becoming True has no value, a
    # quirk of its own that lists have nothing to do with
    return random.choice(["a", "b", "c", "m1", "m2", 1, 2, 3])


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
        diff = DeepDiff(
            old,
            new,
            exclude_types=[type(None)],
            verbose_level=2,
            threshold_to_diff_deeper=StateManager.DIFF_DEEPER_THRESHOLD,
        )
        # Neither are values changing type: DeepDiff's deltas of some of
        # them have no value
        if "type_changes" in diff:
            continue
        StateManager.state = new
        deltas = StateManager.WholeListDeltas(Delta(diff).to_flat_dicts())
        applied = copy.deepcopy(old)
        for delta in deltas:
            Apply(applied, delta)
        assert applied == new, (old, new, deltas)


def TestFocusLists():
    old = {"bracket": {"focus": {"sets": ["m1", "m2", "m3", "m4"], "rounds": ["w:1"]}}}
    new = {"bracket": {"focus": {"sets": ["m1", "m3"], "rounds": []}}}
    StateManager.state = new
    deltas = StateManager.WholeListDeltas(
        Delta(DeepDiff(old, new, verbose_level=2)).to_flat_dicts()
    )
    assert {tuple(d["path"]) for d in deltas} == {
        ("bracket", "focus", "sets"),
        ("bracket", "focus", "rounds"),
    }, deltas
    applied = copy.deepcopy(old)
    for delta in deltas:
        Apply(applied, delta)
    assert applied == new


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
