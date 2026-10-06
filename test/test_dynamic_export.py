# Checks DynamicExport: a person's files in user_data/custom_player_export/
# are exported to <path>.custom, matched by tag then sponsor and tag, kept up
# to date as they change, and cleared when the setting is off.
# Run from the repository root: python test/test_dynamic_export.py
import os
import sys
import tempfile
import time
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

# The export reads ./user_data, and SettingsManager writes its settings there
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data/custom_player_export")

from src.Helpers.DynamicExport import DynamicExport
from src.SettingsManager import SettingsManager
from src.StateManager import StateManager

BASE = DynamicExport.BASE_DIR
PATH = "score.1.team.1.player.1"


def Write(folder, name, content, mode="w"):
    os.makedirs(f"{BASE}/{folder}", exist_ok=True)
    with open(f"{BASE}/{folder}/{name}", mode) as f:
        f.write(content)
    # Some file systems keep mtimes in seconds; make sure a change shows
    t = time.time() + Write.bump
    Write.bump += 2
    os.utime(f"{BASE}/{folder}/{name}", (t, t))


Write.bump = 2


def Custom(path=PATH):
    return StateManager.Get(f"{path}.custom")


def Export(name, team="", path=PATH):
    # The widgets set other keys first, so the player's path exists
    StateManager.Set(f"{path}.name", name)
    DynamicExport.ExportCustomPlayerData(name, team, path)


def TestValues():
    Write("Azure", "bio.txt", "Plays since 2014.\n")
    Write("Azure", "stats.json", '{"wins": 12, "mains": ["mario"]}')
    Write("Azure", "notes.md", "# Notes\n")
    Write("Azure", "broken.json", "{not json")
    Write("Azure", "card.png", b"\x89PNG", mode="wb")
    Write("Azure", "twitter.handle.txt", "@azure")
    Write("Azure", "desktop.ini", "[.ShellClassInfo]")
    Write("Azure", ".hidden.txt", "x")

    Export("azure")
    assert Custom() == {
        "bio": "Plays since 2014.",
        "stats": {"wins": 12, "mains": ["mario"]},
        "notes": "# Notes\n",
        "broken": "{not json",
        "card": f"{BASE}/Azure/card.png",
        "twitter_handle": "@azure",
    }, Custom()
    # Doesn't touch the player's own keys
    assert StateManager.Get(f"{PATH}.name") == "azure"


def TestMatching():
    Write("HD Crimson", "bio.txt", "sponsored")
    Export("Crimson", "HD", path="commentary.1")
    assert Custom("commentary.1") == {"bio": "sponsored"}

    # The tag's own folder wins over the sponsor and tag one
    Write("Crimson", "bio.txt", "tag only")
    Export("Crimson", "HD", path="commentary.1")
    assert Custom("commentary.1") == {"bio": "tag only"}

    # Nobody's folder: cleared
    Export("Nobody", "HD", path="commentary.1")
    assert Custom("commentary.1") is None
    Export("", "", path="commentary.1")
    assert Custom("commentary.1") is None


def TestRefresh():
    Export("azure")
    Write("Azure", "bio.txt", "Edited.")
    os.remove(f"{BASE}/Azure/notes.md")
    DynamicExport.Refresh()
    assert Custom()["bio"] == "Edited."
    assert "notes" not in Custom()

    # A folder made after the player was loaded is found
    Export("Violet", path="score.1.team.2.player.1")
    assert Custom("score.1.team.2.player.1") is None
    Write("violet", "bio.txt", "new")
    DynamicExport.Refresh()
    assert Custom("score.1.team.2.player.1") == {"bio": "new"}

    # A removed player is forgotten, and not brought back
    StateManager.Unset("score.1.team.2.player.1")
    Write("violet", "bio.txt", "newer")
    DynamicExport.Refresh()
    assert StateManager.Get("score.1.team.2.player.1") is None
    assert "score.1.team.2.player.1" not in DynamicExport._people


def TestSetting():
    Export("azure")
    SettingsManager.Set(DynamicExport.SETTING, False)
    DynamicExport.Refresh(force=True)
    assert Custom() is None
    SettingsManager.Set(DynamicExport.SETTING, True)
    DynamicExport.Refresh(force=True)
    assert Custom()["bio"] == "Edited."


if __name__ == "__main__":
    for test in [TestValues, TestMatching, TestRefresh, TestSetting]:
        test()
        print(f"{test.__name__}: OK")
