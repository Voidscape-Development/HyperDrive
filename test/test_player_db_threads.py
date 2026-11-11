# Checks the player database when several threads use it at once (entrants
# and mains are added from worker threads while the GUI thread shows them):
# - players added from threads while the model is rebuilt: nothing raises,
#   no player is lost, in memory or in the file
# - saves are written in the order their copies were taken
# - players are saved under the tag every lookup uses (MakeTag), whatever
#   spaces their prefix and tag come with
# - mains of several games: each game keeps its own
# Run from the repository root: python test/test_player_db_threads.py
import os
import sys
import tempfile
import threading
import time
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

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
        self.characters = {"mario": {}}
        self.selectedGame = {"codename": "ssbu"}


FakeAssetManager.instance = FakeAssetManager()
assetModule = types.ModuleType("src.GameAssetManager")
assetModule.GameAssetManager = FakeAssetManager
sys.modules["src.GameAssetManager"] = assetModule

# Files are written to ./user_data, so work in a scratch directory
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
os.chdir(workDir)

import src.PlayerDB as playerDBModule
from src.PlayerDB import PlayerDB
from src.SettingsManager import SettingsManager

SettingsManager.Get = staticmethod(lambda key, default=None: default)


def Reset():
    with PlayerDB.lock:
        PlayerDB.database.clear()
    PlayerDB.SaveDB()


def RunThreads(targets):
    """Runs the targets in threads, keeping the GUI thread's events going
    (the model is rebuilt on it). Returns what they raised."""
    errors = []

    def guarded(target):
        try:
            target()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=guarded, args=(t,)) for t in targets]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + 60
    while any(t.is_alive() for t in threads):
        app.processEvents()
        time.sleep(0.001)
        assert time.monotonic() < deadline, "the threads are stuck (deadlock?)"
    return errors


def TestAddingFromThreads():
    Reset()
    logged = []
    sink = playerDBModule.logger.add(lambda message: logged.append(str(message)), level="ERROR")

    def adder(thread):
        def run():
            for batch in range(8):
                PlayerDB.AddPlayers(
                    [
                        {"gamerTag": f"p{thread}_{batch}_{i}", "mains": {"ssbu": [["mario"]]}}
                        for i in range(25)
                    ]
                )

        return run

    def reader():
        # What the GUI thread and the web server do meanwhile
        for _ in range(200):
            PlayerDB.Snapshot()
            PlayerDB.GetPlayer("p0_0_0")
            PlayerDB.GetPlayerFromTag("p1_0_0")

    try:
        errors = RunThreads([adder(t) for t in range(4)] + [reader])
        # The GUI thread rebuilding the model on its own too
        PlayerDB.SetupModel()
    finally:
        playerDBModule.logger.remove(sink)

    assert not errors, errors
    assert not logged, logged[:3]
    assert len(PlayerDB.database) == 4 * 8 * 25, len(PlayerDB.database)
    # Every player reached the file, whichever thread saved last
    assert len(PlayerDB.ReadDB()) == 4 * 8 * 25, len(PlayerDB.ReadDB())
    assert PlayerDB.model.rowCount() == 4 * 8 * 25

    # The model has copies: changing a player there doesn't change the DB's
    from qtpy.QtCore import Qt

    shown = PlayerDB.model.item(0).data(Qt.ItemDataRole.UserRole)
    shown["gamerTag"] = "changed"
    assert PlayerDB.GetPlayer(PlayerDB.model.item(0).text())["gamerTag"] != "changed"


def TestSavesKeepTheirOrder():
    """A save that took its copy first is written first, however long its
    write takes: the file ends up with the newest players"""
    Reset()
    realWrite = PlayerDB.WriteDB
    written = []
    firstIsWriting = threading.Event()

    def slowWrite(players):
        first = not written
        written.append(sorted(players))
        if first:
            # The second save has all the time it needs to overtake this one
            firstIsWriting.set()
            time.sleep(0.3)
        realWrite(players)

    PlayerDB.WriteDB = staticmethod(slowWrite)
    try:
        with PlayerDB.lock:
            PlayerDB.database["A"] = {"gamerTag": "A"}

        def second():
            firstIsWriting.wait(5)
            with PlayerDB.lock:
                PlayerDB.database["B"] = {"gamerTag": "B"}
            PlayerDB.SaveDB()

        errors = RunThreads([PlayerDB.SaveDB, second])
    finally:
        PlayerDB.WriteDB = staticmethod(realWrite)

    assert not errors, errors
    assert written == [["A"], ["A", "B"]], written
    assert sorted(PlayerDB.ReadDB()) == ["A", "B"], sorted(PlayerDB.ReadDB())


def TestTags():
    Reset()
    # Spaces around the prefix or the tag don't make another player
    PlayerDB.AddPlayers([{"prefix": " TSM ", "gamerTag": " Tweek ", "name": "Gavin"}])
    assert list(PlayerDB.database) == ["TSM Tweek"], list(PlayerDB.database)
    assert PlayerDB.GetPlayer(PlayerDB.GetTag({"prefix": "TSM", "gamerTag": "Tweek"}))
    assert PlayerDB.HasPlayer("TSM Tweek")
    PlayerDB.AddPlayers([{"prefix": "TSM", "gamerTag": "Tweek", "pronoun": "he/him"}])
    assert list(PlayerDB.database) == ["TSM Tweek"], list(PlayerDB.database)
    assert PlayerDB.GetPlayer("TSM Tweek")["pronoun"] == "he/him"
    assert list(PlayerDB.ReadDB()) == ["TSM Tweek"]
    # The model shows them under the tag they're saved with
    assert PlayerDB.model.item(0).text() == "TSM Tweek"

    # No tag at all: not added (it couldn't be saved or looked up)
    PlayerDB.AddPlayers([{"prefix": None, "gamerTag": None}, {"gamerTag": " "}])
    assert list(PlayerDB.database) == ["TSM Tweek"], list(PlayerDB.database)


def TestMainsOfSeveralGames():
    Reset()
    PlayerDB.AddPlayers(
        [{"gamerTag": "Leo", "mains": {"ssbu": [["joker", 2]], "sf6": [["ken", 1]]}}]
    )
    # Mains from the provider come without skins: the saved ones are kept
    PlayerDB.AddPlayers(
        [{"gamerTag": "Leo", "mains": {"ssbu": [["joker"], ["byleth"]], "sf6": [["ken"]]}}]
    )
    mains = PlayerDB.GetPlayer("Leo")["mains"]
    # (the model adds an empty variant to the mains of the game loaded)
    assert [m[:2] for m in mains["ssbu"]] == [["joker", 2], ["byleth", 0]], mains
    # Each game has its own mains, not the ones of the games before it too
    assert mains["sf6"] == [["ken", 1]], mains

    # A game not in the update keeps what it had
    PlayerDB.AddPlayers([{"gamerTag": "Leo", "mains": {"sf6": [["ryu"]]}}])
    mains = PlayerDB.GetPlayer("Leo")["mains"]
    assert [m[:2] for m in mains["ssbu"]] == [["joker", 2], ["byleth", 0]], mains
    assert mains["sf6"] == [["ryu", 0]], mains


if __name__ == "__main__":
    TestAddingFromThreads()
    TestSavesKeepTheirOrder()
    TestTags()
    TestMainsOfSeveralGames()
    print("OK")
