# Checks what the commentary dashboard gets for the players of a set that
# isn't on a scoreboard (CommentaryPreview): their custom data and avatar,
# and their stats from the provider, only for 1v1 sets and kept for a while.
# Run from the repository root: python test/test_commentary_preview.py
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package


class TournamentDataManager:
    instance = None


# The real one loads the providers and the whole application with them
sys.modules["src.TournamentDataManager"] = types.SimpleNamespace(
    TournamentDataManager=TournamentDataManager
)

# Everything reads and writes ./user_data
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data/custom_player_export/Azure")

from src.CommentaryPreview import CommentaryPreview
from src.StateManager import StateManager


class FakeProvider:
    name = "StartGG"
    SUPPORTS_STATS = True
    url = "https://www.start.gg/tournament/t/event/e"

    def __init__(self):
        self.calls = []

    def GetLastSets(self, playerID, playerNumber, callback, progress_callback, cancel_event):
        self.calls.append(("last_sets", playerID))
        callback.emit(
            {
                "playerNumber": playerNumber,
                "last_sets": [
                    {"round_name": "Winners Round 1", "player1_score": 2, "player2_score": 0}
                ],
            }
        )

    def GetPlayerHistoryStandings(
        self, playerID, playerNumber, gameType, callback, progress_callback, cancel_event
    ):
        self.calls.append(("history_sets", playerID))
        callback.emit(
            {
                "playerNumber": playerNumber,
                "history_sets": [
                    {
                        "placement": 3,
                        "seed": 8,
                        "bracket_type": "DOUBLE_ELIMINATION",
                        "tournament_name": "Big House",
                        "event_date": 1700000000,
                    }
                ],
            }
        )

    def GetRecentSets(
        self, id1, id2, videogame, callback, requestTime, progress_callback, cancel_event
    ):
        self.calls.append(("recent_sets", id1[0], id2[0]))
        callback.emit({"sets": [{"score": [3, 1], "winner": 0}], "request_time": requestTime})


AZURE = {"gamerTag": "Azure", "prefix": "HD", "id": [11, 111]}
# As in the stream queue
MARLOWE = {"name": "Marlowe", "team": "", "id": [22, 222]}


def TestNoProvider():
    TournamentDataManager.instance = None
    with open("user_data/custom_player_export/Azure/bio.txt", "w") as f:
        f.write("Two-time champion\n")
    os.makedirs("user_data/custom_player_export/Marlowe")
    with open("user_data/custom_player_export/Marlowe/stats.json", "w") as f:
        f.write('{"wins": 12}')

    result = CommentaryPreview.Preview([[AZURE], [MARLOWE]])
    assert result["stats"] is False
    assert result["recent_sets"] is None
    assert result["teams"][0][0]["custom"] == {"bio": "Two-time champion"}
    assert result["teams"][1][0]["custom"] == {"stats": {"wins": 12}}
    assert "last_sets" not in result["teams"][0][0]


def TestStats():
    provider = FakeProvider()
    TournamentDataManager.instance = types.SimpleNamespace(provider=provider)
    StateManager.Set("provider_videogame.id", 1386)
    CommentaryPreview._cache.clear()

    result = CommentaryPreview.Preview([[AZURE], [MARLOWE]])
    assert result["stats"] is True
    assert result["recent_sets"] == [{"score": [3, 1], "winner": 0}]
    azure = result["teams"][0][0]
    assert azure["last_sets"][0]["round_name"] == "Winners Round 1"
    assert azure["last_sets"][0]["player_score"] == 2
    assert azure["history_sets"][0]["placement"] == 3
    assert azure["history_sets"][0]["event_date_year"] == "2023"
    # Seeded 8th, came 3rd: placement rounds above the seed
    assert azure["history_sets"][0]["spr"] > 0
    assert len(provider.calls) == 5

    # Asked again (another commentator's page): from the cache
    CommentaryPreview.Preview([[AZURE], [MARLOWE]])
    assert len(provider.calls) == 5


def TestDoublesAndMissingIds():
    provider = FakeProvider()
    TournamentDataManager.instance = types.SimpleNamespace(provider=provider)
    CommentaryPreview._cache.clear()

    # No stats for teams of two, like on the scoreboard
    result = CommentaryPreview.Preview([[AZURE, MARLOWE], [MARLOWE, AZURE]])
    assert result["stats"] is False
    assert len(result["teams"][0]) == 2
    assert provider.calls == []

    # A player without an id (e.g. a custom set): their own stats only
    result = CommentaryPreview.Preview([[AZURE], [{"gamerTag": "Guest"}]])
    assert result["stats"] is True
    assert result["recent_sets"] is None
    assert "last_sets" not in result["teams"][1][0]
    assert ("last_sets", 11) in provider.calls

    # Not a provider with stats
    provider.SUPPORTS_STATS = False
    assert CommentaryPreview.Preview([[AZURE], [MARLOWE]])["stats"] is False

    # Garbage in
    assert CommentaryPreview.Preview(None)["teams"] == []
    assert CommentaryPreview.Preview([["x"], None])["teams"] == [[], []]


if __name__ == "__main__":
    for test in [TestNoProvider, TestStats, TestDoublesAndMissingIds]:
        test()
        print(f"{test.__name__}: OK")
