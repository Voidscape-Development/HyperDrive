# Checks AssetCatalog, behind the asset downloader: pack states and updates,
# search, sizes and dates, and installing a pack (a real 7z archive split in
# parts, served by a fake download) and removing it again. A cancelled or
# failed download must leave no files behind.
# Run from the repository root: python test/test_asset_catalog.py
import datetime
import os
import sys
import tempfile
import time
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

import py7zr
import requests

from src.Helpers import AssetCatalog
from src.Helpers.AssetCatalog import (
    BASE_FILES,
    DOWNLOADS_DIR,
    STATE_INSTALLED,
    STATE_NEW,
    STATE_UPDATE,
)

CATALOG = {
    "ssbu": {
        "name": "Super Smash Bros. Ultimate",
        "assets": {
            "portrait": {
                "name": "Portraits",
                "version": "26.07.31.1",
                "description": "Character select screen portraits",
                "files": {"ssbu.portrait.7z.001": {"name": "ssbu.portrait.7z.001", "size": 1000}},
            },
            "base_files": {
                "name": "Super Smash Bros. Ultimate",
                "version": "26.07.31.1",
                "description": "Base config to use this game.",
                "files": {"ssbu.base_files.7z.001": {"name": "ssbu.base_files.7z.001", "size": 10}},
            },
            "webm": {
                "name": "Webms",
                "version": "26.10.02.2",
                "description": "Vs Screen Webms",
                "files": {
                    "ssbu.webm.7z.002": {"name": "ssbu.webm.7z.002", "size": 2 * 1024**3},
                    "ssbu.webm.7z.001": {"name": "ssbu.webm.7z.001", "size": 1024**3},
                },
            },
        },
    },
    "ggst": {
        "name": "Guilty Gear -STRIVE-",
        "assets": {
            "base_files": {"name": "Guilty Gear -STRIVE-", "version": "1", "files": {}},
            "chibi": {"name": "Chibi characters", "version": "1", "files": {}},
        },
    },
}

INSTALLED = {
    "ssbu": {
        "assets": {
            "base_files": {"version": "26.07.31.1"},
            "portrait": {"version": "26.07.31.1"},
            "webm": {"version": "26.07.31.1"},
        }
    }
}


def TestStatesAndUpdates():
    assert AssetCatalog.Packs(CATALOG, "ssbu") == ["base_files", "portrait", "webm"]
    assert AssetCatalog.PackState(CATALOG, INSTALLED, "ssbu", "portrait") == STATE_INSTALLED
    assert AssetCatalog.PackState(CATALOG, INSTALLED, "ssbu", "webm") == STATE_UPDATE
    assert AssetCatalog.PackState(CATALOG, INSTALLED, "ggst", "chibi") == STATE_NEW
    assert AssetCatalog.Updates(CATALOG, INSTALLED) == [("ssbu", "webm")]
    assert AssetCatalog.HasBaseFiles(INSTALLED, "ssbu")
    assert not AssetCatalog.HasBaseFiles(INSTALLED, "ggst")
    assert AssetCatalog.InstalledPacks(CATALOG, INSTALLED, "ggst") == []
    assert AssetCatalog.PackSize(CATALOG, "ssbu", "webm") == 3 * 1024**3


def TestSearch():
    everything = AssetCatalog.Packs(CATALOG, "ssbu")
    assert AssetCatalog.MatchingPacks(CATALOG, "ssbu", "") == everything
    # The game's name matches: all its packs
    assert AssetCatalog.MatchingPacks(CATALOG, "ssbu", "  smash ULTIMATE ") == everything
    # A pack's name or description matches: only those packs
    assert AssetCatalog.MatchingPacks(CATALOG, "ssbu", "webm") == ["webm"]
    assert AssetCatalog.MatchingPacks(CATALOG, "ssbu", "select screen") == ["portrait"]
    assert AssetCatalog.MatchingPacks(CATALOG, "ggst", "webm") == []


