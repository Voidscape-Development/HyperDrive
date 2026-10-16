# Checks the asset downloader: its download queue (base files first, one job
# at a time, cancel, retry, failures, reloading the games once at the end)
# and its window (selection with base files added, filters, search, the
# review of updates and the offline view). Downloads are faked.
# Run from the repository root: python test/test_asset_downloader.py
import os
import sys
import threading
import time
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda *args, **kwargs: None
SettingsManager.settings = {}

from src.Helpers import QtHelper

QtHelper.init_gui_executor()


# The real GameAssetManager loads every game from disk: a stand-in holding
# what's "installed"
class GameSignals(QObject):
    onLoadAssets = Signal()


class GameAssetManager:
    instance = None


fakeModule = types.ModuleType("src.GameAssetManager")
fakeModule.GameAssetManager = GameAssetManager
sys.modules["src.GameAssetManager"] = fakeModule

loads = []


def LoadGames():
    loads.append(True)
    GameAssetManager.instance.signals.onLoadAssets.emit()


GameAssetManager.instance = types.SimpleNamespace(
    games={}, signals=GameSignals(), LoadGames=LoadGames
)

from src.AssetDownloader import (
    JOB_CANCELLED,
    JOB_DONE,
    JOB_FAILED,
    AssetDownloader,
)
from src.Helpers import AssetCatalog


def Pack(name, version="2", size=1000):
    return {
        "name": name,
        "version": version,
        "files": {f"{name}.7z.001": {"name": f"{name}.7z.001", "size": size}},
    }


CATALOG = {
    "ssbu": {
        "name": "Super Smash Bros. Ultimate",
        "assets": {
            "base_files": Pack("Ultimate"),
            "portrait": Pack("Portraits"),
            "webm": Pack("Webms"),
        },
    },
    "ggst": {
        "name": "Guilty Gear -STRIVE-",
        "assets": {"base_files": Pack("Guilty Gear"), "chibi": Pack("Chibi characters")},
    },
}


def Installed():
    return {
        "ssbu": {
            "name": "Super Smash Bros. Ultimate",
            "assets": {
                "base_files": {"version": "2", "name": "Super Smash Bros. Ultimate"},
                "portrait": {"version": "1", "name": "Portraits"},
            },
        }
    }


installs = []
# Packs whose install fails, and a gate that holds installs until opened
failing = set()
gate = threading.Event()


