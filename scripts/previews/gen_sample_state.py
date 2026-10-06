"""Builds sample_state.json, the program state the layout previews are
rendered with, by running TSH and filling it in with sample_players.json.

Usage, from the repository root, after download_assets.py:
    python scripts/previews/gen_sample_state.py

Use a clean checkout: TSH starts from the program state and settings already
in out/ and user_data/. Needs a display (or QT_QPA_PLATFORM=offscreen). Run it
again when what TSH sends to the layouts changes.
"""

import asyncio
import json
import os
import sys

import orjson

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ["QT_API"] = "PyQt6"

from qasync import QEventLoop  # noqa: E402
from qtpy.QtCore import QTimer  # noqa: E402

import src  # noqa: E402
from src.StateManager import StateManager  # noqa: E402
from src.TSHBracketWidget import TSHBracketWidget  # noqa: E402
from src.TSHGameAssetManager import TSHGameAssetManager  # noqa: E402
from src.TSHPlayerListWidget import TSHPlayerListWidget  # noqa: E402
from src.TSHScoreboardManager import TSHScoreboardManager  # noqa: E402
from src.TSHTournamentDataProvider import TSHTournamentDataProvider  # noqa: E402
from src.TSHWebServer import WebServer  # noqa: E402

GAME = "ssbu"
OUT_FILE = os.path.join(HERE, "sample_state.json")

with open(os.path.join(HERE, "sample_players.json"), encoding="utf-8") as f:
    SAMPLE = json.load(f)
PLAYERS = SAMPLE["players"]


def player(index, **extra):
    """Sample player `index` (1-based), seeded by their position"""
    return {**PLAYERS[index - 1], "seed": index, **extra}


def set_game():
    games = list(TSHGameAssetManager.instance.games.keys())
    TSHGameAssetManager.instance.LoadGameAssets(games.index(GAME) + 1, async_mode=False)


def set_tournament_info():
    TSHTournamentDataProvider.instance.signals.tournament_data_updated.emit(SAMPLE["tournament"])


def set_scoreboard():
    sb = SAMPLE["scoreboard"]
    scoreboard = TSHScoreboardManager.instance.GetScoreboard(1)
    for team, index in enumerate(sb["players"], start=1):
        scoreboard.signals.ChangeSetData.emit(
            {
                "team": team,
                "player": 1,
                "data": player(index),
            }
        )
    scoreboard.signals.ChangeSetData.emit(
        {
            "team1score": sb["score"][0],
            "team2score": sb["score"][1],
            "bestOf": sb["best_of"],
            "tournament_phase": sb["phase"],
            "round_name": sb["match"],
        }
    )


def set_stats():
    """What TSH would fetch from start.gg for the players on the scoreboard"""
    stats = TSHScoreboardManager.instance.GetScoreboard(1).stats
    stats.UpdateRecentSets({"sets": SAMPLE["recent_sets"], "request_time": 1})
    for team, index in enumerate(SAMPLE["scoreboard"]["players"], start=1):
        p = PLAYERS[index - 1]
        stats.UpdateLastSets(
            {
                "playerNumber": str(team),
                "last_sets": [
                    {
                        "player1_name": p["gamerTag"],
                        "player1_team": p.get("prefix"),
                        "player1_seed": index,
                        **s,
                    }
                    for s in SAMPLE["last_sets"]
                ],
            }
        )
        stats.UpdateHistorySets({"playerNumber": str(team), "history_sets": SAMPLE["history_sets"]})


def set_commentary():
    for i, data in enumerate(SAMPLE["commentators"], start=1):
        WebServer.actions.set_commentary_data(i, data)


def set_player_list(window):
    standings = [{"players": [player(i)]} for i in range(1, 9)]
    playerList = window.findChildren(TSHPlayerListWidget)[0]
    playerList.LoadFromStandings(standings)


def set_bracket():
    widget = TSHBracketWidget.instance
    widget.playerList.LoadFromStandings(
        [{"players": [player(i)]} for i in range(1, len(PLAYERS) + 1)], enrichBlocking=False
    )
    phase = widget.NewPhase(name="Top 16")
    bracket = phase.bracket

    # The better seed wins every set, but for a few upsets, until the grand
    # final, which is left to be played
    upsets = {6, 11}
    changed = True
    while changed:
        changed = False
        for m in bracket.order:
            p1, p2 = m.players
            if m.finished or m.isBye or m.isGrandFinal or p1 <= 0 or p2 <= 0:
                continue
            winner = 0 if p1 < p2 else 1
            if (p1 + p2) in upsets:
                winner = 1 - winner
            m.score = [3, 1] if winner == 0 else [2, 3]
            m.finished = True
            bracket.Resolve()
            changed = True
    widget.BracketEdited()


def main():
    loop = QEventLoop(src.App)
    asyncio.set_event_loop(loop)
    window = src.Window(loop)

    steps = [
        set_game,
        set_tournament_info,
        set_scoreboard,
        set_stats,
        set_commentary,
        lambda: set_player_list(window),
        set_bracket,
    ]

    def run(i=0):
        if i < len(steps):
            steps[i]()
            QTimer.singleShot(1500, lambda: run(i + 1))
            return

        with open(OUT_FILE, "wb") as f:
            f.write(
                orjson.dumps(
                    StateManager.state,
                    option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS,
                )
            )
            f.write(b"\n")
        print(f"Wrote {OUT_FILE}")
        os._exit(0)

    # Give the program time to start
    QTimer.singleShot(8000, run)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
