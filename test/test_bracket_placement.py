# Checks where the bracket focus layouts place a bracket
# (bracket.channels.<channel>.placement), from the sample bracket the layout
# previews use: the sets level with the sets feeding them, the round names,
# the lines and the world's size.
# Run from the repository root: python test/test_bracket_placement.py
import json
import os
import sys

sys.path.insert(0, os.path.abspath("src/Helpers"))

from BracketPlacement import *

with open("scripts/previews/sample_state.json", encoding="utf-8") as f:
    BRACKET = json.load(f)["bracket"]["bracket"]


def TestNone():
    assert Place(None) is None
    assert Place({}) is None


def TestElimination():
    placed = Place(BRACKET)
    sets = BRACKET["sets"]
    assert set(placed["sets"]) == {i for i, s in sets.items() if s.get("resetNeeded") is not False}
    for i, box in placed["sets"].items():
        assert (box["w"], box["h"]) == (SET_W, SET_H)
        # Level with the sets feeding it, when they're in its column's side
        fed = [f for f, s in sets.items() if (s.get("nextWin") or {}).get("set") == i]
        fed = [
            placed["sets"][f]
            for f in fed
            if f in placed["sets"] and sets[f]["side"] == sets[i]["side"]
        ]
        if len(fed) == 2:
            assert box["y"] == max(MARGIN + HEADER_H, sum(b["y"] for b in fed) / 2), i
    # Every column has its round name above it
    for side in BRACKET["sides"].values():
        for column in side:
            header = placed["headers"][column["key"]]
            first = placed["sets"][column["sets"][0]]
            assert header["x"] == first["x"] and header["y"] + HEADER_H <= first["y"] + 1
    # The world holds everything
    for box in list(placed["sets"].values()) + list(placed["headers"].values()):
        assert box["x"] + box["w"] <= placed["width"] and box["y"] + box["h"] <= placed["height"]


def TestLines():
    placed = Place(BRACKET)
    assert placed["lines"]
    for line in placed["lines"]:
        a, b = placed["sets"][line["from"]], placed["sets"][line["to"]]
        start, end = line["points"][0], line["points"][-1]
        assert start == [a["x"] + a["w"], a["y"] + a["h"] / 2]
        assert end == [b["x"], b["y"] + b["h"] / 2]
        # Only across, then down or up, then across
        for p, q in zip(line["points"], line["points"][1:]):
            assert p[0] == q[0] or p[1] == q[1]


def TestArrows():
    bracket = json.loads(json.dumps(BRACKET))
    bracket["progressionsOut"] = 2
    last = [
        i for i, s in bracket["sets"].items() if s["side"] == "winners" and not s.get("nextWin")
    ]
    if not last:
        # The winners final goes to the grand final: cut it off
        final = bracket["sides"]["winners"][-1]["sets"][0]
        bracket["sets"][final]["nextWin"] = None
        last = [final]
    arrows = [line for line in Place(bracket)["lines"] if line.get("arrow")]
    assert {line["from"] for line in arrows} >= set(last)
    for line in arrows:
        assert line["to"] is None and line["points"][1][0] - line["points"][0][0] == 45


def TestPool():
    bracket = {
        "type": "ROUND_ROBIN",
        "sides": {
            "pool": [
                {"key": "pool:1", "name": "Round 1", "sets": ["a", "b"]},
                {"key": "pool:2", "name": "Round 2", "sets": ["c"]},
            ]
        },
        "sets": {i: {"id": i, "players": []} for i in "abc"},
    }
    placed = Place(bracket)
    assert placed["sets"]["b"]["y"] == placed["sets"]["a"]["y"] + SET_H + ROW_GAP
    assert placed["sets"]["c"]["x"] == MARGIN + SET_W + COLUMN_GAP
    assert placed["byes"]["pool:1"] == {
        "x": MARGIN,
        "y": placed["sets"]["b"]["y"] + SET_H + ROW_GAP,
        "w": SET_W,
    }
    assert placed["standings"]["x"] == MARGIN + 2 * (SET_W + COLUMN_GAP)
    assert placed["lines"] == []


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("Test"):
            test()
    print("ok")
