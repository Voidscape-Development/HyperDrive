# Checks editing the player database (renames, duplicate tags, deletes) and
# the seeds set by hand in SeedManager.
# Run from the repository root: python test/test_player_db_seeds.py
import os
import sys
import tempfile
import types

import orjson

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication

from src.Helpers.QtHelper import init_gui_executor

app = QApplication.instance() or QApplication(sys.argv)
init_gui_executor()


# The asset manager loads games on import; the DB only needs its icons
class FakeAssetSignals(QObject):
    onLoad = Signal()


class FakeAssetManager:
    instance = None

    def __init__(self):
        self.signals = FakeAssetSignals()
        self.stockIcons = {}
        self.characters = {}
        self.selectedGame = {}


FakeAssetManager.instance = FakeAssetManager()
assetModule = types.ModuleType("src.GameAssetManager")
assetModule.GameAssetManager = FakeAssetManager
sys.modules["src.GameAssetManager"] = assetModule

# Files are written to ./user_data, so work in a scratch directory
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
repoDir = os.path.abspath(".")
os.chdir(workDir)

from src.PlayerDB import PlayerDB
from src.SeedManager import SeedManager


def SavedPlayers():
    return list(PlayerDB.ReadDB().values())


def TestMigrateFromJSON():
    with open("./user_data/local_players.json", "wb") as f:
        f.write(
            orjson.dumps(
                [
                    {"prefix": "TSM", "gamerTag": "Bob", "mains": {"ssbu": [["Link", 0, ""]]}},
                    {"prefix": "", "gamerTag": "Alice", "twitter": "alice"},
                    # Saved as a string by old versions
                    {"gamerTag": "Carol", "mains": '{"ssbu": [["Peach", 1]]}'},
                ]
            )
        )
    PlayerDB.database = {}
    PlayerDB.LoadDB()

    assert set(PlayerDB.database) == {"TSM Bob", "Alice", "Carol"}
    assert PlayerDB.database["Carol"]["mains"] == {"ssbu": [["Peach", 1]]}
    # Unset fields stay missing, so .get() defaults still work
    assert "mains" not in PlayerDB.database["Alice"]
    assert len(SavedPlayers()) == 3
    # The JSON file is kept as a backup and not imported again
    assert not os.path.exists("./user_data/local_players.json")
    assert os.path.exists("./user_data/local_players.json.bak")
    PlayerDB.database = {}
    PlayerDB.LoadDB()
    assert len(PlayerDB.database) == 3

    # Export and import
    PlayerDB.ExportJSON("./export.json")
    with open("./export.json", "rb") as f:
        exported = orjson.loads(f.read())
    assert {p["gamerTag"] for p in exported} == {"Bob", "Alice", "Carol"}
    PlayerDB.DeletePlayers(["Alice", "Carol"])
    assert len(SavedPlayers()) == 1
    assert PlayerDB.ImportJSON("./export.json") == 3
    assert set(PlayerDB.database) == {"TSM Bob", "Alice", "Carol"}
    assert PlayerDB.database["Alice"]["twitter"] == "alice"


def TestReloadAfterExternalEdit():
    from sqlmodel import Session, select

    from src.PlayerDBModels import GetEngine, Player

    PlayerDB.database = {}
    PlayerDB.DeletePlayers([])
    PlayerDB.AddPlayers(
        [{"prefix": "", "gamerTag": "Dan", "seed": 3}, {"prefix": "", "gamerTag": "Erin"}]
    )

    # Edited like the admin page does: straight in the database
    with Session(GetEngine()) as session:
        dan = session.exec(select(Player).where(Player.tag == "Dan")).one()
        dan.name = "Dan D"
        dan.prefix = " C9 "
        session.add(dan)
        erin = session.exec(select(Player).where(Player.tag == "Erin")).one()
        session.delete(erin)
        session.add(Player(gamerTag="Finn", twitter="finn"))
        session.commit()
        session.refresh(dan)
        # The tag follows the prefix and gamerTag
        assert dan.tag == "C9 Dan" and dan.prefix == "C9"

    PlayerDB.ReloadDB()
    assert set(PlayerDB.database) == {"C9 Dan", "Finn"}
    assert PlayerDB.database["C9 Dan"]["name"] == "Dan D"
    assert PlayerDB.database["Finn"]["twitter"] == "finn"

    # Fields that aren't saved survive a reload of the same player
    PlayerDB.AddPlayers([{"prefix": "C9", "gamerTag": "Dan", "seed": 9}])
    with Session(GetEngine()) as session:
        dan = session.exec(select(Player).where(Player.tag == "C9 Dan")).one()
        dan.twitter = "dan"
        session.add(dan)
        session.commit()
    PlayerDB.ReloadDB()
    assert PlayerDB.database["C9 Dan"]["twitter"] == "dan"
    assert PlayerDB.database["C9 Dan"]["seed"] == 9