def TestDisplay():
    assert AssetCatalog.FormatSize(0) == "0 KB"
    assert AssetCatalog.FormatSize(300) == "1 KB"
    assert AssetCatalog.FormatSize(512 * 1024) == "512 KB"
    assert AssetCatalog.FormatSize(int(22.6 * 1024**2)) == "22.6 MB"
    assert AssetCatalog.FormatSize(int(2.2 * 1024**3)) == "2.2 GB"
    assert AssetCatalog.VersionDate("26.10.02.40910") == datetime.date(2026, 10, 2)
    assert AssetCatalog.VersionDate("1") is None
    assert AssetCatalog.VersionDate("26.13.40.1") is None
    assert AssetCatalog.VersionDate(None) is None


def TestPackFiles():
    files = AssetCatalog.PackFiles(CATALOG, "ssbu", "webm")
    # Parts in order, whatever order the catalog lists them in
    assert [f["name"] for f in files] == ["ssbu.webm.7z.001", "ssbu.webm.7z.002"]
    assert files[0]["url"] == AssetCatalog.RELEASE_URL + "ssbu.webm.7z.001"


class FakeResponse:
    def __init__(self, data, chunks=3):
        self.data = data
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.data is None:
            raise requests.HTTPError("404 Not Found")

    def iter_content(self, chunk_size):
        step = max(1, len(self.data) // self.chunks)
        for i in range(0, len(self.data), step):
            yield self.data[i : i + step]


def MakeSplitArchive(root, pack, parts=2):
    """A 7z holding <pack>/config.json and a file, split like the releases are."""
    source = os.path.join(root, "source", pack)
    os.makedirs(source)
    with open(os.path.join(source, "config.json"), "w") as f:
        f.write('{"name": "Portraits", "version": "26.07.31.1"}')
    with open(os.path.join(source, "image.png"), "wb") as f:
        f.write(os.urandom(20000))
    archive = os.path.join(root, "pack.7z")
    with py7zr.SevenZipFile(archive, "w") as z:
        z.writeall(source, arcname=pack)
    data = open(archive, "rb").read()
    size = len(data) // parts + 1
    return [data[i : i + size] for i in range(0, len(data), size)]


def Files(parts, prefix="ssbu.portrait.7z"):
    return [
        {"name": f"{prefix}.{i + 1:03}", "size": len(p), "url": f"https://x/{prefix}.{i + 1:03}"}
        for i, p in enumerate(parts)
    ]


def TestInstallAndRemove():
    with tempfile.TemporaryDirectory() as root:
        gamesDir = os.path.join(root, "games")
        parts = MakeSplitArchive(root, "portrait")
        files = Files(parts)
        served = {f["url"]: p for f, p in zip(files, parts)}
        requests.get = lambda url, **kwargs: FakeResponse(served.get(url))

        progress = []
        unpacked = []
        ok = AssetCatalog.InstallPack(
            "ssbu",
            "portrait",
            files,
            lambda done, total: progress.append((done, total)),
            lambda: False,
            onUnpack=lambda: unpacked.append(True),
            gamesDir=gamesDir,
        )
        assert ok
        packDir = os.path.join(gamesDir, "ssbu", "portrait")
        assert os.path.isfile(os.path.join(packDir, "config.json"))
        assert os.path.getsize(os.path.join(packDir, "image.png")) == 20000
        total = sum(len(p) for p in parts)
        assert progress[-1] == (total, total)
        assert all(a[0] <= b[0] for a, b in zip(progress, progress[1:]))
        assert unpacked == [True]
        # Nothing left from the download
        assert not os.path.exists(os.path.join(gamesDir, DOWNLOADS_DIR))

        # Installing again (an update) works the same
        assert AssetCatalog.InstallPack(
            "ssbu", "portrait", files, lambda d, t: None, lambda: False, gamesDir=gamesDir
        )

        AssetCatalog.RemovePack("ssbu", "portrait", gamesDir=gamesDir)
        assert not os.path.exists(packDir)
        for pack in (BASE_FILES, "../ssbu", "missing"):
            try:
                AssetCatalog.RemovePack("ssbu", pack, gamesDir=gamesDir)
                assert False, f"removed {pack}"
            except ValueError:
                pass
        assert os.path.isdir(os.path.join(gamesDir, "ssbu"))


def TestCancelAndFailureLeaveNothing():
    with tempfile.TemporaryDirectory() as root:
        gamesDir = os.path.join(root, "games")
        parts = MakeSplitArchive(root, "portrait")
        files = Files(parts)
        served = {f["url"]: p for f, p in zip(files, parts)}
        requests.get = lambda url, **kwargs: FakeResponse(served.get(url))

        # Cancelled partway through the first file
        calls = []

        def Cancelled():
            calls.append(1)
            return len(calls) > 2

        assert not AssetCatalog.InstallPack(
            "ssbu", "portrait", files, lambda d, t: None, Cancelled, gamesDir=gamesDir
        )
        assert not os.path.exists(os.path.join(gamesDir, "ssbu", "portrait"))
        assert not os.path.exists(os.path.join(gamesDir, DOWNLOADS_DIR))

        # The second part is missing on the server
        del served[files[1]["url"]]
        try:
            AssetCatalog.InstallPack(
                "ssbu", "portrait", files, lambda d, t: None, lambda: False, gamesDir=gamesDir
            )
            assert False, "a missing part should fail"
        except requests.HTTPError:
            pass
        assert not os.path.exists(os.path.join(gamesDir, "ssbu", "portrait"))
        assert not os.path.exists(os.path.join(gamesDir, DOWNLOADS_DIR))


def TestLogoCache():
    with tempfile.TemporaryDirectory() as root:
        cacheDir = os.path.join(root, "logos")
        fetched = []

        def Fetch(game):
            fetched.append(game)
            return None if game == "offline" else b"new " + game.encode()

        AssetCatalog.FetchLogo = Fetch
        # Not cached: fetched and saved
        assert AssetCatalog.LoadLogo("ssbu", cacheDir) == b"new ssbu"
        assert open(os.path.join(cacheDir, "ssbu.png"), "rb").read() == b"new ssbu"
        # Cached: no fetch
        assert AssetCatalog.LoadLogo("ssbu", cacheDir) == b"new ssbu"
        assert fetched == ["ssbu"]

        # Old: fetched again
        path = os.path.join(cacheDir, "ssbu.png")
        with open(path, "wb") as f:
            f.write(b"old")
        old = time.time() - AssetCatalog.LOGO_CACHE_MAX_AGE - 60
        os.utime(path, (old, old))
        assert AssetCatalog.LoadLogo("ssbu", cacheDir) == b"new ssbu"
        assert fetched == ["ssbu", "ssbu"]

        # Old, and the fetch fails: the old one is better than none
        path = os.path.join(cacheDir, "offline.png")
        with open(path, "wb") as f:
            f.write(b"old")
        os.utime(path, (old, old))
        assert AssetCatalog.LoadLogo("offline", cacheDir) == b"old"
        # Never fetched and the fetch fails: nothing saved, tried again next time
        os.remove(path)
        assert AssetCatalog.LoadLogo("offline", cacheDir) is None
        assert not os.path.exists(path)

        # Game codes that aren't plain file names are never cached
        for game in ("../ssbu", "a/b", ".hidden", ""):
            assert AssetCatalog.LogoCachePath(game, cacheDir) is None
            AssetCatalog.LoadLogo(game, cacheDir)
        assert sorted(os.listdir(cacheDir)) == ["ssbu.png"]
        assert sorted(os.listdir(root)) == ["logos"]


def TestFreeSpace():
    with tempfile.TemporaryDirectory() as root:
        # Works before the games folder exists
        assert AssetCatalog.FreeSpace(os.path.join(root, "not", "yet")) > 0


originalGet = requests.get
originalFetchLogo = AssetCatalog.FetchLogo
try:
    for test in (
        TestStatesAndUpdates,
        TestSearch,
        TestDisplay,
        TestPackFiles,
        TestInstallAndRemove,
        TestCancelAndFailureLeaveNothing,
        TestLogoCache,
        TestFreeSpace,
    ):
        test()
        print(f"{test.__name__}: OK")
finally:
    requests.get = originalGet
    AssetCatalog.FetchLogo = originalFetchLogo
