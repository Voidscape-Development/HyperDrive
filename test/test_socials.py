# Checks players' socials (several platforms per player, Twitter kept in its
# own field too), saving them in the player DB, the socials button, and
# filling set data from the local DB (general.local_player_data).
# Run from the repository root: python test/test_socials.py
import os
import sqlite3
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [
    ("src", "src"),
    ("src.Helpers", "src/Helpers"),
    ("src.TournamentDataProvider", "src/TournamentDataProvider"),
]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication, QFormLayout, QGridLayout, QLineEdit, QWidget

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

# Loads the locale and country files from the repository
from src.TournamentDataProvider.StartGGDataProvider import StartGGDataProvider

# Files are written to ./user_data, so work in a scratch directory
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
repoDir = os.path.abspath(".")
os.chdir(workDir)

from src.Helpers import SocialsHelper
from src.PlayerDB import PlayerDB
from src.PlayerDBModels import GetEngine, ResetEngine
from src.SettingsManager import SettingsManager
from src.SocialsWidget import SocialsButton


def TestHelper():
    # start.gg returns the accounts in any order
    socials = SocialsHelper.FromStartGG(
        [
            {"type": "DISCORD", "externalUsername": "beast#1"},
            {"type": "TWITCH", "externalUsername": "beasttv"},
            {"type": "TWITTER", "externalUsername": "beast"},
            {"type": "MIXER", "externalUsername": "old"},
            {"type": "TWITTER", "externalUsername": "second"},
        ]
    )
    assert socials == {"twitter": "beast", "twitch": "beasttv", "discord": "beast#1"}
    assert list(socials) == ["twitter", "twitch", "discord"]

    # The twitter field wins, and emptying it removes the account
    player = {"twitter": "new", "socials": {"twitter": "old", "youtube": "yt"}}
    assert SocialsHelper.Normalize(player) == {
        "twitter": "new",
        "socials": {"twitter": "new", "youtube": "yt"},
    }
    player = {"twitter": "", "socials": {"twitter": "old", "youtube": "yt"}}
    assert SocialsHelper.Normalize(player)["socials"] == {"youtube": "yt"}
    # Only socials: twitter comes from them
    assert SocialsHelper.Normalize({"socials": {"twitter": "a"}})["twitter"] == "a"
    # Players without either are left alone
    assert SocialsHelper.Normalize({"gamerTag": "x"}) == {"gamerTag": "x"}

    assert SocialsHelper.Merge({"instagram": "i", "twitch": "a"}, {"twitch": "b"}) == {
        "twitch": "b",
        "instagram": "i",
    }
    assert SocialsHelper.URL("youtube", "@chan") == "https://youtube.com/@chan"
    assert SocialsHelper.URL("discord", "x") is None
    print("TestHelper: OK")


def TestAddColumnToOldDB():
    # A database made before the socials column
    ResetEngine()
    path = "./user_data/players.db"
    if os.path.exists(path):
        os.remove(path)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE players (id INTEGER PRIMARY KEY, tag VARCHAR UNIQUE, prefix VARCHAR,"
        ' "gamerTag" VARCHAR, name VARCHAR, twitter VARCHAR, country_code VARCHAR,'
        " state_code VARCHAR, mains JSON, pronoun VARCHAR, custom_textbox VARCHAR)"
    )
    connection.execute(
        "INSERT INTO players (tag, prefix, \"gamerTag\", twitter) VALUES ('Beast', '', 'Beast', 'beast')"
    )
    connection.commit()
    connection.close()

    GetEngine()
    players = PlayerDB.ReadDB()
    assert players["Beast"]["twitter"] == "beast"
    assert players["Beast"]["socials"] == {"twitter": "beast"}
    print("TestAddColumnToOldDB: OK")


def TestSaveAndMerge():
    PlayerDB.database = {}
    PlayerDB.AddPlayers(
        [{"gamerTag": "Beast", "twitter": "beast", "socials": {"instagram": "beast.ig"}}],
        overwrite=True,
    )
    saved = PlayerDB.ReadDB()["Beast"]
    assert saved["socials"] == {"twitter": "beast", "instagram": "beast.ig"}, saved

    # start.gg data adds Twitch and changes Twitter, the Instagram typed in
    # by hand stays
    PlayerDB.AddPlayers(
        [
            {
                "gamerTag": "Beast",
                "twitter": "beast2",
                "socials": {"twitter": "beast2", "twitch": "beasttv"},
            }
        ]
    )
    saved = PlayerDB.ReadDB()["Beast"]
    assert saved["twitter"] == "beast2"
    assert saved["socials"] == {
        "twitter": "beast2",
        "twitch": "beasttv",
        "instagram": "beast.ig",
    }, saved

    # A mains-only update leaves them alone
    PlayerDB.AddPlayers([{"gamerTag": "Beast", "mains": {}}])
    assert PlayerDB.ReadDB()["Beast"]["socials"]["twitch"] == "beasttv"

    # With disable_overwrite, the DB's values win but new platforms are added
    SettingsManager.Set("general.disable_overwrite", True)
    try:
        PlayerDB.AddPlayers(
            [{"gamerTag": "Beast", "socials": {"twitch": "other", "youtube": "yt"}}]
        )
    finally:
        SettingsManager.Unset("general.disable_overwrite")
    socials = PlayerDB.ReadDB()["Beast"]["socials"]
    assert socials["twitch"] == "beasttv" and socials["youtube"] == "yt", socials

    # The editor saves the whole set, removing one
    tag = PlayerDB.UpdatePlayer(
        "Beast", {"gamerTag": "Beast", "twitter": "beast2", "socials": {"twitter": "beast2"}}
    )
    assert tag == "Beast"
    assert PlayerDB.ReadDB()["Beast"]["socials"] == {"twitter": "beast2"}
    print("TestSaveAndMerge: OK")


