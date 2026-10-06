# Checks the games of a scoreboard's set and what's reported to start.gg.
# Run from the repository root: python test/test_game_report.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.TSHGameReport import *


def TestScoreSync():
    report = GameReport()
    report.SetBestOf(5)
    assert len(report.games) == 5

    report.SetScore(1, 2)
    report.SetScore(2, 1)
    assert report.Score() == (2, 1)
    assert [g["winner"] for g in report.games] == [1, 1, 2, None, None]

    # Lowering a score removes the team's last win
    report.SetScore(1, 1)
    assert [g["winner"] for g in report.games] == [1, None, 2, None, None]
    assert report.CurrentGameIndex() == 1

    # Draws are kept and don't count
    report.SetWinner(1, DRAW)
    assert report.Score() == (1, 1)
    report.SetScore(2, 2)
    assert [g["winner"] for g in report.games] == [1, DRAW, 2, 2, None]

    # Fewer games shown keeps the ones played
    report.SetBestOf(3)
    assert len(report.games) == 4
    report.SetBestOf(7)
    assert len(report.games) == 7


def TestSwap():
    report = GameReport()
    report.SetBestOf(3)
    report.SetWinner(0, 1)
    report.SetCharacters(0, 1, ["Mario"])
    report.SetCharacters(0, 2, ["Fox"])
    report.Swap()
    assert report.games[0]["winner"] == 2
    assert report.games[0]["characters"] == {1: ["Fox"], 2: ["Mario"]}


def TestGameData():
    report = GameReport()
    report.SetBestOf(3)
    report.SetWinner(0, 1)
    report.SetStage(0, "battlefield")
    report.SetCharacters(0, 1, ["Mario"])
    report.SetCharacters(0, 2, ["Fox", None])
    report.SetWinner(1, DRAW)
    report.SetWinner(2, 2)

    characters = {"Mario": 1302, "Fox": 1279}
    stages = {"battlefield": 311}
    data = BuildGameData(report, ["e1", "e2"], False, characters.get, stages.get)
    assert data == [
        {
            "gameNum": 1,
            "winnerId": "e1",
            "stageId": "311",
            "selections": [
                {"entrantId": "e1", "characterId": 1302},
                {"entrantId": "e2", "characterId": 1279},
            ],
        },
        {"gameNum": 3, "winnerId": "e2"},
    ], data
    assert SetWinnerEntrant(report, ["e1", "e2"], False) is None

    # Teams swapped on the scoreboard: team 1 is start.gg's second slot
    data = BuildGameData(report, ["e1", "e2"], True, characters.get, stages.get)
    assert data[0]["winnerId"] == "e2"
    assert data[0]["selections"][0] == {"entrantId": "e2", "characterId": 1302}

    report.SetWinner(1, 1)
    assert SetWinnerEntrant(report, ["e1", "e2"], False) == "e1"
    assert SetWinnerEntrant(report, ["e1", "e2"], True) == "e2"


def TestFromProvider():
    report = GameReport()
    report.SetBestOf(5)
    games = [
        {"winner": 0, "stage": "fd", "characters": [["Mario"], ["Fox"]]},
        {"winner": 1, "stage": None, "characters": [[], []]},
    ]
    report.SetFromProvider(games, swapped=True)
    assert report.games[0]["winner"] == 2
    assert report.games[0]["characters"] == {1: ["Fox"], 2: ["Mario"]}
    assert report.Score() == (1, 1)
    assert len(report.games) == 5

    copy = GameReport.FromDict(report.ToDict())
    assert copy.games == report.games


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
