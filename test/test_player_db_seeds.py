# Checks editing the player database (renames, duplicate tags, deletes) and
# the seeds set by hand in TSHSeedManager.
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

from src.Helpers.TSHQtHelper import init_gui_executor

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
assetModule = types.ModuleType("src.TSHGameAssetManager")
assetModule.TSHGameAssetManager = FakeAssetManager
sys.modules["src.TSHGameAssetManager"] = assetModule

# Files are written to ./user_data, so work in a scratch directory
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
repoDir = os.path.abspath(".")
os.chdir(workDir)

from src.TSHPlayerDB import TSHPlayerDB
from src.TSHSeedManager import TSHSeedManager


def SavedPlayers():
    return list(TSHPlayerDB.ReadDB().values())


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
    TSHPlayerDB.database = {}
    TSHPlayerDB.LoadDB()

    assert set(TSHPlayerDB.database) == {"TSM Bob", "Alice", "Carol"}
    assert TSHPlayerDB.database["Carol"]["mains"] == {"ssbu": [["Peach", 1]]}
    # Unset fields stay missing, so .get() defaults still work
    assert "mains" not in TSHPlayerDB.database["Alice"]
    assert len(SavedPlayers()) == 3
    # The JSON file is kept as a backup and not imported again
    assert not os.path.exists("./user_data/local_players.json")
    assert os.path.exists("./user_data/local_players.json.bak")
    TSHPlayerDB.database = {}
    TSHPlayerDB.LoadDB()
    assert len(TSHPlayerDB.database) == 3

    # Export and import
    TSHPlayerDB.ExportJSON("./export.json")
    with open("./export.json", "rb") as f:
        exported = orjson.loads(f.read())
    assert {p["gamerTag"] for p in exported} == {"Bob", "Alice", "Carol"}
    TSHPlayerDB.DeletePlayers(["Alice", "Carol"])
    assert len(SavedPlayers()) == 1
    assert TSHPlayerDB.ImportJSON("./export.json") == 3
    assert set(TSHPlayerDB.database) == {"TSM Bob", "Alice", "Carol"}
    assert TSHPlayerDB.database["Alice"]["twitter"] == "alice"