def TestButton():
    # In a grid, like the player widgets' .ui
    parent = QWidget()
    grid = QGridLayout(parent)
    twitter = QLineEdit()
    twitter.setObjectName("twitter")
    grid.addWidget(twitter, 3, 1)
    button = SocialsButton.Attach(twitter)
    assert parent.findChild(QWidget, "socials") is button
    assert grid.itemAtPosition(3, 1).layout().indexOf(twitter) == 0

    changes = []
    button.changed.connect(lambda: changes.append(button.Socials()))
    twitter.setText("beast")
    twitter.editingFinished.emit()
    assert changes[-1] == {"twitter": "beast"}

    button.MergeOthers({"twitter": "ignored", "twitch": "beasttv"})
    button.MergeOthers({"youtube": "yt"})
    assert button.Socials() == {"twitter": "beast", "twitch": "beasttv", "youtube": "yt"}
    assert button.text() == "+2"
    button.Clear()
    assert button.Socials() == {"twitter": "beast"} and button.text() == "+"

    # In a form, like the player DB editor
    formParent = QWidget()
    form = QFormLayout(formParent)
    edit = QLineEdit()
    form.addRow("Twitter", edit)
    formButton = SocialsButton.Attach(edit)
    row, _ = form.getLayoutPosition(form.itemAt(0, QFormLayout.ItemRole.FieldRole).layout())
    assert row == 0 and formButton.parentWidget() is formParent
    print("TestButton: OK")


def Provider(profiles):
    provider = StartGGDataProvider.__new__(StartGGDataProvider)
    provider._profile_cache = {}
    provider._profileLock = __import__("threading").Lock()
    provider.asked = []

    def query(url, type=None, jsonParams=None, **kwargs):
        userId = jsonParams["variables"]["id"]
        provider.asked.append(userId)
        user = profiles.get(userId)
        return {"data": {"user": user}}

    provider.QueryRequests = query
    return provider


def TestFillFromLocalDB():
    PlayerDB.database = {}
    PlayerDB.AddPlayers(
        [
            {
                "gamerTag": "Known",
                "twitter": "known",
                "socials": {"twitch": "knowntv"},
                "pronoun": "they/them",
                "country_code": "US",
            }
        ]
    )
    provider = Provider(
        {
            7: {
                "id": 7,
                "genderPronoun": "she/her",
                "location": {"country": None, "state": None, "city": None},
                "authorizations": [{"type": "TWITTER", "externalUsername": "newbie"}],
            }
        }
    )

    # In the DB: nothing asked
    known = provider.FillFromLocalDB({"gamerTag": "Known", "id": [1, 5]})
    assert known["socials"] == {"twitter": "known", "twitch": "knowntv"}, known
    assert known["pronoun"] == "they/them" and known["country_code"] == "US"
    assert provider.asked == []

    # Not in it: looked up once, then saved
    new = provider.FillFromLocalDB({"gamerTag": "Newbie", "id": [2, 7]})
    assert new["twitter"] == "newbie" and new["pronoun"] == "she/her", new
    assert provider.asked == [7]
    assert PlayerDB.ReadDB()["Newbie"]["socials"] == {"twitter": "newbie"}
    provider.FillFromLocalDB({"gamerTag": "Newbie", "id": [2, 7]})
    assert provider.asked == [7]

    # No start.gg account: nothing to look up
    provider.FillFromLocalDB({"gamerTag": "Guest", "id": [3, 0]})
    assert provider.asked == [7]
    print("TestFillFromLocalDB: OK")


def TestParseSet():
    user = {
        "id": 9,
        "authorizations": [
            {"type": "TWITCH", "externalUsername": "beasttv"},
            {"type": "TWITTER", "externalUsername": "beast"},
        ],
    }
    data = StartGGDataProvider.ProcessEntrantData(
        {"player": {"id": 1, "gamerTag": "Beast"}, "user": user}
    )
    # The first account used to be taken as the Twitter, whatever it was
    assert data["twitter"] == "beast"
    assert data["socials"] == {"twitter": "beast", "twitch": "beasttv"}

    # Without the profile fields (local_player_data), none are set
    data = StartGGDataProvider.ProcessEntrantData(
        {"player": {"id": 1, "gamerTag": "Beast"}, "user": {"id": 9}}
    )
    assert "twitter" not in data and "socials" not in data
    print("TestParseSet: OK")


if __name__ == "__main__":
    try:
        TestHelper()
        TestAddColumnToOldDB()
        TestSaveAndMerge()
        TestButton()
        TestFillFromLocalDB()
        TestParseSet()
    finally:
        os.chdir(repoDir)
    print("OK")