def FakeInstall(game, pack, files, progress, cancelled, onUnpack=None, gamesDir=None):
    total = sum(f["size"] for f in files)
    progress(total // 2, total)
    while not gate.wait(0.01):
        if cancelled():
            return False
    if cancelled():
        return False
    if (game, pack) in failing:
        raise OSError("disk full")
    if onUnpack:
        onUnpack()
    installs.append((game, pack))
    progress(total, total)
    return True


AssetCatalog.InstallPack = FakeInstall
logoLoads = []
logoGate = threading.Event()
logoGate.set()


def FakeLoadLogo(game):
    # Never the real cache folder or network
    logoLoads.append(game)
    logoGate.wait(5)
    return b"png:" + game.encode()


AssetCatalog.LoadLogo = FakeLoadLogo
AssetCatalog.FreeSpace = lambda gamesDir=None: 50 * 1024**3
fetches = []


def FakeFetch():
    fetches.append(True)
    return CATALOG


AssetCatalog.FetchCatalog = FakeFetch


def WaitFor(condition, timeout=5):
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, "timed out"
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()


def NewDownloader():
    GameAssetManager.instance.games = Installed()
    downloader = AssetDownloader()
    AssetDownloader.instance = downloader
    downloader.UiMounted()
    del installs[:], loads[:], fetches[:]
    failing.clear()
    gate.clear()
    return downloader


def TestCatalogAndUpdates():
    downloader = NewDownloader()
    updates = []
    downloader.signals.AssetUpdates.connect(updates.append)
    downloader.CheckAssetUpdates()
    WaitFor(lambda: updates)
    assert list(updates[-1]) == ["ssbu"] and updates[-1]["ssbu"][0]["name"] == "Portraits"
    # Fresh: no second fetch, the updates are sent again
    downloader.CheckAssetUpdates()
    WaitFor(lambda: len(updates) == 2)
    assert len(fetches) == 1
    downloader.LoadCatalog(force=True)
    WaitFor(lambda: len(fetches) == 2 and not downloader.catalogLoading)


def TestQueueAddsBaseFilesFirst():
    downloader = NewDownloader()
    downloader.catalog = CATALOG
    downloader.Enqueue([("ggst", "chibi"), ("ssbu", "webm")])
    assert [(j.game, j.pack) for j in downloader.jobs] == [
        ("ggst", "base_files"),
        ("ggst", "chibi"),
        ("ssbu", "webm"),
    ]
    assert downloader.jobs[0].packName == "Base files"
    # Queuing what's already queued adds nothing
    downloader.Enqueue([("ggst", "chibi")])
    assert len(downloader.jobs) == 3

    WaitFor(lambda: downloader.jobs[0].done > 0)
    # One at a time
    assert downloader.runningJob is downloader.jobs[0]
    assert all(j.done == 0 for j in downloader.jobs[1:])
    gate.set()
    WaitFor(lambda: all(j.state == JOB_DONE for j in downloader.jobs) and loads)
    assert installs == [("ggst", "base_files"), ("ggst", "chibi"), ("ssbu", "webm")]
    # The games are loaded again once, when the queue is done
    assert len(loads) == 1
    assert downloader.JustInstalled("ggst", "chibi")
    downloader.ClearFinished()
    assert downloader.jobs == []


def TestCancelRetryAndFailure():
    downloader = NewDownloader()
    downloader.catalog = CATALOG
    downloader.Enqueue([("ssbu", "webm"), ("ggst", "chibi")])
    base, webm, chibi = downloader.jobs
    assert (base.pack, webm.pack, chibi.pack) == ("base_files", "webm", "chibi")
    WaitFor(lambda: base.done > 0)
    downloader.Cancel(chibi)
    assert chibi.state == JOB_CANCELLED
    downloader.Cancel(base)
    WaitFor(lambda: base.state == JOB_CANCELLED)
    # The next one starts
    WaitFor(lambda: downloader.runningJob is webm)

    failing.add(("ssbu", "webm"))
    gate.set()
    WaitFor(lambda: webm.state == JOB_FAILED and downloader.runningJob is None)
    assert "disk full" in webm.error
    # Nothing was installed: the games aren't loaded again
    assert loads == []

    failing.clear()
    downloader.Retry(webm)
    WaitFor(lambda: webm.state == JOB_DONE and loads)
    assert installs == [("ssbu", "webm")]
    assert downloader.jobs[-1] is webm


def TestLogosLoadOnce():
    downloader = NewDownloader()
    del logoLoads[:]
    calls = []
    logoGate.clear()
    # Asked for three times while it loads: loaded once, everyone answered
    for _ in range(3):
        downloader.RequestLogo("ssbu", lambda game, data: calls.append((game, data)))
    downloader.RequestLogo("ggst", lambda game, data: calls.append((game, data)))
    logoGate.set()
    WaitFor(lambda: len(calls) == 4)
    assert sorted(logoLoads) == ["ggst", "ssbu"]
    assert calls.count(("ssbu", b"png:ssbu")) == 3
    # Loaded: answered straight away
    downloader.RequestLogo("ssbu", lambda game, data: calls.append((game, data)))
    assert len(calls) == 5 and sorted(logoLoads) == ["ggst", "ssbu"]
    assert downloader.logoWaiters == {}


def TestCancelAllOnQuit():
    downloader = NewDownloader()
    downloader.catalog = CATALOG
    downloader.Enqueue([("ssbu", "webm")])
    WaitFor(lambda: downloader.jobs[0].done > 0)
    app.aboutToQuit.emit()
    WaitFor(lambda: downloader.jobs[0].state == JOB_CANCELLED)


def TestWindow():
    from src.AssetDownloaderWindow import (
        FILTER_INSTALLED,
        FILTER_UPDATES,
        AssetDownloaderWindow,
        UpdatesDialog,
    )

    downloader = NewDownloader()
    downloader.LoadCatalog()
    WaitFor(lambda: downloader.catalog is not None)
    window = AssetDownloaderWindow()
    assert set(window.gameItems) == {"ssbu", "ggst"}
    assert window.updates == [("ssbu", "portrait")]
    assert not window.reviewButton.isHidden()

    # A pack of a game without base files brings them along
    window.SelectGame("ggst")
    assert set(window.packRows) == {"base_files", "chibi"}
    window.packRows["chibi"].check.setChecked(True)
    assert window.IsAutoBase("ggst", "base_files")
    assert window.packRows["base_files"].check.isChecked()
    assert not window.packRows["base_files"].check.isEnabled()
    assert window.SelectedPacks() == [("ggst", "base_files"), ("ggst", "chibi")]
    assert window.downloadButton.isEnabled()
    assert "+ base files" in window.selectionLabel.text()
    window.packRows["chibi"].check.setChecked(False)
    assert window.SelectedPacks() == []
    assert not window.downloadButton.isEnabled()

    # Installed packs can't be picked; one with an update can
    window.SelectGame("ssbu")
    assert window.packRows["base_files"].check.isHidden()
    assert not window.packRows["portrait"].updateButton.isHidden()
    assert window.packRows["webm"].check.isEnabled()

    # Filters and search
    window.SetFilter(FILTER_INSTALLED)
    assert window.gameItems["ggst"].isHidden() and not window.gameItems["ssbu"].isHidden()
    window.SetFilter(FILTER_UPDATES)
    assert window.gameItems["ggst"].isHidden()
    window.filterButtons["all"].click()
    window.search.setText("chibi")
    assert window.gameItems["ssbu"].isHidden() and window.currentGame == "ggst"
    assert set(window.packRows) == {"chibi"}
    window.search.setText("smash ultimate")
    assert window.currentGame == "ssbu" and len(window.packRows) == 3
    window.search.setText("nothing like this")
    assert window.currentGame is None and not window.emptyLabel.isHidden()
    window.search.setText("")

    # Review updates lists what "update all" would download
    dialog = UpdatesDialog(window, window.updates)
    assert dialog.Selected() == [("ssbu", "portrait")]
    dialog.checks[0][0].setChecked(False)
    assert dialog.Selected() == [] and not dialog.okButton.isEnabled()

    # Downloading: the rows and the panel follow the queue
    window.SelectGame("ggst")
    window.packRows["chibi"].check.setChecked(True)
    window.downloadButton.click()
    assert window.selection == {} and len(downloader.jobs) == 2
    assert not window.downloadsPanel.isHidden()
    assert len(window.downloadsPanel.rows) == 2
    assert window.packRows["chibi"].check.isHidden()
    gate.set()
    WaitFor(lambda: all(j.state == JOB_DONE for j in downloader.jobs) and loads)
    assert window.PackState("ggst", "chibi") == AssetCatalog.STATE_INSTALLED

    # Offline: what's installed, nothing to download
    downloader.catalog = None
    downloader.catalogError = "no connection"
    downloader.signals.catalogChanged.emit()
    assert window.offline and not window.banner.isHidden()
    assert set(window.gameItems) == {"ssbu"}
    assert window.packRows["portrait"].check.isHidden()
    assert not window.downloadButton.isEnabled()
    assert window.filterButtons[FILTER_UPDATES].isHidden()
    window.close()


try:
    for test in (
        TestCatalogAndUpdates,
        TestQueueAddsBaseFilesFirst,
        TestCancelRetryAndFailure,
        TestLogosLoadOnce,
        TestCancelAllOnQuit,
        TestWindow,
    ):
        test()
        print(f"{test.__name__}: OK")
finally:
    # A failed check mustn't leave a fake download waiting, or exiting hangs
    gate.set()
    logoGate.set()
