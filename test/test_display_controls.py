# Checks Display Controls: the layout folders found, group names, showing,
# hiding and toggling folders and groups, saving, and the web actions.
# Run from the repository root: python test/test_display_controls.py
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None

from src.StateManager import StateManager

StateManager.Set = lambda key, value: StateManager.state.__setitem__(key, value)

from src.Helpers.DisplayControlsHelper import (
    IsVisible,
    LayoutFolders,
    MatchFolder,
    NormalizeAction,
    NormalizeGroupName,
    Resolve,
)


def MakeLayouts(root):
    for path in (
        "scoreboard/ssbultimate.html",
        "scoreboard - MTF/fgc.html",
        "commentators/tag.html",
        "include/globals.js",
        "include/page.html",
        "deprecated/README.txt",
        "deprecated/player_list/index.html",
        "empty/index.css",
    ):
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").close()


def TestHelper():
    assert NormalizeGroupName("  Main   Stage ") == "main stage"
    assert NormalizeGroupName("a,b") == "a b"
    assert NormalizeGroupName(None) == ""
    assert len(NormalizeGroupName("x" * 100)) == 40
    assert NormalizeAction("SHOW") == "show"
    assert NormalizeAction("nope") is None
    assert Resolve("show", False) is True
    assert Resolve("hide", True) is False
    assert Resolve("toggle", True) is False
    assert Resolve("toggle", False) is True

    with tempfile.TemporaryDirectory() as root:
        MakeLayouts(root)
        folders = LayoutFolders(root)
        assert folders == ["commentators", "player_list", "scoreboard", "scoreboard - MTF"], folders
        assert MatchFolder("Scoreboard", folders) == "scoreboard"
        assert MatchFolder("scoreboard - mtf", folders) == "scoreboard - MTF"
        assert MatchFolder("nope", folders) is None
    assert LayoutFolders("/does/not/exist") == []

    state = {"folders": {"scoreboard": False, "bracket": True}, "groups": {"main": False}}
    assert not IsVisible(state, "scoreboard")
    assert IsVisible(state, "bracket")
    assert not IsVisible(state, "bracket", ["Main"])
    assert IsVisible(state, "bracket", ["other"])
    assert IsVisible({}, "anything", ["main"])
    print("TestHelper: OK")


def TestManager():
    from src.DisplayControls import DisplayControls

    with tempfile.TemporaryDirectory() as root:
        MakeLayouts(root)
        SettingsManager.settings = {}
        changes = []
        DisplayControls.signals.changed.connect(lambda: changes.append(1))

        controls = DisplayControls(root)
        state = StateManager.state["display"]
        assert all(state["folders"].values())
        assert state["groups"] == {}

        assert controls.Set("folder", "SCOREBOARD", "hide") == {
            "kind": "folder",
            "name": "scoreboard",
            "shown": False,
        }
        assert StateManager.state["display"]["folders"]["scoreboard"] is False
        assert SettingsManager.Get("display_controls.folders") == {"scoreboard": False}
        assert controls.Set("folder", "scoreboard", "toggle")["shown"] is True
        assert SettingsManager.Get("display_controls.folders") == {}
        assert controls.Set("folder", "nope", "hide") == {"error": "NO_FOLDER"}
        assert controls.Set("folder", "scoreboard", "explode") == {"error": "UNKNOWN_ACTION"}
        assert controls.Set("thing", "scoreboard", "hide") == {"error": "UNKNOWN_KIND"}

        # Groups are added the first time they're used
        assert controls.Get("group", "Main") == {"error": "NO_GROUP"}
        assert controls.Set("group", "Main", "hide")["shown"] is False
        assert controls.Get("group", "main")["shown"] is False
        controls.AddGroups(["main", "Top 8", "", None])
        assert StateManager.state["display"]["groups"] == {"main": False, "top 8": True}

        assert not controls.AllShown()
        assert controls.SetAll("toggle")["shown"] is True
        assert controls.AllShown()
        assert controls.SetAll("toggle")["shown"] is False
        state = StateManager.state["display"]
        assert not any(state["folders"].values()) and not any(state["groups"].values())
        controls.SetAll("show")

        controls.Set("folder", "commentators", "hide")
        controls.Set("group", "top 8", "hide")
        controls.RemoveGroup("MAIN")
        assert "main" not in StateManager.state["display"]["groups"]

        # Saved: a new instance starts where this one was
        again = DisplayControls(root)
        assert again.State() == controls.State()
        assert again.Get("folder", "commentators")["shown"] is False
        assert again.Get("group", "top 8")["shown"] is False

        # A new layout folder starts out shown
        MakeLayouts(os.path.join(root, "new_layout"))
        os.makedirs(os.path.join(root, "bracket"))
        open(os.path.join(root, "bracket", "index.html"), "w").close()
        again.RefreshFolders()
        assert again.State()["folders"]["bracket"] is True

        assert changes
    print("TestManager: OK")


def TestActions():
    from src.DisplayControls import DisplayControls
    from src.Helpers import QtHelper

    # Runs the actions here instead of on the GUI thread
    class Executor:
        def run_sync(self, fn):
            return fn()

    QtHelper.gui_executor = Executor()
    from src.WebServerActions import WebServerActions

    with tempfile.TemporaryDirectory() as root:
        MakeLayouts(root)
        SettingsManager.settings = {}
        DisplayControls(root)
        actions = WebServerActions.__new__(WebServerActions)

        assert actions.display("folder", "scoreboard", "hide")["shown"] is False
        assert actions.display("folder", "scoreboard")["shown"] is False
        assert actions.display("folder", "nope", "hide") == ("NO_FOLDER", 404)
        assert actions.display("folder", "scoreboard", "nope") == ("UNKNOWN_ACTION", 400)
        assert actions.display("other", "scoreboard") == ("UNKNOWN_KIND", 400)
        assert actions.display("group", "nope") == ("NO_GROUP", 404)
        state = actions.display("all")
        assert state["shown"] is False and state["folders"]["scoreboard"] is False
        assert actions.display("all", None, "show") == {"kind": "all", "shown": True}
        actions.display_register(["Main"])
        actions.display_register("not a list")
        assert actions.display("group", "main")["shown"] is True
    print("TestActions: OK")


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    TestHelper()
    TestManager()
    TestActions()
