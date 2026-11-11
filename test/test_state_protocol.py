# Checks test/state_protocol.py, the Python port of the clients' state
# protocol that the StateManager tests apply deltas with, against the
# conformance fixture the JavaScript client is held to
# (test/fixtures/state_protocol.json, see docs/state-protocol.md).
# Run from the repository root: python test/test_state_protocol.py
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import state_protocol

FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "state_protocol.json"
)
CLIENT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "layout", "include", "state_client.js"
)

with open(FIXTURE, encoding="utf-8") as file:
    fixture = json.load(file)


def TestActions():
    assert list(state_protocol.SET_ACTIONS) == fixture["actions"]["set"]
    assert list(state_protocol.REMOVE_ACTIONS) == fixture["actions"]["remove"]
    # The JavaScript client's, as written in its source
    with open(CLIENT, encoding="utf-8") as file:
        source = file.read()
    assert f"const SET_ACTIONS = {json.dumps(fixture['actions']['set'])};" in source
    assert f"const REMOVE_ACTIONS = {json.dumps(fixture['actions']['remove'])};" in source


def TestFixture():
    steps = 0
    for case in fixture["cases"]:
        requests = []
        sync = state_protocol.Sync(lambda reason, index: requests.append(reason))
        state = {}
        waiting = False
        for i, step in enumerate(case["steps"]):
            at = f"{case['name']}, step {i + 1}"
            asked = len(requests)
            if "full" in step:
                state = sync.full(copy.deepcopy(step["full"]))
                waiting = False
            elif "reset" in step:
                sync.reset()
                state = {}
                waiting = False
            else:
                held, before = state, copy.deepcopy(state)
                status, state = sync.delta(copy.deepcopy(step["delta"]), held)
                assert status == step["status"], (at, status)
                # Applying never writes to the state it is given
                assert held == before, at
                if status != "applied":
                    assert state is held, at
                waiting = waiting or step["resync"]
            assert len(requests) - asked == (1 if step["resync"] else 0), at
            assert sync.index == step["index"], (at, sync.index)
            assert sync.resyncing == waiting, at
            if "state" in step:
                assert state == step["state"], (at, state)
            steps += 1
    assert steps > 50


def TestSharing():
    state = {"a": {"b": {"c": 1}, "d": {"e": 2}}, "l": [{"x": 1}, {"x": 2}], "g": {"n": 1}}
    before = copy.deepcopy(state)
    new = state_protocol.apply_deltas(
        state,
        [
            {"path": ["a", "b", "c"], "action": "values_changed", "value": 5},
            {"path": ["l", 1, "x"], "action": "values_changed", "value": 3},
        ],
    )
    assert state == before
    assert new == {"a": {"b": {"c": 5}, "d": {"e": 2}}, "l": [{"x": 1}, {"x": 3}], "g": {"n": 1}}
    assert new["g"] is state["g"] and new["a"]["d"] is state["a"]["d"]
    assert new["l"][0] is state["l"][0]
    assert new["a"] is not state["a"] and new["l"] is not state["l"]


def TestNumberKeys():
    # StateManager's own state may have numbers as keys, which are text
    # once sent
    state = {"score": {1: {"score": 0}}}
    delta = [{"path": ["score", 1, "score"], "action": "values_changed", "value": 2}]
    assert state_protocol.apply_deltas(state, delta) == {"score": {1: {"score": 2}}}
    sent = json.loads(json.dumps(state))
    assert state_protocol.apply_deltas(sent, delta) == {"score": {"1": {"score": 2}}}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
