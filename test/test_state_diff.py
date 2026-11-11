# Checks DiffStates() of src/StateManager.py, which finds what changed in the
# state: the changes it gives turn the old state into the new one (also when
# only the paths that were set are compared), with the distinctions the
# layouts and the exported files make (1, 1.0 and True, None, lists as a
# whole), and a dict with too many changes for a delta is sent whole.
# Run from the repository root: python test/test_state_diff.py
import copy
import os
import random
import sys

sys.path.insert(0, os.path.abspath("test"))
from state_harness import ApplyStrict, RunTests, Wire

from src.Helpers.DictHelper import deep_clone, deep_get, deep_set, deep_unset
from src.StateManager import ADDED, CHANGED, REMOVED, DiffStates, SameValue


def Apply(old, delta):
    state = Wire(old)
    for path, action, _, value in delta:
        message = {"path": list(path), "action": action}
        if action != REMOVED:
            message["value"] = value
        ApplyStrict(state, Wire(message))
    return state


def Changes(old, new, paths=None):
    changes, delta = DiffStates(old, new, paths)
    # Without a limit the delta is the changes
    assert delta == changes
    return [(".".join(map(str, path)), action) for path, action, _, _ in changes]


def TestSameValue():
    same = [(1, 1), ("a", "a"), (None, None), (1.5, 1.5), ([1, {"a": None}], [1, {"a": None}])]
    same += [((1, 2), [1, 2]), (float("nan"), float("nan")), ({"a": (1,)}, {"a": [1]})]
    for a, b in same:
        assert SameValue(a, b), (a, b)
    different = [(1, 1.0), (1, True), (0, False), (0, None), ("", None), ("1", 1), ([], None)]
    different += [([1], [1.0]), ([1], [True]), ({"a": 1}, {"a": 1.0}), ({}, []), ([1, 2], [2, 1])]
    different += [(1.0, True), ("a", "b"), ([], [None]), ({"a": None}, {})]
    for a, b in different:
        assert not SameValue(a, b), (a, b)
        assert not SameValue(b, a), (a, b)
    # Values that aren't JSON are compared too
    assert SameValue({1, 2}, {1, 2}) and not SameValue({1, 2}, {1, 3})
    assert SameValue(2**70, 2**70) and not SameValue(2**70, 2**70 + 1)


def TestChanges():
    old = {"a": {"x": 1, "y": {"z": "s"}, "gone": {"k": 1}}, "b": [1, 2], "n": None}
    assert Changes(old, copy.deepcopy(old)) == []
    assert Changes({}, {}) == []

    new = {"a": {"x": 2, "y": {"z": "s", "w": None}, "added": {"k": 1}}, "b": [1, 2, 3], "n": 0}
    assert Changes(old, new) == [
        ("a.gone", REMOVED),
        ("a.x", CHANGED),
        ("a.y.w", ADDED),
        ("a.added", ADDED),
        ("b", CHANGED),
        ("n", CHANGED),
    ]
    changes, _ = DiffStates(old, new)
    assert changes[0] == (("a", "gone"), REMOVED, {"k": 1}, None)
    assert changes[1] == (("a", "x"), CHANGED, 1, 2)
    assert changes[2] == (("a", "y", "w"), ADDED, None, None)


def TestTypes():
    # What == takes for equal but isn't in the layouts nor in the files
    for a, b in [(1, 1.0), (1, True), (0, False), (1.0, True)]:
        assert Changes({"k": {"v": a}}, {"k": {"v": b}}) == [("k.v", CHANGED)], (a, b)
        assert Changes({"k": [a]}, {"k": [b]}) == [("k", CHANGED)], (a, b)
    # None is a value like the others: a key with None isn't a missing key
    assert Changes({"k": 1}, {"k": None}) == [("k", CHANGED)]
    assert Changes({"k": None}, {"k": {"a": 1}}) == [("k", CHANGED)]
    assert Changes({"k": {"a": 1}}, {"k": None}) == [("k", CHANGED)]
    assert Changes({}, {"k": None}) == [("k", ADDED)]
    assert Changes({"k": None}, {}) == [("k", REMOVED)]
    assert Changes({"k": None}, {"k": None}) == []
    # A dict becoming something else, or the other way, changes as a whole
    assert Changes({"k": {"a": 1}}, {"k": [1]}) == [("k", CHANGED)]
    assert Changes({"k": "text"}, {"k": {"a": 1}}) == [("k", CHANGED)]
    # A tuple is a list once saved (lastSavedState) and once sent
    assert Changes({"k": [1, [2]]}, {"k": (1, (2,))}) == []
    assert Changes({"k": float("nan")}, {"k": float("nan")}) == []