def TestUpdatePlayer():
    PlayerDB.database = {}
    PlayerDB.AddPlayers(
        [
            {
                "prefix": "TSM",
                "gamerTag": "Bob",
                "name": "Bob B",
                "mains": {"ssbu": [["Link", 0, ""]]},
                "seed": 4,
            },
            {"prefix": "", "gamerTag": "Alice"},
        ]
    )

    # New player
    assert (
        PlayerDB.UpdatePlayer(None, {"prefix": " ", "gamerTag": " Eve ", "name": "Eve E"}) == "Eve"
    )
    assert PlayerDB.database["Eve"]["gamerTag"] == "Eve"

    # Empty tags and tags of other players are refused
    assert PlayerDB.UpdatePlayer(None, {"prefix": "", "gamerTag": ""}) is None
    assert PlayerDB.UpdatePlayer("Eve", {"prefix": "", "gamerTag": "Alice"}) is None
    assert "Eve" in PlayerDB.database

    # Renaming keeps what the editor doesn't show, and drops the old entry
    newTag = PlayerDB.UpdatePlayer("TSM Bob", {"prefix": "G2", "gamerTag": "Bob", "name": "Bobby"})
    assert newTag == "G2 Bob"
    assert "TSM Bob" not in PlayerDB.database
    bob = PlayerDB.database["G2 Bob"]
    assert bob["name"] == "Bobby"
    assert bob["mains"] == {"ssbu": [["Link", 0, ""]]}
    assert bob["seed"] == 4

    # Saving under the same tag works too
    assert (
        PlayerDB.UpdatePlayer("G2 Bob", {"prefix": "G2", "gamerTag": "Bob", "twitter": "bob"})
        == "G2 Bob"
    )

    saved = {(p.get("prefix"), p.get("gamerTag")): p for p in SavedPlayers()}
    assert ("G2", "Bob") in saved and ("TSM", "Bob") not in saved
    assert saved[("G2", "Bob")]["twitter"] == "bob"
    # Imported seeds aren't saved with the players
    assert "seed" not in saved[("G2", "Bob")]

    PlayerDB.DeletePlayers(["Alice", "Eve", "Nobody"])
    assert list(PlayerDB.database.keys()) == ["G2 Bob"]
    assert len(SavedPlayers()) == 1


def TestSeeds():
    PlayerDB.database = {}
    PlayerDB.AddPlayers([{"prefix": "", "gamerTag": "Alice", "seed": 7}])
    SeedManager.overrides = {}
    SeedManager.event = ""

    changed = []
    SeedManager.signals.seed_changed.connect(changed.append)

    assert SeedManager.GetSeed("Alice") == 7
    assert SeedManager.GetSeed("Nobody") is None

    SeedManager.SetSeed("Alice", 2)
    SeedManager.SetSeed("Manual", 5)
    assert SeedManager.GetSeed("Alice") == 2
    assert SeedManager.GetSeed("Manual") == 5
    assert changed[-2:] == ["Alice", "Manual"]

    # Saved and loaded back
    SeedManager.overrides = {}
    SeedManager.Load()
    assert SeedManager.overrides == {"Alice": 2, "Manual": 5}

    # 0 is "no seed", not "use the imported one"
    SeedManager.SetSeed("Alice", 0)
    assert SeedManager.GetSeed("Alice") == 0
    SeedManager.ResetSeed("Alice")
    assert SeedManager.GetSeed("Alice") == 7

    SeedManager.RenamePlayer("Manual", "Renamed")
    assert SeedManager.GetSeed("Renamed") == 5 and SeedManager.GetOverride("Manual") is None

    # Unsetting the event keeps them, loading an event drops the ones made
    # without one
    SeedManager.EventLoaded(None)
    assert SeedManager.GetSeed("Renamed") == 5
    SeedManager.EventLoaded("https://www.start.gg/tournament/a/event/b")
    assert SeedManager.overrides == {}
    SeedManager.SetSeed("Alice", 1)
    # Reloading the same event keeps them, another event drops them
    SeedManager.EventLoaded("https://www.start.gg/tournament/a/event/b")
    assert SeedManager.GetSeed("Alice") == 1
    SeedManager.EventLoaded("https://www.start.gg/tournament/a/event/c")
    assert SeedManager.GetSeed("Alice") == 7
    assert changed[-1] == ""

    SeedManager.SetSeed("Alice", 3)
    SeedManager.ClearAll()
    assert SeedManager.overrides == {} and SeedManager.GetSeed("Alice") == 7


if __name__ == "__main__":
    try:
        TestMigrateFromJSON()
        TestReloadAfterExternalEdit()
        TestUpdatePlayer()
        TestSeeds()
    finally:
        os.chdir(repoDir)
    print("OK")