def TestReloadAfterExternalEdit():
    from sqlmodel import Session, select

    from src.TSHPlayerDBModels import GetEngine, Player

    TSHPlayerDB.database = {}
    TSHPlayerDB.DeletePlayers([])
    TSHPlayerDB.AddPlayers(
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

    TSHPlayerDB.ReloadDB()
    assert set(TSHPlayerDB.database) == {"C9 Dan", "Finn"}
    assert TSHPlayerDB.database["C9 Dan"]["name"] == "Dan D"
    assert TSHPlayerDB.database["Finn"]["twitter"] == "finn"

    # Fields that aren't saved survive a reload of the same player
    TSHPlayerDB.AddPlayers([{"prefix": "C9", "gamerTag": "Dan", "seed": 9}])
    with Session(GetEngine()) as session:
        dan = session.exec(select(Player).where(Player.tag == "C9 Dan")).one()
        dan.twitter = "dan"
        session.add(dan)
        session.commit()
    TSHPlayerDB.ReloadDB()
    assert TSHPlayerDB.database["C9 Dan"]["twitter"] == "dan"
    assert TSHPlayerDB.database["C9 Dan"]["seed"] == 9


def TestUpdatePlayer():
    TSHPlayerDB.database = {}
    TSHPlayerDB.AddPlayers(
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
        TSHPlayerDB.UpdatePlayer(None, {"prefix": " ", "gamerTag": " Eve ", "name": "Eve E"})
        == "Eve"
    )
    assert TSHPlayerDB.database["Eve"]["gamerTag"] == "Eve"

    # Empty tags and tags of other players are refused
    assert TSHPlayerDB.UpdatePlayer(None, {"prefix": "", "gamerTag": ""}) is None
    assert TSHPlayerDB.UpdatePlayer("Eve", {"prefix": "", "gamerTag": "Alice"}) is None
    assert "Eve" in TSHPlayerDB.database

    # Renaming keeps what the editor doesn't show, and drops the old entry
    newTag = TSHPlayerDB.UpdatePlayer(
        "TSM Bob", {"prefix": "G2", "gamerTag": "Bob", "name": "Bobby"}
    )
    assert newTag == "G2 Bob"
    assert "TSM Bob" not in TSHPlayerDB.database
    bob = TSHPlayerDB.database["G2 Bob"]
    assert bob["name"] == "Bobby"
    assert bob["mains"] == {"ssbu": [["Link", 0, ""]]}
    assert bob["seed"] == 4

    # Saving under the same tag works too
    assert (
        TSHPlayerDB.UpdatePlayer("G2 Bob", {"prefix": "G2", "gamerTag": "Bob", "twitter": "bob"})
        == "G2 Bob"
    )

    saved = {(p.get("prefix"), p.get("gamerTag")): p for p in SavedPlayers()}
    assert ("G2", "Bob") in saved and ("TSM", "Bob") not in saved
    assert saved[("G2", "Bob")]["twitter"] == "bob"
    # Imported seeds aren't saved with the players
    assert "seed" not in saved[("G2", "Bob")]

    TSHPlayerDB.DeletePlayers(["Alice", "Eve", "Nobody"])
    assert list(TSHPlayerDB.database.keys()) == ["G2 Bob"]
    assert len(SavedPlayers()) == 1


def TestSeeds():
    TSHPlayerDB.database = {}
    TSHPlayerDB.AddPlayers([{"prefix": "", "gamerTag": "Alice", "seed": 7}])
    TSHSeedManager.overrides = {}
    TSHSeedManager.event = ""

    changed = []
    TSHSeedManager.signals.seed_changed.connect(changed.append)

    assert TSHSeedManager.GetSeed("Alice") == 7
    assert TSHSeedManager.GetSeed("Nobody") is None

    TSHSeedManager.SetSeed("Alice", 2)
    TSHSeedManager.SetSeed("Manual", 5)
    assert TSHSeedManager.GetSeed("Alice") == 2
    assert TSHSeedManager.GetSeed("Manual") == 5
    assert changed[-2:] == ["Alice", "Manual"]

    # Saved and loaded back
    TSHSeedManager.overrides = {}
    TSHSeedManager.Load()
    assert TSHSeedManager.overrides == {"Alice": 2, "Manual": 5}

    # 0 is "no seed", not "use the imported one"
    TSHSeedManager.SetSeed("Alice", 0)
    assert TSHSeedManager.GetSeed("Alice") == 0
    TSHSeedManager.ResetSeed("Alice")
    assert TSHSeedManager.GetSeed("Alice") == 7

    TSHSeedManager.RenamePlayer("Manual", "Renamed")
    assert TSHSeedManager.GetSeed("Renamed") == 5 and TSHSeedManager.GetOverride("Manual") is None

    # Unsetting the event keeps them, loading an event drops the ones made
    # without one
    TSHSeedManager.EventLoaded(None)
    assert TSHSeedManager.GetSeed("Renamed") == 5
    TSHSeedManager.EventLoaded("https://www.start.gg/tournament/a/event/b")
    assert TSHSeedManager.overrides == {}
    TSHSeedManager.SetSeed("Alice", 1)
    # Reloading the same event keeps them, another event drops them
    TSHSeedManager.EventLoaded("https://www.start.gg/tournament/a/event/b")
    assert TSHSeedManager.GetSeed("Alice") == 1
    TSHSeedManager.EventLoaded("https://www.start.gg/tournament/a/event/c")
    assert TSHSeedManager.GetSeed("Alice") == 7
    assert changed[-1] == ""

    TSHSeedManager.SetSeed("Alice", 3)
    TSHSeedManager.ClearAll()
    assert TSHSeedManager.overrides == {} and TSHSeedManager.GetSeed("Alice") == 7


if __name__ == "__main__":
    try:
        TestMigrateFromJSON()
        TestReloadAfterExternalEdit()
        TestUpdatePlayer()
        TestSeeds()
    finally:
        os.chdir(repoDir)
    print("OK")