def TestLists():
    # Lists are replaced, whatever changed in them
    old = {"bracket": {"focus": {"sets": ["m1", "m2", "m3", "m4"], "rounds": ["w:1"], "x": [1]}}}
    new = {"bracket": {"focus": {"sets": ["m1", "m3"], "rounds": [], "x": [1]}}}
    changes, delta = DiffStates(old, new)
    assert delta == [
        (("bracket", "focus", "sets"), CHANGED, ["m1", "m2", "m3", "m4"], ["m1", "m3"]),
        (("bracket", "focus", "rounds"), CHANGED, ["w:1"], []),
    ], delta
    assert Apply(old, delta) == new
    assert Changes({"l": [{"a": 1}]}, {"l": [{"a": 2}]}) == [("l", CHANGED)]


def TestKeys():
    # Keys the paths DeepDiff wrote couldn't hold, and keys that aren't text
    old = {"a/b": {"q'k": 1, 'dq"': 1, "back\\slash": 1, "x y": 1, "": 1, 7: "int", "ü": 1}}
    new = copy.deepcopy(old)
    for key in list(new["a/b"]):
        new["a/b"][key] = 2
    new["a/b"][8] = "added"
    changes, delta = DiffStates(old, new)
    assert [c[0] for c in changes] == [("a/b", k) for k in new["a/b"]]
    assert Apply(old, delta) == Wire(new)

    # 7 and "7" are one key to the clients: removed first, then added
    changes, delta = DiffStates({"d": {"7": "text"}}, {"d": {7: "int"}})
    assert [(c[0], c[1]) for c in changes] == [(("d", "7"), REMOVED), (("d", 7), ADDED)]
    state = {"d": {"7": "text"}}
    for path, action, _, value in delta:
        # As the clients do, for which a missing key is fine
        state["d"].pop(str(path[-1]), None)
        if action != REMOVED:
            state["d"][str(path[-1])] = value
    assert state == {"d": {"7": "int"}}


def TestPaths():
    old = {"a": {"x": 1, "y": {"z": 1}}, "b": {"k": 1}, "c": 1}
    new = {"a": {"x": 2, "y": {"z": 2, "w": 3}}, "b": {"k": 1}, "c": 1}
    # Only what's in the paths is compared
    assert Changes(old, new, [("a", "x")]) == [("a.x", CHANGED)]
    assert Changes(old, new, [("a", "y", "w"), ("b",), ("c",)]) == [("a.y.w", ADDED)]
    assert Changes(old, new, [("a", "y")]) == [("a.y.z", CHANGED), ("a.y.w", ADDED)]
    # A path and paths inside it, in any order: everything in it, once
    for paths in [[("a",), ("a", "x")], [("a", "x"), ("a",)], [("a", "y", "z"), ("a",), ("a",)]]:
        assert Changes(old, new, paths) == [("a.x", CHANGED), ("a.y.z", CHANGED), ("a.y.w", ADDED)]
    # A path that's nowhere, or the same on both sides
    assert Changes(old, new, [("nope", "k"), ("b", "k"), ("c", "k", "j")]) == []

    # Where the path goes through something that isn't a dict on both
    # sides, that's what changed
    assert Changes({"a": None}, {"a": {"b": {"c": 1}}}, [("a", "b", "c")]) == [("a", CHANGED)]
    assert Changes({"a": {"b": {"c": 1}}}, {"a": 5}, [("a", "b", "c")]) == [("a", CHANGED)]
    assert Changes({}, {"a": {"b": {"c": 1}}}, [("a", "b", "c")]) == [("a", ADDED)]
    assert Changes({"a": {"b": {"c": 1}}}, {}, [("a", "b", "c")]) == [("a", REMOVED)]
    assert Changes({"a": [1]}, {"a": [1]}, [("a", "0", "c")]) == []


def TestCollapse():
    def Dict(count, value):
        return {str(i): value for i in range(count)}

    # More changes in a dict than a delta takes: the dict is sent whole, the
    # changes (which the file export follows) stay one by one
    old = {"top": {"small": Dict(5, 0), "big": Dict(30, 0), "same": Dict(30, 0)}}
    new = {"top": {"small": Dict(5, 1), "big": Dict(30, 1), "same": Dict(30, 0)}}
    changes, delta = DiffStates(old, new, None, 10)
    assert len(changes) == 35
    assert [(d[0], d[1]) for d in delta] == [
        (("top", "small", str(i)), CHANGED) for i in range(5)
    ] + [(("top", "big"), CHANGED)]
    assert delta[-1] == (("top", "big"), CHANGED, None, new["top"]["big"])
    assert delta[-1][3] is new["top"]["big"]
    assert Apply(old, delta) == new

    # Counting what's left once the dicts in it are sent whole
    old = {"top": {str(i): Dict(11, 0) for i in range(10)}}
    new = {"top": {str(i): Dict(11, 1) for i in range(10)}}
    changes, delta = DiffStates(old, new, None, 10)
    assert len(changes) == 110
    assert [d[0] for d in delta] == [("top", str(i)) for i in range(10)]
    changes, delta = DiffStates(old, new, None, 9)
    assert [d[0] for d in delta] == [("top",)]
    changes, delta = DiffStates(old, new, [("top", "3"), ("top", "4", "1")], 10)
    assert [d[0] for d in delta] == [("top", "3"), ("top", "4", "1")]
    changes, delta = DiffStates(old, new, [("top", str(i), str(i)) for i in range(10)], 9)
    assert [d[0] for d in delta] == [("top",)]

    # When only the delta is wanted, a dict that's sent whole isn't gone
    # through to its end: the same delta, sooner
    old = {"top": {str(i): {"a": {"b": 0}, "c": 0} for i in range(50)}, "x": {"y": 1}}
    new = {"top": {str(i): {"a": {"b": 1}, "c": 1} for i in range(50)}, "x": {"y": 2}}
    for paths in (None, [("top",), ("x", "y")], [("top", str(i), "a") for i in range(50)]):
        changes, delta = DiffStates(old, new, paths, 10)
        assert [d[0] for d in delta] == [("top",), ("x", "y")][
            : 2 if paths is None or len(paths) == 2 else 1
        ]
        assert DiffStates(old, new, paths, 10, everyChange=False) == (None, delta)

    # The state itself has no path to be sent at: the caller sees the
    # delta is too long, and has everything sent
    changes, delta = DiffStates(Dict(30, 0), Dict(30, 1), None, 10)
    assert len(delta) == 30


