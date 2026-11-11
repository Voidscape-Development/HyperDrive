# Checks the dotted-path helpers of src/Helpers/DictHelper.py that the state
# and the settings are read and written with, in particular where a value on
# the way isn't a dict (None from an API, a text, a list).
# Run from the repository root: python test/test_dict_helper.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.Helpers.DictHelper import deep_clone, deep_clones, deep_get, deep_set, deep_unset


def TestGet():
    data = {"a": {"b": {"c": 1, "none": None, "zero": 0}, "text": "x", "list": [1]}, "n": None}
    assert deep_get(data, "a.b.c") == 1
    assert deep_get(data, "a.b") is data["a"]["b"]
    assert deep_get(data, "a.b.zero", 5) == 0
    # A key that's there with None is None, not the default
    assert deep_get(data, "a.b.none", 5) is None
    assert deep_get(data, "n", 5) is None
    # Missing, or through something that isn't a dict
    for key in ["x", "a.x", "a.b.x", "a.b.c.d", "a.text.x", "a.list.0", "n.x", "a.b.none.x.y"]:
        assert deep_get(data, key) is None, key
        assert deep_get(data, key, 5) == 5, key
    # The default is never looked into
    assert deep_get(data, "x.c", {"c": "from the default"}) == {"c": "from the default"}
    assert deep_get(data, "a.text.c", {"c": 1}) == {"c": 1}
    assert deep_get("text", "a", 5) == 5


def TestSet():
    data = {}
    deep_set(data, "a.b.c", 1)
    deep_set(data, "a.b.d", [1])
    deep_set(data, "top", None)
    assert data == {"a": {"b": {"c": 1, "d": [1]}}, "top": None}
    inner = data["a"]["b"]
    deep_set(data, "a.b.c", 2)
    assert data["a"]["b"] is inner and inner["c"] == 2

    # What's on the way and isn't a dict becomes one
    deep_set(data, "top.x.y", 1)
    deep_set(data, "a.b.c.deeper", 2)
    deep_set(data, "a.b.d.0", 3)
    assert data == {"a": {"b": {"c": {"deeper": 2}, "d": {"0": 3}}}, "top": {"x": {"y": 1}}}


def TestUnset():
    data = {"a": {"b": {"c": 1, "d": 2}}, "text": "x", "n": None}
    deep_unset(data, "a.b.c")
    deep_unset(data, "a.b.missing")
    assert data == {"a": {"b": {"d": 2}}, "text": "x", "n": None}
    # Nothing to remove in what isn't a dict, which stays
    deep_unset(data, "text.x")
    deep_unset(data, "n.x.y")
    deep_unset(data, "a.b.d.x")
    assert data == {"a": {"b": {"d": 2}}, "text": "x", "n": None}
    # The dicts on the way are made, as they always were
    deep_unset(data, "new.x.y")
    assert data["new"] == {"x": {}}
    deep_unset(data, "a")
    deep_unset(data, "a")
    assert "a" not in data


def TestClone():
    data = {"a": {"b": [1, {"c": None}], 5: "int key", "t": (1, 2)}, "f": 1.5, "s": "ü"}
    clone = deep_clone(data)
    assert clone == {"a": {"b": [1, {"c": None}], 5: "int key", "t": [1, 2]}, "f": 1.5, "s": "ü"}
    assert clone["a"] is not data["a"] and clone["a"]["b"][1] is not data["a"]["b"][1]
    first, second = deep_clones(data, 2)
    assert first == second == clone
    assert first["a"] is not second["a"] and first["a"] is not data["a"]

    # Values msgpack doesn't take are cloned too
    odd = {"set": {1, 2}, "big": 2**70, "inner": {"k": [1]}}
    clone = deep_clone(odd)
    assert clone == odd
    assert clone["set"] is not odd["set"] and clone["inner"]["k"] is not odd["inner"]["k"]
    first, second = deep_clones(odd, 2)
    assert first == second == odd and first["inner"] is not second["inner"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