KEYS = ["a", "b", "c", "1", "x y", "q'uote", "sl/ash", "ü"]
SCALARS = [None, 0, 1, 1.0, True, False, "s", "t", "", 2.5, float("nan"), -0.0, 0.0]


def RandomValue(depth=0):
    r = random.random()
    if depth < 3 and r < 0.4:
        value = {random.choice(KEYS): RandomValue(depth + 1) for _ in range(random.randint(0, 4))}
        if random.random() < 0.1:
            value[random.choice([5, 6])] = RandomValue(depth + 1)
        return value
    if r < 0.5:
        return [RandomValue(depth + 1) for _ in range(random.randint(0, 3))]
    if r < 0.55:
        return (1, RandomValue(depth + 1))
    return random.choice(SCALARS)


def Mutate(state):
    """Changes state the way Set() and Unset() do, and returns their paths."""
    paths = []
    for _ in range(random.randint(0, 7)):
        path = [random.choice(["score", "game", "x", "new"])] + [
            random.choice(KEYS[:6]) for _ in range(random.randint(0, 3))
        ]
        key = ".".join(path)
        current = deep_get(state, key)
        r = random.random()
        if r < 0.35 and isinstance(current, dict) and current:
            # Same dict with a few changes, like most Set() calls
            value = copy.deepcopy(current)
            for _ in range(random.randint(0, 3)):
                k = random.choice(list(value.keys()) + KEYS)
                m = random.random()
                if m < 0.5:
                    value[k] = RandomValue(2)
                elif m < 0.7:
                    value.pop(k, None)
            deep_set(state, key, value)
        elif r < 0.5:
            deep_set(state, key, copy.deepcopy(current))
        elif r < 0.85:
            deep_set(state, key, RandomValue(1))
        else:
            deep_unset(state, key)
        paths.append(tuple(path))
    return paths


def Value(state, path):
    for key in path:
        state = state[key]
    return state


def TestRandom(iterations=6000, seed=0):
    random.seed(seed)
    changed = 0
    for _ in range(iterations):
        base = {"score": RandomValue(), "game": RandomValue(), "x": RandomValue()}
        # As lastSavedState is: a clone
        old = deep_clone(base)
        new = copy.deepcopy(base)
        paths = Mutate(new)
        limit = random.choice([None, 1, 3, 100])

        whole = DiffStates(old, new, None, limit)
        narrowed = DiffStates(old, new, paths, limit)
        for used, (changes, delta) in ((None, whole), (paths, narrowed)):
            assert Apply(old, delta) == Wire(new), (old, new, paths, delta)
            for path, action, _, value in changes:
                # The new values are the state's own, for the caller to copy
                assert action == REMOVED or value is Value(new, path)
            # Nothing is changed twice, or inside something that changed
            seen = [c[0] for c in changes]
            assert len(set(seen)) == len(seen)
            assert not any(a != b and a == b[: len(a)] for a in seen for b in seen), seen
            if limit is None:
                assert [(c[0], c[1]) for c in changes] == [(d[0], d[1]) for d in delta]
            else:
                # A dict that's sent whole has more changes in it than that
                for path, action, _, value in delta:
                    inside = sum(1 for c in seen if c[: len(path)] == path)
                    assert inside == 1 or inside > limit, (path, inside, limit)
            # The delta alone is the same, found without every change
            assert DiffStates(old, new, used, limit, everyChange=False) == (None, delta)
        # Comparing only the paths that were set finds the same changes
        assert sorted(map(repr, whole[0])) == sorted(map(repr, narrowed[0])), (old, new, paths)
        changed += bool(whole[0])
    assert changed > iterations / 2


if __name__ == "__main__":
    RunTests(globals())
